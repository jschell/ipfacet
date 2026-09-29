from ipaddress import ip_address

import pytest

from ipfacet import (
    FieldObservation,
    FieldProvenance,
    FieldState,
    IPEnrichment,
    IPScope,
    ResolvedField,
)


def test_present_field_requires_provenance() -> None:
    with pytest.raises(ValueError, match="require value and provenance"):
        ResolvedField(state=FieldState.PRESENT, value=13335)


def test_lookup_error_requires_message() -> None:
    with pytest.raises(ValueError, match="require an error message"):
        ResolvedField[str](state=FieldState.LOOKUP_ERROR)


def test_conflict_preserves_selected_value_and_observations() -> None:
    first = FieldProvenance("one", "asn", "2026-09-01")
    second = FieldProvenance("two", "asn", "2026-09-02")
    field = ResolvedField(
        state=FieldState.CONFLICT,
        value=13335,
        provenance=first,
        observations=(FieldObservation(13335, first), FieldObservation(64500, second)),
    )
    result = IPEnrichment(ip=ip_address("1.1.1.1"), scope=IPScope.GLOBAL, asn=field)
    assert field.conflict
    assert result.has_conflicts
    assert field.observations[1].value == 64500


def test_canonical_serialization_is_deterministic() -> None:
    provenance = FieldProvenance("synthetic", "fixture", "1", "memory")
    result = IPEnrichment(
        ip=ip_address("2001:db8::1"),
        scope=IPScope.DOCUMENTATION,
        asn=ResolvedField(
            FieldState.PRESENT,
            64500,
            provenance,
            (FieldObservation(64500, provenance),),
        ),
    )
    expected = result.to_dict()
    assert result.to_dict() == expected
    assert expected["ip"] == "2001:db8::1"
    assert expected["scope"] == "documentation"
    assert expected["traits"] == []
