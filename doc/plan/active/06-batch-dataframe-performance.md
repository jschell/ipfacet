# Plan 06 — Batch and DataFrame Performance

**Status:** Active  
**Depends on:** At least one real provider from Plans 03–05

## Objective

Make IPFacet practical for SIEM-scale enrichment without coupling the public API to one storage format.

## Workload model

A typical consumer may have ~250,000 telemetry rows but far fewer unique source IPs. Enrichment should deduplicate IPs, enrich uniques, and join results back rather than performing one lookup per event.

## Scope

Benchmark representative workloads:

- 1 lookup,
- 1,000 unique IPs,
- 10,000 unique IPs,
- 100,000 unique IPs,
- optional 250,000 unique IP stress case,
- IPv4 and IPv6 mixes,
- cold and warm process behavior.

Compare applicable formats/readers such as:

- MMDB,
- Parquet/Polars,
- provider-native binary,
- DuckDB/range-join approach if justified.

## DataFrame API

Support:

- Polars as preferred internal/batch path,
- Pandas input/output boundary,
- PyArrow input/output boundary,
- explicit IP column,
- deterministic column naming,
- configurable inclusion of provenance/conflict detail.

Do not force all formats through row-by-row Python calls.

## Metrics

- wall-clock lookup/enrichment time,
- throughput,
- peak memory,
- startup/open cost,
- dataset size,
- deduplication effect,
- join-back cost.

## Exit criteria

- benchmark harness is reproducible,
- default reader choices are evidence-based,
- batch lookup does not perform redundant provider searches for duplicate IPs,
- 100k-unique-IP workload has documented time/memory results,
- no persistent queried-IP cache is introduced,
- CI correctness tests pass; large benchmarks may run separately.
