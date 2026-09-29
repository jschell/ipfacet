"""IPinfo Lite offline provider and acquisition helper."""

from __future__ import annotations

import csv
import gzip
import hashlib
import os
import shutil
import urllib.error
import urllib.request
from array import array
from bisect import bisect_right
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from ipaddress import IPv4Address, IPv4Network, IPv6Network, ip_network
from pathlib import Path
from typing import Protocol

from ipfacet.dataset_store import DatasetStore
from ipfacet.datasets import AcquiredDataset, DatasetDefinition, DatasetManifest, RetentionPolicy
from ipfacet.exceptions import DatasetError, DatasetValidationError
from ipfacet.models import CanonicalField, FieldState, IPAddress
from ipfacet.provider import Capability, ProviderIdentity, ProviderObservation, ProviderResult

IPINFO_LITE_PROVIDER = "ipinfo"
IPINFO_LITE_DATASET = "ipinfo-lite"
IPINFO_LITE_FILENAME = "ipinfo_lite.csv"
IPINFO_LITE_DOWNLOAD_URL = "https://ipinfo.io/data/ipinfo_lite.csv.gz"
IPINFO_LITE_LICENSE = "CC-BY-SA-4.0"
IPINFO_LITE_ATTRIBUTION = "IP address data powered by IPinfo (https://ipinfo.io)"
IPINFO_LITE_SCHEMA = (
    "network",
    "country",
    "country_code",
    "continent",
    "continent_code",
    "asn",
    "as_name",
    "as_domain",
)

IPINFO_LITE_DEFINITION = DatasetDefinition(
    provider=IPINFO_LITE_PROVIDER,
    dataset=IPINFO_LITE_DATASET,
    dataset_format="csv",
    adapter_version="1",
    license_reference=IPINFO_LITE_LICENSE,
    attribution=IPINFO_LITE_ATTRIBUTION,
    retention=RetentionPolicy(retain_previous_versions=True),
    stale_after_days=1,
)


@dataclass(frozen=True, slots=True)
class DownloadMetadata:
    """Sanitized metadata returned by an acquisition transport."""

    last_modified: str | None = None


class DownloadTransport(Protocol):
    """Small injectable transport so CI never needs provider credentials/network."""

    def download(self, url: str, destination: Path) -> DownloadMetadata: ...


class UrllibDownloadTransport:
    """HTTPS transport with redirect support and sanitized failures."""

    def download(self, url: str, destination: Path) -> DownloadMetadata:
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                with destination.open("wb") as output:
                    shutil.copyfileobj(response, output)
                return DownloadMetadata(last_modified=response.headers.get("Last-Modified"))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise DatasetError("IPinfo Lite database download failed") from exc


class IPinfoLiteAcquirer:
    """Acquire the current IPinfo Lite CSV snapshot using an external access token."""

    definition = IPINFO_LITE_DEFINITION

    def __init__(
        self,
        *,
        transport: DownloadTransport | None = None,
        token_getter: Callable[[], str | None] | None = None,
    ) -> None:
        self._transport = transport or UrllibDownloadTransport()
        self._token_getter = token_getter or (lambda: os.environ.get("IPINFO_TOKEN"))

    def acquire(self, destination: Path) -> AcquiredDataset:
        token = self._token_getter()
        if token is None or not token.strip():
            raise DatasetError(
                "IPINFO_TOKEN is required to download IPinfo Lite; "
                "use datasets import for an air-gapped/manual snapshot"
            )

        archive = destination / "ipinfo_lite.csv.gz"
        metadata = self._transport.download(
            f"{IPINFO_LITE_DOWNLOAD_URL}?token={token}",
            archive,
        )
        digest = _file_sha256(archive)
        target = destination / IPINFO_LITE_FILENAME
        try:
            with gzip.open(archive, "rb") as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
        except (gzip.BadGzipFile, EOFError, OSError) as exc:
            raise DatasetValidationError("downloaded IPinfo Lite CSV gzip is invalid") from exc
        archive.unlink()

        release_date = _release_date(metadata.last_modified)
        release = f"{release_date}-{digest[:16]}" if release_date else f"sha256-{digest[:16]}"
        return AcquiredDataset(
            release=release,
            source=IPINFO_LITE_DOWNLOAD_URL,
            source_integrity_algorithm="sha256",
            source_integrity_value=digest,
            source_integrity_verified=True,
        )


