"""Reproducible synthetic GeoLite2 ASN CSV batch benchmark; no vendor data."""

from __future__ import annotations

import argparse
import json
import platform
import resource
import sys
import tempfile
import time
from ipaddress import IPv4Address, IPv6Address, ip_address
from pathlib import Path

import polars as pl

from ipfacet import CanonicalField, FieldPrecedence, ResolutionPolicy, enrich_frame, open_database
from ipfacet.providers.maxmind_geolite2 import FILES, MaxMindGeoLite2CSVProvider

HEADER = "network,autonomous_system_number,autonomous_system_organization\n"


def addresses(count: int) -> list[str]:
    base4 = int(ip_address("11.0.0.0"))
    base6 = int(ip_address("2600::"))
    return [
        str(IPv4Address(base4 + (index // 2) * 256 + 1))
        if index % 2 == 0
        else str(IPv6Address(base6 + (index // 2) * (1 << 64) + 1))
        for index in range(count)
    ]


def fixture(path: Path, count: int) -> int:
    base4 = int(ip_address("11.0.0.0"))
    base6 = int(ip_address("2600::"))
    for family, filename in enumerate(FILES):
        with (path / filename).open("w", encoding="utf-8") as handle:
            handle.write(HEADER)
            for index in range(max(1, (count + (1 if family == 0 else 0)) // 2)):
                network = (
                    f"{IPv4Address(base4 + index * 256)}/24"
                    if family == 0
                    else f"{IPv6Address(base6 + index * (1 << 64))}/64"
                )
                handle.write(f"{network},{64500 + index % 100},Synthetic AS\n")
    return sum((path / filename).stat().st_size for filename in FILES)


def run(unique: int, rows: int) -> dict[str, object]:
    if unique < 1 or rows < unique:
        raise ValueError("require 1 <= unique <= rows")
    with tempfile.TemporaryDirectory(prefix="ipfacet-benchmark-") as directory:
        path = Path(directory)
        dataset_bytes = fixture(path, unique)
        ips = addresses(unique)
        telemetry = pl.DataFrame({"ip": (ips * ((rows + unique - 1) // unique))[:rows]})
        rss_multiplier = 1 if sys.platform == "darwin" else 1024
        rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * rss_multiplier
        start = time.perf_counter()
        provider = MaxMindGeoLite2CSVProvider(path, version="synthetic")
        opened = time.perf_counter()
        policy = ResolutionPolicy(
            tuple(
                FieldPrecedence(field, ("maxmind",))
                for field in (CanonicalField.ASN, CanonicalField.AS_NAME, CanonicalField.NETWORK)
            )
        )
        db = open_database(providers=(provider,), policy=policy)
        db.lookup_many(ips)
        first = time.perf_counter()
        db.lookup_many(ips)
        warm = time.perf_counter()
        result = enrich_frame(db, telemetry, ip_column="ip", fields=(CanonicalField.ASN,))
        joined = time.perf_counter()
        frame_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * rss_multiplier
        lookup = pl.DataFrame(
            {
                "ip": ips,
                "joined_asn": [64500 + (index // 2) % 100 for index in range(unique)],
            }
        )
        join_start = time.perf_counter()
        joined_only = telemetry.join(lookup, on="ip", how="left", maintain_order="left")
        join_end = time.perf_counter()
        rss_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * rss_multiplier
        assert isinstance(result, pl.DataFrame) and result.height == rows
        assert joined_only.height == rows
        return {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "polars": pl.__version__,
            "unique_ips": unique,
            "telemetry_rows": rows,
            "ipv4_ips": (unique + 1) // 2,
            "ipv6_ips": unique // 2,
            "dataset_bytes": dataset_bytes,
            "open_seconds": round(opened - start, 4),
            "first_lookup_seconds": round(first - opened, 4),
            "warm_lookup_seconds": round(warm - first, 4),
            "frame_enrichment_seconds": round(joined - warm, 4),
            "native_join_only_seconds": round(join_end - join_start, 4),
            "warm_unique_ips_per_second": round(unique / (warm - first)),
            "rss_before_bytes": rss_before,
            "frame_peak_rss_bytes": frame_peak,
            "peak_process_rss_bytes": rss_peak,
            "deduplication_ratio": round(rows / unique, 2),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unique", type=int, required=True)
    parser.add_argument("--rows", type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.unique, args.rows), sort_keys=True))


if __name__ == "__main__":
    main()
