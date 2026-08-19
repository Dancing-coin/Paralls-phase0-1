"""Minimal Construction/Production owner for the Econ-1 bakery slice."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from types import MappingProxyType
from typing import Literal, Mapping, Sequence

from pydantic import ConfigDict, Field

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.ecology_consumer_admission import EcologyConsumerAdmissionCheck
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog, GovernedAuthorityContractError
from app.gameplay.models import AtomicEventBatch, AppendBatchResult, GameplayEvent, GameplayFailure, GameplayOutboxEntry, OwnerAuthorizedFragment, StrictGameplayModel
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.semantic_effects import EffectApplication, EffectLifecycleEvaluator, ResistanceProfile, StateDefinition
from app.gameplay.semantic_registry import SemanticRegistry, SemanticRegistryError
from app.gameplay.settlement_plan import build_atomic_event_batch, build_multi_stream_atomic_event_batch_from_fragments
from app.gameplay.shared_contracts import GameplayCommandEnvelope, ScheduledObligation, SettlementReceipt
from app.gameplay.settlement_plan import SettlementPlan
from app.gameplay.organization_government_runtime import WorkerContributionRef


def _canonical_hazard_admission_channel():
    """Create an opaque, closure-owned ecology admission channel."""

    @dataclass(frozen=True)
    class _Admission:
        edge_ref: str
        hazard_event_id: str
        crop_event_id: str

    def issue(*, edge_ref: str, hazard_event_id: str, crop_event_id: str) -> object:
        return _Admission(
            edge_ref=edge_ref,
            hazard_event_id=hazard_event_id,
            crop_event_id=crop_event_id,
        )

    def contains(admission: object) -> bool:
        return isinstance(admission, _Admission)

    return issue, contains


(
    _CANONICAL_HAZARD_ADMISSION_ISSUER,
    _CONTAINS_CANONICAL_HAZARD_ADMISSION,
) = _canonical_hazard_admission_channel()


def _take_canonical_hazard_admission_issuer() -> object:
    """One-time handoff to ecology; remove the transfer surface afterwards."""

    issuer = _CANONICAL_HAZARD_ADMISSION_ISSUER
    del globals()["_CANONICAL_HAZARD_ADMISSION_ISSUER"]
    del globals()["_take_canonical_hazard_admission_issuer"]
    return issuer


def _canonical_seasonal_admission_channel():
    @dataclass(frozen=True)
    class _Admission:
        edge_ref: str
        process_event_id: str

    def issue(*, edge_ref: str, process_event_id: str) -> object:
        return _Admission(edge_ref=edge_ref, process_event_id=process_event_id)

    def contains(admission: object) -> bool:
        return isinstance(admission, _Admission)

    return issue, contains


(
    _CANONICAL_SEASONAL_ADMISSION_ISSUER,
    _CONTAINS_CANONICAL_SEASONAL_ADMISSION,
) = _canonical_seasonal_admission_channel()


def _take_canonical_seasonal_admission_issuer() -> object:
    issuer = _CANONICAL_SEASONAL_ADMISSION_ISSUER
    del globals()["_CANONICAL_SEASONAL_ADMISSION_ISSUER"]
    del globals()["_take_canonical_seasonal_admission_issuer"]
    return issuer


def _canonical_weather_front_admission_channel():
    @dataclass(frozen=True)
    class _Admission:
        edge_ref: str
        weather_event_id: str
        facility_ref: str

    def issue(*, edge_ref: str, weather_event_id: str, facility_ref: str) -> object:
        return _Admission(edge_ref=edge_ref, weather_event_id=weather_event_id, facility_ref=facility_ref)

    def contains(admission: object) -> bool:
        return isinstance(admission, _Admission)

    return issue, contains


(
    _CANONICAL_WEATHER_FRONT_ADMISSION_ISSUER,
    _CONTAINS_CANONICAL_WEATHER_FRONT_ADMISSION,
) = _canonical_weather_front_admission_channel()


def _take_canonical_weather_front_admission_issuer() -> object:
    issuer = _CANONICAL_WEATHER_FRONT_ADMISSION_ISSUER
    del globals()["_CANONICAL_WEATHER_FRONT_ADMISSION_ISSUER"]
    del globals()["_take_canonical_weather_front_admission_issuer"]
    return issuer


def _canonical_weather_front_fanout_admission_channel():
    @dataclass(frozen=True)
    class _Admission:
        edge_ref: str
        weather_event_id: str
        facility_refs: tuple[str, str]

    def issue(*, edge_ref: str, weather_event_id: str, facility_refs: tuple[str, str]) -> object:
        return _Admission(edge_ref=edge_ref, weather_event_id=weather_event_id, facility_refs=facility_refs)

    def contains(admission: object) -> bool:
        return isinstance(admission, _Admission)

    return issue, contains


(
    _CANONICAL_WEATHER_FRONT_FANOUT_ADMISSION_ISSUER,
    _CONTAINS_CANONICAL_WEATHER_FRONT_FANOUT_ADMISSION,
) = _canonical_weather_front_fanout_admission_channel()


def _take_canonical_weather_front_fanout_admission_issuer() -> object:
    issuer = _CANONICAL_WEATHER_FRONT_FANOUT_ADMISSION_ISSUER
    del globals()["_CANONICAL_WEATHER_FRONT_FANOUT_ADMISSION_ISSUER"]
    del globals()["_take_canonical_weather_front_fanout_admission_issuer"]
    return issuer


class Plot(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    plot_ref: str = Field(min_length=1)
    jurisdiction_ref: str = Field(min_length=1)
    owner_ref: str = Field(min_length=1)
    revision: int = Field(default=0, ge=0)


class Blueprint(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    blueprint_ref: str = Field(min_length=1)
    facility_kind: str = Field(min_length=1)
    required_permit_ref: str = Field(min_length=1)
    revision: int = Field(default=1, ge=1)


class Facility(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    facility_ref: str = Field(min_length=1)
    plot_ref: str = Field(min_length=1)
    facility_kind: str = Field(min_length=1)
    condition: float = Field(ge=0, le=1)
    revision: int = Field(default=0, ge=0)


class Recipe(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    recipe_ref: str = Field(min_length=1)
    inputs: dict[str, int] = Field(default_factory=dict)
    output_item: str = Field(min_length=1)
    duration_ticks: int = Field(gt=0)


class ConstructionJob(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    job_ref: str = Field(min_length=1)
    plot_ref: str = Field(min_length=1)
    blueprint_ref: str = Field(min_length=1)
    status: Literal["planned", "started", "completed", "failed"] = "planned"
    reservation_refs: tuple[str, ...] = ()
    pinned_revisions: dict[str, int] = Field(default_factory=dict)


class ProductionRun(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_ref: str = Field(min_length=1)
    facility_ref: str = Field(min_length=1)
    recipe_ref: str = Field(min_length=1)
    status: Literal["started", "completed", "lost", "released"] = "started"
    started_tick: int = Field(ge=0)
    finish_tick: int = Field(ge=0)
    reservation_refs: tuple[str, ...] = ()
    output_item: str | None = None
    maintenance_obligation_ref: str | None = None
    work_order_ref: str | None = None
    shift_ref: str | None = None
    worker_contribution_refs: tuple[str, ...] = ()
    facility_slot_ref: str | None = None


class ConstructionDueCompletionPolicy(StrictGameplayModel):
    """The sole INF-2R policy: caller-selected production completion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_ref: Literal["policy:construction_due_completion"]
    policy_revision: str = Field(min_length=1)

    @staticmethod
    def obligation_id_for(*, run_ref: str) -> str:
        return f"obligation:construction-production:finish:{run_ref}"

    def build_obligation(
        self,
        *,
        run: ProductionRun,
        expected_revision: int,
        status: Literal["open", "due", "cancelled"] = "due",
        retry_policy: dict[str, object] | None = None,
        compensation_policy: dict[str, object] | None = None,
    ) -> ScheduledObligation:
        stream_id = f"gameplay:construction_production:{run.facility_ref}"
        return ScheduledObligation(
            obligation_id=self.obligation_id_for(run_ref=run.run_ref),
            owner_ref=ConstructionProductionAuthority._PRINCIPAL,
            due_tick=run.finish_tick,
            policy_revision=self.policy_revision,
            status=status,
            retry_policy=retry_policy or {},
            compensation_policy=compensation_policy or {},
            source_refs=(run.run_ref, self.policy_ref),
            idempotency_key=f"obligation:construction-production:finish:{run.run_ref}:{self.policy_revision}",
            expected_revisions={stream_id: expected_revision},
            visibility_scope="project",
        )

    @staticmethod
    def build_fragment(
        *,
        run: ProductionRun,
        recipe: Recipe,
        tick: int,
        expected_revision: int,
        obligation: ScheduledObligation | None = None,
        settled_event_type: str | None = None,
    ) -> OwnerAuthorizedFragment:
        if (obligation is None) != (settled_event_type is None):
            raise ValueError("construction_obligation_lifecycle_fields_required")
        if obligation is not None and settled_event_type is not None:
            return ConstructionProductionAuthority.build_due_finish_lifecycle_fragment(
                run=run,
                recipe=recipe,
                tick=tick,
                expected_revision=expected_revision,
                obligation=obligation,
                settled_event_type=settled_event_type,
            )
        return ConstructionProductionAuthority.build_due_finish_fragment(
            run=run,
            recipe=recipe,
            tick=tick,
            expected_revision=expected_revision,
        )


@dataclass(frozen=True)
class ConstructionProductionProjection:
    """Read model rebuilt from this authority's committed facts only."""

    runs: Mapping[str, ProductionRun]
    source_revision_vector: Mapping[str, int]
    facilities: Mapping[str, Facility] = field(default_factory=dict)
    recipes_by_run: Mapping[str, "CommittedProductionRecipe"] = field(default_factory=dict)
    maintenance_states: Mapping[str, ConstructionMaintenanceState] = field(default_factory=dict)


class CommittedProductionRecipe(StrictGameplayModel):
    """Fragment inputs reconstructed from the construction owner's run-start fact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    recipe: Recipe
    source_stream_revision: int = Field(ge=0)


class ProductionRecipeResult(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted: bool
    recipe: CommittedProductionRecipe | None = None
    error_code: str | None = None


class ProductionCompletedEvidenceView(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    owner_principal_ref: str
    recipient_ref: str
    evidence_refs: tuple[str, ...] = ()
    evidence_rows: tuple[dict[str, object], ...] = ()
    source_event_refs: tuple[str, ...] = ()
    source_revision_vector: dict[str, int] = Field(default_factory=dict)
    projection_hash: str


class ConstructionMaintenanceState(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    state_ref: str = Field(min_length=1)
    effect_ref: str = Field(min_length=1)
    stacks: int = Field(ge=1)
    effective_magnitude: int = Field(ge=0)
    resistance_revision: int = Field(ge=0)
    semantic_snapshot_digest: str = Field(min_length=1)


class ConstructionMaintenanceStateObligationResult(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    committed: bool
    obligation: ScheduledObligation | None = None
    append_result: AppendBatchResult | None = None
    error_code: str | None = None


class ConstructionFrostFinishCommand(StrictGameplayModel):
    """Ecology proposal referencing its committed frost fact, never a target choice."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_event_id: str = Field(min_length=1)
    source_stream_revision: int = Field(ge=0)
    hazard_ref: str = Field(min_length=1)
    crop_ref: str = Field(min_length=1)
    plot_ref: str = Field(min_length=1)
    region_ref: str = Field(min_length=1)
    due_tick: int = Field(ge=0)
    semantic_revision: str = Field(min_length=1)
    rule_revision: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    causal_parent_refs: tuple[str, ...] = ()
    privacy_scope: Literal["project", "authority_only"]


class CanonicalFrostProductionFinishCommand(StrictGameplayModel):
    """Construction-owned admission command for one canonical ecology edge."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    edge_ref: str = Field(min_length=1)
    enabled: bool = True
    source_authority_ref: str = Field(min_length=1)
    ecology_stream_id: str = Field(min_length=1)
    ecology_stream_revision: int = Field(ge=0)
    hazard_event_id: str = Field(min_length=1)
    hazard_event_revision: int = Field(ge=0)
    crop_event_id: str = Field(min_length=1)
    crop_event_revision: int = Field(ge=0)
    hazard_ref: str = Field(min_length=1)
    crop_ref: str = Field(min_length=1)
    plot_ref: str = Field(min_length=1)
    region_ref: str = Field(min_length=1)
    effect_ref: str = Field(min_length=1)
    due_tick: int = Field(ge=0)
    causal_parent_refs: tuple[str, ...] = ()
    privacy_scope: Literal["project", "authority_only"]
    idempotency_key: str = Field(min_length=1)


class CanonicalSeasonalConstructionMaintenanceCommand(StrictGameplayModel):
    """Construction-owned admission command for one seasonal ecology edge."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    edge_ref: str = Field(min_length=1)
    enabled: bool = True
    source_authority_ref: str = Field(min_length=1)
    ecology_stream_id: str = Field(min_length=1)
    ecology_stream_revision: int = Field(ge=0)
    process_event_id: str = Field(min_length=1)
    process_event_revision: int = Field(ge=0)
    region_ref: str = Field(min_length=1)
    last_tick: int = Field(ge=0)
    elapsed_ticks: int = Field(gt=0)
    policy_ref: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    privacy_scope: Literal["project", "authority_only"]
    idempotency_key: str = Field(min_length=1)


