"""Canonical IPFacet models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from ipaddress import IPv4Address, IPv6Address

type IPAddress = IPv4Address | IPv6Address


class FieldState(StrEnum):
    """State of a canonical enrichment field."""

    PRESENT = "present"
    NOT_FOUND = "not_found"
    UNSUPPORTED = "unsupported"
    CONFLICT = "conflict"
    LOOKUP_ERROR = "lookup_error"


class IPScope(StrEnum):
    """Locally determined address scope."""

    GLOBAL = "global"
    PRIVATE = "private"
    SHARED = "shared"
    LOOPBACK = "loopback"
    LINK_LOCAL = "link_local"
    MULTICAST = "multicast"
    DOCUMENTATION = "documentation"
    RESERVED = "reserved"
    UNSPECIFIED = "unspecified"


class NetworkTrait(StrEnum):
    """Provider-neutral network characteristics; traits are not maliciousness signals."""

    RESIDENTIAL = "residential"
    MOBILE = "mobile"
    BUSINESS = "business"
    HOSTING = "hosting"
    CLOUD = "cloud"
    CDN = "cdn"
    EDUCATION = "education"
    GOVERNMENT = "government"
    VPN = "vpn"
    PROXY = "proxy"
    TOR = "tor"


@dataclass(frozen=True, slots=True)
class FieldProvenance:
    """Dataset identity for one observation."""

    provider: str
    dataset: str
    version: str
    dataset_format: str | None = None


@dataclass(frozen=True, slots=True)
class FieldObservation[T]:
    """A value reported by one provider dataset."""

    value: T
    provenance: FieldProvenance


@dataclass(frozen=True, slots=True)
class ResolvedField[T]:
    """Resolved canonical field plus all observations used to resolve it."""

    state: FieldState
    value: T | None = None
    provenance: FieldProvenance | None = None
    observations: tuple[FieldObservation[T], ...] = ()
    error: str | None = None

    def __post_init__(self) -> None:
        if self.state in {FieldState.PRESENT, FieldState.CONFLICT}:
            if self.value is None or self.provenance is None:
                raise ValueError("present/conflict fields require value and provenance")
        elif self.value is not None or self.provenance is not None:
            raise ValueError("non-value field states cannot carry value/provenance")
        if self.state is FieldState.LOOKUP_ERROR and not self.error:
            raise ValueError("lookup_error fields require an error message")
        if self.state is not FieldState.LOOKUP_ERROR and self.error is not None:
            raise ValueError("only lookup_error fields may carry an error message")

    @property
    def conflict(self) -> bool:
        return self.state is FieldState.CONFLICT


@dataclass(frozen=True, slots=True)
class IPEnrichment:
    """Canonical enrichment result for one IP address."""

    ip: IPAddress
    scope: IPScope
    asn: ResolvedField[int] = field(default_factory=lambda: ResolvedField(FieldState.UNSUPPORTED))
    as_name: ResolvedField[str] = field(
        default_factory=lambda: ResolvedField(FieldState.UNSUPPORTED)
    )
    as_domain: ResolvedField[str] = field(
        default_factory=lambda: ResolvedField(FieldState.UNSUPPORTED)
    )
    network: ResolvedField[str] = field(
        default_factory=lambda: ResolvedField(FieldState.UNSUPPORTED)
    )
    country_code: ResolvedField[str] = field(
        default_factory=lambda: ResolvedField(FieldState.UNSUPPORTED)
    )
    country_name: ResolvedField[str] = field(
        default_factory=lambda: ResolvedField(FieldState.UNSUPPORTED)
    )
    continent_code: ResolvedField[str] = field(
        default_factory=lambda: ResolvedField(FieldState.UNSUPPORTED)
    )
    isp: ResolvedField[str] = field(default_factory=lambda: ResolvedField(FieldState.UNSUPPORTED))
    traits: frozenset[NetworkTrait] = frozenset()

    @property
    def has_conflicts(self) -> bool:
        fields = (
            self.asn,
            self.as_name,
            self.as_domain,
            self.network,
            self.country_code,
            self.country_name,
            self.continent_code,
            self.isp,
        )
        return any(item.conflict for item in fields)
