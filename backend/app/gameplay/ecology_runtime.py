from __future__ import annotations

from hashlib import sha256
import json
from dataclasses import dataclass
from typing import Literal

from pydantic import ConfigDict, Field

from app.gameplay.construction_production_runtime import (
    CanonicalFrostProductionFinishCommand,
    ConstructionFrostFinishCommand,
    CanonicalSeasonalConstructionMaintenanceCommand,
    CanonicalWeatherFrontConstructionMaintenanceCommand,
    CanonicalWeatherFrontConstructionMaintenanceFanoutCommand,
    _take_canonical_hazard_admission_issuer,
    _take_canonical_seasonal_admission_issuer,
    _take_canonical_weather_front_admission_issuer,
    _take_canonical_weather_front_fanout_admission_issuer,
)
from app.gameplay.organization_government_runtime import (
    _take_canonical_weather_front_organization_supply_admission_issuer,
    _take_canonical_weather_front_organization_supply_fanout_admission_issuer,
)
from app.gameplay.economy_runtime import _take_weather_quote_admission_issuer, _take_weather_quote_fanout_admission_issuer
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog, GovernedAuthorityContractError
from app.gameplay.models import AtomicEventBatch, AppendBatchResult, GameplayFailure, GameplayOutboxEntry, OwnerAuthorizedFragment, StrictGameplayModel
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.semantic_authority import SemanticEffectCommand, SemanticSettlementAuthority
from app.gameplay.semantic_effects import EffectApplication, EffectLifecycleEvaluator, ResistanceProfile, StateDefinition
from app.gameplay.semantic_registry import SemanticRegistry, TagAssignment, TagDefinition
from app.gameplay.settlement_plan import build_multi_stream_atomic_event_batch_from_fragments
from app.gameplay.shared_contracts import GameplayCommandEnvelope, ScheduledObligation


def _ecology_admission_only(method):
    """Bind the one-time issuer outside the public ecology method surface."""

    issuer = _take_canonical_hazard_admission_issuer()

    def admitted(self, *, hazard_ref: str):
        return method(self, hazard_ref=hazard_ref, _issue=issuer)

    return admitted


def _ecology_seasonal_admission_only(method):
    issuer = _take_canonical_seasonal_admission_issuer()

    def admitted(self, *, region_ref: str):
        return method(self, region_ref=region_ref, _issue=issuer)

    return admitted


def _ecology_weather_front_admission_only(method):
    issuer = _take_canonical_weather_front_admission_issuer()

    def admitted(self, *, facility_ref: str, region_ref: str):
        return method(self, facility_ref=facility_ref, region_ref=region_ref, _issue=issuer)

    return admitted


def _ecology_weather_front_fanout_admission_only(method):
    issuer = _take_canonical_weather_front_fanout_admission_issuer()

    def admitted(self, *, facility_refs: tuple[str, str], region_ref: str):
        return method(self, facility_refs=facility_refs, region_ref=region_ref, _issue=issuer)

    return admitted


def _ecology_weather_front_organization_supply_admission_only(method):
    issuer = _take_canonical_weather_front_organization_supply_admission_issuer()

    def admitted(
        self,
        *,
        organization_ref: str,
        counterparty_organization_ref: str,
        commitment_ref: str,
        policy_revision: str,
        organization_grant_refs: tuple[str, ...],
        budget_reservation_refs: tuple[str, ...],
        region_ref: str,
    ):
        return method(
            self,
            organization_ref=organization_ref,
            counterparty_organization_ref=counterparty_organization_ref,
            commitment_ref=commitment_ref,
            policy_revision=policy_revision,
            organization_grant_refs=organization_grant_refs,
            budget_reservation_refs=budget_reservation_refs,
            region_ref=region_ref,
            _issue=issuer,
        )

    return admitted


def _ecology_weather_front_organization_supply_fanout_admission_only(method):
    issuer = _take_canonical_weather_front_organization_supply_fanout_admission_issuer()

    def admitted(
        self,
        *,
        target_specs: tuple[dict[str, object], dict[str, object]],
        region_ref: str,
    ):
        return method(
            self,
            target_specs=target_specs,
            region_ref=region_ref,
            _issue=issuer,
        )

    return admitted


def _ecology_weather_quote_admission_only(method):
    issuer = _take_weather_quote_admission_issuer()
    def admitted(self, *, region_ref: str, quote_ref: str):
        return method(self, region_ref=region_ref, quote_ref=quote_ref, _issue=issuer)
    return admitted


def _ecology_weather_quote_fanout_admission_only(method):
    issuer = _take_weather_quote_fanout_admission_issuer()
    def admitted(self, *, region_ref: str, quote_refs: tuple[str, str]):
        return method(self, region_ref=region_ref, quote_refs=quote_refs, _issue=issuer)
    return admitted


