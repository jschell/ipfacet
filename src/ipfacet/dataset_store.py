"""Filesystem-backed immutable dataset snapshot store."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from ipfacet.datasets import AcquisitionMethod, DatasetDefinition, DatasetManifest
from ipfacet.exceptions import DatasetNotInstalledError, DatasetValidationError


def default_data_dir() -> Path:
    """Return a platform-appropriate per-user data directory without dependencies."""
    if sys.platform == "win32":
        root = os.environ.get("LOCALAPPDATA")
        return Path(root) / "IPFacet" if root else Path.home() / "AppData/Local/IPFacet"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/IPFacet"
    root = os.environ.get("XDG_DATA_HOME")
    return Path(root) / "ipfacet" if root else Path.home() / ".local/share/ipfacet"


def _safe_component(value: str) -> str:
    if not value or value in {".", ".."} or any(char in value for char in "/\\"):
        raise ValueError(f"unsafe dataset path component: {value!r}")
    return value


def snapshot_hash(path: Path) -> str:
    """Hash relative names and file contents for a deterministic snapshot digest."""
    digest = hashlib.sha256()
    files = sorted(
        item for item in path.rglob("*") if item.is_file() and item.name != "manifest.json"
    )
    for item in files:
        relative = item.relative_to(path).as_posix().encode()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        with item.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _manifest_dict(manifest: DatasetManifest) -> dict[str, object]:
    return {
        "schema_version": manifest.schema_version,
        "provider": manifest.provider,
        "dataset": manifest.dataset,
        "release": manifest.release,
        "source": manifest.source,
        "acquisition_method": manifest.acquisition_method.value,
        "acquired_at": manifest.acquired_at.isoformat(),
        "activated_at": (
            None if manifest.activated_at is None else manifest.activated_at.isoformat()
        ),
        "format": manifest.dataset_format,
        "integrity": {
            "algorithm": manifest.integrity_algorithm,
            "value": manifest.integrity_value,
        },
        "adapter_version": manifest.adapter_version,
        "license_reference": manifest.license_reference,
        "attribution": manifest.attribution,
        "retention": {
            "retain_previous_versions": manifest.retain_previous_versions,
            "max_retained_versions": manifest.max_retained_versions,
        },
        "stale_after_days": manifest.stale_after_days,
    }


def _manifest_from_dict(value: dict[str, object]) -> DatasetManifest:
    integrity = cast(dict[str, object], value["integrity"])
    retention = cast(dict[str, object], value["retention"])
    activated = value.get("activated_at")
    return DatasetManifest(
        schema_version=int(cast(int, value["schema_version"])),
        provider=str(value["provider"]),
        dataset=str(value["dataset"]),
        release=str(value["release"]),
        source=str(value["source"]),
        acquisition_method=AcquisitionMethod(str(value["acquisition_method"])),
        acquired_at=datetime.fromisoformat(str(value["acquired_at"])),
        activated_at=None if activated is None else datetime.fromisoformat(str(activated)),
        dataset_format=str(value["format"]),
        integrity_algorithm=str(integrity["algorithm"]),
        integrity_value=str(integrity["value"]),
        adapter_version=str(value["adapter_version"]),
        license_reference=str(value["license_reference"]),
        attribution=None if value.get("attribution") is None else str(value["attribution"]),
        retain_previous_versions=bool(retention["retain_previous_versions"]),
        max_retained_versions=(
            None
            if retention.get("max_retained_versions") is None
            else int(cast(int, retention["max_retained_versions"]))
        ),
        stale_after_days=(
            None
            if value.get("stale_after_days") is None
            else int(cast(int, value["stale_after_days"]))
        ),
    )


class DatasetStore:
    """Own immutable snapshots and the atomic active-version pointer."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or default_data_dir()).expanduser()

    def dataset_root(self, provider: str, dataset: str) -> Path:
        return self.root / "datasets" / _safe_component(provider) / _safe_component(dataset)

    def versions_dir(self, provider: str, dataset: str) -> Path:
        return self.dataset_root(provider, dataset) / "versions"

    def version_path(self, provider: str, dataset: str, release: str) -> Path:
        return self.versions_dir(provider, dataset) / _safe_component(release)

    def staging_dir(self, provider: str, dataset: str) -> Path:
        parent = self.dataset_root(provider, dataset) / "staging"
        parent.mkdir(parents=True, exist_ok=True)
        return Path(tempfile.mkdtemp(prefix="stage-", dir=parent))

    def write_manifest(self, path: Path, manifest: DatasetManifest) -> None:
        path.joinpath("manifest.json").write_text(
            json.dumps(_manifest_dict(manifest), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def read_manifest_path(self, path: Path) -> DatasetManifest:
        try:
            raw = json.loads(path.joinpath("manifest.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise DatasetValidationError(f"invalid dataset manifest at {path}") from exc
        if not isinstance(raw, dict):
            raise DatasetValidationError(f"invalid dataset manifest at {path}")
        try:
            return _manifest_from_dict(cast(dict[str, object], raw))
        except (KeyError, TypeError, ValueError) as exc:
            raise DatasetValidationError(f"invalid dataset manifest at {path}") from exc

    def active_release(self, provider: str, dataset: str) -> str:
        pointer = self.dataset_root(provider, dataset) / "active.json"
        try:
            raw = json.loads(pointer.read_text(encoding="utf-8"))
            release = raw["release"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise DatasetNotInstalledError(f"{provider}/{dataset} has no active dataset") from exc
        if not isinstance(release, str):
            raise DatasetValidationError("active dataset pointer contains an invalid release")
        return _safe_component(release)

    def active_manifest(self, provider: str, dataset: str) -> DatasetManifest:
        release = self.active_release(provider, dataset)
        return self.read_manifest_path(self.version_path(provider, dataset, release))

    def activate(self, manifest: DatasetManifest) -> DatasetManifest:
        activated = replace(manifest, activated_at=datetime.now(UTC))
        path = self.version_path(manifest.provider, manifest.dataset, manifest.release)
        self.write_manifest(path, activated)
        pointer = self.dataset_root(manifest.provider, manifest.dataset) / "active.json"
        pointer.parent.mkdir(parents=True, exist_ok=True)
        temp = pointer.with_name("active.json.tmp")
        temp.write_text(json.dumps({"release": manifest.release}) + "\n", encoding="utf-8")
        os.replace(temp, pointer)
        return activated

    def commit_staged(self, staged: Path, manifest: DatasetManifest) -> Path:
        destination = self.version_path(manifest.provider, manifest.dataset, manifest.release)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise DatasetValidationError(
                f"immutable dataset release already exists: {manifest.provider}/{manifest.dataset} "
                f"{manifest.release}"
            )
        os.replace(staged, destination)
        return destination

    def list_manifests(self, provider: str, dataset: str) -> tuple[DatasetManifest, ...]:
        versions = self.versions_dir(provider, dataset)
        if not versions.exists():
            return ()
        manifests = [self.read_manifest_path(path) for path in versions.iterdir() if path.is_dir()]
        return tuple(sorted(manifests, key=lambda item: item.acquired_at, reverse=True))

    def verify(self, provider: str, dataset: str, release: str | None = None) -> DatasetManifest:
        selected = release or self.active_release(provider, dataset)
        path = self.version_path(provider, dataset, selected)
        manifest = self.read_manifest_path(path)
        actual = snapshot_hash(path)
        if manifest.integrity_algorithm != "sha256" or actual != manifest.integrity_value:
            raise DatasetValidationError(
                f"integrity verification failed for {provider}/{dataset} {selected}"
            )
        return manifest

    def remove_version(self, provider: str, dataset: str, release: str) -> None:
        shutil.rmtree(self.version_path(provider, dataset, release), ignore_errors=True)

    def cleanup_staging(self, staged: Path) -> None:
        shutil.rmtree(staged, ignore_errors=True)

    def enforce_retention(self, definition: DatasetDefinition, active_release: str) -> None:
        manifests = self.list_manifests(definition.provider, definition.dataset)
        if not definition.retention.retain_previous_versions:
            keep = {active_release}
        elif definition.retention.max_retained_versions is not None:
            keep = {
                item.release
                for item in manifests[: definition.retention.max_retained_versions]
            }
            keep.add(active_release)
        else:
            return
        for manifest in manifests:
            if manifest.release not in keep:
                self.remove_version(definition.provider, definition.dataset, manifest.release)
