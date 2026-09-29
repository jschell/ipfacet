from ipaddress import ip_address

from ipfacet import (
    FieldProvenance,
    FieldState,
    IPEnrichment,
    IPScope,
    ResolvedField,
    open_database,
)
from ipfacet.models import IPAddress


class SyntheticBackend:
    def __init__(self) -> None:
        self.calls: list[IPAddress] = []

    def lookup(self, ip: IPAddress) -> IPEnrichment | None:
        self.calls.append(ip)
        if str(ip) != "1.1.1.1":
            return None
        provenance = FieldProvenance("synthetic", "fixture", "1")
        return IPEnrichment(
            ip=ip,
            scope=IPScope.RESERVED,
            asn=ResolvedField(FieldState.PRESENT, 13335, provenance),
        )


def test_lookup_normalizes_scope_and_uses_backend() -> None:
    backend = SyntheticBackend()
    result = open_database(backend=backend).lookup("1.1.1.1")
    assert result.ip == ip_address("1.1.1.1")
    assert result.scope is IPScope.GLOBAL
    assert result.asn.value == 13335


def test_lookup_many_deduplicates_ips() -> None:
    backend = SyntheticBackend()
    results = open_database(backend=backend).lookup_many(["1.1.1.1", "1.1.1.1", "8.8.8.8"])
    assert list(results) == [ip_address("1.1.1.1"), ip_address("8.8.8.8")]
    assert backend.calls.count(ip_address("1.1.1.1")) == 1
    assert backend.calls.count(ip_address("8.8.8.8")) == 1


def test_no_backend_still_classifies_locally() -> None:
    result = open_database().lookup("192.0.2.10")
    assert result.scope is IPScope.DOCUMENTATION
    assert result.asn.state is FieldState.UNSUPPORTED
