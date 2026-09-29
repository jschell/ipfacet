"""Built-in provider dataset registrations."""

from __future__ import annotations

from ipfacet.dataset_manager import DatasetManager
from ipfacet.dataset_store import DatasetStore
from ipfacet.providers.ip2proxy_lite import (
    IP2PROXY_LITE_DATASET,
    IP2PROXY_LITE_DEFINITION,
    IP2PROXY_LITE_PROVIDER,
    IP2ProxyLiteAcquirer,
    IP2ProxyLiteValidator,
)
from ipfacet.providers.ipinfo_lite import (
    IPINFO_LITE_DATASET,
    IPINFO_LITE_DEFINITION,
    IPINFO_LITE_PROVIDER,
    IPinfoLiteAcquirer,
    IPinfoLiteValidator,
)
from ipfacet.providers.maxmind_geolite2 import (
    MAXMIND_DATASET,
    MAXMIND_DEFINITION,
    MAXMIND_PROVIDER,
    MaxMindGeoLite2Acquirer,
    MaxMindGeoLite2Validator,
)


def default_dataset_manager(*, store: DatasetStore | None = None) -> DatasetManager:
    """Return a manager with built-in provider policy/acquisition registrations."""
    return DatasetManager(
        store=store,
        definitions=(IPINFO_LITE_DEFINITION, IP2PROXY_LITE_DEFINITION, MAXMIND_DEFINITION),
        acquirers=(IPinfoLiteAcquirer(), IP2ProxyLiteAcquirer(), MaxMindGeoLite2Acquirer()),
        validators={
            (IPINFO_LITE_PROVIDER, IPINFO_LITE_DATASET): IPinfoLiteValidator(),
            (IP2PROXY_LITE_PROVIDER, IP2PROXY_LITE_DATASET): IP2ProxyLiteValidator(),
            (MAXMIND_PROVIDER, MAXMIND_DATASET): MaxMindGeoLite2Validator(),
        },
    )
