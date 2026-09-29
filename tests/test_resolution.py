from __future__ import annotations

from dataclasses import dataclass, field
from ipaddress import ip_address

import pytest

from ipfacet import (
    CanonicalField,
    Capability,
    FieldPrecedence,
    FieldState,
    IPAddress,
    NetworkTrait,
    ProviderIdentity,
    ProviderMetadata,
    ProviderObservation,
    ProviderResult,
    ResolutionPolicy,
    ResolutionReason,
    open_database,
)


@dataclass
class SyntheticProvider:
    identity: ProviderIdentity
    capabilities: frozenset[Capability]
    fields: tuple[ProviderObservation, ...] = ()
    traits: frozenset[NetworkTrait] = frozenset()
    metadata: tuple[ProviderMetadata, ...] = ()
    calls: list[IPAddress] = field(default_factory=list)

    def lookup(self, ip: IPAddress) -> ProviderResult:
        self.calls.append(ip)
        return ProviderResult(
            ip=ip,
            identity=self.identity,
            fields=self.fields,
            traits=self.traits,
            metadata=self.metadata,
        )


def provider(
    name: str,
    capabilities: set[Capability],
    *observations: ProviderObservation,
    version: str = "v1",
    traits: frozenset[NetworkTrait] = frozenset(),
    metadata: tuple[ProviderMetadata, ...] = (),
) -> SyntheticProvider:
    return SyntheticProvider(
        ProviderIdentity(name, f"{name}-fixture", version, "memory"),
        frozenset(capabilities),
        tuple(observations),
        traits,
        metadata,
    )


def rule(field: CanonicalField, *providers: str) -> FieldPrecedence:
    return FieldPrecedence(field, tuple(providers))


def test_two_providers_contribute_different_canonical_fields() -> None:
    asn = provider(
        "asn_source",
        {Capability.ASN},
        ProviderObservation(CanonicalField.ASN, FieldState.PRESENT, 13335, semantics="BGP origin ASN"),
    )
    geo = provider(
        "geo_source",
        {Capability.COUNTRY},
        ProviderObservation(CanonicalField.COUNTRY_CODE, FieldState.PRESENT, "US"),
        ProviderObservation(CanonicalField.COUNTRY_NAME, FieldState.PRESENT, "United States"),
    )
    policy = ResolutionPolicy(
        (
            rule(CanonicalField.ASN, "asn_source"),
            rule(CanonicalField.COUNTRY_CODE, "geo_source"),
            rule(CanonicalField.COUNTRY_NAME, "geo_source"),
        )
    )

    result = open_database(providers=[geo, asn], policy=policy).lookup("1.1.1.1")

    assert result.asn.value == 13335
    assert result.asn.provenance is not None
    assert result.asn.provenance.provider == "asn_source"
    assert result.asn.provenance.semantics == "BGP origin ASN"
    assert result.country_code.value == "US"
    assert result.country_code.provenance is not None
    assert result.country_code.provenance.provider == "geo_source"


def test_precedence_selects_primary_and_preserves_conflict() -> None:
    primary = provider(
        "primary",
        {Capability.ASN},
        ProviderObservation(CanonicalField.ASN, FieldState.PRESENT, 13335),
    )
    secondary = provider(
        "secondary",
        {Capability.ASN},
        ProviderObservation(CanonicalField.ASN, FieldState.PRESENT, 64500),
    )
    policy = ResolutionPolicy((rule(CanonicalField.ASN, "primary", "secondary"),))

    result = open_database(providers=[secondary, primary], policy=policy).lookup("1.1.1.1")

    assert result.asn.state is FieldState.CONFLICT
    assert result.asn.value == 13335
    assert [item.value for item in result.asn.observations] == [13335, 64500]
    explanation = result.explain("asn")
    assert explanation.reason is ResolutionReason.CONFLICT
    assert explanation.selected_provider == "primary"


def test_missing_primary_falls_back_without_becoming_conflict() -> None:
    primary = provider("primary", {Capability.ASN})
    secondary = provider(
        "secondary",
        {Capability.ASN},
        ProviderObservation(CanonicalField.ASN, FieldState.PRESENT, 13335),
    )
    policy = ResolutionPolicy((rule(CanonicalField.ASN, "primary", "secondary"),))

    result = open_database(providers=[primary, secondary], policy=policy).lookup("1.1.1.1")

    assert result.asn.state is FieldState.PRESENT
    assert result.asn.value == 13335
    explanation = result.explain(CanonicalField.ASN)
    assert explanation.reason is ResolutionReason.FALLBACK
    assert [item.state for item in explanation.providers] == [
        FieldState.NOT_FOUND,
        FieldState.PRESENT,
    ]


