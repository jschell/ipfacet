from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from ipfacet import DatasetError, DatasetNotInstalledError, DatasetValidationError
from ipfacet.credentials import environment_credentials
from ipfacet.dataset_manager import DatasetManager
from ipfacet.dataset_store import DatasetStore
from ipfacet.datasets import (
    AcquiredDataset,
    DatasetDefinition,
    DatasetManifest,
    RetentionPolicy,
)


@dataclass
class SyntheticAcquirer:
    definition: DatasetDefinition
    release: str = "v1"
    content: str = "valid"
    source_integrity_value: str | None = None
    source_integrity_verified: bool = False

    def acquire(self, destination: Path) -> AcquiredDataset:
        destination.joinpath("data.txt").write_text(self.content, encoding="utf-8")
        return AcquiredDataset(
            release=self.release,
            source="https://example.invalid/synthetic",
            source_integrity_algorithm=(
                "sha256" if self.source_integrity_value is not None else None
            ),
            source_integrity_value=self.source_integrity_value,
            source_integrity_verified=self.source_integrity_verified,
        )


class SyntheticValidator:
    def validate(self, dataset_path: Path, manifest: DatasetManifest) -> None:
        if dataset_path.joinpath("data.txt").read_text(encoding="utf-8") != "valid":
            raise DatasetValidationError(f"schema/smoke validation failed for {manifest.release}")


def definition(
    *,
    retain_previous: bool = True,
    max_retained: int | None = None,
    stale_after_days: int | None = 30,
) -> DatasetDefinition:
    return DatasetDefinition(
        provider="synthetic",
        dataset="fixture",
        dataset_format="text",
        adapter_version="1",
        license_reference="fixture-license",
        attribution="Synthetic fixture",
        retention=RetentionPolicy(
            retain_previous_versions=retain_previous,
            max_retained_versions=max_retained,
        ),
        stale_after_days=stale_after_days,
    )


def manager(
    tmp_path: Path,
    acquirer: SyntheticAcquirer,
) -> DatasetManager:
    return DatasetManager(
        store=DatasetStore(tmp_path),
        acquirers=(acquirer,),
        validators={("synthetic", "fixture"): SyntheticValidator()},
    )


def test_install_update_verify_and_rollback(tmp_path: Path) -> None:
    acquirer = SyntheticAcquirer(definition())
    datasets = manager(tmp_path, acquirer)

    first = datasets.install("synthetic", "fixture")
    assert first.release == "v1"
    assert first.activated_at is not None
    assert datasets.verify("synthetic", "fixture").integrity_value == first.integrity_value

    acquirer.release = "v2"
    second = datasets.update("synthetic", "fixture")
    assert second.release == "v2"
    assert datasets.status("synthetic", "fixture").release == "v2"

    rolled_back = datasets.rollback("synthetic", "fixture")
    assert rolled_back.release == "v1"
    assert datasets.status("synthetic", "fixture").release == "v1"


def test_failed_update_never_replaces_active_snapshot(tmp_path: Path) -> None:
    acquirer = SyntheticAcquirer(definition())
    datasets = manager(tmp_path, acquirer)
    datasets.install("synthetic", "fixture")

    acquirer.release = "v2"
    acquirer.content = "invalid"
    with pytest.raises(DatasetValidationError, match="schema/smoke"):
        datasets.update("synthetic", "fixture")

    assert datasets.status("synthetic", "fixture").release == "v1"
    assert not datasets.store.version_path("synthetic", "fixture", "v2").exists()


def test_unverified_source_checksum_is_rejected_before_activation(tmp_path: Path) -> None:
    acquirer = SyntheticAcquirer(definition(), source_integrity_value="0" * 64)
    datasets = manager(tmp_path, acquirer)

    with pytest.raises(ValueError, match="must be verified"):
        datasets.install("synthetic", "fixture")

    with pytest.raises(DatasetNotInstalledError):
        datasets.status("synthetic", "fixture")


def test_verified_source_checksum_is_recorded_separately(tmp_path: Path) -> None:
    acquirer = SyntheticAcquirer(
        definition(),
        source_integrity_value="a" * 64,
        source_integrity_verified=True,
    )
    datasets = manager(tmp_path, acquirer)

    manifest = datasets.install("synthetic", "fixture")

    assert manifest.source_integrity_algorithm == "sha256"
    assert manifest.source_integrity_value == "a" * 64
    assert manifest.integrity_value != manifest.source_integrity_value


def test_verify_detects_post_install_tampering(tmp_path: Path) -> None:
    acquirer = SyntheticAcquirer(definition())
    datasets = manager(tmp_path, acquirer)
    datasets.install("synthetic", "fixture")
    datasets.store.version_path("synthetic", "fixture", "v1").joinpath("data.txt").write_text(
        "tampered",
        encoding="utf-8",
    )

    with pytest.raises(DatasetValidationError, match="integrity verification failed"):
        datasets.verify("synthetic", "fixture")


def test_provider_retention_can_forbid_old_snapshots_and_rollback(tmp_path: Path) -> None:
    acquirer = SyntheticAcquirer(definition(retain_previous=False))
    datasets = manager(tmp_path, acquirer)
    datasets.install("synthetic", "fixture")

    acquirer.release = "v2"
    datasets.update("synthetic", "fixture")

    assert not datasets.store.version_path("synthetic", "fixture", "v1").exists()
    with pytest.raises(DatasetError, match="does not permit"):
        datasets.rollback("synthetic", "fixture")