class IPinfoLiteValidator:
    """Validate the documented Lite CSV schema and representative records."""

    def validate(self, dataset_path: Path, manifest: DatasetManifest) -> None:
        path = dataset_path / IPINFO_LITE_FILENAME
        if not path.is_file():
            raise DatasetValidationError(f"missing {IPINFO_LITE_FILENAME}")
        try:
            with path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                if tuple(reader.fieldnames or ()) != IPINFO_LITE_SCHEMA:
                    raise DatasetValidationError(
                        "IPinfo Lite schema changed: expected "
                        + ",".join(IPINFO_LITE_SCHEMA)
                        + "; received "
                        + ",".join(reader.fieldnames or ())
                    )
                first = next(reader, None)
        except (OSError, UnicodeError, csv.Error) as exc:
            raise DatasetValidationError("IPinfo Lite CSV could not be parsed") from exc
        if first is None:
            raise DatasetValidationError("IPinfo Lite CSV contains no data rows")
        _parse_record(first)


@dataclass(frozen=True, slots=True)
class _CSVRecord:
    network: str
    country: str | None
    country_code: str | None
    continent_code: str | None
    asn: int | None
    as_name: str | None
    as_domain: str | None


class _NetworkOffsets:
    """Compact network-to-line-offset index built from an immutable CSV snapshot."""

    def __init__(self) -> None:
        self.v4_start = array("I")
        self.v4_end = array("I")
        self.v4_offset = array("Q")
        self.v6_start_hi = array("Q")
        self.v6_start_lo = array("Q")
        self.v6_end_hi = array("Q")
        self.v6_end_lo = array("Q")
        self.v6_offset = array("Q")

    def add(self, network: IPv4Network | IPv6Network, offset: int) -> None:
        start = int(network.network_address)
        end = int(network.broadcast_address)
        if network.version == 4:
            if self.v4_end and start <= self.v4_end[-1]:
                raise DatasetValidationError("IPinfo Lite IPv4 networks overlap or are unsorted")
            self.v4_start.append(start)
            self.v4_end.append(end)
            self.v4_offset.append(offset)
            return

        hi_start, lo_start = divmod(start, 1 << 64)
        hi_end, lo_end = divmod(end, 1 << 64)
        if self.v6_end_hi and (hi_start, lo_start) <= (self.v6_end_hi[-1], self.v6_end_lo[-1]):
            raise DatasetValidationError("IPinfo Lite IPv6 networks overlap or are unsorted")
        self.v6_start_hi.append(hi_start)
        self.v6_start_lo.append(lo_start)
        self.v6_end_hi.append(hi_end)
        self.v6_end_lo.append(lo_end)
        self.v6_offset.append(offset)

    def find(self, ip: IPAddress) -> int | None:
        value = int(ip)
        if isinstance(ip, IPv4Address):
            index = bisect_right(self.v4_start, value) - 1
            if index >= 0 and value <= self.v4_end[index]:
                return self.v4_offset[index]
            return None

        hi, lo = divmod(value, 1 << 64)
        low = 0
        high = len(self.v6_start_hi)
        while low < high:
            middle = (low + high) // 2
            if (self.v6_start_hi[middle], self.v6_start_lo[middle]) <= (hi, lo):
                low = middle + 1
            else:
                high = middle
        index = low - 1
        if index >= 0 and (hi, lo) <= (self.v6_end_hi[index], self.v6_end_lo[index]):
            return self.v6_offset[index]
        return None


