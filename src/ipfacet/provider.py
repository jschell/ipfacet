"""Provider contracts and capability declarations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from ipfacet.models import CanonicalField, FieldState, IPAddress, NetworkTrait

type ProviderScalar = int | str
type MetadataValue = str | int | float | bool | None


class Capability(StrEnum):
    """Semantic capabilities a provider may expose."""

    ASN = "asn"
    AS_ORGANIZATION = "as_organization"
    AS_DOMAIN = "as_domain"
    PREFIX = "prefix"
    COUNTRY = "country"
    CONTINENT = "continent"
    REGION = "region"
    CITY = "city"
    TIMEZONE = "timezone"
    ISP = "isp"
    NETWORK_TRAITS = "network_traits"


FIELD_CAPABILITY: dict[CanonicalField, Capability] = {
    CanonicalField.ASN: Capability.ASN,
    CanonicalField.AS_NAME: Capability.AS_ORGANIZATION,
    CanonicalField.AS_DOMAIN: Capability.AS_DOMAIN,
    CanonicalField.NETWORK: Capability.PREFIX,
    CanonicalField.COUNTRY_CODE: Capability.COUNTRY,
    CanonicalField.COUNTRY_NAME: Capability.COUNTRY,
    CanonicalField.CONTINENT_CODE: Capability.CONTINENT,
    CanonicalField.REGION: Capability.REGION,
    CanonicalField.CITY: Capability.CITY,
    CanonicalField.TIMEZONE: Capability.TIMEZONE,
    CanonicalField.ISP: Capability.ISP,
}


@dataclass(frozen=True, slots=True)
class ProviderIdentity:
    """Exact selected provider dataset snapshot."""

    provider: str
    dataset: str
    version: str
    dataset_format: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderObservation:
    """One provider's state/value for a canonical field."""

    field: CanonicalField
    state: FieldState
    value: ProviderScalar | None = None
    error: str | None = None
    semantics: str | None = None

    def __post_init__(self) -> None:
        if self.state is FieldState.CONFLICT:
            raise ValueError("provider observations cannot declare canonical conflicts")
        if self.state is FieldState.PRESENT:
            if self.value is None:
                raise ValueError("present provider observations require a value")
            if self.field is CanonicalField.ASN and (
                not isinstance(self.value, int) or isinstance(self.value, bool)
            ):
                raise TypeError("ASN observations require an integer value")
            if self.field is not CanonicalField.ASN and not isinstance(self.value, str):
                raise TypeError(f"{self.field.value} observations require a string value")
        elif self.value is not None:
            raise ValueError("non-present provider observations cannot carry a value")
        if self.state is FieldState.LOOKUP_ERROR and not self.error:
            raise ValueError("lookup_error provider observations require an error")
        if self.state is not FieldState.LOOKUP_ERROR and self.error is not None:
            raise ValueError("only lookup_error provider observations may carry an error")


@dataclass(frozen=True, slots=True)
class ProviderMetadata:
    """Opaque provider metadata retained without canonical promotion."""

    key: str
    value: MetadataValue


@dataclass(frozen=True, slots=True)
class ProviderResult:
    """Normalized output from exactly one selected provider snapshot."""

    ip: IPAddress
    identity: ProviderIdentity
    fields: tuple[ProviderObservation, ...] = ()
    traits: frozenset[NetworkTrait] = frozenset()
    metadata: tuple[ProviderMetadata, ...] = ()

    def __post_init__(self) -> None:
        field_names = [item.field for item in self.fields]
        if len(field_names) != len(set(field_names)):
            raise ValueError("provider result contains duplicate canonical fields")
        metadata_keys = [item.key for item in self.metadata]
        if len(metadata_keys) != len(set(metadata_keys)):
            raise ValueError("provider result contains duplicate metadata keys")

    def observation(self, field: CanonicalField) -> ProviderObservation | None:
        return next((item for item in self.fields if item.field is field), None)


class EnrichmentProvider(Protocol):
    """Provider-neutral local reference-data lookup contract."""

    @property
    def identity(self) -> ProviderIdentity: ...

    @property
    def capabilities(self) -> frozenset[Capability]: ...

    def lookup(self, ip: IPAddress) -> ProviderResult: ...
