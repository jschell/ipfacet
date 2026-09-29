# IPFacet Architecture Overview

## Mission

IPFacet turns locally installed IP reference datasets into a stable, typed, provider-neutral enrichment interface.

It answers factual questions such as:

- What network/prefix contains this address?
- What ASN and organization does a source associate with it?
- What country/continent does a source associate with it?
- What network traits does a source report?
- Which provider/version supplied each observation?
- Do installed sources disagree?

It does not answer whether an IP is malicious.

## Core flow

```text
IPv4 / IPv6
    |
    +--> local special-range classification
    |
    +--> selected immutable provider snapshots
             |
             +--> provider observations
                       |
                       +--> semantic normalization
                                  |
                                  +--> field resolution
                                           |
                                           +--> canonical result
                                           +--> provenance
                                           +--> conflicts
```

## Resolution model

### Same provider, multiple versions

One selected snapshot participates in a lookup. Versions are never mixed. Normal lookup uses the active validated version; reproducible workflows may explicitly select an installed version when provider retention terms permit.

An older version is never used to fill a field missing from the selected version.

### Different providers

Resolution is field-specific. Example:

```text
ASN:        IPinfo -> MaxMind -> IP2Proxy
country:    MaxMind -> IPinfo -> IP2Proxy
proxy type: IP2Proxy
```

The first usable observation according to policy becomes the resolved value. Alternative observations remain available. Disagreement is a conflict, not an error and not a vote.

### Field states

Canonical field state must distinguish at least:

- PRESENT
- NOT_FOUND
- UNSUPPORTED
- CONFLICT
- LOOKUP_ERROR

## Provenance

Each resolved field and provider observation should be traceable to:

- provider
- dataset
- exact version/release
- dataset format
- acquisition/activation metadata
- applicable source semantics

Agreement among providers must not be converted into invented statistical confidence.

## Network traits

Vendor classifications should normalize into a multi-valued trait model rather than a single mutually exclusive network type. Candidate traits include:

- RESIDENTIAL
- MOBILE
- BUSINESS
- HOSTING
- CLOUD
- CDN
- EDUCATION
- GOVERNMENT
- VPN
- PROXY
- TOR

Original provider observations remain available for explanation/provenance.

## Dataset lifecycle

```text
discover/check release
       |
download OR manual import
       |
integrity verification
       |
schema validation
       |
smoke lookup
       |
manifest
       |
atomic activation
       |
provider-specific retention behavior; GeoLite cleanup is operator-managed
```

Lookup is independent of acquisition and must remain usable in offline/air-gapped environments.

## Integration boundary

A consumer such as Anomaly-Detections may use IPFacet to obtain factual context and then derive behavioral state such as actor-to-ASN novelty or rarity. IPFacet itself does not determine whether those facts are anomalous or malicious.

## Roadmap

- Plan 00: foundation and canonical API — complete
- Plan 01: provider/capability and resolution architecture — complete
- Plan 02: dataset lifecycle and acquisition — complete
- Plan 03: IPinfo Lite provider — complete
- Plan 04: IP2Proxy LITE provider — complete
- Plan 05: MaxMind GeoLite2 provider — complete
- Plan 06: batch/dataframe performance — complete
- Plan 07: consumer integration and V1 hardening — complete
