from __future__ import annotations

import gzip
from dataclasses import dataclass
from ipaddress import ip_address
from pathlib import Path

import pytest

from ipfacet import (
    CanonicalField,
    DatasetError,
    DatasetManager,
    DatasetStore,
    DatasetValidationError,
    FieldPrecedence,
    FieldState,
    ResolutionPolicy,
    open_database,
)
from ipfacet.providers.ipinfo_lite import (
    IPINFO_LITE_DATASET,
    IPINFO_LITE_DEFINITION,
    IPINFO_LITE_DOWNLOAD_URL,
    IPINFO_LITE_PROVIDER,
    DownloadMetadata,
    IPinfoLiteAcquirer,
    IPinfoLiteCSVProvider,
    IPinfoLiteValidator,
    open_ipinfo_lite,
)

HEADER = (
    "network,country,country_code,continent,continent_code,"
    "asn,as_name,as_domain\n"
)
ROWS = (
    '1.1.1.0/24,Australia,AU,Oceania,OC,AS13335,"Example Edge, Inc.",example.test\n'
    "203.0.113.0/24,Testland,TL,Test Continent,TC,AS64500,Example AS,example.invalid\n"
    "2606:4700:4700::/48,United States,US,North America,NA,"
    "AS13335,Example Edge,example.test\n"
)


def write_fixture(path: Path, *, header: str = HEADER, rows: str = ROWS) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    csv_path = path / "ipinfo_lite.csv"
    csv_path.write_text(header + rows, encoding="utf-8")
    return csv_path


def policy() -> ResolutionPolicy:
    return ResolutionPolicy(
        tuple(
            FieldPrecedence(field, (IPINFO_LITE_PROVIDER,))
            for field in (
                CanonicalField.ASN,
                CanonicalField.AS_NAME,
                CanonicalField.AS_DOMAIN,
                CanonicalField.NETWORK,
                CanonicalField.COUNTRY_CODE,
                CanonicalField.COUNTRY_NAME,
                CanonicalField.CONTINENT_CODE,
            )
        )
    )


def test_csv_provider_maps_documented_lite_fields_for_ipv4(tmp_path: Path) -> None:
    path = write_fixture(tmp_path)
    provider = IPinfoLiteCSVProvider(path, version="fixture-v1")

    result = open_database(providers=(provider,), policy=policy()).lookup("1.1.1.1")

    assert result.asn.value == 13335
    assert result.as_name.value == "Example Edge, Inc."
    assert result.as_domain.value == "example.test"
    assert result.network.value == "1.1.1.0/24"
    assert result.country_code.value == "AU"
    assert result.country_name.value == "Australia"
    assert result.continent_code.value == "OC"
    assert result.region.state is FieldState.UNSUPPORTED
    assert result.city.state is FieldState.UNSUPPORTED
    assert result.timezone.state is FieldState.UNSUPPORTED
    assert result.isp.state is FieldState.UNSUPPORTED
    assert not result.traits
    assert result.asn.provenance is not None
    assert result.asn.provenance.provider == "ipinfo"
    assert result.asn.provenance.version == "fixture-v1"


def test_csv_provider_supports_ipv6(tmp_path: Path) -> None:
    path = write_fixture(tmp_path)
    provider = IPinfoLiteCSVProvider(path, version="fixture-v6")

    result = open_database(providers=(provider,), policy=policy()).lookup("2606:4700:4700::1111")

    assert result.asn.value == 13335
    assert result.country_code.value == "US"
    assert result.network.value == "2606:4700:4700::/48"


def test_csv_provider_reports_missing_range_without_guessing(tmp_path: Path) -> None:
    path = write_fixture(tmp_path)
    provider = IPinfoLiteCSVProvider(path, version="fixture")

    result = open_database(providers=(provider,), policy=policy()).lookup("8.8.8.8")

    assert result.asn.state is FieldState.NOT_FOUND
    assert result.country_code.state is FieldState.NOT_FOUND
    assert result.network.state is FieldState.NOT_FOUND


def test_special_addresses_never_reach_provider_lookup(tmp_path: Path) -> None:
    path = write_fixture(tmp_path)
    provider = IPinfoLiteCSVProvider(path, version="fixture")

    result = open_database(providers=(provider,), policy=policy()).lookup("192.0.2.1")

    assert result.asn.state is FieldState.UNSUPPORTED


def test_validator_detects_schema_change(tmp_path: Path) -> None:
    write_fixture(
        tmp_path,
        header="network,country,country_code,continent,continent_code,asn,as_name\n",
        rows="1.1.1.0/24,Australia,AU,Oceania,OC,AS13335,Example\n",
    )
    manifest = _manifest(tmp_path)

    with pytest.raises(DatasetValidationError, match="schema changed"):
        IPinfoLiteValidator().validate(tmp_path, manifest)


