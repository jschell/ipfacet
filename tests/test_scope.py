import pytest

from ipfacet import IPScope, classify_scope, parse_ip


@pytest.mark.parametrize(
    ("value", "scope"),
    [
        ("8.8.8.8", IPScope.GLOBAL),
        ("2001:4860:4860::8888", IPScope.GLOBAL),
        ("10.1.2.3", IPScope.PRIVATE),
        ("172.16.0.1", IPScope.PRIVATE),
        ("192.168.1.1", IPScope.PRIVATE),
        ("fc00::1", IPScope.PRIVATE),
        ("100.64.0.1", IPScope.SHARED),
        ("127.0.0.1", IPScope.LOOPBACK),
        ("::1", IPScope.LOOPBACK),
        ("169.254.1.1", IPScope.LINK_LOCAL),
        ("fe80::1", IPScope.LINK_LOCAL),
        ("224.0.0.1", IPScope.MULTICAST),
        ("ff02::1", IPScope.MULTICAST),
        ("192.0.2.1", IPScope.DOCUMENTATION),
        ("198.51.100.1", IPScope.DOCUMENTATION),
        ("203.0.113.1", IPScope.DOCUMENTATION),
        ("2001:db8::1", IPScope.DOCUMENTATION),
        ("0.0.0.0", IPScope.UNSPECIFIED),
        ("::", IPScope.UNSPECIFIED),
    ],
)
def test_scope_classification(value: str, scope: IPScope) -> None:
    assert classify_scope(parse_ip(value)) is scope


def test_invalid_ip_raises_value_error() -> None:
    with pytest.raises(ValueError):
        parse_ip("not-an-ip")
