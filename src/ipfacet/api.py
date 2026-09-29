"""Notebook- and application-facing API."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace
from typing import Protocol

from ipfacet.models import IPAddress, IPEnrichment
from ipfacet.scope import classify_scope, parse_ip


class LookupBackend(Protocol):
    """Minimal Plan-00 backend contract; provider capabilities arrive in Plan 01."""

    def lookup(self, ip: IPAddress) -> IPEnrichment | None: ...


class Database:
    """Local enrichment database facade."""

    def __init__(self, backend: LookupBackend | None = None) -> None:
        self._backend = backend

    def lookup(self, value: str | IPAddress) -> IPEnrichment:
        ip = parse_ip(value)
        scope = classify_scope(ip)
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


def open_database(*, backend: LookupBackend | None = None) -> Database:
    """Open an IPFacet database facade."""
    return Database(backend=backend)
