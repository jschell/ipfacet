# Batch and DataFrame enrichment

Install one or more optional boundaries: `pip install 'ipfacet[polars]'`, `pip install 'ipfacet[pandas]'`, or `pip install 'ipfacet[arrow]'`. The core package has no DataFrame dependency. Polars is the preferred batch path; Pandas and PyArrow keep their input/output type. Development uses the locked `uv` environment.

```python
import polars as pl
from ipfacet import CanonicalField, enrich_frame, open_database

# Supply installed providers and an explicit ResolutionPolicy as in README.md.
db = open_database(providers=[provider], policy=policy)
events = pl.DataFrame({"source_ip": ["1.1.1.1", "1.1.1.1", None]})
enriched = enrich_frame(
    db, events, ip_column="source_ip", fields=(CanonicalField.ASN,),
    include_provenance=True, include_conflicts=True,
)
```

`enrich_frame` takes an explicit IP column and produces deterministic `ipfacet_` columns: `scope`, `traits` (JSON array), each selected canonical field and its `_state`, and optional `provenance`/`conflicts` JSON. `prefix` changes the namespace. All canonical fields are selected by default; specify `fields` for a narrower table. Null IPs produce null enrichment columns. Invalid non-null IPs raise an error; input columns with output names are rejected. Raw telemetry stays in memory; no queried-IP history or persistent lookup cache is written.

The boundary collects unique raw strings, normalizes them with `parse_ip`, invokes `lookup_many` once per canonical IP, then joins/gathers the result columns onto the original rows. Polars uses a left hash join, Pandas uses indexed mapping, and Arrow uses compute index/take. Equivalent IPv6 spellings share one provider search. This avoids repeated provider searches on duplicated event IPs, while retaining row order and input type.

## Reproduce the benchmarks

Run each case in a fresh process from the repository root:

```sh
uv run --frozen python benchmarks/batch.py --unique 1 --rows 1
uv run --frozen python benchmarks/batch.py --unique 1000 --rows 2500
uv run --frozen python benchmarks/batch.py --unique 10000 --rows 250000
uv run --frozen python benchmarks/batch.py --unique 100000 --rows 100000
# Optional stress:
uv run --frozen python benchmarks/batch.py --unique 250000 --rows 250000
uv run --frozen python benchmarks/compare_parquet.py --unique 50000
```

The harness generates sorted synthetic GeoLite2 ASN style CSV blocks, half IPv4 `/24` and half IPv6 `/64`, with matching IPs. It records opening/index construction, a first lookup pass, a second lookup pass in the same process, full DataFrame enrichment, a native join-only pass over precomputed values, dataset bytes, deduplication ratio, and process high-water RSS. `frame_enrichment_seconds` includes uniqueness extraction, lookup, result projection, and join-back. `native_join_only_seconds` excludes lookup and result-table construction. The process is cold per command; warm refers to a second pass after opening the provider, not a persistent IP cache. OS file cache may already be warm. Measurements are illustrative, not a hardware guarantee.

## Results on this runner, September 29, 2026

Linux x86_64, AMD EPYC 9V74 VM (9 visible CPUs, 9.7 GiB RAM), Python 3.12.14, Polars 1.44.2. Results are single runs in fresh processes, rounded to three decimal places.

| Unique IPs | Event rows | CSV bytes | Open | First lookup | Warm lookup | Full frame | Native join only | Peak process RSS |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 188 | 0.0002 s | 0.0004 s | 0.0002 s | 0.257 s | 0.0009 s | 170 MB |
| 1,000 | 2,500 | 34,630 | 0.015 s | 0.164 s | 0.161 s | 0.462 s | 0.0011 s | 183 MB |
| 10,000 | 250,000 | 350,994 | 0.130 s | 1.838 s | 1.964 s | 2.370 s | 0.0048 s | 288 MB |
| 100,000 | 100,000 | 3,596,054 | 1.289 s | 20.015 s | 20.542 s | 20.344 s | 0.0077 s | 637 MB |

Warm lookup throughput was about 5,000 unique IP/s at 10k and 100k. The 250k event/10k unique case is about 25:1 deduplication, so most time is provider lookup and result projection rather than the native join. Real provider CSVs have far more networks than these fixtures; large real files need a separate opt-in benchmark with licensed data and no CI download.

## Reader choice and next performance work

The current default remains the validated provider-native CSV reader with a compact network-offset index. It supports both IP families, exact snapshot provenance, no extra runtime dependency, and offline use. MaxMind reports production GeoLite ASN CSV around 56–59 MB and MMDB around 12 MB for May–August 2026; our synthetic fixture is much smaller and does not estimate real index startup or memory. The CSV benchmark shows practical deduplicated batch behavior but a clear cost at 100k unique IPs.

The separate Parquet experiment writes 50,000 synthetic IPv4 `/24` ranges to a 103,147-byte file and performs an in-memory `join_asof` plus end-bound check: 0.0034 s to read and 0.0014 s for the join on this runner. This is a constrained, aligned IPv4 experiment. It omits arbitrary prefix overlap, IPv6, provider metadata, canonical conflict resolution, and result projection, so it is not a like-for-like replacement measurement. MMDB is substantially smaller according to MaxMind's published sizes, but a full-size, same-release MMDB/CSV performance comparison requires a licensed dataset; no real dataset is bundled or downloaded in CI. DuckDB range join is deferred until a general IPv4/IPv6 interval strategy is justified. The production default will be revisited when the same-release readers can be validated end to end.
