from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv6Address, ip_address
from pathlib import Path

import pytest

from ipfacet import (
    CanonicalField,
    Capability,
    DatasetError,
    DatasetManager,
    DatasetStore,
    DatasetValidationError,
    FieldPrecedence,
    FieldState,
    NetworkTrait,
    ResolutionPolicy,
    open_database,
)
from ipfacet.providers.ip2proxy_lite import (
    IP2PROXY_LITE_DATASET,
    IP2PROXY_LITE_DEFINITION,
    IP2PROXY_LITE_DOWNLOAD_URL,
    IP2PROXY_LITE_FILENAME,
    IP2PROXY_LITE_PROVIDER,
    DownloadMetadata,
    IP2ProxyLiteAcquirer,
    IP2ProxyLitePX8Provider,
    IP2ProxyLiteValidator,
    open_ip2proxy_lite,
)

MAPPED_BASE = int(IPv6Address("::ffff:0.0.0.0"))


def row(
    start: int,
    end: int,
    *,
    proxy_type: str = "-",
    country_code: str = "US",
    country_name: str = "United States",
    region: str = "Washington",
    city: str = "Seattle",
    isp: str = "Example Network",
    domain: str = "example.test",
    usage_type: str = "ISP",
    asn: str = "64500",
    as_name: str = "Example AS",
    last_seen: str = "-",
) -> str:
    values = (
        str(start),
        str(end),
        proxy_type,
        country_code,
        country_name,
        region,
        city,
        isp,
        domain,
        usage_type,
        asn,
        as_name,
        last_seen,
    )
    output = io.StringIO()
    csv.writer(output, lineterminator="\n").writerow(values)
    return output.getvalue()


def write_fixture(path: Path, rows: str) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    target = path / IP2PROXY_LITE_FILENAME
    target.write_text(rows, encoding="utf-8")
    return target


def policy() -> ResolutionPolicy:
    return ResolutionPolicy(
        tuple(
            FieldPrecedence(field, (IP2PROXY_LITE_PROVIDER,))
            for field in (
                CanonicalField.ASN,
                CanonicalField.AS_NAME,
                CanonicalField.COUNTRY_CODE,
                CanonicalField.COUNTRY_NAME,
                CanonicalField.REGION,
                CanonicalField.CITY,
                CanonicalField.ISP,
            )
        )
    )


def test_px8_maps_documented_open_proxy_sample_semantics(tmp_path: Path) -> None:
    sample_ip = 16782178
    path = write_fixture(
        tmp_path,
        row(
            MAPPED_BASE + sample_ip,
            MAPPED_BASE + sample_ip,
            proxy_type="PUB",
            country_code="JP",
            country_name="Japan",
            region="Tokyo",
            city="Tokyo",
            isp="I2TS Inc.",
            domain="mediaindex.co.jp",
            usage_type="DCH",
            asn="-",
            as_name="-",
            last_seen="30",
        ),
    )
    provider = IP2ProxyLitePX8Provider(path, version="documented-sample")

    result = open_database(providers=(provider,), policy=policy()).lookup("1.0.19.98")

    assert result.country_code.value == "JP"
    assert result.country_name.value == "Japan"
    assert result.region.value == "Tokyo"
    assert result.city.value == "Tokyo"
    assert result.isp.value == "I2TS Inc."
    assert result.asn.state is FieldState.NOT_FOUND
    assert result.as_name.state is FieldState.NOT_FOUND
    assert result.traits == frozenset({NetworkTrait.PROXY, NetworkTrait.HOSTING})


def test_px8_maps_asn_and_multi_usage_type_without_inventing_vpn(tmp_path: Path) -> None:
    sample_ip = 16811364
    path = write_fixture(
        tmp_path,
        row(
            MAPPED_BASE + sample_ip,
            MAPPED_BASE + sample_ip,
            proxy_type="PUB",
            country_code="TH",
            country_name="Thailand",
            region="Krung Thep Maha Nakhon",
            city="Bangkok",
            isp="TOT Public Company Limited",
            domain="tot.co.th",
            usage_type="ISP/MOB",
            asn="23969",
            as_name="TOT Public Company Limited",
            last_seen="1",
        ),
    )
    provider = IP2ProxyLitePX8Provider(path, version="documented-sample")

    result = open_database(providers=(provider,), policy=policy()).lookup("1.0.133.100")

    assert result.asn.value == 23969
    assert result.as_name.value == "TOT Public Company Limited"
    assert result.traits == frozenset({NetworkTrait.PROXY, NetworkTrait.MOBILE})
    assert NetworkTrait.VPN not in result.traits
    assert NetworkTrait.TOR not in result.traits


