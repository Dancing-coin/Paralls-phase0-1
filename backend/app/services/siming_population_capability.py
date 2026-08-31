from __future__ import annotations

from collections.abc import Mapping
import re
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

    def __init__(self, *, planner: PopulationPlanner | None = None, seed_planner: CharacterSeedPlanner | None = None, owner_executor: PopulationOwnerExecutor | None = None, continuity_port: CharacterContinuityPort | None = None) -> None:
        self._planner = planner or PopulationPlanner()
        self._seed_planner = seed_planner or CharacterSeedPlanner()
        self._owner_executor = owner_executor
        self._continuity_port = continuity_port

    def run_cycle(self, cadence_input: PopulationCadenceInput, read_set: PopulationReadSet) -> PopulationCycleResult:
        """Run the legacy population path, delegating closed cohorts to V1."""
        if self._is_v1_cohort(read_set):
            return self.run_cohort_cycle(cadence_input, read_set)
        return self._run_cycle_impl(cadence_input, read_set)

    def run_cohort_cycle(self, cadence_input: PopulationCadenceInput, read_set: PopulationReadSet) -> PopulationCycleResult:
        """Run one Siming-governed three-actor cohort window."""
        if not self._is_v1_cohort(read_set):
            return self._run_cycle_impl(cadence_input, read_set)
        return self._run_cycle_impl(cadence_input, read_set, cohort=True)

    def _run_cycle_impl(self, cadence_input: PopulationCadenceInput, read_set: PopulationReadSet, *, cohort: bool = False) -> PopulationCycleResult:
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
        owner_refs: list[str] = []
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
                and not (cohort and bound.intent_kind == "supply" and bound.actor_ref == "character:char_a")
            ):
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
        actors: dict[str, str] = {}
        for projection in read_set.projections:
            payload = projection.payload
            actor = str(payload.get("actor_ref") or payload.get("profile_ref") or payload.get("character_ref") or "")
            kind = str(payload.get("candidate_kind") or payload.get("kind") or payload.get("behavior_kind") or "")
            if actor in {"character:char_a", "character:char_b", "character:char_c"}:
                actors[actor] = kind
        expected = {
            "character:char_a": {"schedule_gated_supply"},
            "character:char_b": {"routine_work"},
            "character:char_c": {"relationship_negotiation"},
        }
        return set(actors) == set(expected) and all(actors[actor] in kinds for actor, kinds in expected.items())

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
