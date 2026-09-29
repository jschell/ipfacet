"""IP2Proxy LITE PX8 offline provider and acquisition helper."""

from __future__ import annotations

import csv
import hashlib
import os
import shutil
import urllib.error
import urllib.request
import zipfile
from array import array
from collections.abc import Callable
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from ipaddress import IPv4Address
from pathlib import Path
from typing import Protocol

from ipfacet.dataset_store import DatasetStore
from ipfacet.datasets import AcquiredDataset, DatasetDefinition, DatasetManifest, RetentionPolicy
from ipfacet.exceptions import DatasetError, DatasetValidationError
from ipfacet.models import CanonicalField, FieldState, IPAddress, NetworkTrait
from ipfacet.provider import (
    Capability,
    ProviderIdentity,
    ProviderMetadata,
    ProviderObservation,
    ProviderResult,
)

IP2PROXY_LITE_PROVIDER = "ip2proxy"
IP2PROXY_LITE_DATASET = "ip2proxy-lite-px8"
IP2PROXY_LITE_FILENAME = "IP2PROXY-LITE-PX8.IPV6.CSV"
IP2PROXY_LITE_DOWNLOAD_URL = "https://www.ip2location.com/download"
IP2PROXY_LITE_LICENSE = "https://lite.ip2location.com/data-license"
IP2PROXY_LITE_ATTRIBUTION = (
    "IPFacet uses the IP2Proxy LITE database for IP geolocation "
    "(https://www.ip2location.com)."
)
IP2PROXY_LITE_SCHEMA = (
    "ip_from",
    "ip_to",
    "proxy_type",
    "country_code",
    "country_name",
    "region_name",
    "city_name",
    "isp",
    "domain",
    "usage_type",
    "asn",
    "as",
    "last_seen",
)

IP2PROXY_LITE_DEFINITION = DatasetDefinition(
    provider=IP2PROXY_LITE_PROVIDER,
    dataset=IP2PROXY_LITE_DATASET,
    dataset_format="csv-ipv6",
    adapter_version="1",
    license_reference=IP2PROXY_LITE_LICENSE,
    attribution=IP2PROXY_LITE_ATTRIBUTION,
    retention=RetentionPolicy(retain_previous_versions=True),
    stale_after_days=31,
)

_IPV4_MAPPED_BASE = 0xFFFF << 32


@dataclass(frozen=True, slots=True)
class DownloadMetadata:
    """Sanitized metadata returned by the acquisition transport."""

    last_modified: str | None = None


class DownloadTransport(Protocol):
    """Injectable transport so CI does not require provider credentials or network."""

    def download(self, url: str, destination: Path) -> DownloadMetadata: ...


class UrllibDownloadTransport:
    """HTTPS transport with sanitized failures."""

    def download(self, url: str, destination: Path) -> DownloadMetadata:
        try:
            with urllib.request.urlopen(url, timeout=180) as response:
                with destination.open("wb") as output:
                    shutil.copyfileobj(response, output)
                return DownloadMetadata(last_modified=response.headers.get("Last-Modified"))
        except (urllib.error.URLError, TimeoutError, OSError):
            raise DatasetError("IP2Proxy LITE database download failed") from None


