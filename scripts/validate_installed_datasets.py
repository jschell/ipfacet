"""Read-only, opt-in smoke of operator-installed provider snapshots."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from ipaddress import ip_address
from pathlib import Path
from unittest.mock import patch

import ipfacet
from ipfacet import DatasetStore, FieldState, default_dataset_manager
from ipfacet.providers import open_ip2proxy_lite, open_ipinfo_lite, open_maxmind_geolite2

PROVIDERS = {
    "ipinfo": ("ipinfo-lite", open_ipinfo_lite),
    "ip2proxy": ("ip2proxy-lite-px8", open_ip2proxy_lite),
    "maxmind": ("geolite2-asn", open_maxmind_geolite2),
}
SAMPLES = (ip_address("1.1.1.1"), ip_address("2606:4700::1111"))


def validate(store: DatasetStore, selected: list[str]) -> dict[str, object]:
    manager = default_dataset_manager(store=store)
    snapshots: list[dict[str, object]] = []
    for key in selected:
        dataset, opener = PROVIDERS[key]
        manifest = manager.verify(key, dataset)
        provider = opener(store)
        if (provider.identity.provider, provider.identity.dataset, provider.identity.version) != (
            key,
            dataset,
            manifest.release,
        ):
            raise ValueError(f"{key}/{dataset}: lookup snapshot does not match verified manifest")
        samples: dict[str, dict[str, int]] = {}
        # Acquisition is separate; reject any network attempt during lookup.
        with (
            patch("socket.socket.connect", side_effect=RuntimeError("network access attempted")),
            patch("urllib.request.urlopen", side_effect=RuntimeError("network access attempted")),
        ):
            for address in SAMPLES:
                result = provider.lookup(address)
                if result.ip != address or result.identity != provider.identity:
                    raise ValueError(
                        f"{key}/{dataset}: lookup returned another address or snapshot"
                    )
                if not result.fields or any(
                    field.state is FieldState.LOOKUP_ERROR for field in result.fields
                ):
                    raise ValueError(f"{key}/{dataset}: lookup failed")
                samples["ipv4" if address.version == 4 else "ipv6"] = dict(
                    sorted(Counter(field.state.value for field in result.fields).items())
                )
        snapshots.append(
            {
                "provider": key,
                "dataset": dataset,
                "release": manifest.release,
                "sha256": manifest.integrity_value,
                "adapter_version": manifest.adapter_version,
                "stale": manifest.is_stale(),
                "license_reference": manifest.license_reference,
                "field_states": samples,
            }
        )
    return {"ipfacet_version": ipfacet.__version__, "snapshots": snapshots}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, help="installed dataset store root")
    parser.add_argument(
        "--provider",
        action="append",
        choices=tuple(PROVIDERS),
        required=True,
        help="select each installed provider to validate (repeatable)",
    )
    args = parser.parse_args()
    try:
        report = validate(DatasetStore(args.store), list(dict.fromkeys(args.provider)))
    except (ipfacet.DatasetError, OSError, ValueError, RuntimeError) as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
