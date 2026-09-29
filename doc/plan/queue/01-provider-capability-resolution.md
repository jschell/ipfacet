# Plan 01 — Provider, Capability, and Resolution Architecture

**Status:** Queue  
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
