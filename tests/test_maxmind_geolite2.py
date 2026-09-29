from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from ipaddress import ip_address
from pathlib import Path

import pytest

from ipfacet import (
    CanonicalField,
    DatasetManager,
    DatasetStore,
    DatasetValidationError,
    FieldPrecedence,
    FieldState,
    ResolutionPolicy,
    open_database,
)
from ipfacet.provider import ProviderObservation, ProviderResult
from ipfacet.providers.ipinfo_lite import IPinfoLiteCSVProvider
from ipfacet.providers.maxmind_geolite2 import (
    FILES,
    MAXMIND_DATASET,
    MAXMIND_DEFINITION,
    MAXMIND_PROVIDER,
    MAXMIND_URL,
    DownloadMetadata,
    MaxMindGeoLite2Acquirer,
    MaxMindGeoLite2CSVProvider,
    MaxMindGeoLite2Validator,
    open_maxmind_geolite2,
)

HEADER = "network,autonomous_system_number,autonomous_system_organization\n"
V4 = "1.1.1.0/24,64500,MaxMind Example\n8.8.8.0/24,,\n"
V6 = "2606:4700::/32,64501,IPv6 Example\n"


def fixture(path: Path, v4: str = V4, v6: str = V6) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    for name, rows in zip(FILES, (v4, v6), strict=True):
        (path / name).write_text(HEADER + rows)
    return path


def manager(path: Path) -> DatasetManager:
    return DatasetManager(
        store=DatasetStore(path),
        definitions=(MAXMIND_DEFINITION,),
        validators={(MAXMIND_PROVIDER, MAXMIND_DATASET): MaxMindGeoLite2Validator()},
    )


def observation(result: ProviderResult, field: CanonicalField) -> ProviderObservation:
    value = result.observation(field)
    assert value is not None
    return value


def test_offline_ipv4_ipv6_and_missing(tmp_path: Path) -> None:
    source = fixture(tmp_path / "source")
    service = manager(tmp_path / "store")
    manifest = service.import_dataset(MAXMIND_PROVIDER, MAXMIND_DATASET, source, release="20260929")
    provider = open_maxmind_geolite2(service.store)
    assert observation(provider.lookup(ip_address("1.1.1.1")), CanonicalField.ASN).value == 64500
    assert (
        observation(provider.lookup(ip_address("2606:4700::1")), CanonicalField.ASN).value == 64501
    )
    assert (
        observation(provider.lookup(ip_address("8.8.8.8")), CanonicalField.ASN).state
        is FieldState.NOT_FOUND
    )
    assert (
        observation(provider.lookup(ip_address("9.9.9.9")), CanonicalField.NETWORK).state
        is FieldState.NOT_FOUND
    )
    assert (
        observation(provider.lookup(ip_address("1.1.1.1")), CanonicalField.AS_NAME).value
        == "MaxMind Example"
    )
    assert manifest.attribution is not None and "MaxMind" in manifest.attribution
    assert manifest.retain_previous_versions


def test_invalid_update_does_not_replace_active_and_old_release_is_retained(tmp_path: Path) -> None:
    service = manager(tmp_path / "store")
    service.import_dataset(
        MAXMIND_PROVIDER, MAXMIND_DATASET, fixture(tmp_path / "first"), release="first"
    )
    invalid = fixture(tmp_path / "invalid", v4="1.1.1.0/24,not-an-asn,Invalid\n")
    with pytest.raises(DatasetValidationError):
        service.import_dataset(MAXMIND_PROVIDER, MAXMIND_DATASET, invalid, release="bad")
    assert service.status(MAXMIND_PROVIDER, MAXMIND_DATASET).release == "first"
    service.import_dataset(
        MAXMIND_PROVIDER,
        MAXMIND_DATASET,
        fixture(tmp_path / "second", v4="1.1.1.0/24,64502,New\n"),
        release="second",
    )
    assert {m.release for m in service.store.list_manifests(MAXMIND_PROVIDER, MAXMIND_DATASET)} == {
        "first",
        "second",
    }
    assert (
        observation(
            open_maxmind_geolite2(service.store).lookup(ip_address("1.1.1.1")),
            CanonicalField.ASN,
        ).value
        == 64502
    )


