from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import GameplayOutboxEntry, StrictGameplayModel
from app.gameplay.civilization_capability_runtime import CivilizationCapabilityView
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.settlement_plan import (
    SettlementPlan,
    build_multi_stream_atomic_event_batch_from_fragments,
)
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from app.gameplay.organization_government_runtime import OrganizationAuthority
from app.gameplay.organization_government_runtime import GovernmentAuthority
from app.gameplay.econ1_economy_runtime import EconomyAuthority
from app.gameplay.shared_contracts import ScheduledObligation
from app.gameplay.survival_runtime import SurvivalAuthority, SurvivalStateExpiryPolicy
from app.world_runtime.obligations import ObligationLifecycleProjection, ObligationLifecycleRegistration, ObligationSettlementCoordinator, ObligationSettlementResult

from .models import (
    BatchIntentCandidate,
    ContinuityMergeReceipt,
    PopulationBatchPlan,
    PopulationWorldPlan,
    WorldModeProfile,
)
from .social_input import FrozenSocialPlanningInput
from .source_inputs import HouseholdScheduleInput, OrganizationScheduleInput, ProductionCompletedEvidenceInput
from .capability_input import FrozenCapabilityEligibilityInput
from .siming_contracts import PopulationBatchReport, PopulationReadSet


class SocialPlanningResult:
    def __init__(self, *, accepted: bool, plan: PopulationBatchPlan | None = None, error_code: str | None = None) -> None:
        self.accepted = accepted
        self.plan = plan
        self.error_code = error_code


@dataclass(frozen=True)
class PopulationActivationCandidate:
    candidate_ref: str
    actor_ref: str
    reason: str
    activation_reason: str
    budget: int
    scope: str
    source_revision_vector: dict[str, int]
    fallback: str = "requeue"


@dataclass(frozen=True)
class PopulationOwnerBoundIntent:
    candidate_ref: str
    actor_ref: str
    intent_kind: str
    scope: str
    payload: dict[str, object]
    source_revision_vector: dict[str, int]


@dataclass(frozen=True)
class PopulationRejectedCandidate:
    candidate_ref: str
    reason: str
    candidate_kind: str = ""


def _digest(value: object) -> str:
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                value, sort_keys=True, separators=(",", ":"), default=str
            ).encode()
        ).hexdigest()
    )


def _plan_digest(plan: PopulationBatchPlan) -> str:
    normalized = plan.model_copy(
        update={
            "candidates": tuple(
                sorted(
                    plan.candidates,
                    key=lambda item: (
                        -item.priority,
                        item.profile_ref,
                        item.intent_ref,
                    ),
                )
            )
        }
    )
    return _digest(normalized.model_dump(mode="json"))


def _capability_supply_plan_digest(plan: PopulationWorldPlan) -> str:
    return _digest(plan.model_dump(mode="json"))


def _capability_inspection_plan_digest(plan: PopulationWorldPlan) -> str:
    return _digest(plan.model_dump(mode="json"))


def _production_wage_plan_digest(plan: PopulationWorldPlan) -> str:
    return _digest(plan.model_dump(mode="json"))


class BranchWorkWageRequest(StrictGameplayModel):
    """Fixed INF-4T request; branch data is admission evidence, never a writer."""

    batch_ref: str
    branch_ref: str
    branch_buffer_digest: str
    branch_base_event_digest: str
    branch_base_checkpoint_sequence: int
    branch_tail_boundary: int
    branch_replay_contract_digest: str
    candidate_intent_ref: str
    candidate_digest: str
    worker_ref: str
    production_evidence_ref: str
    authenticated_actor_ref: str
    wage_plan_digest: str


def _branch_work_wage_request_digest(request: BranchWorkWageRequest) -> str:
    return _digest(request.model_dump(mode="json"))




