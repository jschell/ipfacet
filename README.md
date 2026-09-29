# IPFacet

IPFacet is a provider-neutral Python library for **local, offline IP address enrichment** from downloaded reference datasets.

Its purpose is deliberately narrow: given an IPv4 or IPv6 address, return normalized factual network and geographic context with field-level provenance. IPFacet does **not** assign maliciousness, reputation, or threat scores.

## Status

IPFacet is pre-alpha. Plans 00–02 establish the canonical API, provider resolution, and safe local dataset lifecycle. Plan 03 adds IPinfo Lite as the first real offline reference-data provider. Plan 04 adds IP2Proxy LITE PX8 with deliberately constrained open-proxy and network-usage semantics.

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

IPFacet works without an external dataset for local IP scope classification. Plan 01 adds typed provider capabilities and deterministic cross-provider resolution while keeping real vendor adapters out of the core.

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

Planned provider-backed use remains:

```python
db = ipfacet.open_database()
result = db.lookup("1.1.1.1")
results = db.lookup_many(["1.1.1.1", "8.8.8.8"])
```

## Canonical semantics

Fields distinguish `PRESENT`, `NOT_FOUND`, `UNSUPPORTED`, `CONFLICT`, and `LOOKUP_ERROR`. Agreement among providers is not converted into invented statistical confidence.

Network characteristics are modeled as independent traits such as hosting, CDN, VPN, proxy, and Tor rather than a single mutually exclusive vendor category. These are contextual facts, not maliciousness findings.

## Explicit non-goals

IPFacet is not a threat-intelligence or reputation platform. V1 does not include malicious-IP scoring, vendor risk scores as canonical facts, IOC feeds, online reputation APIs, DNS/rDNS enrichment, persistent histories of queried IP addresses, or background schedulers.

## Dataset lifecycle

Reference datasets are not bundled in the Python package. `DatasetManager` stages and validates snapshots before activation, records credential-free provenance/licensing manifests, verifies local SHA-256 integrity, enforces provider retention constraints, supports verified rollback, and treats manual/air-gapped imports as first-class.

The CLI exposes `ipfacet datasets available/list/status/install/import/update/verify/rollback`. Real-provider automated downloads remain disabled until each provider plan documents authentication, automation permission, download limits, attribution, redistribution, retention/destruction, and old-snapshot rules. See [doc/dataset-lifecycle.md](doc/dataset-lifecycle.md).

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

Third-party reference databases are never bundled in the IPFacet Python distribution.