def test_provider_max_retention_is_enforced(tmp_path: Path) -> None:
    acquirer = SyntheticAcquirer(definition(max_retained=2))
    datasets = manager(tmp_path, acquirer)
    for release in ("v1", "v2", "v3"):
        acquirer.release = release
        datasets.install("synthetic", "fixture")

    releases = {item.release for item in datasets.store.list_manifests("synthetic", "fixture")}
    assert releases == {"v2", "v3"}


def test_air_gapped_import_works_without_acquirer(tmp_path: Path) -> None:
    source = tmp_path / "airgap"
    source.mkdir()
    source.joinpath("data.txt").write_text("valid", encoding="utf-8")
    registered = definition()
    datasets = DatasetManager(
        store=DatasetStore(tmp_path / "store"),
        definitions=(registered,),
        validators={("synthetic", "fixture"): SyntheticValidator()},
    )

    manifest = datasets.import_dataset(
        "synthetic",
        "fixture",
        source,
        release="offline-1",
        source_reference="removable-media",
    )

    assert manifest.release == "offline-1"
    assert manifest.source == "removable-media"
    assert manifest.acquisition_method.value == "import"
    assert datasets.verify("synthetic", "fixture").release == "offline-1"


def test_manifest_contains_required_lifecycle_metadata(tmp_path: Path) -> None:
    acquirer = SyntheticAcquirer(definition())
    datasets = manager(tmp_path, acquirer)
    manifest = datasets.install("synthetic", "fixture")
    raw = json.loads(
        datasets.store.version_path("synthetic", "fixture", "v1")
        .joinpath("manifest.json")
        .read_text(encoding="utf-8")
    )

    assert raw["provider"] == "synthetic"
    assert raw["dataset"] == "fixture"
    assert raw["release"] == "v1"
    assert raw["source"] == "https://example.invalid/synthetic"
    assert raw["acquired_at"]
    assert raw["activated_at"]
    assert raw["format"] == "text"
    assert raw["integrity"]["algorithm"] == "sha256"
    assert raw["integrity"]["value"] == manifest.integrity_value
    assert raw["source_integrity"]["algorithm"] is None
    assert raw["source_integrity"]["value"] is None
    assert raw["adapter_version"] == "1"
    assert raw["license_reference"] == "fixture-license"
    assert raw["retention"]["retain_previous_versions"] is True


def test_credentials_stay_external_to_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "super-secret-license-key"
    monkeypatch.setenv("IPFACET_FIXTURE_KEY", secret)
    credentials = environment_credentials(("IPFACET_FIXTURE_KEY",))
    assert credentials["IPFACET_FIXTURE_KEY"] == secret

    acquirer = SyntheticAcquirer(definition())
    datasets = manager(tmp_path, acquirer)
    datasets.install("synthetic", "fixture")

    manifest_text = (
        datasets.store.version_path("synthetic", "fixture", "v1")
        .joinpath("manifest.json")
        .read_text(encoding="utf-8")
    )
    assert secret not in manifest_text
    assert "IPFACET_FIXTURE_KEY" not in manifest_text


def test_available_and_list_installed_are_deterministic(tmp_path: Path) -> None:
    acquirer = SyntheticAcquirer(definition())
    datasets = manager(tmp_path, acquirer)
    assert [(item.provider, item.dataset) for item in datasets.available()] == [
        ("synthetic", "fixture")
    ]
    assert datasets.list_installed() == ()

    datasets.install("synthetic", "fixture")
    assert [(item.provider, item.dataset) for item in datasets.list_installed()] == [
        ("synthetic", "fixture")
    ]


def test_immutable_release_cannot_be_overwritten(tmp_path: Path) -> None:
    acquirer = SyntheticAcquirer(definition())
    datasets = manager(tmp_path, acquirer)
    datasets.install("synthetic", "fixture")

    with pytest.raises(DatasetValidationError, match="immutable dataset release"):
        datasets.install("synthetic", "fixture")


def test_unsafe_release_is_rejected(tmp_path: Path) -> None:
    acquirer = SyntheticAcquirer(definition(), release="../escape")
    datasets = manager(tmp_path, acquirer)

    with pytest.raises(ValueError, match="unsafe dataset path"):
        datasets.install("synthetic", "fixture")


def test_activation_failure_leaves_previous_pointer_usable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    acquirer = SyntheticAcquirer(definition())
    datasets = manager(tmp_path, acquirer)
    datasets.install("synthetic", "fixture")
    original_activate = datasets.store.activate

    acquirer.release = "v2"

    def fail_v2(manifest: DatasetManifest) -> DatasetManifest:
        if manifest.release == "v2":
            raise OSError("simulated atomic pointer failure")
        return original_activate(manifest)

    monkeypatch.setattr(datasets.store, "activate", fail_v2)
    with pytest.raises(OSError, match="simulated atomic pointer failure"):
        datasets.update("synthetic", "fixture")

    assert datasets.status("synthetic", "fixture").release == "v1"
    assert not datasets.store.version_path("synthetic", "fixture", "v2").exists()


def test_air_gapped_import_rejects_symlinks(tmp_path: Path) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("do-not-import", encoding="utf-8")
    source = tmp_path / "airgap-links"
    source.mkdir()
    source.joinpath("linked.txt").symlink_to(outside)
    datasets = DatasetManager(
        store=DatasetStore(tmp_path / "store"),
        definitions=(definition(),),
    )

    with pytest.raises(DatasetValidationError, match="unsupported symlink"):
        datasets.import_dataset(
            "synthetic",
            "fixture",
            source,
            release="linked",
        )

    with pytest.raises(DatasetNotInstalledError):
        datasets.status("synthetic", "fixture")