class IP2ProxyLiteAcquirer:
    """Acquire a PX8 LITE IPv6 CSV package using external account credentials."""

    definition = IP2PROXY_LITE_DEFINITION

    def __init__(
        self,
        *,
        transport: DownloadTransport | None = None,
        token_getter: Callable[[], str | None] | None = None,
        code_getter: Callable[[], str | None] | None = None,
    ) -> None:
        self._transport = transport or UrllibDownloadTransport()
        self._token_getter = token_getter or (
            lambda: os.environ.get("IP2LOCATION_DOWNLOAD_TOKEN")
        )
        self._code_getter = code_getter or (
            lambda: os.environ.get("IP2PROXY_LITE_FILE_CODE")
        )

    def acquire(self, destination: Path) -> AcquiredDataset:
        token = self._token_getter()
        code = self._code_getter()
        if token is None or not token.strip():
            raise DatasetError(
                "IP2LOCATION_DOWNLOAD_TOKEN is required to download IP2Proxy LITE; "
                "use datasets import for an air-gapped/manual snapshot"
            )
        if code is None or not code.strip():
            raise DatasetError(
                "IP2PROXY_LITE_FILE_CODE is required; use the PX8 LITE IPv6 CSV "
                "download code shown in the IP2Location account area"
            )

        archive = destination / "ip2proxy-lite-px8.zip"
        metadata = self._transport.download(
            f"{IP2PROXY_LITE_DOWNLOAD_URL}?token={token}&file={code}",
            archive,
        )
        digest = _file_sha256(archive)
        try:
            with zipfile.ZipFile(archive) as package:
                names = package.namelist()
                matches = [
                    name
                    for name in names
                    if Path(name).name.upper() == IP2PROXY_LITE_FILENAME
                ]
                if len(matches) != 1:
                    raise DatasetValidationError(
                        "IP2Proxy LITE archive must contain exactly one "
                        f"{IP2PROXY_LITE_FILENAME}"
                    )
                source = package.open(matches[0])
                with source, (destination / IP2PROXY_LITE_FILENAME).open("wb") as output:
                    shutil.copyfileobj(source, output)
        except (zipfile.BadZipFile, OSError) as exc:
            raise DatasetValidationError("downloaded IP2Proxy LITE ZIP is invalid") from exc
        archive.unlink()

        release_date = _release_date(metadata.last_modified)
        release = f"{release_date}-{digest[:16]}" if release_date else f"sha256-{digest[:16]}"
        return AcquiredDataset(
            release=release,
            source=IP2PROXY_LITE_DOWNLOAD_URL,
            source_integrity_algorithm="sha256",
            source_integrity_value=digest,
            source_integrity_verified=True,
        )


@dataclass(frozen=True, slots=True)
class _PX8Record:
    ip_from: int
    ip_to: int
    proxy_type: str | None
    country_code: str | None
    country_name: str | None
    region_name: str | None
    city_name: str | None
    isp: str | None
    domain: str | None
    usage_type: str | None
    asn: int | None
    as_name: str | None
    last_seen: int | None


class _EndOffsetIndex:
    """Compact sorted end-address index for the provider's IPv6 numeric CSV."""

    def __init__(self) -> None:
        self.end_hi = array("Q")
        self.end_lo = array("Q")
        self.offset = array("Q")
        self._previous_end = -1

    def add(self, record: _PX8Record, offset: int) -> None:
        if record.ip_from > record.ip_to:
            raise DatasetValidationError("IP2Proxy LITE range start exceeds range end")
        if record.ip_from <= self._previous_end:
            raise DatasetValidationError("IP2Proxy LITE ranges overlap or are unsorted")
        hi, lo = divmod(record.ip_to, 1 << 64)
        self.end_hi.append(hi)
        self.end_lo.append(lo)
        self.offset.append(offset)
        self._previous_end = record.ip_to

    def find(self, value: int) -> int | None:
        hi, lo = divmod(value, 1 << 64)
        low = 0
        high = len(self.end_hi)
        while low < high:
            middle = (low + high) // 2
            if (self.end_hi[middle], self.end_lo[middle]) < (hi, lo):
                low = middle + 1
            else:
                high = middle
        if low >= len(self.offset):
            return None
        return self.offset[low]


