"""Built-in provider dataset registrations."""

from __future__ import annotations

from ipfacet.dataset_manager import DatasetManager
from ipfacet.dataset_store import DatasetStore
from ipfacet.providers.ipinfo_lite import (
    IPINFO_LITE_DATASET,
    IPINFO_LITE_DEFINITION,
    IPINFO_LITE_PROVIDER,
    IPinfoLiteAcquirer,
    IPinfoLiteValidator,
)


def default_dataset_manager(*, store: DatasetStore | None = None) -> DatasetManager:
    """Return a manager with built-in provider policy/acquisition registrations."""
    return DatasetManager(
        store=store,
        definitions=(IPINFO_LITE_DEFINITION,),
        acquirers=(IPinfoLiteAcquirer(),),
        validators={(IPINFO_LITE_PROVIDER, IPINFO_LITE_DATASET): IPinfoLiteValidator()},
    )
