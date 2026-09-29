# Plan 07 — Consumer Integration and V1 Hardening

**Status:** Queue  
**Depends on:** Plans 00–06

## Objective

Stabilize IPFacet V1 as a reusable dependency and validate integration with a real consumer without importing consumer-specific anomaly logic into IPFacet.

## Scope

- semantic versioning/release policy,
- changelog,
- generated/public API documentation as appropriate,
- compatibility/migration rules for canonical schema changes,
- package build/install validation,
- CLI usability,
- dataset status diagnostics,
- consumer contract tests,
- integration example for Anomaly-Detections or equivalent notebook workflow.

## Consumer boundary

IPFacet provides factual enrichment. A consumer may derive:

- actor -> ASN relationships,
- ASN novelty/rarity,
- country novelty,
- network-trait context,
- cross-source pivots.

Those behavioral calculations remain outside IPFacet.

## V1 acceptance surface

- IPv4 + IPv6,
- offline lookup,
- single + batch lookup,
- at least two independently useful real providers if licensing/capability validation supports them,
- provider-neutral canonical model,
- provenance,
- deterministic precedence,
- conflict preservation,
- dataset install/import/update/verify lifecycle,
- provider-specific retention enforcement,
- Polars/Pandas/PyArrow integration,
- no DNS/reputation/threat-intelligence dependency.

## Exit criteria

- clean installation from built package,
- documented end-to-end offline example,
- consumer integration test passes,
- public API compatibility policy documented,
- all prior plans complete,
- full CI passes,
- V1 release candidate can be reproduced from repository state.
