# Plan 05 — MaxMind GeoLite2 Provider

**Status:** Complete  
**Depends on:** Plans 01–02

## Objective

Implement GeoLite2 as an independent ASN/geography provider and validate cross-provider conflict behavior.

## Scope

- GeoLite2 ASN first; Country/City only where useful to canonical fields,
- MMDB reader and/or documented CSV path as justified by performance,
- account/license-key based acquisition helper,
- manual import,
- IPv4/IPv6,
- field-level provenance,
- attribution metadata,
- conflict comparison with IPinfo.

## Retention responsibility

Current GeoLite terms require old GeoLite database/data versions to cease use and be destroyed within 30 days following release of an updated database.

The adapter/lifecycle policy must therefore:

- explain the 30-day destruction deadline in documentation and metadata guidance,
- leave deletion of old snapshots to the operator, as explicitly requested,
- preserve reproducibility through result provenance/version/hash after the operator removes old data.

Terms must be revalidated at implementation time.

## Implementation outcome

The ASN CSV adapter, authenticated acquisition, manual import, IPv4/IPv6 offline
lookup, provenance, and IPinfo conflict tests are implemented. The operator manages
destruction of superseded GeoLite data under the current EULA; IPFacet does not
delete old releases automatically. See `doc/providers/maxmind-geolite2.md`.

CI passed on PR #6 (98 tests, Ruff, strict Pyright, lock check, and build).

## Exit criteria

- offline ASN lookup works for IPv4/IPv6,
- update path preserves old snapshots and documents the operator's destruction duty,
- attribution/license metadata is surfaced,
- cross-provider disagreement is preserved and resolved by policy,
- CI passes.
