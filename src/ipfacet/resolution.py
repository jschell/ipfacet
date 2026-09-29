"""Deterministic field-specific provider resolution."""

from __future__ import annotations

from dataclasses import dataclass

from ipfacet.models import (
    CanonicalField,
    FieldExplanation,
    FieldObservation,
    FieldProvenance,
    FieldState,
    IPAddress,
    IPEnrichment,
    IPScope,
    ProviderFieldStatus,
    ResolutionReason,
    ResolvedField,
)
from ipfacet.provider import (
    FIELD_CAPABILITY,
    Capability,
    EnrichmentProvider,
    ProviderObservation,
    ProviderResult,
)
from ipfacet.scope import classify_scope


@dataclass(frozen=True, slots=True)
class FieldPrecedence:
    """Ordered provider names for one canonical field."""

    field: CanonicalField
    providers: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.providers:
            raise ValueError(f"{self.field.value} precedence cannot be empty")
        if len(self.providers) != len(set(self.providers)):
            raise ValueError(f"{self.field.value} precedence contains duplicate providers")


@dataclass(frozen=True, slots=True)
class ResolutionPolicy:
    """Explicit field-specific source precedence."""

    rules: tuple[FieldPrecedence, ...]

    def __post_init__(self) -> None:
        fields = [rule.field for rule in self.rules]
        if len(fields) != len(set(fields)):
            raise ValueError("resolution policy contains duplicate field rules")

    def providers_for(self, field: CanonicalField) -> tuple[str, ...]:
        rule = next((item for item in self.rules if item.field is field), None)
        return () if rule is None else rule.providers


def _provenance(result: ProviderResult, observation: ProviderObservation) -> FieldProvenance:
    identity = result.identity
    return FieldProvenance(
        provider=identity.provider,
        dataset=identity.dataset,
        version=identity.version,
        dataset_format=identity.dataset_format,
        semantics=observation.semantics,
    )


