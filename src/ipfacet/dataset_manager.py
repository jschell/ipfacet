"""Dataset acquisition, validation, activation, verification, and rollback."""

from __future__ import annotations

import shutil
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from ipfacet.dataset_store import DatasetStore, snapshot_hash
from ipfacet.datasets import (
    AcquiredDataset,
    AcquisitionMethod,
    DatasetAcquirer,
    DatasetDefinition,
    DatasetManifest,
    DatasetValidator,
)
from ipfacet.exceptions import DatasetError, DatasetNotInstalledError, DatasetValidationError


class DatasetManager:
    """Coordinate provider-specific acquisition with provider-neutral safe activation."""

    def __init__(
        self,
        *,
        store: DatasetStore | None = None,
        acquirers: Iterable[DatasetAcquirer] = (),
        validators: Mapping[tuple[str, str], DatasetValidator] | None = None,
    ) -> None:
        self.store = store or DatasetStore()
        registered = tuple(acquirers)
        self._acquirers = {
            (item.definition.provider, item.definition.dataset): item for item in registered
        }
        if len(self._acquirers) != len(registered):
            raise ValueError("duplicate dataset acquirer registration")
        self._validators = dict(validators or {})

    def available(self) -> tuple[DatasetDefinition, ...]:
        return tuple(
            sorted(
                (item.definition for item in self._acquirers.values()),
                key=lambda item: (item.provider, item.dataset),
            )
        )

    def list_installed(self) -> tuple[DatasetManifest, ...]:
        base = self.store.root / "datasets"
        if not base.exists():
            return ()
        manifests: list[DatasetManifest] = []
        for provider in base.iterdir():
            if not provider.is_dir():
                continue
            for dataset in provider.iterdir():
                if not dataset.is_dir():
                    continue
                try:
                    manifests.append(self.store.active_manifest(provider.name, dataset.name))
                except DatasetNotInstalledError:
                    continue
        return tuple(sorted(manifests, key=lambda item: (item.provider, item.dataset)))

    def status(self, provider: str, dataset: str) -> DatasetManifest:
        return self.store.active_manifest(provider, dataset)

    def install(self, provider: str, dataset: str) -> DatasetManifest:
        key = (provider, dataset)
        acquirer = self._acquirers.get(key)
        if acquirer is None:
            raise DatasetError(f"no acquisition helper registered for {provider}/{dataset}")
        staged = self.store.staging_dir(provider, dataset)
        try:
            acquired = acquirer.acquire(staged)
            return self._finalize(staged, acquirer.definition, acquired, AcquisitionMethod.DOWNLOAD)
        except Exception:
            self.store.cleanup_staging(staged)
            raise

    def update(self, provider: str, dataset: str) -> DatasetManifest:
        return self.install(provider, dataset)

    def import_dataset(
        self,
        definition: DatasetDefinition,
        source: Path,
        *,
        release: str,
        source_reference: str = "manual-import",
    ) -> DatasetManifest:
        if not source.is_dir():
            raise DatasetValidationError("manual import source must be a directory")
        staged = self.store.staging_dir(definition.provider, definition.dataset)
        try:
            for item in source.iterdir():
                target = staged / item.name
                if item.is_dir():
                    shutil.copytree(item, target)
                else:
                    shutil.copy2(item, target)
            acquired = AcquiredDataset(release=release, source=source_reference)
            return self._finalize(staged, definition, acquired, AcquisitionMethod.IMPORT)
        except Exception:
            self.store.cleanup_staging(staged)
            raise

    def verify(
        self,
        provider: str,
        dataset: str,
        *,
        release: str | None = None,
    ) -> DatasetManifest:
        manifest = self.store.verify(provider, dataset, release)
        validator = self._validators.get((provider, dataset))
        if validator is not None:
            selected = release or manifest.release
            validator.validate(self.store.version_path(provider, dataset, selected), manifest)
        return manifest

    def rollback(
        self,
        provider: str,
        dataset: str,
        *,
        release: str | None = None,
    ) -> DatasetManifest:
        active = self.store.active_manifest(provider, dataset)
        if not active.retain_previous_versions:
            raise DatasetError(f"{provider}/{dataset} does not permit retained-version rollback")
        candidates = [
            item
            for item in self.store.list_manifests(provider, dataset)
            if item.release != active.release
        ]
        if release is not None:
            candidates = [item for item in candidates if item.release == release]
        if not candidates:
            raise DatasetNotInstalledError(
                f"no rollback snapshot available for {provider}/{dataset}"
            )
        target = candidates[0]
        self.verify(provider, dataset, release=target.release)
        return self.store.activate(target)

    def _finalize(
        self,
        staged: Path,
        definition: DatasetDefinition,
        acquired: AcquiredDataset,
        method: AcquisitionMethod,
    ) -> DatasetManifest:
        digest = snapshot_hash(staged)
        manifest = DatasetManifest(
            schema_version=1,
            provider=definition.provider,
            dataset=definition.dataset,
            release=acquired.release,
            source=acquired.source,
            acquisition_method=method,
            acquired_at=datetime.now(UTC),
            activated_at=None,
            dataset_format=definition.dataset_format,
            integrity_algorithm="sha256",
            integrity_value=digest,
            source_integrity_algorithm=acquired.source_integrity_algorithm,
            source_integrity_value=acquired.source_integrity_value,
            adapter_version=definition.adapter_version,
            license_reference=definition.license_reference,
            attribution=definition.attribution,
            retain_previous_versions=definition.retention.retain_previous_versions,
            max_retained_versions=definition.retention.max_retained_versions,
            stale_after_days=definition.stale_after_days,
        )
        validator = self._validators.get((definition.provider, definition.dataset))
        if validator is not None:
            validator.validate(staged, manifest)
        self.store.write_manifest(staged, manifest)
        self.store.commit_staged(staged, manifest)
        try:
            activated = self.store.activate(manifest)
        except Exception:
            self.store.remove_version(definition.provider, definition.dataset, acquired.release)
            raise
        self.store.enforce_retention(definition, activated.release)
        return activated
