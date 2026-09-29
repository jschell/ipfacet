"""Notebook- and application-facing API."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace
from typing import Protocol

from ipfacet.models import IPAddress, IPEnrichment
from ipfacet.provider import EnrichmentProvider
from ipfacet.resolution import ProviderResolver, ResolutionPolicy
from ipfacet.scope import classify_scope, parse_ip


class LookupBackend(Protocol):
    """Legacy Plan-00 single-backend contract."""

    def lookup(self, ip: IPAddress) -> IPEnrichment | None: ...


class Database:
    """Local enrichment database facade."""

    def __init__(
        self,
        backend: LookupBackend | None = None,
        *,
        providers: tuple[EnrichmentProvider, ...] = (),
        policy: ResolutionPolicy | None = None,
    ) -> None:
        if backend is not None and providers:
            raise ValueError("backend and providers are mutually exclusive")
        if providers and policy is None:
            raise ValueError("provider lookup requires an explicit resolution policy")
        if policy is not None and not providers:
            raise ValueError("resolution policy requires providers")
        self._backend = backend
        self._resolver = (
            ProviderResolver(providers, policy)
            if providers and policy is not None
            else None
        )

    def lookup(self, value: str | IPAddress) -> IPEnrichment:
        ip = parse_ip(value)
        scope = classify_scope(ip)

        if self._resolver is not None:
            return self._resolver.lookup(ip)

        if self._backend is None:
            return IPEnrichment(ip=ip, scope=scope)
        result = self._backend.lookup(ip)
        if result is None:
            return IPEnrichment(ip=ip, scope=scope)
        if result.ip != ip:
            raise ValueError("backend returned enrichment for a different IP address")
        return replace(result, scope=scope)

    def lookup_many(self, values: Iterable[str | IPAddress]) -> Mapping[IPAddress, IPEnrichment]:
        """Enrich unique addresses once and return results keyed by parsed IP."""
        parsed = dict.fromkeys(parse_ip(value) for value in values)
        return {ip: self.lookup(ip) for ip in parsed}


def open_database(
    *,
    backend: LookupBackend | None = None,
    providers: Iterable[EnrichmentProvider] = (),
    policy: ResolutionPolicy | None = None,
) -> Database:
    """Open an IPFacet database facade with a legacy backend or provider set."""
    return Database(backend=backend, providers=tuple(providers), policy=policy)
