"""Bounded orchestration over admitted owners; this module never appends facts.

The first admitted operations are existing organization windows and economy wage
obligations. No generic payload-to-event writer or global transaction is added.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from fractions import Fraction
from typing import Literal

from app.gameplay.econ1_economy_runtime import EconomyAuthority, OperatingWindow
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, ProjectionCheckpoint
from app.gameplay.organization_government_runtime import OrganizationAuthority
from app.gameplay.settlement_plan import SettlementPlan
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from .adapter_admission import AdapterAdmission, AdapterDescriptor
from .temporal_contracts import SettlementWindow, SimulationTimeline, TemporalProfile, ClockMapping, SimulationTime


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: object) -> str:
    # Match the existing SettlementPlan command digest, including JSON escaping.
    return "sha256:" + hashlib.sha256(_json(value).encode()).hexdigest()


def _dump(value):
    return json.loads(json.dumps(asdict(value), default=str))


@dataclass(frozen=True)
class FrozenSettlementWindow:
    window: SettlementWindow
    timeline: SimulationTimeline
    profile: TemporalProfile
    mapping: ClockMapping

    def validate(self, plan) -> None:
        w, t, p, m = self.window, self.timeline, self.profile, self.mapping
        expected = {}
        reads = dict(w.frozen_read_set)
        if len(reads) != len(w.frozen_read_set):
            raise ValueError("batch_window_read_set_duplicate")
        for op in plan.operations:
            for stream, revision in op.command.expected_revisions.items():
                if stream in expected and expected[stream] != revision:
                    raise ValueError("batch_window_revision_mismatch")
                expected[stream] = revision
        times = (w.from_time, w.to_time, w.input_cutoff, w.confirmation_boundary)
        if (plan.timeline_ref != w.timeline_id or w.timeline_id != t.timeline_id
                or plan.window_ref != w.window_ref or w.settlement_idempotency_key != plan.batch_ref
                or plan.confirmation_boundary != f"{w.window_ref}:end"
                or t.profile_ref != p.profile_id or t.profile_revision != p.revision
                or m.target_timeline_ref != t.timeline_id or m.target_profile_revision != p.revision
                or m.ratio != 1 / p.step_duration or m.source_unit_ref != p.canonical_unit_ref
                or t.advancement_owner_ref != m.source_clock_ref
                or not m.revision or not p.revision or t.status != "active"
                or w.from_time.canonical_time_value >= w.to_time.canonical_time_value
                or w.input_cutoff != w.to_time or w.confirmation_boundary != w.to_time
                or w.to_time.step_index != t.current_step
                or any(time.timeline_id != t.timeline_id or time.substep_index != 0
                       or time.canonical_time_value != time.step_index * p.step_duration for time in times)
                or any(not m.valid_source_interval[0] <= time.canonical_time_value <= m.valid_source_interval[1]
                       or (time.canonical_time_value - m.source_origin) * m.ratio + m.target_origin != time.step_index
                       for time in times)
                or w.late_input_policy_ref != "reject_after_cutoff"
                or w.ordering_policy_ref != plan.ordering_policy_ref
                or set(w.participant_scope) != {op.owner_ref for op in plan.operations}
                or not plan.evidence_refs or w.evidence_refs != plan.evidence_refs
                or not plan.definition_and_rule_pins or not plan.frozen_read_set_ref
                or tuple(sorted(expected.items())) != tuple(sorted(w.expected_authority_revisions))):
            raise ValueError("batch_window_contract_mismatch")
        producers = {op.operation_ref: op for op in plan.operations}
        for op in plan.operations:
            dependency_revisions = {stream: revision + 1
                for a, b in plan.dependency_edges if b == op.operation_ref
                for stream, revision in producers[a].command.expected_revisions.items()}
            if any(reads.get(stream) != revision for stream, revision in op.command.expected_revisions.items()):
                raise ValueError("batch_window_owner_revision_not_frozen")
            for stream, revision in op.command.read_set_revisions.items():
                if dependency_revisions.get(stream, reads.get(stream)) != revision:
                    raise ValueError("batch_window_read_revision_not_frozen")
            request = json.loads(op.request_json)
            if op.owner_ref == OrganizationAuthority._PRINCIPAL:
                operating = request["window"]
                if (operating["opens_at_tick"] != w.from_time.canonical_time_value
                        or operating["closes_at_tick"] != w.to_time.canonical_time_value
                        or operating["policy_revision"] not in plan.definition_and_rule_pins):
                    raise ValueError("batch_window_operating_range_mismatch")
            else:
                if (request["due_tick"] != w.to_time.canonical_time_value
                        or not set(request["work_evidence_refs"]).issubset(w.evidence_refs)
                        or request["policy_revision"] not in plan.definition_and_rule_pins):
                    raise ValueError("batch_window_wage_input_mismatch")


@dataclass(frozen=True)
class FrozenOwnerOperation:
    operation_ref: str
    owner_ref: str
    owner_contract_ref: str
    command_json: str
    request_json: str

    @property
    def command(self) -> GameplayCommandEnvelope:
        return GameplayCommandEnvelope.model_validate_json(self.command_json)

    @property
    def input_digest(self) -> str:
        return _digest({"command": json.loads(self.command_json), "request": json.loads(self.request_json)})


@dataclass(frozen=True)
class BatchSettlementPlan:
    batch_ref: str
    timeline_ref: str
    window_ref: str
    plan_revision: str
    frozen_read_set_ref: str
    evidence_refs: tuple[str, ...]
    definition_and_rule_pins: tuple[str, ...]
    operations: tuple[FrozenOwnerOperation, ...]
    dependency_edges: tuple[tuple[str, str], ...]
    ordering_policy_ref: str
    consistency_scope: str
    failure_policy_ref: str
    confirmation_boundary: str
    recovery_cursor: int
    predecessor_batch_ref: str | None = None
    frozen_window: FrozenSettlementWindow | None = None

    @property
    def input_digest(self) -> str:
        value = _dump(self)
        value.pop("recovery_cursor")
        return _digest(value)

    def ordered_operations(self) -> tuple[FrozenOwnerOperation, ...]:
        if (not self.operations or self.ordering_policy_ref != "dependency_then_ref"
                or self.consistency_scope != "owner_atomic"
                or self.failure_policy_ref != "query_then_bounded_retry"
                or not 0 <= self.recovery_cursor <= len(self.operations)):
            raise ValueError("batch_policy_not_admitted")
        remaining = {op.operation_ref: op for op in self.operations}
        if len(remaining) != len(self.operations):
            raise ValueError("batch_operation_duplicate")
        keys = {(op.owner_ref, op.command.idempotency_key) for op in self.operations}
        if len(keys) != len(self.operations):
            raise ValueError("batch_idempotency_key_duplicate")
        if any(a not in remaining or b not in remaining for a, b in self.dependency_edges):
            raise ValueError("batch_dependency_unknown")
        ordered: list[FrozenOwnerOperation] = []
        while remaining:
            ready = sorted(ref for ref in remaining if not any(
                target == ref and source in remaining for source, target in self.dependency_edges))
            if not ready:
                raise ValueError("batch_dependency_cycle")
            for ref in ready:
                ordered.append(remaining.pop(ref))
        return tuple(ordered)


@dataclass(frozen=True)
class OwnerCommitReceipt:
    batch_ref: str
    plan_revision: str
    owner_ref: str
    operation_ref: str
    input_digest: str
    accepted_event_refs: tuple[str, ...]
    rejected_proposal_refs: tuple[str, ...]
    conflict_refs: tuple[str, ...]
    owner_revision_before: tuple[tuple[str, int], ...]
    owner_revision_after: tuple[tuple[str, int], ...]
    status: Literal["committed", "rejected", "deferred"]


@dataclass(frozen=True)
class BatchSettlementResult:
    batch_ref: str
    input_digest: str
    stage: Literal["completed", "pending_recovery"]
    receipts: tuple[OwnerCommitReceipt, ...]
    recovery_cursor: int
    confirmation_boundary: str | None


class _OwnerAdapter:
    owner_ref: str
    contract_ref: str

    def __init__(self, *, owner: object, store: GameplayEventStore) -> None:
        # A receipt query must use the very store used by this owner.
        if getattr(owner, "_store", None) is not store:
            raise ValueError("batch_owner_store_mismatch")
        self.owner = owner
        self.store = store

    def validate(self, operation: FrozenOwnerOperation) -> None:
        if operation.owner_ref != self.owner_ref or operation.owner_contract_ref != self.contract_ref:
            raise ValueError("batch_owner_contract_not_admitted")
        recreated = self.freeze(operation_ref=operation.operation_ref, **json.loads(operation.request_json))
        if recreated != operation:
            raise ValueError("batch_operation_freeze_mismatch")

    def query(self, operation: FrozenOwnerOperation) -> AppendBatchResult | None:
        self.validate(operation)
        command = operation.command
        record = self.store.get_idempotency_record(self.owner_ref, command.idempotency_key)
        result = self.store.get_by_idempotency(self.owner_ref, command.idempotency_key)
        if record is None and result is None:
            return None
        if record is None or result is None:
            raise ValueError("owner_receipt_incomplete")
        expected_batch = SettlementPlan.from_command_envelope(command).to_atomic_event_batch()
        expected = expected_batch.idempotency_record
        if record.payload_digest != expected.payload_digest:
            raise ValueError("idempotency_payload_mismatch")
        self._validate_committed_result(result=result, expected_batch=expected_batch)
        return result

    def _validate_committed_result(self, *, result: AppendBatchResult, expected_batch) -> None:
        if not result.committed:
            return
        expected_events = tuple(expected_batch.events)
        actual_ids = tuple(result.committed_event_ids)
        if not expected_events or actual_ids != tuple(event.event_id for event in expected_events):
            raise ValueError("owner_receipt_event_refs_invalid")
        if result.transaction_id != expected_batch.transaction_id or result.command_id != expected_batch.command_id:
            raise ValueError("owner_receipt_identity_invalid")
        try:
            actual_events = tuple(self.store.get_event(event_id) for event_id in actual_ids)
        except KeyError as exc:
            raise ValueError("owner_receipt_event_refs_invalid") from exc
        for actual, expected in zip(actual_events, expected_events):
            actual_data = actual.model_dump(mode="json")
            expected_data = expected.model_dump(mode="json")
            for field in ("stream_revision", "global_sequence"):
                actual_data.pop(field, None)
                expected_data.pop(field, None)
            if actual_data != expected_data:
                raise ValueError("owner_receipt_event_mismatch")


class OrganizationWindowBatchAdapter(_OwnerAdapter):
    owner_ref = OrganizationAuthority._PRINCIPAL
    contract_ref = "inf:organization-operating-window@1"

    def freeze(self, *, operation_ref: str, window: OperatingWindow | dict, command_id: str,
               idempotency_key: str, causation_id: str, correlation_id: str,
               visibility_scope: str) -> FrozenOwnerOperation:
        window = OperatingWindow.model_validate(window)
        if (not operation_ref or not window.organization_ref.startswith("org:")
                or window.status not in {"planned", "open"} or window.closes_at_tick < window.opens_at_tick
                or visibility_scope not in {"project", "authority_only"}):
            raise ValueError("batch_window_request_not_admitted")
        request = dict(window=window.model_dump(mode="json"), command_id=command_id,
                       idempotency_key=idempotency_key, causation_id=causation_id,
                       correlation_id=correlation_id, visibility_scope=visibility_scope)
        command = GameplayCommandEnvelope(
            command_id=command_id, command_type="gameplay.organization.open_operating_window", command_version=1,
            principal_ref=self.owner_ref, actor_ref=None, project_ref=None,
            transaction_id=f"transaction:{command_id}", idempotency_key=idempotency_key,
            expected_revisions={f"gameplay:organization:window:{window.window_ref}": 0},
            causation_id=causation_id, correlation_id=correlation_id, source_ref=self.owner_ref,
            submitted_at=f"tick:{window.opens_at_tick}", pinned_revisions={"organization_window_policy": 1},
            payload={"stream_ref": f"gameplay:organization:window:{window.window_ref}",
                     "event_type": "gameplay.organization.operating_window_opened", "visibility_policy": visibility_scope,
                     **window.model_dump(mode="json"), "status": "open"})
        return FrozenOwnerOperation(operation_ref, self.owner_ref, self.contract_ref,
                                    command.model_dump_json(), _json(request))

    def commit(self, operation: FrozenOwnerOperation) -> AppendBatchResult:
        self.validate(operation)
        request = json.loads(operation.request_json)
        request["window"] = OperatingWindow.model_validate(request["window"])
        return self.owner.open_operating_window(**request)


class EconomyWageBatchAdapter(_OwnerAdapter):
    owner_ref = EconomyAuthority._PRINCIPAL
    contract_ref = "inf:economy-wage-accrual-obligation@1"

    def freeze(self, *, operation_ref: str, command: GameplayCommandEnvelope | dict,
               accrual_ref: str, organization_ref: str, work_evidence_refs: tuple[str, ...],
               wage_amount_minor: int, due_tick: int, policy_revision: str) -> FrozenOwnerOperation:
        command = GameplayCommandEnvelope.model_validate(command)
        if (not operation_ref or command.principal_ref != self.owner_ref or command.source_ref != self.owner_ref
                or not command.actor_ref or not command.actor_ref.startswith("character:")
                or set(command.expected_revisions) != {f"gameplay:economy:wage:{command.actor_ref}"}
                or command.payload.get("visibility_scope") != "project"
                or set(command.payload) - {"visibility_scope", "semantic_effect_ref", "semantic_snapshot_digest"}
                or not accrual_ref or not organization_ref or not work_evidence_refs
                or any(not ref for ref in work_evidence_refs)
                or type(wage_amount_minor) is not int or wage_amount_minor <= 0
                or type(due_tick) is not int or due_tick < 0 or not policy_revision):
            raise ValueError("batch_wage_request_not_admitted")
        effect = command.payload.get("semantic_effect_ref")
        snapshot = command.payload.get("semantic_snapshot_digest")
        if ((effect is None) != (snapshot is None) or effect is not None and (
                effect != "effect:wage_accrual_due" or not isinstance(snapshot, str) or not snapshot)):
            raise ValueError("batch_wage_request_not_admitted")
        request = dict(command=command.model_dump(mode="json"), accrual_ref=accrual_ref,
                       organization_ref=organization_ref, work_evidence_refs=work_evidence_refs,
                       wage_amount_minor=wage_amount_minor, due_tick=due_tick, policy_revision=policy_revision)
        payload = dict(stream_ref=f"gameplay:economy:wage:{command.actor_ref}",
                       event_type="gameplay.economy.wage_obligation_opened", visibility_policy="project",
                       obligation_id=f"obligation:economy:wage:{command.actor_ref}:{accrual_ref}",
                       accrual_ref=accrual_ref, organization_ref=organization_ref, payee_actor_ref=command.actor_ref,
                       work_evidence_refs=tuple(work_evidence_refs), amount=wage_amount_minor, due_tick=due_tick,
                       policy_ref="policy:economy_wage_accrual", policy_revision=policy_revision)
        for key in ("semantic_effect_ref", "semantic_snapshot_digest"):
            if key in command.payload:
                payload[key] = command.payload[key]
        normalized = command.model_copy(update={"payload": payload}, deep=True)
        return FrozenOwnerOperation(operation_ref, self.owner_ref, self.contract_ref,
                                    normalized.model_dump_json(), _json(request))

    def commit(self, operation: FrozenOwnerOperation) -> AppendBatchResult:
        self.validate(operation)
        request = json.loads(operation.request_json)
        request["command"] = GameplayCommandEnvelope.model_validate(request["command"])
        request["work_evidence_refs"] = tuple(request["work_evidence_refs"])
        return self.owner.open_wage_obligation(**request)


class BatchSettlementCoordinator:
    def __init__(self, *, adapters: tuple[_OwnerAdapter, ...]) -> None:
        self.adapters = {(a.owner_ref, a.contract_ref): a for a in adapters}
        if len(self.adapters) != len(adapters):
            raise ValueError("batch_adapter_duplicate")

    def load(self, batch_ref: str) -> BatchSettlementPlan:
        store = next(iter(self.adapters.values())).store
        saved = store.get_projection_checkpoint(f"batch-input:{batch_ref}")
        if saved is None or saved.projector_id != "world_runtime.batch_input@1":
            raise ValueError("batch_frozen_input_missing")
        value = dict(saved.state["plan"])
        frozen = value.pop("frozen_window")
        from .temporal_migration import _profile, _mapping
        window = dict(frozen["window"])
        for key in ("from_time", "to_time", "input_cutoff", "confirmation_boundary"):
            window[key] = SimulationTime(**dict(window[key], canonical_time_value=Fraction(window[key]["canonical_time_value"])))
        for key in ("participant_scope", "evidence_refs"):
            window[key] = tuple(window[key])
        for key in ("frozen_read_set", "expected_authority_revisions"):
            window[key] = tuple(tuple(row) for row in window[key])
        value["frozen_window"] = FrozenSettlementWindow(
            SettlementWindow(**window), SimulationTimeline(**frozen["timeline"]),
            _profile(frozen["profile"]), _mapping(frozen["mapping"]))
        value["operations"] = tuple(FrozenOwnerOperation(**op) for op in value["operations"])
        for key in ("evidence_refs", "definition_and_rule_pins"):
            value[key] = tuple(value[key])
        value["dependency_edges"] = tuple(tuple(edge) for edge in value["dependency_edges"])
        plan = BatchSettlementPlan(**value)
        if plan.input_digest != saved.projection_hash:
            raise ValueError("batch_frozen_input_digest_mismatch")
        return plan

    def _freeze(self, plan: BatchSettlementPlan) -> None:
        """Persist complete immutable input, not a projection or progress assertion.

        The existing checkpoint container is only storage here. Owner receipts
        remain the sole source for reconstructing execution progress.
        """
        stores = {id(adapter.store): adapter.store for adapter in self.adapters.values()}
        if len(stores) != 1:
            raise ValueError("batch_shared_store_required")
        store = next(iter(stores.values()))
        checkpoint_id = f"batch-input:{plan.batch_ref}"
        saved = store.get_projection_checkpoint(checkpoint_id)
        if saved is not None:
            if saved.projection_hash != plan.input_digest or self.load(plan.batch_ref).input_digest != plan.input_digest:
                raise ValueError("batch_input_identity_reused")
            return
        if plan.frozen_window is None:
            raise ValueError("batch_window_required")
        plan.frozen_window.validate(plan)
        context = _dump(plan.frozen_window)
        context["window"].pop("settlement_idempotency_key")
        checkpoints = []
        for op in plan.operations:
            identity = _digest((op.owner_ref, op.command.idempotency_key))
            claim_id = f"batch-operation:{identity}"
            claim_digest = _digest(dict(operation=op.input_digest, window=context,
                                        rules=plan.definition_and_rule_pins, plan_revision=plan.plan_revision,
                                        dependencies=sorted((a, b) for a, b in plan.dependency_edges if b == op.operation_ref),
                                        ordering=plan.ordering_policy_ref, failure=plan.failure_policy_ref))
            prior = store.get_projection_checkpoint(claim_id)
            if prior is not None and prior.projection_hash != claim_digest:
                raise ValueError("batch_operation_identity_reused")
            checkpoints.append(ProjectionCheckpoint(
                checkpoint_id=claim_id, projector_id="world_runtime.batch_operation@1",
                projector_version="1", projection_schema_version=1,
                state={"batch_ref": plan.batch_ref}, projection_hash=claim_digest))
        checkpoints.append(ProjectionCheckpoint(
            checkpoint_id=checkpoint_id, projector_id="world_runtime.batch_input@1",
            projector_version="1", projection_schema_version=1,
            state={"plan": _dump(replace(plan, recovery_cursor=0))}, projection_hash=plan.input_digest))
        store.save_projection_checkpoints_atomic(checkpoints)

    def execute(self, plan: BatchSettlementPlan, *, budget: int,
                predecessor: BatchSettlementPlan | None = None,
                adapter_admission: AdapterAdmission | None = None,
                current_descriptors: tuple[AdapterDescriptor, ...] = ()) -> BatchSettlementResult:
        if type(budget) is not int or budget < 0:
            raise ValueError("batch_budget_invalid")
        ordered = plan.ordered_operations()
        if plan.predecessor_batch_ref is not None:
            if (predecessor is None or predecessor.batch_ref != plan.predecessor_batch_ref
                    or predecessor.batch_ref == plan.batch_ref):
                raise ValueError("batch_predecessor_required")
            # This admitted successor policy only carries unchanged operations.
            # Changing or compensating a previous operation needs its owner policy.
            current = {op.operation_ref: op for op in ordered}
            if any(current.get(op.operation_ref) != op for op in predecessor.operations):
                raise ValueError("batch_successor_operation_changed")
        adapters = {}
        for op in ordered:
            adapter = self.adapters.get((op.owner_ref, op.owner_contract_ref))
            if adapter is None:
                raise ValueError("batch_owner_contract_not_admitted")
            adapter.validate(op)
            adapters[op.operation_ref] = adapter
        self._freeze(plan)
        receipts: dict[str, OwnerCommitReceipt] = {}
        for op in ordered:
            command = op.command
            observed_before = tuple(sorted((stream, adapters[op.operation_ref].store.get_stream_head(stream))
                                           for stream in command.expected_revisions))
            result = None
            conflict = ()
            status = "deferred"
            adapter = adapters[op.operation_ref]
            try:
                result = adapter.query(op)
                dependencies = [receipts[a] for a, b in plan.dependency_edges if b == op.operation_ref]
                if adapter_admission is not None and not adapter_admission.can_confirm(current_descriptors):
                    conflict = ("adapter_confirmation_blocked",)
                    # Preserve the actual committed receipt, but do not confirm
                    # this batch while a participating adapter has lost capability.
                elif result is None and any(r.status != "committed" for r in dependencies):
                    conflict = ("dependency_not_committed",)
                elif result is None and any(command.read_set_revisions.get(stream) != revision
                                             for receipt in dependencies
                                             for stream, revision in receipt.owner_revision_after):
                    conflict = ("dependency_revision_not_pinned",)
                elif result is None and budget > 0:
                    budget -= 1
                    try:
                        result = adapter.commit(op)
                    except TimeoutError:
                        # A timeout says nothing about whether the owner committed.
                        result = adapter.query(op)
                        if result is None:
                            conflict = ("owner_receipt_unknown",)
                if result is not None:
                    status = "committed" if result.committed else "rejected"
                    if result.failure is not None:
                        conflict = (result.failure.error_code,)
            except ValueError as exc:
                status = "rejected"
                conflict = (str(exc),)
            receipts[op.operation_ref] = OwnerCommitReceipt(
                plan.batch_ref, plan.plan_revision, op.owner_ref, op.operation_ref, op.input_digest,
                tuple(result.committed_event_ids) if result is not None and result.committed else (),
                (op.operation_ref,) if status == "rejected" else (), conflict,
                tuple(sorted(command.expected_revisions.items())) if result is not None and result.committed else observed_before,
                tuple(sorted(result.resulting_stream_revisions.items())) if result is not None and result.committed else (),
                status)
        values = tuple(receipts.values())
        cursor = 0
        for receipt in values:
            if receipt.status != "committed":
                break
            cursor += 1
        completed = cursor == len(values) and (adapter_admission is None
                                               or adapter_admission.can_confirm(current_descriptors))
        return BatchSettlementResult(plan.batch_ref, plan.input_digest,
                                     "completed" if completed else "pending_recovery", values, cursor,
                                     plan.confirmation_boundary if completed else None)