class PopulationPlanner:
    """Pure proposal generator; it has no store and no append method."""

    ADMITTED_BEHAVIORS = frozenset(
        {
            "routine_work",
            "schedule_gated_supply",
            "relationship_negotiation",
            "high_value_event",
            "b3_event",
        }
    )
    ACTIVATION_BEHAVIORS = frozenset(
        {"relationship_negotiation", "high_value_event", "b3_event"}
    )

    def plan_three_actor_cohort(self, read_set: PopulationReadSet) -> PopulationBatchReport:
        """Classify the closed three-actor cohort without performing writes."""
        actors = ("character:char_a", "character:char_b", "character:char_c")
        cohort_ref = self._cohort_ref(read_set.cadence.cadence_id)
        by_actor: dict[str, object] = {}
        invalid: list[PopulationRejectedCandidate] = []
        for projection in read_set.projections:
            aliases = {
                str(projection.payload.get(key)).strip()
                for key in ("actor_ref", "profile_ref", "character_ref")
                if projection.payload.get(key) not in (None, "")
            }
            actor = next(iter(aliases), "") if len(aliases) == 1 else ""
            ref_parts = projection.ref.split(":")
            ref_actor = f"character:{ref_parts[1]}" if len(ref_parts) > 2 and ref_parts[0] == "projection" else ""
            if len(aliases) != 1 or actor not in actors or ref_actor != actor:
                invalid.append(PopulationRejectedCandidate(projection.ref, "cohort_actor_ref_invalid", str(actor)))
                continue
            if actor in by_actor:
                invalid.append(PopulationRejectedCandidate(projection.ref, "cohort_actor_duplicate", actor))
                continue
            by_actor[actor] = projection
        if invalid or len(read_set.projections) != len(actors) or set(by_actor) != set(actors):
            unprocessed = tuple(projection.ref for projection in read_set.projections)
            return self._population_report(
                batch_ref=f"population-cohort:{read_set.cadence.cadence_id}",
                read_set=read_set,
                selected=(),
                presentation={},
                activations=(),
                owner_intents=(),
                rejected=tuple(invalid),
                budget_used=0,
                unprocessed=unprocessed,
            ).model_copy(
                update={
                    "cohort_ref": cohort_ref,
                    "cohort_member_refs": actors,
                    "unprocessed_count": len(unprocessed),
                }
            )
        selected: list[str] = []
        unprocessed: list[str] = []
        presentation: dict[str, object] = {}
        activations: list[PopulationActivationCandidate] = []
        intents: list[PopulationOwnerBoundIntent] = []
        budget_used = 0
        rejected: list[PopulationRejectedCandidate] = []
        for index, actor in enumerate(actors):
            projection = by_actor.get(actor)
            if projection is None:
                continue
            if len(selected) >= read_set.cadence.catch_up_limit:
                unprocessed.extend(by_actor[a].ref for a in actors[index:])
                break
            if budget_used >= read_set.cadence.budget:
                unprocessed.extend(by_actor[a].ref for a in actors[index:] if a in by_actor)
                break
            payload = dict(projection.payload)
            kind = str(payload.get("candidate_kind") or payload.get("kind") or payload.get("behavior_kind") or "")
            expected = {actors[0]: "char_a_supply", actors[1]: "char_b_routine_work", actors[2]: "char_c_social_activation"}[actor]
            if kind not in {expected, {"char_a_supply": "schedule_gated_supply", "char_b_routine_work": "routine_work", "char_c_social_activation": "relationship_negotiation"}[expected]}:
                rejected.append(PopulationRejectedCandidate(projection.ref, "cohort_behavior_mismatch", kind))
                continue
            if actor == actors[0]:
                owner_payload = self._schedule_gated_supply_owner_payload(read_set=read_set, batch_ref=f"population-cohort:{read_set.cadence.cadence_id}", actor_ref=actor, payload=payload)
                if owner_payload is None:
                    rejected.append(PopulationRejectedCandidate(projection.ref, "schedule_context_invalid", kind))
                    continue
                selected.append(projection.ref)
                budget_used += 1
                intents.append(PopulationOwnerBoundIntent(projection.ref, actor, "supply", projection.scope, owner_payload, dict(projection.revision_vector)))
            elif actor == actors[1]:
                selected.append(projection.ref)
                budget_used += 1
                presentation[actor] = {"actor_ref": actor, "behavior_kind": "routine_work", "deterministic": True, "scope": projection.scope, "source_revision_vector": dict(projection.revision_vector), "state_deltas": {}, "activation_hints": tuple(str(item) for item in (payload.get("activation_hints") or ())) }
            else:
                selected.append(projection.ref)
                budget_used += 1
                activations.append(PopulationActivationCandidate(projection.ref, actor, "relationship_negotiation_requires_activation", str(payload.get("activation_reason") or "relationship_negotiation"), 1, "actor:self", dict(projection.revision_vector)))
        report = self._population_report(batch_ref=f"population-cohort:{read_set.cadence.cadence_id}", read_set=read_set, selected=tuple(selected), presentation=presentation, activations=tuple(activations), owner_intents=tuple(intents), rejected=tuple(rejected), budget_used=budget_used, unprocessed=tuple(unprocessed))
        return report.model_copy(update={"cohort_ref": cohort_ref, "cohort_member_refs": actors, "presentation_seed_count": len(presentation), "activation_candidate_count": len(activations), "owner_intent_count": len(intents), "selected_count": len(selected), "unprocessed_count": len(unprocessed)})

    @staticmethod
    def _cohort_ref(cadence_id: str) -> str:
        prefix = "cadence:"
        return cadence_id.removeprefix(prefix) if cadence_id.startswith(prefix) else cadence_id

    @staticmethod
    def schedule_pending_digest(plan: PopulationWorldPlan) -> str:
        """Pin the exact admitted schedule plan; this is not a generic payload digest."""
        return _digest(plan.model_dump(mode="json"))

    @staticmethod
    def schedule_owner_request_digest(
        *,
        plan: PopulationWorldPlan,
        pending_change_ref: str,
        social_input: FrozenSocialPlanningInput,
        household_input: HouseholdScheduleInput,
        organization_input: OrganizationScheduleInput,
        request_context_digest: str,
    ) -> str:
        return _digest(
            {
                "plan": plan.model_dump(mode="json"),
                "pending_change_ref": pending_change_ref,
                "social_input": social_input.model_dump(mode="json"),
                "household_input": household_input.model_dump(mode="json"),
                "organization_input": organization_input.model_dump(mode="json"),
                "request_context_digest": request_context_digest,
            }
        )

    def plan_population_cycle(self, read_set: PopulationReadSet) -> PopulationBatchReport:
        """Calculate one deterministic batch; this method has no write authority."""
        cadence = read_set.cadence
        batch_ref = f"population-batch:{cadence.cadence_id}:{read_set.read_set_digest[-12:]}"
        rejected: list[PopulationRejectedCandidate] = []
        if not self._valid_population_read_set(read_set):
            for projection in read_set.projections:
                rejected.append(PopulationRejectedCandidate(projection.ref, "stale_read_set"))
            return self._population_report(
                batch_ref=batch_ref,
                read_set=read_set,
                selected=(),
                presentation={},
                activations=(),
                owner_intents=(),
                rejected=tuple(rejected),
                budget_used=0,
                unprocessed=tuple(item.ref for item in read_set.projections),
            )

        ordered = sorted(
            read_set.projections,
            key=lambda item: (
                -int(item.payload.get("priority", 0) or 0),
                str(item.payload.get("actor_ref") or item.payload.get("profile_ref") or item.ref),
                item.ref,
            ),
        )
        selected: list[str] = []
        unprocessed: list[str] = []
        presentation: dict[str, object] = {}
        activations: list[PopulationActivationCandidate] = []
        owner_intents: list[PopulationOwnerBoundIntent] = []
        budget_used = 0
        for index, projection in enumerate(ordered):
            payload = projection.payload
            kind = str(payload.get("candidate_kind") or payload.get("kind") or payload.get("behavior_kind") or "")
            if kind not in self.ADMITTED_BEHAVIORS:
                rejected.append(PopulationRejectedCandidate(projection.ref, "capability_not_admitted", kind))
                continue
            default_cost = 1 if kind in self.ACTIVATION_BEHAVIORS else 0
            try:
                cost = max(0, int(payload.get("budget_cost", default_cost) or 0))
            except (TypeError, ValueError):
                rejected.append(PopulationRejectedCandidate(projection.ref, "budget_invalid", kind))
                continue
            if kind in self.ACTIVATION_BEHAVIORS and cost == 0:
                cost = 1
            fallback = str(payload.get("fallback") or "requeue")
            if fallback not in {"no-op", "requeue"}:
                rejected.append(PopulationRejectedCandidate(projection.ref, "fallback_invalid", kind))
                continue
            if len(selected) >= cadence.catch_up_limit or budget_used + cost > cadence.budget:
                unprocessed.extend(item.ref for item in ordered[index:])
                break
            selected.append(projection.ref)
            actor_ref = str(payload.get("actor_ref") or payload.get("profile_ref") or projection.ref)
            scope = str(payload.get("actor_scope") or projection.scope)
            source_vector = dict(projection.revision_vector)
            if kind == "schedule_gated_supply":
                owner_payload = self._schedule_gated_supply_owner_payload(
                    read_set=read_set,
                    batch_ref=batch_ref,
                    actor_ref=actor_ref,
                    payload=payload,
                )
                if owner_payload is None:
                    selected.pop()
                    rejected.append(
                        PopulationRejectedCandidate(
                            projection.ref,
                            "schedule_context_invalid",
                            kind,
                        )
                    )
                    continue
                owner_intents.append(PopulationOwnerBoundIntent(projection.ref, actor_ref, kind, scope, owner_payload, source_vector))
                budget_used += cost
            elif kind in {"relationship_negotiation", "high_value_event", "b3_event"} or str(payload.get("behavior_tier", "")).upper() in {"B2", "B3"}:
                activations.append(PopulationActivationCandidate(
                    candidate_ref=projection.ref,
                    actor_ref=actor_ref,
                    reason="high_value_b2_requires_activation" if kind == "relationship_negotiation" else "high_value_b3_requires_activation",
                    activation_reason=str(payload.get("activation_reason") or kind),
                    budget=cost,
                    scope="actor:self" if actor_ref.startswith("character:") else scope,
                    source_revision_vector=source_vector,
                    fallback=fallback,
                ))
                budget_used += cost
            else:
                presentation[projection.ref] = {
                    "actor_ref": actor_ref,
                    "behavior_kind": kind,
                    "deterministic": True,
                    "scope": scope,
                    "source_revision_vector": source_vector,
                }
        return self._population_report(
            batch_ref=batch_ref,
            read_set=read_set,
            selected=tuple(selected),
            presentation=presentation,
            activations=tuple(activations),
            owner_intents=tuple(owner_intents),
            rejected=tuple(rejected),
            budget_used=budget_used,
            unprocessed=tuple(unprocessed),
        )

    def _schedule_gated_supply_owner_payload(
        self,
        *,
        read_set: PopulationReadSet,
        batch_ref: str,
        actor_ref: str,
        payload: dict[str, object],
    ) -> dict[str, object] | None:
        raw = payload.get("schedule_gated_supply_source_context")
        if raw is None:
            return dict(payload)
        if not isinstance(raw, dict) or set(raw) - {
            "mode",
            "candidate",
            "social_input",
            "household_input",
            "organization_input",
            "base_event_digest",
            "base_checkpoint_sequence",
            "tail_boundary",
        }:
            return None
        try:
            mode = WorldModeProfile.model_validate(raw["mode"])
            candidate = BatchIntentCandidate.model_validate(raw["candidate"])
            social = FrozenSocialPlanningInput.model_validate(raw["social_input"])
            household = HouseholdScheduleInput.model_validate(raw["household_input"])
            organization = OrganizationScheduleInput.model_validate(raw["organization_input"])
            base_event_digest = str(raw["base_event_digest"])
            base_checkpoint_sequence = int(raw.get("base_checkpoint_sequence", 0))
            tail_boundary = int(raw["tail_boundary"])
        except (KeyError, TypeError, ValueError):
            return None
        cadence = read_set.cadence
        if (
            not base_event_digest
            or isinstance(raw.get("base_checkpoint_sequence", 0), bool)
            or isinstance(raw.get("tail_boundary"), bool)
            or base_checkpoint_sequence < 0
            or tail_boundary < base_checkpoint_sequence
            or mode.world_ref != cadence.world_ref
            or mode.revision != cadence.world_mode_revision
            or candidate.intent_kind != "supply"
            or candidate.profile_ref != actor_ref
            or candidate.profile_ref != social.recipient_ref
            or candidate.profile_ref != household.recipient_ref
            or candidate.profile_ref != organization.recipient_ref
            or candidate.privacy_scope != cadence.report_scope
            or candidate.payload.get("organization_ref") != organization.organization_ref
            or candidate.expected_revisions.get(
                f"gameplay:organization:{organization.organization_ref}"
            )
            != organization.source_revision_vector.get(
                f"gameplay:organization:{organization.organization_ref}"
            )
            or not any(
                row.get("work_order_ref")
                == candidate.payload.get("schedule_work_order_ref")
                for row in organization.work_orders
            )
        ):
            return None
        source_vector: dict[str, int] = {}
        for vector in (
            social.source_revision_vector,
            household.source_revision_vector,
            organization.source_revision_vector,
            candidate.expected_revisions,
        ):
            for stream_id, revision in vector.items():
                if stream_id in source_vector and source_vector[stream_id] != revision:
                    return None
                source_vector[stream_id] = revision
        if source_vector != cadence.base_revision_vector:
            return None
        plan = self.plan_world(
            batch_ref=batch_ref,
            world_ref=cadence.world_ref,
            mode=mode,
            candidates=(candidate,),
            base_event_digest=base_event_digest,
            base_checkpoint_sequence=base_checkpoint_sequence,
            tail_boundary=tail_boundary,
            active_revision_refs=(mode.revision,),
            source_revision_vector=source_vector,
            deterministic_seed=cadence.deterministic_seed,
            report_scope=cadence.report_scope,
        ).model_copy(
            update={
                "source_vectors": {
                    "social": dict(social.source_revision_vector),
                    "household": dict(household.source_revision_vector),
                    "organization": dict(organization.source_revision_vector),
                },
                "social_input_digest": social.input_digest,
                "social_recipient_ref": social.recipient_ref,
                "household_input_digest": household.input_digest,
                "household_recipient_ref": household.recipient_ref,
                "organization_input_digest": organization.input_digest,
                "organization_recipient_ref": organization.recipient_ref,
                "organization_schedule_ref": organization.organization_ref,
            },
            deep=True,
        )
        enriched = dict(payload)
        enriched.pop("schedule_gated_supply_source_context", None)
        enriched["schedule_gated_supply_owner_context"] = {
            "plan": plan.model_dump(mode="json"),
            "social_input": social.model_dump(mode="json"),
            "household_input": household.model_dump(mode="json"),
            "organization_input": organization.model_dump(mode="json"),
        }
        return enriched

    @staticmethod
    def _valid_population_read_set(read_set: PopulationReadSet) -> bool:
        cadence = read_set.cadence
        canonical = PopulationReadSet.from_inputs(cadence, read_set.projections)
        if canonical.read_set_digest != read_set.read_set_digest:
            return False
        return all(
            projection.scope in {cadence.report_scope, "public", "actor:self"}
            and projection.revision_vector == cadence.base_revision_vector
            for projection in read_set.projections
        )

    @staticmethod
    def _population_report(*, batch_ref: str, read_set: PopulationReadSet, selected: tuple[str, ...], presentation: dict[str, object], activations: tuple[PopulationActivationCandidate, ...], owner_intents: tuple[PopulationOwnerBoundIntent, ...], rejected: tuple[PopulationRejectedCandidate, ...], budget_used: int, unprocessed: tuple[str, ...]) -> PopulationBatchReport:
        cadence = read_set.cadence
        report = PopulationBatchReport(
            batch_ref=batch_ref,
            selected_cohort_refs=selected,
            presentation_seeds=presentation,
            activation_candidates=tuple(item.candidate_ref for item in activations),
            owner_bound_intents=owner_intents,
            rejected_candidates=rejected,
            budget_used=budget_used,
            budget_remaining=max(0, cadence.budget - budget_used),
            unprocessed_cohort_refs=unprocessed,
            read_set_digest=read_set.read_set_digest,
            result_digest="pending",
        )
        digest = _digest({
            "batch_ref": batch_ref,
            "selected_cohort_refs": selected,
            "presentation_seeds": presentation,
            "activation_candidates": [asdict(item) for item in activations],
            "owner_bound_intents": [asdict(item) for item in owner_intents],
            "rejected_candidates": [asdict(item) for item in rejected],
            "budget_used": budget_used,
            "budget_remaining": max(0, cadence.budget - budget_used),
            "unprocessed_cohort_refs": unprocessed,
            "read_set_digest": read_set.read_set_digest,
        })
        return report.model_copy(update={"result_digest": digest})

    def plan(
        self,
        *,
        batch_ref: str,
        world_ref: str,
        mode: WorldModeProfile,
        candidates: tuple[BatchIntentCandidate, ...],
        input_digest: str,
        deterministic_seed: str,
    ) -> PopulationBatchPlan:
        ordered = tuple(
            sorted(
                candidates,
                key=lambda item: (-item.priority, item.profile_ref, item.intent_ref),
            )
        )[: mode.batch_limit]
        return PopulationBatchPlan(
            batch_ref=batch_ref,
            world_ref=world_ref,
            policy_revision=mode.revision,
            package_revision=ordered[0].package_revision if ordered else "package:none",
            deterministic_seed=deterministic_seed,
            input_digest=input_digest,
            budget=mode.wake_budget,
            candidates=ordered,
        )

    def plan_from_social_input(
        self,
        *,
        store: GameplayEventStore,
        batch_ref: str,
        world_ref: str,
        mode: WorldModeProfile,
        social_input: FrozenSocialPlanningInput,
        candidates: tuple[BatchIntentCandidate, ...],
        deterministic_seed: str,
        unsupported_inputs: tuple[str, ...] = (),
    ) -> SocialPlanningResult:
        if unsupported_inputs:
            return SocialPlanningResult(accepted=False, error_code="inf4r_unsupported_input")
        validation = social_input.validate_against(store=store)
        if not validation.accepted:
            return SocialPlanningResult(accepted=False, error_code=validation.error_code)
        if world_ref != mode.world_ref:
            return SocialPlanningResult(accepted=False, error_code="inf4r_world_mode_mismatch")
        if any(candidate.profile_ref != social_input.recipient_ref for candidate in candidates):
            return SocialPlanningResult(accepted=False, error_code="social_recipient_scope_denied")
        plan = self.plan(
            batch_ref=batch_ref,
            world_ref=world_ref,
            mode=mode,
            candidates=candidates,
            input_digest=social_input.input_digest,
            deterministic_seed=deterministic_seed,
        )
        plan = plan.model_copy(
            update={
                "social_recipient_ref": social_input.recipient_ref,
                "social_observed_at": social_input.observed_at,
                "social_projection_digest": social_input.projection_digest,
                "social_source_revision_vector": dict(social_input.source_revision_vector),
            },
            deep=True,
        )
        return SocialPlanningResult(accepted=True, plan=plan)

    def plan_from_source_inputs(
        self,
        *,
        store: GameplayEventStore,
        batch_ref: str,
        world_ref: str,
        mode: WorldModeProfile,
        household_input: HouseholdScheduleInput,
        organization_input: OrganizationScheduleInput,
        candidates: tuple[BatchIntentCandidate, ...],
        deterministic_seed: str,
    ) -> SocialPlanningResult:
        if household_input.recipient_ref != organization_input.recipient_ref:
            return SocialPlanningResult(accepted=False, error_code="source_recipient_scope_denied")
        for source in (household_input, organization_input):
            validation = source.validate_against(store=store)
            if not validation.accepted:
                return SocialPlanningResult(accepted=False, error_code=validation.error_code)
        if world_ref != mode.world_ref:
            return SocialPlanningResult(accepted=False, error_code="inf4x_world_mode_mismatch")
        if any(candidate.profile_ref != household_input.recipient_ref for candidate in candidates):
            return SocialPlanningResult(accepted=False, error_code="source_recipient_scope_denied")
        plan = self.plan(
            batch_ref=batch_ref,
            world_ref=world_ref,
            mode=mode,
            candidates=candidates,
            input_digest=_digest(
                {
                    "household": household_input.input_digest,
                    "organization": organization_input.input_digest,
                }
            ),
            deterministic_seed=deterministic_seed,
        ).model_copy(
            update={
                "household_recipient_ref": household_input.recipient_ref,
                "household_observed_at": household_input.observed_at,
                "household_projection_digest": household_input.projection_digest,
                "household_source_revision_vector": dict(household_input.source_revision_vector),
                "organization_recipient_ref": organization_input.recipient_ref,
                "organization_observed_at": organization_input.observed_at,
                "organization_projection_digest": organization_input.projection_digest,
                "organization_source_revision_vector": dict(organization_input.source_revision_vector),
            },
            deep=True,
        )
        return SocialPlanningResult(accepted=True, plan=plan)

    def plan_world(
        self,
        *,
        batch_ref: str,
        world_ref: str,
        mode: WorldModeProfile,
        candidates: tuple[BatchIntentCandidate, ...],
        base_event_digest: str,
        tail_boundary: int,
        active_revision_refs: tuple[str, ...],
        source_revision_vector: dict[str, int],
        deterministic_seed: str,
        report_scope: str,
        base_checkpoint_sequence: int = 0,
        activation_lock_refs: tuple[str, ...] = (),
    ) -> PopulationWorldPlan:
        plan = self.plan(
            batch_ref=batch_ref,
            world_ref=world_ref,
            mode=mode,
            candidates=candidates,
            input_digest=_digest({
                "base_event_digest": base_event_digest,
                "base_checkpoint_sequence": base_checkpoint_sequence,
                "tail_boundary": tail_boundary,
                "active_revision_refs": active_revision_refs,
                "source_revision_vector": dict(sorted(source_revision_vector.items())),
                "report_scope": report_scope,
            }),
            deterministic_seed=deterministic_seed,
        )
        return PopulationWorldPlan(
            batch_ref=plan.batch_ref,
            world_ref=plan.world_ref,
            mode=mode.mode,
            mode_revision=mode.revision,
            package_revision=plan.package_revision,
            policy_revision=plan.policy_revision,
            deterministic_seed=plan.deterministic_seed,
            input_digest=plan.input_digest,
            source_vectors={"world": dict(source_revision_vector)},
            base_checkpoint_event_count=base_checkpoint_sequence,
            tail_event_count=tail_boundary - base_checkpoint_sequence,
            budget=plan.budget,
            activation_locks=activation_lock_refs,
            idempotency_keys=tuple(candidate.idempotency_key for candidate in plan.candidates),
            report_scope=report_scope,
            candidates=plan.candidates,
            base_event_digest=base_event_digest,
            base_checkpoint_sequence=base_checkpoint_sequence,
            tail_boundary=tail_boundary,
            active_revision_refs=active_revision_refs,
            source_revision_vector=dict(source_revision_vector),
            activation_lock_refs=activation_lock_refs,
        )

    def plan_capability_gated_supply(
        self,
        *,
        store: GameplayEventStore,
        batch_ref: str,
        world_ref: str,
        mode: WorldModeProfile,
        capability_input: FrozenCapabilityEligibilityInput,
        candidate: BatchIntentCandidate,
        base_event_digest: str,
        tail_boundary: int,
        active_revision_refs: tuple[str, ...],
        deterministic_seed: str,
        report_scope: str,
    ) -> SocialPlanningResult:
        validation = capability_input.validate_against(store=store)
        if not validation.accepted:
            return SocialPlanningResult(accepted=False, error_code=validation.error_code)
        if world_ref != mode.world_ref:
            return SocialPlanningResult(accepted=False, error_code="inf4y_world_mode_mismatch")
        if capability_input.policy_revision not in active_revision_refs:
            return SocialPlanningResult(accepted=False, error_code="capability_policy_not_pinned")
        if candidate.intent_kind != "supply":
            return SocialPlanningResult(accepted=False, error_code="capability_consumer_intent_unsupported")
        if candidate.payload.get("required_capability_ref") != capability_input.capability_ref or candidate.payload.get("required_capability_jurisdiction_ref") != capability_input.jurisdiction_ref:
            return SocialPlanningResult(accepted=False, error_code="capability_candidate_mapping_denied")
        source_vector = dict(candidate.expected_revisions)
        for stream_id, revision in capability_input.source_revision_vector.items():
            if stream_id in source_vector and source_vector[stream_id] != revision:
                return SocialPlanningResult(accepted=False, error_code="capability_source_vector_conflict")
            source_vector[stream_id] = revision
        plan = self.plan_world(
            batch_ref=batch_ref,
            world_ref=world_ref,
            mode=mode,
            candidates=(candidate,),
            base_event_digest=base_event_digest,
            tail_boundary=tail_boundary,
            active_revision_refs=active_revision_refs,
            source_revision_vector=source_vector,
            deterministic_seed=deterministic_seed,
            report_scope=report_scope,
        ).model_copy(
            update={
                "capability_ref": capability_input.capability_ref,
                "capability_jurisdiction_ref": capability_input.jurisdiction_ref,
                "capability_revision": capability_input.capability_revision,
                "capability_policy_revision": capability_input.policy_revision,
                "capability_evaluated_tick": capability_input.evaluated_tick,
                "capability_source_event_refs": capability_input.source_event_refs,
                "capability_projection_digest": capability_input.projection_digest,
                "capability_source_revision_vector": dict(capability_input.source_revision_vector),
                "capability_reader_scope": capability_input.reader_scope,
                "capability_eligibility_digest": capability_input.input_digest,
            },
            deep=True,
        )
        return SocialPlanningResult(accepted=True, plan=plan)

    def plan_capability_gated_inspection(
        self,
        *,
        store: GameplayEventStore,
        batch_ref: str,
        world_ref: str,
        mode: WorldModeProfile,
        capability_input: FrozenCapabilityEligibilityInput,
        candidate: BatchIntentCandidate,
        base_event_digest: str,
        tail_boundary: int,
        active_revision_refs: tuple[str, ...],
        deterministic_seed: str,
        report_scope: str,
    ) -> SocialPlanningResult:
        validation = capability_input.validate_against(store=store)
        if not validation.accepted:
            return SocialPlanningResult(accepted=False, error_code=validation.error_code)
        if world_ref != mode.world_ref:
            return SocialPlanningResult(accepted=False, error_code="inf4y_world_mode_mismatch")
        if capability_input.policy_revision not in active_revision_refs:
            return SocialPlanningResult(accepted=False, error_code="capability_policy_not_pinned")
        if candidate.intent_kind != "inspection":
            return SocialPlanningResult(accepted=False, error_code="capability_consumer_intent_unsupported")
        if (
            candidate.payload.get("required_capability_ref") != capability_input.capability_ref
            or candidate.payload.get("required_capability_jurisdiction_ref") != capability_input.jurisdiction_ref
            or candidate.payload.get("jurisdiction_ref") != capability_input.jurisdiction_ref
        ):
            return SocialPlanningResult(accepted=False, error_code="capability_candidate_mapping_denied")
        source_vector = dict(candidate.expected_revisions)
        for stream_id, revision in capability_input.source_revision_vector.items():
            if stream_id in source_vector and source_vector[stream_id] != revision:
                return SocialPlanningResult(accepted=False, error_code="capability_source_vector_conflict")
            source_vector[stream_id] = revision
        plan = self.plan_world(
            batch_ref=batch_ref,
            world_ref=world_ref,
            mode=mode,
            candidates=(candidate,),
            base_event_digest=base_event_digest,
            tail_boundary=tail_boundary,
            active_revision_refs=active_revision_refs,
            source_revision_vector=source_vector,
            deterministic_seed=deterministic_seed,
            report_scope=report_scope,
        ).model_copy(
            update={
                "capability_ref": capability_input.capability_ref,
                "capability_jurisdiction_ref": capability_input.jurisdiction_ref,
                "capability_revision": capability_input.capability_revision,
                "capability_policy_revision": capability_input.policy_revision,
                "capability_evaluated_tick": capability_input.evaluated_tick,
                "capability_source_event_refs": capability_input.source_event_refs,
                "capability_projection_digest": capability_input.projection_digest,
                "capability_source_revision_vector": dict(capability_input.source_revision_vector),
                "capability_reader_scope": capability_input.reader_scope,
                "capability_eligibility_digest": capability_input.input_digest,
            },
            deep=True,
        )
        return SocialPlanningResult(accepted=True, plan=plan)

    def plan_production_evidence_wage(
        self,
        *,
        store: GameplayEventStore,
        batch_ref: str,
        world_ref: str,
        mode: WorldModeProfile,
        production_evidence_input: ProductionCompletedEvidenceInput,
        candidate: BatchIntentCandidate,
        base_event_digest: str,
        tail_boundary: int,
        active_revision_refs: tuple[str, ...],
        deterministic_seed: str,
        report_scope: str,
    ) -> SocialPlanningResult:
        validation = production_evidence_input.validate_against(store=store)
        if not validation.accepted:
            return SocialPlanningResult(accepted=False, error_code=validation.error_code)
        if world_ref != mode.world_ref or candidate.intent_kind != "work":
            return SocialPlanningResult(accepted=False, error_code="production_wage_candidate_unsupported")
        if candidate.profile_ref != production_evidence_input.recipient_ref or candidate.privacy_scope != "actor:self" or report_scope != "actor:self":
            return SocialPlanningResult(accepted=False, error_code="production_wage_privacy_denied")
        wage_policy_revision = str(candidate.payload.get("wage_policy_revision", ""))
        if wage_policy_revision not in active_revision_refs:
            return SocialPlanningResult(accepted=False, error_code="production_wage_policy_unpinned")
        wage_stream = f"gameplay:economy:wage:{candidate.profile_ref}"
        expected_wage_revision = candidate.expected_revisions.get(wage_stream)
        if expected_wage_revision is None or store.get_stream_head(wage_stream) != expected_wage_revision:
            return SocialPlanningResult(accepted=False, error_code="production_wage_revision_conflict")
        source_vector = dict(production_evidence_input.source_revision_vector)
        source_vector[wage_stream] = expected_wage_revision
        plan = self.plan_world(
            batch_ref=batch_ref,
            world_ref=world_ref,
            mode=mode,
            candidates=(candidate,),
            base_event_digest=base_event_digest,
            tail_boundary=tail_boundary,
            active_revision_refs=active_revision_refs,
            source_revision_vector=source_vector,
            deterministic_seed=deterministic_seed,
            report_scope=report_scope,
        ).model_copy(
            update={
                "production_evidence_recipient_ref": production_evidence_input.recipient_ref,
                "production_evidence_observed_at": production_evidence_input.observed_at,
                "production_evidence_projection_digest": production_evidence_input.projection_digest,
                "production_evidence_refs": production_evidence_input.evidence_refs,
                "production_evidence_rows": production_evidence_input.evidence_rows,
                "production_evidence_event_refs": production_evidence_input.source_event_refs,
                "production_evidence_source_revision_vector": dict(production_evidence_input.source_revision_vector),
                "production_evidence_input_digest": production_evidence_input.input_digest,
            },
            deep=True,
        )
        return SocialPlanningResult(accepted=True, plan=plan)

    def plan_from_world_inputs(
        self,
        *,
        store: GameplayEventStore,
        batch_ref: str,
        world_ref: str,
        mode: WorldModeProfile,
        social_input: FrozenSocialPlanningInput,
        household_input: HouseholdScheduleInput | None,
        organization_input: OrganizationScheduleInput | None,
        candidates: tuple[BatchIntentCandidate, ...],
        deterministic_seed: str,
        mode_name: str,
        capability_input: CivilizationCapabilityView | None = None,
    ) -> SocialPlanningResult:
        # INF-4Y-A admits the owner/read surface only. No consumer binding exists.
        if capability_input is not None:
            return SocialPlanningResult(
                accepted=False,
                error_code="civilization_capability_consumer_not_admitted",
            )
        if household_input is None or organization_input is None:
            return SocialPlanningResult(accepted=False, error_code="population_world_source_missing")
        if mode_name not in {"game", "simulation", "preview"}:
            return SocialPlanningResult(accepted=False, error_code="population_world_mode_invalid")
        social_result = self.plan_from_social_input(
            store=store,
            batch_ref=batch_ref,
            world_ref=world_ref,
            mode=mode,
            social_input=social_input,
            candidates=candidates,
            deterministic_seed=deterministic_seed,
        )
        if not social_result.accepted:
            return social_result
        source_result = self.plan_from_source_inputs(
            store=store,
            batch_ref=batch_ref,
            world_ref=world_ref,
            mode=mode,
            household_input=household_input,
            organization_input=organization_input,
            candidates=candidates,
            deterministic_seed=deterministic_seed,
        )
        if not source_result.accepted:
            return source_result
        if social_result.plan is None or source_result.plan is None:
            return SocialPlanningResult(accepted=False, error_code="population_world_plan_missing")
        if social_input.recipient_ref != household_input.recipient_ref:
            return SocialPlanningResult(accepted=False, error_code="source_recipient_scope_denied")
        # The planner stays proposal-only. Preserve every validated owner pin in
        # one plan so a later, owner-bound consumer can revalidate all sources.
        combined = social_result.plan.model_copy(
            update={
                "input_digest": _digest(
                    {
                        "social": social_input.input_digest,
                        "household": household_input.input_digest,
                        "organization": organization_input.input_digest,
                    }
                ),
                "household_recipient_ref": source_result.plan.household_recipient_ref,
                "household_observed_at": source_result.plan.household_observed_at,
                "household_projection_digest": source_result.plan.household_projection_digest,
                "household_source_revision_vector": dict(source_result.plan.household_source_revision_vector),
                "organization_recipient_ref": source_result.plan.organization_recipient_ref,
                "organization_observed_at": source_result.plan.organization_observed_at,
                "organization_projection_digest": source_result.plan.organization_projection_digest,
                "organization_source_revision_vector": dict(source_result.plan.organization_source_revision_vector),
            },
            deep=True,
        )
        return SocialPlanningResult(accepted=True, plan=combined)

    def plan_schedule_gated_supply(
        self,
        *,
        store: GameplayEventStore,
        batch_ref: str,
        world_ref: str,
        mode: WorldModeProfile,
        social_input: FrozenSocialPlanningInput,
        household_input: HouseholdScheduleInput,
        organization_input: OrganizationScheduleInput,
        candidate: BatchIntentCandidate,
        base_event_digest: str,
        tail_boundary: int,
        active_revision_refs: tuple[str, ...],
        deterministic_seed: str,
        report_scope: str,
        activation_lock_refs: tuple[str, ...] = (),
    ) -> SocialPlanningResult:
        """Bind existing schedule projections to the already admitted supply row."""
        source = self.plan_from_world_inputs(
            store=store,
            batch_ref=batch_ref,
            world_ref=world_ref,
            mode=mode,
            social_input=social_input,
            household_input=household_input,
            organization_input=organization_input,
            candidates=(candidate,),
            deterministic_seed=deterministic_seed,
            mode_name=mode.mode,
        )
        if not source.accepted or source.plan is None:
            return source
        if candidate.intent_kind != "supply" or candidate.profile_ref != organization_input.recipient_ref:
            return SocialPlanningResult(accepted=False, error_code="schedule_consumer_mapping_denied")
        if report_scope != candidate.privacy_scope:
            return SocialPlanningResult(accepted=False, error_code="schedule_privacy_denied")
        payload = candidate.payload
        if payload.get("organization_ref") != organization_input.organization_ref:
            return SocialPlanningResult(accepted=False, error_code="schedule_organization_scope_denied")
        work_order_ref = payload.get("schedule_work_order_ref")
        if not isinstance(work_order_ref, str) or not any(row.get("work_order_ref") == work_order_ref for row in organization_input.work_orders):
            return SocialPlanningResult(accepted=False, error_code="schedule_work_order_missing")
        source_vector: dict[str, int] = {}
        for vector in (
            social_input.source_revision_vector,
            household_input.source_revision_vector,
            organization_input.source_revision_vector,
            candidate.expected_revisions,
        ):
            for stream_id, revision in vector.items():
                if stream_id in source_vector and source_vector[stream_id] != revision:
                    return SocialPlanningResult(accepted=False, error_code="schedule_source_vector_conflict")
                source_vector[stream_id] = revision
        organization_stream = f"gameplay:organization:{organization_input.organization_ref}"
        if candidate.expected_revisions.get(organization_stream) != organization_input.source_revision_vector.get(organization_stream):
            return SocialPlanningResult(accepted=False, error_code="schedule_target_revision_unpinned")
        if self._stream_stale(store=store, source_vector=source_vector):
            return SocialPlanningResult(accepted=False, error_code="source_revision_stale")
        plan = self.plan_world(
            batch_ref=batch_ref,
            world_ref=world_ref,
            mode=mode,
            candidates=(candidate,),
            base_event_digest=base_event_digest,
            tail_boundary=tail_boundary,
            active_revision_refs=active_revision_refs,
            source_revision_vector=source_vector,
            deterministic_seed=deterministic_seed,
            report_scope=report_scope,
            activation_lock_refs=activation_lock_refs,
        ).model_copy(
            update={
                "source_vectors": {
                    "social": dict(social_input.source_revision_vector),
                    "household": dict(household_input.source_revision_vector),
                    "organization": dict(organization_input.source_revision_vector),
                },
                "social_input_digest": social_input.input_digest,
                "social_recipient_ref": social_input.recipient_ref,
                "household_input_digest": household_input.input_digest,
                "household_recipient_ref": household_input.recipient_ref,
                "organization_input_digest": organization_input.input_digest,
                "organization_recipient_ref": organization_input.recipient_ref,
                "organization_schedule_ref": organization_input.organization_ref,
            },
            deep=True,
        )
        return SocialPlanningResult(accepted=True, plan=plan)

    @staticmethod
    def _stream_stale(*, store: GameplayEventStore, source_vector: dict[str, int]) -> bool:
        return any(store.get_stream_head(stream_id) != revision for stream_id, revision in source_vector.items())


    def envelopes(
        self, plan: PopulationBatchPlan
    ) -> tuple[GameplayCommandEnvelope, ...]:
        return tuple(self._envelope(plan, candidate) for candidate in plan.candidates)

    @staticmethod
    def _envelope(
        plan: PopulationBatchPlan, candidate: BatchIntentCandidate
    ) -> GameplayCommandEnvelope:
        payload = dict(candidate.payload)
        payload.update(
            {
                "profile_ref": candidate.profile_ref,
                "intent_ref": candidate.intent_ref,
                "claim_refs": list(candidate.claim_refs),
                "policy_revision": candidate.policy_revision,
                "package_revision": candidate.package_revision,
                "expected_revisions": dict(candidate.expected_revisions),
                "batch_plan_digest": _plan_digest(plan),
            }
        )
        return GameplayCommandEnvelope(
            command_id=candidate.intent_ref,
            command_type=f"population.intent.{candidate.intent_kind}",
            command_version=1,
            principal_ref=candidate.source_ref,
            actor_ref=candidate.profile_ref,
            project_ref=plan.world_ref,
            transaction_id=f"transaction:{plan.batch_ref}",
            idempotency_key=candidate.idempotency_key,
            expected_revisions=dict(candidate.expected_revisions),
            causation_id=f"batch:{plan.batch_ref}",
            correlation_id=candidate.correlation_id,
            source_ref=candidate.source_ref,
            submitted_at="population-planner",
            pinned_revisions={"policy": 1, "package": 1},
            payload=payload,
        )


