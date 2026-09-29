# Plan 03 — IPinfo Lite Provider

**Status:** Active  
**Depends on:** Plans 01–02

## Objective

Implement IPinfo Lite as the first real offline provider for basic ASN and country/continent enrichment.

## Expected free/Lite semantics to validate at implementation time

Current provider documentation describes Lite as including:

- ASN,
- AS name,
- AS domain,
- country/country code,
- continent/continent code.

Do not assume city, region, privacy/VPN/proxy, or richer AS-type fields are part of Lite.

## Scope

- document current Lite license/attribution/download terms,
- provider acquisition helper when terms permit,
- manual import,
- choose supported local format(s) based on Plan 06 benchmark needs,
- IPv4 and IPv6,
- canonical mapping,
- exact dataset version/provenance,
- provider-published sample/synthetic fixture tests,
- missing-range behavior,
- schema-change detection.

## Format strategy

IPinfo currently documents downloadable CSV, JSON, MMDB, and Parquet. Do not hard-code Parquet as the only runtime format before performance testing. Prefer a reader abstraction that permits at least one efficient single-lookup path and one efficient batch path.

## Exit criteria

- fully offline lookup after install/import,
- canonical ASN/name/domain and country/continent fields match documented sample expectations,
- IPv4/IPv6 tests pass,
- attribution/license requirements documented,
- no Lite result is mislabeled as paid privacy/network-type data,
- CI passes.
