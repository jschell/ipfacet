# IP2Proxy LITE PX8 Provider

Research validated 2026-09-29 against current IP2Location/IP2Proxy first-party documentation.

## Selected free dataset

IPFacet uses **IP2Proxy LITE PX8** rather than PX9-PX12.

PX8 is the smallest current LITE variant that contains all of the factual fields needed for this provider:

```text
ip_from
ip_to
proxy_type
country_code
country_name
region_name
city_name
isp
domain
usage_type
asn
as
last_seen
```

PX9 and later add threat/residential/provider/fraud-oriented columns that are outside IPFacet V1's factual network-context boundary. Avoiding those editions makes it impossible for this adapter to accidentally promote a vendor threat or fraud score.

Sources:

- https://lite.ip2location.com/database/px8-ip-proxytype-country-region-city-isp-domain-usagetype-asn-lastseen
- https://lite.ip2location.com/ip2proxy-lite

## Critical LITE proxy-coverage boundary

Current first-party documentation states that IP2Proxy LITE detects **open proxies (`PUB`)**. It separately describes VPN, Tor, data-center/hosting proxy classification, residential proxy, consumer privacy network, enterprise private network, and other proxy categories as commercial-edition coverage.

Therefore Plan 04 intentionally applies these rules:

- `proxy_type=PUB` -> canonical `PROXY` trait,
- `proxy_type=-` -> no proxy/privacy trait,
- any other non-empty LITE proxy type fails snapshot validation,
- LITE never creates canonical `VPN` or `TOR` traits,
- a LITE `usage_type=DCH` is **not** treated as `proxy_type=DCH`.

This strict validation forces a code/research review if IP2Location later expands or changes LITE coverage rather than silently changing IPFacet semantics.

Sources:

- https://lite.ip2location.com/ip2proxy-lite
- https://lite.ip2location.com/database/px8-ip-proxytype-country-region-city-isp-domain-usagetype-asn-lastseen

## Usage-type traits

IP2Location documents `usage_type` as a classification of the ISP or company. This is semantically distinct from proxy type.

IPFacet maps only direct, useful classifications:

```text
DCH -> HOSTING     (Data Center/Web Hosting/Transit)
CDN -> CDN         (Content Delivery Network)
MOB -> MOBILE      (Mobile ISP)
EDU -> EDUCATION   (University/College/School)
GOV -> GOVERNMENT  (Government)
```

Combined values such as the provider-published `ISP/MOB` sample are split into independent codes, so that example receives `MOBILE` while fixed-line `ISP` itself is not assumed to mean residential.

Other current codes such as COM, ORG, MIL, LIB, ISP, SES/AIC, and RSV remain available in provider metadata but are not forced into a canonical trait where the mapping would be lossy or misleading.

Source:

- https://blog.ip2location.com/knowledge-base/what-is-usage-type/

## Canonical scalar mapping

```text
country_code -> country_code
country_name -> country_name
region_name  -> region
city_name    -> city
isp          -> isp
asn          -> asn
as           -> as_name
```

The provider's `domain` means a domain associated with the IP address range. It is **not** promoted to canonical `as_domain`, because those semantics differ from IPinfo Lite's autonomous-system official domain.

PX8 numeric `ip_from`/`ip_to` ranges are lookup mechanics and are not promoted to canonical `network`/prefix.

Provider-only metadata retained on a matched record:

```text
proxy_type
usage_type
domain
last_seen_days
```

ASN/AS are preserved as IP2Proxy's own observations. IPFacet does not reinterpret them as allocation ownership, RIR registrant, or independently verified BGP-origin data. Cross-provider agreement/disagreement is handled by the Plan-01 resolver.

## IPv4 and IPv6

IP2Location documents separate IPv4 and IPv6 CSV representations. Its current IPv6 CSV guidance states that IPv6 CSV data also contains IPv4 ranges represented as IPv4-mapped IPv6 numeric ranges.

IPFacet therefore installs the PX8 LITE IPv6 CSV and converts an IPv4 query to its `::ffff:0:0/96` mapped numeric representation before lookup. Native IPv6 addresses use their ordinary 128-bit integer representation.

This gives one immutable local file and one lookup index for both address families.

Source:

- https://blog.ip2location.com/knowledge-base/ipv4-ip-queries-using-ipv6-csv-data-db11-lite/

## Acquisition

IP2Location documents automated downloads using a download token and a database file code. Current first-party guidance says the token and the applicable database `CODE` are available in the account area.

IPFacet deliberately does not guess or hard-code an undocumented PX8 LITE file code. Automated acquisition requires:

```text
IP2LOCATION_DOWNLOAD_TOKEN
IP2PROXY_LITE_FILE_CODE
```

The second value must be the account-provided **PX8 LITE IPv6 CSV** download code.

The request follows the provider-documented form:

```text
https://www.ip2location.com/download?token=<token>&file=<code>
```

Neither value is written to manifests or source provenance. The manifest records only the credential-free download endpoint.

Manual/air-gapped import remains first-class and requires a directory containing:

```text
IP2PROXY-LITE-PX8.IPV6.CSV
```

Sources:

- https://blog.ip2location.com/knowledge-base/how-to-connect-ip2proxy-mongodb-docker-in-debian-container/
- https://blog.ip2location.com/knowledge-base/how-to-automate-ip2location-bin-database-download/

## Update cadence

The provider's current pages are not perfectly consistent about LITE publication cadence: the IP2Proxy LITE overview describes bi-weekly updates, while individual PX pages describe continuously generated proxy information and advertise automated daily download.

IPFacet contains no scheduler and performs no lookup-time network calls. The dataset manifest uses a 16-day staleness threshold as a conservative signal aligned to the overview's bi-weekly LITE statement. Users may explicitly update more often if their provider account permits it.

Sources:

- https://lite.ip2location.com/ip2proxy-lite
- https://lite.ip2location.com/database/px8-ip-proxytype-country-region-city-isp-domain-usagetype-asn-lastseen

## License, attribution, and redistribution

The current LITE Terms of Use state that the download is free under its conditions, explicitly prohibit redistribution or resale of the product, and require IP2Location credit. The PX8 page separately states that LITE is free for personal or commercial use with attribution.

Required project acknowledgment:

> IPFacet uses the IP2Proxy LITE database for IP geolocation (https://www.ip2location.com).

Consequences for IPFacet:

- no IP2Proxy database is bundled in the Python package,
- no provider database rows are committed as test fixtures,
- CI uses synthetic rows plus values derived from the provider-published documentation samples,
- installed snapshots remain local to the user,
- manifests retain the provider license URL and attribution,
- source database redistribution is not a feature of IPFacet.

The current LITE terms reviewed for Plan 04 do not specify a MaxMind-style destruction deadline for obsolete local snapshots, so immutable local versions remain permitted by IPFacet's lifecycle policy. This is not permission to redistribute those snapshots.

Sources:

- https://lite.ip2location.com/data-license
- https://lite.ip2location.com/database/px8-ip-proxytype-country-region-city-isp-domain-usagetype-asn-lastseen

## Schema and safety behavior

PX8 LITE CSV is headerless and position-defined by the provider documentation. IPFacet requires exactly 13 fields per row, validates every numeric range before activation, rejects overlapping/unsorted ranges, validates ASN/last-seen integer syntax, and rejects proxy classifications outside the documented LITE `PUB` boundary.

The adapter never reads or exposes threat/fraud-score fields because PX8 does not contain them.

## Privacy boundary

Only explicit dataset acquisition contacts IP2Location. Once installed/imported, all enrichment lookups are local. Investigated IP addresses are never sent to IP2Location by this provider.
