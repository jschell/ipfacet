# Changelog

## 1.0.0rc1 — 2026-09-29

First V1 release candidate; no package has been published.

- Typed provider-neutral IPv4/IPv6 enrichment, field states, provenance, deterministic resolution, and conflict traces.
- Offline IPinfo Lite, IP2Proxy LITE PX8, and MaxMind GeoLite2 ASN CSV adapters with explicit acquisition and manual import.
- Atomic snapshot activation, integrity verification, rollback where permitted, provider-specific manifest metadata, and dataset CLI.
- Polars, Pandas, and PyArrow batch boundaries with canonical IP deduplication and optional provenance/conflict columns.
- Synthetic benchmark harness and offline notebook consumer contract.
- GeoLite superseded release deletion remains an operator responsibility; see provider guidance.

Compatibility policy and release reproduction steps: [doc/compatibility.md](doc/compatibility.md).
