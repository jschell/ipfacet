# IPFacet

IPFacet is a provider-neutral Python library for **local, offline IP address enrichment** from downloaded reference datasets.

Its purpose is deliberately narrow: given an IPv4 or IPv6 address, return normalized factual network and geographic context with field-level provenance. IPFacet does **not** assign maliciousness, reputation, or threat scores.

## Status

IPFacet is a V1 release candidate (`1.0.0rc1`). It provides offline adapters for IPinfo Lite, IP2Proxy LITE PX8, and MaxMind GeoLite2 ASN, plus batch DataFrame enrichment. See the [public API](doc/public-api.md), [changelog](CHANGELOG.md), and [compatibility policy](doc/compatibility.md).
The [operator release validation](doc/release-validation.md) records the remaining opt-in licensed-dataset gate before a final release decision.

## Goals

- Offline lookup after datasets are installed.
- Normalize multiple providers behind one stable typed API.
- Preserve field-level provenance and source disagreements.
- Treat dataset versions as immutable snapshots.
- Support deterministic field-specific source precedence.
- Keep acquisition/update logic separate from lookup logic.
- Support IPv4 and IPv6.
- Make batch enrichment efficient for SIEM-scale workflows.
- Support Polars first, with Pandas and PyArrow at the public boundary in the batch plan.
- Keep provider datasets and credentials out of the repository.

## Install for development

Python 3.12+ and [uv](https://docs.astral.sh/uv/) are required.

```bash
uv sync --frozen
uv run --frozen pytest
```

The committed `uv.lock` is the dependency source of truth for reproducible development and CI.

## Current API

```python
import ipfacet

db = ipfacet.open_database()
result = db.lookup("192.0.2.10")

assert result.scope is ipfacet.IPScope.DOCUMENTATION
```

IPFacet works without an external dataset for local IP scope classification. Provider-backed lookups require installed datasets, opened provider snapshots, and an explicit resolution policy.

A provider-backed database uses explicit field precedence:

```python
from ipfacet import CanonicalField, FieldPrecedence, ResolutionPolicy, open_database

policy = ResolutionPolicy(
    (
        FieldPrecedence(CanonicalField.ASN, ("primary", "fallback")),
    )
)

db = open_database(providers=[primary, fallback], policy=policy)
result = db.lookup("1.1.1.1")
explanation = result.explain("asn")
```

Provider registration order does not select winners; the field policy does. Conflicting present values preserve all observations and select according to policy. Missing, unsupported, and lookup-error states remain distinguishable in the explanation trace.

See the [offline notebook integration](doc/consumer-notebook.md) for a complete provider-backed example with installation, policy, batch enrichment, and derived relationship state.
The [Anomaly-Detections pilot](doc/consumer-pilot.md) maps IPFacet facts into that package's engagement-scoped derived state without adding a dependency to either package yet.

For telemetry tables, `enrich_frame(db, frame, ip_column="source_ip")` supports Polars,
Pandas, and PyArrow through optional extras, deduplicates IPs before provider lookup,
and joins results back in input row order. See [batch and DataFrame guidance](doc/batch-dataframes.md)
for columns, provenance options, benchmarks, and limits.

## Canonical semantics

Fields distinguish `PRESENT`, `NOT_FOUND`, `UNSUPPORTED`, `CONFLICT`, and `LOOKUP_ERROR`. Agreement among providers is not converted into invented statistical confidence.

Network characteristics are modeled as independent traits such as hosting, CDN, VPN, proxy, and Tor rather than a single mutually exclusive vendor category. These are contextual facts, not maliciousness findings.

## Explicit non-goals

IPFacet is not a threat-intelligence or reputation platform. V1 does not include malicious-IP scoring, vendor risk scores as canonical facts, IOC feeds, online reputation APIs, DNS/rDNS enrichment, persistent histories of queried IP addresses, or background schedulers.

## Dataset lifecycle

Reference datasets are not bundled in the Python package. `DatasetManager` stages and validates snapshots before activation, records credential-free provenance/licensing manifests, verifies local SHA-256 integrity, supports verified rollback, and treats manual/air-gapped imports as first-class. GeoLite superseded-release destruction is managed by the operator.

The CLI exposes `ipfacet datasets available/list/status/install/import/update/verify/rollback`. Provider downloads are explicit and separately documented; ordinary lookup is offline. `datasets status --verify` checks the active snapshot and shows licensing, freshness, retained releases, and operator warnings. See [doc/dataset-lifecycle.md](doc/dataset-lifecycle.md).

## Development workflow

The project targets Python 3.12+ and uses `uv`, Ruff, strict Pyright, and pytest. Read [AGENTS.md](AGENTS.md) before making changes.

Plans are tracked under:

```text
doc/plan/
├── active/
├── complete/
└── queue/
```

Architecture and roadmap context are in [doc/overview.md](doc/overview.md). Provider capability, semantic-mapping, precedence, fallback, conflict, and version-isolation rules are documented in [doc/provider-resolution.md](doc/provider-resolution.md).


## Data attribution

IPinfo Lite data is licensed separately from IPFacet under CC BY-SA 4.0.

IP address data powered by IPinfo: https://ipinfo.io

Provider terms, schema semantics, acquisition limits, version identity, and attribution details are documented in [doc/providers/ipinfo-lite.md](doc/providers/ipinfo-lite.md).

IPFacet uses the IP2Proxy LITE database for IP geolocation (https://www.ip2location.com). IP2Proxy LITE terms, free-tier coverage limits, acquisition behavior, and canonical trait mappings are documented in [doc/providers/ip2proxy-lite.md](doc/providers/ip2proxy-lite.md).

This product includes GeoLite Data created by MaxMind, available from https://www.maxmind.com. See [GeoLite2 ASN provider guidance](doc/providers/maxmind-geolite2.md) for acquisition, attribution, and the operator-managed 30-day destruction obligation for superseded data.

Third-party reference databases are never bundled in the IPFacet Python distribution.