class IP2ProxyLitePX8Provider:
    """Offline PX8 LITE provider; LITE proxy semantics are limited to PUB."""

    capabilities = frozenset(
        {
            Capability.ASN,
            Capability.AS_ORGANIZATION,
            Capability.COUNTRY,
            Capability.REGION,
            Capability.CITY,
            Capability.ISP,
            Capability.NETWORK_TRAITS,
        }
    )

    def __init__(self, path: Path, *, version: str) -> None:
        self._path = path
        self.identity = ProviderIdentity(
            provider=IP2PROXY_LITE_PROVIDER,
            dataset=IP2PROXY_LITE_DATASET,
            version=version,
            dataset_format="csv-ipv6",
        )
        self._index = self._build_index()

    def _build_index(self) -> _EndOffsetIndex:
        index = _EndOffsetIndex()
        try:
            with self._path.open("rb") as handle:
                while True:
                    offset = handle.tell()
                    line = handle.readline()
                    if not line:
                        break
                    row = next(csv.reader([line.decode("utf-8")]))
                    record = _parse_record(row)
                    index.add(record, offset)
        except (OSError, UnicodeError, csv.Error, ValueError) as exc:
            if isinstance(exc, DatasetValidationError):
                raise
            raise DatasetValidationError("IP2Proxy LITE CSV index build failed") from exc
        if not index.offset:
            raise DatasetValidationError("IP2Proxy LITE CSV contains no records")
        return index

    def lookup(self, ip: IPAddress) -> ProviderResult:
        numeric = _provider_ip_number(ip)
        offset = self._index.find(numeric)
        if offset is None:
            return ProviderResult(ip=ip, identity=self.identity, fields=self._not_found_fields())

        try:
            with self._path.open("rb") as handle:
                handle.seek(offset)
                row = next(csv.reader([handle.readline().decode("utf-8")]))
            record = _parse_record(row)
        except (OSError, UnicodeError, csv.Error, ValueError):
            return ProviderResult(
                ip=ip,
                identity=self.identity,
                fields=self._error_fields("IP2Proxy LITE CSV lookup failed"),
            )

        if not (record.ip_from <= numeric <= record.ip_to):
            return ProviderResult(ip=ip, identity=self.identity, fields=self._not_found_fields())

        values: dict[CanonicalField, int | str | None] = {
            CanonicalField.ASN: record.asn,
            CanonicalField.AS_NAME: record.as_name,
            CanonicalField.COUNTRY_CODE: record.country_code,
            CanonicalField.COUNTRY_NAME: record.country_name,
            CanonicalField.REGION: record.region_name,
            CanonicalField.CITY: record.city_name,
            CanonicalField.ISP: record.isp,
        }
        semantics = {
            CanonicalField.ASN: "IP2Proxy LITE PX8 autonomous system number",
            CanonicalField.AS_NAME: "IP2Proxy LITE PX8 autonomous system name",
            CanonicalField.COUNTRY_CODE: "IP2Proxy LITE PX8 ISO 3166 country code",
            CanonicalField.COUNTRY_NAME: "IP2Proxy LITE PX8 country name",
            CanonicalField.REGION: "IP2Proxy LITE PX8 region or state",
            CanonicalField.CITY: "IP2Proxy LITE PX8 city",
            CanonicalField.ISP: "IP2Proxy LITE PX8 ISP or company name",
        }
        observations: list[ProviderObservation] = []
        for field, value in values.items():
            if value is None:
                observations.append(ProviderObservation(field=field, state=FieldState.NOT_FOUND))
            else:
                observations.append(
                    ProviderObservation(
                        field=field,
                        state=FieldState.PRESENT,
                        value=value,
                        semantics=semantics[field],
                    )
                )

        traits = _traits(record)
        metadata = (
            ProviderMetadata("proxy_type", record.proxy_type),
            ProviderMetadata("usage_type", record.usage_type),
            ProviderMetadata("domain", record.domain),
            ProviderMetadata("last_seen_days", record.last_seen),
        )
        return ProviderResult(
            ip=ip,
            identity=self.identity,
            fields=tuple(observations),
            traits=traits,
            metadata=metadata,
        )

    @staticmethod
    def _not_found_fields() -> tuple[ProviderObservation, ...]:
        return tuple(
            ProviderObservation(field=field, state=FieldState.NOT_FOUND)
            for field in _SUPPORTED_FIELDS
        )

    @staticmethod
    def _error_fields(message: str) -> tuple[ProviderObservation, ...]:
        return tuple(
            ProviderObservation(field=field, state=FieldState.LOOKUP_ERROR, error=message)
            for field in _SUPPORTED_FIELDS
        )


