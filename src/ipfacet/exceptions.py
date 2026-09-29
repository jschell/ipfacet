"""IPFacet exception hierarchy."""


class IPFacetError(Exception):
    """Base exception for expected IPFacet failures."""


class DatasetError(IPFacetError):
    """Base exception for dataset lifecycle failures."""


class DatasetNotInstalledError(DatasetError):
    """Requested reference dataset is not installed."""


class DatasetValidationError(DatasetError):
    """Reference dataset failed validation."""


class LookupError(IPFacetError):
    """Reference-data lookup failed."""
