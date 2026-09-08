from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Callable, Protocol, Sequence

from app.character_agent.models.simulation_seed import CharacterContinuityCommand, CharacterContinuityReceipt
from app.models.authority_event import AuthorityEvent
from app.population_continuity.batch import PopulationOwnerBoundIntent, PopulationPlanner
from app.population_continuity.domain_projection_sources import production_receipt_population_projections
from app.population_continuity.models import PopulationWorldPlan
from app.population_continuity.social_input import FrozenSocialPlanningInput
from app.population_continuity.source_inputs import HouseholdScheduleInput, OrganizationScheduleInput
from app.population_continuity.models import BatchIntentCandidate
from app.population_continuity.seed_planner import CharacterSeedPlanner
from app.population_continuity.siming_contracts import PopulationBatchReport, PopulationCadenceInput, PopulationCycleResult, PopulationOwnerReceipt, PopulationReadSet
from app.population_continuity.decision_surface import PopulationCapabilityCatalog, PopulationCapabilityDescriptor, PopulationDecision, PopulationDecisionPlanner, PopulationDecisionPolicy


class PopulationOwnerExecutor(Protocol):
    def submit(self, intent: BatchIntentCandidate, *, read_set: PopulationReadSet) -> PopulationOwnerReceipt: ...


class CharacterContinuityPort(Protocol):
    def apply_command(self, command: CharacterContinuityCommand) -> CharacterContinuityReceipt: ...

    def current_revision(self, actor_ref: str) -> int: ...


ReadSetBuilder = Callable[[AuthorityEvent, PopulationCadenceInput], PopulationReadSet]
_CHARACTER_REF_PATTERN = re.compile(r"character:[a-z0-9_.-]+")


def default_population_read_set_builder(event: AuthorityEvent, cadence: PopulationCadenceInput) -> PopulationReadSet:
    """Build the scoped projection envelope and the fixed bakery owner context."""
    projections = tuple()
    raw = event.payload.get("population_projections")
    if raw is None:
        raw = [event.payload[key] for key in ("world_mode_projection", "organization_projection", "household_projection", "social_projection", "public_projection") if isinstance(event.payload.get(key), dict)]
    if isinstance(raw, (list, tuple)):
        from app.population_continuity.siming_contracts import PopulationProjection

        projections = tuple(PopulationProjection.model_validate(item) for item in raw if isinstance(item, dict))
    owner_receipt_value = event.payload.get("population_owner_receipt")
    organization_projection = event.payload.get("organization_projection")
    if isinstance(owner_receipt_value, dict) and isinstance(organization_projection, dict):
        from app.population_continuity.siming_contracts import PopulationOwnerReceipt

        try:
            owner_receipt = PopulationOwnerReceipt.model_validate(owner_receipt_value)
            projections = production_receipt_population_projections(
                owner_receipt=owner_receipt,
                organization_projection=organization_projection,
                scope=cadence.report_scope,
            )
        except (TypeError, ValueError):
            projections = ()
    def named_value(name: str, *aliases: str) -> object:
        value = event.payload.get(name)
        if value is None:
            for projection in projections:
                if projection.ref in aliases:
                    value = projection.payload
                    break
        if isinstance(value, dict) and isinstance(value.get("payload"), dict):
            value = value["payload"]
        return value

    plan_value = event.payload.get("population_world_plan") or event.payload.get("world_plan")
    if plan_value is None:
        for projection in projections:
            if projection.ref in {"world_mode", "world-mode", "world_mode_projection"}:
                plan_value = projection.payload.get("population_world_plan") or projection.payload.get("world_plan") or projection.payload.get("plan")
                break
    pending_value = event.payload.get("activation_pending_projection") or event.payload.get("activation_pending_context")
    if isinstance(plan_value, dict) and isinstance(plan_value.get("payload"), dict):
        plan_value = plan_value["payload"]
    if isinstance(pending_value, dict) and isinstance(pending_value.get("payload"), dict):
        pending_value = pending_value["payload"]
    if isinstance(plan_value, dict) and isinstance(pending_value, dict):
        try:
            plan = PopulationWorldPlan.model_validate(plan_value)
            pending_candidates = ((pending_value,) if "change_ref" in pending_value else tuple(
                item for item in pending_value.values() if isinstance(item, dict)
            ))
            pending_rows = tuple(
                row for row in pending_candidates
                if isinstance(row, dict)
                and row.get("kind") == "schedule_gated_supply"
                and row.get("status") == "released"
                and row.get("plan_digest") == PopulationPlanner.schedule_pending_digest(plan)
            )
            def source_value(name: str) -> object:
                value = named_value(name, name.removesuffix("_projection"))
                input_name = name.removesuffix("_projection") + "_input"
                if isinstance(value, dict) and isinstance(value.get(input_name), dict):
                    value = value[input_name]
                return value
            source_values = {
                "social_input": FrozenSocialPlanningInput.model_validate(source_value("social_projection")),
                "household_input": HouseholdScheduleInput.model_validate(source_value("household_projection")),
                "organization_input": OrganizationScheduleInput.model_validate(source_value("organization_projection")),
            }
            if len(pending_rows) == 1:
                pending = pending_rows[0]
                for index, projection in enumerate(projections):
                    payload = projection.payload
                    if str(payload.get("candidate_kind") or payload.get("kind") or payload.get("behavior_kind") or "") != "schedule_gated_supply":
                        continue
                    actor_ref = str(payload.get("actor_ref") or payload.get("profile_ref") or "")
                    candidate = plan.candidates[0]
                    if (
                        candidate.profile_ref != actor_ref
                        or pending.get("profile_ref") != actor_ref
                        or pending.get("world_ref") != plan.world_ref
                        or pending.get("lock_ref") not in plan.activation_lock_refs
                        or any(value.recipient_ref != actor_ref for value in source_values.values())
                    ):
                        continue
                    context = {
                        "plan": plan.model_dump(mode="json"),
                        "pending_change_ref": pending.get("change_ref"),
                        **{key: value.model_dump(mode="json") for key, value in source_values.items()},
                    }
                    projections = projections[:index] + (
                        projection.model_copy(update={"payload": {**payload, "schedule_gated_supply_owner_context": context}}, deep=True),
                    ) + projections[index + 1:]
                    break
        except (KeyError, TypeError, ValueError):
            pass
    return PopulationReadSet.from_inputs(cadence, projections)


