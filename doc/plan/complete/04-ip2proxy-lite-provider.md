# Plan 04 — IP2Proxy LITE Provider

**Status:** Complete  
**Depends on:** Plans 01–02

## Objective

Evaluate and implement the useful factual portion of IP2Proxy LITE without confusing a rich file schema with commercial-edition coverage.

## Critical semantic constraint

Current IP2Proxy LITE documentation describes LITE proxy coverage as open proxies (`PUB`). Broader categories such as VPN, Tor, data-center/hosting, residential proxy, consumer privacy network, and enterprise private network are described as commercial-edition coverage.

Therefore:

- validate actual LITE records/coverage before defining canonical traits,
- do not claim LITE provides comprehensive VPN/Tor/hosting detection merely because columns or commercial taxonomies exist,
- do not promote vendor `threat` or fraud-score fields into canonical IPFacet facts.

## Scope

- document exact free downloadable LITE variants,
- licensing/attribution and automated-download requirements,
- IPv4/IPv6,
- proxy type where genuinely represented by LITE data,
- country and other factual columns only when semantics/coverage are documented,
- ASN/AS observations only after comparing semantics with Plan 03/05 sources,
- original provider classification retained in provider metadata,
- canonical trait mapping only for validated semantics.

## Exit criteria

- free-tier capabilities are documented from current provider terms/docs,
- adapter does not overstate LITE coverage,
- representative sample records are tested,
- attribution requirements are surfaced by dataset manager,
- no threat/fraud score becomes canonical,
- CI passes.


## Completion record

Completed after the provider research gate, implementation, semantic audit, and final CI gate passed.

Implemented and validated:

- selected PX8 LITE to obtain factual proxy/geographic/network context without importing PX9-PX12 threat/fraud-oriented fields,
- documented current free-tier licensing, attribution, no-redistribution requirement, download authentication, update-cadence ambiguity, and coverage boundaries,
- external `IP2LOCATION_DOWNLOAD_TOKEN` plus account-provided `IP2PROXY_LITE_FILE_CODE`; no guessed provider file code,
- credential-free manifest provenance and sanitized download failures,
- ZIP acquisition that extracts only the expected PX8 LITE IPv6 CSV,
- manual/air-gapped import,
- IPv4 lookup through documented IPv4-mapped IPv6 numeric ranges plus native IPv6,
- compact 128-bit end-range/file-offset index,
- full pre-activation 13-column row/range validation,
- strict `PUB`-only LITE proxy validation,
- `PUB -> PROXY` with no LITE VPN/Tor inference,
- independent factual usage mappings: DCH→HOSTING, CDN→CDN, MOB→MOBILE, EDU→EDUCATION, GOV→GOVERNMENT,
- country, region, city, ISP, ASN, and AS-name canonical observations,
- provider `domain` deliberately retained as metadata rather than mislabeled as AS domain,
- proxy type, usage type, domain, and last-seen retained as provider metadata,
- no threat, residential-proxy, provider, or fraud-score fields in the selected adapter schema,
- representative provider-published sample semantics covered using synthetic fixture construction,
- required attribution recorded in manifests and project documentation,
- source provider databases excluded from repository/package fixtures.

Validation:

- `uv sync --frozen --dev` — pass
- `uv lock --check` — pass
- Ruff lint — pass
- Ruff format — pass
- strict Pyright — 0 errors, 0 warnings
- pytest — 93 passed
- `uv build` — pass
