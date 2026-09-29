# IPinfo Lite Provider

Research validated 2026-09-29 against IPinfo's current first-party documentation.

## Scope and semantics

IPinfo Lite is the free country + ASN dataset. The current CIDR-based schema is:

```text
network
country
country_code
continent
continent_code
asn
as_name
as_domain
```

IPFacet maps those fields to:

```text
network         -> network
country         -> country_name
country_code    -> country_code
continent_code  -> continent_code
asn             -> asn (canonical integer; provider AS prefix removed)
as_name         -> as_name
as_domain       -> as_domain
```

`continent` (the full continent name) is retained by the source dataset but is not currently a canonical IPFacet scalar field.

IPinfo's current first-party descriptions are not fully identical: the Lite product page describes `asn` as the autonomous system number announcing the IP address, while the Lite database schema describes the ASN in terms of an organization that owns the IP range block. IPFacet does not choose between those two provider descriptions. Provenance therefore calls the value the **IPinfo Lite ASN for the IP range** and does not independently label it BGP origin ASN, allocation ownership, ISP, RIR registrant, or network owner. `as_name` remains the provider's AS organization name.

Lite does **not** provide canonical city, region, timezone, ISP, privacy/VPN/proxy, hosting, network-type, or threat/reputation data. The provider must not synthesize those fields.

Sources:

- https://ipinfo.io/developers/ipinfo-lite-database
- https://ipinfo.io/lite

## Acquisition research gate

### Authentication

Database downloads use an IPinfo access token in the download URL. IPFacet reads it from `IPINFO_TOKEN` at execution time and never writes the token to config, manifests, source provenance, or logs.

Documented endpoint used by Plan 03:

```text
https://ipinfo.io/data/ipinfo_lite.csv.gz?token=$TOKEN
```

Source:

- https://ipinfo.io/developers/database-filename-reference
- https://ipinfo.io/developers/database-download

### Automated download

IPinfo explicitly documents command-line/programmatic database download and follows an HTTP redirect to a short-lived CDN URL. Automated acquisition is therefore enabled.

IPFacet stores the credential-free canonical endpoint as source provenance, never the tokenized request URL or signed redirect target.

### Download limits and refresh cadence

IPinfo currently limits database downloads to 10 downloads per unique IP address per unique dataset per day. IPinfo states that the database refreshes daily and recommends downloading once per day and distributing that copy internally.

IPFacet does not contain a scheduler or background updater. One explicit `datasets install/update` invocation performs at most one IPinfo Lite database download.

Source:

- https://support.ipinfo.io/hc/en-us/articles/30792506260626-Why-are-We-Getting-429-Error-Code-When-Downloading-the-Database

### Formats

IPinfo documents CSV, JSON, MMDB, and Parquet. Its database guide describes MMDB as optimized for high-performance single-IP lookups, CSV for ingestion, and Parquet for analytical workloads.

Plan 03 supports CSV because it is dependency-free, directly validates the documented tabular schema, and supports both single and batch-facing provider abstractions. The provider builds a compact range-to-file-offset index and reads only the matched row after indexing.

Plan 06 must benchmark CSV against MMDB and/or Parquet before IPFacet declares a preferred production format. Plan 03 does not make CSV a permanent canonical storage choice.

Sources:

- https://ipinfo.io/developers/database-download
- https://ipinfo.io/developers/ipinfo-lite-database

### Licensing, attribution, redistribution, retention

IPinfo states that IPinfo Lite data downloads are released under the Creative Commons Attribution-ShareAlike 4.0 International license (CC BY-SA 4.0). IPinfo explicitly permits commercial/product use and redistribution subject to attribution/share-alike requirements.

Required project attribution:

> IP address data powered by IPinfo (https://ipinfo.io)

IPFacet records the license identifier and attribution in every installed Lite manifest and documents attribution here and in the project README.

The current Lite documentation does not impose a provider-specific destruction window for obsolete snapshots. Plan 03 therefore permits immutable historical snapshot retention for reproducibility. This differs intentionally from providers whose licenses require old database destruction.

Sources:

- https://ipinfo.io/developers/ipinfo-lite-database
- https://ipinfo.io/lite
- https://creativecommons.org/licenses/by-sa/4.0/

## Version identity

IPinfo publishes a daily-updated database but does not document a semantic release number in the downloaded filename. IPFacet identifies an acquired snapshot using:

```text
<HTTP Last-Modified date>-<first 16 hex chars of downloaded gzip SHA-256>
```

If `Last-Modified` is unavailable or invalid, the release identifier is:

```text
sha256-<first 16 hex chars>
```

The complete SHA-256 of the downloaded gzip is retained separately as verified source-integrity provenance. The installed snapshot receives the independent Plan-02 tree SHA-256.

This makes two different snapshots distinguishable even if served on the same date and avoids claiming that acquisition time is the provider's release version.

## Schema-change behavior

The Plan-03 adapter requires the documented eight-column CSV schema in its documented order. Missing, renamed, reordered, or added fields fail validation before activation rather than being silently reinterpreted.

Provider records that cannot be parsed into the documented network/ASN/geographic semantics fail validation or return a lookup error; IPFacet does not guess replacements.

## Privacy boundary

Only database acquisition contacts IPinfo. Once installed/imported, lookup is entirely local. Investigated IP addresses are never sent to IPinfo by this provider.
