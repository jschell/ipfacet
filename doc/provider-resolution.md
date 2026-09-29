# Provider and Resolution Semantics

Plan 01 defines the contract real dataset adapters must follow. Provider adapters normalize source data into these semantics before the resolver sees it; the resolver does not guess semantic equivalence.

## Canonical scalar fields

| Canonical field | Required semantic meaning |
| --- | --- |
| `asn` | Autonomous System Number associated with the provider's documented routing/origin concept. The adapter must document that concept in observation semantics. |
| `as_name` | Organization/name associated by the source with the AS itself. Do not map an allocation registrant or generic ISP here without documented equivalence. |
| `as_domain` | Domain associated by the source with the AS organization. |
| `network` | Provider-reported IP prefix/network containing the address. |
| `country_code` / `country_name` | Provider geolocation country, not RIR allocation country unless the source explicitly defines it as geolocation. |
| `continent_code` | Provider geolocation continent. |
| `region`, `city`, `timezone` | Optional provider geolocation properties. |
| `isp` | Provider's documented ISP/network-operator concept. This is distinct from AS organization and allocation owner. |

BGP origin, allocation/registration organization, AS organization, ISP, and network operator remain distinct unless a specific provider's documentation establishes semantic equivalence for the mapped field.

## Capabilities

A provider declares semantic capabilities before lookup. Returning a canonical field without declaring its required capability is an error. A declared capability with no observation for an address is `NOT_FOUND`; absence of the capability is `UNSUPPORTED`.

Network classifications use independent `NetworkTrait` values such as `HOSTING`, `CLOUD`, `CDN`, `VPN`, `PROXY`, and `TOR`. Multiple traits may coexist. They are factual context, not maliciousness or reputation scores.

## Resolution

Scalar resolution is explicit and field-specific:

```python
from ipfacet import CanonicalField, FieldPrecedence, ResolutionPolicy

policy = ResolutionPolicy(
    (
        FieldPrecedence(CanonicalField.ASN, ("ipinfo", "maxmind")),
        FieldPrecedence(CanonicalField.COUNTRY_CODE, ("maxmind", "ipinfo")),
        FieldPrecedence(CanonicalField.COUNTRY_NAME, ("maxmind", "ipinfo")),
    )
)
```

Rules:

1. Exactly one selected version of each provider may participate.
2. Every provider capable of a scalar field must appear in that field's precedence rule.
3. Provider registration order never changes the result; policy order does.
4. A missing, unsupported, or failed primary may fall through to a later present value.
5. Different present values produce `CONFLICT`; the first present value by policy is selected and every present observation is retained.
6. Equal present values produce `PRESENT` with an `AGREEMENT` explanation. Agreement does not create a confidence score.
7. With no present value, `LOOKUP_ERROR` takes precedence over terminal `NOT_FOUND`; otherwise the field is `UNSUPPORTED`.
8. Network traits are unioned because they are independent normalized facts rather than mutually exclusive scalar values. Each trait observation retains provenance.

Use `result.explain("asn")` to inspect the deterministic provider-state trace used for a scalar field.

## Version isolation

`ProviderIdentity` identifies the exact provider, dataset, version, and format selected for lookup. IPFacet rejects two snapshots with the same provider name in one resolver. An older version is never consulted to fill a value missing from the selected version.

Dataset acquisition and active-version selection are implemented in Plan 02; Plan 01 only enforces the lookup-side invariant.

## Provider metadata

Adapters may retain unknown or vendor-specific source fields as typed `ProviderMetadata` on `ProviderResult`. The resolver never promotes those keys into canonical fields. In particular, vendor risk, reputation, or threat scores are not canonical IPFacet facts.
