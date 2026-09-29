"""Built-in reference-data providers."""

from ipfacet.providers.ip2proxy_lite import (
    IP2PROXY_LITE_DEFINITION,
    IP2ProxyLiteAcquirer,
    IP2ProxyLitePX8Provider,
    IP2ProxyLiteValidator,
    open_ip2proxy_lite,
)
from ipfacet.providers.ipinfo_lite import (
    IPINFO_LITE_DEFINITION,
    IPinfoLiteAcquirer,
    IPinfoLiteCSVProvider,
    IPinfoLiteValidator,
    open_ipinfo_lite,
)
from ipfacet.providers.maxmind_geolite2 import (
    MAXMIND_DEFINITION,
    MaxMindGeoLite2Acquirer,
    MaxMindGeoLite2CSVProvider,
    MaxMindGeoLite2Validator,
    open_maxmind_geolite2,
)

__all__ = [
    "IP2PROXY_LITE_DEFINITION",
    "IPINFO_LITE_DEFINITION",
    "MAXMIND_DEFINITION",
    "IP2ProxyLiteAcquirer",
    "IP2ProxyLitePX8Provider",
    "IP2ProxyLiteValidator",
    "IPinfoLiteAcquirer",
    "IPinfoLiteCSVProvider",
    "IPinfoLiteValidator",
    "MaxMindGeoLite2Acquirer",
    "MaxMindGeoLite2CSVProvider",
    "MaxMindGeoLite2Validator",
    "open_ip2proxy_lite",
    "open_ipinfo_lite",
    "open_maxmind_geolite2",
]
