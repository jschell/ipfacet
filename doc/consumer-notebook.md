# Offline notebook integration

The notebook retrieves raw events from the SIEM into memory. IPFacet reads installed local reference datasets and returns factual context. The consumer derives behavioral relationships and can store **derived** engagement-local features; ordinary raw telemetry stays in the SIEM. Full raw events may be retained only when directly tied to an investigated or confirmed incident under the engagement's policy.

## Prepare datasets outside the notebook

Install IPinfo Lite and MaxMind GeoLite2 ASN with their documented credentials or import manually downloaded files. Neither provider dataset is bundled with IPFacet. Read the [IPinfo](providers/ipinfo-lite.md) and [MaxMind](providers/maxmind-geolite2.md) terms and attribution guidance. GeoLite superseded releases are deleted by the operator, not by IPFacet.

```sh
ipfacet datasets available
ipfacet datasets install ipinfo ipinfo-lite
ipfacet datasets install maxmind geolite2-asn
ipfacet datasets status ipinfo ipinfo-lite --verify
ipfacet datasets status maxmind geolite2-asn --verify
```

`status --verify` checks the active snapshot's hash and provider schema. Status also reports license/attribution, freshness, retained releases, and the GeoLite operator warning. A failed verification exits with status 2. Manual/air-gapped import is documented in the provider guides.

## Notebook cell

Install `ipfacet[polars]` in the notebook's Python environment. The code below expects installed provider snapshots. Build an explicit policy for every field each provider declares; registration order never decides a winner.

```python
import polars as pl
from pathlib import Path
from ipfacet import (
    CanonicalField, FieldPrecedence, ResolutionPolicy,
    enrich_frame, open_database,
)
from ipfacet.providers import open_ipinfo_lite, open_maxmind_geolite2

providers = (open_ipinfo_lite(), open_maxmind_geolite2())
policy = ResolutionPolicy(
    tuple(FieldPrecedence(field, ("ipinfo", "maxmind")) for field in (
        CanonicalField.ASN, CanonicalField.AS_NAME, CanonicalField.NETWORK,
    )) + tuple(FieldPrecedence(field, ("ipinfo",)) for field in (
        CanonicalField.AS_DOMAIN, CanonicalField.COUNTRY_CODE,
        CanonicalField.COUNTRY_NAME, CanonicalField.CONTINENT_CODE,
    ))
)
db = open_database(providers=providers, policy=policy)

# Runnable synthetic input; replace with the notebook's in-memory SIEM query result.
# Do not write the raw event frame to engagement storage.
events = pl.DataFrame({
    "actor": ["example-a", "example-a", "example-b"],
    "source_ip": ["1.1.1.1", "1.1.1.1", "8.8.8.8"],
})
enriched = enrich_frame(
    db, events, ip_column="source_ip",
    fields=(CanonicalField.ASN, CanonicalField.COUNTRY_CODE),
    include_provenance=True, include_conflicts=True,
)

# Consumer-owned derived relationship state. Review its fields under engagement policy.
actor_asn_counts = (
    enriched.drop_nulls("ipfacet_asn")
    .group_by("actor", "ipfacet_asn")
    .agg(pl.len().alias("event_count"))
)
derived_dir = Path("engagement/derived")
derived_dir.mkdir(parents=True, exist_ok=True)
actor_asn_counts.write_parquet(derived_dir / "actor_asn_counts.parquet")
```

Do not store the `enriched` event frame by default: it still contains raw event rows. The relationship aggregate can support actor-to-ASN novelty in a consumer baseline, but IPFacet does not calculate anomaly or maliciousness scores. To reproduce a result later, store only the relevant version/hash identifiers and derived feature provenance according to the engagement's retention rules; provider databases remain subject to their own terms.

The synthetic [consumer contract test](../tests/test_consumer_contract.py) installs two provider snapshots, disables lookup-time network access, runs the frame path, and verifies conflict/fallback and relationship aggregation. It needs no account or customer data.
