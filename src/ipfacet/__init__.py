"""Provider-neutral offline IP enrichment."""

from ipfacet.api import Database, LookupBackend, open_database
from ipfacet.credentials import environment_credentials
from ipfacet.dataset_manager import DatasetManager
from ipfacet.dataset_store import DatasetStore, default_data_dir
from ipfacet.datasets import (
    AcquiredDataset,
    AcquisitionMethod,
    DatasetAcquirer,
    DatasetDefinition,
    DatasetManifest,
    DatasetValidator,
    RetentionPolicy,
)
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
    ResolutionReason,
    ResolvedField,
)
from ipfacet.provider import (
    Capability,
    EnrichmentProvider,
    ProviderIdentity,
    ProviderMetadata,
    ProviderObservation,
    ProviderResult,
)
from ipfacet.registry import default_dataset_manager
from ipfacet.resolution import FieldPrecedence, ResolutionPolicy
from ipfacet.scope import classify_scope, parse_ip

__all__ = [
    "AcquiredDataset",
    "AcquisitionMethod",
    "CanonicalField",
    "Capability",
    "Database",
    "DatasetAcquirer",
    "DatasetDefinition",
    "DatasetError",
    "DatasetManager",
    "DatasetManifest",
    "DatasetNotInstalledError",
    "DatasetStore",
    "DatasetValidationError",
    "DatasetValidator",
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
    "ResolutionPolicy",
    "ResolutionReason",
    "ResolvedField",
    "RetentionPolicy",
    "classify_scope",
    "default_data_dir",
    "default_dataset_manager",
    "environment_credentials",
    "open_database",
    "parse_ip",
]

__version__ = "0.1.0.dev0"