class PopulationSimulationCapability:
    _ADMITTED_SCOPES = frozenset({"organization:summary", "public", "actor:self"})
    _V1_SELECTOR = "selector:cohort-bakery:v1"
    _V1_RULESET = "rules:cohort-bakery:v1"
    _V1_ACTORS = ("character:char_a", "character:char_b", "character:char_c")

    def __init__(self, *, planner: PopulationPlanner | None = None, seed_planner: CharacterSeedPlanner | None = None, owner_executor: PopulationOwnerExecutor | None = None, continuity_port: CharacterContinuityPort | None = None, decision_planner: PopulationDecisionPlanner | None = None, owner_executors: Mapping[str, PopulationOwnerExecutor] | None = None) -> None:
        self._planner = planner or PopulationPlanner()
        self._seed_planner = seed_planner or CharacterSeedPlanner()
        self._owner_executor = owner_executor
        self._continuity_port = continuity_port
        self._decision_planner = decision_planner or PopulationDecisionPlanner()
        self._owner_executors = dict(owner_executors or {})

    @classmethod
    def default_decision_policy(cls, cadence: PopulationCadenceInput) -> PopulationDecisionPolicy:
        return PopulationDecisionPolicy(
            policy_revision=cadence.policy_revision,
            default_fidelity_tier="B1",
            budget=cadence.budget,
            max_candidates=cadence.catch_up_limit,
        )

    @classmethod
    def default_capabilities(
        cls, cadence: PopulationCadenceInput
    ) -> tuple[PopulationCapabilityDescriptor, ...]:
        return PopulationCapabilityCatalog.default(cadence.policy_revision)

    def run_default_decision_cycle(
        self, cadence_input: PopulationCadenceInput, read_set: PopulationReadSet
    ) -> PopulationCycleResult:
        return self.run_decision_cycle(
            cadence_input,
            read_set,
            self.default_decision_policy(cadence_input),
            self.default_capabilities(cadence_input),
        )

    @staticmethod
    def is_v1_fixture(read_set: PopulationReadSet) -> bool:
        return PopulationSimulationCapability._looks_like_v1_cohort(read_set)

    def run_decision_cycle(
        self,
        cadence_input: PopulationCadenceInput,
        read_set: PopulationReadSet,
        policy: PopulationDecisionPolicy,
        capabilities: tuple[PopulationCapabilityDescriptor, ...],
    ) -> PopulationCycleResult:
        return self._run_decision_cycle(cadence_input, read_set, policy, capabilities)

    def _run_decision_cycle(
        self,
        cadence_input: PopulationCadenceInput,
        read_set: PopulationReadSet,
        policy: PopulationDecisionPolicy,
        capabilities: tuple[PopulationCapabilityDescriptor, ...],
        *,
        accepted_owner_receipt_refs: Sequence[str] = (),
    ) -> PopulationCycleResult:
        """Evaluate and settle a generic decision through existing authority paths."""
        if read_set.cadence != cadence_input:
            return self._requeue(f"population-batch:{cadence_input.cadence_id}:requeue", read_set, "stale_read_set")
        candidates = self._decision_planner.evaluate(read_set, capabilities, policy)
        candidates = self._decision_planner.filter_registered(candidates, capabilities)
        decision = self._decision_planner.select(candidates, policy).model_copy(
            update={"read_set_digest": read_set.read_set_digest}
        )
        selected_refs = {
            projection_ref
            for candidate in decision.selected_candidates
            for projection_ref in candidate.source_projection_refs
        }
        selected_projections = tuple(
            projection for projection in read_set.projections if projection.ref in selected_refs
        )
        if not selected_projections:
            report = PopulationBatchReport(
                batch_ref=f"population-decision:{cadence_input.cadence_id}",
                selected_count=0,
                budget_used=decision.budget_used,
                budget_remaining=decision.budget_remaining,
                read_set_digest=read_set.read_set_digest,
                result_digest=decision.result_digest,
            )
            return PopulationCycleResult(
                status="accepted",
                batch_ref=report.batch_ref,
                report=report,
                decision=decision,
                production_append_count=0,
            )
        for candidate in decision.selected_candidates:
            projection = next(
                (item for item in read_set.projections if item.ref in candidate.source_projection_refs),
                None,
            )
            descriptor = next(
                (item for item in capabilities if candidate.behavior_kind in item.accepted_behavior_kinds),
                None,
            )
            if projection is not None and descriptor is not None:
                requested_owner = projection.payload.get("owner_ref") or projection.payload.get("target_owner")
                if requested_owner is not None and str(requested_owner) != descriptor.target_owner:
                    return self._requeue(
                        f"population-decision:{cadence_input.cadence_id}:requeue",
                        read_set,
                        "capability_owner_override_denied",
                    )
        unknown_selected = tuple(
            candidate
            for candidate in decision.selected_candidates
            if candidate.behavior_kind not in PopulationPlanner.ADMITTED_BEHAVIORS
        )
        settled_owner_receipt_refs = {
            str(candidate_source.payload.get("source_owner_receipt_ref"))
            for candidate_source in selected_projections
            if candidate_source.payload.get("source_owner_receipt_ref")
        }
        if not settled_owner_receipt_refs.issubset(accepted_owner_receipt_refs):
            return self._requeue(
                f"population-decision:{cadence_input.cadence_id}:requeue",
                read_set,
                "unverified_owner_receipt",
            )
        generic_owner_candidates = tuple(
            candidate
            for candidate in decision.selected_candidates
            if "owner_bound_intent" in candidate.allowed_outputs
            and candidate.behavior_kind != "schedule_gated_supply"
            and not any(
                item.payload.get("source_owner_receipt_ref")
                for item in selected_projections
                if item.ref in candidate.source_projection_refs
            )
        )
        if generic_owner_candidates:
            receipts: list[PopulationOwnerReceipt] = []
            for candidate in generic_owner_candidates:
                projection = next(item for item in read_set.projections if item.ref in candidate.source_projection_refs)
                executor = self._owner_executors.get(candidate.capability_id)
                if executor is None:
                    return self._requeue(
                        f"population-decision:{cadence_input.cadence_id}:requeue",
                        read_set,
                        "capability_owner_adapter_missing",
                    )
                payload = dict(projection.payload.get("owner_payload") or projection.payload)
                intent = BatchIntentCandidate(
                    intent_ref=candidate.candidate_ref,
                    profile_ref=candidate.actor_ref,
                    intent_kind=str(payload.get("intent_kind") or candidate.behavior_kind),
                    payload=payload,
                    expected_revisions=dict(candidate.source_revision_vector),
                    policy_revision=policy.policy_revision,
                    package_revision=candidate.capability_id,
                    idempotency_key=candidate.idempotency_key,
                    correlation_id=cadence_input.cadence_id,
                    source_ref=candidate.source_projection_refs[0],
                    privacy_scope=projection.scope,
                )
                receipts.append(executor.submit(intent, read_set=read_set))
            if any(
                not receipt.committed
                or (receipt.zero_write and receipt.idempotency_status != "duplicate_replayed")
                for receipt in receipts
            ):
                return PopulationCycleResult(
                    status="requeue",
                    batch_ref=f"population-decision:{cadence_input.cadence_id}",
                    report=PopulationBatchReport(
                        batch_ref=f"population-decision:{cadence_input.cadence_id}",
                        owner_intent_count=len(generic_owner_candidates),
                        budget_used=decision.budget_used,
                        budget_remaining=decision.budget_remaining,
                        read_set_digest=read_set.read_set_digest,
                        result_digest=decision.result_digest,
                    ),
                    decision=decision,
                    owner_receipts=tuple(receipts),
                    reason="owner_rejected",
                    production_append_count=0,
                )
            if self._continuity_port is not None and any(
                candidate.behavior_kind in {
                    "organization_production_work_contribution",
                    "inventory_output_custody",
                }
                for candidate in generic_owner_candidates
            ):
                receipt_by_projection = {
                    candidate.source_projection_refs[0]: receipt.receipt_ref
                    for candidate, receipt in zip(generic_owner_candidates, receipts)
                    if receipt.committed
                }
                settled_projections = tuple(
                    projection.model_copy(
                        update={
                            "payload": {
                                **projection.payload,
                                "source_owner_receipt_ref": receipt_by_projection[projection.ref],
                                "source_owner_receipt_refs": (receipt_by_projection[projection.ref],),
                            }
                        },
                        deep=True,
                    )
                    if projection.ref in receipt_by_projection
                    else projection
                    for projection in selected_projections
                )
                selected_read_set = PopulationReadSet.from_inputs(cadence_input, settled_projections)
                core_refs = {
                    candidate.actor_ref
                    for candidate in decision.selected_candidates
                    if "character_core_command" in candidate.allowed_outputs
                }
                settled = tuple(receipt.receipt_ref for receipt in receipts)
                settled_result = self._run_cycle_impl(
                    cadence_input,
                    selected_read_set,
                    allowed_character_core_refs=core_refs,
                    accepted_owner_receipt_refs=settled,
                )
                return settled_result.model_copy(
                    update={
                        "decision": decision,
                        "owner_receipts": tuple(receipts),
                        "production_append_count": sum(
                            1 for receipt in receipts if receipt.committed and not receipt.zero_write
                        ),
                    }
                )
            return PopulationCycleResult(
                status="accepted",
                batch_ref=f"population-decision:{cadence_input.cadence_id}",
                report=PopulationBatchReport(
                    batch_ref=f"population-decision:{cadence_input.cadence_id}",
                    selected_cohort_refs=tuple(candidate.actor_ref for candidate in decision.selected_candidates),
                    owner_intent_count=len(generic_owner_candidates),
                    owner_committed_count=sum(
                        1
                        for receipt in receipts
                        if receipt.committed
                        and (
                            not receipt.zero_write
                            or receipt.idempotency_status == "duplicate_replayed"
                        )
                    ),
                    budget_used=decision.budget_used,
                    budget_remaining=decision.budget_remaining,
                    read_set_digest=read_set.read_set_digest,
                    result_digest=decision.result_digest,
                ),
                decision=decision,
                owner_receipts=tuple(receipts),
                production_append_count=sum(
                    1 for receipt in receipts if receipt.committed and not receipt.zero_write
                ),
            )
        if unknown_selected:
            if any(
                output in {"owner_bound_intent", "character_core_command"}
                for candidate in unknown_selected
                for output in candidate.allowed_outputs
            ):
                return self._requeue(
                    f"population-decision:{cadence_input.cadence_id}:requeue",
                    read_set,
                    "capability_output_unsupported",
                )
            if len(unknown_selected) != len(decision.selected_candidates):
                return self._requeue(
                    f"population-decision:{cadence_input.cadence_id}:requeue",
                    read_set,
                    "mixed_generic_output_unsupported",
                )
            presentation = {
                candidate.actor_ref: {
                    "actor_ref": candidate.actor_ref,
                    "behavior_kind": candidate.behavior_kind,
                    "fidelity_tier": candidate.fidelity_tier,
                    "source_projection_refs": list(candidate.source_projection_refs),
                }
                for candidate in unknown_selected
                if "presentation_seed" in candidate.allowed_outputs
            }
            activations = tuple(
                candidate.source_projection_refs[0]
                for candidate in unknown_selected
                if "activation_candidate" in candidate.allowed_outputs and candidate.source_projection_refs
            )
            report = PopulationBatchReport(
                batch_ref=f"population-decision:{cadence_input.cadence_id}",
                selected_cohort_refs=tuple(candidate.actor_ref for candidate in unknown_selected),
                presentation_seeds=presentation,
                activation_candidates=activations,
                selected_count=len(unknown_selected),
                presentation_seed_count=len(presentation),
                activation_candidate_count=len(activations),
                budget_used=decision.budget_used,
                budget_remaining=decision.budget_remaining,
                read_set_digest=read_set.read_set_digest,
                result_digest=decision.result_digest,
            )
            return PopulationCycleResult(
                status="accepted",
                batch_ref=report.batch_ref,
                report=report,
                decision=decision,
                production_append_count=0,
            )
        selected_read_set = PopulationReadSet.from_inputs(cadence_input, selected_projections)
        allowed_core_refs = {
            candidate.actor_ref
            for candidate in decision.selected_candidates
            if "character_core_command" in candidate.allowed_outputs
        }
        result = self._run_cycle_impl(
            cadence_input,
            selected_read_set,
            allowed_character_core_refs=allowed_core_refs,
            accepted_owner_receipt_refs=tuple(sorted(settled_owner_receipt_refs)),
        )
        return result.model_copy(update={"decision": decision})

    def replan_from_receipts(
        self,
        previous_decision: PopulationDecision | None,
        receipts: Sequence[PopulationOwnerReceipt],
        next_read_set: PopulationReadSet,
        policy: PopulationDecisionPolicy,
        capabilities: tuple[PopulationCapabilityDescriptor, ...],
    ) -> PopulationCycleResult:
        """Re-evaluate only after prior Owner receipts have reached a terminal success."""
        if any(
            not receipt.committed
            or (receipt.zero_write and receipt.idempotency_status != "duplicate_replayed")
            for receipt in receipts
        ):
            return self._requeue(
                f"population-decision:{next_read_set.cadence.cadence_id}:requeue",
                next_read_set,
                "owner_rejected",
            )
        production_receipts = tuple(
            receipt
            for receipt in receipts
            if receipt.event_family == "gameplay.organization.production_work_contribution_accepted"
        )
        if production_receipts:
            receipts_by_ref = {receipt.receipt_ref: receipt for receipt in production_receipts}
            receipt_vector: dict[str, int] = {}
            for receipt in production_receipts:
                for stream, revision in receipt.revision_vector.items():
                    if stream in receipt_vector and receipt_vector[stream] != revision:
                        return self._requeue(
                            f"population-decision:{next_read_set.cadence.cadence_id}:requeue",
                            next_read_set,
                            "stale_read_set",
                        )
                    receipt_vector[stream] = revision
            if (
                any(receipt.owner_ref != "actor_gameplay.organization_domain" for receipt in production_receipts)
                or next_read_set.cadence.base_revision_vector != receipt_vector
                or receipt_vector.get(next_read_set.cadence.cadence_source_ref)
                != next_read_set.cadence.cadence_source_revision
                or any(
                    projection.revision_vector != receipt_vector
                    or projection.payload.get("source_owner_receipt_ref") not in receipts_by_ref
                    or projection.revision_vector != receipts_by_ref[projection.payload["source_owner_receipt_ref"]].revision_vector
                    or projection.payload.get("source_domain") != "production"
                    or projection.payload.get("candidate_kind") != "organization_production_work_contribution"
                    for projection in next_read_set.projections
                )
            ):
                return self._requeue(
                    f"population-decision:{next_read_set.cadence.cadence_id}:requeue",
                    next_read_set,
                    "stale_read_set",
                )
        if previous_decision is None:
            return self._requeue(
                f"population-decision:{next_read_set.cadence.cadence_id}:requeue",
                next_read_set,
                "previous_decision_missing",
            )
        return self._run_decision_cycle(
            next_read_set.cadence,
            next_read_set,
            policy,
            capabilities,
            accepted_owner_receipt_refs=tuple(receipt.receipt_ref for receipt in production_receipts),
        )

    def run_cycle(self, cadence_input: PopulationCadenceInput, read_set: PopulationReadSet) -> PopulationCycleResult:
        """Run the legacy population path, delegating closed cohorts to V1."""
        if self._looks_like_v1_cohort(read_set):
            return self.run_cohort_cycle(cadence_input, read_set)
        return self._run_cycle_impl(cadence_input, read_set)

    def run_cohort_cycle(self, cadence_input: PopulationCadenceInput, read_set: PopulationReadSet) -> PopulationCycleResult:
        """Run one Siming-governed three-actor cohort window."""
        if not self._looks_like_v1_cohort(read_set):
            return self._run_cycle_impl(cadence_input, read_set)
        reason = self._v1_admission_reason(read_set)
        if reason:
            return self._requeue(
                f"population-batch:{cadence_input.cadence_id}:requeue",
                read_set,
                reason,
            )
        return self._run_cycle_impl(cadence_input, read_set, cohort=True)

    def _run_cycle_impl(
        self,
        cadence_input: PopulationCadenceInput,
        read_set: PopulationReadSet,
        *,
        cohort: bool = False,
        allowed_character_core_refs: set[str] | None = None,
        accepted_owner_receipt_refs: Sequence[str] = (),
    ) -> PopulationCycleResult:
        batch_ref = f"population-batch:{cadence_input.cadence_id}:requeue"
        if not self._scope_admitted(cadence_input.report_scope):
            return self._requeue(batch_ref, read_set, "projection_scope_denied")
        if read_set.cadence != cadence_input:
            return self._requeue(batch_ref, read_set, "stale_read_set")
        try:
            canonical = PopulationReadSet.from_inputs(cadence_input, read_set.projections)
        except Exception:
            return self._requeue(batch_ref, read_set, "stale_read_set")
        if (
            canonical.read_set_digest != read_set.read_set_digest
            or any(
                projection.revision_vector != cadence_input.base_revision_vector
                for projection in read_set.projections
            )
        ):
            return self._requeue(batch_ref, read_set, "stale_read_set")
        if any(not self._projection_scope_admitted(projection, cadence_input) for projection in read_set.projections):
            return self._requeue(batch_ref, read_set, "projection_scope_denied")
        if self._continuity_port is not None and not callable(
            getattr(self._continuity_port, "current_revision", None)
        ):
            return self._requeue(batch_ref, read_set, "continuity_revision_reader_missing")

        report = (
            self._planner.plan_three_actor_cohort(read_set)
            if cohort
            else self._planner.plan_population_cycle(read_set)
        )
        if any(getattr(item, "reason", "") == "stale_read_set" for item in report.rejected_candidates):
            return PopulationCycleResult(status="requeue", batch_ref=report.batch_ref, report=report, reason="stale_read_set", production_append_count=0)
        actor_revisions: dict[str, int] = {}
        if self._continuity_port is not None:
            try:
                actor_revisions = {
                    actor_ref: self._current_revision(actor_ref)
                    for actor_ref in self._planned_actor_refs(read_set)
                }
            except Exception:
                return self._requeue(
                    report.batch_ref,
                    read_set,
                    "continuity_revision_reader_invalid",
                )
        owner_receipts: list[PopulationOwnerReceipt] = []
        owner_refs: list[str] = list(accepted_owner_receipt_refs)
        owner_receipt_associations: dict[str, str] = {}
        for bound in report.owner_bound_intents:
            if isinstance(bound, dict):
                bound = PopulationOwnerBoundIntent(
                    candidate_ref=str(bound.get("candidate_ref", "")), actor_ref=str(bound.get("actor_ref", "")),
                    intent_kind=str(bound.get("intent_kind", "")), scope=str(bound.get("scope", "")),
                    payload=dict(bound.get("payload") or {}), source_revision_vector=dict(bound.get("source_revision_vector") or {}),
                )
            if not isinstance(bound, PopulationOwnerBoundIntent) or (
                bound.intent_kind != "schedule_gated_supply"
                and not (
                    bound.intent_kind == "inventory_output_custody"
                    and str(bound.payload.get("source_owner_receipt_ref") or "") in accepted_owner_receipt_refs
                )
                and not (cohort and bound.intent_kind == "supply" and bound.actor_ref == "character:char_a")
            ):
                continue
            settled_receipt_ref = str(bound.payload.get("source_owner_receipt_ref") or "")
            if settled_receipt_ref in accepted_owner_receipt_refs:
                owner_receipt_associations[bound.candidate_ref] = settled_receipt_ref
                continue
            if self._owner_executor is None:
                continue
            intent = BatchIntentCandidate(
                intent_ref=f"{bound.candidate_ref}:supply", profile_ref=bound.actor_ref, intent_kind="supply",
                payload=dict(bound.payload), expected_revisions=dict(bound.source_revision_vector), policy_revision=read_set.cadence.policy_revision,
                package_revision="package:population:v1", idempotency_key=f"{bound.candidate_ref}:supply", correlation_id=read_set.cadence.cadence_id,
                source_ref="population:siming", privacy_scope=bound.scope,
            )
            receipt = self._owner_executor.submit(intent, read_set=read_set)
            owner_receipts.append(receipt)
            if receipt.committed and (
                not receipt.zero_write
                or receipt.idempotency_status == "duplicate_replayed"
            ):
                owner_refs.append(receipt.receipt_ref)
                owner_receipt_associations[bound.candidate_ref] = receipt.receipt_ref

        seeds = self._seed_planner.derive(
            read_set,
            owner_refs,
            owner_receipt_associations=owner_receipt_associations,
        )
        if cohort:
            selected_refs = set(report.selected_cohort_refs)
            seeds = tuple(
                seed.model_copy(update={"memory_candidates": ()}) if seed.actor_ref == "character:char_b" else seed
                for seed in seeds
                if any(seed.seed_id.endswith(f":{projection_ref}") for projection_ref in selected_refs)
                and seed.actor_ref in {"character:char_a", "character:char_b"}
            )
        continuity_receipts: list[CharacterContinuityReceipt] = []
        next_actor_revisions = dict(actor_revisions)
        continuity_failure_status = ""
        continuity_failure_reason = ""
        if self._continuity_port is not None and not (
            cohort and report.owner_bound_intents and len(owner_refs) < len(report.owner_bound_intents)
        ):
            for seed in seeds:
                if not seed.actor_ref.startswith("character:"):
                    continue
                if allowed_character_core_refs is not None and seed.actor_ref not in allowed_character_core_refs:
                    continue
                if seed.owner_effect_status in {"owner_settlement_required", "rejected"}:
                    continue
                command = CharacterContinuityCommand(
                    command_id=f"continuity:{seed.seed_id}", actor_ref=seed.actor_ref,
                    source_owner_receipt_refs=seed.source_owner_receipt_refs,
                    expected_character_revision=next_actor_revisions[seed.actor_ref], source_revision_vector=dict(seed.source_revision_vector),
                    state_delta={
                        **dict(seed.state_deltas),
                        "presentation_seed": dict(seed.presentation_seed),
                        "activation_hints": list(seed.activation_hints),
                    },
                    memory_candidate_refs=tuple(item.candidate_id for item in seed.memory_candidates),
                    exposure_evidence={
                        "source_event_refs": list(seed.source_event_refs),
                        "memory_candidates": [item.model_dump(mode="json") for item in seed.memory_candidates],
                        "visibility_scope": seed.visibility_scope,
                        "privacy_disposition": "actor_private",
                        **(
                            {"exposure_basis": seed.memory_candidates[0].exposure_basis}
                            if seed.memory_candidates
                            else {}
                        ),
                    },
                    policy_revision="policy:character-continuity:v1",
                    idempotency_key=seed.idempotency_key, world_effect_required=seed.owner_effect_status == "settled",
                )
                receipt = self._continuity_port.apply_command(command)
                continuity_receipts.append(receipt)
                if receipt.status in {"committed", "idempotent_replay"}:
                    next_actor_revisions[seed.actor_ref] = max(
                        next_actor_revisions[seed.actor_ref],
                        receipt.character_revision_after,
                    )
                    continue
                continuity_failure_status = (
                    "rejected" if receipt.status == "rejected" else "requeue"
                )
                continuity_failure_reason = f"character_continuity_{receipt.status}"
                break

        status = "accepted"
        if report.owner_bound_intents and (self._owner_executor is None or len(owner_refs) < len(report.owner_bound_intents)):
            status = "owner_settlement_required"
        if continuity_failure_status:
            status = continuity_failure_status
        if cohort:
            report = report.model_copy(update={
                "owner_committed_count": sum(1 for item in owner_receipts if item.committed and not item.zero_write),
                "continuity_committed_count": sum(1 for item in continuity_receipts if item.status in {"committed", "idempotent_replay"}),
                "continuity_requeue_count": sum(1 for item in continuity_receipts if item.status in {"requeued", "rejected"}),
            })
            audits = ({
                "cohort_ref": report.cohort_ref,
                "window": cadence_input.cadence_id.rsplit(":", 1)[-1],
                "classification": {
                    "selected": report.selected_count,
                    "unprocessed": report.unprocessed_count,
                    "rejected": len(report.rejected_candidates),
                    "presentation_seed_count": report.presentation_seed_count,
                    "activation_candidate_count": report.activation_candidate_count,
                },
                "owner": {"submitted": len(owner_receipts), "committed": report.owner_committed_count},
                "continuity": {"submitted": len(continuity_receipts), "committed": report.continuity_committed_count, "requeue": report.continuity_requeue_count},
                "read_set_digest": report.read_set_digest,
                "result_digest": report.result_digest,
            },)
        else:
            audits = ()
        return PopulationCycleResult(status=status, batch_ref=report.batch_ref, report=report, seed_candidates=seeds, owner_receipts=tuple(owner_receipts), continuity_receipts=tuple(continuity_receipts), audits=audits, reason=continuity_failure_reason, production_append_count=sum(1 for item in owner_receipts if item.committed and not item.zero_write))

    @staticmethod
    def _is_v1_cohort(read_set: PopulationReadSet) -> bool:
        return PopulationSimulationCapability._v1_admission_reason(read_set) == ""

    @staticmethod
    def _looks_like_v1_cohort(read_set: PopulationReadSet) -> bool:
        cadence = read_set.cadence
        return cadence.cadence_id.startswith("cadence:cohort:") or (
            cadence.selector_revision == PopulationSimulationCapability._V1_SELECTOR
            or cadence.ruleset_revision == PopulationSimulationCapability._V1_RULESET
        )

    @staticmethod
    def _v1_admission_reason(read_set: PopulationReadSet) -> str:
        cadence = read_set.cadence
        parts = cadence.cadence_id.split(":")
        if (
            len(parts) != 4
            or parts[:3] != ["cadence", "cohort", "bakery"]
            or parts[3] not in {"W0", "W1"}
            or cadence.selector_revision != PopulationSimulationCapability._V1_SELECTOR
            or cadence.ruleset_revision != PopulationSimulationCapability._V1_RULESET
            or cadence.policy_revision != cadence.world_mode_revision
        ):
            return "stale_read_set"
        if cadence.report_scope != "organization:summary" or len(read_set.projections) != 3:
            return "cohort_input_invalid"
        window = parts[3]
        expected_kinds = {
            "character:char_a": "schedule_gated_supply",
            "character:char_b": "routine_work",
            "character:char_c": "relationship_negotiation",
        }
        actors: dict[str, str] = {}
        for projection in read_set.projections:
            payload = projection.payload
            aliases = {
                str(payload.get(key)).strip()
                for key in ("actor_ref", "profile_ref", "character_ref")
                if payload.get(key) not in (None, "")
            }
            if len(aliases) != 1:
                return "cohort_input_invalid"
            actor = next(iter(aliases))
            kind = str(payload.get("candidate_kind") or payload.get("kind") or payload.get("behavior_kind") or "")
            expected_ref = f"projection:{actor.removeprefix('character:')}:{window}"
            if (
                actor not in expected_kinds
                or actor in actors
                or projection.ref != expected_ref
                or kind != expected_kinds[actor]
                or projection.scope not in {"organization:summary", "public"}
            ):
                return "cohort_input_invalid"
            actors[actor] = kind
        return "" if tuple(sorted(actors)) == tuple(sorted(expected_kinds)) else "cohort_input_invalid"

    def _current_revision(self, actor_ref: str) -> int:
        reader = getattr(self._continuity_port, "current_revision", None)
        if not callable(reader):
            raise ValueError("continuity_revision_reader_missing")
        revision = reader(actor_ref)
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
            raise ValueError("continuity_revision_reader_invalid")
        return revision

    @staticmethod
    def _planned_actor_refs(read_set: PopulationReadSet) -> tuple[str, ...]:
        actors = {
            str(
                projection.payload.get("actor_ref")
                or projection.payload.get("profile_ref")
                or projection.payload.get("character_ref")
                or ""
            )
            for projection in read_set.projections
            if str(
                projection.payload.get("candidate_kind")
                or projection.payload.get("kind")
                or projection.payload.get("behavior_kind")
                or ""
            )
            in CharacterSeedPlanner.ADMITTED_BEHAVIORS
        }
        return tuple(sorted(actor for actor in actors if actor.startswith("character:")))

    @staticmethod
    def _projection_scope_admitted(projection, cadence: PopulationCadenceInput) -> bool:
        if not PopulationSimulationCapability._scope_admitted(cadence.report_scope):
            return False
        if projection.scope not in {cadence.report_scope, "public", "actor:self"}:
            return False
        if not PopulationSimulationCapability._scope_admitted(projection.scope):
            return False
        if PopulationSimulationCapability._forbidden_scope_marker(projection.ref):
            return False
        payload = projection.payload
        actor_ref = payload.get("actor_ref") or payload.get("profile_ref") or payload.get("character_ref")
        actor_text = str(actor_ref or "").strip().lower()
        if actor_ref is not None and not actor_text.startswith("character:"):
            return False
        return PopulationSimulationCapability._payload_scope_admitted(
            payload,
            actor_ref=actor_text,
        )

    @staticmethod
    def _payload_scope_admitted(
        value: object,
        *,
        actor_ref: str,
    ) -> bool:
        if isinstance(value, Mapping):
            for key, nested in value.items():
                normalized_key = str(key).strip().lower()
                if normalized_key == "private" and (
                    nested is True
                    or str(nested).strip().lower()
                    in {"true", "private", "actor_private"}
                ):
                    return False
                if "branch" in normalized_key and nested not in (None, "", False):
                    return False
                if normalized_key == "actor_scope" and nested != "actor:self":
                    return False
                if not PopulationSimulationCapability._payload_scope_admitted(
                    nested,
                    actor_ref=actor_ref,
                ):
                    return False
            return True
        if isinstance(value, (list, tuple, set, frozenset)):
            return all(
                PopulationSimulationCapability._payload_scope_admitted(
                    item,
                    actor_ref=actor_ref,
                )
                for item in value
            )
        if not isinstance(value, str):
            return True
        normalized = value.strip().lower()
        if PopulationSimulationCapability._forbidden_scope_marker(normalized):
            return False
        if actor_ref and any(
            referenced_actor != actor_ref
            for referenced_actor in _CHARACTER_REF_PATTERN.findall(normalized)
        ):
            return False
        return True

    @staticmethod
    def _forbidden_scope_marker(value: object) -> bool:
        if not isinstance(value, str):
            return False
        normalized = value.strip().lower()
        return (
            normalized == "private"
            or "actor_private" in normalized
            or "private:" in normalized
            or "branch:" in normalized
        )

    @staticmethod
    def _scope_admitted(scope: object) -> bool:
        if not isinstance(scope, str):
            return False
        normalized = scope.strip().lower()
        return normalized in PopulationSimulationCapability._ADMITTED_SCOPES

    @staticmethod
    def _requeue(batch_ref: str, read_set: PopulationReadSet, reason: str) -> PopulationCycleResult:
        report = PopulationBatchReport(batch_ref=batch_ref, read_set_digest=read_set.read_set_digest, result_digest="sha256:requeue", budget_used=0, budget_remaining=read_set.cadence.budget, unprocessed_cohort_refs=tuple(item.ref for item in read_set.projections))
        return PopulationCycleResult(status="requeue", batch_ref=batch_ref, report=report, reason=reason, production_append_count=0)


__all__ = ["PopulationSimulationCapability", "PopulationOwnerExecutor", "CharacterContinuityPort", "ReadSetBuilder", "default_population_read_set_builder"]
