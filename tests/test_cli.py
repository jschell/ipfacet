import pytest

from ipfacet.cli import main


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "ipfacet 0.1.0.dev0" in capsys.readouterr().out
