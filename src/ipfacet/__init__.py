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
    CanonicalField,
    FieldExplanation,
    FieldObservation,
    FieldProvenance,
    FieldState,
    IPAddress,
    IPEnrichment,
    IPScope,
    NetworkTrait,
    ProviderFieldStatus,
    ResolvedField,
    ResolutionReason,
)
from ipfacet.provider import (
    Capability,
    EnrichmentProvider,
    ProviderIdentity,
    ProviderMetadata,
    ProviderObservation,
    ProviderResult,
)
from ipfacet.resolution import FieldPrecedence, ResolutionPolicy
from ipfacet.scope import classify_scope, parse_ip

__all__ = [
    "CanonicalField",
    "Capability",
    "Database",
    "DatasetError",
    "DatasetNotInstalledError",
    "DatasetValidationError",
    "EnrichmentProvider",
    "FieldExplanation",
    "FieldObservation",
    "FieldPrecedence",
    "FieldProvenance",
    "FieldState",
    "IPAddress",
    "IPEnrichment",
    "IPFacetError",
    "IPScope",
    "LookupBackend",
    "LookupError",
    "NetworkTrait",
    "ProviderFieldStatus",
    "ProviderIdentity",
    "ProviderMetadata",
    "ProviderObservation",
    "ProviderResult",
    "ResolvedField",
    "ResolutionPolicy",
    "ResolutionReason",
    "classify_scope",
    "open_database",
    "parse_ip",
]

__version__ = "0.1.0.dev0"
