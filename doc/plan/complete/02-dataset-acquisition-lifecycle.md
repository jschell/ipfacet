# Plan 02 — Dataset Acquisition and Lifecycle

**Status:** Complete  
**Depends on:** Plans 00–01

## Objective

Provide safe helpers for acquiring or importing reference datasets while keeping lookup fully offline and respecting provider-specific credentials, licensing, attribution, versioning, and retention requirements.

## Scope

- dataset-provider/acquisition protocol separate from lookup provider,
- platform-appropriate shared data directory,
- `datasets available/list/status/install/import/update/verify` CLI,
- Python `DatasetManager`,
- environment/external credential discovery,
- no plaintext credential storage by default,
- download staging,
- integrity/checksum verification when available,
- schema validation,
- smoke lookups,
- manifest generation,
- atomic activation,
- rollback to previous valid version when legally retainable,
- staleness reporting,
- provider-specific attribution and retention metadata,
- manual/air-gapped import.

## Manifest

At minimum record:

- provider,
- dataset,
- exact release/version,
- source/acquisition method,
- acquired timestamp,
- activated timestamp,
- format,
- integrity/hash data,
- schema/adapter version,
- applicable attribution/license identifier or reference,
- retention constraints.

## Safety requirements

- Never bundle provider datasets in the Python distribution.
- Never commit downloaded datasets.
- Never commit credentials.
- Failed updates cannot replace a working active dataset.
- Generic retention settings cannot override provider restrictions.
- No daemon/scheduler. Update commands run once and exit.
- Avoid unnecessary downloads and respect provider download limits.

## Research gate

Before enabling automated download for a provider, document:

- authentication mechanism,
- permitted automation,
- download limits,
- attribution,
- redistribution restrictions,
- retention/destruction requirements,
- whether old snapshots may be retained.

If terms are unclear, support manual import first.

## Tests

Use local synthetic archives and mock acquisition endpoints. CI must not require external accounts or downloads.

## Exit criteria

- synthetic provider supports install/import/update/verify/rollback,
- atomic activation failure paths are tested,
- retention policy is enforceable per provider,
- air-gapped import works,
- credentials never enter manifests/logs/config by default,
- CI passes.


## Completion record

Completed after the final frozen-lock CI run passed.

Implemented and validated:

- acquisition protocol remains separate from offline lookup providers,
- provider dataset definitions are registered independently from download acquirers, allowing manual-only support,
- platform-appropriate per-user data roots,
- immutable version directories with staged validation and atomic active-pointer replacement,
- credential-free manifests with release, source, timestamps, format, local snapshot SHA-256, adapter version, license/attribution, retention, and staleness metadata,
- verified provider/source checksum metadata is recorded separately from the installed-tree hash,
- provider schema/smoke validation hooks,
- failed validation and failed activation leave the prior active snapshot usable,
- provider retention restrictions control snapshot destruction and rollback availability,
- manual/air-gapped import uses registered provider policy and the same validation path,
- symlinks are rejected from snapshot trees,
- environment-only credential discovery helper,
- `datasets available/list/status/install/import/update/verify/rollback` CLI,
- real-provider automated downloads remain gated on provider-specific terms research.

Validation:

- `uv sync --frozen --dev` — pass
- `uv lock --check` — pass
- Ruff lint — pass
- Ruff format — pass
- strict Pyright — 0 errors, 0 warnings
- pytest — 65 passed
- `uv build` — pass
