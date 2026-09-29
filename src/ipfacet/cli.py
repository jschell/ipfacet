"""IPFacet command-line interface."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from ipfacet import __version__
from ipfacet.dataset_manager import DatasetManager
from ipfacet.exceptions import DatasetError


def _manifest_json(manifest: object) -> str:
    from ipfacet.datasets import DatasetManifest

    if not isinstance(manifest, DatasetManifest):
        raise TypeError("expected DatasetManifest")
    return json.dumps(
        {
            "provider": manifest.provider,
            "dataset": manifest.dataset,
            "release": manifest.release,
            "format": manifest.dataset_format,
            "source": manifest.source,
            "acquired_at": manifest.acquired_at.isoformat(),
            "activated_at": (
                None if manifest.activated_at is None else manifest.activated_at.isoformat()
            ),
            "stale": manifest.is_stale(),
        },
        sort_keys=True,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ipfacet", description="Offline IP enrichment")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command")
    datasets = commands.add_parser("datasets", help="manage local reference datasets")
    actions = datasets.add_subparsers(dest="dataset_command", required=True)

    actions.add_parser("available", help="list registered acquisition helpers")
    actions.add_parser("list", help="list active installed datasets")

    status = actions.add_parser("status", help="show one active dataset")
    status.add_argument("provider")
    status.add_argument("dataset")

    for name in ("install", "update"):
        command = actions.add_parser(name, help=f"{name} a registered provider dataset")
        command.add_argument("provider")
        command.add_argument("dataset")

    verify = actions.add_parser("verify", help="verify integrity and provider schema")
    verify.add_argument("provider")
    verify.add_argument("dataset")
    verify.add_argument("--release")

    rollback = actions.add_parser("rollback", help="activate a retained valid snapshot")
    rollback.add_argument("provider")
    rollback.add_argument("dataset")
    rollback.add_argument("--release")

    imported = actions.add_parser("import", help="import a local/air-gapped dataset directory")
    imported.add_argument("provider")
    imported.add_argument("dataset")
    imported.add_argument("source", type=Path)
    imported.add_argument("--release", required=True)
    imported.add_argument("--source-reference", default="manual-import")
    return parser


def main(argv: Sequence[str] | None = None, *, manager: DatasetManager | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command is None:
        return 0
    dataset_manager = manager or DatasetManager()
    try:
        if args.dataset_command == "available":
            for definition in dataset_manager.available():
                print(f"{definition.provider}/{definition.dataset}")
        elif args.dataset_command == "list":
            for manifest in dataset_manager.list_installed():
                print(_manifest_json(manifest))
        elif args.dataset_command == "status":
            print(_manifest_json(dataset_manager.status(args.provider, args.dataset)))
        elif args.dataset_command == "install":
            print(_manifest_json(dataset_manager.install(args.provider, args.dataset)))
        elif args.dataset_command == "update":
            print(_manifest_json(dataset_manager.update(args.provider, args.dataset)))
        elif args.dataset_command == "verify":
            print(
                _manifest_json(
                    dataset_manager.verify(
                        args.provider,
                        args.dataset,
                        release=args.release,
                    )
                )
            )
        elif args.dataset_command == "rollback":
            print(
                _manifest_json(
                    dataset_manager.rollback(
                        args.provider,
                        args.dataset,
                        release=args.release,
                    )
                )
            )
        elif args.dataset_command == "import":
            print(
                _manifest_json(
                    dataset_manager.import_dataset(
                        args.provider,
                        args.dataset,
                        args.source,
                        release=args.release,
                        source_reference=args.source_reference,
                    )
                )
            )
        return 0
    except DatasetError as exc:
        print(f"ipfacet: {exc}")
        return 2