def test_agreement_records_both_observations_without_confidence() -> None:
    one = provider(
        "one",
        {Capability.ASN},
        ProviderObservation(CanonicalField.ASN, FieldState.PRESENT, 13335),
    )
    two = provider(
        "two",
        {Capability.ASN},
        ProviderObservation(CanonicalField.ASN, FieldState.PRESENT, 13335),
    )
    policy = ResolutionPolicy((rule(CanonicalField.ASN, "one", "two"),))

    result = open_database(providers=[one, two], policy=policy).lookup("1.1.1.1")

    assert result.asn.state is FieldState.PRESENT
    assert len(result.asn.observations) == 2
    assert result.explain("asn").reason is ResolutionReason.AGREEMENT


def test_error_is_preserved_when_later_provider_supplies_fallback() -> None:
    broken = provider(
        "broken",
        {Capability.ASN},
        ProviderObservation(
            CanonicalField.ASN,
            FieldState.LOOKUP_ERROR,
            error="fixture unavailable",
        ),
    )
    fallback = provider(
        "fallback",
        {Capability.ASN},
        ProviderObservation(CanonicalField.ASN, FieldState.PRESENT, 13335),
    )
    policy = ResolutionPolicy((rule(CanonicalField.ASN, "broken", "fallback"),))

    result = open_database(providers=[broken, fallback], policy=policy).lookup("1.1.1.1")

    assert result.asn.value == 13335
    explanation = result.explain("asn")
    assert explanation.reason is ResolutionReason.FALLBACK
    assert explanation.providers[0].state is FieldState.LOOKUP_ERROR
    assert explanation.providers[0].error == "fixture unavailable"


def test_error_wins_when_no_provider_has_a_value() -> None:
    broken = provider(
        "broken",
        {Capability.ASN},
        ProviderObservation(CanonicalField.ASN, FieldState.LOOKUP_ERROR, error="bad index"),
    )
    missing = provider("missing", {Capability.ASN})
    policy = ResolutionPolicy((rule(CanonicalField.ASN, "broken", "missing"),))

    result = open_database(providers=[broken, missing], policy=policy).lookup("1.1.1.1")

    assert result.asn.state is FieldState.LOOKUP_ERROR
    assert result.asn.error == "broken: bad index"
    assert result.explain("asn").reason is ResolutionReason.LOOKUP_ERROR


def test_policy_can_show_unsupported_before_fallback() -> None:
    no_asn = provider("no_asn", {Capability.COUNTRY})
    asn = provider(
        "asn",
        {Capability.ASN},
        ProviderObservation(CanonicalField.ASN, FieldState.PRESENT, 13335),
    )
    policy = ResolutionPolicy(
        (
            rule(CanonicalField.ASN, "no_asn", "asn"),
            rule(CanonicalField.COUNTRY_CODE, "no_asn"),
            rule(CanonicalField.COUNTRY_NAME, "no_asn"),
        )
    )

    result = open_database(providers=[no_asn, asn], policy=policy).lookup("1.1.1.1")

    explanation = result.explain("asn")
    assert explanation.reason is ResolutionReason.FALLBACK
    assert explanation.providers[0].state is FieldState.UNSUPPORTED


def test_provider_registration_order_does_not_change_resolution() -> None:
    primary = provider(
        "primary",
        {Capability.ASN},
        ProviderObservation(CanonicalField.ASN, FieldState.PRESENT, 13335),
    )
    secondary = provider(
        "secondary",
        {Capability.ASN},
        ProviderObservation(CanonicalField.ASN, FieldState.PRESENT, 64500),
    )
    policy = ResolutionPolicy((rule(CanonicalField.ASN, "primary", "secondary"),))

    first = open_database(providers=[primary, secondary], policy=policy).lookup("1.1.1.1")
    second = open_database(providers=[secondary, primary], policy=policy).lookup("1.1.1.1")

    assert first.to_dict() == second.to_dict()


