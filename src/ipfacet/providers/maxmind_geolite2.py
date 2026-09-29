"""Offline MaxMind GeoLite2 ASN CSV provider and explicit acquisition."""

from __future__ import annotations

import base64
import csv
import hashlib
import http.client
import os
import re
import shutil
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from ipaddress import IPv4Address, ip_network
from pathlib import Path
from typing import IO, Protocol

from ipfacet.dataset_store import DatasetStore
from ipfacet.datasets import AcquiredDataset, DatasetDefinition, DatasetManifest, RetentionPolicy
from ipfacet.exceptions import DatasetError, DatasetValidationError
from ipfacet.models import CanonicalField, FieldState, IPAddress
from ipfacet.provider import Capability, ProviderIdentity, ProviderObservation, ProviderResult
from ipfacet.providers.ipinfo_lite import NetworkOffsets

MAXMIND_PROVIDER = "maxmind"
MAXMIND_DATASET = "geolite2-asn"
MAXMIND_URL = "https://download.maxmind.com/geoip/databases/GeoLite2-ASN-CSV/download?suffix=zip"
MAXMIND_ATTRIBUTION = (
    "This product includes GeoLite Data created by MaxMind, available from https://www.maxmind.com."
)
MAXMIND_LICENSE = "https://www.maxmind.com/en/geolite/eula"
FILES = ("GeoLite2-ASN-Blocks-IPv4.csv", "GeoLite2-ASN-Blocks-IPv6.csv")
HEADER = ("network", "autonomous_system_number", "autonomous_system_organization")
FIELDS = (CanonicalField.ASN, CanonicalField.AS_NAME, CanonicalField.NETWORK)

MAXMIND_DEFINITION = DatasetDefinition(
    provider=MAXMIND_PROVIDER,
    dataset=MAXMIND_DATASET,
    dataset_format="csv",
    adapter_version="1",
    license_reference=MAXMIND_LICENSE,
    attribution=MAXMIND_ATTRIBUTION,
    # The operator manages destruction of superseded releases under the EULA.
    retention=RetentionPolicy(retain_previous_versions=True),
    stale_after_days=7,
)


@dataclass(frozen=True, slots=True)
class DownloadMetadata:
    """Non-sensitive response details."""

    last_modified: str | None = None


class DownloadTransport(Protocol):
    def download(self, url: str, destination: Path, account: str, key: str) -> DownloadMetadata: ...