class ContinuityMergeAuthority:
    def __init__(
        self,
        *,
        store: GameplayEventStore,
        registry: CharacterProfileRegistry,
        mode: WorldModeProfile,
    ) -> None:
        self.store = store
        self.registry = registry
        self.mode = mode

    def merge(self, plan: PopulationBatchPlan) -> ContinuityMergeReceipt:
        # A PopulationBatchPlan has no owner-fragment mapping. It must never turn
        # caller-selected stream/event payload into production truth.
        return self._failed(plan, "legacy_population_merge_retired")

    def merge_world_plan(
        self,
        plan: PopulationWorldPlan,
        *,
        owner_request_digest: str | None = None,
    ) -> ContinuityMergeReceipt:
        if plan.world_ref != self.mode.world_ref or plan.policy_revision != self.mode.revision:
            return self._failed(plan, "stale_policy_revision")
        if plan.mode != self.mode.mode:
            return self._failed(plan, "world_mode_mismatch")
        # Preview plans are consumed only by BranchPreviewAuthority's isolated buffer.
        if plan.mode == "preview":
            return self._failed(plan, "preview_requires_branch")
        if plan.report_scope not in self.mode.allowed_privacy_scopes:
            return self._failed(plan, "privacy_denial")
        candidate = plan.candidates[0]
        owner_principal_ref = (
            GovernmentAuthority._PRINCIPAL
            if candidate.intent_kind == "inspection"
            else OrganizationAuthority._PRINCIPAL
            if candidate.intent_kind == "supply"
            else None
        )
        if owner_principal_ref is not None:
            existing = self.store.get_by_idempotency(
                owner_principal_ref, f"merge:{plan.batch_ref}"
            )
            if existing is not None:
                event = self.store.get_event(existing.committed_event_ids[0])
                stored_request_digest = event.payload.get(
                    "population_owner_request_digest"
                )
                if stored_request_digest != owner_request_digest and (
                    stored_request_digest is not None
                    or owner_request_digest is not None
                ):
                    return self._failed(plan, "idempotency_key_reused")
                replay = GameplayProjectionReplay(
                    projector_id="population-continuity",
                    projector_version="1",
                ).full_replay(self.store.read_events())
                return ContinuityMergeReceipt(
                    committed=True,
                    batch_ref=plan.batch_ref,
                    accepted_intent_refs=(candidate.intent_ref,),
                    committed_event_ids=tuple(existing.committed_event_ids),
                    revision_vector=dict(existing.resulting_stream_revisions),
                    replay_hash=replay.projection_hash,
                    scope=(plan.report_scope,),
                    redaction="scope-filtered",
                    zero_write=False,
                    idempotency_status="duplicate_replayed",
                    owner_receipt_ref=owner_principal_ref,
                )
        if any(
            self.store.get_stream_head(stream_id) != revision
            for stream_id, revision in plan.source_revision_vector.items()
        ):
            return self._failed(plan, "source_revision_stale")
        if plan.activation_lock_refs:
            return self._failed(plan, "activation_lock_pending")
        if any(candidate.intent_kind not in {"supply", "inspection"} for candidate in plan.candidates):
            return self._failed(plan, "owner_mapping_unsupported")
        payload = candidate.payload
        organization_ref = str(payload.get("organization_ref", ""))
        stream_id = (
            f"gameplay:government:{organization_ref}"
            if candidate.intent_kind == "inspection"
            else f"gameplay:organization:{organization_ref}"
        )
        expected_revision = plan.source_revision_vector.get(stream_id)
        if expected_revision is None:
            return self._failed(plan, "source_revision_missing")
        try:
            if candidate.intent_kind == "inspection":
                fragment = GovernmentAuthority(store=self.store).build_commercial_inspection_fragment(
                    inspection_ref=str(payload.get("inspection_ref", "")),
                    organization_ref=organization_ref,
                    jurisdiction_ref=str(payload.get("jurisdiction_ref", "")),
                    policy_revision=plan.policy_revision,
                    policy_digest=str(payload.get("policy_digest", "")),
                    evidence_ref=str(payload.get("evidence_ref", "")),
                    passed=bool(payload.get("passed", False)),
                )
            else:
                fragment = OrganizationAuthority(store=self.store).build_commerce_commitment_fragment(
                    organization_ref=organization_ref,
                    commitment_ref=str(payload.get("commitment_ref", "")),
                    counterparty_organization_ref=str(payload.get("counterparty_organization_ref", "")),
                    organization_grant_refs=tuple(str(item) for item in payload.get("organization_grant_refs", ())),
                    budget_reservation_refs=tuple(str(item) for item in payload.get("budget_reservation_refs", ())),
                    policy_revision=plan.policy_revision,
                    expected_revision=expected_revision,
                    capability_eligibility_digest=plan.capability_eligibility_digest,
                    capability_consumer_plan_digest=(
                        _capability_supply_plan_digest(plan)
                        if plan.capability_eligibility_digest is not None
                        else None
                    ),
                )
        except (KeyError, TypeError, ValueError):
            return self._failed(plan, "owner_mapping_rejected")
        if owner_request_digest is not None:
            fragment = fragment.model_copy(
                update={
                    "event_specs": {
                        stream_id: tuple(
                            (
                                event_type,
                                {
                                    **payload,
                                    "population_owner_request_digest": owner_request_digest,
                                },
                            )
                            for event_type, payload in specs
                        )
                        for stream_id, specs in fragment.event_specs.items()
                    }
                },
                deep=True,
            )
        batch = build_multi_stream_atomic_event_batch_from_fragments(
            command_id=f"merge:{plan.batch_ref}",
            idempotency_principal_ref=fragment.owner_principal_ref,
            idempotency_key=f"merge:{plan.batch_ref}",
            causation_id=f"batch:{plan.batch_ref}",
            correlation_id=plan.batch_ref,
            fragments=(fragment,),
        )
        if candidate.intent_kind == "inspection":
            inspection_event = next(
                event
                for event in batch.events
                if event.event_type == "gameplay.government.inspection_recorded"
            )
            batch = batch.model_copy(
                update={
                    "outbox_entries": [
                        GameplayOutboxEntry(
                            outbox_id=f"outbox:{inspection_event.event_id}",
                            transaction_id=batch.transaction_id,
                            event_id=inspection_event.event_id,
                            global_sequence=0,
                            topic="world.government.inspection.scoped_projection",
                            audience=plan.report_scope,
                            payload_projection={
                                "inspection_ref": str(payload.get("inspection_ref", "")),
                                "organization_ref": organization_ref,
                                "jurisdiction_ref": str(payload.get("jurisdiction_ref", "")),
                                "passed": bool(payload.get("passed", False)),
                            },
                        )
                    ]
                },
                deep=True,
            )
        result = self.store.append_batch(batch)
        if not result.committed:
            return self._failed(plan, result.failure.error_code if result.failure else "append_rejected")
        replay = GameplayProjectionReplay(projector_id="population-continuity", projector_version="1").full_replay(self.store.read_events())
        return ContinuityMergeReceipt(
            committed=True,
            batch_ref=plan.batch_ref,
            accepted_intent_refs=(candidate.intent_ref,),
            committed_event_ids=tuple(result.committed_event_ids),
            revision_vector=dict(result.resulting_stream_revisions),
            replay_hash=replay.projection_hash,
            scope=(plan.report_scope,),
            redaction="scope-filtered",
            zero_write=False,
            idempotency_status=result.idempotency_status,
            owner_receipt_ref=fragment.owner_principal_ref,
        )

    def merge_schedule_gated_supply(
        self,
        *,
        plan: PopulationWorldPlan,
        social_input: FrozenSocialPlanningInput,
        household_input: HouseholdScheduleInput,
        organization_input: OrganizationScheduleInput,
        owner_request_digest: str | None = None,
    ) -> ContinuityMergeReceipt:
        """Recheck frozen existing-owner sources before the approved supply merge."""
        candidate = plan.candidates[0]
        if (
            plan.social_input_digest != social_input.input_digest
            or plan.household_input_digest != household_input.input_digest
            or plan.organization_input_digest != organization_input.input_digest
            or plan.social_recipient_ref != social_input.recipient_ref
            or plan.household_recipient_ref != household_input.recipient_ref
            or plan.organization_recipient_ref != organization_input.recipient_ref
            or plan.organization_schedule_ref != organization_input.organization_ref
        ):
            return self._failed(plan, "schedule_source_pin_mismatch")
        if candidate.intent_kind != "supply" or candidate.profile_ref != organization_input.recipient_ref:
            return self._failed(plan, "schedule_consumer_mapping_denied")
        if plan.report_scope != candidate.privacy_scope:
            return self._failed(plan, "schedule_privacy_denied")
        if candidate.payload.get("organization_ref") != organization_input.organization_ref:
            return self._failed(plan, "schedule_organization_scope_denied")
        work_order_ref = candidate.payload.get("schedule_work_order_ref")
        if not isinstance(work_order_ref, str) or not any(row.get("work_order_ref") == work_order_ref for row in organization_input.work_orders):
            return self._failed(plan, "schedule_work_order_missing")
        for source in (social_input, household_input, organization_input):
            validation = source.validate_against(store=self.store)
            if not validation.accepted:
                return self._failed(plan, validation.error_code or "schedule_source_invalid")
        if any(
            plan.source_revision_vector.get(stream_id) != revision
            for source in (social_input, household_input, organization_input)
            for stream_id, revision in source.source_revision_vector.items()
        ):
            return self._failed(plan, "schedule_source_vector_conflict")
        return self.merge_world_plan(
            plan, owner_request_digest=owner_request_digest
        )

    def merge_released_schedule_gated_supply(
        self,
        *,
        plan: PopulationWorldPlan,
        pending_change_ref: str,
        social_input: FrozenSocialPlanningInput,
        household_input: HouseholdScheduleInput,
        organization_input: OrganizationScheduleInput,
        request_context_digest: str = "",
    ) -> ContinuityMergeReceipt:
        """Consume one released activation-owned schedule admission, then the existing owner row."""
        from .activation import ProfileActivationAuthority

        released_plan = plan.model_copy(
            update={"activation_lock_refs": (), "activation_locks": ()}, deep=True
        )
        pending = ProfileActivationAuthority(
            registry=self.registry, store=self.store
        ).pending_projection(plan.world_ref).get(pending_change_ref)
        from .activation import ActivationObligationBindingContract

        binding = ActivationObligationBindingContract.by_ref(
            pending.get("binding_ref") if pending is not None else None
        )
        candidate = plan.candidates[0]
        if (
            pending is None
            or binding is None
            or binding.binding_ref != "activation-binding:schedule-gated-supply:v1"
            or binding.target_owner_ref != OrganizationAuthority._PRINCIPAL
            or pending.get("status") != "released"
            or pending.get("kind") != "schedule_gated_supply"
            or pending.get("plan_digest") != PopulationPlanner.schedule_pending_digest(plan)
            or pending.get("profile_ref") != candidate.profile_ref
            or pending.get("world_ref") != plan.world_ref
            or pending.get("lock_ref") not in plan.activation_lock_refs
        ):
            return self._failed(plan, "released_schedule_pending_invalid")
        owner_request_digest = PopulationPlanner.schedule_owner_request_digest(
            plan=plan,
            pending_change_ref=pending_change_ref,
            social_input=social_input,
            household_input=household_input,
            organization_input=organization_input,
            request_context_digest=request_context_digest,
        )
        if self.store.get_by_idempotency(
            OrganizationAuthority._PRINCIPAL, f"merge:{plan.batch_ref}"
        ) is not None:
            return self.merge_world_plan(
                released_plan, owner_request_digest=owner_request_digest
            )
        return self.merge_schedule_gated_supply(
            plan=released_plan,
            social_input=social_input,
            household_input=household_input,
            organization_input=organization_input,
            owner_request_digest=owner_request_digest,
        )

    def merge_released_survival_state_expiry(
        self,
        *,
        world_ref: str,
        profile_ref: str,
        pending_change_ref: str,
        obligation: ScheduledObligation,
    ) -> ObligationSettlementResult:
        """Settle one released activation admission through the existing Survival owner."""
        from .activation import ProfileActivationAuthority
        from .activation import ActivationObligationBindingContract

        pending = ProfileActivationAuthority(registry=self.registry, store=self.store).pending_projection(world_ref).get(pending_change_ref)
        stream_id = f"gameplay:survival:{profile_ref}"
        if (
            pending is None
            or pending.get("status") != "released"
            or pending.get("kind") != "survival_state_expiry"
            or pending.get("profile_ref") != profile_ref
            or pending.get("world_ref") != world_ref
            or pending.get("privacy_scope") != "project"
            or pending.get("obligation_id") != obligation.obligation_id
            or pending.get("policy_revision") != obligation.policy_revision
            or pending.get("expected_survival_revision") != obligation.expected_revisions.get(stream_id)
            or obligation.status != "due"
        ):
            return ObligationSettlementResult(committed=False, error_code="released_survival_pending_invalid")
        registrations = (
            ObligationLifecycleRegistration(
                policy_ref="policy:survival_state_expiry",
                policy_revision="1",
                owner_ref=SurvivalAuthority._PRINCIPAL,
                stream_pattern="gameplay:survival:{actor_ref}",
                opened_event_type="gameplay.survival.obligation_opened",
                settled_event_type="gameplay.survival.obligation_settled",
                cancelled_event_type="gameplay.survival.obligation_cancelled",
                retry_event_type="gameplay.survival.obligation_retry_scheduled",
                compensated_event_type="gameplay.survival.obligation_compensated",
                visibility_scope="project",
            ),
        )
        lifecycle = ObligationLifecycleProjection(registrations).rebuild(self.store.read_events())
        coordinator = ObligationSettlementCoordinator(store=self.store, lifecycle_registrations=registrations)
        obligation_prefix = f"obligation:survival:state:{profile_ref}:"
        state_ref = obligation.obligation_id.removeprefix(obligation_prefix)
        binding = ActivationObligationBindingContract.by_ref(
            pending.get("binding_ref") if pending is not None else None
        )
        if (
            binding is None
            or binding.pending_kind != "survival_state_expiry"
            or binding.target_owner_ref != SurvivalAuthority._PRINCIPAL
            or binding.state_ref != state_ref
            or binding.policy_ref != "policy:survival_state_expiry"
            or binding.policy_revision != "1"
            or not obligation.obligation_id.startswith(obligation_prefix)
            or state_ref not in {"state:cold", "state:dehydrated", "state:overheated", "state:fatigued"}
        ):
            return ObligationSettlementResult(committed=False, error_code="released_survival_obligation_invalid")
        existing = self.store.get_by_idempotency(
            "world_runtime.activation_survival_expiry", obligation.idempotency_key
        )
        if existing is not None and existing.committed:
            committed = lifecycle.terminal.get(obligation.obligation_id)
            if (
                committed is None
                or committed.status != "settled"
                or committed.owner_ref != SurvivalAuthority._PRINCIPAL
                or committed.stream_id != stream_id
                or committed.policy_ref != "policy:survival_state_expiry"
                or committed.policy_revision != obligation.policy_revision
                or committed.due_tick != obligation.due_tick
            ):
                return ObligationSettlementResult(committed=False, error_code="idempotency_key_reused")
            return ObligationSettlementResult(
                committed=True,
                idempotency_status="duplicate_replayed",
                committed_event_ids=tuple(existing.committed_event_ids),
                receipt=coordinator._receipt(existing, obligation),
            )
        source = lifecycle.open.get(obligation.obligation_id)
        if (
            source is None
            or source.owner_ref != SurvivalAuthority._PRINCIPAL
            or source.stream_id != stream_id
            or source.policy_ref != "policy:survival_state_expiry"
            or source.policy_revision != "1"
        ):
            return ObligationSettlementResult(committed=False, error_code="released_survival_obligation_invalid")
        canonical = SurvivalStateExpiryPolicy(policy_revision="1").build_obligation(
            actor_ref=profile_ref,
            state_ref=state_ref,
            due_tick=source.due_tick,
            expected_revision=self.store.get_stream_head(stream_id),
            status="due",
        )
        if canonical.obligation_id != obligation.obligation_id:
            return ObligationSettlementResult(committed=False, error_code="released_survival_obligation_invalid")
        if self.store.get_stream_head(stream_id) != obligation.expected_revisions.get(stream_id):
            return ObligationSettlementResult(
                committed=False,
                error_code="released_survival_obligation_invalid",
            )
        plan = coordinator.plan_settle(
            obligation=canonical,
            fragments=(
                SurvivalAuthority.build_state_expiry_fragment(
                    obligation=canonical,
                    actor_ref=profile_ref,
                    state_ref=state_ref,
                    expected_revision=self.store.get_stream_head(stream_id),
                ),
            ),
            principal_ref="world_runtime.activation_survival_expiry",
        )
        if plan.duplicate_result is not None:
            return ObligationSettlementResult(
                committed=True,
                idempotency_status="duplicate_replayed",
                committed_event_ids=tuple(plan.duplicate_result.committed_event_ids),
                receipt=plan.receipt,
            )
        if not plan.ready or plan.owner_commit_batch is None:
            return ObligationSettlementResult(
                committed=False,
                error_code=plan.error_code or "released_survival_obligation_invalid",
            )
        append = SurvivalAuthority(store=self.store).commit_obligation_batch(plan.owner_commit_batch)
        if not append.committed:
            return ObligationSettlementResult(
                committed=False,
                error_code=append.failure.error_code if append.failure else "released_survival_obligation_invalid",
            )
        return ObligationSettlementResult(
            committed=True,
            idempotency_status=append.idempotency_status,
            committed_event_ids=tuple(append.committed_event_ids),
            receipt=coordinator._receipt(append, canonical),
        )

    def merge_production_evidence_wage(self, plan: PopulationWorldPlan) -> ContinuityMergeReceipt:
        if plan.world_ref != self.mode.world_ref or plan.policy_revision != self.mode.revision or plan.mode != self.mode.mode:
            return self._failed(plan, "stale_policy_revision")
        if plan.report_scope != "actor:self" or plan.activation_lock_refs:
            return self._failed(plan, "production_wage_privacy_denied")
        if len(plan.candidates) != 1 or plan.candidates[0].intent_kind != "work":
            return self._failed(plan, "production_wage_candidate_unsupported")
        candidate = plan.candidates[0]
        if candidate.profile_ref != plan.production_evidence_recipient_ref or candidate.privacy_scope != "actor:self":
            return self._failed(plan, "production_wage_privacy_denied")
        existing = self.store.get_by_idempotency(EconomyAuthority._PRINCIPAL, f"merge:{plan.batch_ref}")
        if existing is not None:
            prior_event = self.store.get_event(existing.committed_event_ids[0])
            if prior_event.payload.get("production_wage_plan_digest") != _production_wage_plan_digest(plan):
                return self._failed(plan, "idempotency_key_reused")
            replay = GameplayProjectionReplay(projector_id="population-continuity", projector_version="1").full_replay(self.store.read_events())
            return ContinuityMergeReceipt(committed=True, batch_ref=plan.batch_ref, accepted_intent_refs=(candidate.intent_ref,), committed_event_ids=tuple(existing.committed_event_ids), revision_vector=dict(existing.resulting_stream_revisions), replay_hash=replay.projection_hash, scope=("actor:self",), redaction="scope-filtered", zero_write=False, idempotency_status="duplicate_replayed", owner_receipt_ref=EconomyAuthority._PRINCIPAL)
        input_value = ProductionCompletedEvidenceInput(
            recipient_ref=plan.production_evidence_recipient_ref or "",
            observed_at=plan.production_evidence_observed_at or "",
            owner_principal_ref="actor_gameplay.construction_production_domain",
            projection_digest=plan.production_evidence_projection_digest or "",
            source_revision_vector=dict(plan.production_evidence_source_revision_vector),
            evidence_refs=plan.production_evidence_refs,
            evidence_rows=plan.production_evidence_rows,
            source_event_refs=plan.production_evidence_event_refs,
        )
        if plan.production_evidence_input_digest != input_value.input_digest:
            return self._failed(plan, "production_evidence_input_digest_mismatch")
        validation = input_value.validate_against(store=self.store)
        if not validation.accepted:
            return self._failed(plan, validation.error_code or "production_evidence_source_invalid")
        wage_stream = f"gameplay:economy:wage:{candidate.profile_ref}"
        expected_wage_revision = candidate.expected_revisions.get(wage_stream)
        if expected_wage_revision is None or self.store.get_stream_head(wage_stream) != expected_wage_revision:
            return self._failed(plan, "production_wage_revision_conflict")
        payload = candidate.payload
        try:
            result = EconomyAuthority(store=self.store).settle_production_evidence_wage_accrual(
                command_id=f"merge:{plan.batch_ref}",
                idempotency_key=f"merge:{plan.batch_ref}",
                causation_id=f"batch:{plan.batch_ref}",
                correlation_id=plan.batch_ref,
                organization_ref=str(payload.get("organization_ref", "")),
                worker_ref=candidate.profile_ref,
                wage_obligation_ref=str(payload.get("wage_obligation_ref", "")),
                work_evidence_refs=plan.production_evidence_refs,
                production_evidence_projection_digest=plan.production_evidence_projection_digest or "",
                production_evidence_source_event_refs=plan.production_evidence_event_refs,
                production_evidence_source_revision_vector=dict(plan.production_evidence_source_revision_vector),
                production_wage_plan_digest=_production_wage_plan_digest(plan),
                wage_amount_minor=int(payload.get("wage_amount_minor", 0)),
                wage_policy_revision=str(payload.get("wage_policy_revision", "")),
                expected_wage_revision=expected_wage_revision,
            )
        except (TypeError, ValueError):
            return self._failed(plan, "production_wage_mapping_rejected")
        if not result.committed:
            return self._failed(plan, result.failure.error_code if result.failure else "append_rejected")
        replay = GameplayProjectionReplay(projector_id="population-continuity", projector_version="1").full_replay(self.store.read_events())
        return ContinuityMergeReceipt(committed=True, batch_ref=plan.batch_ref, accepted_intent_refs=(candidate.intent_ref,), committed_event_ids=tuple(result.committed_event_ids), revision_vector=dict(result.resulting_stream_revisions), replay_hash=replay.projection_hash, scope=("actor:self",), redaction="scope-filtered", zero_write=False, idempotency_status=result.idempotency_status, owner_receipt_ref=EconomyAuthority._PRINCIPAL)

    def merge_branch_work_wage(
        self,
        *,
        request: BranchWorkWageRequest,
        wage_plan: PopulationWorldPlan,
    ) -> ContinuityMergeReceipt:
        """Validate an isolated branch request, then invoke the existing Economy owner."""
        plan = wage_plan
        if (
            plan.batch_ref != request.batch_ref
            or request.wage_plan_digest != _production_wage_plan_digest(plan)
            or plan.world_ref != self.mode.world_ref
            or plan.policy_revision != self.mode.revision
            or plan.mode != self.mode.mode
            or plan.report_scope != "actor:self"
            or request.worker_ref != request.authenticated_actor_ref
            or not request.worker_ref.startswith("character:")
            or len(plan.candidates) != 1
            or plan.candidates[0].profile_ref != request.worker_ref
            or plan.candidates[0].intent_kind != "work"
            or plan.candidates[0].privacy_scope != "actor:self"
            or request.candidate_intent_ref != plan.candidates[0].intent_ref
        ):
            return self._failed(plan, "branch_work_wage_request_denied")
        request_digest = _branch_work_wage_request_digest(request)
        existing = self.store.get_by_idempotency(
            EconomyAuthority._PRINCIPAL, f"branch-wage:{request.batch_ref}"
        )
        if existing is not None:
            prior = self.store.get_event(existing.committed_event_ids[0])
            if prior.payload.get("branch_work_wage_request_digest") != request_digest:
                return self._failed(plan, "idempotency_key_reused")
            replay = GameplayProjectionReplay(
                projector_id="population-continuity", projector_version="1"
            ).full_replay(self.store.read_events())
            return ContinuityMergeReceipt(
                committed=True,
                batch_ref=plan.batch_ref,
                accepted_intent_refs=(plan.candidates[0].intent_ref,),
                committed_event_ids=tuple(existing.committed_event_ids),
                revision_vector=dict(existing.resulting_stream_revisions),
                replay_hash=replay.projection_hash,
                scope=("actor:self",),
                redaction="scope-filtered",
                zero_write=False,
                idempotency_status="duplicate_replayed",
                owner_receipt_ref=EconomyAuthority._PRINCIPAL,
            )
        from app.character_agent.profile.registry import CharacterProfileRegistry
        from app.gameplay.construction_production_runtime import ConstructionProductionAuthority
        from app.population_continuity.branch_preview import BranchPreviewAuthority

        branch_stream = BranchPreviewAuthority.admission_stream_id(branch_ref=request.branch_ref)
        snapshot_events = [
            event
            for event in self.store.read_stream(branch_stream)
            if event.event_type == "gameplay.branch_preview.isolated_snapshot_recorded"
        ]
        if len(snapshot_events) != 1:
            return self._failed(plan, "branch_snapshot_missing")
        snapshot = snapshot_events[0]
        records = snapshot.payload.get("records")
        descriptor = next((record for record in records or () if isinstance(record, dict) and record.get("kind") == "branch_descriptor"), None)
        candidate_record = next((record for record in records or () if isinstance(record, dict) and record.get("kind") == "branch_candidate_proposed" and record.get("intent_ref") == request.candidate_intent_ref), None)
        if (
            snapshot.visibility_policy != "creator_debug"
            or snapshot.payload.get("branch_ref") != request.branch_ref
            or snapshot.payload.get("buffer_digest") != request.branch_buffer_digest
            or not isinstance(records, (list, tuple))
            or not isinstance(descriptor, dict)
            or not isinstance(candidate_record, dict)
            or descriptor.get("base_event_digest") != request.branch_base_event_digest
            or descriptor.get("base_checkpoint_sequence") != request.branch_base_checkpoint_sequence
            or descriptor.get("tail_boundary") != request.branch_tail_boundary
            or descriptor.get("replay_contract_digest") != request.branch_replay_contract_digest
            or candidate_record.get("candidate_digest") != request.candidate_digest
            or candidate_record.get("profile_ref") != request.worker_ref
            or request.candidate_digest != _digest(plan.candidates[0].model_dump(mode="json"))
        ):
            return self._failed(plan, "branch_snapshot_pin_mismatch")
        try:
            branch_authority = BranchPreviewAuthority(
                store=self.store,
                registry=CharacterProfileRegistry(profiles_by_actor_id={}),
            )
            branch_authority.durable_branch_projection(request.branch_ref)
            branch_authority.production_replay()
        except (TypeError, ValueError, KeyError):
            return self._failed(plan, "branch_replay_contract_invalid")
        source = ProductionCompletedEvidenceInput(
            recipient_ref=plan.production_evidence_recipient_ref or "",
            observed_at=plan.production_evidence_observed_at or "",
            owner_principal_ref="actor_gameplay.construction_production_domain",
            projection_digest=plan.production_evidence_projection_digest or "",
            source_revision_vector=dict(plan.production_evidence_source_revision_vector),
            evidence_refs=plan.production_evidence_refs,
            evidence_rows=plan.production_evidence_rows,
            source_event_refs=plan.production_evidence_event_refs,
        )
        if request.production_evidence_ref not in source.evidence_refs:
            return self._failed(plan, "production_evidence_ref_mismatch")
        validation = source.validate_against(store=self.store)
        if not validation.accepted:
            return self._failed(plan, validation.error_code or "production_evidence_source_invalid")
        canonical = ConstructionProductionAuthority(store=self.store).completed_evidence_view_for(recipient_ref=request.worker_ref)
        if canonical.projection_hash != source.projection_digest or request.production_evidence_ref not in canonical.evidence_refs:
            return self._failed(plan, "production_evidence_source_mismatch")
        candidate = plan.candidates[0]
        wage_stream = f"gameplay:economy:wage:{request.worker_ref}"
        expected_wage_revision = candidate.expected_revisions.get(wage_stream)
        if expected_wage_revision is None or self.store.get_stream_head(wage_stream) != expected_wage_revision:
            return self._failed(plan, "production_wage_revision_conflict")
        from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:branch-work-wage-admission@1",
                contract_kind="settlement",
                owner_ref=EconomyAuthority._PRINCIPAL,
                stream_ids=(wage_stream,),
                event_types=("gameplay.economy.wage_accrued",),
                projection_scope="project",
            )
        except ValueError:
            return self._failed(plan, "branch_work_wage_contract_denied")
        payload = candidate.payload
        try:
            result = EconomyAuthority(store=self.store).settle_production_evidence_wage_accrual(
                command_id=f"branch-wage:{plan.batch_ref}",
                idempotency_key=f"branch-wage:{plan.batch_ref}",
                causation_id=f"branch:{request.branch_ref}",
                correlation_id=plan.batch_ref,
                organization_ref=str(payload.get("organization_ref", "")),
                worker_ref=request.worker_ref,
                wage_obligation_ref=str(payload.get("wage_obligation_ref", "")),
                work_evidence_refs=plan.production_evidence_refs,
                production_evidence_projection_digest=source.projection_digest,
                production_evidence_source_event_refs=source.source_event_refs,
                production_evidence_source_revision_vector=dict(source.source_revision_vector),
                production_wage_plan_digest=_production_wage_plan_digest(plan),
                wage_amount_minor=int(payload.get("wage_amount_minor", 0)),
                wage_policy_revision=str(payload.get("wage_policy_revision", "")),
                expected_wage_revision=expected_wage_revision,
                branch_work_wage_request_digest=request_digest,
            )
        except (TypeError, ValueError):
            return self._failed(plan, "branch_work_wage_mapping_rejected")
        if not result.committed:
            return self._failed(plan, result.failure.error_code if result.failure else "append_rejected")
        replay = GameplayProjectionReplay(projector_id="population-continuity", projector_version="1").full_replay(self.store.read_events())
        return ContinuityMergeReceipt(
            committed=True,
            batch_ref=plan.batch_ref,
            accepted_intent_refs=(candidate.intent_ref,),
            committed_event_ids=tuple(result.committed_event_ids),
            revision_vector=dict(result.resulting_stream_revisions),
            replay_hash=replay.projection_hash,
            scope=("actor:self",),
            redaction="scope-filtered",
            zero_write=False,
            idempotency_status=result.idempotency_status,
            owner_receipt_ref=EconomyAuthority._PRINCIPAL,
        )

    def merge_capability_gated_supply(self, plan: PopulationWorldPlan) -> ContinuityMergeReceipt:
        existing = self.store.get_by_idempotency(
            OrganizationAuthority._PRINCIPAL,
            f"merge:{plan.batch_ref}",
        )
        if existing is not None:
            event = self.store.get_event(existing.committed_event_ids[0])
            if event.payload.get("capability_consumer_plan_digest") != _capability_supply_plan_digest(plan):
                return self._failed(plan, "idempotency_key_reused")
            replay = GameplayProjectionReplay(
                projector_id="population-continuity", projector_version="1"
            ).full_replay(self.store.read_events())
            return ContinuityMergeReceipt(
                committed=True,
                batch_ref=plan.batch_ref,
                accepted_intent_refs=(plan.candidates[0].intent_ref,),
                committed_event_ids=tuple(existing.committed_event_ids),
                revision_vector=dict(existing.resulting_stream_revisions),
                replay_hash=replay.projection_hash,
                scope=(plan.report_scope,),
                redaction="scope-filtered",
                zero_write=False,
                idempotency_status="duplicate_replayed",
                owner_receipt_ref=OrganizationAuthority._PRINCIPAL,
            )
        try:
            capability_input = FrozenCapabilityEligibilityInput(
                capability_ref=plan.capability_ref or "",
                jurisdiction_ref=plan.capability_jurisdiction_ref or "",
                capability_revision=plan.capability_revision or 0,
                policy_revision=plan.capability_policy_revision or "",
                effective_tick=plan.capability_evaluated_tick or 0,
                status="active",
                visibility="authority_only",
                reader_scope=plan.capability_reader_scope or "",
                evaluated_tick=plan.capability_evaluated_tick or 0,
                source_event_refs=plan.capability_source_event_refs,
                projection_digest=plan.capability_projection_digest or "",
                source_revision_vector=dict(plan.capability_source_revision_vector),
            )
        except (TypeError, ValueError):
            return self._failed(plan, "capability_source_invalid")
        validation = capability_input.validate_against(store=self.store)
        if not validation.accepted:
            return self._failed(plan, validation.error_code or "capability_source_invalid")
        if plan.capability_eligibility_digest != capability_input.input_digest:
            return self._failed(plan, "capability_eligibility_digest_mismatch")
        if len(plan.candidates) != 1 or plan.candidates[0].intent_kind != "supply":
            return self._failed(plan, "capability_consumer_intent_unsupported")
        candidate = plan.candidates[0]
        if candidate.payload.get("required_capability_ref") != capability_input.capability_ref or candidate.payload.get("required_capability_jurisdiction_ref") != capability_input.jurisdiction_ref:
            return self._failed(plan, "capability_candidate_mapping_denied")
        return self.merge_world_plan(plan)

    def merge_capability_gated_inspection(self, plan: PopulationWorldPlan) -> ContinuityMergeReceipt:
        if plan.world_ref != self.mode.world_ref or plan.policy_revision != self.mode.revision:
            return self._failed(plan, "stale_policy_revision")
        if plan.mode != self.mode.mode:
            return self._failed(plan, "world_mode_mismatch")
        if plan.report_scope not in self.mode.allowed_privacy_scopes:
            return self._failed(plan, "privacy_denial")
        existing = self.store.get_by_idempotency(
            GovernmentAuthority._PRINCIPAL,
            f"merge:{plan.batch_ref}",
        )
        if existing is not None:
            event = self.store.get_event(existing.committed_event_ids[0])
            if event.payload.get("capability_consumer_plan_digest") != _capability_inspection_plan_digest(plan):
                return self._failed(plan, "idempotency_key_reused")
            replay = GameplayProjectionReplay(
                projector_id="population-continuity", projector_version="1"
            ).full_replay(self.store.read_events())
            return ContinuityMergeReceipt(
                committed=True,
                batch_ref=plan.batch_ref,
                accepted_intent_refs=(plan.candidates[0].intent_ref,),
                committed_event_ids=tuple(existing.committed_event_ids),
                revision_vector=dict(existing.resulting_stream_revisions),
                replay_hash=replay.projection_hash,
                scope=(plan.report_scope,),
                redaction="scope-filtered",
                zero_write=False,
                idempotency_status="duplicate_replayed",
                owner_receipt_ref=GovernmentAuthority._PRINCIPAL,
            )
        try:
            capability_input = FrozenCapabilityEligibilityInput(
                capability_ref=plan.capability_ref or "",
                jurisdiction_ref=plan.capability_jurisdiction_ref or "",
                capability_revision=plan.capability_revision or 0,
                policy_revision=plan.capability_policy_revision or "",
                effective_tick=plan.capability_evaluated_tick or 0,
                status="active",
                visibility="authority_only",
                reader_scope=plan.capability_reader_scope or "",
                evaluated_tick=plan.capability_evaluated_tick or 0,
                source_event_refs=plan.capability_source_event_refs,
                projection_digest=plan.capability_projection_digest or "",
                source_revision_vector=dict(plan.capability_source_revision_vector),
            )
        except (TypeError, ValueError):
            return self._failed(plan, "capability_source_invalid")
        validation = capability_input.validate_against(store=self.store)
        if not validation.accepted:
            return self._failed(plan, validation.error_code or "capability_source_invalid")
        if plan.capability_eligibility_digest != capability_input.input_digest:
            return self._failed(plan, "capability_eligibility_digest_mismatch")
        if len(plan.candidates) != 1 or plan.candidates[0].intent_kind != "inspection":
            return self._failed(plan, "capability_consumer_intent_unsupported")
        candidate = plan.candidates[0]
        payload = candidate.payload
        if (
            payload.get("required_capability_ref") != capability_input.capability_ref
            or payload.get("required_capability_jurisdiction_ref") != capability_input.jurisdiction_ref
            or payload.get("jurisdiction_ref") != capability_input.jurisdiction_ref
        ):
            return self._failed(plan, "capability_candidate_mapping_denied")
        if plan.capability_policy_revision not in plan.active_revision_refs:
            return self._failed(plan, "capability_policy_not_pinned")
        organization_ref = str(payload.get("organization_ref", ""))
        stream_id = f"gameplay:government:{organization_ref}"
        expected_revision = plan.source_revision_vector.get(stream_id)
        if expected_revision is None:
            return self._failed(plan, "source_revision_missing")
        if self.store.get_stream_head(stream_id) != expected_revision:
            return self._failed(plan, "source_revision_stale")
        try:
            fragment = GovernmentAuthority(store=self.store).build_commercial_inspection_fragment(
                inspection_ref=str(payload.get("inspection_ref", "")),
                organization_ref=organization_ref,
                jurisdiction_ref=str(payload.get("jurisdiction_ref", "")),
                policy_revision=plan.policy_revision,
                policy_digest=str(payload.get("policy_digest", "")),
                evidence_ref=str(payload.get("evidence_ref", "")),
                passed=bool(payload.get("passed", False)),
                capability_eligibility_digest=capability_input.input_digest,
                capability_consumer_plan_digest=_capability_inspection_plan_digest(plan),
            )
        except (KeyError, TypeError, ValueError):
            return self._failed(plan, "owner_mapping_rejected")
        batch = build_multi_stream_atomic_event_batch_from_fragments(
            command_id=f"merge:{plan.batch_ref}",
            idempotency_principal_ref=fragment.owner_principal_ref,
            idempotency_key=f"merge:{plan.batch_ref}",
            causation_id=f"batch:{plan.batch_ref}",
            correlation_id=plan.batch_ref,
            fragments=(fragment,),
        )
        inspection_event = next(
            event
            for event in batch.events
            if event.event_type == "gameplay.government.inspection_recorded"
        )
        batch = batch.model_copy(
            update={
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{inspection_event.event_id}",
                        transaction_id=batch.transaction_id,
                        event_id=inspection_event.event_id,
                        global_sequence=0,
                        topic="world.government.inspection.scoped_projection",
                        audience=plan.report_scope,
                        payload_projection={
                            "inspection_ref": str(payload.get("inspection_ref", "")),
                            "organization_ref": organization_ref,
                            "jurisdiction_ref": str(payload.get("jurisdiction_ref", "")),
                            "passed": bool(payload.get("passed", False)),
                            "capability_eligibility_digest": capability_input.input_digest,
                            "capability_consumer_plan_digest": _capability_inspection_plan_digest(plan),
                        },
                    )
                ]
            },
            deep=True,
        )
        result = self.store.append_batch(batch)
        if not result.committed:
            return self._failed(plan, result.failure.error_code if result.failure else "append_rejected")
        replay = GameplayProjectionReplay(
            projector_id="population-continuity", projector_version="1"
        ).full_replay(self.store.read_events())
        return ContinuityMergeReceipt(
            committed=True,
            batch_ref=plan.batch_ref,
            accepted_intent_refs=(candidate.intent_ref,),
            committed_event_ids=tuple(result.committed_event_ids),
            revision_vector=dict(result.resulting_stream_revisions),
            replay_hash=replay.projection_hash,
            scope=(plan.report_scope,),
            redaction="scope-filtered",
            zero_write=False,
            idempotency_status=result.idempotency_status,
            owner_receipt_ref=GovernmentAuthority._PRINCIPAL,
        )


    @staticmethod
    def _failed(plan: PopulationBatchPlan, reason: str) -> ContinuityMergeReceipt:
        return ContinuityMergeReceipt(
            committed=False,
            batch_ref=plan.batch_ref,
            zero_write=True,
            stop_reason=reason,
        )