def test_duplicate_provider_versions_are_rejected() -> None:
    old = provider("same", {Capability.ASN}, version="v1")
    new = provider("same", {Capability.ASN}, version="v2")
    policy = ResolutionPolicy((rule(CanonicalField.ASN, "same"),))

    with pytest.raises(ValueError, match="one selected version"):
        open_database(providers=[old, new], policy=policy)


def test_policy_must_include_every_capable_provider() -> None:
    one = provider("one", {Capability.ASN})
    two = provider("two", {Capability.ASN})
    policy = ResolutionPolicy((rule(CanonicalField.ASN, "one"),))

    with pytest.raises(ValueError, match="omits capable providers: two"):
        open_database(providers=[one, two], policy=policy)


def test_unknown_provider_in_policy_is_rejected() -> None:
    one = provider("one", {Capability.ASN})
    policy = ResolutionPolicy((rule(CanonicalField.ASN, "one", "ghost"),))

    with pytest.raises(ValueError, match="unknown providers: ghost"):
        open_database(providers=[one], policy=policy)


def test_undeclared_capability_cannot_emit_canonical_field() -> None:
    bad = provider(
        "bad",
        set(),
        ProviderObservation(CanonicalField.ASN, FieldState.PRESENT, 13335),
    )
    policy = ResolutionPolicy((rule(CanonicalField.ASN, "bad"),))

    with pytest.raises(ValueError, match="without declaring asn"):
        open_database(providers=[bad], policy=policy).lookup("1.1.1.1")


def test_provider_metadata_is_not_promoted_to_canonical_fields() -> None:
    source = provider(
        "source",
        {Capability.ASN},
        ProviderObservation(CanonicalField.ASN, FieldState.PRESENT, 13335),
        metadata=(ProviderMetadata("vendor_risk_score", 99),),
    )
    policy = ResolutionPolicy((rule(CanonicalField.ASN, "source"),))

    result = open_database(providers=[source], policy=policy).lookup("1.1.1.1")

    assert result.asn.value == 13335
    assert "vendor_risk_score" not in result.to_dict()


def test_network_traits_are_multi_valued_and_provenanced() -> None:
    hosting = provider(
        "hosting",
        {Capability.NETWORK_TRAITS},
        traits=frozenset({NetworkTrait.HOSTING, NetworkTrait.CLOUD}),
    )
    proxy = provider(
        "proxy",
        {Capability.NETWORK_TRAITS},
        traits=frozenset({NetworkTrait.PROXY}),
    )
    result = open_database(
        providers=[proxy, hosting],
        policy=ResolutionPolicy(()),
    ).lookup("1.1.1.1")

    assert result.traits == frozenset(
        {NetworkTrait.HOSTING, NetworkTrait.CLOUD, NetworkTrait.PROXY}
    )
    assert [item.provenance.provider for item in result.trait_observations] == [
        "hosting",
        "hosting",
        "proxy",
    ]


def test_special_addresses_are_classified_without_provider_lookup() -> None:
    source = provider("source", {Capability.ASN})
    policy = ResolutionPolicy((rule(CanonicalField.ASN, "source"),))

    result = open_database(providers=[source], policy=policy).lookup("192.0.2.10")

    assert result.scope.value == "documentation"
    assert source.calls == []


def test_capability_discovery_is_explicit() -> None:
    source = provider("source", {Capability.ASN, Capability.COUNTRY})
    assert Capability.ASN in source.capabilities
    assert Capability.COUNTRY in source.capabilities
    assert Capability.ISP not in source.capabilities


def test_provider_observation_rejects_wrong_semantic_type() -> None:
    with pytest.raises(TypeError, match="ASN observations require an integer"):
        ProviderObservation(CanonicalField.ASN, FieldState.PRESENT, "13335")

    with pytest.raises(TypeError, match="country_code observations require a string"):
        ProviderObservation(CanonicalField.COUNTRY_CODE, FieldState.PRESENT, 1)


def test_provider_result_rejects_duplicate_fields() -> None:
    identity = ProviderIdentity("one", "fixture", "v1")
    observation = ProviderObservation(CanonicalField.ASN, FieldState.PRESENT, 13335)
    with pytest.raises(ValueError, match="duplicate canonical fields"):
        ProviderResult(
            ip=ip_address("1.1.1.1"),
            identity=identity,
            fields=(observation, observation),
        )
