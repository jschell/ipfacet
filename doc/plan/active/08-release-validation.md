# Plan 08 — Release Validation and Consumer Pilot Readiness

**Status:** Active  
**Depends on:** Plans 00–07

## Objective

Validate the `1.0.0rc1` artifact across claimed Python/platform boundaries and prepare a real Anomaly-Detections consumer pilot without publishing or tagging a release prematurely.

## Scope

- run full CI on Python 3.12 and 3.13 on Linux, plus Python 3.12 on macOS and Windows,
- install the built wheel outside the checkout and verify its CLI/core import on each platform,
- install each optional Polars, Pandas, and PyArrow extra independently and smoke its DataFrame path on Linux Python 3.13,
- keep provider datasets, credentials, raw SIEM telemetry, and internet lookup out of CI,
- document how Anomaly-Detections' existing `source_ip` and derived actor/IP state can consume IPFacet facts in memory, with an explicit package pin and engagement-local derived state,
- document remaining gates for a final tag/package publication and real licensed dataset smoke checks.

## Out of scope

- publishing a package, creating a release/tag, or changing Anomaly-Detections dependencies,
- storing ordinary raw events in engagement Parquet,
- changing provider semantics or GeoLite's operator-managed old-release deletion.

## Exit criteria

- all matrix jobs and wheel/extras smoke checks pass,
- the consumer pilot boundary and remaining release gates are documented,
- no persistent queried-IP cache or provider database is introduced.
