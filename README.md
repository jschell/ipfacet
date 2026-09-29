# IPFacet

IPFacet is a provider-neutral Python library for **local, offline IP address enrichment** from downloaded reference datasets.

Its purpose is deliberately narrow: given an IPv4 or IPv6 address, return normalized factual network and geographic context with field-level provenance. IPFacet does **not** assign maliciousness, reputation, or threat scores.

## Goals

- Offline lookup after datasets are installed.
- Normalize multiple providers behind one stable typed API.
- Preserve field-level provenance and source disagreements.
- Treat dataset versions as immutable snapshots.
- Support deterministic field-specific source precedence.
- Keep acquisition/update logic separate from lookup logic.
- Support IPv4 and IPv6.
- Make batch enrichment efficient for SIEM-scale workflows.
- Support Polars first, with Pandas and PyArrow at the public boundary.
- Keep provider datasets and credentials out of the repository.

## Intended data

Initial provider targets are:

- IPinfo Lite for ASN, AS organization/domain, country, and continent context.
- IP2Proxy LITE for network/proxy/usage classifications where licensing and free-tier capabilities permit.
- MaxMind GeoLite2 as an independent ASN/geography provider and fallback/reference implementation.

Future providers may include routing/RIR-derived sources where they add semantics not represented by the initial providers.

## Canonical model

IPFacet will normalize factual observations such as:

- IP scope and special-purpose classification
- origin/network ASN where supported by provider semantics
- AS organization and domain
- network/prefix
- country/continent and optional region/city
- ISP
- network traits such as hosting, CDN, residential, mobile, business, education, government, VPN, proxy, and Tor
- field-level provider, dataset, and dataset-version provenance

Provider disagreement is preserved. A configured field-specific precedence policy selects a convenient resolved value without discarding alternative observations.

## Explicit non-goals

IPFacet is not a threat-intelligence or reputation platform. V1 does not include:

- malicious-IP scoring
- vendor risk scores as canonical facts
- IOC feeds
- VirusTotal, AbuseIPDB, GreyNoise, or similar online reputation APIs
- DNS/rDNS enrichment
- persistent histories of queried IP addresses
- background daemons or schedulers

## Dataset lifecycle

Reference datasets are not bundled in the Python package. Dataset helpers may download or import provider data, validate it, record provenance and licensing metadata, and atomically activate a validated version.

Credentials remain external to IPFacet configuration. Air-gapped/manual imports are first-class.

Provider-specific retention requirements must be enforced; historical snapshots are never assumed to be legally retainable indefinitely.

## Planned API

```python
import ipfacet

db = ipfacet.open_database()

result = db.lookup("1.1.1.1")
results = db.lookup_many(["1.1.1.1", "8.8.8.8"])
```

Batch enrichment will deduplicate source IPs before lookup and join normalized results back to caller data.

## Development

The project targets Python 3.12+ and uses `uv` as the dependency and environment manager.

Plans are tracked under:

```text
doc/plan/
├── active/
├── complete/
└── queue/
```

Read [AGENTS.md](AGENTS.md) before making changes. Architecture and roadmap context are in [doc/overview.md](doc/overview.md).
