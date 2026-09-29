# AGENTS.md

## Purpose

IPFacet is a provider-neutral Python package for local/offline IP enrichment. Preserve that boundary: factual reference-data normalization belongs here; threat intelligence, maliciousness scoring, and behavioral anomaly detection do not.

## Read plans first

Before changing code:

1. Read `README.md` and `doc/overview.md`.
2. Read `doc/plan/active/`.
3. Check `doc/plan/queue/` for dependencies and future constraints.
4. Work only from an active plan unless making a narrowly scoped corrective change.

Plan lifecycle:

```text
queue -> active -> complete
```

Move a plan to `complete` only when all exit criteria are satisfied and CI passes.

## Python/tooling

- Python 3.12+.
- Use `uv` for environments, dependency management, locking, and command execution.
- Commit `uv.lock`.
- Do not add `requirements.txt`, Poetry, Pipenv, or a parallel dependency source.
- Use a `src/` package layout.
- Ruff for lint/format.
- Strict Pyright for type checking.
- pytest for tests.
- Public APIs must be typed.
- Avoid hidden global mutable state.

## Architectural boundaries

- Canonical models must not expose provider-specific dictionaries as the public API.
- Provider adapters may depend on canonical interfaces; canonical/core modules must not import provider implementations.
- Dataset acquisition is separate from dataset lookup.
- Lookup must work fully offline once datasets are installed/imported.
- Do not make network calls during ordinary lookup.
- Do not persist a history of queried IP addresses.
- In-process caches are allowed when bounded and non-persistent.
- Never silently combine values from different versions of the same provider dataset.
- Never resurrect a missing value from an older dataset version.
- Cross-provider fallback is allowed only through explicit field-resolution policy.
- Preserve disagreements and provenance even when a resolved value is selected.
- Do not convert provider threat/risk/reputation fields into canonical IPFacet facts.
- Network traits are contextual facts, not maliciousness findings.

## Dataset and licensing rules

- Never commit third-party provider databases to the repository.
- Never commit provider credentials, tokens, account IDs, or license keys.
- Credentials should come from environment variables or explicitly supported external credential mechanisms.
- Dataset installers must record source, version/release, acquisition time, integrity information where available, format, and relevant license/attribution metadata.
- Provider-specific retention restrictions override generic snapshot retention.
- Updates must be staged and validated before atomic activation.
- A failed update must leave the previously active dataset usable.
- Manual/air-gapped dataset import must remain supported.

## Semantics

Do not normalize semantically different concepts merely because providers use similar labels. In particular distinguish where evidence permits:

- BGP/origin ASN
- registered/allocation organization
- AS organization
- ISP/network operator
- vendor network classification

Unknown, unsupported, not found, conflict, and lookup failure are distinct states.

Special/private/reserved IPv4 and IPv6 ranges should be classified locally rather than sent through provider lookup paths.

## Testing

Use synthetic fixtures or provider-published sample data whose use is permitted. Do not use customer telemetry.

Tests should cover:

- IPv4 and IPv6
- special/private/reserved ranges
- provider capability declarations
- normalization
- source precedence
- fallback
- conflicts
- missing/unsupported/error states
- version isolation
- provenance
- schema changes
- atomic update/rollback behavior
- batch deduplication and deterministic results

Integration tests requiring downloaded provider datasets must be opt-in and must not make CI dependent on private credentials.

## Changes to public behavior

When changing canonical fields, provider precedence, provenance, retention, or dataset semantics:

- update documentation,
- add migration/compatibility notes when appropriate,
- add tests demonstrating the old and new behavior,
- do not silently reinterpret persisted values.

## Completion standard

A plan is complete only when its documented exit criteria are met, relevant tests exist, Ruff passes, strict Pyright passes, pytest passes, and documentation reflects the implemented behavior.