def test_schema_change_and_wrong_family_rejected(tmp_path: Path) -> None:
    source = fixture(tmp_path / "source")
    (source / FILES[0]).write_text("network,asn,name\n1.1.1.0/24,1,A\n")
    with pytest.raises(DatasetValidationError, match="schema changed"):
        manager(tmp_path / "store").import_dataset(
            MAXMIND_PROVIDER, MAXMIND_DATASET, source, release="bad"
        )
    fixture(source, v6="1.1.1.0/24,1,A\n")
    with pytest.raises(DatasetValidationError, match="wrong family"):
        manager(tmp_path / "store").import_dataset(
            MAXMIND_PROVIDER, MAXMIND_DATASET, source, release="bad2"
        )


def test_ipinfo_disagreement_preserves_both_observations(tmp_path: Path) -> None:
    maxmind = MaxMindGeoLite2CSVProvider(fixture(tmp_path / "maxmind"), version="mm-1")
    ipinfo_path = tmp_path / "ipinfo.csv"
    ipinfo_path.write_text(
        "network,country,country_code,continent,continent_code,asn,as_name,as_domain\n"
        "1.1.1.0/24,Australia,AU,Oceania,OC,AS13335,IPinfo Example,example.test\n"
    )
    ipinfo = IPinfoLiteCSVProvider(ipinfo_path, version="ipinfo-1")
    policy = ResolutionPolicy(
        tuple(
            FieldPrecedence(field, ("ipinfo", "maxmind"))
            for field in (CanonicalField.ASN, CanonicalField.AS_NAME, CanonicalField.NETWORK)
        )
        + tuple(
            FieldPrecedence(field, ("ipinfo",))
            for field in (
                CanonicalField.AS_DOMAIN,
                CanonicalField.COUNTRY_CODE,
                CanonicalField.COUNTRY_NAME,
                CanonicalField.CONTINENT_CODE,
            )
        )
    )
    result = open_database(providers=(ipinfo, maxmind), policy=policy).lookup("1.1.1.1")
    assert result.asn.state is FieldState.CONFLICT
    assert result.asn.value == 13335
    assert result.asn.provenance is not None and result.asn.provenance.provider == "ipinfo"
    assert len(result.asn.observations) == 2
    assert {item.provenance.provider for item in result.asn.observations} == {"ipinfo", "maxmind"}


@dataclass
class FakeTransport:
    payload: bytes
    credentials: tuple[str, str] | None = None
    url: str | None = None

    def download(self, url: str, destination: Path, account: str, key: str) -> DownloadMetadata:
        self.url = url
        self.credentials = (account, key)
        destination.write_bytes(self.payload)
        return DownloadMetadata()


def test_explicit_acquisition_keeps_credentials_out_of_manifest(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, rows in zip(FILES, (V4, V6), strict=True):
            archive.writestr(f"GeoLite2-ASN-CSV_20260929/{name}", HEADER + rows)
    transport = FakeTransport(buffer.getvalue())
    acquirer = MaxMindGeoLite2Acquirer(
        transport=transport, credential_getter=lambda: ("12345", "secret-test-key")
    )
    service = DatasetManager(
        store=DatasetStore(tmp_path),
        acquirers=(acquirer,),
        validators={(MAXMIND_PROVIDER, MAXMIND_DATASET): MaxMindGeoLite2Validator()},
    )
    manifest = service.install(MAXMIND_PROVIDER, MAXMIND_DATASET)
    assert manifest.release.startswith("20260929-")
    assert transport.url == MAXMIND_URL
    assert transport.credentials == ("12345", "secret-test-key")
    saved = (
        service.store.version_path(MAXMIND_PROVIDER, MAXMIND_DATASET, manifest.release)
        / "manifest.json"
    ).read_text()
    assert "secret-test-key" not in saved and "12345" not in saved