def test_px8_preserves_vendor_classification_as_metadata(tmp_path: Path) -> None:
    ip = MAPPED_BASE + 0x08080808
    path = write_fixture(
        tmp_path,
        row(
            ip,
            ip,
            proxy_type="PUB",
            usage_type="CDN",
            domain="resolver.example",
            last_seen="7",
        ),
    )
    provider = IP2ProxyLitePX8Provider(path, version="fixture")

    result = provider.lookup(ip_address("8.8.8.8"))
    metadata = {item.key: item.value for item in result.metadata}

    assert metadata == {
        "proxy_type": "PUB",
        "usage_type": "CDN",
        "domain": "resolver.example",
        "last_seen_days": 7,
    }
    assert result.traits == frozenset({NetworkTrait.PROXY, NetworkTrait.CDN})


def test_px8_non_proxy_record_does_not_gain_proxy_privacy_traits(tmp_path: Path) -> None:
    ip = MAPPED_BASE + 0x09090909
    path = write_fixture(tmp_path, row(ip, ip, proxy_type="-", usage_type="ISP"))
    provider = IP2ProxyLitePX8Provider(path, version="fixture")

    result = open_database(providers=(provider,), policy=policy()).lookup("9.9.9.9")

    assert result.traits == frozenset()
    assert NetworkTrait.PROXY not in result.traits
    assert NetworkTrait.VPN not in result.traits
    assert NetworkTrait.TOR not in result.traits


def test_px8_usage_traits_are_independent_factual_tags(tmp_path: Path) -> None:
    codes = {
        "DCH": NetworkTrait.HOSTING,
        "CDN": NetworkTrait.CDN,
        "MOB": NetworkTrait.MOBILE,
        "EDU": NetworkTrait.EDUCATION,
        "GOV": NetworkTrait.GOVERNMENT,
    }
    rows = ""
    base = MAPPED_BASE + 0x0A000001
    for index, code in enumerate(codes):
        rows += row(base + index, base + index, usage_type=code)
    path = write_fixture(tmp_path, rows)
    provider = IP2ProxyLitePX8Provider(path, version="fixture")

    for index, expected in enumerate(codes.values()):
        address = IPv4Address(0x0A000001 + index)
        result = provider.lookup(address)
        assert result.traits == frozenset({expected})


def test_px8_supports_native_ipv6(tmp_path: Path) -> None:
    start = int(IPv6Address("2606:4700:4700::"))
    end = int(IPv6Address("2606:4700:4700::ffff"))
    path = write_fixture(
        tmp_path,
        row(
            start,
            end,
            country_code="US",
            country_name="United States",
            region="California",
            city="San Francisco",
            usage_type="CDN",
            asn="13335",
            as_name="Example Edge",
        ),
    )
    provider = IP2ProxyLitePX8Provider(path, version="ipv6")

    result = open_database(providers=(provider,), policy=policy()).lookup(
        "2606:4700:4700::1111"
    )

    assert result.asn.value == 13335
    assert result.country_code.value == "US"
    assert result.traits == frozenset({NetworkTrait.CDN})


def test_px8_missing_range_is_not_found(tmp_path: Path) -> None:
    ip = MAPPED_BASE + 0x01010101
    path = write_fixture(tmp_path, row(ip, ip))
    provider = IP2ProxyLitePX8Provider(path, version="fixture")

    result = open_database(providers=(provider,), policy=policy()).lookup("8.8.8.8")

    assert result.asn.state is FieldState.NOT_FOUND
    assert result.country_code.state is FieldState.NOT_FOUND
    assert not result.traits


def test_px8_rejects_non_pub_proxy_type_to_prevent_lite_overclaim(tmp_path: Path) -> None:
    ip = MAPPED_BASE + 0x01010101
    path = write_fixture(tmp_path, row(ip, ip, proxy_type="VPN"))

    with pytest.raises(DatasetValidationError, match="invalid IP2Proxy LITE PX8 record"):
        IP2ProxyLitePX8Provider(path, version="fixture")


def test_px8_rejects_wrong_column_count(tmp_path: Path) -> None:
    path = write_fixture(tmp_path, '"1","2","PUB"\n')

    with pytest.raises(DatasetValidationError, match="13 columns"):
        IP2ProxyLitePX8Provider(path, version="fixture")


def test_px8_rejects_overlapping_or_unsorted_ranges(tmp_path: Path) -> None:
    base = MAPPED_BASE + 0x01010100
    path = write_fixture(
        tmp_path,
        row(base, base + 10) + row(base + 5, base + 20),
    )

    with pytest.raises(DatasetValidationError, match="overlap or are unsorted"):
        IP2ProxyLitePX8Provider(path, version="fixture")