_SUPPORTED_FIELDS = (
    CanonicalField.ASN,
    CanonicalField.AS_NAME,
    CanonicalField.COUNTRY_CODE,
    CanonicalField.COUNTRY_NAME,
    CanonicalField.REGION,
    CanonicalField.CITY,
    CanonicalField.ISP,
)

_USAGE_TRAITS = {
    "DCH": NetworkTrait.HOSTING,
    "CDN": NetworkTrait.CDN,
    "MOB": NetworkTrait.MOBILE,
    "EDU": NetworkTrait.EDUCATION,
    "GOV": NetworkTrait.GOVERNMENT,
}


class IP2ProxyLiteValidator:
    """Validate PX8 LITE's exact 13-column numeric range schema before activation."""

    def validate(self, dataset_path: Path, manifest: DatasetManifest) -> None:
        path = dataset_path / IP2PROXY_LITE_FILENAME
        if not path.is_file():
            raise DatasetValidationError(f"missing {IP2PROXY_LITE_FILENAME}")
        IP2ProxyLitePX8Provider(path, version=manifest.release)


def open_ip2proxy_lite(store: DatasetStore | None = None) -> IP2ProxyLitePX8Provider:
    """Open the active installed PX8 LITE IPv6 CSV for fully offline lookup."""
    selected = store or DatasetStore()
    manifest = selected.active_manifest(IP2PROXY_LITE_PROVIDER, IP2PROXY_LITE_DATASET)
    if manifest.dataset_format != "csv-ipv6":
        raise DatasetValidationError(
            f"unsupported IP2Proxy LITE installed format: {manifest.dataset_format}"
        )
    path = (
        selected.version_path(
            IP2PROXY_LITE_PROVIDER,
            IP2PROXY_LITE_DATASET,
            manifest.release,
        )
        / IP2PROXY_LITE_FILENAME
    )
    return IP2ProxyLitePX8Provider(path, version=manifest.release)


def _parse_record(row: list[str]) -> _PX8Record:
    if len(row) != len(IP2PROXY_LITE_SCHEMA):
        raise DatasetValidationError(
            f"IP2Proxy LITE PX8 row must contain {len(IP2PROXY_LITE_SCHEMA)} columns"
        )
    try:
        ip_from = int(row[0])
        ip_to = int(row[1])
        if ip_from < 0 or ip_to >= 1 << 128:
            raise ValueError("IP range outside IPv6 numeric space")
        asn = _optional_int(row[10])
        last_seen = _optional_int(row[12])
        if last_seen is not None and last_seen < 0:
            raise ValueError("negative last_seen")
        return _PX8Record(
            ip_from=ip_from,
            ip_to=ip_to,
            proxy_type=_optional_text(row[2]),
            country_code=_optional_text(row[3]),
            country_name=_optional_text(row[4]),
            region_name=_optional_text(row[5]),
            city_name=_optional_text(row[6]),
            isp=_optional_text(row[7]),
            domain=_optional_text(row[8]),
            usage_type=_optional_text(row[9]),
            asn=asn,
            as_name=_optional_text(row[11]),
            last_seen=last_seen,
        )
    except ValueError as exc:
        raise DatasetValidationError("invalid IP2Proxy LITE PX8 record") from exc


def _traits(record: _PX8Record) -> frozenset[NetworkTrait]:
    traits: set[NetworkTrait] = set()
    if record.proxy_type == "PUB":
        traits.add(NetworkTrait.PROXY)
    if record.usage_type is not None:
        for code in record.usage_type.split("/"):
            trait = _USAGE_TRAITS.get(code)
            if trait is not None:
                traits.add(trait)
    return frozenset(traits)


def _provider_ip_number(ip: IPAddress) -> int:
    if isinstance(ip, IPv4Address):
        return _IPV4_MAPPED_BASE + int(ip)
    return int(ip)


def _optional_text(value: str) -> str | None:
    return None if value in {"", "-"} else value


def _optional_int(value: str) -> int | None:
    return None if value in {"", "-"} else int(value)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _release_date(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return parsed.date().isoformat()
