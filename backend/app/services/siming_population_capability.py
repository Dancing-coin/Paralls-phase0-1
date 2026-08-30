from __future__ import annotations

from typing import Callable, Protocol, Sequence

from app.character_agent.models.simulation_seed import CharacterContinuityCommand, CharacterContinuityReceipt
from app.models.authority_event import AuthorityEvent
from app.population_continuity.batch import PopulationOwnerBoundIntent, PopulationPlanner
from app.population_continuity.models import BatchIntentCandidate
from app.population_continuity.seed_planner import CharacterSeedPlanner
from app.population_continuity.siming_contracts import PopulationBatchReport, PopulationCadenceInput, PopulationCycleResult, PopulationOwnerReceipt, PopulationReadSet


class PopulationOwnerExecutor(Protocol):
    def submit(self, intent: BatchIntentCandidate, *, read_set: PopulationReadSet) -> PopulationOwnerReceipt: ...


class CharacterContinuityPort(Protocol):
    def apply_command(self, command: CharacterContinuityCommand) -> CharacterContinuityReceipt: ...


ReadSetBuilder = Callable[[AuthorityEvent, PopulationCadenceInput], PopulationReadSet]


def default_population_read_set_builder(event: AuthorityEvent, cadence: PopulationCadenceInput) -> PopulationReadSet:
    """Build only the scoped projection envelope carried by the authority event."""
    projections = tuple()
    raw = event.payload.get("population_projections")
    if raw is None:
        raw = [event.payload[key] for key in ("world_mode_projection", "organization_projection", "household_projection", "social_projection", "public_projection") if isinstance(event.payload.get(key), dict)]
    if isinstance(raw, (list, tuple)):
        from app.population_continuity.siming_contracts import PopulationProjection
        projections = tuple(PopulationProjection.model_validate(item) for item in raw if isinstance(item, dict))
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
        if canonical.read_set_digest != read_set.read_set_digest:
            return self._requeue(batch_ref, read_set, "stale_read_set")

        report = self._planner.plan_population_cycle(read_set)
        if any(getattr(item, "reason", "") == "stale_read_set" for item in report.rejected_candidates):
            return PopulationCycleResult(status="requeue", batch_ref=report.batch_ref, report=report, reason="stale_read_set", production_append_count=0)
        owner_receipts: list[PopulationOwnerReceipt] = []
        owner_refs: list[str] = []
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

        seeds = self._seed_planner.derive(read_set, owner_refs)
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