class CanonicalWeatherFrontConstructionMaintenanceCommand(StrictGameplayModel):
    """Construction-owned admission command for the weather-front edge."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    edge_ref: str = Field(min_length=1)
    enabled: bool = True
    source_authority_ref: str = Field(min_length=1)
    ecology_stream_id: str = Field(min_length=1)
    ecology_stream_revision: int = Field(ge=0)
    weather_event_id: str = Field(min_length=1)
    weather_event_revision: int = Field(ge=0)
    source_region_ref: str = Field(min_length=1)
    target_region_ref: str = Field(min_length=1)
    facility_ref: str = Field(min_length=1)
    weather_ref: str = Field(min_length=1)
    tick: int = Field(ge=0)
    policy_ref: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    privacy_scope: Literal["project", "authority_only"]
    idempotency_key: str = Field(min_length=1)


class CanonicalWeatherFrontConstructionMaintenanceFanoutCommand(StrictGameplayModel):
    """Construction-owned fixed two-facility weather-front fanout command."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    edge_ref: str = Field(min_length=1)
    enabled: bool = True
    source_authority_ref: str = Field(min_length=1)
    ecology_stream_id: str = Field(min_length=1)
    ecology_stream_revision: int = Field(ge=0)
    weather_event_id: str = Field(min_length=1)
    weather_event_revision: int = Field(ge=0)
    source_region_ref: str = Field(min_length=1)
    target_region_ref: str = Field(min_length=1)
    facility_refs: tuple[str, str]
    weather_ref: str = Field(min_length=1)
    tick: int = Field(ge=0)
    policy_ref: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    privacy_scope: Literal["project", "authority_only"]
    idempotency_key: str = Field(min_length=1)