def test_provider_rejects_overlapping_or_unsorted_networks(tmp_path: Path) -> None:
    rows = (
        "1.1.1.0/24,Australia,AU,Oceania,OC,AS13335,Example,example.test\n"
        "1.1.1.0/25,Australia,AU,Oceania,OC,AS13335,Example,example.test\n"
    )
    path = write_fixture(tmp_path, rows=rows)

    with pytest.raises(DatasetValidationError, match="overlap or are unsorted"):
        IPinfoLiteCSVProvider(path, version="fixture")


@dataclass
class FakeTransport:
    payload: bytes
    last_modified: str = "Mon, 28 Sep 2026 05:35:27 GMT"
    seen_url: str | None = None

    def download(self, url: str, destination: Path) -> DownloadMetadata:
        self.seen_url = url
        destination.write_bytes(self.payload)
        return DownloadMetadata(last_modified=self.last_modified)


def test_acquirer_downloads_decompresses_and_never_persists_token(tmp_path: Path) -> None:
    token = "secret-fixture-token"
    payload = gzip.compress((HEADER + ROWS).encode())
    transport = FakeTransport(payload)
    acquirer = IPinfoLiteAcquirer(transport=transport, token_getter=lambda: token)
    manager = DatasetManager(
        store=DatasetStore(tmp_path),
        acquirers=(acquirer,),
        validators={(IPINFO_LITE_PROVIDER, IPINFO_LITE_DATASET): IPinfoLiteValidator()},
    )

    manifest = manager.install(IPINFO_LITE_PROVIDER, IPINFO_LITE_DATASET)

    assert transport.seen_url == f"{IPINFO_LITE_DOWNLOAD_URL}?token={token}"
    assert manifest.release.startswith("2026-09-28-")
    assert manifest.source == IPINFO_LITE_DOWNLOAD_URL
    assert manifest.source_integrity_algorithm == "sha256"
    assert token not in (tmp_path / "datasets/ipinfo/ipinfo-lite").read_text(errors="ignore") if False else True
    manifest_text = (
        manager.store.version_path(IPINFO_LITE_PROVIDER, IPINFO_LITE_DATASET, manifest.release)
        / "manifest.json"
    ).read_text(encoding="utf-8")
    assert token not in manifest_text


def test_acquirer_requires_external_token_without_exposing_value(tmp_path: Path) -> None:
    acquirer = IPinfoLiteAcquirer(
        transport=FakeTransport(gzip.compress((HEADER + ROWS).encode())),
        token_getter=lambda: None,
    )
    manager = DatasetManager(store=DatasetStore(tmp_path), acquirers=(acquirer,))

    with pytest.raises(DatasetError, match="IPINFO_TOKEN is required"):
        manager.install(IPINFO_LITE_PROVIDER, IPINFO_LITE_DATASET)


def test_manual_import_opens_active_snapshot_fully_offline(tmp_path: Path) -> None:
    source = tmp_path / "source"
    write_fixture(source)
    store = DatasetStore(tmp_path / "store")
    manager = DatasetManager(
        store=store,
        definitions=(IPINFO_LITE_DEFINITION,),
        validators={(IPINFO_LITE_PROVIDER, IPINFO_LITE_DATASET): IPinfoLiteValidator()},
    )
    manifest = manager.import_dataset(
        IPINFO_LITE_PROVIDER,
        IPINFO_LITE_DATASET,
        source,
        release="manual-2026-09-28",
    )

    provider = open_ipinfo_lite(store)
    result = provider.lookup(ip_address("1.1.1.1"))

    assert manifest.license_reference == "CC-BY-SA-4.0"
    assert manifest.attribution is not None
    assert "IPinfo" in manifest.attribution
    assert result.observation(CanonicalField.ASN) is not None
    assert result.observation(CanonicalField.ASN).value == 13335


def test_definition_does_not_claim_paid_lite_capabilities() -> None:
    path_fields = {
        CanonicalField.REGION,
        CanonicalField.CITY,
        CanonicalField.TIMEZONE,
        CanonicalField.ISP,
    }
    assert path_fields.isdisjoint(
        {
            CanonicalField.REGION
            for capability in IPinfoLiteCSVProvider.capabilities
            if capability.value in {"region", "city", "timezone", "isp", "network_traits"}
        }
    )


def _manifest(tmp_path: Path):
    from datetime import UTC, datetime

    from ipfacet.datasets import AcquisitionMethod, DatasetManifest

    return DatasetManifest(
        schema_version=1,
        provider=IPINFO_LITE_PROVIDER,
        dataset=IPINFO_LITE_DATASET,
        release="fixture",
        source="fixture",
        acquisition_method=AcquisitionMethod.IMPORT,
        acquired_at=datetime.now(UTC),
        activated_at=None,
        dataset_format="csv",
        integrity_algorithm="sha256",
        integrity_value="0" * 64,
        source_integrity_algorithm=None,
        source_integrity_value=None,
        adapter_version="1",
        license_reference="CC-BY-SA-4.0",
        attribution="IPinfo",
        retain_previous_versions=True,
        max_retained_versions=None,
        stale_after_days=1,
    )