class ProviderResolver:
    """Lookup and resolve a fixed set of selected provider snapshots."""

    def __init__(
        self,
        providers: tuple[EnrichmentProvider, ...],
        policy: ResolutionPolicy,
    ) -> None:
        if not providers:
            raise ValueError("at least one provider is required")
        names = [provider.identity.provider for provider in providers]
        if len(names) != len(set(names)):
            raise ValueError(
                "only one selected version per provider may participate in a lookup"
            )
        self._providers = {provider.identity.provider: provider for provider in providers}
        self._policy = policy
        self._validate_policy()

    def _validate_policy(self) -> None:
        known = set(self._providers)
        for rule in self._policy.rules:
            unknown = set(rule.providers) - known
            if unknown:
                raise ValueError(
                    f"{rule.field.value} precedence references unknown providers: "
                    f"{', '.join(sorted(unknown))}"
                )

        for field, capability in FIELD_CAPABILITY.items():
            capable = {
                name
                for name, provider in self._providers.items()
                if capability in provider.capabilities
            }
            if not capable:
                continue
            configured = set(self._policy.providers_for(field))
            missing = capable - configured
            if missing:
                raise ValueError(
                    f"{field.value} precedence omits capable providers: "
                    f"{', '.join(sorted(missing))}"
                )

    def lookup(self, ip: IPAddress) -> IPEnrichment:
        scope = classify_scope(ip)
        if scope is not IPScope.GLOBAL:
            return IPEnrichment(ip=ip, scope=scope)

        results: dict[str, ProviderResult] = {}
        for name, provider in self._providers.items():
            result = provider.lookup(ip)
            self._validate_result(provider, result, ip)
            results[name] = result

        scalar: dict[CanonicalField, ResolvedField[int] | ResolvedField[str]] = {}
        explanations: list[FieldExplanation] = []
        for field in CanonicalField:
            resolved, explanation = self._resolve_field(field, results)
            scalar[field] = resolved
            explanations.append(explanation)

        trait_observations: list[FieldObservation] = []
        traits = set()
        for name in sorted(results):
            provider = self._providers[name]
            if Capability.NETWORK_TRAITS not in provider.capabilities:
                continue
            result = results[name]
            provenance = FieldProvenance(
                provider=result.identity.provider,
                dataset=result.identity.dataset,
                version=result.identity.version,
                dataset_format=result.identity.dataset_format,
                semantics="normalized network trait",
            )
            for trait in sorted(result.traits, key=lambda item: item.value):
                traits.add(trait)
                trait_observations.append(FieldObservation(trait, provenance))

        return IPEnrichment(
            ip=ip,
            scope=scope,
            asn=self._as_int(scalar[CanonicalField.ASN]),
            as_name=self._as_str(scalar[CanonicalField.AS_NAME]),
            as_domain=self._as_str(scalar[CanonicalField.AS_DOMAIN]),
            network=self._as_str(scalar[CanonicalField.NETWORK]),
            country_code=self._as_str(scalar[CanonicalField.COUNTRY_CODE]),
            country_name=self._as_str(scalar[CanonicalField.COUNTRY_NAME]),
            continent_code=self._as_str(scalar[CanonicalField.CONTINENT_CODE]),
            region=self._as_str(scalar[CanonicalField.REGION]),
            city=self._as_str(scalar[CanonicalField.CITY]),
            timezone=self._as_str(scalar[CanonicalField.TIMEZONE]),
            isp=self._as_str(scalar[CanonicalField.ISP]),
            traits=frozenset(traits),
            trait_observations=tuple(trait_observations),
            explanations=tuple(explanations),
        )

    @staticmethod
    def _validate_result(
        provider: EnrichmentProvider,
        result: ProviderResult,
        ip: IPAddress,
    ) -> None:
        if result.ip != ip:
            raise ValueError("provider returned enrichment for a different IP address")
        if result.identity != provider.identity:
            raise ValueError("provider result identity does not match selected provider snapshot")
        for observation in result.fields:
            required = FIELD_CAPABILITY[observation.field]
            if required not in provider.capabilities:
                raise ValueError(
                    f"{provider.identity.provider} returned {observation.field.value} "
                    f"without declaring {required.value}"
                )
        if result.traits and Capability.NETWORK_TRAITS not in provider.capabilities:
            raise ValueError(
                f"{provider.identity.provider} returned traits without declaring network_traits"
            )

    @staticmethod
    def _status(
        result: ProviderResult,
        state: FieldState,
        *,
        value: int | str | None = None,
        error: str | None = None,
    ) -> ProviderFieldStatus:
        identity = result.identity
        return ProviderFieldStatus(
            provider=identity.provider,
            dataset=identity.dataset,
            version=identity.version,
            state=state,
            value=value,
            error=error,
        )

    def _resolve_field(
        self,
        field: CanonicalField,
        results: dict[str, ProviderResult],
    ) -> tuple[ResolvedField[int] | ResolvedField[str], FieldExplanation]:
        capability = FIELD_CAPABILITY[field]
        order = self._policy.providers_for(field)
        statuses: list[ProviderFieldStatus] = []
        present: list[tuple[ProviderResult, ProviderObservation]] = []

        for name in order:
            provider = self._providers[name]
            result = results[name]
            if capability not in provider.capabilities:
                statuses.append(
                    self._status(result, FieldState.UNSUPPORTED)
                )
                continue
            observation = result.observation(field)
            if observation is None:
                statuses.append(self._status(result, FieldState.NOT_FOUND))
                continue
            statuses.append(
                self._status(
                    result,
                    observation.state,
                    value=observation.value,
                    error=observation.error,
                )
            )
            if observation.state is FieldState.PRESENT:
                present.append((result, observation))

        if present:
            selected_result, selected_observation = present[0]
            selected_value = selected_observation.value
            observations = tuple(
                FieldObservation(observation.value, _provenance(result, observation))
                for result, observation in present
                if observation.value is not None
            )
            conflict = any(
                observation.value != selected_value for _, observation in present[1:]
            )
            fallback = statuses[0].state is not FieldState.PRESENT if statuses else False
            if conflict:
                state = FieldState.CONFLICT
                reason = ResolutionReason.CONFLICT
            elif len(present) > 1:
                state = FieldState.PRESENT
                reason = ResolutionReason.AGREEMENT
            elif fallback:
                state = FieldState.PRESENT
                reason = ResolutionReason.FALLBACK
            else:
                state = FieldState.PRESENT
                reason = ResolutionReason.SELECTED
            resolved = ResolvedField(
                state=state,
                value=selected_value,
                provenance=_provenance(selected_result, selected_observation),
                observations=observations,
            )
            return resolved, FieldExplanation(
                field=field,
                state=state,
                reason=reason,
                selected_provider=selected_result.identity.provider,
                providers=tuple(statuses),
            )

        errors = [status for status in statuses if status.state is FieldState.LOOKUP_ERROR]
        if errors:
            message = "; ".join(
                f"{status.provider}: {status.error}" for status in errors if status.error
            )
            resolved = ResolvedField[int](
                state=FieldState.LOOKUP_ERROR,
                error=message,
            )
            state = FieldState.LOOKUP_ERROR
            reason = ResolutionReason.LOOKUP_ERROR
        elif any(status.state is FieldState.NOT_FOUND for status in statuses):
            resolved = ResolvedField[int](state=FieldState.NOT_FOUND)
            state = FieldState.NOT_FOUND
            reason = ResolutionReason.NOT_FOUND
        else:
            resolved = ResolvedField[int](state=FieldState.UNSUPPORTED)
            state = FieldState.UNSUPPORTED
            reason = ResolutionReason.UNSUPPORTED

        return resolved, FieldExplanation(
            field=field,
            state=state,
            reason=reason,
            selected_provider=None,
            providers=tuple(statuses),
        )

    @staticmethod
    def _as_int(value: ResolvedField[int] | ResolvedField[str]) -> ResolvedField[int]:
        if value.value is not None and (
            not isinstance(value.value, int) or isinstance(value.value, bool)
        ):
            raise TypeError("resolved ASN must be an integer")
        return ResolvedField(
            state=value.state,
            value=value.value,
            provenance=value.provenance,
            observations=tuple(
                FieldObservation(item.value, item.provenance)
                for item in value.observations
                if isinstance(item.value, int) and not isinstance(item.value, bool)
            ),
            error=value.error,
        )

    @staticmethod
    def _as_str(value: ResolvedField[int] | ResolvedField[str]) -> ResolvedField[str]:
        if value.value is not None and not isinstance(value.value, str):
            raise TypeError("resolved string field must be a string")
        return ResolvedField(
            state=value.state,
            value=value.value,
            provenance=value.provenance,
            observations=tuple(
                FieldObservation(item.value, item.provenance)
                for item in value.observations
                if isinstance(item.value, str)
            ),
            error=value.error,
        )
