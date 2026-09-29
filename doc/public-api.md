# Public API reference for 1.0.0rc1

Import provider-neutral types and functions from `ipfacet`; built-in adapters and open helpers live in `ipfacet.providers`. Install optional `polars`, `pandas`, or `arrow` extras for the corresponding frame boundary. Type signatures and docstrings in `src/ipfacet/` are the detailed reference; this page identifies the supported composition points.

| API | Purpose |
|---|---|
| `open_database(providers=..., policy=...)` | Create a `Database` from already opened provider snapshots and an explicit `ResolutionPolicy`. Without providers it only classifies local IP scope. |
| `Database.lookup(ip)` | Return one `IPEnrichment` for a string or parsed IPv4/IPv6 address. |
| `Database.lookup_many(ips)` | Return insertion-ordered unique results keyed by parsed addresses; each canonical IP is looked up once per invocation. |
| `enrich_frame(db, frame, ip_column=..., fields=..., prefix=..., include_provenance=..., include_conflicts=...)` | Return the same Polars/Pandas/PyArrow type with factual columns joined in original row order. |
| `FieldPrecedence(field, providers)`, `ResolutionPolicy(rules)` | Choose source order separately for each capable canonical field. Every capable provider must be listed for that field. |
| `IPEnrichment` and `ResolvedField` | Access values, states, observations and field provenance; `result.explain(field)` returns the source trace, and `result.to_dict()` is JSON-compatible. |
| `DatasetStore`, `DatasetManager`, `default_dataset_manager()` | Manage local snapshots, explicit acquisition/import, active status, integrity verification, and rollback where permitted. |
| `open_ipinfo_lite()`, `open_ip2proxy_lite()`, `open_maxmind_geolite2()` | Open an active local snapshot for fully offline lookups; pass a `DatasetStore` to select a nondefault data root. |

## Field resolution

`CanonicalField` includes ASN, AS name/domain, network prefix, country code/name, continent code, region, city, timezone, and ISP. `FieldState` distinguishes `PRESENT`, `NOT_FOUND`, `UNSUPPORTED`, `CONFLICT`, and `LOOKUP_ERROR`. A conflict retains all observations and follows the explicit precedence policy; it is not a vote or confidence score. Network traits are a separate multi-valued set of contextual facts. Provider-specific metadata stays at the provider boundary.

The result's `to_dict()` includes field states, selected values, observation provenance, traits and explanations. The DataFrame boundary emits deterministic prefixed scalar and `_state` columns, with optional JSON provenance/conflicts. See [batch guidance](batch-dataframes.md) for null, invalid-IP and collision handling, and [provider resolution](provider-resolution.md) for semantic mappings.

## Provider and dataset lifecycle

A consumer constructs `Database` from provider instances; it does not call acquisition during lookup. `default_dataset_manager()` registers built-in policies and explicit download helpers. Credentials come from external environment variables and are not persisted. `datasets status --verify` diagnoses an installed snapshot; see [dataset lifecycle](dataset-lifecycle.md) and the individual provider guides. GeoLite obsolete data removal is the operator's responsibility.

## Stability

The [compatibility policy](compatibility.md) covers public imports, model serialization, frame column names, CLI JSON, and manifest semantics. Pin `1.0.0rc1` while validating a consumer and review the changelog before upgrading. No final V1 package is published by this plan.
