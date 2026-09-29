# Anomaly-Detections pilot boundary

Anomaly-Detections is a separate package. Its `EngagementContext.normalize(data, source=...)` produces an in-memory Polars frame with canonical `actor`, `timestamp`, and `source_ip` columns. Its existing `actor_ip` relationship state is derived and written through `ctx.stores.state`. IPFacet can enrich that normalized frame with factual ASN/network context before a consumer-owned aggregate. This is a pilot recipe, not a dependency or API change in either package.

## Candidate notebook flow

Use the [IPFacet notebook setup](consumer-notebook.md) to open installed provider snapshots and build an explicit `db` policy. Obtain `events` from the SIEM query in the notebook. Then:

```python
import hashlib
from pathlib import Path
import polars as pl
import siem_anomaly as sa
from ipfacet import CanonicalField, enrich_frame

ctx = sa.open_engagement(engagement_path)
normalized = ctx.normalize(events, source="microsoft.entra_signin")
enriched = enrich_frame(
    db, normalized, ip_column="source_ip",
    fields=(CanonicalField.ASN,), include_provenance=True,
)

# Persist only relationship state. Never write normalized/enriched event rows.
actor_asn = (
    enriched
    .with_columns(
        pl.col("timestamp").cast(pl.Utf8)
        .str.to_datetime(strict=False, time_zone="UTC")
        .dt.date().alias("_date")
    )
    .drop_nulls(["actor", "ipfacet_asn", "_date"])
    .group_by(["actor", "ipfacet_asn"])
    .agg(
        pl.len().alias("event_count"),
        pl.col("_date").min().alias("first_seen_date"),
        pl.col("_date").max().alias("last_seen_date"),
        pl.col("_date").n_unique().alias("days_seen"),
        pl.col("ipfacet_provenance").unique().alias("source_provenance"),
    )
)
token = hashlib.sha256(query_id.encode("utf-8")).hexdigest()[:16]
ctx.stores.state.write(Path("actor_asn") / "ipfacet-v1" / f"{token}.parquet", actor_asn)
```

This path stores aggregate relationship state, not a one-row-per-event copy. The provider/version provenance accompanies derived relationships. The notebook should record its SIEM query coverage and package/adapter versions in its engagement manifest. Anomaly-Detections can use the relationship state to determine novelty or rarity, but those judgments belong to the consumer. IPFacet does not label an address malicious.

## Packaging and validation gate

Anomaly-Detections currently has no IPFacet dependency. Its Python package is still `0.0.0`; IPFacet is `1.0.0rc1` and has not been published or tagged. A subsequent consumer PR can add an optional pinned dependency after the release artifact location is chosen, register `actor_asn` with a versioned feature schema, integrate coverage/backfill semantics, and test that event-level rows never enter engagement storage. Avoid a floating Git branch dependency or an implicit provider lookup inside generic detectors.

Before a final IPFacet V1 release, run operator-authorized opt-in smoke tests using actual current provider datasets under their terms. Compare same-release MaxMind CSV/MMDB if pursuing a different default reader; synthetic performance numbers do not establish real database throughput. Publication, tagging, and consumer dependency changes remain separate reviewable actions.
