# Plan 05 — MaxMind GeoLite2 Provider

**Status:** Queue  
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

## Mandatory retention behavior

Current GeoLite terms require old GeoLite database/data versions to cease use and be destroyed within 30 days following release of an updated database.

The adapter/lifecycle policy must therefore:

- not support indefinite GeoLite snapshot retention,
- expose the provider-specific destruction deadline,
- remove obsolete versions within the required window,
- preserve reproducibility through result provenance/version/hash rather than assuming the source database can be retained forever,
- avoid a generic `retain_versions` setting that could violate provider terms.

Terms must be revalidated at implementation time.

## Exit criteria

- offline ASN lookup works for IPv4/IPv6,
- update path enforces provider-specific retention constraints,
- attribution/license metadata is surfaced,
- cross-provider disagreement is preserved and resolved by policy,
- CI passes.
