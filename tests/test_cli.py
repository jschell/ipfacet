from pathlib import Path

import pytest

from ipfacet.cli import main


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "ipfacet 0.1.0.dev0" in capsys.readouterr().out


def test_dataset_cli_airgap_import_list_and_verify(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from ipfacet.dataset_manager import DatasetManager
    from ipfacet.dataset_store import DatasetStore
    from ipfacet.datasets import DatasetDefinition

    source = tmp_path / "source"
    source.mkdir()
    source.joinpath("data.txt").write_text("fixture", encoding="utf-8")
    definition = DatasetDefinition(
        provider="manual",
        dataset="fixture",
        dataset_format="text",
        adapter_version="1",
        license_reference="manual-license",
    )
    manager = DatasetManager(
        store=DatasetStore(tmp_path / "store"),
        definitions=(definition,),
    )

    assert (
        main(
            [
                "datasets",
                "import",
                "manual",
                "fixture",
                str(source),
                "--release",
                "v1",
            ],
            manager=manager,
        )
        == 0
    )
    imported = capsys.readouterr().out
    assert '"release": "v1"' in imported

    assert main(["datasets", "list"], manager=manager) == 0
    assert '"provider": "manual"' in capsys.readouterr().out

    assert main(["datasets", "verify", "manual", "fixture"], manager=manager) == 0
    assert '"release": "v1"' in capsys.readouterr().out


def test_dataset_cli_returns_error_without_registered_acquirer(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from ipfacet.dataset_manager import DatasetManager
    from ipfacet.dataset_store import DatasetStore

    manager = DatasetManager(store=DatasetStore(tmp_path))
    assert main(["datasets", "install", "missing", "fixture"], manager=manager) == 2
    assert "no acquisition helper registered" in capsys.readouterr().out
