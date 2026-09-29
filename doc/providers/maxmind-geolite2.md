# MaxMind GeoLite2 ASN provider

IPFacet uses the free GeoLite2 ASN **CSV** release for factual ASN, AS organization, and CIDR context. It does not map ASN organization to ISP, ownership, threat, or risk. Country and City datasets are outside this adapter's scope. CSV avoids a new binary reader dependency; Plan 06 will evaluate lookup throughput and format choices. The adapter indexes the two CSV block files in memory at open time and reads matching records from disk. Normal lookups are offline.

## License and attribution

The [GeoLite End User License Agreement](https://www.maxmind.com/en/geolite/eula), updated February 12, 2026, applies separately from IPFacet's MIT license. Display attribution for use of the data:

> This product includes GeoLite Data created by MaxMind, available from https://www.maxmind.com.

This text and the license URL are stored in each installed snapshot's manifest. Check the EULA for your use case, including restrictions on redistribution and use. MaxMind may change its terms.

**Operator retention responsibility:** Under the current EULA, an old GeoLite database or data release must cease being used and be destroyed within 30 days after MaxMind releases an update. IPFacet keeps old installed snapshots after activation and performs no automatic destruction. The operator must check MaxMind release dates, stop using obsolete snapshots, and remove their directories and any other copies before the deadline. The deadline is measured from MaxMind's updated release date, not from when IPFacet installs it. A manually supplied release label may not encode that date. IPFacet's `datasets status` exposes active release and acquisition time; inspect `datasets/<provider>/<dataset>/versions/` for retained releases. An operator should also account for backups, exports, and independently copied datasets. The generic rollback operation can still select an old release; the operator is responsible for using only a release permitted by the EULA.

IPFacet retains version and hash in result provenance and manifests; the operator can separately preserve non-database provenance after deleting old data. No GeoLite database is bundled with the package or tests.

## Install and update

Create a free MaxMind account and license key. Set `MAXMIND_ACCOUNT_ID` and `MAXMIND_LICENSE_KEY` in the environment. Then run:

```sh
ipfacet datasets install maxmind geolite2-asn
ipfacet datasets update maxmind geolite2-asn
```

Acquisition uses MaxMind's [account download permalink](https://dev.maxmind.com/geoip/updating-databases/) for `GeoLite2-ASN-CSV` with HTTP Basic authentication and HTTPS redirects. Credentials and redirected URLs are not stored in manifests. The source archive SHA-256 and extracted snapshot SHA-256 are recorded, but the archive hash is a local integrity identity rather than a vendor-published checksum. Downloads are explicit, never initiated by lookup. MaxMind documents download limits and 429 responses. No background update scheduler is installed.

For a manual or air-gapped install, extract the MaxMind ASN CSV archive to a directory containing both `GeoLite2-ASN-Blocks-IPv4.csv` and `GeoLite2-ASN-Blocks-IPv6.csv`, then import that directory with its actual release date as the release label:

```sh
ipfacet datasets import maxmind geolite2-asn /path/to/extracted --release 20260929
```

The complete CSV files are checked before activation for the expected columns, valid CIDRs/ASNs, family placement, and nonoverlapping sorted networks. A failed import leaves the previous active dataset usable. MaxMind's documented CSV fields are network, autonomous_system_number, and autonomous_system_organization; blank values remain `NOT_FOUND`. See the [ASN database reference](https://dev.maxmind.com/geoip/docs/databases/asn/).