class _StripCrossHostAuth(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: http.client.HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if (
            redirected is not None
            and urllib.parse.urlparse(req.full_url).netloc != urllib.parse.urlparse(newurl).netloc
        ):
            redirected.remove_header("Authorization")
        return redirected


class UrllibDownloadTransport:
    """Authenticated HTTPS download, stripping credentials on cross-host redirects."""

    def download(self, url: str, destination: Path, account: str, key: str) -> DownloadMetadata:
        header = base64.b64encode(f"{account}:{key}".encode()).decode("ascii")
        request = urllib.request.Request(url, headers={"Authorization": f"Basic {header}"})
        try:
            opener = urllib.request.build_opener(_StripCrossHostAuth())
            with opener.open(request, timeout=120) as response, destination.open("wb") as output:
                if response.url.split(":", 1)[0] != "https":
                    raise DatasetError("GeoLite2 download redirected to non-HTTPS URL")
                shutil.copyfileobj(response, output)
                return DownloadMetadata(last_modified=response.headers.get("Last-Modified"))
        except (urllib.error.URLError, TimeoutError, OSError):
            raise DatasetError("GeoLite2 ASN download failed") from None


class MaxMindGeoLite2Acquirer:
    """Download the current ASN CSV zip using external account credentials."""

    definition = MAXMIND_DEFINITION

    def __init__(
        self,
        *,
        transport: DownloadTransport | None = None,
        credential_getter: Callable[[], tuple[str | None, str | None]] | None = None,
    ) -> None:
        self._transport = transport or UrllibDownloadTransport()
        self._credentials = credential_getter or (
            lambda: (os.environ.get("MAXMIND_ACCOUNT_ID"), os.environ.get("MAXMIND_LICENSE_KEY"))
        )

    def acquire(self, destination: Path) -> AcquiredDataset:
        account, key = self._credentials()
        if not account or not key or not account.strip() or not key.strip():
            raise DatasetError(
                "MAXMIND_ACCOUNT_ID and MAXMIND_LICENSE_KEY are required; "
                "use datasets import for manual installation"
            )
        archive = destination / "download.zip"
        self._transport.download(MAXMIND_URL, archive, account, key)
        digest = _sha256(archive)
        try:
            with zipfile.ZipFile(archive) as source:
                for filename in FILES:
                    matches = [
                        info
                        for info in source.infolist()
                        if info.filename.split("/")[-1] == filename and not info.is_dir()
                    ]
                    if len(matches) != 1 or matches[0].file_size > 150_000_000:
                        raise DatasetValidationError(
                            f"GeoLite2 archive missing or oversized {filename}"
                        )
                    with (
                        source.open(matches[0]) as input_file,
                        (destination / filename).open("wb") as output,
                    ):
                        shutil.copyfileobj(input_file, output)
                dates = {
                    match.group(1)
                    for name in source.namelist()
                    if (match := re.search(r"GeoLite2-ASN-CSV_(\d{8})/", name))
                }
        except (OSError, zipfile.BadZipFile, RuntimeError, EOFError) as exc:
            raise DatasetValidationError("invalid GeoLite2 ASN ZIP archive") from exc
        archive.unlink()
        release = (
            f"{next(iter(dates))}-{digest[:16]}" if len(dates) == 1 else f"sha256-{digest[:16]}"
        )
        return AcquiredDataset(
            release=release,
            source=MAXMIND_URL,
            source_integrity_algorithm="sha256",
            source_integrity_value=digest,
            source_integrity_verified=True,
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse(row: Mapping[str, str]) -> tuple[str, int | None, str | None]:
    try:
        network = ip_network(row["network"], strict=True)
        raw = row["autonomous_system_number"]
        if raw and (not raw.isascii() or not raw.isdigit() or int(raw) > 4294967295):
            raise ValueError("invalid ASN")
        return (
            str(network),
            int(raw) if raw else None,
            row["autonomous_system_organization"] or None,
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise DatasetValidationError("invalid GeoLite2 ASN record") from exc


class MaxMindGeoLite2CSVProvider:
    """Indexed, fully offline IPv4/IPv6 ASN lookups."""

    capabilities = frozenset({Capability.ASN, Capability.AS_ORGANIZATION, Capability.PREFIX})

    def __init__(self, path: Path, *, version: str) -> None:
        self._path = path
        self.identity = ProviderIdentity(
            provider=MAXMIND_PROVIDER,
            dataset=MAXMIND_DATASET,
            version=version,
            dataset_format="csv",
        )
        self._indexes = self._build_indexes()

    def _build_indexes(self) -> tuple[NetworkOffsets, NetworkOffsets]:
        indexes = (NetworkOffsets(), NetworkOffsets())
        for family, filename in enumerate(FILES):
            try:
                with (self._path / filename).open("rb") as handle:
                    header = handle.readline().decode("utf-8-sig").rstrip("\r\n")
                    if tuple(next(csv.reader([header]))) != HEADER:
                        raise DatasetValidationError("GeoLite2 ASN schema changed")
                    count = 0
                    while line := handle.readline():
                        offset = handle.tell() - len(line)
                        row = next(csv.reader([line.decode("utf-8")]))
                        if len(row) != len(HEADER):
                            raise DatasetValidationError(
                                "GeoLite2 ASN row has unexpected field count"
                            )
                        network_text, _, _ = _parse(dict(zip(HEADER, row, strict=True)))
                        network = ip_network(network_text)
                        if network.version != (4 if family == 0 else 6):
                            raise DatasetValidationError(
                                "GeoLite2 ASN network in wrong family file"
                            )
                        indexes[family].add(network, offset)
                        count += 1
                    if not count:
                        raise DatasetValidationError("GeoLite2 ASN CSV contains no data")
            except (OSError, UnicodeError, csv.Error, ValueError) as exc:
                if isinstance(exc, DatasetValidationError):
                    raise
                raise DatasetValidationError("GeoLite2 ASN index build failed") from exc
        return indexes

    def lookup(self, ip: IPAddress) -> ProviderResult:
        family = 0 if isinstance(ip, IPv4Address) else 1
        offset = self._indexes[family].find(ip)
        if offset is None:
            return self._result(ip, None)
        try:
            with (self._path / FILES[family]).open("rb") as handle:
                handle.seek(offset)
                row = next(csv.reader([handle.readline().decode("utf-8")]))
            parsed = _parse(dict(zip(HEADER, row, strict=True)))
        except (OSError, UnicodeError, csv.Error, ValueError, DatasetValidationError):
            return ProviderResult(
                ip=ip,
                identity=self.identity,
                fields=tuple(
                    ProviderObservation(
                        field=f,
                        state=FieldState.LOOKUP_ERROR,
                        error="GeoLite2 ASN CSV lookup failed",
                    )
                    for f in FIELDS
                ),
            )
        return self._result(ip, parsed)

    def _result(
        self, ip: IPAddress, parsed: tuple[str, int | None, str | None] | None
    ) -> ProviderResult:
        values = (None, None, None) if parsed is None else (parsed[1], parsed[2], parsed[0])
        semantics = (
            "MaxMind ASN associated with IP range",
            "organization associated with registered ASN",
            "GeoLite2 ASN CIDR block",
        )
        fields = tuple(
            ProviderObservation(
                field=field,
                state=FieldState.PRESENT if value is not None else FieldState.NOT_FOUND,
                value=value,
                semantics=semantics[index] if value is not None else None,
            )
            for index, (field, value) in enumerate(zip(FIELDS, values, strict=True))
        )
        return ProviderResult(ip=ip, identity=self.identity, fields=fields)


class MaxMindGeoLite2Validator:
    def validate(self, dataset_path: Path, manifest: DatasetManifest) -> None:
        MaxMindGeoLite2CSVProvider(dataset_path, version=manifest.release)


def open_maxmind_geolite2(store: DatasetStore | None = None) -> MaxMindGeoLite2CSVProvider:
    selected = store or DatasetStore()
    manifest = selected.active_manifest(MAXMIND_PROVIDER, MAXMIND_DATASET)
    if manifest.dataset_format != "csv":
        raise DatasetValidationError("unsupported GeoLite2 ASN installed format")
    return MaxMindGeoLite2CSVProvider(
        selected.version_path(MAXMIND_PROVIDER, MAXMIND_DATASET, manifest.release),
        version=manifest.release,
    )
