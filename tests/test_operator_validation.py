"""Operator validation checks only selected local snapshots and metadata."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from ipfacet import DatasetStore, default_dataset_manager

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_installed_datasets.py"


def run_validation(store: DatasetStore, provider: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--store", str(store.root), "--provider", provider],
        capture_output=True,
        text=True,
        check=False,
    )


def test_opt_in_validation_report_excludes_address_and_values(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "ipinfo_lite.csv").write_text(
        "network,country,country_code,continent,continent_code,asn,as_name,as_domain\n"
        "1.1.1.0/24,Australia,AU,Oceania,OC,AS13335,Example Edge,example.test\n"
        "2606:4700::/32,United States,US,North America,NA,AS13335,Example Edge,example.test\n",
        encoding="utf-8",
    )
    store = DatasetStore(tmp_path / "installed")
    manager = default_dataset_manager(store=store)
    manager.import_dataset("ipinfo", "ipinfo-lite", source, release="fixture-a")
    result = run_validation(store, "ipinfo")
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    snapshot = report["snapshots"]
    assert isinstance(snapshot, list)
    assert snapshot[0]["release"] == "fixture-a"
    assert snapshot[0]["field_states"] == {"ipv4": {"present": 7}, "ipv6": {"present": 7}}
    serialized = json.dumps(report)
    for forbidden in ("1.1.1.1", "2606:4700", "13335", "Example Edge"):
        assert forbidden not in serialized

    installed = store.version_path("ipinfo", "ipinfo-lite", "fixture-a")
    (installed / "ipinfo_lite.csv").write_text("corrupt", encoding="utf-8")
    result = run_validation(store, "ipinfo")
    assert result.returncode == 2
    assert "integrity verification failed" in result.stderr
    assert not result.stdout


def test_missing_selected_snapshot_fails(tmp_path: Path) -> None:
    result = run_validation(DatasetStore(tmp_path), "maxmind")
    assert result.returncode == 2
    assert "no active dataset" in result.stderr
    assert not result.stdout
