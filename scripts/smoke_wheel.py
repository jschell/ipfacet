"""Install the built wheel in isolated environments outside the checkout."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

CORE_CHECK = (
    "import importlib.metadata, ipfacet; "
    'assert importlib.metadata.version("ipfacet") == "1.0.0rc1"; '
    'assert ipfacet.open_database().lookup("192.0.2.1").scope '
    "is ipfacet.IPScope.DOCUMENTATION"
)
FRAME_CHECK = (
    "import os, ipfacet; "
    'name=os.environ["IPFACET_SMOKE_EXTRA"]; '
    'frame=(__import__("polars").DataFrame({"ip":["1.1.1.1",None]}) '
    'if name=="polars" else __import__("pandas").DataFrame({"ip":["1.1.1.1",None]}) '
    'if name=="pandas" else __import__("pyarrow").table({"ip":["1.1.1.1",None]})); '
    'result=ipfacet.enrich_frame(ipfacet.open_database(),frame,ip_column="ip"); '
    "assert len(result)==2"
)


def smoke(wheel: Path, *, extra: str | None = None) -> None:
    with tempfile.TemporaryDirectory(prefix="ipfacet-wheel-") as directory:
        root = Path(directory)
        environment = root / "venv"
        subprocess.run(["uv", "venv", "--python", sys.executable, str(environment)], check=True)
        binaries = environment / ("Scripts" if os.name == "nt" else "bin")
        python = binaries / ("python.exe" if os.name == "nt" else "python")
        cli = binaries / ("ipfacet.exe" if os.name == "nt" else "ipfacet")
        package = f"{wheel}[{extra}]" if extra else str(wheel)
        subprocess.run(["uv", "pip", "install", "--python", str(python), package], check=True)
        subprocess.run([str(python), "-c", CORE_CHECK], cwd=root, check=True)
        subprocess.run([str(cli), "--version"], cwd=root, check=True)
        if extra is not None:
            env = {**os.environ, "IPFACET_SMOKE_EXTRA": extra}
            subprocess.run([str(python), "-c", FRAME_CHECK], cwd=root, env=env, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--extras", action="store_true", help="test each DataFrame extra separately"
    )
    args = parser.parse_args()
    wheels = list(Path("dist").glob("ipfacet-1.0.0rc1-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError("expected exactly one built release-candidate wheel")
    wheel = wheels[0].resolve()
    smoke(wheel)
    if args.extras:
        for extra in ("polars", "pandas", "arrow"):
            smoke(wheel, extra=extra)


if __name__ == "__main__":
    main()