def test_px8_does_not_claim_threat_or_paid_privacy_capabilities() -> None:
    assert Capability.NETWORK_TRAITS in IP2ProxyLitePX8Provider.capabilities
    assert Capability.AS_DOMAIN not in IP2ProxyLitePX8Provider.capabilities
    assert Capability.PREFIX not in IP2ProxyLitePX8Provider.capabilities
    assert Capability.TIMEZONE not in IP2ProxyLitePX8Provider.capabilities


@dataclass
class FakeTransport:
    payload: bytes
    last_modified: str = "Tue, 29 Sep 2026 05:35:27 GMT"
    seen_url: str | None = None

    def download(self, url: str, destination: Path) -> DownloadMetadata:
        self.seen_url = url
        destination.write_bytes(self.payload)
        return DownloadMetadata(last_modified=self.last_modified)


def zip_payload(rows: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as package:
        package.writestr(IP2PROXY_LITE_FILENAME, rows)
    return output.getvalue()


def test_acquirer_uses_account_code_without_persisting_credentials(tmp_path: Path) -> None:
    token = "fixture-download-token"
    code = "fixture-px8-ipv6-code"
    ip = MAPPED_BASE + 0x01010101
    transport = FakeTransport(zip_payload(row(ip, ip)))
    acquirer = IP2ProxyLiteAcquirer(
        transport=transport,
        token_getter=lambda: token,
        code_getter=lambda: code,
    )
    manager = DatasetManager(
        store=DatasetStore(tmp_path),
        acquirers=(acquirer,),
        validators={
            (IP2PROXY_LITE_PROVIDER, IP2PROXY_LITE_DATASET): IP2ProxyLiteValidator()
        },
    )

    manifest = manager.install(IP2PROXY_LITE_PROVIDER, IP2PROXY_LITE_DATASET)

    assert transport.seen_url == (
        f"{IP2PROXY_LITE_DOWNLOAD_URL}?token={token}&file={code}"
    )
    assert manifest.release.startswith("2026-09-29-")
    assert manifest.source == IP2PROXY_LITE_DOWNLOAD_URL
    manifest_text = (
        manager.store.version_path(
            IP2PROXY_LITE_PROVIDER,
            IP2PROXY_LITE_DATASET,
            manifest.release,
        )
        / "manifest.json"
    ).read_text(encoding="utf-8")
    assert token not in manifest_text
    assert code not in manifest_text


@pytest.mark.parametrize(
    ("token", "code", "message"),
    [
        (None, "code", "IP2LOCATION_DOWNLOAD_TOKEN is required"),
        ("token", None, "IP2PROXY_LITE_FILE_CODE is required"),
    ],
)
def test_acquirer_requires_external_account_values(
    tmp_path: Path,
    token: str | None,
    code: str | None,
    message: str,
) -> None:
    acquirer = IP2ProxyLiteAcquirer(
        transport=FakeTransport(b"unused"),
        token_getter=lambda: token,
        code_getter=lambda: code,
    )
    manager = DatasetManager(store=DatasetStore(tmp_path), acquirers=(acquirer,))

    with pytest.raises(DatasetError, match=message):
        manager.install(IP2PROXY_LITE_PROVIDER, IP2PROXY_LITE_DATASET)


def test_manual_import_opens_active_snapshot_offline(tmp_path: Path) -> None:
    source = tmp_path / "source"
    ip = MAPPED_BASE + 0x01010101
    write_fixture(source, row(ip, ip, proxy_type="PUB", usage_type="DCH"))
    store = DatasetStore(tmp_path / "store")
    manager = DatasetManager(
        store=store,
        definitions=(IP2PROXY_LITE_DEFINITION,),
        validators={
            (IP2PROXY_LITE_PROVIDER, IP2PROXY_LITE_DATASET): IP2ProxyLiteValidator()
        },
    )
    manifest = manager.import_dataset(
        IP2PROXY_LITE_PROVIDER,
        IP2PROXY_LITE_DATASET,
        source,
        release="manual-2026-09",
    )

    provider = open_ip2proxy_lite(store)
    result = provider.lookup(ip_address("1.1.1.1"))

    assert manifest.license_reference == "https://lite.ip2location.com/data-license"
    assert manifest.attribution is not None
    assert "IP2Proxy LITE" in manifest.attribution
    assert result.traits == frozenset({NetworkTrait.PROXY, NetworkTrait.HOSTING})
