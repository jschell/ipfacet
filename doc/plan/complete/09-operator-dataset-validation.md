# Plan 09 — Operator Dataset Validation

**Status:** Complete  
**Depends on:** Plan 08

## Objective

Make the remaining real-dataset release gate reproducible on an operator's machine, without distributing licensed files or requiring credentials in CI.

## Scope

- provide a read-only, opt-in command for selected installed provider snapshots,
- verify active snapshot integrity and adapter schema, then exercise both address families through the offline provider lookup path,
- emit a compact report with package version, snapshot release/hash, freshness, and aggregate field states; do not record sampled IPs, field values, credentials, or raw telemetry,
- document what a human must review before tagging/publishing V1, including provider terms and GeoLite operator-managed deletion,
- exercise the command with synthetic installed fixtures in CI.

## Out of scope

- acquiring or redistributing third-party datasets, performing online lookups, automatically deleting old GeoLite releases, tagging/publishing, or changing the consumer repository.

## Exit criteria

- the command succeeds on synthetic installed snapshots, fails on missing/corrupt snapshots and lookup errors, and emits no address/value data,
- Ruff, Pyright, pytest, and the repository CI pass,
- the release record clearly separates completed synthetic/cross-platform checks from unrun licensed-data checks.