class PackageDeclaredFacilityTransformIntentV1(StrictGameplayModel):
    """Typed proposal for the single admitted industrial facility transform.

    Authority coordinates and package content are intentionally absent from this
    caller surface; they are resolved from the active immutable package binding.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    facility_ref: str = Field(min_length=1)
    acquisition_event_id: str = Field(min_length=1)
    expected_revision: int = Field(ge=0)
    expected_facility_revision: int = Field(ge=0)
    command_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    submitted_at: str = Field(min_length=1)


class FrostFinishSettlementResult(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    committed: bool
    idempotency_status: str = "rejected"
    error_code: str | None = None
    committed_event_ids: tuple[str, ...] = ()


class FrostProductionTarget(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run: ProductionRun
    stream_id: str = Field(min_length=1)
    expected_revision: int = Field(ge=0)


class FrostProductionTargetSelection(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted: bool
    target: FrostProductionTarget | None = None
    error_code: str | None = None


class ConstructionProductionProjector:
    _STARTED = "gameplay.construction_production.run_started"
    _FINISHED = "gameplay.construction_production.run_finished"
    _MAINTENANCE = "gameplay.construction_production.maintenance_obligation_created"
    _MAINTENANCE_STATE = "gameplay.construction_production.maintenance_state_applied"
    _MAINTENANCE_STATE_OPENED = "gameplay.construction_production.maintenance_state_obligation_opened"
    _MAINTENANCE_STATE_DISPELLED = "gameplay.construction_production.maintenance_state_dispelled"
    _MAINTENANCE_STATE_CANCELLED = "gameplay.construction_production.maintenance_state_obligation_cancelled"
    _MAINTENANCE_STATE_EXPIRED = "gameplay.construction_production.maintenance_state_expired"
    _ACQUIRED = "gameplay.construction_production.facility_acquired"
    _REPAIRED = "gameplay.construction_production.facility_repaired"
    _REPAIR_COMPENSATED = "gameplay.construction_production.facility_repair_compensated"
    _TRANSFORMED = "gameplay.construction_production.facility_transformed"

    def rebuild(
        self,
        events: Sequence[GameplayEvent],
        *,
        checkpoint: ConstructionProductionProjection | None = None,
    ) -> ConstructionProductionProjection:
        runs: dict[str, ProductionRun] = dict(checkpoint.runs) if checkpoint is not None else {}
        facilities: dict[str, Facility] = dict(checkpoint.facilities) if checkpoint is not None else {}
        revisions: dict[str, int] = dict(checkpoint.source_revision_vector) if checkpoint is not None else {}
        recipes_by_run: dict[str, CommittedProductionRecipe] = (
            dict(checkpoint.recipes_by_run) if checkpoint is not None else {}
        )
        maintenance_states: dict[str, ConstructionMaintenanceState] = (
            dict(checkpoint.maintenance_states) if checkpoint is not None else {}
        )
        for event in sorted(events, key=lambda value: (value.global_sequence, value.event_id)):
            if event.event_type not in {
                self._STARTED,
                self._FINISHED,
                self._MAINTENANCE,
                self._MAINTENANCE_STATE,
                self._MAINTENANCE_STATE_OPENED,
                self._MAINTENANCE_STATE_DISPELLED,
                self._MAINTENANCE_STATE_CANCELLED,
                self._MAINTENANCE_STATE_EXPIRED,
                self._ACQUIRED,
                self._REPAIRED,
                self._REPAIR_COMPENSATED,
                self._TRANSFORMED,
            }:
                continue
            payload = event.payload
            if event.event_type == self._ACQUIRED:
                facility_ref = str(payload.get("facility_ref", ""))
                if not facility_ref or facility_ref in facilities:
                    raise ValueError("facility_duplicate")
                facilities[facility_ref] = Facility(
                    facility_ref=facility_ref,
                    plot_ref=str(payload["plot_ref"]),
                    facility_kind=str(payload["facility_kind"]),
                    condition=float(payload["condition"]),
                    revision=int(payload.get("revision", 0)),
                )
                revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
                continue
            if event.event_type in {self._REPAIRED, self._REPAIR_COMPENSATED}:
                facility_ref = str(payload.get("facility_ref", ""))
                facility = facilities.get(facility_ref)
                if facility is None:
                    raise ValueError("facility_repair_target_missing")
                if event.event_type == self._REPAIRED:
                    prior = float(payload["prior_condition"])
                    next_condition = float(payload["next_condition"])
                else:
                    prior = float(payload["prior_condition"])
                    next_condition = float(payload["restored_condition"])
                if abs(facility.condition - prior) > 1e-9:
                    raise ValueError("facility_repair_condition_conflict")
                facilities[facility_ref] = facility.model_copy(
                    update={
                        "condition": next_condition,
                        "revision": int(payload["facility_revision"]),
                    },
                    deep=True,
                )
                revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
                continue
            if event.event_type == self._TRANSFORMED:
                facility_ref = str(payload.get("facility_ref", ""))
                facility = facilities.get(facility_ref)
                if facility is None:
                    raise ValueError("facility_transform_target_missing")
                legacy_bakery = (
                    payload.get("prior_kind") == "bakery"
                    and payload.get("next_kind") == "bakery_reinforced"
                )
                package_oven_kiln = (
                    payload.get("prior_kind") == "oven"
                    and payload.get("next_kind") == "kiln"
                    and payload.get("outcome_family") == "construction_facility_package_declared_transform@1"
                    and payload.get("capability_ref") == "capability:construction-facility-package-declared-transform@1"
                    and payload.get("package_revision") == "package:industrial-facilities:v1"
                    and payload.get("content_digest") == "sha256:41e1b40bcd1fd13e1692f2f51aed7dea6dceee0b1605bf215fe6c673fcd11f88"
                    and payload.get("declaration_ref") == "declaration:industrial-facilities-oven-to-kiln@1"
                    and payload.get("declaration_digest") == "sha256:04869873a57a24b834cc123a14440444717bdd482910eb9d8ae1d50cc3bc2ed8"
                    and payload.get("descriptor_ref") == "descriptor:construction-facility-package-declared-transform@1"
                    and payload.get("descriptor_revision") == "descriptor:construction-facility-package-declared-transform@1"
                    and payload.get("policy_revision") == "policy:industrial-facilities:oven-to-kiln@1"
                    and payload.get("project_ref") == facility.plot_ref
                )
                if (
                    not (legacy_bakery or package_oven_kiln)
                    or facility.facility_kind != payload["prior_kind"]
                    or facility.revision != int(payload["prior_facility_revision"])
                ):
                    raise ValueError("facility_transform_conflict")
                facilities[facility_ref] = facility.model_copy(
                    update={
                        "facility_kind": str(payload["next_kind"]),
                        "revision": int(payload["facility_revision"]),
                    },
                    deep=True,
                )
                revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
                continue
            if event.event_type == self._MAINTENANCE_STATE:
                facility_ref = str(payload.get("facility_ref", ""))
                if not facility_ref:
                    raise ValueError("construction_event_payload_invalid")
                maintenance_states[facility_ref] = ConstructionMaintenanceState(
                    state_ref=str(payload["state_ref"]),
                    effect_ref=str(payload["effect_ref"]),
                    stacks=int(payload["next_stacks"]),
                    effective_magnitude=int(payload["effective_magnitude"]),
                    resistance_revision=int(payload["resistance_revision"]),
                    semantic_snapshot_digest=str(payload["semantic_snapshot_digest"]),
                )
                revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
                continue
            if event.event_type == self._MAINTENANCE_STATE_OPENED:
                revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
                continue
            if event.event_type == self._MAINTENANCE_STATE_DISPELLED:
                facility_ref = str(payload.get("facility_ref", ""))
                if not facility_ref or facility_ref not in maintenance_states:
                    raise ValueError("construction_maintenance_state_dispel_invalid")
                maintenance_states.pop(facility_ref)
                revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
                continue
            if event.event_type == self._MAINTENANCE_STATE_CANCELLED:
                revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
                continue
            if event.event_type == self._MAINTENANCE_STATE_EXPIRED:
                facility_ref = str(payload.get("facility_ref", ""))
                if not facility_ref or facility_ref not in maintenance_states:
                    raise ValueError("construction_maintenance_state_expiry_invalid")
                maintenance_states.pop(facility_ref)
                revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
                continue
            run_ref = str(payload.get("run_ref", ""))
            if not run_ref:
                raise ValueError("construction_event_payload_invalid")
            if event.event_type == self._STARTED:
                if run_ref in runs:
                    raise ValueError("production_run_duplicate")
                runs[run_ref] = ProductionRun(
                    run_ref=run_ref,
                    facility_ref=str(payload["facility_ref"]),
                    recipe_ref=str(payload["recipe_ref"]),
                    started_tick=int(payload["started_tick"]),
                    finish_tick=int(payload["finish_tick"]),
                    reservation_refs=tuple(payload.get("reservation_refs", ())),
                    output_item=(str(payload["output_item"]) if payload.get("output_item") else None),
                    worker_contribution_refs=tuple(
                        str(item.get("contribution_digest", ""))
                        for item in payload.get("worker_contributions", ())
                        if isinstance(item, dict) and item.get("contribution_digest")
                    ),
                )
                recipe_snapshot = payload.get("recipe_snapshot")
                if recipe_snapshot is not None:
                    if not isinstance(recipe_snapshot, dict):
                        raise ValueError("construction_recipe_snapshot_invalid")
                    recipe = Recipe(
                        recipe_ref=str(recipe_snapshot["recipe_ref"]),
                        inputs={},
                        output_item=str(recipe_snapshot["output_item"]),
                        duration_ticks=int(recipe_snapshot["duration_ticks"]),
                    )
                    if recipe.recipe_ref != runs[run_ref].recipe_ref:
                        raise ValueError("construction_recipe_snapshot_mismatch")
                    recipes_by_run[run_ref] = CommittedProductionRecipe(
                        recipe=recipe,
                        source_stream_revision=event.stream_revision,
                    )
            elif event.event_type == self._FINISHED:
                run = runs.get(run_ref)
                if run is None or run.status != "started":
                    raise ValueError("production_run_missing")
                runs[run_ref] = run.model_copy(
                    update={"status": "completed", "output_item": str(payload["output_item"])}, deep=True
                )
            else:
                run = runs.get(run_ref)
                if run is None:
                    raise ValueError("production_run_missing")
                runs[run_ref] = run.model_copy(
                    update={"maintenance_obligation_ref": str(payload["obligation_ref"])}, deep=True
                )
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
        return ConstructionProductionProjection(
            runs=MappingProxyType(dict(sorted(runs.items()))),
            source_revision_vector=MappingProxyType(dict(sorted(revisions.items()))),
            facilities=MappingProxyType(dict(sorted(facilities.items()))),
            recipes_by_run=MappingProxyType(dict(sorted(recipes_by_run.items()))),
            maintenance_states=MappingProxyType(dict(sorted(maintenance_states.items()))),
        )


class ConstructionProductionAuthority:
    owner = "construction-production"
    _PRINCIPAL = "actor_gameplay.construction_production_domain"

    def __init__(self, *, store: GameplayEventStore, package_registry: object | None = None) -> None:
        self._store = store
        self._package_registry = package_registry
        self._projector = ConstructionProductionProjector()

    def commit_obligation_batch(self, batch: AtomicEventBatch) -> AppendBatchResult:
        """Commit only a Construction-owned lifecycle plan."""
        if not batch.owner_fragments or any(
            fragment.owner_principal_ref != self._PRINCIPAL
            or any(not event.stream_id.startswith("gameplay:construction_production:") for event in batch.events)
            for fragment in batch.owner_fragments
        ):
            return self._rejected_append(batch.command_id, "construction_owner_commit_scope_denied")
        event_types = tuple(event.event_type for event in batch.events)
        if any(".maintenance_state_" in event_type for event_type in event_types):
            try:
                GovernedAuthorityContractCatalog.require_operation(
                    contract_ref="inf:construction-maintenance-state-expiry@1",
                    contract_kind="lifecycle",
                    owner_ref=self._PRINCIPAL,
                    stream_ids=tuple(sorted({event.stream_id for event in batch.events})),
                    event_types=event_types,
                    projection_scope="project",
                )
            except GovernedAuthorityContractError as error:
                return self._rejected_append(batch.command_id, str(error))
        return self._store.append_batch(batch)

    @staticmethod
    def facility_package_transform_receipt_for(
        *, result: AppendBatchResult | None, scope: str
    ) -> SettlementReceipt:
        if scope != "project":
            raise ValueError("construction_facility_transform_receipt_scope_denied")
        if result is None:
            raise ValueError("construction_facility_transform_receipt_missing")
        return SettlementReceipt.from_append_result(
            result=result,
            audit_refs=(f"construction_transaction:{result.transaction_id}",),
        )

    def projector(self, *, checkpoint_at: int | None = None) -> ConstructionProductionProjection:
        events = self._store.read_events()
        if checkpoint_at is None:
            return self._projector.rebuild(events)
        checkpoint = self._projector.rebuild(events[:checkpoint_at])
        return self._projector.rebuild(events[checkpoint_at:], checkpoint=checkpoint)

    def transform_facility_from_package(
        self, intent: PackageDeclaredFacilityTransformIntentV1
    ) -> AppendBatchResult:
        """Commit the frozen industrial ``oven -> kiln`` operation only.

        The package and descriptor are read-only inputs from the active patch
        set. The caller supplies only a typed facility/evidence reference.
        """
        command_id = intent.command_id
        package_revision = "package:industrial-facilities:v1"
        capability_ref = "capability:construction-facility-package-declared-transform@1"
        binding_ref = "binding:industrial-facilities-oven-to-kiln@1"
        descriptor_ref = "descriptor:construction-facility-package-declared-transform@1"
        descriptor_revision = descriptor_ref
        outcome_family = "construction_facility_package_declared_transform@1"
        outcome_family_ref = "outcome:construction-facility-package-declared-transform@1"
        event_type = "gameplay.construction_production.facility_transformed"
        stream_id = f"gameplay:construction_production:{intent.facility_ref}"

        registry = self._package_registry
        active = getattr(registry, "active_patch_set", None) if registry is not None else None
        if active is None:
            return self._rejected_append(command_id, "construction_facility_transform_package_inactive")
        try:
            manifests = registry.active_manifests(active.active_patch_set_revision)
        except Exception:
            return self._rejected_append(command_id, "construction_facility_transform_package_inactive")
        package_matches = tuple(
            manifest
            for manifest in manifests
            if manifest.patch_id == "package:industrial-facilities"
            and manifest.patch_revision_id == package_revision
        )
        if not package_matches:
            return self._rejected_append(command_id, "construction_facility_transform_package_unknown")
        if len(package_matches) != 1:
            return self._rejected_append(command_id, "construction_facility_transform_package_ambiguous")
        manifest = package_matches[0]
        if manifest.content_digest != "sha256:41e1b40bcd1fd13e1692f2f51aed7dea6dceee0b1605bf215fe6c673fcd11f88":
            return self._rejected_append(command_id, "construction_facility_transform_digest_mismatch")
        extension = manifest.platform_extension
        if extension is None:
            return self._rejected_append(command_id, "construction_facility_transform_binding_unknown")
        declarations = tuple(
            declaration
            for declaration in extension.outcome_declarations
            if declaration.declaration_ref == "declaration:industrial-facilities-oven-to-kiln@1"
        )
        requests = tuple(
            request
            for request in extension.capability_binding_requests
            if request.binding_ref == binding_ref
        )
        bindings = tuple(binding for binding in active.capability_bindings if binding.binding_ref == binding_ref)
        if len(declarations) != 1 or len(requests) != 1:
            return self._rejected_append(command_id, "construction_facility_transform_binding_unknown")
        if len(bindings) != 1:
            return self._rejected_append(
                command_id,
                "construction_facility_transform_binding_ambiguous" if len(bindings) > 1 else "construction_facility_transform_binding_unadmitted",
            )
        declaration = declarations[0]
        request = requests[0]
        binding = bindings[0]
        if (
            declaration.outcome_family_ref != outcome_family_ref
            or declaration.policy_revision_ref != "policy:industrial-facilities:oven-to-kiln@1"
            or declaration.eligibility_refs != ("construction:facility-acquired@1",)
            or request.capability_ref != capability_ref
            or request.declaration_ref != declaration.declaration_ref
            or tuple(requirement.predicate_family_ref for requirement in request.typed_read_requirements)
            != ("predicate:construction-facility-acquired@1",)
            or request.proposal_effect_types != ("effect:construction-facility-package-declared-transform@1",)
            or binding.package_revision != package_revision
            or binding.content_digest != manifest.content_digest
            or binding.declaration_digest != declaration.declaration_digest
            or binding.descriptor_ref != descriptor_ref
            or binding.descriptor_revision != descriptor_revision
        ):
            return self._rejected_append(command_id, "construction_facility_transform_binding_conflict")

        canonical_idempotency_key = (
            f"construction:facility-transform:{package_revision}:{manifest.content_digest}:"
            f"{intent.facility_ref}:{intent.acquisition_event_id}"
        )
        if intent.idempotency_key != canonical_idempotency_key:
            return self._rejected_append(command_id, "construction_facility_transform_idempotency_key_invalid")
        existing = self._store.get_by_idempotency(self._PRINCIPAL, intent.idempotency_key)
        if existing is not None:
            prior = next(
                (event for event in self._store.read_events() if event.event_id in set(existing.committed_event_ids)),
                None,
            )
            if prior is not None and prior.event_type == event_type and (
                prior.payload.get("facility_ref") == intent.facility_ref
                and prior.payload.get("acquisition_event_id") == intent.acquisition_event_id
                and prior.payload.get("expected_stream_revision") == intent.expected_revision
                and prior.payload.get("prior_facility_revision") == intent.expected_facility_revision
                and prior.causation_id == intent.causation_id
                and prior.correlation_id == intent.correlation_id
            ):
                return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            return self._rejected_append(command_id, "idempotency_key_reused")
        try:
            acquisition_event = self._store.get_event(intent.acquisition_event_id)
        except KeyError:
            return self._rejected_append(command_id, "construction_facility_transform_source_missing")
        if (
            acquisition_event.event_type != "gameplay.construction_production.facility_acquired"
            or acquisition_event.stream_id != stream_id
            or acquisition_event.visibility_policy != "project"
            or acquisition_event.payload.get("facility_ref") != intent.facility_ref
            or acquisition_event.payload.get("facility_kind") != "oven"
        ):
            return self._rejected_append(command_id, "construction_facility_transform_source_invalid")
        projection = self.projector()
        facility = projection.facilities.get(intent.facility_ref)
        if facility is None or facility.facility_kind != "oven":
            return self._rejected_append(command_id, "construction_facility_transform_target_invalid")
        if facility.plot_ref != acquisition_event.payload.get("plot_ref"):
            return self._rejected_append(command_id, "construction_facility_transform_binding_conflict")
        if facility.revision != intent.expected_facility_revision:
            return self._rejected_append(command_id, "construction_facility_transform_facility_revision_conflict")
        if self._store.get_stream_head(stream_id) != intent.expected_revision:
            return self._rejected_append(command_id, "revision_conflict")
        if acquisition_event.stream_revision <= 0:
            return self._rejected_append(command_id, "construction_facility_transform_source_revision_conflict")
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:construction-facility-package-declared-transform@1",
                contract_kind="settlement",
                owner_ref=self._PRINCIPAL,
                stream_ids=(stream_id,),
                event_types=(event_type,),
                projection_scope="project",
            )
        except GovernedAuthorityContractError as error:
            return self._rejected_append(command_id, str(error))

        envelope = GameplayCommandEnvelope(
            command_id=command_id,
            command_type="gameplay.construction_production.package_declared_facility_transform",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=intent.facility_ref,
            project_ref=str(acquisition_event.payload["plot_ref"]),
            transaction_id=f"transaction:{command_id}",
            idempotency_key=intent.idempotency_key,
            expected_revisions={stream_id: intent.expected_revision},
            causation_id=intent.causation_id,
            correlation_id=intent.correlation_id,
            source_ref=intent.acquisition_event_id,
            submitted_at=intent.submitted_at,
            pinned_revisions={
                "acquisition_event": acquisition_event.stream_revision,
                "facility": intent.expected_facility_revision,
                "active_patch_set": 1,
            },
            payload={
                "stream_ref": stream_id,
                "event_type": event_type,
                "visibility_policy": "project",
                "owner_principal_ref": self._PRINCIPAL,
                "facility_ref": intent.facility_ref,
                "project_ref": acquisition_event.payload["plot_ref"],
                "acquisition_event_id": intent.acquisition_event_id,
                "acquisition_event_revision": acquisition_event.stream_revision,
                "expected_stream_revision": intent.expected_revision,
                "prior_kind": "oven",
                "next_kind": "kiln",
                "prior_facility_revision": intent.expected_facility_revision,
                "facility_revision": intent.expected_facility_revision + 1,
                "package_id": manifest.patch_id,
                "package_revision": package_revision,
                "content_digest": manifest.content_digest,
                "declaration_ref": declaration.declaration_ref,
                "declaration_digest": declaration.declaration_digest,
                "descriptor_ref": descriptor_ref,
                "descriptor_revision": descriptor_revision,
                "active_patch_set_revision": active.active_patch_set_revision,
                "capability_ref": capability_ref,
                "outcome_family": outcome_family,
                "policy_revision": declaration.policy_revision_ref,
                "eligibility_ref": "construction:facility-acquired@1",
                "predicate_family_ref": "predicate:construction-facility-acquired@1",
                "terminal": "v1_terminal_no_compensation",
            },
        )
        batch = SettlementPlan.from_command_envelope(envelope).to_atomic_event_batch()
        event = batch.events[0]
        batch = batch.model_copy(
            update={
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}",
                        transaction_id=batch.transaction_id,
                        event_id=event.event_id,
                        global_sequence=0,
                        topic="construction_production.scoped_projection",
                        audience="project",
                        payload_projection={
                            "facility_ref": intent.facility_ref,
                            "project_ref": acquisition_event.payload["plot_ref"],
                            "next_kind": "kiln",
                        },
                    )
                ]
            },
            deep=True,
        )
        return self._store.append_batch(batch)

    def select_due_run_for_plot(
        self, *, plot_ref: str, due_tick: int, checkpoint_at: int | None = None
    ) -> FrostProductionTargetSelection:
        projection = self.projector(checkpoint_at=checkpoint_at)
        candidates = [
            run
            for run in projection.runs.values()
            if run.status == "started"
            and run.finish_tick <= due_tick
            and (facility := projection.facilities.get(run.facility_ref)) is not None
            and facility.plot_ref == plot_ref
        ]
        active_on_plot = [
            run
            for run in projection.runs.values()
            if run.status == "started"
            and (facility := projection.facilities.get(run.facility_ref)) is not None
            and facility.plot_ref == plot_ref
        ]
        if not active_on_plot:
            return FrostProductionTargetSelection(accepted=False, error_code="frost_production_target_missing")
        if not candidates:
            return FrostProductionTargetSelection(accepted=False, error_code="frost_production_target_not_due")
        if len(candidates) != 1:
            return FrostProductionTargetSelection(accepted=False, error_code="frost_production_target_ambiguous")
        run = candidates[0]
        stream_id = f"gameplay:construction_production:{run.facility_ref}"
        return FrostProductionTargetSelection(
            accepted=True,
            target=FrostProductionTarget(
                run=run,
                stream_id=stream_id,
                expected_revision=projection.source_revision_vector[stream_id],
            ),
        )

    def recipe_for_run(
        self,
        *,
        run_ref: str,
        expected_source_revision: int,
        scope: Literal["public", "authority"] = "public",
        checkpoint_at: int | None = None,
    ) -> ProductionRecipeResult:
        if scope != "authority":
            return ProductionRecipeResult(accepted=False, error_code="construction_recipe_scope_denied")
        projection = self.projector(checkpoint_at=checkpoint_at)
        if run_ref not in projection.runs:
            return ProductionRecipeResult(accepted=False, error_code="construction_recipe_missing")
        recipe = projection.recipes_by_run.get(run_ref)
        if recipe is None:
            return ProductionRecipeResult(accepted=False, error_code="construction_recipe_snapshot_missing")
        if recipe.source_stream_revision != expected_source_revision:
            return ProductionRecipeResult(accepted=False, error_code="construction_recipe_revision_conflict")
        return ProductionRecipeResult(accepted=True, recipe=recipe)

    def settle_frost_due_finish(
        self,
        command: ConstructionFrostFinishCommand,
        *,
        retry_policy: Mapping[str, object] | None = None,
        compensation_policy: Mapping[str, object] | None = None,
    ) -> FrostFinishSettlementResult:
        if retry_policy:
            return FrostFinishSettlementResult(committed=False, error_code="frost_production_retry_unsupported")
        if compensation_policy:
            return FrostFinishSettlementResult(committed=False, error_code="frost_production_compensation_unsupported")
        if command.privacy_scope != "project":
            return FrostFinishSettlementResult(committed=False, error_code="frost_production_privacy_scope_denied")
        try:
            source_event = self._store.get_event(command.source_event_id)
        except KeyError:
            return FrostFinishSettlementResult(committed=False, error_code="frost_production_source_missing")
        if not self._matches_committed_frost_source(source_event, command):
            return FrostFinishSettlementResult(committed=False, error_code="frost_production_source_revision_conflict")
        idempotency_key = f"frost-production:{command.source_event_id}"
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None:
            return FrostFinishSettlementResult(
                committed=existing.committed,
                idempotency_status="duplicate_replayed",
                error_code=existing.failure.error_code if existing.failure else None,
                committed_event_ids=tuple(existing.committed_event_ids),
            )
        selection = self.select_due_run_for_plot(plot_ref=command.plot_ref, due_tick=command.due_tick)
        if not selection.accepted or selection.target is None:
            return FrostFinishSettlementResult(committed=False, error_code=selection.error_code)
        target = selection.target
        projection = self.projector()
        recipe_source = projection.recipes_by_run.get(target.run.run_ref)
        if recipe_source is None:
            return FrostFinishSettlementResult(committed=False, error_code="frost_production_recipe_missing")
        try:
            fragment = self.build_due_finish_fragment(
                run=target.run,
                recipe=recipe_source.recipe,
                tick=command.due_tick,
                expected_revision=target.expected_revision,
            )
        except ValueError as exc:
            return FrostFinishSettlementResult(committed=False, error_code=str(exc))
        stream_id = target.stream_id
        payload = fragment.event_specs[stream_id][0][1]
        propagation = command.model_dump(mode="json")
        fragment = fragment.model_copy(
            update={
                "fragment_id": f"{fragment.fragment_id}:frost:{command.source_event_id}",
                "source_rule_ref": "ecology:frost-production-finish:v1",
                "read_set_revisions": {command.crop_ref: command.source_stream_revision},
                "pinned_revisions": {
                    **fragment.pinned_revisions,
                    "frost_source": command.source_stream_revision,
                    "recipe_source": recipe_source.source_stream_revision,
                },
                "event_specs": {stream_id: (("gameplay.construction_production.run_finished", {**payload, "frost_propagation": propagation}),)},
            },
            deep=True,
        )
        batch = build_multi_stream_atomic_event_batch_from_fragments(
            command_id=f"command:frost-production:{command.source_event_id}:{target.run.run_ref}",
            idempotency_principal_ref=self._PRINCIPAL,
            idempotency_key=idempotency_key,
            causation_id=command.source_event_id,
            correlation_id=f"frost-production:{command.hazard_ref}:{target.run.run_ref}",
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
                        topic="construction_production.scoped_projection",
                        audience="project",
                        payload_projection={
                            "facility_ref": target.run.facility_ref,
                            "run_ref": target.run.run_ref,
                            "completed_tick": command.due_tick,
                        },
                    )
                ]
            },
            deep=True,
        )
        result = self._store.append_batch(batch)
        return FrostFinishSettlementResult(
            committed=result.committed,
            idempotency_status=result.idempotency_status,
            error_code=result.failure.error_code if result.failure else None,
            committed_event_ids=tuple(result.committed_event_ids),
        )

    def settle_canonical_frost_due_finish(
        self, command: CanonicalFrostProductionFinishCommand, *, admission: object | None = None
    ) -> FrostFinishSettlementResult:
        if command.edge_ref != "ecology-hazard:frost-to-construction-finish:v1":
            return FrostFinishSettlementResult(committed=False, error_code="canonical_hazard_edge_unsupported")
        if not command.enabled:
            return FrostFinishSettlementResult(committed=False, error_code="canonical_hazard_edge_disabled")
        if (
            admission is None
            or not _CONTAINS_CANONICAL_HAZARD_ADMISSION(admission)
            or getattr(admission, "edge_ref", None) != command.edge_ref
            or getattr(admission, "hazard_event_id", None) != command.hazard_event_id
            or getattr(admission, "crop_event_id", None) != command.crop_event_id
        ):
            return FrostFinishSettlementResult(committed=False, error_code="canonical_hazard_admission_required")
        if command.source_authority_ref != "authority:ecology":
            return FrostFinishSettlementResult(committed=False, error_code="canonical_hazard_source_authority_required")
        if command.privacy_scope != "project":
            return FrostFinishSettlementResult(committed=False, error_code="canonical_hazard_privacy_scope_denied")
        if self._store.get_stream_head(command.ecology_stream_id) != command.ecology_stream_revision:
            return FrostFinishSettlementResult(committed=False, error_code="canonical_hazard_source_revision_conflict")
        try:
            hazard_event = self._store.get_event(command.hazard_event_id)
            crop_event = self._store.get_event(command.crop_event_id)
        except KeyError:
            return FrostFinishSettlementResult(committed=False, error_code="canonical_hazard_source_missing")
        if not self._matches_canonical_frost_source(hazard_event, crop_event, command):
            return FrostFinishSettlementResult(committed=False, error_code="canonical_hazard_source_revision_conflict")
        existing = self._store.get_by_idempotency(self._PRINCIPAL, command.idempotency_key)
        if existing is not None:
            return FrostFinishSettlementResult(committed=existing.committed, idempotency_status="duplicate_replayed", error_code=existing.failure.error_code if existing.failure else None, committed_event_ids=tuple(existing.committed_event_ids))
        selection = self.select_due_run_for_plot(plot_ref=command.plot_ref, due_tick=command.due_tick)
        if not selection.accepted or selection.target is None:
            return FrostFinishSettlementResult(committed=False, error_code=selection.error_code)
        target = selection.target
        recipe_source = self.projector().recipes_by_run.get(target.run.run_ref)
        if recipe_source is None:
            return FrostFinishSettlementResult(committed=False, error_code="canonical_hazard_recipe_missing")
        fragment = self.build_due_finish_fragment(run=target.run, recipe=recipe_source.recipe, tick=command.due_tick, expected_revision=target.expected_revision)
        payload = fragment.event_specs[target.stream_id][0][1]
        fragment = fragment.model_copy(update={
            "fragment_id": f"{fragment.fragment_id}:canonical-hazard:{command.hazard_event_id}",
            "source_rule_ref": command.edge_ref,
            "read_set_revisions": {command.ecology_stream_id: command.ecology_stream_revision},
            "pinned_revisions": {**fragment.pinned_revisions, "hazard_event": command.hazard_event_revision, "crop_event": command.crop_event_revision, "ecology_head": command.ecology_stream_revision, "recipe_source": recipe_source.source_stream_revision},
            "event_specs": {target.stream_id: (("gameplay.construction_production.run_finished", {**payload, "canonical_hazard_propagation": command.model_dump(mode="json")}),)},
            "event_visibility_policies": {target.stream_id: ("project",)},
        }, deep=True)
        batch = build_multi_stream_atomic_event_batch_from_fragments(command_id=f"command:{command.idempotency_key}:{target.run.run_ref}", idempotency_principal_ref=self._PRINCIPAL, idempotency_key=command.idempotency_key, causation_id=command.hazard_event_id, correlation_id=f"canonical-hazard:{command.hazard_ref}:{target.run.run_ref}", fragments=(fragment,))
        event = batch.events[0]
        batch = batch.model_copy(update={"outbox_entries": [GameplayOutboxEntry(outbox_id=f"outbox:{event.event_id}", transaction_id=batch.transaction_id, event_id=event.event_id, global_sequence=0, topic="construction_production.scoped_projection", audience="project", payload_projection={"facility_ref": target.run.facility_ref, "run_ref": target.run.run_ref, "completed_tick": command.due_tick})]}, deep=True)
        result = self._store.append_batch(batch)
        return FrostFinishSettlementResult(committed=result.committed, idempotency_status=result.idempotency_status, error_code=result.failure.error_code if result.failure else None, committed_event_ids=tuple(result.committed_event_ids))

    @staticmethod
    def _matches_canonical_frost_source(hazard_event: GameplayEvent, crop_event: GameplayEvent, command: CanonicalFrostProductionFinishCommand) -> bool:
        hazard = hazard_event.payload.get("record")
        crop = crop_event.payload.get("record")
        return bool(
            hazard_event.event_type == "gameplay.ecology.hazard.recorded"
            and crop_event.event_type == "gameplay.ecology.crop.recorded"
            and hazard_event.visibility_policy == crop_event.visibility_policy == "project"
            and hazard_event.stream_id == crop_event.stream_id == command.ecology_stream_id
            and hazard_event.stream_revision == command.hazard_event_revision
            and crop_event.stream_revision == command.crop_event_revision
            and isinstance(hazard, dict) and isinstance(crop, dict)
            and hazard.get("hazard_ref") == command.hazard_ref
            and hazard.get("source_crop_ref") == command.crop_ref
            and crop.get("crop_ref") == command.crop_ref
            and crop.get("plot_ref") == command.plot_ref
            and hazard.get("region_ref") == crop.get("region_ref") == command.region_ref
            and hazard.get("effect_ref") == command.effect_ref == "effect:frost"
            and hazard.get("due_tick") == command.due_tick
            and tuple(hazard.get("causal_parent_refs", ())) == command.causal_parent_refs
        )

    def canonical_frost_finish_projection(self, *, scope: Literal["public", "authority"] = "public") -> dict[str, object]:
        facts = [event.payload for event in self._store.read_events() if event.event_type == "gameplay.construction_production.run_finished" and "canonical_hazard_propagation" in event.payload]
        return {
            "finished_runs": tuple({"facility_ref": str(payload["facility_ref"]), "run_ref": str(payload["run_ref"]), "completed_tick": int(payload["completed_tick"])} for payload in facts),
            "canonical_hazard_propagation": tuple(dict(payload["canonical_hazard_propagation"]) for payload in facts) if scope == "authority" else (),
        }

    def canonical_frost_replay(self, *, checkpoint_at: int | None = None):
        replay = GameplayProjectionReplay(projector_id="infra-hazard-propagation", projector_version="1")
        events = self._store.read_events()
        if checkpoint_at is None:
            return replay.full_replay(events)
        checkpoint = replay.create_checkpoint(events[:checkpoint_at])
        return replay.checkpoint_plus_tail_replay(checkpoint, events[checkpoint_at:])

    @staticmethod
    def _matches_committed_frost_source(event: GameplayEvent, command: ConstructionFrostFinishCommand) -> bool:
        payload = event.payload
        return (
            event.event_type == "semantic.effect.settled"
            and event.stream_id == command.crop_ref
            and event.stream_revision == command.source_stream_revision
            and payload.get("effect_ref") == "effect:frost"
            and payload.get("hazard_ref") == command.hazard_ref
            and payload.get("region_ref") == command.region_ref
            and payload.get("plot_ref") == command.plot_ref
            and payload.get("due_tick") == command.due_tick
            and payload.get("semantic_revision") == command.semantic_revision
            and payload.get("rule_revision") == command.rule_revision
            and payload.get("policy_revision") == command.policy_revision
            and payload.get("hazard_privacy_scope") == command.privacy_scope
            and tuple(payload.get("causal_parent_refs", ())) == command.causal_parent_refs
        )

    def frost_finish_projection(self, *, scope: Literal["public", "authority"] = "public") -> dict[str, object]:
        facts = [
            event.payload
            for event in self._store.read_events()
            if event.event_type == "gameplay.construction_production.run_finished"
            and "frost_propagation" in event.payload
        ]
        public = tuple(
            {
                "facility_ref": str(payload["facility_ref"]),
                "run_ref": str(payload["run_ref"]),
                "completed_tick": int(payload["completed_tick"]),
            }
            for payload in facts
        )
        return {
            "finished_runs": public,
            "frost_propagation": tuple(dict(payload["frost_propagation"]) for payload in facts) if scope == "authority" else (),
        }

    def replay_projection(self, *, checkpoint_at: int | None = None):
        replay = GameplayProjectionReplay(projector_id="infra-regional-ecology", projector_version="1")
        events = self._store.read_events()
        if checkpoint_at is None:
            return replay.full_replay(events)
        checkpoint = replay.create_checkpoint(events[:checkpoint_at])
        return replay.checkpoint_plus_tail_replay(checkpoint, events[checkpoint_at:])

    def reinforce_bakery_facility(
        self,
        *,
        facility_ref: str,
        acquisition_event_id: str,
        expected_revision: int,
        expected_facility_revision: int,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        submitted_at: str,
    ) -> AppendBatchResult:
        """Append the one admitted, terminal ``bakery -> bakery_reinforced`` fact."""
        command_id = f"construction:bakery-reinforcement:{facility_ref}:{acquisition_event_id}"
        canonical_idempotency_key = (
            f"facility-transform:bakery-reinforcement:{facility_ref}:{acquisition_event_id}:v1"
        )
        if idempotency_key != canonical_idempotency_key:
            return self._rejected_append(
                command_id,
                "construction_bakery_reinforcement_idempotency_key_invalid",
            )
        stream_id = f"gameplay:construction_production:{facility_ref}"
        try:
            acquisition_event = self._store.get_event(acquisition_event_id)
        except KeyError:
            return self._rejected_append(command_id, "construction_bakery_reinforcement_source_missing")
        if (
            acquisition_event.event_type != "gameplay.construction_production.facility_acquired"
            or acquisition_event.stream_id != stream_id
            or acquisition_event.visibility_policy != "project"
            or acquisition_event.payload.get("facility_ref") != facility_ref
            or acquisition_event.payload.get("facility_kind") != "bakery"
        ):
            return self._rejected_append(command_id, "construction_bakery_reinforcement_source_kind_invalid")

        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None:
            prior = next(
                (
                    event
                    for event in self._store.read_events()
                    if event.event_id in set(existing.committed_event_ids)
                ),
                None,
            )
            if prior is not None and prior.event_type == "gameplay.construction_production.facility_transformed" and (
                prior.payload.get("facility_ref") == facility_ref
                and prior.payload.get("acquisition_event_id") == acquisition_event_id
                and prior.payload.get("acquisition_event_revision") == acquisition_event.stream_revision
                and prior.payload.get("expected_stream_revision") == expected_revision
                and prior.payload.get("prior_facility_revision") == expected_facility_revision
                and prior.causation_id == causation_id
                and prior.correlation_id == correlation_id
            ):
                return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            return self._rejected_append(command_id, "idempotency_key_reused")

        projection = self.projector()
        facility = projection.facilities.get(facility_ref)
        if facility is None or facility.facility_kind != "bakery":
            return self._rejected_append(command_id, "construction_bakery_reinforcement_target_invalid")
        if facility.plot_ref != acquisition_event.payload.get("plot_ref"):
            return self._rejected_append(command_id, "construction_bakery_reinforcement_source_binding_invalid")
        if facility.revision != expected_facility_revision:
            return self._rejected_append(
                command_id,
                "construction_bakery_reinforcement_facility_revision_conflict",
            )
        if self._store.get_stream_head(stream_id) != expected_revision:
            return self._rejected_append(command_id, "revision_conflict")
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:construction-facility-bakery-reinforcement@1",
                contract_kind="settlement",
                owner_ref=self._PRINCIPAL,
                stream_ids=(stream_id,),
                event_types=("gameplay.construction_production.facility_transformed",),
                projection_scope="project",
            )
        except GovernedAuthorityContractError as error:
            return self._rejected_append(command_id, str(error))

        envelope = GameplayCommandEnvelope(
            command_id=command_id,
            command_type="gameplay.construction_production.reinforce_bakery_facility",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=facility_ref,
            project_ref=None,
            transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key,
            expected_revisions={stream_id: expected_revision},
            causation_id=causation_id,
            correlation_id=correlation_id,
            source_ref=acquisition_event_id,
            submitted_at=submitted_at,
            pinned_revisions={
                "acquisition_event": acquisition_event.stream_revision,
                "facility": expected_facility_revision,
                "transform_policy": 1,
            },
            payload={
                "stream_ref": stream_id,
                "event_type": "gameplay.construction_production.facility_transformed",
                "visibility_policy": "project",
                "owner_principal_ref": self._PRINCIPAL,
                "facility_ref": facility_ref,
                "acquisition_event_id": acquisition_event_id,
                "acquisition_event_revision": acquisition_event.stream_revision,
                "expected_stream_revision": expected_revision,
                "prior_kind": "bakery",
                "next_kind": "bakery_reinforced",
                "prior_facility_revision": expected_facility_revision,
                "facility_revision": expected_facility_revision + 1,
                "transform_policy_ref": "policy:construction_bakery_reinforcement",
                "transform_policy_revision": "1",
            },
        )
        batch = SettlementPlan.from_command_envelope(envelope).to_atomic_event_batch()
        event = batch.events[0]
        batch = batch.model_copy(
            update={
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}",
                        transaction_id=batch.transaction_id,
                        event_id=event.event_id,
                        global_sequence=0,
                        topic="construction_production.scoped_projection",
                        audience="project",
                        payload_projection={
                            "facility_ref": facility_ref,
                            "next_kind": "bakery_reinforced",
                        },
                    )
                ],
            },
            deep=True,
        )
        return self._store.append_batch(batch)

    def settle_facility_repair(
        self,
        *,
        facility_ref: str,
        repair_ref: str,
        repair_amount: float,
        expected_revision: int,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        source_ref: str,
        submitted_at: str,
        privacy_scope: str,
    ) -> AppendBatchResult:
        """Append one Construction-owned, reversible facility repair."""
        if privacy_scope != "project":
            return self._rejected_append(f"construction:repair:{repair_ref}", "construction_repair_privacy_scope_denied")
        if repair_amount <= 0 or repair_amount > 1:
            return self._rejected_append(f"construction:repair:{repair_ref}", "construction_repair_amount_invalid")
        stream_id = f"gameplay:construction_production:{facility_ref}"
        projection = self.projector()
        facility = projection.facilities.get(facility_ref)
        if facility is None:
            return self._rejected_append(f"construction:repair:{repair_ref}", "construction_repair_target_missing")
        command_id = f"construction:repair:{repair_ref}"
        envelope = GameplayCommandEnvelope(
            command_id=command_id,
            command_type="gameplay.construction_production.repair_facility",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=facility_ref,
            project_ref=None,
            transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key,
            expected_revisions={stream_id: expected_revision},
            causation_id=causation_id,
            correlation_id=correlation_id,
            source_ref=source_ref,
            submitted_at=submitted_at,
            pinned_revisions={"facility": facility.revision},
            payload={
                "stream_ref": stream_id,
                "event_type": "gameplay.construction_production.facility_repaired",
                "visibility_policy": "project",
                "owner_principal_ref": self._PRINCIPAL,
                "facility_ref": facility_ref,
                "repair_ref": repair_ref,
                "prior_condition": facility.condition,
                "next_condition": min(1.0, facility.condition + repair_amount),
                "repair_amount": repair_amount,
                "facility_revision": facility.revision + 1,
            },
        )
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None:
            prior = next(
                (event for event in self._store.read_events() if event.event_id in set(existing.committed_event_ids)),
                None,
            )
            if prior is not None and prior.event_type == "gameplay.construction_production.facility_repaired" and (
                prior.payload.get("facility_ref") == facility_ref
                and prior.payload.get("repair_ref") == repair_ref
                and prior.payload.get("repair_amount") == repair_amount
                and prior.causation_id == causation_id
                and prior.correlation_id == correlation_id
            ):
                return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            return self._rejected_append(command_id, "idempotency_key_reused")
        if self._store.get_stream_head(stream_id) != expected_revision:
            return self._rejected_append(command_id, "revision_conflict")
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:construction-facility-repair@1",
                contract_kind="settlement",
                owner_ref=self._PRINCIPAL,
                stream_ids=(stream_id,),
                event_types=("gameplay.construction_production.facility_repaired",),
                projection_scope="project",
            )
        except GovernedAuthorityContractError as error:
            return self._rejected_append(command_id, str(error))
        batch = SettlementPlan.from_command_envelope(envelope).to_atomic_event_batch()
        event = batch.events[0]
        batch = batch.model_copy(
            update={
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}",
                        transaction_id=batch.transaction_id,
                        event_id=event.event_id,
                        global_sequence=0,
                        topic="construction_production.scoped_projection",
                        audience="project",
                        payload_projection={"facility_ref": facility_ref, "condition": envelope.payload["next_condition"]},
                    )
                ],
            },
            deep=True,
        )
        return self._store.append_batch(batch)

    def compensate_facility_repair(
        self,
        *,
        repair_event_id: str,
        expected_revision: int,
        reason_ref: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        source_ref: str,
        submitted_at: str,
        privacy_scope: str,
    ) -> AppendBatchResult:
        if privacy_scope != "project":
            return self._rejected_append(f"construction:repair-compensate:{repair_event_id}", "construction_repair_privacy_scope_denied")
        try:
            repair_event = self._store.get_event(repair_event_id)
        except KeyError:
            return self._rejected_append(f"construction:repair-compensate:{repair_event_id}", "construction_repair_source_missing")
        if repair_event.event_type != "gameplay.construction_production.facility_repaired" or repair_event.visibility_policy != "project":
            return self._rejected_append(f"construction:repair-compensate:{repair_event_id}", "construction_repair_source_invalid")
        facility_ref = str(repair_event.payload.get("facility_ref", ""))
        stream_id = f"gameplay:construction_production:{facility_ref}"
        command_id = f"construction:repair-compensate:{repair_event_id}"
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None:
            prior = next(
                (event for event in self._store.read_events() if event.event_id in set(existing.committed_event_ids)),
                None,
            )
            if prior is not None and prior.event_type == "gameplay.construction_production.facility_repair_compensated" and (
                prior.payload.get("repair_event_id") == repair_event_id
                and prior.payload.get("reason_ref") == reason_ref
                and prior.causation_id == causation_id
                and prior.correlation_id == correlation_id
            ):
                return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            return self._rejected_append(command_id, "idempotency_key_reused")
        projection = self.projector()
        facility = projection.facilities.get(facility_ref)
        if facility is None or facility.condition != float(repair_event.payload.get("next_condition", -1)):
            return self._rejected_append(f"construction:repair-compensate:{repair_event_id}", "construction_repair_compensation_not_current")
        envelope = GameplayCommandEnvelope(
            command_id=command_id,
            command_type="gameplay.construction_production.compensate_facility_repair",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=facility_ref,
            project_ref=None,
            transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key,
            expected_revisions={stream_id: expected_revision},
            causation_id=causation_id,
            correlation_id=correlation_id,
            source_ref=source_ref,
            submitted_at=submitted_at,
            pinned_revisions={"repair_event": repair_event.stream_revision},
            payload={
                "stream_ref": stream_id,
                "event_type": "gameplay.construction_production.facility_repair_compensated",
                "visibility_policy": "project",
                "owner_principal_ref": self._PRINCIPAL,
                "facility_ref": facility_ref,
                "repair_event_id": repair_event_id,
                "prior_condition": facility.condition,
                "restored_condition": float(repair_event.payload["prior_condition"]),
                "facility_revision": facility.revision + 1,
                "reason_ref": reason_ref,
            },
        )
        if self._store.get_stream_head(stream_id) != expected_revision:
            return self._rejected_append(command_id, "revision_conflict")
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:construction-facility-repair@1",
                contract_kind="settlement",
                owner_ref=self._PRINCIPAL,
                stream_ids=(stream_id,),
                event_types=("gameplay.construction_production.facility_repair_compensated",),
                projection_scope="project",
            )
        except GovernedAuthorityContractError as error:
            return self._rejected_append(command_id, str(error))
        batch = SettlementPlan.from_command_envelope(envelope).to_atomic_event_batch()
        event = batch.events[0]
        batch = batch.model_copy(
            update={
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}",
                        transaction_id=batch.transaction_id,
                        event_id=event.event_id,
                        global_sequence=0,
                        topic="construction_production.scoped_projection",
                        audience="project",
                        payload_projection={"facility_ref": facility_ref, "condition": envelope.payload["restored_condition"]},
                    )
                ],
            },
            deep=True,
        )
        return self._store.append_batch(batch)

    def settle_facility_acquisition(
        self,
        *,
        plot: Plot,
        facility: Facility,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        if facility.plot_ref != plot.plot_ref or facility.condition <= 0:
            raise ValueError("facility_acquisition_invalid")
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None:
            return existing
        if facility.facility_ref in self.projector().facilities:
            raise ValueError("facility_duplicate")
        stream_id = f"gameplay:construction_production:{facility.facility_ref}"
        batch = build_atomic_event_batch(
            command_id=command_id,
            principal_ref=self._PRINCIPAL,
            stream_id=stream_id,
            expected_revision=self._store.get_stream_head(stream_id),
            event_specs=[
                (
                    "gameplay.construction_production.facility_acquired",
                    facility.model_dump(mode="json"),
                )
            ],
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            pinned_revisions={"plot": plot.revision, "facility": facility.revision},
        )
        return self._store.append_batch(batch)

    def settle_start_run(
        self,
        *,
        facility: Facility,
        recipe: Recipe,
        run_ref: str,
        tick: int,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        reservation_refs: tuple[str, ...] = (),
        worker_contribution_refs: tuple[WorkerContributionRef, ...] = (),
        due_completion_policy_revision: str = "1",
    ) -> AppendBatchResult:
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None:
            return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
        run = self.start_run(
            facility=facility,
            recipe=recipe,
            run_ref=run_ref,
            tick=tick,
            reservation_refs=reservation_refs,
            worker_contribution_refs=worker_contribution_refs,
        )
        stream_id = f"gameplay:construction_production:{facility.facility_ref}"
        batch = build_atomic_event_batch(
            command_id=command_id,
            principal_ref=self._PRINCIPAL,
            stream_id=stream_id,
            expected_revision=self._store.get_stream_head(stream_id),
            event_specs=[
                (
                    "gameplay.construction_production.run_started",
                    {
                        "run_ref": run.run_ref,
                        "facility_ref": run.facility_ref,
                        "recipe_ref": run.recipe_ref,
                        "started_tick": run.started_tick,
                        "finish_tick": run.finish_tick,
                        "reservation_refs": run.reservation_refs,
                        "output_item": run.output_item,
                        "worker_contributions": [
                            contribution.model_dump(mode="json")
                            for contribution in worker_contribution_refs
                        ],
                        "recipe_snapshot": {
                            "recipe_ref": recipe.recipe_ref,
                            "output_item": recipe.output_item,
                            "duration_ticks": recipe.duration_ticks,
                        },
                        "due_obligation_id": ConstructionDueCompletionPolicy.obligation_id_for(
                            run_ref=run.run_ref
                        ),
                        "due_policy_ref": "policy:construction_due_completion",
                        "due_policy_revision": due_completion_policy_revision,
                    },
                )
            ],
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            pinned_revisions={"facility": facility.revision, "recipe": recipe.duration_ticks},
        )
        return self._store.append_batch(batch)

    def record_completed_work_evidence(
        self,
        *,
        run_ref: str,
        contribution: WorkerContributionRef,
        evidence_ref: str,
        observed_at: str,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        expected_stream_revision: int | None = None,
    ) -> AppendBatchResult:
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None:
            prior = self._store.get_event(existing.committed_event_ids[0])
            if (
                prior.event_type != "gameplay.construction_production.work_completion_evidence_recorded"
                or prior.payload.get("run_ref") != run_ref
                or prior.payload.get("evidence_ref") != evidence_ref
                or prior.payload.get("contribution_digest") != contribution.contribution_digest
                or prior.payload.get("observed_at") != observed_at
            ):
                return self._rejected_work_evidence(
                    command_id=command_id,
                    error_code="idempotency_key_reused",
                )
            return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
        projection = self.projector()
        run = projection.runs.get(run_ref)
        if run is None or run.status != "completed":
            return self._rejected_work_evidence(
                command_id=command_id,
                error_code="production_evidence_run_not_completed",
            )
        stream_id = f"gameplay:construction_production:{run.facility_ref}"
        started_event = next(
            (
                event
                for event in self._store.read_stream(stream_id)
                if event.event_type == "gameplay.construction_production.run_started"
                and event.payload.get("run_ref") == run_ref
            ),
            None,
        )
        finished_event = next(
            (
                event
                for event in reversed(self._store.read_stream(stream_id))
                if event.event_type == "gameplay.construction_production.run_finished"
                and event.payload.get("run_ref") == run_ref
            ),
            None,
        )
        committed_contributions = tuple(started_event.payload.get("worker_contributions", ())) if started_event else ()
        contribution_payload = contribution.model_dump(mode="json")
        if started_event is None or finished_event is None or contribution_payload not in committed_contributions:
            return self._rejected_work_evidence(
                command_id=command_id,
                error_code="production_evidence_contribution_mismatch",
            )
        canonical_evidence_ref = (
            f"evidence:production-completed:{run_ref}:{contribution.contribution_digest}"
        )
        if not evidence_ref:
            return self._rejected_work_evidence(
                command_id=command_id,
                error_code="production_evidence_ref_required",
            )
        if evidence_ref != canonical_evidence_ref:
            return self._rejected_work_evidence(
                command_id=command_id,
                error_code="production_evidence_ref_untrusted",
            )
        current_revision = self._store.get_stream_head(stream_id)
        if expected_stream_revision is not None and expected_stream_revision != current_revision:
            return self._rejected_work_evidence(
                command_id=command_id,
                error_code="production_evidence_revision_conflict",
            )
        payload = {
            "evidence_ref": evidence_ref,
            "run_ref": run_ref,
            "facility_ref": run.facility_ref,
            "actor_ref": contribution.actor_ref,
            "assignment_ref": contribution.assignment_ref,
            "work_order_ref": contribution.work_order_ref,
            "contribution_digest": contribution.contribution_digest,
            "evidence_kind": "production-completed",
            "outcome": "completed",
            "verification_state": "verified",
            "source_digest": contribution.contribution_digest,
            "source_run_finished_event_ref": finished_event.event_id,
            "source_run_finished_revision": finished_event.stream_revision,
            "observed_at": observed_at,
        }
        command = GameplayCommandEnvelope(
            command_id=command_id,
            command_type="gameplay.construction_production.record_completed_work_evidence",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=contribution.actor_ref,
            project_ref=None,
            transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key,
            expected_revisions={stream_id: current_revision},
            read_set_revisions={stream_id: finished_event.stream_revision},
            causation_id=causation_id,
            correlation_id=correlation_id,
            source_ref=finished_event.event_id,
            submitted_at=observed_at,
            pinned_revisions={"production:run_finished": finished_event.stream_revision},
            payload={
                "stream_ref": stream_id,
                "event_type": "gameplay.construction_production.work_completion_evidence_recorded",
                "visibility_policy": f"actor:{contribution.actor_ref}",
                "evidence_refs": (evidence_ref,),
                **payload,
            },
        )
        batch = SettlementPlan.from_command_envelope(command).to_atomic_event_batch().model_copy(
            update={
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:event:{command_id}:1",
                        transaction_id=f"transaction:{command_id}",
                        event_id=f"event:{command_id}:1",
                        global_sequence=0,
                        topic="construction_production.completed_evidence.scoped_projection",
                        audience=f"actor:{contribution.actor_ref}",
                        payload_projection={"run_ref": run_ref, "evidence_ref": evidence_ref},
                    )
                ]
            },
            deep=True,
        )
        return self._store.append_batch(batch)

    def completed_evidence_view_for(self, *, recipient_ref: str) -> ProductionCompletedEvidenceView:
        rows: list[dict[str, object]] = []
        event_refs: list[str] = []
        revisions: dict[str, int] = {}
        for event in self._store.read_events():
            if event.event_type != "gameplay.construction_production.work_completion_evidence_recorded":
                continue
            if recipient_ref == self._PRINCIPAL:
                pass
            elif (
                recipient_ref != event.payload.get("actor_ref")
                or event.visibility_policy != f"actor:{recipient_ref}"
            ):
                continue
            rows.append(dict(event.payload))
            event_refs.append(event.event_id)
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
        rows.sort(key=lambda row: str(row["evidence_ref"]))
        event_refs.sort()
        projection = {
            "recipient_ref": recipient_ref,
            "evidence_rows": rows,
            "source_event_refs": event_refs,
            "source_revision_vector": dict(sorted(revisions.items())),
        }
        return ProductionCompletedEvidenceView(
            owner_principal_ref=self._PRINCIPAL,
            recipient_ref=recipient_ref,
            evidence_refs=tuple(str(row["evidence_ref"]) for row in rows),
            evidence_rows=tuple(rows),
            source_event_refs=tuple(event_refs),
            source_revision_vector=dict(sorted(revisions.items())),
            projection_hash="sha256:" + hashlib.sha256(
                json.dumps(projection, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
            ).hexdigest(),
        )

    def settle_finish_run(
        self,
        run: ProductionRun,
        *,
        tick: int,
        recipe: Recipe,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None:
            return existing
        completed = self.finish_run(run, tick=tick, recipe=recipe)
        stream_id = f"gameplay:construction_production:{completed.facility_ref}"
        batch = build_atomic_event_batch(
            command_id=command_id,
            principal_ref=self._PRINCIPAL,
            stream_id=stream_id,
            expected_revision=self._store.get_stream_head(stream_id),
            event_specs=[
                (
                    "gameplay.construction_production.run_finished",
                    {
                        "run_ref": completed.run_ref,
                        "facility_ref": completed.facility_ref,
                        "recipe_ref": completed.recipe_ref,
                        "completed_tick": tick,
                        "output_item": completed.output_item,
                    },
                )
            ],
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            pinned_revisions={"recipe": recipe.duration_ticks},
        )
        return self._store.append_batch(batch)

    def settle_maintenance_obligation(
        self,
        run: ProductionRun,
        *,
        obligation_ref: str,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        if not obligation_ref:
            raise ValueError("maintenance_obligation_required")
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None:
            return existing
        stream_id = f"gameplay:construction_production:{run.facility_ref}"
        batch = build_atomic_event_batch(
            command_id=command_id,
            principal_ref=self._PRINCIPAL,
            stream_id=stream_id,
            expected_revision=self._store.get_stream_head(stream_id),
            event_specs=[
                (
                    "gameplay.construction_production.maintenance_obligation_created",
                    {"run_ref": run.run_ref, "obligation_ref": obligation_ref},
                )
            ],
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
        )
        return self._store.append_batch(batch)

    def apply_maintenance_state(
        self,
        *,
        command_id: str,
        idempotency_key: str,
        facility_ref: str,
        expected_revision: int,
        causation_id: str,
        correlation_id: str,
        source_ref: str,
        submitted_at: str,
        pinned_revisions: Mapping[str, int],
        semantic_snapshot_digest: str,
        application: EffectApplication,
        resistance: ResistanceProfile,
        definition: StateDefinition,
    ) -> AppendBatchResult:
        try:
            contract = SemanticRegistry.require_closed_state_owner_contract(
                effect_ref=application.effect_ref,
                state_ref=definition.state_ref,
            )
        except SemanticRegistryError:
            return self._rejected_maintenance_state(command_id, "construction_maintenance_owner_mapping_unregistered")
        expected_definition = contract.definition
        if (
            contract.owner_ref != self._PRINCIPAL
            or contract.stream_pattern != "gameplay:construction_production:{facility_ref}"
            or contract.apply_event_type != "gameplay.construction_production.maintenance_state_applied"
            or contract.projection_scope != "project"
            or application.effect_ref != contract.effect_ref
            or application.target_component_ref != facility_ref
            or application.stack_key != "maintenance"
            or application.expires_at_tick is not None
            or resistance.effect_ref != contract.effect_ref
            or definition != expected_definition
        ):
            return self._rejected_maintenance_state(command_id, "construction_maintenance_owner_mapping_unregistered")
        if dict(pinned_revisions) != {"semantic": 1}:
            return self._rejected_maintenance_state(command_id, "semantic_closed_registry_revision_mismatch")
        stream_id = f"gameplay:construction_production:{facility_ref}"
        projection = self.projector()
        if facility_ref not in projection.facilities:
            return self._rejected_maintenance_state(command_id, "construction_maintenance_facility_unknown")
        current = projection.maintenance_states.get(facility_ref)
        resolution = EffectLifecycleEvaluator().resolve(
            application,
            resistance=resistance,
            state=definition,
            existing_stacks=current.stacks if current is not None else 0,
        )
        if not resolution.accepted:
            return self._rejected_maintenance_state(
                command_id,
                resolution.error_code or "construction_maintenance_state_rejected",
            )
        envelope = GameplayCommandEnvelope(
            command_id=command_id,
            command_type="gameplay.construction_production.apply_maintenance_state",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=facility_ref,
            project_ref=None,
            transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key,
            expected_revisions={stream_id: expected_revision},
            causation_id=causation_id,
            correlation_id=correlation_id,
            source_ref=source_ref,
            submitted_at=submitted_at,
            pinned_revisions=dict(pinned_revisions),
            payload={
                "stream_ref": stream_id,
                "event_type": "gameplay.construction_production.maintenance_state_applied",
                "visibility_policy": "project",
                "facility_ref": facility_ref,
                "state_ref": definition.state_ref,
                "effect_ref": application.effect_ref,
                "effective_magnitude": resolution.effective_magnitude,
                "next_stacks": resolution.next_stacks,
                "resistance_revision": resistance.revision,
                "semantic_snapshot_digest": semantic_snapshot_digest,
            },
        )
        proposal_digest = self._maintenance_state_digest(
            envelope=envelope,
            application=application,
            resistance=resistance,
            definition=definition,
            semantic_snapshot_digest=semantic_snapshot_digest,
        )
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None:
            record = self._store.get_idempotency_record(self._PRINCIPAL, idempotency_key)
            if record is not None and record.payload_digest == proposal_digest:
                return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            return self._rejected_maintenance_state(command_id, "idempotency_key_reused")
        if self._store.get_stream_head(stream_id) != expected_revision:
            return self._rejected_maintenance_state(command_id, "revision_conflict")
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:construction-maintenance-state-expiry@1",
                contract_kind="lifecycle",
                owner_ref=self._PRINCIPAL,
                stream_ids=(stream_id,),
                event_types=("gameplay.construction_production.maintenance_state_applied",),
                projection_scope="project",
            )
        except GovernedAuthorityContractError as error:
            return self._rejected_maintenance_state(command_id, str(error))
        base_batch = SettlementPlan.from_command_envelope(envelope).to_atomic_event_batch()
        batch = base_batch.model_copy(
            update={
                "idempotency_record": base_batch.idempotency_record.model_copy(
                    update={"payload_digest": proposal_digest},
                    deep=True,
                ),
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:event:{command_id}:1",
                        transaction_id=f"transaction:{command_id}",
                        event_id=f"event:{command_id}:1",
                        global_sequence=0,
                        topic="construction_production.scoped_projection",
                        audience="project",
                        payload_projection={
                            "facility_ref": facility_ref,
                            "state_ref": definition.state_ref,
                        },
                    )
                ],
            },
            deep=True,
        )
        return self._store.append_batch(batch)

    @classmethod
    def maintenance_state_obligation_registration(
        cls, *, include_semantic_action_cancellation: bool = False
    ):
        """Return the fixed expiry row, optionally with the closed semantic dispel terminal."""
        from app.world_runtime.obligations import ObligationLifecycleRegistration

        return ObligationLifecycleRegistration(
            policy_ref="policy:construction_maintenance_state_expiry@1",
            policy_revision="1",
            owner_ref=cls._PRINCIPAL,
            stream_pattern="gameplay:construction_production:{facility_ref}",
            opened_event_type="gameplay.construction_production.maintenance_state_obligation_opened",
            settled_event_type="gameplay.construction_production.maintenance_state_obligation_settled",
            cancelled_event_type=(
                "gameplay.construction_production.maintenance_state_obligation_cancelled"
                if include_semantic_action_cancellation
                else None
            ),
            expired_event_type="gameplay.construction_production.maintenance_state_expired",
            visibility_scope="project",
            requires_committed_open=True,
            requires_expired_event_on_settle=True,
        )

    @classmethod
    def build_maintenance_state_obligation(
        cls,
        *,
        facility_ref: str,
        obligation_id: str,
        state_event_id: str,
        due_tick: int,
        expected_revision: int,
        idempotency_key: str,
    ) -> ScheduledObligation:
        stream_id = f"gameplay:construction_production:{facility_ref}"
        return ScheduledObligation(
            obligation_id=obligation_id,
            owner_ref=cls._PRINCIPAL,
            due_tick=due_tick,
            policy_revision="1",
            status="open",
            idempotency_key=idempotency_key,
            expected_revisions={stream_id: expected_revision},
            visibility_scope="project",
            source_refs=("policy:construction_maintenance_state_expiry@1", f"state_event:{state_event_id}"),
        )

    def open_maintenance_state_obligation(
        self,
        *,
        state_event_id: str,
        due_tick: int,
        expected_revision: int,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConstructionMaintenanceStateObligationResult:
        if due_tick < 0:
            raise ValueError("maintenance_state_due_tick_invalid")
        try:
            source = self._store.get_event(state_event_id)
        except KeyError as exc:
            raise ValueError("maintenance_state_source_unknown") from exc
        payload = source.payload
        facility_ref = payload.get("facility_ref")
        if (
            source.event_type != "gameplay.construction_production.maintenance_state_applied"
            or source.visibility_policy != "project"
            or not isinstance(facility_ref, str)
            or not facility_ref
            or payload.get("effect_ref") != "effect:maintenance_required"
            or payload.get("state_ref") != "state:maintenance_due"
            or not isinstance(payload.get("semantic_snapshot_digest"), str)
        ):
            raise ValueError("maintenance_state_source_invalid")
        stream_id = f"gameplay:construction_production:{facility_ref}"
        if source.stream_id != stream_id:
            raise ValueError("maintenance_state_source_invalid")
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None:
            existing_event = self._store.get_event(existing.committed_event_ids[0]) if existing.committed_event_ids else None
            original_expected_revision = (existing_event.stream_revision - 1) if existing_event is not None else None
            if (
                existing_event is None
                or existing_event.payload.get("state_event_id") != state_event_id
                or existing_event.payload.get("due_tick") != due_tick
                or existing_event.correlation_id != correlation_id
                or expected_revision != original_expected_revision
            ):
                raise ValueError("idempotency_key_reused")
            return ConstructionMaintenanceStateObligationResult(
                committed=existing.committed,
                obligation=ScheduledObligation(
                    obligation_id=str(existing_event.payload["obligation_id"]),
                    owner_ref=self._PRINCIPAL,
                    due_tick=due_tick,
                    policy_revision="1",
                    status="open",
                    idempotency_key=idempotency_key,
                    expected_revisions={stream_id: original_expected_revision},
                    visibility_scope="project",
                    source_refs=("policy:construction_maintenance_state_expiry@1", f"state_event:{state_event_id}"),
                ),
                append_result=existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True),
            )
        if self._store.get_stream_head(stream_id) != expected_revision:
            raise ValueError("revision_conflict")
        events = self._store.read_stream(stream_id)
        opened_for_source = [
            event
            for event in events
            if event.event_type == "gameplay.construction_production.maintenance_state_obligation_opened"
            and event.payload.get("state_event_id") == state_event_id
        ]
        if opened_for_source:
            raise ValueError("maintenance_state_obligation_active")
        opened_obligation_ids = {
            str(event.payload.get("obligation_id", ""))
            for event in events
            if event.event_type == "gameplay.construction_production.maintenance_state_obligation_opened"
        }
        terminal_obligation_ids = {
            str(event.payload.get("obligation_id", ""))
            for event in events
            if event.event_type
            in {
                "gameplay.construction_production.maintenance_state_expired",
                "gameplay.construction_production.maintenance_state_obligation_settled",
            }
        }
        if any(obligation_id and obligation_id not in terminal_obligation_ids for obligation_id in opened_obligation_ids):
            raise ValueError("maintenance_state_obligation_active")
        obligation = self.build_maintenance_state_obligation(
            facility_ref=facility_ref,
            obligation_id=f"obligation:construction-maintenance-state:{facility_ref}:{state_event_id}",
            state_event_id=state_event_id,
            due_tick=due_tick,
            expected_revision=expected_revision,
            idempotency_key=idempotency_key,
        )
        command = GameplayCommandEnvelope(
            command_id=f"construction:maintenance-state:open:{state_event_id}",
            command_type="gameplay.construction_production.open_maintenance_state_obligation",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=facility_ref,
            project_ref=None,
            transaction_id=f"transaction:construction:maintenance-state:open:{state_event_id}",
            idempotency_key=idempotency_key,
            expected_revisions={stream_id: expected_revision},
            causation_id=state_event_id,
            correlation_id=correlation_id,
            source_ref="construction_maintenance_state",
            submitted_at="maintenance-state-open",
            pinned_revisions={"state_source": source.stream_revision},
            payload={
                "stream_ref": stream_id,
                "event_type": "gameplay.construction_production.maintenance_state_obligation_opened",
                "visibility_policy": "project",
                "obligation_id": obligation.obligation_id,
                "policy_ref": "policy:construction_maintenance_state_expiry@1",
                "policy_revision": "1",
                "due_tick": due_tick,
                "facility_ref": facility_ref,
                "state_event_id": state_event_id,
                "state_event_revision": source.stream_revision,
                "semantic_snapshot_digest": payload["semantic_snapshot_digest"],
            },
        )
        batch = SettlementPlan.from_command_envelope(command).to_atomic_event_batch()
        event = batch.events[0]
        batch = batch.model_copy(
            update={
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}",
                        transaction_id=batch.transaction_id,
                        event_id=event.event_id,
                        global_sequence=0,
                        topic="construction_production.maintenance_state.scoped_projection",
                        audience="project",
                        payload_projection={"facility_ref": facility_ref, "obligation_id": obligation.obligation_id},
                    )
                ]
            },
            deep=True,
        )
        result = self._store.append_batch(batch)
        return ConstructionMaintenanceStateObligationResult(
            committed=result.committed,
            obligation=obligation if result.committed else None,
            append_result=result,
            error_code=(result.failure.error_code if result.failure else None),
        )

    @classmethod
    def build_maintenance_state_expiry_fragment(
        cls,
        *,
        obligation: ScheduledObligation,
        facility_ref: str,
        expected_revision: int,
    ) -> OwnerAuthorizedFragment:
        stream_id = f"gameplay:construction_production:{facility_ref}"
        if (
            obligation.owner_ref != cls._PRINCIPAL
            or obligation.expected_revisions != {stream_id: expected_revision}
            or obligation.policy_revision != "1"
            or "policy:construction_maintenance_state_expiry@1" not in obligation.source_refs
        ):
            raise ValueError("maintenance_state_obligation_invalid")
        return OwnerAuthorizedFragment(
            fragment_id=f"fragment:construction:maintenance-state-expiry:{obligation.obligation_id}",
            owner_principal_ref=cls._PRINCIPAL,
            source_rule_ref="construction-production:maintenance-state-expiry",
            expected_revisions={stream_id: expected_revision},
            pinned_revisions={"maintenance_state_policy": 1},
            event_specs={
                stream_id: (
                    (
                        "gameplay.construction_production.maintenance_state_expired",
                        {
                            "obligation_id": obligation.obligation_id,
                            "facility_ref": facility_ref,
                            "prior_state": obligation.status,
                            "current_state": "expired",
                            "policy_ref": "policy:construction_maintenance_state_expiry@1",
                            "policy_revision": "1",
                            "due_tick": obligation.due_tick,
                        },
                    ),
                    (
                        "gameplay.construction_production.maintenance_state_obligation_settled",
                        {
                            "obligation_id": obligation.obligation_id,
                            "prior_state": obligation.status,
                            "current_state": "settled",
                            "policy_ref": "policy:construction_maintenance_state_expiry@1",
                            "policy_revision": "1",
                            "due_tick": obligation.due_tick,
                        },
                    ),
                )
            },
        )

    @classmethod
    def build_maintenance_state_dispel_fragment(
        cls,
        *,
        obligation: ScheduledObligation,
        facility_ref: str,
        state_ref: str,
        expected_revision: int,
        reason_ref: str,
    ) -> OwnerAuthorizedFragment:
        stream_id = f"gameplay:construction_production:{facility_ref}"
        if (
            not reason_ref
            or state_ref != "state:maintenance_due"
            or obligation.owner_ref != cls._PRINCIPAL
            or obligation.expected_revisions != {stream_id: expected_revision}
            or obligation.policy_revision != "1"
            or "policy:construction_maintenance_state_expiry@1" not in obligation.source_refs
        ):
            raise ValueError("construction_maintenance_state_dispel_fragment_invalid")
        return OwnerAuthorizedFragment(
            fragment_id=f"fragment:construction:maintenance-state-dispel:{facility_ref}:{state_ref}:{reason_ref}",
            owner_principal_ref=cls._PRINCIPAL,
            source_rule_ref="construction-production:maintenance-state-dispel",
            expected_revisions={stream_id: expected_revision},
            event_specs={
                stream_id: (
                    (
                        "gameplay.construction_production.maintenance_state_dispelled",
                        {
                            "facility_ref": facility_ref,
                            "state_ref": state_ref,
                            "obligation_id": obligation.obligation_id,
                            "reason_ref": reason_ref,
                        },
                    ),
                    (
                        "gameplay.construction_production.maintenance_state_obligation_cancelled",
                        {
                            "obligation_id": obligation.obligation_id,
                            "prior_state": obligation.status,
                            "current_state": "cancelled",
                            "policy_ref": "policy:construction_maintenance_state_expiry@1",
                            "policy_revision": obligation.policy_revision,
                            "due_tick": obligation.due_tick,
                            "reason_ref": reason_ref,
                        },
                    ),
                )
            },
            event_visibility_policies={stream_id: ("project", "project")},
        )

    def settle_canonical_seasonal_maintenance(
        self,
        *,
        command: CanonicalSeasonalConstructionMaintenanceCommand,
        admission: object | None,
        run: ProductionRun,
        obligation_ref: str,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        expected_revision: int,
    ) -> AppendBatchResult:
        if command.edge_ref != "ecology-process:seasonal-to-construction-maintenance:v1" or not command.enabled:
            return self._rejected_append(command_id, "seasonal_maintenance_edge_unsupported")
        if (
            admission is None
            or not _CONTAINS_CANONICAL_SEASONAL_ADMISSION(admission)
            or getattr(admission, "edge_ref", None) != command.edge_ref
            or getattr(admission, "process_event_id", None) != command.process_event_id
        ):
            return self._rejected_append(command_id, "seasonal_maintenance_admission_required")
        if command.source_authority_ref != "authority:ecology" or command.privacy_scope != "project":
            return self._rejected_append(command_id, "seasonal_maintenance_source_denied")
        if self._store.get_stream_head(command.ecology_stream_id) != command.ecology_stream_revision:
            return self._rejected_append(command_id, "seasonal_maintenance_source_revision_conflict")
        try:
            source_event = self._store.get_event(command.process_event_id)
        except KeyError:
            return self._rejected_append(command_id, "seasonal_maintenance_source_missing")
        if not self._matches_canonical_seasonal_source(source_event, command):
            return self._rejected_append(command_id, "seasonal_maintenance_source_revision_conflict")
        stream_id = f"gameplay:construction_production:{run.facility_ref}"
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None:
            return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
        if self._store.get_stream_head(stream_id) != expected_revision:
            return self._rejected_append(command_id, "revision_conflict")
        fragment = OwnerAuthorizedFragment(
            fragment_id=f"fragment:construction:seasonal-maintenance:{run.run_ref}:{command.process_event_id}",
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref=command.edge_ref,
            expected_revisions={stream_id: expected_revision},
            read_set_revisions={command.ecology_stream_id: command.ecology_stream_revision},
            pinned_revisions={"process_event": command.process_event_revision, "ecology_head": command.ecology_stream_revision},
            event_specs={stream_id: ((
                "gameplay.construction_production.maintenance_obligation_created",
                {
                    "run_ref": run.run_ref,
                    "obligation_ref": obligation_ref,
                    "seasonal_ecology_propagation": command.model_dump(mode="json"),
                },
            ),)},
            event_visibility_policies={stream_id: ("project",)},
        )
        batch = build_multi_stream_atomic_event_batch_from_fragments(
            command_id=command_id,
            idempotency_principal_ref=self._PRINCIPAL,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            fragments=(fragment,),
        )
        event = batch.events[0]
        batch = batch.model_copy(update={"outbox_entries": [GameplayOutboxEntry(
            outbox_id=f"outbox:{event.event_id}", transaction_id=batch.transaction_id,
            event_id=event.event_id, global_sequence=0,
            topic="construction_production.scoped_projection", audience="project",
            payload_projection={"facility_ref": run.facility_ref, "run_ref": run.run_ref, "obligation_ref": obligation_ref},
        )]}, deep=True)
        return self._store.append_batch(batch)

    def settle_canonical_weather_front_maintenance(
        self,
        *,
        command: CanonicalWeatherFrontConstructionMaintenanceCommand,
        admission: object | None,
        run: ProductionRun,
        obligation_ref: str,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        expected_revision: int,
    ) -> AppendBatchResult:
        edge_ref = "ecology-weather:front-to-construction-maintenance:v1"
        if command.edge_ref != edge_ref or not command.enabled:
            return self._rejected_append(command_id, "weather_front_maintenance_edge_unsupported")
        if (
            admission is None
            or not _CONTAINS_CANONICAL_WEATHER_FRONT_ADMISSION(admission)
            or getattr(admission, "edge_ref", None) != command.edge_ref
            or getattr(admission, "weather_event_id", None) != command.weather_event_id
            or getattr(admission, "facility_ref", None) != command.facility_ref
        ):
            return self._rejected_append(command_id, "weather_front_maintenance_admission_required")
        if command.source_authority_ref != "authority:ecology" or command.privacy_scope != "project":
            return self._rejected_append(command_id, "weather_front_maintenance_source_denied")
        if run.facility_ref != command.facility_ref:
            return self._rejected_append(command_id, "weather_front_maintenance_facility_mismatch")
        stream_id = f"gameplay:construction_production:{run.facility_ref}"
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None:
            prior = next(
                (event for event in self._store.read_events() if event.event_id in set(existing.committed_event_ids)),
                None,
            )
            if prior is None or (
                prior.payload.get("obligation_ref") == obligation_ref
                and prior.payload.get("weather_front_ecology_propagation") == command.model_dump(mode="json")
            ):
                return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            return self._rejected_append(command_id, "idempotency_key_reused")
        admission_check = EcologyConsumerAdmissionCheck.verify(
            store=self._store,
            contract_ref="inf:weather-front-construction-maintenance@1",
            target_owner_ref=self._PRINCIPAL,
            target_stream_ids=(stream_id,),
            target_event_types=("gameplay.construction_production.maintenance_obligation_created",),
            projection_scope="project",
            source_event_id=command.weather_event_id,
            source_stream_id=command.ecology_stream_id,
            source_revision=command.ecology_stream_revision,
            target_expected_revisions={stream_id: expected_revision},
            idempotency_key=idempotency_key,
        )
        if not admission_check.accepted:
            error_code = admission_check.error_code
            if error_code == "ecology_consumer_source_missing":
                error_code = "weather_front_maintenance_source_missing"
            elif error_code == "ecology_consumer_source_pin_invalid":
                error_code = "weather_front_maintenance_source_revision_conflict"
            elif error_code == "ecology_consumer_target_revision_conflict":
                error_code = "revision_conflict"
            return self._rejected_append(command_id, error_code or "weather_front_maintenance_admission_invalid")
        source_event = self._store.get_event(command.weather_event_id)
        if not self._matches_canonical_weather_front_source(source_event, command):
            return self._rejected_append(command_id, "weather_front_maintenance_source_revision_conflict")
        fragment = OwnerAuthorizedFragment(
            fragment_id=f"fragment:construction:weather-front-maintenance:{run.run_ref}:{command.weather_event_id}",
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref=edge_ref,
            expected_revisions={stream_id: expected_revision},
            read_set_revisions={command.ecology_stream_id: command.ecology_stream_revision},
            pinned_revisions={"weather_event": command.weather_event_revision, "ecology_head": command.ecology_stream_revision},
            event_specs={stream_id: ((
                "gameplay.construction_production.maintenance_obligation_created",
                {
                    "run_ref": run.run_ref,
                    "obligation_ref": obligation_ref,
                    "weather_front_ecology_propagation": command.model_dump(mode="json"),
                },
            ),)},
            event_visibility_policies={stream_id: ("project",)},
        )
        batch = build_multi_stream_atomic_event_batch_from_fragments(
            command_id=command_id,
            idempotency_principal_ref=self._PRINCIPAL,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            fragments=(fragment,),
        )
        event = batch.events[0]
        batch = batch.model_copy(update={"outbox_entries": [GameplayOutboxEntry(
            outbox_id=f"outbox:{event.event_id}",
            transaction_id=batch.transaction_id,
            event_id=event.event_id,
            global_sequence=0,
            topic="construction_production.scoped_projection",
            audience="project",
            payload_projection={"facility_ref": run.facility_ref, "run_ref": run.run_ref, "obligation_ref": obligation_ref},
        )]}, deep=True)
        return self._store.append_batch(batch)

    @staticmethod
    def _matches_canonical_seasonal_source(
        event: GameplayEvent, command: CanonicalSeasonalConstructionMaintenanceCommand
    ) -> bool:
        payload = event.payload
        return bool(
            event.event_type == "gameplay.ecology.seasonal_process_advanced"
            and event.visibility_policy == "project"
            and event.stream_id == command.ecology_stream_id
            and event.stream_revision == command.process_event_revision
            and payload.get("region_ref") == command.region_ref
            and payload.get("last_tick") == command.last_tick
            and payload.get("elapsed_ticks") == command.elapsed_ticks
            and payload.get("policy_ref") == command.policy_ref
            and payload.get("policy_revision") == command.policy_revision
        )

    @staticmethod
    def _matches_canonical_weather_front_source(
        event: GameplayEvent, command: CanonicalWeatherFrontConstructionMaintenanceCommand
    ) -> bool:
        payload = event.payload
        return bool(
            event.event_type == "gameplay.ecology.weather_front.propagated"
            and event.visibility_policy == "project"
            and event.stream_id == command.ecology_stream_id
            and event.stream_revision == command.weather_event_revision
            and payload.get("source_region_ref") == command.source_region_ref
            and payload.get("target_region_ref") == command.target_region_ref
            and payload.get("weather_ref") == command.weather_ref
            and payload.get("tick") == command.tick
            and payload.get("policy_ref") == command.policy_ref
            and payload.get("policy_revision") == command.policy_revision
        )

    def settle_canonical_weather_front_maintenance_fanout(
        self,
        *,
        command: CanonicalWeatherFrontConstructionMaintenanceFanoutCommand,
        admission: object | None,
        runs: tuple[ProductionRun, ProductionRun],
        obligation_refs: tuple[str, str],
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        expected_revisions: dict[str, int],
    ) -> AppendBatchResult:
        edge_ref = "ecology-weather:front-to-construction-maintenance-fanout:v1"
        if command.edge_ref != edge_ref or not command.enabled or len(set(command.facility_refs)) != 2:
            return self._rejected_append(command_id, "weather_front_maintenance_fanout_unsupported")
        if (
            admission is None
            or not _CONTAINS_CANONICAL_WEATHER_FRONT_FANOUT_ADMISSION(admission)
            or getattr(admission, "edge_ref", None) != command.edge_ref
            or getattr(admission, "weather_event_id", None) != command.weather_event_id
            or getattr(admission, "facility_refs", None) != command.facility_refs
        ):
            return self._rejected_append(command_id, "weather_front_maintenance_fanout_admission_required")
        if command.source_authority_ref != "authority:ecology" or command.privacy_scope != "project":
            return self._rejected_append(command_id, "weather_front_maintenance_fanout_source_denied")
        if tuple(run.facility_ref for run in runs) != command.facility_refs or len(obligation_refs) != 2:
            return self._rejected_append(command_id, "weather_front_maintenance_fanout_target_mismatch")
        if self._store.get_stream_head(command.ecology_stream_id) != command.ecology_stream_revision:
            return self._rejected_append(command_id, "weather_front_maintenance_fanout_source_revision_conflict")
        try:
            source_event = self._store.get_event(command.weather_event_id)
        except KeyError:
            return self._rejected_append(command_id, "weather_front_maintenance_fanout_source_missing")
        if not self._matches_canonical_weather_front_source(source_event, command):
            return self._rejected_append(command_id, "weather_front_maintenance_fanout_source_revision_conflict")
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None:
            prior_events = [event for event in self._store.read_events() if event.event_id in set(existing.committed_event_ids)]
            if len(prior_events) == 2 and tuple(event.payload.get("obligation_ref") for event in sorted(prior_events, key=lambda item: item.stream_id)) == obligation_refs and all(
                event.event_type == "gameplay.construction_production.maintenance_obligation_created"
                and event.payload.get("weather_front_ecology_propagation") == command.model_dump(mode="json")
                for event in prior_events
            ):
                return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            return self._rejected_append(command_id, "idempotency_key_reused")
        stream_ids = tuple(f"gameplay:construction_production:{run.facility_ref}" for run in runs)
        if set(expected_revisions) != set(stream_ids) or any(
            self._store.get_stream_head(stream_id) != expected_revisions[stream_id] for stream_id in stream_ids
        ):
            return self._rejected_append(command_id, "revision_conflict")
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:weather-front-construction-maintenance@1",
                contract_kind="ecology_consumer",
                owner_ref=self._PRINCIPAL,
                stream_ids=stream_ids,
                event_types=(
                    "gameplay.construction_production.maintenance_obligation_created",
                ),
                projection_scope="project",
            )
        except GovernedAuthorityContractError as error:
            return self._rejected_append(command_id, str(error))
        fragments = tuple(
            OwnerAuthorizedFragment(
                fragment_id=f"fragment:construction:weather-front-maintenance-fanout:{run.run_ref}:{command.weather_event_id}",
                owner_principal_ref=self._PRINCIPAL,
                source_rule_ref=edge_ref,
                expected_revisions={stream_id: expected_revisions[stream_id]},
                read_set_revisions={command.ecology_stream_id: command.ecology_stream_revision},
                pinned_revisions={"weather_event": command.weather_event_revision, "ecology_head": command.ecology_stream_revision},
                event_specs={stream_id: ((
                    "gameplay.construction_production.maintenance_obligation_created",
                    {
                        "run_ref": run.run_ref,
                        "obligation_ref": obligation_ref,
                        "weather_front_ecology_propagation": command.model_dump(mode="json"),
                    },
                ),)},
                event_visibility_policies={stream_id: ("project",)},
            )
            for run, stream_id, obligation_ref in zip(runs, stream_ids, obligation_refs)
        )
        batch = build_multi_stream_atomic_event_batch_from_fragments(
            command_id=command_id,
            idempotency_principal_ref=self._PRINCIPAL,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            fragments=fragments,
        )
        batch = batch.model_copy(
            update={
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}",
                        transaction_id=batch.transaction_id,
                        event_id=event.event_id,
                        global_sequence=0,
                        topic="construction_production.scoped_projection",
                        audience="project",
                        payload_projection={"facility_ref": event.payload.get("run_ref"), "obligation_ref": event.payload.get("obligation_ref")},
                    )
                    for event in batch.events
                ]
            },
            deep=True,
        )
        return self._store.append_batch(batch)

    @staticmethod
    def _rejected_append(command_id: str, reason: str) -> AppendBatchResult:
        return AppendBatchResult(
            committed=False,
            transaction_id=f"transaction:{command_id}",
            command_id=command_id,
            idempotency_status="rejected",
            failure=GameplayFailure(error_code=reason, message=reason, failed_stage="construction_admission"),
        )

    @staticmethod
    def _maintenance_state_digest(
        *,
        envelope: GameplayCommandEnvelope,
        application: EffectApplication,
        resistance: ResistanceProfile,
        definition: StateDefinition,
        semantic_snapshot_digest: str,
    ) -> str:
        payload = {
            "command": envelope.model_dump(mode="json"),
            "application": application.model_dump(mode="json"),
            "resistance": resistance.model_dump(mode="json"),
            "definition": definition.model_dump(mode="json"),
            "semantic_snapshot_digest": semantic_snapshot_digest,
        }
        return "sha256:" + hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _rejected_maintenance_state(command_id: str, reason: str) -> AppendBatchResult:
        return AppendBatchResult(
            committed=False,
            transaction_id=f"transaction:{command_id}",
            command_id=command_id,
            idempotency_status="rejected",
            failure=GameplayFailure(
                error_code=reason,
                message=reason,
                failed_stage="construction_maintenance_state",
            ),
        )

    @classmethod
    def build_due_finish_fragment(
        cls,
        *,
        run: ProductionRun,
        recipe: Recipe,
        tick: int,
        expected_revision: int,
    ) -> OwnerAuthorizedFragment:
        completed = cls.finish_run(run, tick=tick, recipe=recipe)
        stream_id = f"gameplay:construction_production:{completed.facility_ref}"
        return OwnerAuthorizedFragment(
            fragment_id=f"fragment:production:due:{completed.run_ref}:{tick}",
            owner_principal_ref=cls._PRINCIPAL,
            source_rule_ref="construction-production:due-finish",
            expected_revisions={stream_id: expected_revision},
            pinned_revisions={"recipe": recipe.duration_ticks},
            event_specs={stream_id: (("gameplay.construction_production.run_finished", {"run_ref": completed.run_ref, "facility_ref": completed.facility_ref, "recipe_ref": completed.recipe_ref, "completed_tick": tick, "output_item": completed.output_item}),)},
        )

    @classmethod
    def build_due_finish_lifecycle_fragment(
        cls,
        *,
        run: ProductionRun,
        recipe: Recipe,
        tick: int,
        expected_revision: int,
        obligation: ScheduledObligation,
        settled_event_type: str,
    ) -> OwnerAuthorizedFragment:
        fragment = cls.build_due_finish_fragment(
            run=run, recipe=recipe, tick=tick, expected_revision=expected_revision
        )
        stream_id = f"gameplay:construction_production:{run.facility_ref}"
        return fragment.model_copy(
            update={
                "fragment_id": f"{fragment.fragment_id}:lifecycle",
                "event_specs": {
                    stream_id: (
                        *fragment.event_specs[stream_id],
                        (
                            settled_event_type,
                            {
                                "obligation_id": obligation.obligation_id,
                                "prior_state": obligation.status,
                                "current_state": "settled",
                                "policy_revision": obligation.policy_revision,
                                "due_tick": obligation.due_tick,
                                "attempt": 1,
                            },
                        ),
                    )
                },
            },
            deep=True,
        )

    @classmethod
    def build_obligation_cancellation_fragment(
        cls,
        *,
        obligation: ScheduledObligation,
        cancelled_event_type: str,
        reason_ref: str,
    ) -> OwnerAuthorizedFragment:
        if obligation.status not in {"open", "due"}:
            raise ValueError("obligation_not_cancellable")
        stream_ids = tuple(obligation.expected_revisions)
        if len(stream_ids) != 1:
            raise ValueError("obligation_stream_ambiguous")
        stream_id = stream_ids[0]
        return OwnerAuthorizedFragment(
            fragment_id=f"fragment:production:cancel:{obligation.obligation_id}",
            owner_principal_ref=cls._PRINCIPAL,
            source_rule_ref="construction-production:obligation-cancel",
            expected_revisions=dict(obligation.expected_revisions),
            event_specs={
                stream_id: (
                    (
                        cancelled_event_type,
                        {
                            "obligation_id": obligation.obligation_id,
                            "prior_state": obligation.status,
                            "current_state": "cancelled",
                            "policy_revision": obligation.policy_revision,
                            "due_tick": obligation.due_tick,
                            "reason_ref": reason_ref,
                        },
                    ),
                )
            },
        )

    @staticmethod
    def start_run(
        *,
        facility: Facility,
        recipe: Recipe,
        run_ref: str,
        tick: int,
        reservation_refs: tuple[str, ...] = (),
        worker_contribution_refs: tuple[WorkerContributionRef, ...] = (),
    ) -> ProductionRun:
        if facility.condition <= 0:
            raise ValueError("facility_unavailable")
        return ProductionRun(
            run_ref=run_ref,
            facility_ref=facility.facility_ref,
            recipe_ref=recipe.recipe_ref,
            started_tick=tick,
            finish_tick=tick + recipe.duration_ticks,
            reservation_refs=reservation_refs,
            output_item=recipe.output_item,
            worker_contribution_refs=tuple(
                contribution.contribution_digest for contribution in worker_contribution_refs
            ),
        )

    @staticmethod
    def _rejected_work_evidence(*, command_id: str, error_code: str) -> AppendBatchResult:
        from app.gameplay.models import GameplayFailure

        return AppendBatchResult(
            committed=False,
            transaction_id=f"transaction:{command_id}",
            command_id=command_id,
            idempotency_status="rejected",
            failure=GameplayFailure(
                error_code=error_code,
                message=error_code,
                failed_stage="production_completed_evidence",
            ),
        )

    @staticmethod
    def finish_run(run: ProductionRun, *, tick: int, recipe: Recipe) -> ProductionRun:
        if run.status != "started":
            raise ValueError("production_run_final")
        if tick < run.finish_tick:
            raise ValueError("production_not_due")
        return run.model_copy(update={"status": "completed", "output_item": recipe.output_item}, deep=True)

    @staticmethod
    def maintenance(run: ProductionRun, *, obligation_ref: str) -> ProductionRun:
        return run.model_copy(update={"maintenance_obligation_ref": obligation_ref}, deep=True)

__all__ = ["Blueprint", "CanonicalFrostProductionFinishCommand", "CanonicalSeasonalConstructionMaintenanceCommand", "CanonicalWeatherFrontConstructionMaintenanceCommand", "CanonicalWeatherFrontConstructionMaintenanceFanoutCommand", "CommittedProductionRecipe", "ConstructionDueCompletionPolicy", "ConstructionFrostFinishCommand", "ConstructionJob", "ConstructionMaintenanceState", "ConstructionMaintenanceStateObligationResult", "ConstructionProductionAuthority", "ConstructionProductionProjection", "ConstructionProductionProjector", "Facility", "FrostFinishSettlementResult", "FrostProductionTarget", "FrostProductionTargetSelection", "PackageDeclaredFacilityTransformIntentV1", "Plot", "ProductionCompletedEvidenceView", "ProductionRecipeResult", "ProductionRun", "Recipe"]
