# Plan 04 — IP2Proxy LITE Provider

**Status:** Active  
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
