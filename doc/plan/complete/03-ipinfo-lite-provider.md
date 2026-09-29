# Plan 03 — IPinfo Lite Provider

**Status:** Complete  
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


## Completion record

Completed after the final implementation gate passed.

Implemented and validated:

- current IPinfo Lite license, attribution, automated-download, rate-limit, retention, and schema research gate,
- CC BY-SA 4.0 attribution in project documentation and installed manifests,
- registered IPinfo Lite dataset definition and default CLI acquisition helper,
- external `IPINFO_TOKEN` authentication with no credential persistence,
- sanitized acquisition failures and credential-free source provenance,
- one explicit database download per install/update invocation; no scheduler or lookup-time network access,
- gzip CSV acquisition, downloaded-artifact SHA-256, and Last-Modified + hash snapshot identity,
- manual/air-gapped import through the Plan-02 lifecycle,
- exact eight-column current Lite schema validation,
- full pre-activation row/network validation,
- compact IPv4/IPv6 network-to-file-offset index,
- canonical ASN, AS name/domain, network, country, and continent-code mapping,
- explicit NOT_FOUND for blank provider fields and absent ranges,
- unsupported state for city, region, timezone, ISP, privacy, and network-trait fields,
- neutral ASN provenance that preserves ambiguity between IPinfo's current "announcing ASN" and "range ownership" descriptions,
- documented provider sample expectations and synthetic acquisition fixtures,
- CSV support without declaring CSV the permanent preferred format; Plan 06 retains the MMDB/Parquet benchmark decision.

Validation:

- `uv sync --frozen --dev` — pass
- `uv lock --check` — pass
- Ruff lint — pass
- Ruff format — pass
- strict Pyright — 0 errors, 0 warnings
- pytest — 78 passed
- `uv build` — pass
