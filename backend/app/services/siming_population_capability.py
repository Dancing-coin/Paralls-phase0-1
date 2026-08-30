from __future__ import annotations

from typing import Callable, Protocol, Sequence

from app.character_agent.models.simulation_seed import CharacterContinuityCommand, CharacterContinuityReceipt
from app.models.authority_event import AuthorityEvent
from app.population_continuity.batch import PopulationOwnerBoundIntent, PopulationPlanner
from app.population_continuity.models import PopulationWorldPlan
from app.population_continuity.social_input import FrozenSocialPlanningInput
from app.population_continuity.source_inputs import HouseholdScheduleInput, OrganizationScheduleInput
from app.population_continuity.models import BatchIntentCandidate
from app.population_continuity.seed_planner import CharacterSeedPlanner
from app.population_continuity.siming_contracts import PopulationBatchReport, PopulationCadenceInput, PopulationCycleResult, PopulationOwnerReceipt, PopulationReadSet


class PopulationOwnerExecutor(Protocol):
    def submit(self, intent: BatchIntentCandidate, *, read_set: PopulationReadSet) -> PopulationOwnerReceipt: ...


class CharacterContinuityPort(Protocol):
    def apply_command(self, command: CharacterContinuityCommand) -> CharacterContinuityReceipt: ...


ReadSetBuilder = Callable[[AuthorityEvent, PopulationCadenceInput], PopulationReadSet]


def default_population_read_set_builder(event: AuthorityEvent, cadence: PopulationCadenceInput) -> PopulationReadSet:
    """Build the scoped projection envelope and the fixed bakery owner context."""
    projections = tuple()
    raw = event.payload.get("population_projections")
    if raw is None:
        raw = [event.payload[key] for key in ("world_mode_projection", "organization_projection", "household_projection", "social_projection", "public_projection") if isinstance(event.payload.get(key), dict)]
    if isinstance(raw, (list, tuple)):
        from app.population_continuity.siming_contracts import PopulationProjection

        projections = tuple(PopulationProjection.model_validate(item) for item in raw if isinstance(item, dict))
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
    def __init__(self, *, planner: PopulationPlanner | None = None, seed_planner: CharacterSeedPlanner | None = None, owner_executor: PopulationOwnerExecutor | None = None, continuity_port: CharacterContinuityPort | None = None) -> None:
        self._planner = planner or PopulationPlanner()
        self._seed_planner = seed_planner or CharacterSeedPlanner()
        self._owner_executor = owner_executor
        self._continuity_port = continuity_port

    def run_cycle(self, cadence_input: PopulationCadenceInput, read_set: PopulationReadSet) -> PopulationCycleResult:
        batch_ref = f"population-batch:{cadence_input.cadence_id}:requeue"
        if read_set.cadence != cadence_input:
            return self._requeue(batch_ref, read_set, "stale_read_set")
        try:
            canonical = PopulationReadSet.from_inputs(cadence_input, read_set.projections)
        except Exception:
            return self._requeue(batch_ref, read_set, "stale_read_set")
        if (
            canonical.read_set_digest != read_set.read_set_digest
            or any(
                projection.scope not in {cadence_input.report_scope, "public", "actor:self"}
                or projection.revision_vector != cadence_input.base_revision_vector
                for projection in read_set.projections
            )
        ):
            return self._requeue(batch_ref, read_set, "stale_read_set")

        report = self._planner.plan_population_cycle(read_set)
        if any(getattr(item, "reason", "") == "stale_read_set" for item in report.rejected_candidates):
            return PopulationCycleResult(status="requeue", batch_ref=report.batch_ref, report=report, reason="stale_read_set", production_append_count=0)
        owner_receipts: list[PopulationOwnerReceipt] = []
        owner_refs: list[str] = []
        owner_receipt_associations: dict[str, str] = {}
        for bound in report.owner_bound_intents:
            if isinstance(bound, dict):
                bound = PopulationOwnerBoundIntent(
                    candidate_ref=str(bound.get("candidate_ref", "")), actor_ref=str(bound.get("actor_ref", "")),
                    intent_kind=str(bound.get("intent_kind", "")), scope=str(bound.get("scope", "")),
                    payload=dict(bound.get("payload") or {}), source_revision_vector=dict(bound.get("source_revision_vector") or {}),
                )
            if not isinstance(bound, PopulationOwnerBoundIntent) or bound.intent_kind != "schedule_gated_supply":
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
            if receipt.committed and not receipt.zero_write:
                owner_refs.append(receipt.receipt_ref)
                owner_receipt_associations[bound.candidate_ref] = receipt.receipt_ref

        seeds = self._seed_planner.derive(
            read_set,
            owner_refs,
            owner_receipt_associations=owner_receipt_associations,
        )
        continuity_receipts: list[CharacterContinuityReceipt] = []
        if self._continuity_port is not None:
            for seed in seeds:
                if not seed.actor_ref.startswith("character:"):
                    continue
                command = CharacterContinuityCommand(
                    command_id=f"continuity:{seed.seed_id}", actor_ref=seed.actor_ref,
                    source_owner_receipt_refs=seed.source_owner_receipt_refs,
                    expected_character_revision=0, source_revision_vector=dict(seed.source_revision_vector),
                    state_delta=dict(seed.state_deltas), memory_candidate_refs=tuple(item.candidate_id for item in seed.memory_candidates),
                    exposure_evidence={"source_event_refs": list(seed.source_event_refs)}, policy_revision=read_set.cadence.policy_revision,
                    idempotency_key=seed.idempotency_key, world_effect_required=seed.owner_effect_status == "settled",
                )
                continuity_receipts.append(self._continuity_port.apply_command(command))

        status = "accepted"
        if report.owner_bound_intents and (self._owner_executor is None or len(owner_refs) < len(report.owner_bound_intents)):
            status = "owner_settlement_required"
        return PopulationCycleResult(status=status, batch_ref=report.batch_ref, report=report, seed_candidates=seeds, owner_receipts=tuple(owner_receipts), continuity_receipts=tuple(continuity_receipts), production_append_count=sum(1 for item in owner_receipts if item.committed and not item.zero_write))

    @staticmethod
    def _requeue(batch_ref: str, read_set: PopulationReadSet, reason: str) -> PopulationCycleResult:
        report = PopulationBatchReport(batch_ref=batch_ref, read_set_digest=read_set.read_set_digest, result_digest="sha256:requeue", budget_used=0, budget_remaining=read_set.cadence.budget, unprocessed_cohort_refs=tuple(item.ref for item in read_set.projections))
        return PopulationCycleResult(status="requeue", batch_ref=batch_ref, report=report, reason=reason, production_append_count=0)


__all__ = ["PopulationSimulationCapability", "PopulationOwnerExecutor", "CharacterContinuityPort", "ReadSetBuilder", "default_population_read_set_builder"]