class EcologyRecord(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EnvironmentRegion(EcologyRecord):
    region_ref: str = Field(min_length=1)
    climate_profile_ref: str = Field(min_length=1)
    biome_tags: tuple[str, ...] = ()
    jurisdiction_ref: str = Field(min_length=1)
    neighbor_region_refs: tuple[str, ...] = ()
    revision: int = Field(ge=0)


class EnvironmentalState(EcologyRecord):
    region_ref: str = Field(min_length=1)
    temperature_centi_c: int
    moisture_basis_points: int = Field(ge=0, le=10_000)
    weather_ref: str = Field(min_length=1)
    revision: int = Field(ge=0)


class ResourceNode(EcologyRecord):
    node_ref: str = Field(min_length=1)
    region_ref: str = Field(min_length=1)
    substance_ref: str = Field(min_length=1)
    quantity: int = Field(ge=0)
    regeneration_per_tick: int = Field(ge=0)
    revision: int = Field(ge=0)


class CropRecord(EcologyRecord):
    crop_ref: str = Field(min_length=1)
    region_ref: str = Field(min_length=1)
    plot_ref: str | None = None
    health: int = Field(ge=0, le=100)
    growth_basis_points: int = Field(ge=0, le=10_000)
    revision: int = Field(ge=0)
    owner_ref: str = Field(min_length=1)


class HazardRecord(EcologyRecord):
    hazard_ref: str = Field(min_length=1)
    region_ref: str = Field(min_length=1)
    effect_ref: str = Field(min_length=1)
    source_crop_ref: str | None = None
    severity_basis_points: int = Field(ge=0, le=10_000)
    due_tick: int = Field(ge=0)
    duration_ticks: int = Field(gt=0)
    chain_budget: int = Field(default=1, gt=0)
    chain_depth: int = Field(default=0, ge=0)
    causal_parent_refs: tuple[str, ...] = ()
    semantic_revision: str = Field(min_length=1)
    rule_revision: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    revision: int = Field(default=0, ge=0)
    idempotency_key: str = Field(min_length=1)
    privacy_scope: Literal["project", "authority_only", "private_evidence"] = "project"


class EcologySeasonalProcessPolicy(EcologyRecord):
    """Closed, ecology-owned regional process; never a cross-domain writer."""

    policy_ref: Literal["policy:ecology_seasonal_cycle"] = "policy:ecology_seasonal_cycle"
    policy_revision: str = Field(default="1", min_length=1)
    max_elapsed_ticks: int = Field(default=16, gt=0, le=64)
    moisture_per_tick: int = Field(default=100, ge=0, le=1_000)
    crop_growth_per_tick: int = Field(default=50, ge=0, le=1_000)


class EcologyDroughtProcessPolicy(EcologyRecord):
    """Closed Ecology-only drought process over existing regional records."""

    policy_ref: Literal["policy:ecology_drought_cycle"] = "policy:ecology_drought_cycle"
    policy_revision: Literal["1"] = "1"
    max_elapsed_ticks: Literal[16] = 16
    moisture_loss_per_tick: Literal[500] = 500
    resource_loss_per_tick: Literal[2] = 2
    crop_health_loss_per_tick: Literal[5] = 5


class EcologyWeatherFrontPropagationPolicy(EcologyRecord):
    """Closed one-step regional weather propagation, owned only by ecology."""

    policy_ref: Literal["policy:ecology_weather_front_step"] = "policy:ecology_weather_front_step"
    policy_revision: Literal["1"] = "1"
    max_targets: Literal[1] = 1
    max_chain_depth: Literal[1] = 1


class EcologyWeatherFrontPathPropagationPolicy(EcologyRecord):
    """Closed, caller-driven Ecology-only path propagation with three hops."""

    policy_ref: Literal["policy:ecology_weather_front_path"] = "policy:ecology_weather_front_path"
    policy_revision: Literal["1"] = "1"
    max_targets: Literal[3] = 3
    max_chain_depth: Literal[3] = 3


class EcologyWeatherFrontFanoutPolicy(EcologyRecord):
    """Closed one-round fanout over existing Ecology region streams only."""

    policy_ref: Literal["policy:ecology_weather_front_fanout"] = "policy:ecology_weather_front_fanout"
    policy_revision: Literal["1"] = "1"
    max_targets: Literal[3] = 3
    max_chain_depth: Literal[1] = 1


class EcologyWeatherFrontWaveFanoutPolicy(EcologyRecord):
    """Closed two-wave fanout over existing Ecology region streams only."""

    policy_ref: Literal["policy:ecology_weather_front_wave_fanout"] = "policy:ecology_weather_front_wave_fanout"
    policy_revision: Literal["1"] = "1"
    max_targets: Literal[6] = 6
    max_chain_depth: Literal[2] = 2
    max_first_wave_targets: Literal[3] = 3


class EcologyWeatherFrontEventPlannerPolicy(EcologyRecord):
    """Closed Ecology-only planner bounds for event-derived propagation."""

    policy_ref: Literal["policy:ecology_weather_front_event_planner"] = "policy:ecology_weather_front_event_planner"
    policy_revision: Literal["1"] = "1"
    max_chain_depth: Literal[2] = 2
    max_first_wave_targets: Literal[3] = 3
    max_targets: Literal[6] = 6


class EcologyWeatherFrontWavePlan(EcologyRecord):
    """Immutable proposal derived from one committed weather-front event."""

    source_weather_event_id: str = Field(min_length=1)
    source_weather_event_revision: int = Field(ge=1)
    source_ecology_stream_id: str = Field(min_length=1)
    source_ecology_stream_revision: int = Field(ge=1)
    root_region_ref: str = Field(min_length=1)
    prior_source_region_ref: str = Field(min_length=1)
    weather_ref: str = Field(min_length=1)
    tick: int = Field(ge=0)
    policy_ref: Literal["policy:ecology_weather_front_event_planner"]
    policy_revision: Literal["1"] = "1"
    waves: tuple[tuple[tuple[str, str], ...], ...] = Field(min_length=1, max_length=2)
    planner_digest: str = Field(min_length=1)
    privacy_scope: Literal["project"] = "project"


class EcologyFrostCropStateExpiryPolicy(EcologyRecord):
    """The one admitted Ecology-owned scheduled crop-state row."""

    policy_ref: Literal["policy:ecology_frost_crop_state_expiry@1"] = "policy:ecology_frost_crop_state_expiry@1"
    policy_revision: Literal["1"] = "1"

    @staticmethod
    def obligation_id_for(*, region_ref: str, crop_ref: str) -> str:
        return f"obligation:ecology:frosted:{region_ref}:{crop_ref}"

    def build_obligation(
        self,
        *,
        region_ref: str,
        crop_ref: str,
        due_tick: int,
        expected_revision: int,
    ) -> ScheduledObligation:
        stream_id = EcologyHazardAuthority.ecology_stream_id(region_ref=region_ref)
        return ScheduledObligation(
            obligation_id=self.obligation_id_for(region_ref=region_ref, crop_ref=crop_ref),
            owner_ref=EcologyHazardAuthority._PRINCIPAL,
            due_tick=due_tick,
            policy_revision=self.policy_revision,
            status="open",
            source_refs=(self.policy_ref, f"crop:{crop_ref}", f"region:{region_ref}"),
            idempotency_key=f"obligation:ecology:frosted:{region_ref}:{crop_ref}:{self.policy_revision}",
            expected_revisions={stream_id: expected_revision},
            visibility_scope="project",
        )


class EcologyDroughtStateExpiryPolicy(EcologyRecord):
    """The one admitted Ecology-owned scheduled drought-state row."""

    policy_ref: Literal["policy:ecology_drought_state_expiry@1"] = "policy:ecology_drought_state_expiry@1"
    policy_revision: Literal["1"] = "1"

    @staticmethod
    def obligation_id_for(*, region_ref: str) -> str:
        return f"obligation:ecology:drought:{region_ref}"

    def build_obligation(
        self,
        *,
        region_ref: str,
        source_event_id: str,
        due_tick: int,
        expected_revision: int,
    ) -> ScheduledObligation:
        stream_id = EcologyHazardAuthority.ecology_stream_id(region_ref=region_ref)
        return ScheduledObligation(
            obligation_id=self.obligation_id_for(region_ref=region_ref),
            owner_ref=EcologyHazardAuthority._PRINCIPAL,
            due_tick=due_tick,
            policy_revision=self.policy_revision,
            status="open",
            source_refs=(self.policy_ref, region_ref, source_event_id),
            idempotency_key=f"obligation:ecology:drought:{region_ref}:{self.policy_revision}",
            expected_revisions={stream_id: expected_revision},
            visibility_scope="project",
        )


class HazardSettlementResult(EcologyRecord):
    committed: bool
    error_code: str | None = None
    committed_event_ids: tuple[str, ...] = ()
    idempotency_status: str = "rejected"


class FrostPropagationSource(EcologyRecord):
    hazard_ref: str = Field(min_length=1)
    crop_ref: str = Field(min_length=1)
    plot_ref: str = Field(min_length=1)
    region_ref: str = Field(min_length=1)
    source_event_id: str = Field(min_length=1)
    source_stream_revision: int = Field(ge=0)
    due_tick: int = Field(ge=0)
    semantic_revision: str = Field(min_length=1)
    rule_revision: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    causal_parent_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    privacy_scope: Literal["project", "authority_only"]


class FrostSourceResult(EcologyRecord):
    accepted: bool
    source: FrostPropagationSource | None = None
    error_code: str | None = None


class FrostFinishProposalResult(EcologyRecord):
    accepted: bool
    proposal: ConstructionFrostFinishCommand | None = None
    error_code: str | None = None


class CanonicalFrostProductionProposalResult(EcologyRecord):
    accepted: bool
    command: CanonicalFrostProductionFinishCommand | None = None
    error_code: str | None = None


class CanonicalWeatherFrontOrganizationSupplyCommand(EcologyRecord):
    edge_ref: Literal["ecology-weather:front-to-organization-supply:v1"]
    command_id: str = Field(min_length=1)
    source_authority_ref: Literal["authority:ecology"]
    ecology_stream_id: str = Field(min_length=1)
    ecology_stream_revision: int = Field(ge=1)
    weather_event_id: str = Field(min_length=1)
    weather_event_revision: int = Field(ge=1)
    source_region_ref: str = Field(min_length=1)
    target_region_ref: str = Field(min_length=1)
    weather_ref: str = Field(min_length=1)
    tick: int = Field(ge=0)
    organization_ref: str = Field(min_length=1)
    counterparty_organization_ref: str = Field(min_length=1)
    commitment_ref: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    organization_grant_refs: tuple[str, ...]
    budget_reservation_refs: tuple[str, ...]
    privacy_scope: Literal["project"]
    idempotency_key: str = Field(min_length=1)


class CanonicalWeatherFrontOrganizationSupplyFanoutTarget(EcologyRecord):
    organization_ref: str = Field(min_length=1)
    counterparty_organization_ref: str = Field(min_length=1)
    commitment_ref: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    organization_grant_refs: tuple[str, ...]
    budget_reservation_refs: tuple[str, ...]


class CanonicalWeatherFrontOrganizationSupplyFanoutCommand(EcologyRecord):
    edge_ref: Literal["ecology-weather:front-to-organization-supply-fanout:v1"]
    command_id: str = Field(min_length=1)
    source_authority_ref: Literal["authority:ecology"]
    ecology_stream_id: str = Field(min_length=1)
    ecology_stream_revision: int = Field(ge=1)
    weather_event_id: str = Field(min_length=1)
    weather_event_revision: int = Field(ge=1)
    source_region_ref: str = Field(min_length=1)
    target_region_ref: str = Field(min_length=1)
    weather_ref: str = Field(min_length=1)
    tick: int = Field(ge=0)
    target_specs: tuple[
        CanonicalWeatherFrontOrganizationSupplyFanoutTarget,
        CanonicalWeatherFrontOrganizationSupplyFanoutTarget,
    ]
    privacy_scope: Literal["project"]
    idempotency_key: str = Field(min_length=1)


@dataclass(frozen=True)
class CanonicalFrostConstructionIntent:
    command: CanonicalFrostProductionFinishCommand
    admission: object


@dataclass(frozen=True)
class CanonicalSeasonalConstructionIntent:
    command: CanonicalSeasonalConstructionMaintenanceCommand
    admission: object


@dataclass(frozen=True)
class CanonicalWeatherFrontConstructionIntent:
    command: CanonicalWeatherFrontConstructionMaintenanceCommand
    admission: object


@dataclass(frozen=True)
class CanonicalWeatherFrontConstructionFanoutIntent:
    command: CanonicalWeatherFrontConstructionMaintenanceFanoutCommand
    admission: object


@dataclass(frozen=True)
class CanonicalWeatherFrontOrganizationSupplyIntent:
    command: CanonicalWeatherFrontOrganizationSupplyCommand
    admission: object


@dataclass(frozen=True)
class CanonicalWeatherFrontOrganizationSupplyFanoutIntent:
    command: CanonicalWeatherFrontOrganizationSupplyFanoutCommand
    admission: object


class EcologyHazardAuthority:
    """Ecology owns hazard facts; crop state remains a semantic owner settlement."""

    _PRINCIPAL = "authority:ecology"
    _STREAM_PREFIX = "gameplay:ecology:"

    def __init__(self, *, store: GameplayEventStore) -> None:
        self.store = store
        self.registry = SemanticRegistry()
        self.registry.register_tag(TagDefinition(tag_ref="type:crop", category="type", version="1"))
        self.semantic_authority = SemanticSettlementAuthority(store=store, registry=self.registry)

    def commit_obligation_batch(self, batch: AtomicEventBatch) -> AppendBatchResult:
        """Commit only an Ecology-owned lifecycle plan."""
        if not batch.owner_fragments or any(
            fragment.owner_principal_ref != self._PRINCIPAL
            or any(not event.stream_id.startswith(self._STREAM_PREFIX) for event in batch.events)
            for fragment in batch.owner_fragments
        ):
            return self._rejected_obligation_append(batch.command_id, "ecology_owner_commit_scope_denied")
        event_types = tuple(event.event_type for event in batch.events)
        if any(".crop_state_" in event_type for event_type in event_types):
            contract_ref = "inf:ecology-frost-state-expiry@1"
        elif any(".drought_state_" in event_type for event_type in event_types):
            contract_ref = "inf:ecology-drought-state-expiry@1"
        else:
            contract_ref = ""
        if contract_ref:
            try:
                GovernedAuthorityContractCatalog.require_operation(
                    contract_ref=contract_ref,
                    contract_kind="lifecycle",
                    owner_ref=self._PRINCIPAL,
                    stream_ids=tuple(sorted({event.stream_id for event in batch.events})),
                    event_types=event_types,
                    projection_scope="project",
                )
            except GovernedAuthorityContractError as error:
                return self._rejected_obligation_append(batch.command_id, str(error))
        return self.store.append_batch(batch)

    @staticmethod
    def _rejected_obligation_append(command_id: str, error_code: str) -> AppendBatchResult:
        return AppendBatchResult(
            committed=False,
            transaction_id=f"transaction:{command_id}",
            command_id=command_id,
            idempotency_status="rejected",
            failure=GameplayFailure(error_code=error_code, message=error_code, failed_stage="ecology_obligation_commit"),
        )

    @classmethod
    def ecology_stream_id(cls, *, region_ref: str) -> str:
        return f"{cls._STREAM_PREFIX}{region_ref}"

    @classmethod
    def canonical_contract(cls) -> dict[str, object]:
        """Expose the admitted owner map for continuation/admission checks.

        This is a read-only contract description. It does not register a
        consumer, create a projection, or provide an alternate write path.
        """
        return {
            "owner": cls._PRINCIPAL,
            "stream_pattern": f"{cls._STREAM_PREFIX}{{region_ref}}",
            "record_kinds": ("region", "environment", "resource", "crop", "hazard"),
            "event_types": (
                "gameplay.ecology.region.recorded",
                "gameplay.ecology.region.retired",
                "gameplay.ecology.environment.recorded",
                "gameplay.ecology.environment.retired",
                "gameplay.ecology.resource.recorded",
                "gameplay.ecology.resource.retired",
                "gameplay.ecology.crop.recorded",
                "gameplay.ecology.crop.retired",
                "gameplay.ecology.hazard.recorded",
                "gameplay.ecology.hazard.retired",
                "gameplay.ecology.weather_front.propagated",
            ),
            "enabled_consumer_edges": (
                "ecology-hazard:frost-to-construction-finish:v1",
                "ecology-process:seasonal-to-construction-maintenance:v1",
                "ecology-weather:front-to-construction-maintenance:v1",
                "ecology-weather:front-to-construction-maintenance-fanout:v1",
                "ecology-weather:front-to-organization-supply:v1",
                "ecology-weather:front-to-organization-supply-fanout:v1",
                "ecology-weather:front-to-economy-quote:v1",
                "ecology-weather:front-to-economy-quote-fanout:v1",
            ),
            "consumer_admission_fence": "exact_ecology_registered_identity",
            "regional_propagation": {
                "policy_ref": "policy:ecology_weather_front_step",
                "policy_revision": "1",
                "max_targets": 1,
                "max_chain_depth": 1,
                "scope": "project",
            },
            "regional_path_propagation": {
                "policy_ref": "policy:ecology_weather_front_path",
                "policy_revision": "1",
                "max_targets": 3,
                "max_chain_depth": 3,
                "scope": "project",
            },
            "regional_fanout": {
                "policy_ref": "policy:ecology_weather_front_fanout",
                "policy_revision": "1",
                "max_targets": 3,
                "max_chain_depth": 1,
                "scope": "project",
            },
            "regional_wave_fanout": {
                "policy_ref": "policy:ecology_weather_front_wave_fanout",
                "policy_revision": "1",
                "max_targets": 6,
                "max_chain_depth": 2,
                "scope": "project",
            },
            "regional_event_derived_planner": {
                "policy_ref": "policy:ecology_weather_front_event_planner",
                "policy_revision": "1",
                "max_targets": 6,
                "max_chain_depth": 2,
                "source": "committed_project_weather_front_event",
                "scope": "project",
            },
            "state_obligation_rows": (
                {
                    "effect_ref": "effect:frost",
                    "state_ref": "state:frosted@1",
                    "policy_ref": "policy:ecology_frost_crop_state_expiry@1",
                    "stream_pattern": f"{cls._STREAM_PREFIX}{{region_ref}}",
                    "visibility_scope": "project",
                },
                {
                    "effect_ref": "effect:drought",
                    "state_ref": "state:drought@1",
                    "policy_ref": "policy:ecology_drought_state_expiry@1",
                    "stream_pattern": f"{cls._STREAM_PREFIX}{{region_ref}}",
                    "visibility_scope": "project",
                },
            ),
            "blocked_next_package": "INF-4R",
            "write_path": (
                "authority -> GameplayCommandEnvelope/SettlementPlan -> "
                "GameplayEventStore.append_batch -> outbox/replay -> scoped projection"
            ),
        }

    def record_region_bundle(
        self,
        *,
        envelope: GameplayCommandEnvelope,
        region: EnvironmentRegion,
        environment: EnvironmentalState,
        resource: ResourceNode,
        crop: CropRecord,
        hazard: HazardRecord,
    ) -> AppendBatchResult:
        if envelope.principal_ref != self._PRINCIPAL or envelope.source_ref != self._PRINCIPAL:
            return self._rejected(envelope, "ecology_authority_required")
        if hazard.privacy_scope == "private_evidence":
            return self._rejected(envelope, "ecology_privacy_scope_denied")
        if {environment.region_ref, resource.region_ref, crop.region_ref, hazard.region_ref} != {region.region_ref}:
            return self._rejected(envelope, "ecology_region_bundle_mismatch")
        stream_id = self.ecology_stream_id(region_ref=region.region_ref)
        projection = self.regional_projection(scope="authority")
        if any(
            record_ref in projection[collection]
            for collection, record_ref in (
                ("regions", region.region_ref),
                ("environments", region.region_ref),
                ("resources", resource.node_ref),
                ("crops", crop.crop_ref),
                ("hazards", hazard.hazard_ref),
            )
        ):
            return self._rejected(envelope, "ecology_bundle_not_initial")
        try:
            fragment = self._record_region_bundle_fragment(
                envelope=envelope,
                stream_id=stream_id,
                region=region,
                environment=environment,
                resource=resource,
                crop=crop,
                hazard=hazard,
                visibility_scope=self._visibility_scope(envelope),
            )
            batch = build_multi_stream_atomic_event_batch_from_fragments(
                command_id=envelope.command_id,
                idempotency_principal_ref=envelope.principal_ref,
                idempotency_key=envelope.idempotency_key,
                causation_id=envelope.causation_id,
                correlation_id=envelope.correlation_id,
                fragments=(fragment,),
            )
            batch = batch.model_copy(
                update={
                    "outbox_entries": [
                        GameplayOutboxEntry(
                            outbox_id=f"outbox:{event.event_id}",
                            transaction_id=batch.transaction_id,
                            event_id=event.event_id,
                            global_sequence=0,
                            topic="world.ecology.scoped_projection",
                            audience=event.visibility_policy,
                            payload_projection={"region_ref": region.region_ref, "event_type": event.event_type},
                        )
                        for event in batch.events
                    ]
                },
                deep=True,
            )
        except ValueError as exc:
            return self._rejected(envelope, str(exc))
        return self.store.append_batch(batch)

    def apply_crop_state(
        self,
        *,
        command: GameplayCommandEnvelope,
        hazard_ref: str,
        crop_ref: str,
        application: EffectApplication,
        resistance: ResistanceProfile,
        definition: StateDefinition,
        expiry_policy: EcologyFrostCropStateExpiryPolicy | None = None,
    ) -> AppendBatchResult:
        """Commit the fixed frost crop-state row; semantic evaluation never writes it."""
        policy = expiry_policy or EcologyFrostCropStateExpiryPolicy()
        projection = self.regional_projection(scope="authority")
        hazard = projection["hazards"].get(hazard_ref)
        crop = projection["crops"].get(crop_ref)
        if not isinstance(hazard, dict) or not isinstance(crop, dict):
            return self._rejected(command, "ecology_crop_state_source_missing")
        region_ref = hazard.get("region_ref")
        if not isinstance(region_ref, str) or region_ref != crop.get("region_ref"):
            return self._rejected(command, "ecology_crop_state_region_mismatch")
        stream_id = self.ecology_stream_id(region_ref=region_ref)
        if (
            command.principal_ref != self._PRINCIPAL
            or command.source_ref != self._PRINCIPAL
            or command.actor_ref != crop_ref
        ):
            return self._rejected(command, "ecology_crop_state_authority_required")
        if command.payload.get("visibility_scope", "project") != "project":
            return self._rejected(command, "ecology_crop_state_privacy_scope_denied")
        if hazard.get("privacy_scope") != "project":
            return self._rejected(command, "ecology_crop_state_source_privacy_denied")
        try:
            contract = SemanticRegistry.require_closed_state_owner_contract(
                effect_ref=application.effect_ref,
                state_ref=definition.state_ref,
            )
        except ValueError:
            return self._rejected(command, "ecology_crop_state_row_unregistered")
        if (
            contract.owner_ref != self._PRINCIPAL
            or contract.stream_pattern != "gameplay:ecology:{region_ref}"
            or contract.apply_event_type != "gameplay.ecology.crop_state_applied"
            or contract.opened_event_type != "gameplay.ecology.crop_state_obligation_opened"
            or contract.expired_event_type != "gameplay.ecology.crop_state_expired"
            or contract.settled_event_type != "gameplay.ecology.crop_state_obligation_settled"
            or contract.projection_scope != "project"
            or hazard.get("effect_ref") != contract.effect_ref
            or application.effect_ref != contract.effect_ref
            or resistance.effect_ref != contract.effect_ref
            or application.target_component_ref != crop_ref
            or definition != contract.definition
        ):
            return self._rejected(command, "ecology_crop_state_row_unregistered")
        digest = self._crop_state_application_digest(
            command=command,
            hazard_ref=hazard_ref,
            crop_ref=crop_ref,
            application=application,
            resistance=resistance,
            definition=definition,
            policy=policy,
        )
        existing = self.store.get_by_idempotency(self._PRINCIPAL, command.idempotency_key)
        if existing is not None and existing.committed:
            if self._committed_crop_state_application_digest(existing.committed_event_ids) == digest:
                return existing.model_copy(update={"idempotency_status": "duplicate_replayed"})
            return self._rejected(command, "idempotency_key_reused")
        if command.expected_revisions != {stream_id: self.store.get_stream_head(stream_id)}:
            return self._rejected(command, "revision_conflict")
        resolution = EffectLifecycleEvaluator().resolve(
            application,
            resistance=resistance,
            state=definition,
            existing_stacks=1 if self._has_open_frost_crop_state(region_ref=region_ref, crop_ref=crop_ref) else 0,
        )
        if not resolution.accepted or resolution.expiry_obligation is None:
            return self._rejected(command, resolution.error_code or "ecology_crop_state_expiry_required")
        obligation = policy.build_obligation(
            region_ref=region_ref,
            crop_ref=crop_ref,
            due_tick=int(resolution.expiry_obligation["due_tick"]),
            expected_revision=self.store.get_stream_head(stream_id),
        )
        try:
            fragment = OwnerAuthorizedFragment(
                fragment_id=f"fragment:ecology:frosted:apply:{region_ref}:{crop_ref}:{command.command_id}",
                owner_principal_ref=self._PRINCIPAL,
                source_rule_ref="ecology:frost-crop-state:v1",
                expected_revisions={stream_id: self.store.get_stream_head(stream_id)},
                pinned_revisions={"ecology": self.store.get_stream_head(stream_id)},
                event_specs={
                    stream_id: (
                        (
                            "gameplay.ecology.crop_state_applied",
                            {
                                "region_ref": region_ref,
                                "crop_ref": crop_ref,
                                "hazard_ref": hazard_ref,
                                "effect_ref": application.effect_ref,
                                "state_ref": definition.state_ref,
                                "stacks": resolution.next_stacks,
                                "effective_magnitude": resolution.effective_magnitude,
                                "due_tick": obligation.due_tick,
                                "crop_state_application_digest": digest,
                            },
                        ),
                        (
                            "gameplay.ecology.crop_state_obligation_opened",
                            {
                                "obligation_id": obligation.obligation_id,
                                "due_tick": obligation.due_tick,
                                "policy_ref": policy.policy_ref,
                                "policy_revision": policy.policy_revision,
                                "region_ref": region_ref,
                                "crop_ref": crop_ref,
                                "hazard_ref": hazard_ref,
                            },
                        ),
                    )
                },
                event_visibility_policies={stream_id: ("project", "project")},
            )
            batch = build_multi_stream_atomic_event_batch_from_fragments(
                command_id=command.command_id,
                idempotency_principal_ref=self._PRINCIPAL,
                idempotency_key=command.idempotency_key,
                causation_id=command.causation_id,
                correlation_id=command.correlation_id,
                fragments=(fragment,),
            )
            batch = batch.model_copy(
                update={
                    "outbox_entries": [
                        GameplayOutboxEntry(
                            outbox_id=f"outbox:{event.event_id}",
                            transaction_id=batch.transaction_id,
                            event_id=event.event_id,
                            global_sequence=0,
                            topic="world.ecology.scoped_projection",
                            audience="project",
                            payload_projection={"region_ref": region_ref, "crop_ref": crop_ref, "event_type": event.event_type},
                        )
                        for event in batch.events
                    ]
                },
                deep=True,
            )
        except ValueError as exc:
            return self._rejected(command, str(exc))
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:ecology-frost-state-expiry@1",
                contract_kind="lifecycle",
                owner_ref=self._PRINCIPAL,
                stream_ids=(stream_id,),
                event_types=tuple(event.event_type for event in batch.events),
                projection_scope="project",
            )
        except GovernedAuthorityContractError as error:
            return self._rejected(command, str(error))
        return self.store.append_batch(batch)

    def apply_drought_state(
        self,
        *,
        command: GameplayCommandEnvelope,
        region_ref: str,
        source_event_id: str,
        source_event_revision: int,
        application: EffectApplication,
        resistance: ResistanceProfile,
        definition: StateDefinition,
        expiry_policy: EcologyDroughtStateExpiryPolicy | None = None,
    ) -> AppendBatchResult:
        """Commit the fixed drought state row from one pinned drought-process event."""
        policy = expiry_policy or EcologyDroughtStateExpiryPolicy()
        stream_id = self.ecology_stream_id(region_ref=region_ref)
        if (
            command.principal_ref != self._PRINCIPAL
            or command.source_ref != self._PRINCIPAL
            or command.actor_ref != region_ref
        ):
            return self._rejected(command, "ecology_drought_state_authority_required")
        if command.payload.get("visibility_scope", "project") != "project":
            return self._rejected(command, "ecology_drought_state_privacy_scope_denied")
        digest = self._drought_state_application_digest(
            command=command,
            region_ref=region_ref,
            source_event_id=source_event_id,
            source_event_revision=source_event_revision,
            application=application,
            resistance=resistance,
            definition=definition,
            policy=policy,
        )
        existing = self.store.get_by_idempotency(self._PRINCIPAL, command.idempotency_key)
        if existing is not None and existing.committed:
            if self._committed_drought_state_application_digest(existing.committed_event_ids) == digest:
                return existing.model_copy(update={"idempotency_status": "duplicate_replayed"})
            return self._rejected(command, "idempotency_key_reused")
        try:
            source_event = self.store.get_event(source_event_id)
        except KeyError:
            return self._rejected(command, "ecology_drought_state_source_missing")
        if source_event.visibility_policy != "project":
            return self._rejected(command, "ecology_drought_state_source_privacy_denied")
        if (
            source_event.event_type != "gameplay.ecology.drought_process_advanced"
            or source_event.stream_id != stream_id
            or source_event.stream_revision != source_event_revision
            or source_event.payload.get("region_ref") != region_ref
        ):
            return self._rejected(command, "ecology_drought_state_source_invalid")
        latest_source = next(
            (
                event
                for event in reversed(self.store.read_stream(stream_id))
                if event.event_type == "gameplay.ecology.drought_process_advanced"
                and event.visibility_policy == "project"
                and event.payload.get("region_ref") == region_ref
            ),
            None,
        )
        if (
            latest_source is None
            or latest_source.event_id != source_event_id
            or latest_source.stream_revision != source_event_revision
        ):
            return self._rejected(command, "ecology_drought_state_source_stale")
        try:
            contract = SemanticRegistry.require_closed_state_owner_contract(
                effect_ref=application.effect_ref,
                state_ref=definition.state_ref,
            )
        except ValueError:
            return self._rejected(command, "ecology_drought_state_row_unregistered")
        if (
            contract.owner_ref != self._PRINCIPAL
            or contract.stream_pattern != "gameplay:ecology:{region_ref}"
            or contract.apply_event_type != "gameplay.ecology.drought_state_applied"
            or contract.opened_event_type != "gameplay.ecology.drought_state_obligation_opened"
            or contract.expired_event_type != "gameplay.ecology.drought_state_expired"
            or contract.settled_event_type != "gameplay.ecology.drought_state_obligation_settled"
            or contract.projection_scope != "project"
            or application.effect_ref != contract.effect_ref
            or resistance.effect_ref != contract.effect_ref
            or application.target_component_ref != region_ref
            or definition != contract.definition
        ):
            return self._rejected(command, "ecology_drought_state_row_unregistered")
        if command.expected_revisions != {stream_id: self.store.get_stream_head(stream_id)}:
            return self._rejected(command, "revision_conflict")
        if self._has_open_drought_state(region_ref=region_ref):
            return self._rejected(command, "ecology_drought_state_already_open")
        resolution = EffectLifecycleEvaluator().resolve(
            application,
            resistance=resistance,
            state=definition,
            existing_stacks=0,
        )
        if not resolution.accepted or resolution.expiry_obligation is None:
            return self._rejected(command, resolution.error_code or "ecology_drought_state_expiry_required")
        obligation = policy.build_obligation(
            region_ref=region_ref,
            source_event_id=source_event_id,
            due_tick=int(resolution.expiry_obligation["due_tick"]),
            expected_revision=self.store.get_stream_head(stream_id),
        )
        try:
            fragment = OwnerAuthorizedFragment(
                fragment_id=f"fragment:ecology:drought:apply:{region_ref}:{command.command_id}",
                owner_principal_ref=self._PRINCIPAL,
                source_rule_ref="ecology:drought-state:v1",
                expected_revisions={stream_id: self.store.get_stream_head(stream_id)},
                pinned_revisions={"ecology": self.store.get_stream_head(stream_id)},
                event_specs={
                    stream_id: (
                        (
                            "gameplay.ecology.drought_state_applied",
                            {
                                "region_ref": region_ref,
                                "source_event_id": source_event_id,
                                "source_event_revision": source_event_revision,
                                "effect_ref": application.effect_ref,
                                "state_ref": definition.state_ref,
                                "stacks": resolution.next_stacks,
                                "effective_magnitude": resolution.effective_magnitude,
                                "due_tick": obligation.due_tick,
                                "drought_state_application_digest": digest,
                            },
                        ),
                        (
                            "gameplay.ecology.drought_state_obligation_opened",
                            {
                                "obligation_id": obligation.obligation_id,
                                "due_tick": obligation.due_tick,
                                "policy_ref": policy.policy_ref,
                                "policy_revision": policy.policy_revision,
                                "region_ref": region_ref,
                                "source_event_id": source_event_id,
                                "source_event_revision": source_event_revision,
                            },
                        ),
                    )
                },
                event_visibility_policies={stream_id: ("project", "project")},
            )
            batch = build_multi_stream_atomic_event_batch_from_fragments(
                command_id=command.command_id,
                idempotency_principal_ref=self._PRINCIPAL,
                idempotency_key=command.idempotency_key,
                causation_id=command.causation_id,
                correlation_id=command.correlation_id,
                fragments=(fragment,),
            )
            batch = batch.model_copy(
                update={
                    "outbox_entries": [
                        GameplayOutboxEntry(
                            outbox_id=f"outbox:{event.event_id}",
                            transaction_id=batch.transaction_id,
                            event_id=event.event_id,
                            global_sequence=0,
                            topic="world.ecology.scoped_projection",
                            audience="project",
                            payload_projection={"region_ref": region_ref, "event_type": event.event_type},
                        )
                        for event in batch.events
                    ]
                },
                deep=True,
            )
        except ValueError as exc:
            return self._rejected(command, str(exc))
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:ecology-drought-state-expiry@1",
                contract_kind="lifecycle",
                owner_ref=self._PRINCIPAL,
                stream_ids=(stream_id,),
                event_types=tuple(event.event_type for event in batch.events),
                projection_scope="project",
            )
        except GovernedAuthorityContractError as error:
            return self._rejected(command, str(error))
        return self.store.append_batch(batch)

    def dispel_frost_crop_state(
        self,
        *,
        command: GameplayCommandEnvelope,
        hazard_ref: str,
        crop_ref: str,
        definition: StateDefinition,
    ) -> AppendBatchResult:
        """Cancel only the exact active frost state obligation on Ecology's stream."""
        projection = self.regional_projection(scope="authority")
        hazard = projection["hazards"].get(hazard_ref)
        crop = projection["crops"].get(crop_ref)
        if not isinstance(hazard, dict) or not isinstance(crop, dict):
            return self._rejected(command, "ecology_crop_state_source_missing")
        region_ref = hazard.get("region_ref")
        if not isinstance(region_ref, str) or region_ref != crop.get("region_ref"):
            return self._rejected(command, "ecology_crop_state_region_mismatch")
        stream_id = self.ecology_stream_id(region_ref=region_ref)
        if (
            command.principal_ref != self._PRINCIPAL
            or command.source_ref != self._PRINCIPAL
            or command.actor_ref != crop_ref
            or command.payload.get("visibility_scope") != "project"
            or command.payload.get("effect_ref") != "effect:ecology_frost_state_dispel"
            or hazard.get("privacy_scope") != "project"
        ):
            return self._rejected(command, "ecology_crop_state_action_invalid")
        try:
            contract = SemanticRegistry.require_closed_state_owner_contract(
                effect_ref="effect:frost", state_ref=definition.state_ref
            )
            lifecycle = SemanticRegistry.require_closed_lifecycle_owner_contract(
                effect_ref="effect:frost", state_ref=definition.state_ref
            )
        except ValueError:
            return self._rejected(command, "ecology_crop_state_action_unregistered")
        if (
            contract.owner_ref != self._PRINCIPAL
            or contract.stream_pattern != "gameplay:ecology:{region_ref}"
            or contract.definition != definition
            or not definition.dispel_allowed
            or "effect:ecology_frost_state_dispel" not in lifecycle.action_effect_refs
            or "gameplay.ecology.crop_state_dispelled" not in lifecycle.event_types
            or "gameplay.ecology.crop_state_obligation_cancelled" not in lifecycle.event_types
        ):
            return self._rejected(command, "ecology_crop_state_action_unregistered")
        policy = EcologyFrostCropStateExpiryPolicy()
        obligation_id = policy.obligation_id_for(region_ref=region_ref, crop_ref=crop_ref)
        digest = self._crop_state_action_digest(
            command=command,
            hazard_ref=hazard_ref,
            crop_ref=crop_ref,
            definition=definition,
            obligation_id=obligation_id,
        )
        existing = self.store.get_by_idempotency(self._PRINCIPAL, command.idempotency_key)
        if existing is not None and existing.committed:
            if self._committed_crop_state_action_digest(existing.committed_event_ids) == digest:
                return existing.model_copy(update={"idempotency_status": "duplicate_replayed"})
            return self._rejected(command, "idempotency_key_reused")
        if command.expected_revisions != {stream_id: self.store.get_stream_head(stream_id)}:
            return self._rejected(command, "revision_conflict")
        if not self._has_open_frost_crop_state(region_ref=region_ref, crop_ref=crop_ref):
            return self._rejected(command, "ecology_crop_state_action_source_not_open")
        if self._active_frost_crop_state_hazard_for(region_ref=region_ref, crop_ref=crop_ref) != hazard_ref:
            return self._rejected(command, "ecology_crop_state_action_source_not_open")
        try:
            fragment = OwnerAuthorizedFragment(
                fragment_id=f"fragment:ecology:frosted:dispel:{region_ref}:{crop_ref}:{command.command_id}",
                owner_principal_ref=self._PRINCIPAL,
                source_rule_ref="ecology:frost-crop-state-dispel:v1",
                expected_revisions={stream_id: self.store.get_stream_head(stream_id)},
                pinned_revisions={"ecology": self.store.get_stream_head(stream_id)},
                event_specs={
                    stream_id: (
                        (
                            "gameplay.ecology.crop_state_dispelled",
                            {
                                "obligation_id": obligation_id,
                                "region_ref": region_ref,
                                "crop_ref": crop_ref,
                                "hazard_ref": hazard_ref,
                                "effect_ref": "effect:frost",
                                "state_ref": definition.state_ref,
                                "crop_state_action_digest": digest,
                            },
                        ),
                        (
                            "gameplay.ecology.crop_state_obligation_cancelled",
                            {
                                "obligation_id": obligation_id,
                                "prior_state": "open",
                                "current_state": "cancelled",
                                "policy_ref": policy.policy_ref,
                                "policy_revision": policy.policy_revision,
                            },
                        ),
                    )
                },
                event_visibility_policies={stream_id: ("project", "project")},
            )
            batch = build_multi_stream_atomic_event_batch_from_fragments(
                command_id=command.command_id,
                idempotency_principal_ref=self._PRINCIPAL,
                idempotency_key=command.idempotency_key,
                causation_id=command.causation_id,
                correlation_id=command.correlation_id,
                fragments=(fragment,),
            )
            batch = batch.model_copy(
                update={
                    "outbox_entries": [
                        GameplayOutboxEntry(
                            outbox_id=f"outbox:{event.event_id}",
                            transaction_id=batch.transaction_id,
                            event_id=event.event_id,
                            global_sequence=0,
                            topic="world.ecology.scoped_projection",
                            audience="project",
                            payload_projection={
                                "region_ref": region_ref,
                                "crop_ref": crop_ref,
                                "event_type": event.event_type,
                            },
                        )
                        for event in batch.events
                    ]
                },
                deep=True,
            )
        except ValueError as exc:
            return self._rejected(command, str(exc))
        return self.store.append_batch(batch)

    @classmethod
    def build_frost_crop_state_fragment(
        cls,
        *,
        obligation: ScheduledObligation,
        region_ref: str,
        hazard_ref: str,
        crop_ref: str,
        expected_revision: int,
    ) -> OwnerAuthorizedFragment:
        stream_id = cls.ecology_stream_id(region_ref=region_ref)
        policy = EcologyFrostCropStateExpiryPolicy()
        if (
            obligation.owner_ref != cls._PRINCIPAL
            or obligation.status not in {"open", "due", "retry"}
            or obligation.expected_revisions != {stream_id: expected_revision}
            or obligation.obligation_id != policy.obligation_id_for(region_ref=region_ref, crop_ref=crop_ref)
            or policy.policy_ref not in obligation.source_refs
        ):
            raise ValueError("ecology_frost_crop_state_fragment_invalid")
        return OwnerAuthorizedFragment(
            fragment_id=f"fragment:ecology:frosted:expiry:{region_ref}:{crop_ref}:{obligation.due_tick}",
            owner_principal_ref=cls._PRINCIPAL,
            source_rule_ref="ecology:frost-crop-state-expiry:v1",
            expected_revisions={stream_id: expected_revision},
            pinned_revisions={"ecology_frost_crop_state_expiry": obligation.due_tick},
            event_specs={
                stream_id: (
                    (
                        "gameplay.ecology.crop_state_expired",
                        {
                            "obligation_id": obligation.obligation_id,
                            "region_ref": region_ref,
                            "crop_ref": crop_ref,
                            "hazard_ref": hazard_ref,
                            "state_ref": "state:frosted@1",
                            "due_tick": obligation.due_tick,
                        },
                    ),
                    (
                        "gameplay.ecology.crop_state_obligation_settled",
                        {
                            "obligation_id": obligation.obligation_id,
                            "prior_state": obligation.status,
                            "current_state": "settled",
                            "policy_ref": policy.policy_ref,
                            "policy_revision": obligation.policy_revision,
                        },
                    ),
                )
            },
            event_visibility_policies={stream_id: ("project", "project")},
        )

    def build_drought_state_fragment(
        self,
        *,
        obligation: ScheduledObligation,
        region_ref: str,
        expected_revision: int,
    ) -> OwnerAuthorizedFragment:
        stream_id = self.ecology_stream_id(region_ref=region_ref)
        policy = EcologyDroughtStateExpiryPolicy()
        opening_refs = tuple(
            source_ref
            for source_ref in obligation.source_refs
            if source_ref.startswith("opening_event:")
        )
        if (
            obligation.owner_ref != self._PRINCIPAL
            or obligation.status not in {"open", "due", "retry"}
            or obligation.expected_revisions != {stream_id: expected_revision}
            or obligation.obligation_id != policy.obligation_id_for(region_ref=region_ref)
            or policy.policy_ref not in obligation.source_refs
            or len(opening_refs) != 1
        ):
            raise ValueError("ecology_drought_state_fragment_invalid")
        try:
            opening_event = self.store.get_event(opening_refs[0].removeprefix("opening_event:"))
        except KeyError as exc:
            raise ValueError("ecology_drought_state_fragment_invalid") from exc
        opening_payload = opening_event.payload
        source_event_id = opening_payload.get("source_event_id")
        source_event_revision = opening_payload.get("source_event_revision")
        if (
            opening_event.event_type != "gameplay.ecology.drought_state_obligation_opened"
            or opening_event.visibility_policy != "project"
            or opening_event.stream_id != stream_id
            or opening_payload.get("obligation_id") != obligation.obligation_id
            or opening_payload.get("policy_ref") != policy.policy_ref
            or opening_payload.get("policy_revision") != obligation.policy_revision
            or opening_payload.get("region_ref") != region_ref
            or not isinstance(source_event_id, str)
            or not source_event_id
            or not isinstance(source_event_revision, int)
            or isinstance(source_event_revision, bool)
        ):
            raise ValueError("ecology_drought_state_fragment_invalid")
        try:
            source_event = self.store.get_event(source_event_id)
        except KeyError as exc:
            raise ValueError("ecology_drought_state_fragment_invalid") from exc
        if (
            source_event.event_type != "gameplay.ecology.drought_process_advanced"
            or source_event.visibility_policy != "project"
            or source_event.stream_id != stream_id
            or source_event.stream_revision != source_event_revision
            or source_event.payload.get("region_ref") != region_ref
        ):
            raise ValueError("ecology_drought_state_fragment_invalid")
        return OwnerAuthorizedFragment(
            fragment_id=f"fragment:ecology:drought:expiry:{region_ref}:{obligation.due_tick}",
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref="ecology:drought-state-expiry:v1",
            expected_revisions={stream_id: expected_revision},
            pinned_revisions={"ecology_drought_state_expiry": obligation.due_tick},
            event_specs={
                stream_id: (
                    (
                        "gameplay.ecology.drought_state_expired",
                        {
                            "obligation_id": obligation.obligation_id,
                            "region_ref": region_ref,
                            "source_event_id": source_event_id,
                            "state_ref": "state:drought@1",
                            "due_tick": obligation.due_tick,
                        },
                    ),
                    (
                        "gameplay.ecology.drought_state_obligation_settled",
                        {
                            "obligation_id": obligation.obligation_id,
                            "prior_state": obligation.status,
                            "current_state": "settled",
                            "policy_ref": policy.policy_ref,
                            "policy_revision": obligation.policy_revision,
                        },
                    ),
                )
            },
            event_visibility_policies={stream_id: ("project", "project")},
        )

    def crop_state_replay(self, *, checkpoint_at: int | None = None):
        replay = GameplayProjectionReplay(projector_id="infra-ecology-frost-crop-state", projector_version="1")
        events = self.store.read_events()
        if checkpoint_at is None:
            return replay.full_replay(events)
        checkpoint = replay.create_checkpoint(events[:checkpoint_at])
        return replay.checkpoint_plus_tail_replay(checkpoint, events[checkpoint_at:])

    def drought_state_replay(self, *, checkpoint_at: int | None = None):
        replay = GameplayProjectionReplay(projector_id="infra-ecology-drought-state", projector_version="1")
        events = self.store.read_events()
        if checkpoint_at is None:
            return replay.full_replay(events)
        checkpoint = replay.create_checkpoint(events[:checkpoint_at])
        return replay.checkpoint_plus_tail_replay(checkpoint, events[checkpoint_at:])

    def _has_open_frost_crop_state(self, *, region_ref: str, crop_ref: str) -> bool:
        obligation_id = EcologyFrostCropStateExpiryPolicy.obligation_id_for(region_ref=region_ref, crop_ref=crop_ref)
        opened = False
        for event in self.store.read_events():
            if event.payload.get("obligation_id") != obligation_id:
                continue
            if event.event_type == "gameplay.ecology.crop_state_obligation_opened":
                opened = True
            elif event.event_type in {"gameplay.ecology.crop_state_obligation_settled", "gameplay.ecology.crop_state_obligation_cancelled"}:
                opened = False
        return opened

    def _active_frost_crop_state_hazard_for(self, *, region_ref: str, crop_ref: str) -> str | None:
        obligation_id = EcologyFrostCropStateExpiryPolicy.obligation_id_for(region_ref=region_ref, crop_ref=crop_ref)
        active_hazard_ref: str | None = None
        for event in self.store.read_events():
            payload = event.payload
            if event.event_type == "gameplay.ecology.crop_state_applied" and (
                payload.get("region_ref") == region_ref and payload.get("crop_ref") == crop_ref
            ):
                hazard_ref = payload.get("hazard_ref")
                active_hazard_ref = hazard_ref if isinstance(hazard_ref, str) else None
            elif (
                payload.get("obligation_id") == obligation_id
                and event.event_type in {
                    "gameplay.ecology.crop_state_expired",
                    "gameplay.ecology.crop_state_obligation_settled",
                    "gameplay.ecology.crop_state_dispelled",
                    "gameplay.ecology.crop_state_obligation_cancelled",
                }
            ):
                active_hazard_ref = None
        return active_hazard_ref

    def _has_open_drought_state(self, *, region_ref: str) -> bool:
        obligation_id = EcologyDroughtStateExpiryPolicy.obligation_id_for(region_ref=region_ref)
        opened = False
        for event in self.store.read_events():
            if event.payload.get("obligation_id") != obligation_id:
                continue
            if event.event_type == "gameplay.ecology.drought_state_obligation_opened":
                opened = True
            elif event.event_type == "gameplay.ecology.drought_state_obligation_settled":
                opened = False
        return opened

    @staticmethod
    def _crop_state_action_digest(
        *,
        command: GameplayCommandEnvelope,
        hazard_ref: str,
        crop_ref: str,
        definition: StateDefinition,
        obligation_id: str,
    ) -> str:
        encoded = json.dumps(
            {
                "command": command.model_dump(mode="json"),
                "hazard_ref": hazard_ref,
                "crop_ref": crop_ref,
                "definition": definition.model_dump(mode="json"),
                "obligation_id": obligation_id,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        return "sha256:" + sha256(encoded).hexdigest()

    def _committed_crop_state_action_digest(self, event_ids: tuple[str, ...]) -> str | None:
        committed_ids = set(event_ids)
        for event in self.store.read_events():
            if event.event_id in committed_ids and event.event_type == "gameplay.ecology.crop_state_dispelled":
                digest = event.payload.get("crop_state_action_digest")
                return digest if isinstance(digest, str) else None
        return None

    @staticmethod
    def _crop_state_application_digest(
        *,
        command: GameplayCommandEnvelope,
        hazard_ref: str,
        crop_ref: str,
        application: EffectApplication,
        resistance: ResistanceProfile,
        definition: StateDefinition,
        policy: EcologyFrostCropStateExpiryPolicy,
    ) -> str:
        encoded = json.dumps(
            {
                "command": command.model_dump(mode="json"),
                "hazard_ref": hazard_ref,
                "crop_ref": crop_ref,
                "application": application.model_dump(mode="json"),
                "resistance": resistance.model_dump(mode="json"),
                "definition": definition.model_dump(mode="json"),
                "policy": policy.model_dump(mode="json"),
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        return "sha256:" + sha256(encoded).hexdigest()

    def _committed_crop_state_application_digest(self, event_ids: tuple[str, ...]) -> str | None:
        committed_ids = set(event_ids)
        for event in self.store.read_events():
            if event.event_id in committed_ids and event.event_type == "gameplay.ecology.crop_state_applied":
                digest = event.payload.get("crop_state_application_digest")
                return digest if isinstance(digest, str) else None
        return None

    @staticmethod
    def _drought_state_application_digest(
        *,
        command: GameplayCommandEnvelope,
        region_ref: str,
        source_event_id: str,
        source_event_revision: int,
        application: EffectApplication,
        resistance: ResistanceProfile,
        definition: StateDefinition,
        policy: EcologyDroughtStateExpiryPolicy,
    ) -> str:
        encoded = json.dumps(
            {
                "command": command.model_dump(mode="json"),
                "region_ref": region_ref,
                "source_event_id": source_event_id,
                "source_event_revision": source_event_revision,
                "application": application.model_dump(mode="json"),
                "resistance": resistance.model_dump(mode="json"),
                "definition": definition.model_dump(mode="json"),
                "policy": policy.model_dump(mode="json"),
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        return "sha256:" + sha256(encoded).hexdigest()

    def _committed_drought_state_application_digest(self, event_ids: tuple[str, ...]) -> str | None:
        committed_ids = set(event_ids)
        for event in self.store.read_events():
            if event.event_id in committed_ids and event.event_type == "gameplay.ecology.drought_state_applied":
                digest = event.payload.get("drought_state_application_digest")
                return digest if isinstance(digest, str) else None
        return None

    def record_resource(
        self,
        *,
        envelope: GameplayCommandEnvelope,
        resource: ResourceNode,
    ) -> AppendBatchResult:
        return self.record_record(envelope=envelope, record_kind="resource", record=resource)

    def record_record(
        self,
        *,
        envelope: GameplayCommandEnvelope,
        record_kind: Literal["region", "environment", "resource", "crop", "hazard"],
        record: EcologyRecord,
    ) -> AppendBatchResult:
        record_ref = self._record_ref(record_kind=record_kind, record=record)
        region_ref = getattr(record, "region_ref", "")
        if not isinstance(region_ref, str) or not region_ref or not record_ref:
            return self._rejected(envelope, "ecology_record_invalid")
        stream_id = self.ecology_stream_id(region_ref=region_ref)
        if envelope.principal_ref != self._PRINCIPAL or envelope.source_ref != self._PRINCIPAL:
            return self._rejected(envelope, "ecology_authority_required")
        if envelope.expected_revisions != {stream_id: self.store.get_stream_head(stream_id)}:
            return self._rejected(envelope, "revision_conflict")
        collection = self._collections()[record_kind]
        current = self.regional_projection(scope="authority")[collection].get(record_ref)
        if current is None and record.revision != 0:
            return self._rejected(envelope, "ecology_record_revision_conflict")
        if current is not None and record.revision != int(current["revision"]) + 1:
            return self._rejected(envelope, "ecology_record_revision_conflict")
        if record_kind == "hazard" and isinstance(record, HazardRecord) and record.privacy_scope == "private_evidence":
            return self._rejected(envelope, "ecology_privacy_scope_denied")
        try:
            visibility_scope = self._visibility_scope(envelope)
            fragment = OwnerAuthorizedFragment(
                fragment_id=f"fragment:ecology:record:{record_kind}:{record_ref}:{envelope.command_id}",
                owner_principal_ref=self._PRINCIPAL,
                source_rule_ref=f"ecology:{record_kind}-record:v1",
                expected_revisions=dict(envelope.expected_revisions),
                pinned_revisions={record_kind: record.revision},
                event_specs={
                    stream_id: (
                        (
                            f"gameplay.ecology.{record_kind}.recorded",
                            {
                                "record_ref": record_ref,
                                "record": record.model_dump(mode="json"),
                                "source_revision": record.revision,
                                "causal_parent_refs": [],
                            },
                        ),
                    )
                },
                event_visibility_policies={stream_id: (visibility_scope,)},
            )
            batch = build_multi_stream_atomic_event_batch_from_fragments(
                command_id=envelope.command_id,
                idempotency_principal_ref=envelope.principal_ref,
                idempotency_key=envelope.idempotency_key,
                causation_id=envelope.causation_id,
                correlation_id=envelope.correlation_id,
                fragments=(fragment,),
            )
            event = batch.events[0]
            batch = batch.model_copy(
                update={
                    "outbox_entries": [
                        GameplayOutboxEntry(
                            outbox_id=f"outbox:{event.event_id}",
                            transaction_id=batch.transaction_id,
                            event_id=event.event_id,
                            global_sequence=0,
                            topic="world.ecology.scoped_projection",
                            audience=event.visibility_policy,
                            payload_projection={"region_ref": region_ref, "record_ref": record_ref, "event_type": event.event_type},
                        )
                    ]
                },
                deep=True,
            )
        except ValueError as exc:
            return self._rejected(envelope, str(exc))
        return self.store.append_batch(batch)

    @staticmethod
    def _visibility_scope(envelope: GameplayCommandEnvelope) -> Literal["project", "authority_only"]:
        scope = envelope.payload.get("visibility_scope", "project")
        if scope not in {"project", "authority_only"}:
            raise ValueError("ecology_visibility_scope_unsupported")
        return scope

    @staticmethod
    def _collections() -> dict[str, str]:
        return {
            "region": "regions",
            "environment": "environments",
            "resource": "resources",
            "crop": "crops",
            "hazard": "hazards",
        }

    @staticmethod
    def _record_ref(*, record_kind: str, record: EcologyRecord) -> str:
        field = {
            "region": "region_ref",
            "environment": "region_ref",
            "resource": "node_ref",
            "crop": "crop_ref",
            "hazard": "hazard_ref",
        }.get(record_kind)
        value = getattr(record, field, "") if field is not None else ""
        return value if isinstance(value, str) else ""

    def retire_record(
        self,
        *,
        envelope: GameplayCommandEnvelope,
        region_ref: str,
        record_kind: Literal["region", "environment", "resource", "crop", "hazard"],
        record_ref: str,
    ) -> AppendBatchResult:
        existing = self.store.get_by_idempotency(envelope.principal_ref, envelope.idempotency_key)
        if existing is not None:
            return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
        collection = self._collections().get(record_kind)
        if collection is None:
            return self._rejected(envelope, "ecology_record_kind_unsupported")
        if envelope.principal_ref != self._PRINCIPAL or envelope.source_ref != self._PRINCIPAL:
            return self._rejected(envelope, "ecology_authority_required")
        stream_id = self.ecology_stream_id(region_ref=region_ref)
        if envelope.expected_revisions != {stream_id: self.store.get_stream_head(stream_id)}:
            return self._rejected(envelope, "revision_conflict")
        record = self.regional_projection(scope="authority")[collection].get(record_ref)
        if record is None:
            return self._rejected(envelope, "ecology_record_missing")
        try:
            fragment = OwnerAuthorizedFragment(
                fragment_id=f"fragment:ecology:retire:{record_kind}:{record_ref}:{envelope.command_id}",
                owner_principal_ref=self._PRINCIPAL,
                source_rule_ref="ecology:regional-retirement:v1",
                expected_revisions=dict(envelope.expected_revisions),
                pinned_revisions={"record": int(record["revision"])},
                event_specs={
                    stream_id: (
                        (
                            f"gameplay.ecology.{record_kind}.retired",
                            {
                                "record_ref": record_ref,
                                "source_revision": int(record["revision"]),
                                "causal_parent_refs": list(record.get("causal_parent_refs", ())),
                            },
                        ),
                    )
                },
                event_visibility_policies={stream_id: ("project",)},
            )
            batch = build_multi_stream_atomic_event_batch_from_fragments(
                command_id=envelope.command_id,
                idempotency_principal_ref=envelope.principal_ref,
                idempotency_key=envelope.idempotency_key,
                causation_id=envelope.causation_id,
                correlation_id=envelope.correlation_id,
                fragments=(fragment,),
            )
            event = batch.events[0]
            batch = batch.model_copy(
                update={
                    "outbox_entries": [
                        GameplayOutboxEntry(
                            outbox_id=f"outbox:{event.event_id}",
                            transaction_id=batch.transaction_id,
                            event_id=event.event_id,
                            global_sequence=0,
                            topic="world.ecology.scoped_projection",
                            audience=event.visibility_policy,
                            payload_projection={"region_ref": region_ref, "record_ref": record_ref, "event_type": event.event_type},
                        )
                    ]
                },
                deep=True,
            )
        except ValueError as exc:
            return self._rejected(envelope, str(exc))
        return self.store.append_batch(batch)

    @classmethod
    def _record_region_bundle_fragment(
        cls,
        *,
        envelope: GameplayCommandEnvelope,
        stream_id: str,
        region: EnvironmentRegion,
        environment: EnvironmentalState,
        resource: ResourceNode,
        crop: CropRecord,
        hazard: HazardRecord,
        visibility_scope: Literal["project", "authority_only"],
    ) -> OwnerAuthorizedFragment:
        record_specs = (
            ("region", region.region_ref, region),
            ("environment", region.region_ref, environment),
            ("resource", resource.node_ref, resource),
            ("crop", crop.crop_ref, crop),
            ("hazard", hazard.hazard_ref, hazard),
        )
        return OwnerAuthorizedFragment(
            fragment_id=f"fragment:ecology:record:{region.region_ref}:{envelope.command_id}",
            owner_principal_ref=cls._PRINCIPAL,
            source_rule_ref="ecology:regional-records:v1",
            expected_revisions=dict(envelope.expected_revisions),
            pinned_revisions={"region": region.revision},
            event_specs={
                stream_id: tuple(
                    (
                        f"gameplay.ecology.{record_kind}.recorded",
                        {
                            "record_ref": record_ref,
                            "record": record.model_dump(mode="json"),
                            "source_revision": record.revision,
                            "causal_parent_refs": list(hazard.causal_parent_refs),
                        },
                    )
                    for record_kind, record_ref, record in record_specs
                )
            },
            event_visibility_policies={stream_id: tuple(visibility_scope for _ in record_specs)},
        )

    @staticmethod
    def _rejected(envelope: GameplayCommandEnvelope, error_code: str) -> AppendBatchResult:
        return AppendBatchResult(
            committed=False,
            transaction_id=envelope.transaction_id or f"transaction:{envelope.command_id}",
            command_id=envelope.command_id,
            idempotency_status="rejected",
            failure={
                "error_code": error_code,
                "message": error_code,
                "failed_stage": "ecology_admission",
            },
        )


    def settle_frost(self, *, hazard: HazardRecord, crop: CropRecord, resistance: ResistanceProfile) -> HazardSettlementResult:
        existing = self.store.get_by_idempotency("authority:ecology", hazard.idempotency_key)
        if existing is not None and existing.committed:
            return HazardSettlementResult(committed=True, committed_event_ids=tuple(existing.committed_event_ids), idempotency_status="duplicate_replayed")
        if hazard.effect_ref != "effect:frost" or resistance.effect_ref != hazard.effect_ref:
            return HazardSettlementResult(committed=False, error_code="hazard_effect_unsupported")
        if hazard.privacy_scope == "private_evidence":
            return HazardSettlementResult(committed=False, error_code="hazard_privacy_scope_denied")
        if hazard.chain_depth >= hazard.chain_budget:
            return HazardSettlementResult(committed=False, error_code="hazard_chain_budget_exhausted")
        if self.store.get_stream_head(crop.crop_ref) != crop.revision:
            return HazardSettlementResult(committed=False, error_code="revision_conflict")
        try:
            self.registry.assign_tag(TagAssignment(entity_ref=crop.crop_ref, tag_ref="type:crop", source_ref="ecology", revision=crop.revision))
        except ValueError:
            pass
        snapshot = self.registry.build_snapshot(crop.crop_ref, policy_context_ref=hazard.policy_revision, source_revision_vector={"semantic": crop.revision, "rule": crop.revision})
        result = self.semantic_authority.settle_lifecycle(
            SemanticEffectCommand(
                command_id=hazard.hazard_ref,
                idempotency_key=hazard.idempotency_key,
                principal_ref="authority:ecology",
                owner_ref=crop.owner_ref,
                stream_id=crop.crop_ref,
                expected_revision=crop.revision,
                effect_ref=hazard.effect_ref,
                target_ref=crop.crop_ref,
                semantic_snapshot=snapshot,
                expected_snapshot_digest=snapshot.digest,
                causal_parent_refs=hazard.causal_parent_refs,
                evidence_refs=(f"hazard:{hazard.hazard_ref}",),
                privacy_scope=hazard.privacy_scope,
            ),
            application=EffectApplication(effect_ref=hazard.effect_ref, target_component_ref=crop.crop_ref, magnitude=hazard.severity_basis_points // 100, stack_key=hazard.effect_ref, expires_at_tick=hazard.due_tick + hazard.duration_ticks, causal_chain_id=hazard.hazard_ref),
            resistance=resistance,
            state=StateDefinition(state_ref="state:frosted", stack_policy="refresh", stack_limit=1, expiry_policy="scheduled"),
            existing_stacks=0,
            lifecycle_payload={
                "hazard_ref": hazard.hazard_ref,
                "region_ref": hazard.region_ref,
                "plot_ref": crop.plot_ref,
                "due_tick": hazard.due_tick,
                "semantic_revision": hazard.semantic_revision,
                "rule_revision": hazard.rule_revision,
                "policy_revision": hazard.policy_revision,
                "hazard_privacy_scope": hazard.privacy_scope,
            },
        )
        return HazardSettlementResult(committed=result.committed, error_code=result.failure.error_code if result.failure else None, committed_event_ids=tuple(result.committed_event_ids), idempotency_status=result.idempotency_status)

    def frost_source(
        self, *, hazard_ref: str, scope: Literal["public", "authority"] = "public"
    ) -> FrostSourceResult:
        for event in reversed(self.store.read_events()):
            payload = event.payload
            if (
                event.event_type == "semantic.effect.settled"
                and payload.get("effect_ref") == "effect:frost"
                and payload.get("hazard_ref") == hazard_ref
            ):
                plot_ref = payload.get("plot_ref")
                if not isinstance(plot_ref, str) or not plot_ref:
                    return FrostSourceResult(accepted=False, error_code="frost_source_plot_missing")
                privacy_scope = str(payload.get("hazard_privacy_scope", "project"))
                if privacy_scope not in {"project", "authority_only"}:
                    return FrostSourceResult(accepted=False, error_code="frost_source_privacy_unsupported")
                evidence_refs = tuple(str(ref) for ref in payload.get("evidence_refs", ()))
                return FrostSourceResult(
                    accepted=True,
                    source=FrostPropagationSource(
                        hazard_ref=hazard_ref,
                        crop_ref=str(payload["entity_ref"]),
                        plot_ref=plot_ref,
                        region_ref=str(payload["region_ref"]),
                        source_event_id=event.event_id,
                        source_stream_revision=event.stream_revision,
                        due_tick=int(payload["due_tick"]),
                        semantic_revision=str(payload["semantic_revision"]),
                        rule_revision=str(payload["rule_revision"]),
                        policy_revision=str(payload["policy_revision"]),
                        causal_parent_refs=tuple(str(ref) for ref in payload.get("causal_parent_refs", ())),
                        evidence_refs=evidence_refs if scope == "authority" else (),
                        privacy_scope=privacy_scope,
                    ),
                )
        return FrostSourceResult(accepted=False, error_code="frost_source_missing")

    def regional_projection(self, *, scope: Literal["public", "authority"] = "public") -> dict[str, object]:
        records: dict[str, dict[str, dict[str, object]]] = {
            "regions": {},
            "environments": {},
            "resources": {},
            "crops": {},
            "hazards": {},
            "processes": {},
            "drought_processes": {},
            "frontiers": {},
            "frontier_edges": [],
        }
        kinds = {
            "region": "regions",
            "environment": "environments",
            "resource": "resources",
            "crop": "crops",
            "hazard": "hazards",
        }
        for event in self.store.read_events():
            prefix = "gameplay.ecology."
            if scope == "public" and event.visibility_policy != "project":
                continue
            if event.event_type == "gameplay.ecology.weather_front.propagated":
                source_region_ref = event.payload.get("source_region_ref")
                target_region_ref = event.payload.get("target_region_ref")
                weather_ref = event.payload.get("weather_ref")
                tick = event.payload.get("tick")
                policy_ref = event.payload.get("policy_ref")
                if all(isinstance(value, str) and value for value in (source_region_ref, target_region_ref, weather_ref, policy_ref)) and isinstance(tick, int):
                    frontier: dict[str, object] = {
                        "target_region_ref": target_region_ref,
                        "weather_ref": weather_ref,
                        "tick": tick,
                        "policy_ref": policy_ref,
                    }
                    if scope == "authority":
                        frontier["policy_revision"] = str(event.payload.get("policy_revision", ""))
                        frontier["source_region_revision"] = int(event.payload.get("source_region_revision", 0))
                        frontier["target_region_revision"] = int(event.payload.get("target_region_revision", 0))
                        frontier["source_environment_revision"] = int(event.payload.get("source_environment_revision", 0))
                        frontier["target_environment_revision"] = int(event.payload.get("target_environment_revision", 0))
                        if isinstance(event.payload.get("wave_fanout_digest"), str):
                            frontier["wave_fanout_digest"] = event.payload["wave_fanout_digest"]
                            frontier["chain_depth"] = int(event.payload.get("chain_depth", 0))
                    records["frontiers"][source_region_ref] = frontier
                    records["frontier_edges"].append({"source_region_ref": source_region_ref, **frontier})
                continue
            if event.event_type == "gameplay.ecology.seasonal_process_advanced":
                region_ref = event.payload.get("region_ref")
                last_tick = event.payload.get("last_tick")
                policy_ref = event.payload.get("policy_ref")
                if isinstance(region_ref, str) and isinstance(last_tick, int) and isinstance(policy_ref, str):
                    process: dict[str, object] = {"last_tick": last_tick, "policy_ref": policy_ref}
                    if scope == "authority":
                        process["policy_revision"] = str(event.payload.get("policy_revision", ""))
                        process["elapsed_ticks"] = int(event.payload.get("elapsed_ticks", 0))
                    records["processes"][region_ref] = process
                continue
            if event.event_type == "gameplay.ecology.drought_process_advanced":
                region_ref = event.payload.get("region_ref")
                last_tick = event.payload.get("last_tick")
                policy_ref = event.payload.get("policy_ref")
                if isinstance(region_ref, str) and isinstance(last_tick, int) and isinstance(policy_ref, str):
                    process: dict[str, object] = {"last_tick": last_tick, "policy_ref": policy_ref}
                    if scope == "authority":
                        process["policy_revision"] = str(event.payload.get("policy_revision", ""))
                        process["elapsed_ticks"] = int(event.payload.get("elapsed_ticks", 0))
                    records["drought_processes"][region_ref] = process
                continue
            suffix = ".recorded"
            if not event.event_type.startswith(prefix):
                continue
            suffix = ".recorded"
            retired_suffix = ".retired"
            if event.event_type.endswith(retired_suffix):
                record_kind = event.event_type.removeprefix(prefix).removesuffix(retired_suffix)
                collection = kinds.get(record_kind)
                record_ref = event.payload.get("record_ref")
                if collection is not None and isinstance(record_ref, str):
                    records[collection].pop(record_ref, None)
                continue
            if not event.event_type.endswith(suffix):
                continue
            record_kind = event.event_type.removeprefix(prefix).removesuffix(suffix)
            collection = kinds.get(record_kind)
            record_ref = event.payload.get("record_ref")
            record = event.payload.get("record")
            if collection is None or not isinstance(record_ref, str) or not isinstance(record, dict):
                continue
            view = dict(record)
            if scope == "authority":
                view["causal_parent_refs"] = list(event.payload.get("causal_parent_refs", ()))
            else:
                for key in ("causal_parent_refs", "idempotency_key", "evidence_refs"):
                    view.pop(key, None)
            records[collection][record_ref] = view
        return records

    def advance_seasonal_process(
        self,
        *,
        envelope: GameplayCommandEnvelope,
        policy: EcologySeasonalProcessPolicy,
        region_ref: str,
    ) -> AppendBatchResult:
        """Advance one ecology region through one existing-store atomic batch."""
        existing = self.store.get_by_idempotency(envelope.principal_ref, envelope.idempotency_key)
        if existing is not None:
            return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
        if envelope.principal_ref != self._PRINCIPAL or envelope.source_ref != self._PRINCIPAL:
            return self._rejected(envelope, "ecology_authority_required")
        try:
            visibility_scope = self._visibility_scope(envelope)
        except ValueError as exc:
            return self._rejected(envelope, str(exc))
        if visibility_scope != "project":
            return self._rejected(envelope, "ecology_process_privacy_scope_denied")
        stream_id = self.ecology_stream_id(region_ref=region_ref)
        if envelope.expected_revisions != {stream_id: self.store.get_stream_head(stream_id)}:
            return self._rejected(envelope, "revision_conflict")
        tick = envelope.payload.get("tick")
        if not isinstance(tick, int) or isinstance(tick, bool) or tick < 0:
            return self._rejected(envelope, "ecology_process_tick_invalid")
        projection = self.regional_projection(scope="authority")
        environment = projection["environments"].get(region_ref)
        if not isinstance(environment, dict):
            return self._rejected(envelope, "ecology_process_environment_missing")
        process = projection["processes"].get(region_ref, {})
        last_tick = int(process.get("last_tick", 0)) if isinstance(process, dict) else 0
        elapsed = tick - last_tick
        if elapsed <= 0 or elapsed > policy.max_elapsed_ticks:
            return self._rejected(envelope, "ecology_process_tick_out_of_range")
        resources = [record for record in projection["resources"].values() if record.get("region_ref") == region_ref]
        crops = [record for record in projection["crops"].values() if record.get("region_ref") == region_ref]
        if not resources or not crops:
            return self._rejected(envelope, "ecology_process_records_missing")
        def canonical_record(record: dict[str, object]) -> dict[str, object]:
            return {key: value for key, value in record.items() if key not in {"causal_parent_refs", "idempotency_key", "evidence_refs"}}

        next_environment = EnvironmentalState.model_validate(canonical_record(environment)).model_copy(
            update={
                "weather_ref": "weather:rain" if environment["weather_ref"] == "weather:clear" else "weather:clear",
                "moisture_basis_points": min(10_000, int(environment["moisture_basis_points"]) + policy.moisture_per_tick * elapsed),
                "revision": int(environment["revision"]) + 1,
            }
        )
        next_resources = tuple(
            ResourceNode.model_validate(canonical_record(record)).model_copy(
                update={"quantity": int(record["quantity"]) + int(record["regeneration_per_tick"]) * elapsed, "revision": int(record["revision"]) + 1}
            )
            for record in resources
        )
        next_crops = tuple(
            CropRecord.model_validate(canonical_record(record)).model_copy(
                update={"growth_basis_points": min(10_000, int(record["growth_basis_points"]) + policy.crop_growth_per_tick * elapsed), "revision": int(record["revision"]) + 1}
            )
            for record in crops
        )
        event_specs: list[tuple[str, dict[str, object]]] = [
            ("gameplay.ecology.environment.recorded", {"record_ref": region_ref, "record": next_environment.model_dump(mode="json"), "source_revision": next_environment.revision, "causal_parent_refs": []}),
        ]
        event_specs.extend(
            ("gameplay.ecology.resource.recorded", {"record_ref": record.node_ref, "record": record.model_dump(mode="json"), "source_revision": record.revision, "causal_parent_refs": []})
            for record in sorted(next_resources, key=lambda value: value.node_ref)
        )
        event_specs.extend(
            ("gameplay.ecology.crop.recorded", {"record_ref": record.crop_ref, "record": record.model_dump(mode="json"), "source_revision": record.revision, "causal_parent_refs": []})
            for record in sorted(next_crops, key=lambda value: value.crop_ref)
        )
        event_specs.append(
            ("gameplay.ecology.seasonal_process_advanced", {"region_ref": region_ref, "last_tick": tick, "elapsed_ticks": elapsed, "policy_ref": policy.policy_ref, "policy_revision": policy.policy_revision})
        )
        fragment = OwnerAuthorizedFragment(
            fragment_id=f"fragment:ecology:seasonal-process:{region_ref}:{tick}",
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref=f"ecology:seasonal-process:{policy.policy_ref}:{policy.policy_revision}",
            expected_revisions=dict(envelope.expected_revisions),
            pinned_revisions={"process_last_tick": last_tick, "policy": int(policy.policy_revision) if policy.policy_revision.isdigit() else 0},
            event_specs={stream_id: tuple(event_specs)},
            event_visibility_policies={stream_id: tuple("project" for _ in event_specs)},
        )
        try:
            batch = build_multi_stream_atomic_event_batch_from_fragments(
                command_id=envelope.command_id,
                idempotency_principal_ref=envelope.principal_ref,
                idempotency_key=envelope.idempotency_key,
                causation_id=envelope.causation_id,
                correlation_id=envelope.correlation_id,
                fragments=(fragment,),
            )
        except ValueError as exc:
            return self._rejected(envelope, str(exc))
        batch = batch.model_copy(
            update={
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}", transaction_id=batch.transaction_id,
                        event_id=event.event_id, global_sequence=0, topic="world.ecology.scoped_projection",
                        audience="project", payload_projection={"region_ref": region_ref, "event_type": event.event_type},
                    )
                    for event in batch.events
                ]
            },
            deep=True,
        )
        return self.store.append_batch(batch)

    def advance_drought_process(
        self,
        *,
        envelope: GameplayCommandEnvelope,
        policy: EcologyDroughtProcessPolicy,
        region_ref: str,
    ) -> AppendBatchResult:
        """Apply one bounded drought correction through the existing Ecology stream."""
        existing = self.store.get_by_idempotency(envelope.principal_ref, envelope.idempotency_key)
        if existing is not None:
            return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
        if envelope.principal_ref != self._PRINCIPAL or envelope.source_ref != self._PRINCIPAL:
            return self._rejected(envelope, "ecology_authority_required")
        try:
            visibility_scope = self._visibility_scope(envelope)
        except ValueError as exc:
            return self._rejected(envelope, str(exc))
        if visibility_scope != "project":
            return self._rejected(envelope, "ecology_process_privacy_scope_denied")
        stream_id = self.ecology_stream_id(region_ref=region_ref)
        if envelope.expected_revisions != {stream_id: self.store.get_stream_head(stream_id)}:
            return self._rejected(envelope, "revision_conflict")
        tick = envelope.payload.get("tick")
        if not isinstance(tick, int) or isinstance(tick, bool) or tick < 0:
            return self._rejected(envelope, "ecology_process_tick_invalid")
        projection = self.regional_projection(scope="authority")
        environment = projection["environments"].get(region_ref)
        last = projection["drought_processes"].get(region_ref, {})
        last_tick = int(last.get("last_tick", 0)) if isinstance(last, dict) else 0
        elapsed = tick - last_tick
        if not isinstance(environment, dict) or elapsed <= 0 or elapsed > policy.max_elapsed_ticks:
            return self._rejected(envelope, "ecology_drought_process_invalid")
        resources = [record for record in projection["resources"].values() if record.get("region_ref") == region_ref]
        crops = [record for record in projection["crops"].values() if record.get("region_ref") == region_ref]
        if not resources or not crops:
            return self._rejected(envelope, "ecology_process_records_missing")
        def canonical(record: dict[str, object]) -> dict[str, object]:
            return {key: value for key, value in record.items() if key not in {"causal_parent_refs", "idempotency_key", "evidence_refs"}}
        next_environment = EnvironmentalState.model_validate(canonical(environment)).model_copy(update={"moisture_basis_points": max(0, int(environment["moisture_basis_points"]) - policy.moisture_loss_per_tick * elapsed), "revision": int(environment["revision"]) + 1})
        next_resources = tuple(ResourceNode.model_validate(canonical(record)).model_copy(update={"quantity": max(0, int(record["quantity"]) - policy.resource_loss_per_tick * elapsed), "revision": int(record["revision"]) + 1}) for record in resources)
        next_crops = tuple(CropRecord.model_validate(canonical(record)).model_copy(update={"health": max(0, int(record["health"]) - policy.crop_health_loss_per_tick * elapsed), "revision": int(record["revision"]) + 1}) for record in crops)
        specs: list[tuple[str, dict[str, object]]] = [("gameplay.ecology.environment.recorded", {"record_ref": region_ref, "record": next_environment.model_dump(mode="json"), "source_revision": next_environment.revision, "causal_parent_refs": []})]
        specs.extend(("gameplay.ecology.resource.recorded", {"record_ref": value.node_ref, "record": value.model_dump(mode="json"), "source_revision": value.revision, "causal_parent_refs": []}) for value in sorted(next_resources, key=lambda value: value.node_ref))
        specs.extend(("gameplay.ecology.crop.recorded", {"record_ref": value.crop_ref, "record": value.model_dump(mode="json"), "source_revision": value.revision, "causal_parent_refs": []}) for value in sorted(next_crops, key=lambda value: value.crop_ref))
        specs.append(("gameplay.ecology.drought_process_advanced", {"region_ref": region_ref, "last_tick": tick, "elapsed_ticks": elapsed, "policy_ref": policy.policy_ref, "policy_revision": policy.policy_revision}))
        fragment = OwnerAuthorizedFragment(fragment_id=f"fragment:ecology:drought-process:{region_ref}:{tick}", owner_principal_ref=self._PRINCIPAL, source_rule_ref=f"ecology:drought-process:{policy.policy_ref}:{policy.policy_revision}", expected_revisions=dict(envelope.expected_revisions), pinned_revisions={"drought_last_tick": last_tick, "policy": 1}, event_specs={stream_id: tuple(specs)}, event_visibility_policies={stream_id: tuple("project" for _ in specs)})
        try:
            batch = build_multi_stream_atomic_event_batch_from_fragments(command_id=envelope.command_id, idempotency_principal_ref=envelope.principal_ref, idempotency_key=envelope.idempotency_key, causation_id=envelope.causation_id, correlation_id=envelope.correlation_id, fragments=(fragment,))
        except ValueError as exc:
            return self._rejected(envelope, str(exc))
        batch = batch.model_copy(update={"outbox_entries": [GameplayOutboxEntry(outbox_id=f"outbox:{event.event_id}", transaction_id=batch.transaction_id, event_id=event.event_id, global_sequence=0, topic="world.ecology.scoped_projection", audience="project", payload_projection={"region_ref": region_ref, "event_type": event.event_type}) for event in batch.events]}, deep=True)
        return self.store.append_batch(batch)

    def propagate_weather_front(
        self,
        *,
        envelope: GameplayCommandEnvelope,
        policy: EcologyWeatherFrontPropagationPolicy,
        source_region_ref: str,
        target_region_ref: str,
    ) -> AppendBatchResult:
        """Commit one ecology-owned regional weather step through one batch."""
        existing = self.store.get_by_idempotency(envelope.principal_ref, envelope.idempotency_key)
        if existing is not None:
            return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
        if envelope.principal_ref != self._PRINCIPAL or envelope.source_ref != self._PRINCIPAL:
            return self._rejected(envelope, "ecology_authority_required")
        try:
            visibility_scope = self._visibility_scope(envelope)
        except ValueError as exc:
            return self._rejected(envelope, str(exc))
        if visibility_scope != "project":
            return self._rejected(envelope, "ecology_front_privacy_scope_denied")
        if source_region_ref == target_region_ref:
            return self._rejected(envelope, "ecology_front_adjacency_denied")
        source_stream = self.ecology_stream_id(region_ref=source_region_ref)
        target_stream = self.ecology_stream_id(region_ref=target_region_ref)
        expected_revisions = {
            source_stream: self.store.get_stream_head(source_stream),
            target_stream: self.store.get_stream_head(target_stream),
        }
        if envelope.expected_revisions != expected_revisions:
            return self._rejected(envelope, "revision_conflict")
        tick = envelope.payload.get("tick")
        if not isinstance(tick, int) or isinstance(tick, bool) or tick < 0:
            return self._rejected(envelope, "ecology_front_tick_invalid")
        projection = self.regional_projection(scope="authority")
        source_region = projection["regions"].get(source_region_ref)
        target_region = projection["regions"].get(target_region_ref)
        source_environment = projection["environments"].get(source_region_ref)
        target_environment = projection["environments"].get(target_region_ref)
        if not all(isinstance(value, dict) for value in (source_region, target_region, source_environment, target_environment)):
            return self._rejected(envelope, "ecology_front_records_missing")
        if target_region_ref not in tuple(source_region.get("neighbor_region_refs", ())) or source_region_ref not in tuple(target_region.get("neighbor_region_refs", ())):
            return self._rejected(envelope, "ecology_front_adjacency_denied")

        def canonical_record(record: dict[str, object]) -> dict[str, object]:
            return {key: value for key, value in record.items() if key not in {"causal_parent_refs", "idempotency_key", "evidence_refs"}}

        next_environment = EnvironmentalState.model_validate(canonical_record(target_environment)).model_copy(
            update={
                "weather_ref": str(source_environment["weather_ref"]),
                "revision": int(target_environment["revision"]) + 1,
            }
        )
        frontier_payload = {
            "source_region_ref": source_region_ref,
            "target_region_ref": target_region_ref,
            "weather_ref": str(source_environment["weather_ref"]),
            "tick": tick,
            "policy_ref": policy.policy_ref,
            "policy_revision": policy.policy_revision,
            "chain_depth": 1,
            "chain_budget": policy.max_chain_depth,
            "source_region_revision": int(source_region["revision"]),
            "target_region_revision": int(target_region["revision"]),
            "source_environment_revision": int(source_environment["revision"]),
            "target_environment_revision": int(target_environment["revision"]),
        }
        source_fragment = OwnerAuthorizedFragment(
            fragment_id=f"fragment:ecology:weather-front:source:{source_region_ref}:{target_region_ref}:{tick}",
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref=f"ecology:weather-front:{policy.policy_ref}:{policy.policy_revision}",
            expected_revisions={source_stream: expected_revisions[source_stream]},
            pinned_revisions={
                "source_region": int(source_region["revision"]),
                "source_environment": int(source_environment["revision"]),
                "policy": 1,
            },
            event_specs={source_stream: (("gameplay.ecology.weather_front.propagated", frontier_payload),)},
            event_visibility_policies={source_stream: ("project",)},
        )
        target_fragment = OwnerAuthorizedFragment(
            fragment_id=f"fragment:ecology:weather-front:target:{source_region_ref}:{target_region_ref}:{tick}",
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref=f"ecology:weather-front:{policy.policy_ref}:{policy.policy_revision}",
            expected_revisions={target_stream: expected_revisions[target_stream]},
            pinned_revisions={
                "target_region": int(target_region["revision"]),
                "target_environment": int(target_environment["revision"]),
            },
            event_specs={
                target_stream: (
                    (
                        "gameplay.ecology.environment.recorded",
                        {
                            "record_ref": target_region_ref,
                            "record": next_environment.model_dump(mode="json"),
                            "source_revision": next_environment.revision,
                            "causal_parent_refs": [],
                        },
                    ),
                )
            },
            event_visibility_policies={target_stream: ("project",)},
        )
        try:
            batch = build_multi_stream_atomic_event_batch_from_fragments(
                command_id=envelope.command_id,
                idempotency_principal_ref=envelope.principal_ref,
                idempotency_key=envelope.idempotency_key,
                causation_id=envelope.causation_id,
                correlation_id=envelope.correlation_id,
                fragments=(source_fragment, target_fragment),
            )
        except ValueError as exc:
            return self._rejected(envelope, str(exc))
        batch = batch.model_copy(
            update={
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}", transaction_id=batch.transaction_id,
                        event_id=event.event_id, global_sequence=0, topic="world.ecology.scoped_projection",
                        audience="project", payload_projection={"region_ref": event.stream_id.removeprefix(self._STREAM_PREFIX), "event_type": event.event_type},
                    )
                    for event in batch.events
                ]
            },
            deep=True,
        )
        return self.store.append_batch(batch)

    def propagate_weather_front_path(
        self,
        *,
        envelope: GameplayCommandEnvelope,
        policy: EcologyWeatherFrontPathPropagationPolicy,
        region_path: tuple[str, ...],
    ) -> AppendBatchResult:
        """Commit a closed, finite weather-front path on existing Ecology streams."""
        if envelope.principal_ref != self._PRINCIPAL or envelope.source_ref != self._PRINCIPAL:
            return self._rejected(envelope, "ecology_authority_required")
        try:
            visibility_scope = self._visibility_scope(envelope)
        except ValueError as exc:
            return self._rejected(envelope, str(exc))
        if visibility_scope != "project":
            return self._rejected(envelope, "ecology_front_privacy_scope_denied")
        if (
            len(region_path) < 2
            or len(region_path) - 1 > policy.max_chain_depth
            or len(region_path) - 1 > policy.max_targets
            or len(set(region_path)) != len(region_path)
            or any(not region_ref for region_ref in region_path)
        ):
            return self._rejected(envelope, "ecology_front_path_invalid")
        request_digest = self._weather_front_path_digest(envelope=envelope, policy=policy, region_path=region_path)
        existing = self.store.get_by_idempotency(envelope.principal_ref, envelope.idempotency_key)
        if existing is not None:
            if self._weather_front_path_digest_for_events(existing.committed_event_ids) == request_digest:
                return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            return self._rejected(envelope, "idempotency_key_reused")
        tick = envelope.payload.get("tick")
        if not isinstance(tick, int) or isinstance(tick, bool) or tick < 0:
            return self._rejected(envelope, "ecology_front_tick_invalid")
        expected_revisions = {
            self.ecology_stream_id(region_ref=region_ref): self.store.get_stream_head(
                self.ecology_stream_id(region_ref=region_ref)
            )
            for region_ref in region_path
        }
        if envelope.expected_revisions != expected_revisions:
            return self._rejected(envelope, "revision_conflict")
        projection = self.regional_projection(scope="authority")
        regions = projection["regions"]
        environments = projection["environments"]
        if not isinstance(regions, dict) or not isinstance(environments, dict):
            return self._rejected(envelope, "ecology_front_records_missing")
        region_records = [regions.get(region_ref) for region_ref in region_path]
        environment_records = [environments.get(region_ref) for region_ref in region_path]
        if not all(isinstance(record, dict) for record in (*region_records, *environment_records)):
            return self._rejected(envelope, "ecology_front_records_missing")
        for source_region_ref, target_region_ref, source_region, target_region in zip(
            region_path,
            region_path[1:],
            region_records,
            region_records[1:],
        ):
            if (
                target_region_ref not in tuple(source_region.get("neighbor_region_refs", ()))
                or source_region_ref not in tuple(target_region.get("neighbor_region_refs", ()))
            ):
                return self._rejected(envelope, "ecology_front_adjacency_denied")

        def canonical_record(record: dict[str, object]) -> dict[str, object]:
            return {
                key: value
                for key, value in record.items()
                if key not in {"causal_parent_refs", "idempotency_key", "evidence_refs"}
            }

        root_weather_ref = str(environment_records[0]["weather_ref"])
        event_specs_by_stream: dict[str, list[tuple[str, dict[str, object]]]] = {
            self.ecology_stream_id(region_ref=region_ref): [] for region_ref in region_path
        }
        pinned_by_stream: dict[str, dict[str, int]] = {
            self.ecology_stream_id(region_ref=region_ref): {"policy": 1} for region_ref in region_path
        }
        for chain_depth, (source_region_ref, target_region_ref, source_region, target_region, source_environment, target_environment) in enumerate(
            zip(
                region_path,
                region_path[1:],
                region_records,
                region_records[1:],
                environment_records,
                environment_records[1:],
            ),
            start=1,
        ):
            source_stream = self.ecology_stream_id(region_ref=source_region_ref)
            target_stream = self.ecology_stream_id(region_ref=target_region_ref)
            frontier_payload = {
                "source_region_ref": source_region_ref,
                "target_region_ref": target_region_ref,
                "weather_ref": root_weather_ref,
                "tick": tick,
                "policy_ref": policy.policy_ref,
                "policy_revision": policy.policy_revision,
                "chain_depth": chain_depth,
                "chain_budget": policy.max_chain_depth,
                "path_digest": request_digest,
                "source_region_revision": int(source_region["revision"]),
                "target_region_revision": int(target_region["revision"]),
                "source_environment_revision": int(source_environment["revision"]),
                "target_environment_revision": int(target_environment["revision"]),
            }
            next_environment = EnvironmentalState.model_validate(canonical_record(target_environment)).model_copy(
                update={"weather_ref": root_weather_ref, "revision": int(target_environment["revision"]) + 1}
            )
            event_specs_by_stream[source_stream].append(("gameplay.ecology.weather_front.propagated", frontier_payload))
            event_specs_by_stream[target_stream].append(
                (
                    "gameplay.ecology.environment.recorded",
                    {
                        "record_ref": target_region_ref,
                        "record": next_environment.model_dump(mode="json"),
                        "source_revision": next_environment.revision,
                        "causal_parent_refs": [],
                    },
                )
            )
            pinned_by_stream[source_stream].update(
                {"source_region": int(source_region["revision"]), "source_environment": int(source_environment["revision"])}
            )
            pinned_by_stream[target_stream].update(
                {"target_region": int(target_region["revision"]), "target_environment": int(target_environment["revision"])}
            )
        fragments = tuple(
            OwnerAuthorizedFragment(
                fragment_id=f"fragment:ecology:weather-front-path:{request_digest}:{stream_id}",
                owner_principal_ref=self._PRINCIPAL,
                source_rule_ref=f"ecology:weather-front-path:{policy.policy_ref}:{policy.policy_revision}",
                expected_revisions={stream_id: expected_revisions[stream_id]},
                pinned_revisions=pinned_by_stream[stream_id],
                event_specs={stream_id: tuple(event_specs)},
                event_visibility_policies={stream_id: tuple("project" for _event in event_specs)},
            )
            for stream_id, event_specs in event_specs_by_stream.items()
        )
        try:
            batch = build_multi_stream_atomic_event_batch_from_fragments(
                command_id=envelope.command_id,
                idempotency_principal_ref=envelope.principal_ref,
                idempotency_key=envelope.idempotency_key,
                causation_id=envelope.causation_id,
                correlation_id=envelope.correlation_id,
                fragments=fragments,
            )
        except ValueError as exc:
            return self._rejected(envelope, str(exc))
        batch = batch.model_copy(
            update={
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}",
                        transaction_id=batch.transaction_id,
                        event_id=event.event_id,
                        global_sequence=0,
                        topic="world.ecology.scoped_projection",
                        audience="project",
                        payload_projection={
                            "region_ref": event.stream_id.removeprefix(self._STREAM_PREFIX),
                            "event_type": event.event_type,
                        },
                    )
                    for event in batch.events
                ]
            },
            deep=True,
        )
        return self.store.append_batch(batch)

    def fanout_weather_front(
        self,
        *,
        envelope: GameplayCommandEnvelope,
        policy: EcologyWeatherFrontFanoutPolicy,
        root_region_ref: str,
        target_region_refs: tuple[str, ...],
    ) -> AppendBatchResult:
        """Copy one root weather state to a bounded explicit neighbor set."""
        if envelope.principal_ref != self._PRINCIPAL or envelope.source_ref != self._PRINCIPAL:
            return self._rejected(envelope, "ecology_authority_required")
        try:
            visibility_scope = self._visibility_scope(envelope)
        except ValueError as exc:
            return self._rejected(envelope, str(exc))
        if visibility_scope != "project":
            return self._rejected(envelope, "ecology_front_privacy_scope_denied")
        if (
            not root_region_ref
            or not target_region_refs
            or len(target_region_refs) > policy.max_targets
            or root_region_ref in target_region_refs
            or len(set(target_region_refs)) != len(target_region_refs)
            or any(not target for target in target_region_refs)
        ):
            return self._rejected(envelope, "ecology_front_fanout_invalid")
        request_digest = self._weather_front_fanout_digest(
            envelope=envelope, policy=policy, root_region_ref=root_region_ref, target_region_refs=target_region_refs
        )
        existing = self.store.get_by_idempotency(envelope.principal_ref, envelope.idempotency_key)
        if existing is not None:
            if self._weather_front_fanout_digest_for_events(existing.committed_event_ids) == request_digest:
                return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            return self._rejected(envelope, "idempotency_key_reused")
        tick = envelope.payload.get("tick")
        if not isinstance(tick, int) or isinstance(tick, bool) or tick < 0:
            return self._rejected(envelope, "ecology_front_tick_invalid")
        region_refs = (root_region_ref, *target_region_refs)
        expected_revisions = {
            self.ecology_stream_id(region_ref=region_ref): self.store.get_stream_head(self.ecology_stream_id(region_ref=region_ref))
            for region_ref in region_refs
        }
        if envelope.expected_revisions != expected_revisions:
            return self._rejected(envelope, "revision_conflict")
        projection = self.regional_projection(scope="authority")
        regions, environments = projection["regions"], projection["environments"]
        if not isinstance(regions, dict) or not isinstance(environments, dict):
            return self._rejected(envelope, "ecology_front_records_missing")
        root_region, root_environment = regions.get(root_region_ref), environments.get(root_region_ref)
        target_regions = [regions.get(target) for target in target_region_refs]
        target_environments = [environments.get(target) for target in target_region_refs]
        if not isinstance(root_region, dict) or not isinstance(root_environment, dict) or not all(
            isinstance(record, dict) for record in (*target_regions, *target_environments)
        ):
            return self._rejected(envelope, "ecology_front_records_missing")
        if any(
            target not in tuple(root_region.get("neighbor_region_refs", ()))
            or root_region_ref not in tuple(target_region.get("neighbor_region_refs", ()))
            for target, target_region in zip(target_region_refs, target_regions)
        ):
            return self._rejected(envelope, "ecology_front_adjacency_denied")

        def canonical_record(record: dict[str, object]) -> dict[str, object]:
            return {key: value for key, value in record.items() if key not in {"causal_parent_refs", "idempotency_key", "evidence_refs"}}

        root_stream = self.ecology_stream_id(region_ref=root_region_ref)
        root_weather_ref = str(root_environment["weather_ref"])
        root_events: list[tuple[str, dict[str, object]]] = []
        fragments: list[OwnerAuthorizedFragment] = []
        for target_region_ref, target_region, target_environment in zip(target_region_refs, target_regions, target_environments):
            target_stream = self.ecology_stream_id(region_ref=target_region_ref)
            root_events.append(
                (
                    "gameplay.ecology.weather_front.propagated",
                    {
                        "source_region_ref": root_region_ref,
                        "target_region_ref": target_region_ref,
                        "weather_ref": root_weather_ref,
                        "tick": tick,
                        "policy_ref": policy.policy_ref,
                        "policy_revision": policy.policy_revision,
                        "chain_depth": 1,
                        "chain_budget": policy.max_chain_depth,
                        "fanout_digest": request_digest,
                        "source_region_revision": int(root_region["revision"]),
                        "target_region_revision": int(target_region["revision"]),
                        "source_environment_revision": int(root_environment["revision"]),
                        "target_environment_revision": int(target_environment["revision"]),
                    },
                )
            )
            next_environment = EnvironmentalState.model_validate(canonical_record(target_environment)).model_copy(
                update={"weather_ref": root_weather_ref, "revision": int(target_environment["revision"]) + 1}
            )
            fragments.append(
                OwnerAuthorizedFragment(
                    fragment_id=f"fragment:ecology:weather-front-fanout:target:{request_digest}:{target_region_ref}",
                    owner_principal_ref=self._PRINCIPAL,
                    source_rule_ref=f"ecology:weather-front-fanout:{policy.policy_ref}:{policy.policy_revision}",
                    expected_revisions={target_stream: expected_revisions[target_stream]},
                    pinned_revisions={
                        f"target_region:{target_region_ref}": int(target_region["revision"]),
                        f"target_environment:{target_region_ref}": int(target_environment["revision"]),
                    },
                    event_specs={target_stream: (("gameplay.ecology.environment.recorded", {"record_ref": target_region_ref, "record": next_environment.model_dump(mode="json"), "source_revision": next_environment.revision, "causal_parent_refs": []}),)},
                    event_visibility_policies={target_stream: ("project",)},
                )
            )
        fragments.append(
            OwnerAuthorizedFragment(
                fragment_id=f"fragment:ecology:weather-front-fanout:root:{request_digest}",
                owner_principal_ref=self._PRINCIPAL,
                source_rule_ref=f"ecology:weather-front-fanout:{policy.policy_ref}:{policy.policy_revision}",
                expected_revisions={root_stream: expected_revisions[root_stream]},
                pinned_revisions={"root_region": int(root_region["revision"]), "root_environment": int(root_environment["revision"]), "policy": 1},
                event_specs={root_stream: tuple(root_events)},
                event_visibility_policies={root_stream: tuple("project" for _event in root_events)},
            )
        )
        try:
            batch = build_multi_stream_atomic_event_batch_from_fragments(
                command_id=envelope.command_id, idempotency_principal_ref=envelope.principal_ref, idempotency_key=envelope.idempotency_key,
                causation_id=envelope.causation_id, correlation_id=envelope.correlation_id, fragments=tuple(fragments)
            )
        except ValueError as exc:
            return self._rejected(envelope, str(exc))
        batch = batch.model_copy(update={"outbox_entries": [GameplayOutboxEntry(outbox_id=f"outbox:{event.event_id}", transaction_id=batch.transaction_id, event_id=event.event_id, global_sequence=0, topic="world.ecology.scoped_projection", audience="project", payload_projection={"region_ref": event.stream_id.removeprefix(self._STREAM_PREFIX), "event_type": event.event_type}) for event in batch.events]}, deep=True)
        return self.store.append_batch(batch)

    @staticmethod
    def _weather_front_event_planner_digest(
        *,
        source_weather_event_id: str,
        source_weather_event_revision: int,
        source_ecology_stream_id: str,
        source_ecology_stream_revision: int,
        root_region_ref: str,
        prior_source_region_ref: str,
        weather_ref: str,
        tick: int,
        policy: EcologyWeatherFrontEventPlannerPolicy,
        waves: tuple[tuple[tuple[str, str], ...], ...],
    ) -> str:
        payload = {
            "source_weather_event_id": source_weather_event_id,
            "source_weather_event_revision": source_weather_event_revision,
            "source_ecology_stream_id": source_ecology_stream_id,
            "source_ecology_stream_revision": source_ecology_stream_revision,
            "root_region_ref": root_region_ref,
            "prior_source_region_ref": prior_source_region_ref,
            "weather_ref": weather_ref,
            "tick": tick,
            "policy": policy.model_dump(mode="json"),
            "waves": waves,
        }
        return "sha256:" + sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    def propose_weather_front_wave_plan_from_event(
        self,
        *,
        source_weather_event_id: str,
        policy: EcologyWeatherFrontEventPlannerPolicy,
    ) -> tuple[EcologyWeatherFrontWavePlan | None, str | None]:
        """Derive a bounded next frontier from committed Ecology evidence only."""
        source_event = next(
            (event for event in self.store.read_events() if event.event_id == source_weather_event_id),
            None,
        )
        if source_event is None:
            return None, "weather_front_source_missing"
        if source_event.event_type != "gameplay.ecology.weather_front.propagated":
            return None, "weather_front_source_invalid"
        if source_event.visibility_policy != "project":
            return None, "weather_front_source_privacy_denied"
        payload = source_event.payload
        try:
            prior_source_region_ref = str(payload["source_region_ref"])
            root_region_ref = str(payload["target_region_ref"])
            weather_ref = str(payload["weather_ref"])
            tick = payload["tick"]
            chain_depth = payload.get("chain_depth", 0)
        except (KeyError, TypeError, ValueError):
            return None, "weather_front_source_invalid"
        if (
            not prior_source_region_ref
            or not root_region_ref
            or prior_source_region_ref == root_region_ref
            or not weather_ref
            or not isinstance(tick, int)
            or isinstance(tick, bool)
            or tick < 0
            or not isinstance(chain_depth, int)
            or isinstance(chain_depth, bool)
            or chain_depth < 0
        ):
            return None, "weather_front_source_invalid"
        if source_event.stream_id != self.ecology_stream_id(region_ref=prior_source_region_ref):
            return None, "weather_front_source_invalid"
        if chain_depth >= policy.max_chain_depth:
            return None, "weather_front_no_eligible_targets"
        projection = self.regional_projection(scope="authority")
        regions = projection.get("regions")
        environments = projection.get("environments")
        if not isinstance(regions, dict) or not isinstance(environments, dict):
            return None, "weather_front_source_missing"
        if not isinstance(regions.get(root_region_ref), dict) or not isinstance(environments.get(root_region_ref), dict):
            return None, "weather_front_source_missing"

        visited = {prior_source_region_ref, root_region_ref}
        frontier = (root_region_ref,)
        waves: list[tuple[tuple[str, str], ...]] = []
        for depth in range(policy.max_chain_depth):
            candidates: list[tuple[str, str]] = []
            for source_region_ref in frontier:
                source_region = regions.get(source_region_ref)
                if not isinstance(source_region, dict):
                    continue
                for target_region_ref in sorted(tuple(source_region.get("neighbor_region_refs", ()) or ())):
                    target_region = regions.get(target_region_ref)
                    target_environment = environments.get(target_region_ref)
                    if (
                        not isinstance(target_region, dict)
                        or not isinstance(target_environment, dict)
                        or target_region_ref in visited
                        or target_environment.get("weather_ref") == weather_ref
                        or source_region_ref not in tuple(target_region.get("neighbor_region_refs", ()) or ())
                        or (source_region_ref, target_region_ref) in candidates
                    ):
                        continue
                    candidates.append((source_region_ref, target_region_ref))
            budget = policy.max_first_wave_targets if depth == 0 else policy.max_targets - sum(len(wave) for wave in waves)
            selected = tuple(candidates[:budget])
            if not selected:
                break
            waves.append(selected)
            visited.update(target for _source, target in selected)
            frontier = tuple(target for _source, target in selected)
            if sum(len(wave) for wave in waves) >= policy.max_targets:
                break
        if not waves:
            return None, "weather_front_no_eligible_targets"
        source_stream_revision = self.store.get_stream_head(source_event.stream_id)
        digest = self._weather_front_event_planner_digest(
            source_weather_event_id=source_event.event_id,
            source_weather_event_revision=source_event.stream_revision,
            source_ecology_stream_id=source_event.stream_id,
            source_ecology_stream_revision=source_stream_revision,
            root_region_ref=root_region_ref,
            prior_source_region_ref=prior_source_region_ref,
            weather_ref=weather_ref,
            tick=tick,
            policy=policy,
            waves=tuple(waves),
        )
        return EcologyWeatherFrontWavePlan(
            source_weather_event_id=source_event.event_id,
            source_weather_event_revision=source_event.stream_revision,
            source_ecology_stream_id=source_event.stream_id,
            source_ecology_stream_revision=source_stream_revision,
            root_region_ref=root_region_ref,
            prior_source_region_ref=prior_source_region_ref,
            weather_ref=weather_ref,
            tick=tick,
            policy_ref=policy.policy_ref,
            policy_revision=policy.policy_revision,
            waves=tuple(waves),
            planner_digest=digest,
        ), None

    def propagate_weather_front_wave_plan(
        self,
        *,
        envelope: GameplayCommandEnvelope,
        policy: EcologyWeatherFrontWaveFanoutPolicy,
        plan: EcologyWeatherFrontWavePlan,
    ) -> AppendBatchResult:
        """Revalidate a read-only plan, then reuse the existing Ecology batch writer."""
        if envelope.principal_ref != self._PRINCIPAL or envelope.source_ref != self._PRINCIPAL:
            return self._rejected(envelope, "ecology_authority_required")
        if plan.policy_ref != "policy:ecology_weather_front_event_planner" or plan.policy_revision != "1":
            return self._rejected(envelope, "weather_front_planner_policy_invalid")
        if envelope.payload.get("source_weather_event_id") != plan.source_weather_event_id or envelope.payload.get("planner_digest") != plan.planner_digest:
            return self._rejected(envelope, "weather_front_planner_digest_invalid")
        forwarded_expected_revisions = dict(envelope.expected_revisions)
        forwarded_expected_revisions.pop(plan.source_ecology_stream_id, None)
        forwarded_envelope = envelope.model_copy(
            update={
                "expected_revisions": forwarded_expected_revisions,
                "payload": {**envelope.payload, "tick": plan.tick},
            },
            deep=True,
        )
        request_digest = self._weather_front_wave_fanout_digest(
            envelope=forwarded_envelope,
            policy=policy,
            root_region_ref=plan.root_region_ref,
            waves=plan.waves,
        )
        existing = self.store.get_by_idempotency(envelope.principal_ref, envelope.idempotency_key)
        if existing is not None:
            if self._weather_front_wave_fanout_digest_for_events(existing.committed_event_ids) == request_digest:
                return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            return self._rejected(envelope, "idempotency_key_reused")
        planner_policy = EcologyWeatherFrontEventPlannerPolicy()
        current_plan, current_plan_error = self.propose_weather_front_wave_plan_from_event(
            source_weather_event_id=plan.source_weather_event_id,
            policy=planner_policy,
        )
        if current_plan is None:
            return self._rejected(envelope, current_plan_error or "weather_front_source_revision_conflict")
        if current_plan.planner_digest != plan.planner_digest:
            return self._rejected(envelope, "weather_front_source_revision_conflict")
        if current_plan != plan:
            return self._rejected(envelope, "weather_front_planner_digest_invalid")
        if envelope.expected_revisions.get(plan.source_ecology_stream_id) != plan.source_ecology_stream_revision:
            return self._rejected(envelope, "revision_conflict")
        return self.fanout_weather_front_waves(
            envelope=forwarded_envelope,
            policy=policy,
            root_region_ref=plan.root_region_ref,
            waves=plan.waves,
        )

    def fanout_weather_front_waves(
        self,
        *,
        envelope: GameplayCommandEnvelope,
        policy: EcologyWeatherFrontWaveFanoutPolicy,
        root_region_ref: str,
        waves: tuple[tuple[tuple[str, str], ...], ...],
    ) -> AppendBatchResult:
        """Commit one closed two-wave Ecology-only weather propagation batch."""
        if envelope.principal_ref != self._PRINCIPAL or envelope.source_ref != self._PRINCIPAL:
            return self._rejected(envelope, "ecology_authority_required")
        try:
            visibility_scope = self._visibility_scope(envelope)
        except ValueError as exc:
            return self._rejected(envelope, str(exc))
        if visibility_scope != "project":
            return self._rejected(envelope, "ecology_front_privacy_scope_denied")
        if len(waves) not in (1, policy.max_chain_depth) or any(not wave for wave in waves):
            return self._rejected(envelope, "ecology_front_wave_invalid")
        first_wave = waves[0]
        second_wave = waves[1] if len(waves) == 2 else ()
        edges = (*first_wave, *second_wave)
        first_targets = tuple(target for _source, target in first_wave)
        targets = tuple(target for _source, target in edges)
        if (
            not root_region_ref
            or len(first_wave) > policy.max_first_wave_targets
            or len(edges) > policy.max_targets
            or any(not source or not target or source == target for source, target in edges)
            or any(source != root_region_ref for source, _target in first_wave)
            or any(source not in first_targets for source, _target in second_wave)
            or root_region_ref in targets
            or len(set(targets)) != len(targets)
        ):
            return self._rejected(envelope, "ecology_front_wave_invalid")
        request_digest = self._weather_front_wave_fanout_digest(
            envelope=envelope, policy=policy, root_region_ref=root_region_ref, waves=waves
        )
        existing = self.store.get_by_idempotency(envelope.principal_ref, envelope.idempotency_key)
        if existing is not None:
            if self._weather_front_wave_fanout_digest_for_events(existing.committed_event_ids) == request_digest:
                return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            return self._rejected(envelope, "idempotency_key_reused")
        tick = envelope.payload.get("tick")
        if not isinstance(tick, int) or isinstance(tick, bool) or tick < 0:
            return self._rejected(envelope, "ecology_front_tick_invalid")
        region_refs = tuple(sorted({root_region_ref, *(region_ref for edge in edges for region_ref in edge)}))
        expected_revisions = {
            self.ecology_stream_id(region_ref=region_ref): self.store.get_stream_head(
                self.ecology_stream_id(region_ref=region_ref)
            )
            for region_ref in region_refs
        }
        if envelope.expected_revisions != expected_revisions:
            return self._rejected(envelope, "revision_conflict")
        projection = self.regional_projection(scope="authority")
        regions = projection["regions"]
        environments = projection["environments"]
        if not isinstance(regions, dict) or not isinstance(environments, dict):
            return self._rejected(envelope, "ecology_front_records_missing")
        if any(not isinstance(regions.get(region_ref), dict) or not isinstance(environments.get(region_ref), dict) for region_ref in region_refs):
            return self._rejected(envelope, "ecology_front_records_missing")
        for source_region_ref, target_region_ref in edges:
            source_region = regions[source_region_ref]
            target_region = regions[target_region_ref]
            if (
                target_region_ref not in tuple(source_region.get("neighbor_region_refs", ()))
                or source_region_ref not in tuple(target_region.get("neighbor_region_refs", ()))
            ):
                return self._rejected(envelope, "ecology_front_adjacency_denied")

        def canonical_record(record: dict[str, object]) -> dict[str, object]:
            return {
                key: value
                for key, value in record.items()
                if key not in {"causal_parent_refs", "idempotency_key", "evidence_refs"}
            }

        root_weather_ref = str(environments[root_region_ref]["weather_ref"])
        effective_environments = {region_ref: canonical_record(environments[region_ref]) for region_ref in region_refs}
        event_specs_by_stream: dict[str, list[tuple[str, dict[str, object]]]] = {
            self.ecology_stream_id(region_ref=region_ref): [] for region_ref in region_refs
        }
        pinned_by_stream: dict[str, dict[str, int]] = {
            self.ecology_stream_id(region_ref=region_ref): {
                f"region:{region_ref}": int(regions[region_ref]["revision"]),
                f"environment:{region_ref}": int(environments[region_ref]["revision"]),
                "policy": 1,
            }
            for region_ref in region_refs
        }
        for chain_depth, wave in enumerate(waves, start=1):
            for source_region_ref, target_region_ref in wave:
                source_stream = self.ecology_stream_id(region_ref=source_region_ref)
                target_stream = self.ecology_stream_id(region_ref=target_region_ref)
                source_environment = effective_environments[source_region_ref]
                target_environment = effective_environments[target_region_ref]
                next_environment = EnvironmentalState.model_validate(target_environment).model_copy(
                    update={
                        "weather_ref": root_weather_ref,
                        "revision": int(target_environment["revision"]) + 1,
                    }
                )
                event_specs_by_stream[source_stream].append(
                    (
                        "gameplay.ecology.weather_front.propagated",
                        {
                            "source_region_ref": source_region_ref,
                            "target_region_ref": target_region_ref,
                            "weather_ref": root_weather_ref,
                            "tick": tick,
                            "policy_ref": policy.policy_ref,
                            "policy_revision": policy.policy_revision,
                            "chain_depth": chain_depth,
                            "chain_budget": policy.max_chain_depth,
                            "wave_fanout_digest": request_digest,
                            "source_region_revision": int(regions[source_region_ref]["revision"]),
                            "target_region_revision": int(regions[target_region_ref]["revision"]),
                            "source_environment_revision": int(source_environment["revision"]),
                            "target_environment_revision": int(target_environment["revision"]),
                        },
                    )
                )
                event_specs_by_stream[target_stream].append(
                    (
                        "gameplay.ecology.environment.recorded",
                        {
                            "record_ref": target_region_ref,
                            "record": next_environment.model_dump(mode="json"),
                            "source_revision": next_environment.revision,
                            "causal_parent_refs": [],
                        },
                    )
                )
                effective_environments[target_region_ref] = next_environment.model_dump(mode="json")
        fragments = tuple(
            OwnerAuthorizedFragment(
                fragment_id=f"fragment:ecology:weather-front-wave-fanout:{request_digest}:{stream_id}",
                owner_principal_ref=self._PRINCIPAL,
                source_rule_ref=f"ecology:weather-front-wave-fanout:{policy.policy_ref}:{policy.policy_revision}",
                expected_revisions={stream_id: expected_revisions[stream_id]},
                pinned_revisions=pinned_by_stream[stream_id],
                event_specs={stream_id: tuple(event_specs)},
                event_visibility_policies={stream_id: tuple("project" for _event in event_specs)},
            )
            for stream_id, event_specs in event_specs_by_stream.items()
        )
        try:
            batch = build_multi_stream_atomic_event_batch_from_fragments(
                command_id=envelope.command_id,
                idempotency_principal_ref=envelope.principal_ref,
                idempotency_key=envelope.idempotency_key,
                causation_id=envelope.causation_id,
                correlation_id=envelope.correlation_id,
                fragments=fragments,
            )
        except ValueError as exc:
            return self._rejected(envelope, str(exc))
        batch = batch.model_copy(
            update={
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}",
                        transaction_id=batch.transaction_id,
                        event_id=event.event_id,
                        global_sequence=0,
                        topic="world.ecology.scoped_projection",
                        audience="project",
                        payload_projection={
                            "region_ref": event.stream_id.removeprefix(self._STREAM_PREFIX),
                            "event_type": event.event_type,
                        },
                    )
                    for event in batch.events
                ]
            },
            deep=True,
        )
        return self.store.append_batch(batch)

    @staticmethod
    def _weather_front_fanout_digest(*, envelope: GameplayCommandEnvelope, policy: EcologyWeatherFrontFanoutPolicy, root_region_ref: str, target_region_refs: tuple[str, ...]) -> str:
        payload = {"command": envelope.model_dump(mode="json"), "policy": policy.model_dump(mode="json"), "root_region_ref": root_region_ref, "target_region_refs": target_region_refs}
        return "sha256:" + sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    def _weather_front_fanout_digest_for_events(self, event_ids: tuple[str, ...]) -> str | None:
        for event in self.store.read_events():
            if event.event_id in set(event_ids) and event.event_type == "gameplay.ecology.weather_front.propagated":
                value = event.payload.get("fanout_digest")
                return value if isinstance(value, str) else None
        return None

    @staticmethod
    def _weather_front_wave_fanout_digest(
        *,
        envelope: GameplayCommandEnvelope,
        policy: EcologyWeatherFrontWaveFanoutPolicy,
        root_region_ref: str,
        waves: tuple[tuple[tuple[str, str], ...], ...],
    ) -> str:
        payload = {
            "command": envelope.model_dump(mode="json"),
            "policy": policy.model_dump(mode="json"),
            "root_region_ref": root_region_ref,
            "waves": waves,
        }
        return "sha256:" + sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    def _weather_front_wave_fanout_digest_for_events(self, event_ids: tuple[str, ...]) -> str | None:
        for event in self.store.read_events():
            if event.event_id in set(event_ids) and event.event_type == "gameplay.ecology.weather_front.propagated":
                value = event.payload.get("wave_fanout_digest")
                return value if isinstance(value, str) else None
        return None

    @staticmethod
    def _weather_front_path_digest(
        *,
        envelope: GameplayCommandEnvelope,
        policy: EcologyWeatherFrontPathPropagationPolicy,
        region_path: tuple[str, ...],
    ) -> str:
        payload = {
            "command": envelope.model_dump(mode="json"),
            "policy": policy.model_dump(mode="json"),
            "region_path": region_path,
        }
        return "sha256:" + sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    def _weather_front_path_digest_for_events(self, event_ids: tuple[str, ...]) -> str | None:
        for event in self.store.read_events():
            if event.event_id in set(event_ids) and event.event_type == "gameplay.ecology.weather_front.propagated":
                value = event.payload.get("path_digest")
                return value if isinstance(value, str) else None
        return None

    def regional_replay(self, *, checkpoint_at: int | None = None):
        replay = GameplayProjectionReplay(projector_id="infra-regional-ecology-truth", projector_version="1")
        events = self.store.read_events()
        if checkpoint_at is None:
            return replay.full_replay(events)
        checkpoint = replay.create_checkpoint(events[:checkpoint_at])
        return replay.checkpoint_plus_tail_replay(checkpoint, events[checkpoint_at:])

    def propose_seasonal_process_to_construction_maintenance(
        self, *, region_ref: str
    ) -> tuple[CanonicalSeasonalConstructionMaintenanceCommand | None, str | None]:
        stream_id = self.ecology_stream_id(region_ref=region_ref)
        events = [
            event for event in self.store.read_stream(stream_id)
            if event.event_type == "gameplay.ecology.seasonal_process_advanced"
            and event.visibility_policy == "project"
            and event.payload.get("region_ref") == region_ref
        ]
        if not events:
            return None, "seasonal_process_source_missing"
        event = events[-1]
        payload = event.payload
        try:
            command = CanonicalSeasonalConstructionMaintenanceCommand(
                edge_ref="ecology-process:seasonal-to-construction-maintenance:v1",
                source_authority_ref=self._PRINCIPAL,
                ecology_stream_id=stream_id,
                ecology_stream_revision=self.store.get_stream_head(stream_id),
                process_event_id=event.event_id,
                process_event_revision=event.stream_revision,
                region_ref=region_ref,
                last_tick=int(payload["last_tick"]),
                elapsed_ticks=int(payload["elapsed_ticks"]),
                policy_ref=str(payload["policy_ref"]),
                policy_revision=str(payload["policy_revision"]),
                privacy_scope="project",
                idempotency_key=f"seasonal-maintenance:{event.event_id}",
            )
        except (KeyError, TypeError, ValueError):
            return None, "seasonal_process_source_invalid"
        return command, None

    @_ecology_seasonal_admission_only
    def admit_seasonal_process_to_construction_maintenance(
        self, *, region_ref: str, _issue: object
    ) -> tuple[CanonicalSeasonalConstructionIntent | None, str | None]:
        command, error = self.propose_seasonal_process_to_construction_maintenance(region_ref=region_ref)
        if command is None:
            return None, error
        return CanonicalSeasonalConstructionIntent(
            command=command,
            admission=_issue(edge_ref=command.edge_ref, process_event_id=command.process_event_id),
        ), None

    def propose_weather_front_to_construction_maintenance(
        self, *, facility_ref: str, region_ref: str
    ) -> tuple[CanonicalWeatherFrontConstructionMaintenanceCommand | None, str | None]:
        candidates = [
            event
            for event in self.store.read_events()
            if event.event_type == "gameplay.ecology.weather_front.propagated"
            and event.visibility_policy == "project"
            and event.payload.get("target_region_ref") == region_ref
        ]
        if not candidates:
            return None, "weather_front_source_missing"
        event = candidates[-1]
        payload = event.payload
        try:
            command = CanonicalWeatherFrontConstructionMaintenanceCommand(
                edge_ref="ecology-weather:front-to-construction-maintenance:v1",
                source_authority_ref=self._PRINCIPAL,
                ecology_stream_id=event.stream_id,
                ecology_stream_revision=self.store.get_stream_head(event.stream_id),
                weather_event_id=event.event_id,
                weather_event_revision=event.stream_revision,
                source_region_ref=str(payload["source_region_ref"]),
                target_region_ref=str(payload["target_region_ref"]),
                facility_ref=facility_ref,
                weather_ref=str(payload["weather_ref"]),
                tick=int(payload["tick"]),
                policy_ref=str(payload["policy_ref"]),
                policy_revision=str(payload["policy_revision"]),
                privacy_scope="project",
                idempotency_key=f"weather-front-maintenance:{event.event_id}:{facility_ref}",
            )
        except (KeyError, TypeError, ValueError):
            return None, "weather_front_source_invalid"
        return command, None

    @_ecology_weather_front_admission_only
    def admit_weather_front_to_construction_maintenance(
        self, *, facility_ref: str, region_ref: str, _issue: object
    ) -> tuple[CanonicalWeatherFrontConstructionIntent | None, str | None]:
        command, error = self.propose_weather_front_to_construction_maintenance(
            facility_ref=facility_ref, region_ref=region_ref
        )
        if command is None:
            return None, error
        return CanonicalWeatherFrontConstructionIntent(
            command=command,
            admission=_issue(
                edge_ref=command.edge_ref,
                weather_event_id=command.weather_event_id,
                facility_ref=command.facility_ref,
            ),
        ), None

    def propose_weather_front_to_construction_maintenance_fanout(
        self, *, facility_refs: tuple[str, str], region_ref: str
    ) -> tuple[CanonicalWeatherFrontConstructionMaintenanceFanoutCommand | None, str | None]:
        if len(facility_refs) != 2 or len(set(facility_refs)) != 2 or any(not value for value in facility_refs):
            return None, "weather_front_fanout_target_invalid"
        candidates = [
            event
            for event in self.store.read_events()
            if event.event_type == "gameplay.ecology.weather_front.propagated"
            and event.visibility_policy == "project"
            and event.payload.get("target_region_ref") == region_ref
        ]
        if not candidates:
            return None, "weather_front_source_missing"
        event = candidates[-1]
        payload = event.payload
        try:
            command = CanonicalWeatherFrontConstructionMaintenanceFanoutCommand(
                edge_ref="ecology-weather:front-to-construction-maintenance-fanout:v1",
                source_authority_ref=self._PRINCIPAL,
                ecology_stream_id=event.stream_id,
                ecology_stream_revision=self.store.get_stream_head(event.stream_id),
                weather_event_id=event.event_id,
                weather_event_revision=event.stream_revision,
                source_region_ref=str(payload["source_region_ref"]),
                target_region_ref=str(payload["target_region_ref"]),
                facility_refs=facility_refs,
                weather_ref=str(payload["weather_ref"]),
                tick=int(payload["tick"]),
                policy_ref=str(payload["policy_ref"]),
                policy_revision=str(payload["policy_revision"]),
                privacy_scope="project",
                idempotency_key=f"weather-front-maintenance-fanout:{event.event_id}:{':'.join(facility_refs)}",
            )
        except (KeyError, TypeError, ValueError):
            return None, "weather_front_source_invalid"
        return command, None

    @_ecology_weather_front_fanout_admission_only
    def admit_weather_front_to_construction_maintenance_fanout(
        self, *, facility_refs: tuple[str, str], region_ref: str, _issue: object
    ) -> tuple[CanonicalWeatherFrontConstructionFanoutIntent | None, str | None]:
        command, error = self.propose_weather_front_to_construction_maintenance_fanout(facility_refs=facility_refs, region_ref=region_ref)
        if command is None:
            return None, error
        return CanonicalWeatherFrontConstructionFanoutIntent(
            command=command,
            admission=_issue(edge_ref=command.edge_ref, weather_event_id=command.weather_event_id, facility_refs=command.facility_refs),
        ), None

    def propose_weather_front_to_organization_supply(
        self,
        *,
        organization_ref: str,
        counterparty_organization_ref: str,
        commitment_ref: str,
        policy_revision: str,
        organization_grant_refs: tuple[str, ...],
        budget_reservation_refs: tuple[str, ...],
        region_ref: str,
    ) -> tuple[CanonicalWeatherFrontOrganizationSupplyCommand | None, str | None]:
        if (
            not organization_ref
            or not counterparty_organization_ref
            or not commitment_ref
            or not policy_revision
            or not organization_grant_refs
            or not budget_reservation_refs
            or any(not ref.startswith("grant:") for ref in organization_grant_refs)
            or any(not ref.startswith("reservation:") for ref in budget_reservation_refs)
        ):
            return None, "weather_front_organization_target_invalid"
        candidates = [
            event
            for event in self.store.read_events()
            if event.event_type == "gameplay.ecology.weather_front.propagated"
            and event.visibility_policy == "project"
            and event.payload.get("target_region_ref") == region_ref
        ]
        if not candidates:
            return None, "weather_front_source_missing"
        event = candidates[-1]
        payload = event.payload
        try:
            command = CanonicalWeatherFrontOrganizationSupplyCommand(
                edge_ref="ecology-weather:front-to-organization-supply:v1",
                command_id=(
                    f"command:ecology-weather-front-organization:{event.event_id}:{commitment_ref}"
                ),
                source_authority_ref=self._PRINCIPAL,
                ecology_stream_id=event.stream_id,
                ecology_stream_revision=self.store.get_stream_head(event.stream_id),
                weather_event_id=event.event_id,
                weather_event_revision=event.stream_revision,
                source_region_ref=str(payload["source_region_ref"]),
                target_region_ref=str(payload["target_region_ref"]),
                weather_ref=str(payload["weather_ref"]),
                tick=int(payload["tick"]),
                organization_ref=organization_ref,
                counterparty_organization_ref=counterparty_organization_ref,
                commitment_ref=commitment_ref,
                policy_revision=policy_revision,
                organization_grant_refs=organization_grant_refs,
                budget_reservation_refs=budget_reservation_refs,
                privacy_scope="project",
                idempotency_key=f"weather-front-organization-supply:{event.event_id}:{organization_ref}:{commitment_ref}",
            )
        except (KeyError, TypeError, ValueError):
            return None, "weather_front_source_invalid"
        return command, None

    @_ecology_weather_front_organization_supply_admission_only
    def admit_weather_front_to_organization_supply(
        self,
        *,
        organization_ref: str,
        counterparty_organization_ref: str,
        commitment_ref: str,
        policy_revision: str,
        organization_grant_refs: tuple[str, ...],
        budget_reservation_refs: tuple[str, ...],
        region_ref: str,
        _issue: object,
    ) -> tuple[CanonicalWeatherFrontOrganizationSupplyIntent | None, str | None]:
        command, error = self.propose_weather_front_to_organization_supply(
            organization_ref=organization_ref,
            counterparty_organization_ref=counterparty_organization_ref,
            commitment_ref=commitment_ref,
            policy_revision=policy_revision,
            organization_grant_refs=organization_grant_refs,
            budget_reservation_refs=budget_reservation_refs,
            region_ref=region_ref,
        )
        if command is None:
            return None, error
        return CanonicalWeatherFrontOrganizationSupplyIntent(
            command=command,
            admission=_issue(
                edge_ref=command.edge_ref,
                weather_event_id=command.weather_event_id,
                organization_ref=command.organization_ref,
                commitment_ref=command.commitment_ref,
            ),
        ), None

    def propose_weather_front_to_organization_supply_fanout(
        self,
        *,
        target_specs: tuple[dict[str, object], dict[str, object]],
        region_ref: str,
    ) -> tuple[CanonicalWeatherFrontOrganizationSupplyFanoutCommand | None, str | None]:
        if not isinstance(target_specs, tuple) or len(target_specs) != 2:
            return None, "weather_front_organization_fanout_target_invalid"
        normalized_targets: list[CanonicalWeatherFrontOrganizationSupplyFanoutTarget] = []
        for spec in target_specs:
            try:
                target = CanonicalWeatherFrontOrganizationSupplyFanoutTarget.model_validate(spec)
            except Exception:
                return None, "weather_front_organization_fanout_target_invalid"
            if (
                not target.organization_grant_refs
                or not target.budget_reservation_refs
                or any(not ref.startswith("grant:") for ref in target.organization_grant_refs)
                or any(not ref.startswith("reservation:") for ref in target.budget_reservation_refs)
            ):
                return None, "weather_front_organization_fanout_target_invalid"
            normalized_targets.append(target)
        canonical_targets = tuple(
            sorted(normalized_targets, key=lambda item: item.organization_ref)
        )
        organization_refs = tuple(
            target.organization_ref for target in canonical_targets
        )
        if len(set(organization_refs)) != 2:
            return None, "weather_front_organization_fanout_target_invalid"
        candidates = [
            event
            for event in self.store.read_events()
            if event.event_type == "gameplay.ecology.weather_front.propagated"
            and event.visibility_policy == "project"
            and event.payload.get("target_region_ref") == region_ref
        ]
        if not candidates:
            return None, "weather_front_source_missing"
        event = candidates[-1]
        payload = event.payload
        try:
            command = CanonicalWeatherFrontOrganizationSupplyFanoutCommand(
                edge_ref="ecology-weather:front-to-organization-supply-fanout:v1",
                command_id=(
                    "command:ecology-weather-front-organization-fanout:"
                    f"{event.event_id}:{':'.join(organization_refs)}"
                ),
                source_authority_ref=self._PRINCIPAL,
                ecology_stream_id=event.stream_id,
                ecology_stream_revision=self.store.get_stream_head(event.stream_id),
                weather_event_id=event.event_id,
                weather_event_revision=event.stream_revision,
                source_region_ref=str(payload["source_region_ref"]),
                target_region_ref=str(payload["target_region_ref"]),
                weather_ref=str(payload["weather_ref"]),
                tick=int(payload["tick"]),
                target_specs=canonical_targets,
                privacy_scope="project",
                idempotency_key=(
                    "weather-front-organization-supply-fanout:"
                    f"{event.event_id}:{':'.join(organization_refs)}"
                ),
            )
        except (KeyError, TypeError, ValueError):
            return None, "weather_front_source_invalid"
        return command, None

    @_ecology_weather_front_organization_supply_fanout_admission_only
    def admit_weather_front_to_organization_supply_fanout(
        self,
        *,
        target_specs: tuple[dict[str, object], dict[str, object]],
        region_ref: str,
        _issue: object,
    ) -> tuple[
        CanonicalWeatherFrontOrganizationSupplyFanoutIntent | None,
        str | None,
    ]:
        command, error = self.propose_weather_front_to_organization_supply_fanout(
            target_specs=target_specs,
            region_ref=region_ref,
        )
        if command is None:
            return None, error
        return CanonicalWeatherFrontOrganizationSupplyFanoutIntent(
            command=command,
            admission=_issue(
                edge_ref=command.edge_ref,
                weather_event_id=command.weather_event_id,
                organization_refs=tuple(
                    target.organization_ref for target in command.target_specs
                ),
            ),
        ), None

    @_ecology_weather_quote_admission_only
    def admit_weather_front_to_economy_quote(self, *, region_ref: str, quote_ref: str, _issue: object):
        candidates = [event for event in self.store.read_events() if event.event_type == "gameplay.ecology.weather_front.propagated" and event.visibility_policy == "project" and event.payload.get("target_region_ref") == region_ref]
        if not candidates or not quote_ref:
            return None, "weather_front_quote_source_missing"
        event = candidates[-1]
        source = {"weather_event_id": event.event_id, "ecology_stream_id": event.stream_id, "ecology_revision": event.stream_revision, "region_ref": region_ref, "quote_ref": quote_ref}
        return source, _issue(**source)

    @_ecology_weather_quote_fanout_admission_only
    def admit_weather_front_to_economy_quote_fanout(self, *, region_ref: str, quote_refs: tuple[str, str], _issue: object):
        if (
            not isinstance(quote_refs, tuple)
            or len(quote_refs) != 2
            or any(not isinstance(ref, str) or not ref for ref in quote_refs)
            or quote_refs[0] == quote_refs[1]
        ):
            return None, "weather_front_quote_fanout_target_invalid"
        candidates = [
            event for event in self.store.read_events()
            if event.event_type == "gameplay.ecology.weather_front.propagated"
            and event.visibility_policy == "project"
            and event.payload.get("target_region_ref") == region_ref
        ]
        if not candidates:
            return None, "weather_front_quote_fanout_source_missing"
        event = candidates[-1]
        canonical_refs = tuple(sorted(quote_refs))
        source = {
            "weather_event_id": event.event_id,
            "ecology_stream_id": event.stream_id,
            "ecology_revision": event.stream_revision,
            "region_ref": region_ref,
            "quote_refs": canonical_refs,
        }
        return source, _issue(**source)

    def propose_canonical_frost_to_construction(
        self, *, hazard_ref: str
    ) -> CanonicalFrostProductionProposalResult:
        active_hazards: dict[str, object] = {}
        active_crops: dict[str, object] = {}
        retired_hazards: set[str] = set()
        private_hazards: set[str] = set()
        for event in self.store.read_events():
            record_ref = event.payload.get("record_ref")
            if not isinstance(record_ref, str):
                continue
            if event.event_type == "gameplay.ecology.hazard.retired":
                active_hazards.pop(record_ref, None)
                retired_hazards.add(record_ref)
            elif event.event_type == "gameplay.ecology.crop.retired":
                active_crops.pop(record_ref, None)
            elif event.event_type == "gameplay.ecology.hazard.recorded":
                retired_hazards.discard(record_ref)
                if event.visibility_policy == "project":
                    active_hazards[record_ref] = event
                else:
                    private_hazards.add(record_ref)
            elif event.event_type == "gameplay.ecology.crop.recorded" and event.visibility_policy == "project":
                active_crops[record_ref] = event
        hazard_event = active_hazards.get(hazard_ref)
        if hazard_event is None:
            if hazard_ref in retired_hazards:
                return CanonicalFrostProductionProposalResult(accepted=False, error_code="canonical_hazard_source_retired")
            if hazard_ref in private_hazards:
                return CanonicalFrostProductionProposalResult(accepted=False, error_code="canonical_hazard_source_privacy_denied")
            return CanonicalFrostProductionProposalResult(accepted=False, error_code="canonical_hazard_source_missing")
        hazard = hazard_event.payload.get("record")
        if not isinstance(hazard, dict):
            return CanonicalFrostProductionProposalResult(accepted=False, error_code="canonical_hazard_source_invalid")
        if str(hazard.get("privacy_scope", "")) != "project":
            return CanonicalFrostProductionProposalResult(accepted=False, error_code="canonical_hazard_source_privacy_denied")
        source_crop_ref = hazard.get("source_crop_ref")
        if not isinstance(source_crop_ref, str) or not source_crop_ref:
            return CanonicalFrostProductionProposalResult(accepted=False, error_code="canonical_hazard_crop_source_missing")
        crop_event = active_crops.get(source_crop_ref)
        if crop_event is None:
            return CanonicalFrostProductionProposalResult(accepted=False, error_code="canonical_hazard_crop_source_missing")
        crop = crop_event.payload["record"]
        stream_id = hazard_event.stream_id
        stream_head = self.store.get_stream_head(stream_id)
        if crop_event.stream_id != stream_id or hazard_event.stream_revision > stream_head:
            return CanonicalFrostProductionProposalResult(accepted=False, error_code="canonical_hazard_source_revision_conflict")
        return CanonicalFrostProductionProposalResult(
            accepted=True,
            command=CanonicalFrostProductionFinishCommand(
                edge_ref="ecology-hazard:frost-to-construction-finish:v1",
                source_authority_ref=self._PRINCIPAL,
                ecology_stream_id=stream_id,
                ecology_stream_revision=stream_head,
                hazard_event_id=hazard_event.event_id,
                hazard_event_revision=hazard_event.stream_revision,
                crop_event_id=crop_event.event_id,
                crop_event_revision=crop_event.stream_revision,
                hazard_ref=str(hazard["hazard_ref"]),
                crop_ref=str(crop["crop_ref"]),
                plot_ref=str(crop["plot_ref"]),
                region_ref=str(hazard["region_ref"]),
                effect_ref=str(hazard["effect_ref"]),
                due_tick=int(hazard["due_tick"]),
                causal_parent_refs=tuple(str(value) for value in hazard.get("causal_parent_refs", ())),
                privacy_scope="project",
                idempotency_key=f"canonical-frost-production:{hazard_event.event_id}:{crop_event.event_id}",
            ),
        )

    @_ecology_admission_only
    def admit_canonical_frost_to_construction(
        self,
        *,
        hazard_ref: str,
        _issue: object,
    ) -> tuple[CanonicalFrostConstructionIntent | None, str | None]:
        proposal = self.propose_canonical_frost_to_construction(hazard_ref=hazard_ref)
        if not proposal.accepted or proposal.command is None:
            return None, proposal.error_code
        command = proposal.command
        admission = _issue(
            edge_ref=command.edge_ref,
            hazard_event_id=command.hazard_event_id,
            crop_event_id=command.crop_event_id,
        )
        return CanonicalFrostConstructionIntent(command=command, admission=admission), None

    def propose_frost_due_finish(self, *, hazard_ref: str) -> FrostFinishProposalResult:
        source = self.frost_source(hazard_ref=hazard_ref, scope="authority")
        if not source.accepted or source.source is None:
            return FrostFinishProposalResult(accepted=False, error_code=source.error_code)
        value = source.source
        return FrostFinishProposalResult(
            accepted=True,
            proposal=ConstructionFrostFinishCommand(
                source_event_id=value.source_event_id,
                source_stream_revision=value.source_stream_revision,
                hazard_ref=value.hazard_ref,
                crop_ref=value.crop_ref,
                plot_ref=value.plot_ref,
                region_ref=value.region_ref,
                due_tick=value.due_tick,
                semantic_revision=value.semantic_revision,
                rule_revision=value.rule_revision,
                policy_revision=value.policy_revision,
                causal_parent_refs=value.causal_parent_refs,
                privacy_scope=value.privacy_scope,
            ),
        )

    def replay(self, *, checkpoint_at: int | None = None):
        replay = GameplayProjectionReplay(projector_id="infra-ecology-disaster", projector_version="1")
        events = self.store.read_events()
        if checkpoint_at is None:
            return replay.full_replay(events)
        checkpoint = replay.create_checkpoint(events[:checkpoint_at])
        return replay.checkpoint_plus_tail_replay(checkpoint, events[checkpoint_at:])

    def project(self, *, scope: Literal["public", "authority"] = "public") -> dict[str, object]:
        events = self.store.read_events()
        evidence = tuple(ref for event in events for ref in event.payload.get("evidence_refs", ()))
        return {"event_refs": tuple(event.event_id for event in events), "evidence_refs": evidence if scope == "authority" else ()}


__all__ = ["CanonicalFrostConstructionIntent", "CanonicalSeasonalConstructionIntent", "CanonicalFrostProductionProposalResult", "CanonicalWeatherFrontOrganizationSupplyCommand", "CanonicalWeatherFrontOrganizationSupplyFanoutCommand", "CanonicalWeatherFrontOrganizationSupplyFanoutIntent", "CanonicalWeatherFrontOrganizationSupplyIntent", "HazardRecord", "EcologyHazardAuthority", "EcologySeasonalProcessPolicy", "EcologyWeatherFrontPropagationPolicy", "EcologyWeatherFrontWaveFanoutPolicy", "EnvironmentalState", "EnvironmentRegion", "FrostFinishProposalResult", "FrostPropagationSource", "FrostSourceResult", "HazardSettlementResult", "ResourceNode", "CropRecord"]