class IPinfoLiteCSVProvider:
    """Offline IPinfo Lite CSV provider with a compact in-memory range index."""

    capabilities = frozenset(
        {
            Capability.ASN,
            Capability.AS_ORGANIZATION,
            Capability.AS_DOMAIN,
            Capability.PREFIX,
            Capability.COUNTRY,
            Capability.CONTINENT,
        }
    )

    def __init__(self, path: Path, *, version: str) -> None:
        self._path = path
        self.identity = ProviderIdentity(
            provider=IPINFO_LITE_PROVIDER,
            dataset=IPINFO_LITE_DATASET,
            version=version,
            dataset_format="csv",
        )
        self._index = self._build_index()

    def _build_index(self) -> _NetworkOffsets:
        index = _NetworkOffsets()
        try:
            with self._path.open("rb") as handle:
                header = handle.readline().decode("utf-8-sig").rstrip("\r\n")
                fields = tuple(next(csv.reader([header])))
                if fields != IPINFO_LITE_SCHEMA:
                    raise DatasetValidationError("IPinfo Lite CSV schema does not match adapter")
                while True:
                    offset = handle.tell()
                    line = handle.readline()
                    if not line:
                        break
                    row = next(csv.reader([line.decode("utf-8")]))
                    if len(row) != len(IPINFO_LITE_SCHEMA):
                        raise DatasetValidationError(
                            "IPinfo Lite CSV row has unexpected field count"
                        )
                    network = ip_network(row[0], strict=False)
                    index.add(network, offset)
        except (OSError, UnicodeError, csv.Error, ValueError) as exc:
            if isinstance(exc, DatasetValidationError):
                raise
            raise DatasetValidationError("IPinfo Lite CSV index build failed") from exc
        return index

    def lookup(self, ip: IPAddress) -> ProviderResult:
        offset = self._index.find(ip)
        if offset is None:
            return ProviderResult(ip=ip, identity=self.identity, fields=self._not_found_fields())

        try:
            with self._path.open("rb") as handle:
                handle.seek(offset)
                row = next(csv.reader([handle.readline().decode("utf-8")]))
            record = _parse_record(dict(zip(IPINFO_LITE_SCHEMA, row, strict=True)))
        except (OSError, UnicodeError, csv.Error, ValueError):
            return ProviderResult(
                ip=ip,
                identity=self.identity,
                fields=self._error_fields("IPinfo Lite CSV lookup failed"),
            )

        semantics = {
            CanonicalField.ASN: "IPinfo Lite ASN for the IP range",
            CanonicalField.AS_NAME: "IPinfo Lite autonomous-system organization name",
            CanonicalField.AS_DOMAIN: "IPinfo Lite autonomous-system official domain",
            CanonicalField.NETWORK: "IPinfo Lite CIDR/IP range",
            CanonicalField.COUNTRY_CODE: "IPinfo Lite ISO 3166 country code",
            CanonicalField.COUNTRY_NAME: "IPinfo Lite country name",
            CanonicalField.CONTINENT_CODE: "IPinfo Lite continent code",
        }
        values: dict[CanonicalField, int | str | None] = {
            CanonicalField.ASN: record.asn,
            CanonicalField.AS_NAME: record.as_name,
            CanonicalField.AS_DOMAIN: record.as_domain,
            CanonicalField.NETWORK: record.network,
            CanonicalField.COUNTRY_CODE: record.country_code,
            CanonicalField.COUNTRY_NAME: record.country,
            CanonicalField.CONTINENT_CODE: record.continent_code,
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
        return ProviderResult(
            ip=ip,
            identity=self.identity,
            fields=tuple(observations),
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
    CanonicalField.AS_DOMAIN,
    CanonicalField.NETWORK,
    CanonicalField.COUNTRY_CODE,
    CanonicalField.COUNTRY_NAME,
    CanonicalField.CONTINENT_CODE,
)


def open_ipinfo_lite(store: DatasetStore | None = None) -> IPinfoLiteCSVProvider:
    """Open the active installed IPinfo Lite snapshot for fully offline lookup."""
    selected = store or DatasetStore()
    manifest = selected.active_manifest(IPINFO_LITE_PROVIDER, IPINFO_LITE_DATASET)
    if manifest.dataset_format != "csv":
        raise DatasetValidationError(
            f"unsupported IPinfo Lite installed format: {manifest.dataset_format}"
        )
    path = (
        selected.version_path(
            IPINFO_LITE_PROVIDER,
            IPINFO_LITE_DATASET,
            manifest.release,
        )
        / IPINFO_LITE_FILENAME
    )
    return IPinfoLiteCSVProvider(path, version=manifest.release)


def _parse_record(row: Mapping[str, str]) -> _CSVRecord:
    try:
        network = ip_network(row["network"], strict=False)
        asn_text = row["asn"]
        if asn_text and (not asn_text.startswith("AS") or not asn_text[2:].isdigit()):
            raise ValueError("invalid ASN")
        return _CSVRecord(
            network=str(network),
            country=row["country"] or None,
            country_code=row["country_code"] or None,
            continent_code=row["continent_code"] or None,
            asn=int(asn_text[2:]) if asn_text else None,
            as_name=row["as_name"] or None,
            as_domain=row["as_domain"] or None,
        )
    except (KeyError, ValueError) as exc:
        raise DatasetValidationError("invalid IPinfo Lite record") from exc


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
