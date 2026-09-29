"""Synthetic IPv4 /24 range-join experiment; not a production GeoLite reader."""

from __future__ import annotations

import argparse
import json
import tempfile
import time
from ipaddress import ip_address
from pathlib import Path

import polars as pl


def run(count: int) -> dict[str, object]:
    base = int(ip_address("11.0.0.0"))
    with tempfile.TemporaryDirectory(prefix="ipfacet-parquet-") as directory:
        path = Path(directory) / "ranges.parquet"
        source = pl.DataFrame(
            {
                "start": [base + index * 256 for index in range(count)],
                "end": [base + index * 256 + 255 for index in range(count)],
                "asn": [64500 + index % 100 for index in range(count)],
            }
        )
        source.write_parquet(path)
        query = pl.DataFrame({"ip_int": [base + index * 256 + 1 for index in range(count)]})
        start = time.perf_counter()
        ranges = pl.read_parquet(path)
        opened = time.perf_counter()
        result = query.join_asof(ranges, left_on="ip_int", right_on="start", strategy="backward")
        result = result.with_columns(
            pl.when(pl.col("ip_int") <= pl.col("end"))
            .then(pl.col("asn"))
            .otherwise(None)
            .alias("matched_asn")
        )
        finished = time.perf_counter()
        assert result.height == count and result["matched_asn"].null_count() == 0
        return {
            "ipv4_unique": count,
            "parquet_bytes": path.stat().st_size,
            "read_seconds": round(opened - start, 4),
            "join_seconds": round(finished - opened, 4),
            "scope": "synthetic aligned IPv4 /24 only; excludes normalization and provenance",
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unique", type=int, default=50000)
    args = parser.parse_args()
    print(json.dumps(run(args.unique), sort_keys=True))


if __name__ == "__main__":
    main()
