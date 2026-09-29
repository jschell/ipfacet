# Plan 00 — Foundation and Canonical API

**Status:** Complete

## Objective

Establish IPFacet as a typed Python 3.12+ package with a minimal provider-neutral public API and CI foundation. This plan defines the contracts later provider and dataset plans must implement without prematurely choosing a vendor storage format.

## Scope

- `pyproject.toml` with `uv` workflow and committed lockfile.
- `src/ipfacet/` package layout.
- Ruff, strict Pyright, pytest, and GitHub Actions.
- Canonical IPv4/IPv6 input parsing.
- Local classification for private/special-purpose ranges.
- Typed canonical result, field observation, field state, provenance, and conflict models.
- Minimal `open_database()`, `lookup()`, and `lookup_many()` contracts backed initially by synthetic/in-memory providers.
- Stable exception hierarchy.
- Initial CLI shell sufficient to expose version/help.
- Public API documentation in README/doc.
- Synthetic fixtures only.

## Canonical requirements

A field must be able to represent:

- resolved value,
- PRESENT / NOT_FOUND / UNSUPPORTED / CONFLICT / LOOKUP_ERROR,
- selected provenance,
- all contributing observations,
- conflict state.

Do not introduce numeric confidence merely because multiple sources agree.

Network characteristics must support multiple traits rather than one mutually exclusive vendor type.

## Non-goals

- Real provider downloads/readers.
- Threat/reputation data.
- DNS.
- Persistent query cache.
- Dataset scheduler.
- Anomaly detection.

## Tests

- valid/invalid IPv4 and IPv6,
- private/loopback/link-local/multicast/documentation/CGNAT/ULA and other Python-recognizable special ranges,
- deterministic canonical serialization,
- field states and conflict representation,
- synthetic batch lookup,
- no network access required by tests.

## Exit criteria

- `uv sync --frozen` succeeds from a clean checkout.
- Ruff lint and format checks pass.
- strict Pyright passes.
- pytest passes.
- package builds successfully.
- public API is typed and documented.
- no provider-specific implementation leaks into canonical models.
- CI runs all required checks.


## Completion record

Completed on the Plan 00 implementation branch after the frozen-lock CI run passed.

Validation:

- `uv sync --frozen --dev` — pass
- `uv lock --check` — pass
- Ruff lint — pass
- Ruff format — pass
- strict Pyright — 0 errors, 0 warnings
- pytest — 28 passed
- `uv build` — pass
- canonical serialization regression test — pass
- no real provider data/network dependency introduced
