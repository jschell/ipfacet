# Plan 01 — Provider, Capability, and Resolution Architecture

**Status:** Complete  
**Depends on:** Plan 00

## Objective

Implement provider-neutral capability discovery, provider observations, field-specific precedence, fallback, and explicit conflict handling.

## Scope

- `EnrichmentProvider` protocol.
- Capability model for ASN, organization/domain, prefix/network, country/continent, optional geography, ISP, and network traits.
- Provider result/observation contract.
- Field-specific source-precedence configuration.
- Deterministic resolution engine.
- Explicit distinction between fallback and conflict.
- Explanation API such as `result.explain("asn")`.
- Provider/version isolation.
- Unknown provider fields retained only as provider metadata, never silently promoted into canonical fields.

## Resolution rules

1. One selected version per provider participates in a lookup.
2. Never mix versions from the same provider.
3. Never use an older provider version to fill a missing value in the selected version.
4. Across providers, use explicit per-field precedence.
5. Missing primary value may fall through to the next configured provider.
6. Conflicting present values select according to precedence while preserving all observations.
7. Agreement is recorded but does not create statistical confidence.

## Semantic guardrail

Before two provider fields map to one canonical field, document that they represent the same concept. Do not collapse BGP origin, allocation owner, AS organization, ISP, and network operator without evidence.

## Tests

- capability discovery,
- precedence,
- fallback,
- conflict,
- agreement,
- unsupported/not-found/error behavior,
- version isolation,
- deterministic explanations,
- provider-order independence where policy is unchanged.

## Exit criteria

- two synthetic providers can contribute different canonical fields,
- conflict/fallback behavior is fully tested,
- field provenance survives resolution,
- provider implementations are not imported by canonical/core modules,
- CI passes.


## Completion record

Completed on the Plan 01 implementation branch after the final frozen-lock CI run passed.

Implemented and validated:

- typed `EnrichmentProvider`, provider identity, observation, result, and metadata contracts,
- explicit semantic capabilities for ASN, AS organization/domain, prefix, geography, ISP, and network traits,
- field-specific deterministic precedence independent of provider registration order,
- fallback, agreement, conflict, not-found, unsupported, and lookup-error behavior,
- one-selected-version-per-provider enforcement,
- field-level provenance including provider dataset version and source semantics,
- deterministic `result.explain(...)` traces,
- multi-valued network traits with per-observation provenance,
- semantic mapping guardrails documented in `doc/provider-resolution.md`,
- vendor-specific metadata retained only at the provider boundary and never promoted automatically.

Validation:

- `uv sync --frozen --dev` — pass
- `uv lock --check` — pass
- Ruff lint — pass
- Ruff format — pass
- strict Pyright — 0 errors, 0 warnings
- pytest — 48 passed
- `uv build` — pass
