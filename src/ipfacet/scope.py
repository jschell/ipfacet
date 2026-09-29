"""Local IP parsing and special-purpose classification."""

from __future__ import annotations

from ipaddress import IPv4Address, IPv6Address, ip_address, ip_network

from ipfacet.models import IPAddress, IPScope

_DOCUMENTATION = (
    ip_network("192.0.2.0/24"),
    ip_network("198.51.100.0/24"),
    ip_network("203.0.113.0/24"),
    ip_network("2001:db8::/32"),
)
_SHARED = (ip_network("100.64.0.0/10"),)
_PRIVATE = (
    ip_network("10.0.0.0/8"),
    ip_network("172.16.0.0/12"),
    ip_network("192.168.0.0/16"),
    ip_network("fc00::/7"),
)


def parse_ip(value: str | IPAddress) -> IPAddress:
    """Parse an IPv4/IPv6 string, preserving already parsed addresses."""
    if isinstance(value, (IPv4Address, IPv6Address)):
        return value
    return ip_address(value)


def classify_scope(address: IPAddress) -> IPScope:
    """Classify an address without consulting an enrichment dataset."""
    if any(address in network for network in _DOCUMENTATION):
        return IPScope.DOCUMENTATION
    if any(address in network for network in _SHARED):
        return IPScope.SHARED
    if any(address in network for network in _PRIVATE):
        return IPScope.PRIVATE
    if address.is_unspecified:
        return IPScope.UNSPECIFIED
    if address.is_loopback:
        return IPScope.LOOPBACK
    if address.is_link_local:
        return IPScope.LINK_LOCAL
    if address.is_multicast:
        return IPScope.MULTICAST
    if address.is_reserved:
        return IPScope.RESERVED
    if address.is_global:
        return IPScope.GLOBAL
    if address.is_private:
        return IPScope.PRIVATE
    return IPScope.RESERVED
