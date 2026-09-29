"""Dataset acquisition contracts and lifecycle models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol


class AcquisitionMethod(StrEnum):
    """How a dataset snapshot entered the local store."""

    DOWNLOAD = "download"
    IMPORT = "import"


@dataclass(frozen=True, slots=True)
class RetentionPolicy:
    """Provider restrictions that generic retention settings cannot relax."""

    retain_previous_versions: bool = True
    max_retained_versions: int | None = None

    def __post_init__(self) -> None:
        if self.max_retained_versions is not None and self.max_retained_versions < 1:
            raise ValueError("max_retained_versions must be at least 1")
        if not self.retain_previous_versions and self.max_retained_versions not in {None, 1}:
            raise ValueError("non-retaining providers cannot retain multiple versions")


@dataclass(frozen=True, slots=True)
class DatasetDefinition:
    """Provider-owned lifecycle metadata for one reference dataset."""

    provider: str
    dataset: str
    dataset_format: str
    adapter_version: str
    license_reference: str
    attribution: str | None = None
    retention: RetentionPolicy = RetentionPolicy()
    stale_after_days: int | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("provider", self.provider),
            ("dataset", self.dataset),
            ("dataset_format", self.dataset_format),
            ("adapter_version", self.adapter_version),
            ("license_reference", self.license_reference),
        ):
            if not value.strip():
                raise ValueError(f"{name} cannot be empty")
        if self.stale_after_days is not None and self.stale_after_days < 1:
            raise ValueError("stale_after_days must be at least 1")


@dataclass(frozen=True, slots=True)
class AcquiredDataset:
    """Acquisition result staged by a provider-specific acquisition helper."""

    release: str
    source: str
    source_integrity_algorithm: str | None = None
    source_integrity_value: str | None = None
    source_integrity_verified: bool = False

    def __post_init__(self) -> None:
        if not self.release.strip():
            raise ValueError("release cannot be empty")
        if not self.source.strip():
            raise ValueError("source cannot be empty")
        if (self.source_integrity_algorithm is None) != (self.source_integrity_value is None):
            raise ValueError("source integrity algorithm and value must be supplied together")
        if self.source_integrity_algorithm is not None and not self.source_integrity_verified:
            raise ValueError("source integrity metadata must be verified before acquisition returns")


@dataclass(frozen=True, slots=True)
class DatasetManifest:
    """Credential-free immutable metadata for one installed snapshot."""

    schema_version: int
    provider: str
    dataset: str
    release: str
    source: str
    acquisition_method: AcquisitionMethod
    acquired_at: datetime
    activated_at: datetime | None
    dataset_format: str
    integrity_algorithm: str
    integrity_value: str
    source_integrity_algorithm: str | None
    source_integrity_value: str | None
    adapter_version: str
    license_reference: str
    attribution: str | None
    retain_previous_versions: bool
    max_retained_versions: int | None
    stale_after_days: int | None

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported manifest schema version")
        if self.acquired_at.tzinfo is None:
            raise ValueError("acquired_at must be timezone-aware")
        if self.activated_at is not None and self.activated_at.tzinfo is None:
            raise ValueError("activated_at must be timezone-aware")

    @property
    def key(self) -> str:
        return f"{self.provider}/{self.dataset}"

    def is_stale(self, now: datetime | None = None) -> bool:
        if self.stale_after_days is None:
            return False
        current = now or datetime.now(UTC)
        return (current - self.acquired_at).days >= self.stale_after_days


class DatasetAcquirer(Protocol):
    """Network/manual acquisition contract, deliberately separate from lookup."""

    @property
    def definition(self) -> DatasetDefinition: ...

    def acquire(self, destination: Path) -> AcquiredDataset:
        """Populate an empty staging directory and describe the acquired release."""
        ...


class DatasetValidator(Protocol):
    """Provider-specific schema and smoke validation contract."""

    def validate(self, dataset_path: Path, manifest: DatasetManifest) -> None:
        """Raise DatasetValidationError when the staged snapshot is unusable."""
        ...
