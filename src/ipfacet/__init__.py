"""Provider-neutral offline IP enrichment."""

from ipfacet.api import Database, LookupBackend, open_database
from ipfacet.exceptions import (
    DatasetError,
    DatasetNotInstalledError,
    DatasetValidationError,
    IPFacetError,
    LookupError,
)
from ipfacet.models import (
    FieldObservation,
    FieldProvenance,
    FieldState,
    IPAddress,
    IPEnrichment,
    IPScope,
    NetworkTrait,
    ResolvedField,
)
from ipfacet.scope import classify_scope, parse_ip

__all__ = [
    "Database",
    "DatasetError",
    "DatasetNotInstalledError",
    "DatasetValidationError",
    "FieldObservation",
    "FieldProvenance",
    "FieldState",
    "IPAddress",
    "IPEnrichment",
    "IPFacetError",
    "IPScope",
    "LookupBackend",
    "LookupError",
    "NetworkTrait",
    "ResolvedField",
    "classify_scope",
    "open_database",
    "parse_ip",
]

__version__ = "0.1.0.dev0"
