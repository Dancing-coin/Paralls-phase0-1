from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
from collections.abc import Mapping

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.gameplay.settlement_plan import build_multi_stream_atomic_event_batch
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from app.world_runtime.scheduling import (
    RuntimePopulationPolicy,
    RuntimeWakeUpCandidate,
    select_population_continuity_actor_ids,
)

from .models import DueEvaluationReceipt, WorldModeProfile, WorldModeReceipt
from .continuous import B0ContinuousResult, advance_b0_row
from .hot_state import PopulationDueIndex, PopulationHotState
from .siming_contracts import PopulationCadenceInput, PopulationProjection, dump_population_projections
from .roster import PopulationRoster, load_population_roster
from .member_ledger import (
    MEMBER_HANDOFF_EVENT, MEMBER_LEDGER_EVENT, MEMBER_LEDGER_OWNER, ConfirmedMemberResult, MemberEntry, MemberHandoffRecord, MemberLedgerRecord,
    MEMBER_REENTRY_EVENT, MemberReentryRecord, MemberResultRecord, PopulationMemberLedger, actor_result_source, member_ledger_replay, partition_members,
    member_ledger_stream, member_result_stream, parse_member_record, pending_member_results, read_member_ledger_state,
)
from .simulation_contracts import CharacterSimulationFrame, ParticipationResolution, simulation_digest
from .handoff import prepare_intersection


@dataclass(frozen=True)
class PopulationCadenceConfirmationReceipt:
    cadence_id: str
    status: str
    window_start: int
    window_end: int
    advanced_count: int
    presentation_due_count: int
    new_due_count: int
    due_count: int
    deferred_count: int
    rejected_count: int
    due_backlog_count: int
    projection_digest: str
    result_digest: str


class WorldContinuityRuntime:
    """Explicit request boundary over existing runtime cadence policy."""

    def __init__(
        self,
        *,
        store: GameplayEventStore,
        mode: WorldModeProfile,
        authorized_actor_refs: frozenset[str] | None = None,
        roster: PopulationRoster | None = None,
    ) -> None:
        self.store = store
        self.mode = mode
        self.authorized_actor_refs = authorized_actor_refs
        self.roster = roster if roster is not None else load_population_roster()
        from .recovery import population_kernel_digest
        self._population_kernel_digest = population_kernel_digest()
        self._cadence_cache: dict[tuple[object, ...], PopulationCadenceInput] = {}
        self._projection_cache: dict[tuple[object, ...], tuple[PopulationProjection, ...]] = {}
        self.population_hot_state = PopulationHotState(self.roster.actor_ids)
        self._population_due_index = PopulationDueIndex()
        for actor_id in self.roster.actor_ids:
            row = self.population_hot_state.read(actor_id)
            self._population_due_index.schedule(
                actor_id,
                "b0:presentation-threshold",
                int(row["next_due_tick"]),
                int(row["revision"]),
            )
        self._preview_results: dict[tuple[object, ...], tuple[B0ContinuousResult, ...]] = {}
        self._confirmed_receipts: dict[str, PopulationCadenceConfirmationReceipt] = {}
        self._confirmed_fingerprints: dict[str, str] = {}
        self._confirmed_window_end: int | None = None
        self._confirmed_rule_identity: tuple[str, str, str, str] | None = None
        self.last_population_confirmation: PopulationCadenceConfirmationReceipt | None = None
        self._character_participation: dict[str, ParticipationResolution] | None = None
        self._character_activation_authority = None
        self._character_cohort_ref: str | None = None
        self._admission_previews: dict[str, str] = {}
        self._active_b0_actor_ids: tuple[str, ...] = ()

    @property
    def latest_confirmation(self) -> PopulationCadenceConfirmationReceipt | None:
        return self.last_population_confirmation

    def configure_character_participation(self, *, resolutions, activation_authority, cohort_ref: str) -> None:
        """装配已解析参与策略；未配置的既有运行保持原人口合同。"""
        expected = {f"character:{actor}" for actor in self.roster.actor_ids}
        if set(resolutions) != expected:
            raise ValueError("character_participation_roster_mismatch")
        if (not cohort_ref or not callable(getattr(activation_authority, "active_lock", None))
                or activation_authority.store is not self.store):
            raise ValueError("character_participation_context_invalid")
        validated = {actor: ParticipationResolution.model_validate(value.model_dump(mode="python"))
                     for actor, value in resolutions.items()}
        ledger = self.read_member_ledger(cohort_ref)
        if {entry.actor_ref for entry in ledger.member_entries} != expected:
            raise ValueError("character_participation_roster_mismatch")
        self._character_participation = validated
        self._character_activation_authority = activation_authority
        self._character_cohort_ref = cohort_ref

    def _character_admission(self, cadence: PopulationCadenceInput) -> tuple[tuple[str, ...], str | None]:
        if self._character_participation is None:
            return self.roster.actor_ids, None
        ledger = self.read_member_ledger(self._character_cohort_ref)
        members = {entry.actor_ref: entry for entry in ledger.member_entries}
        eligible, pins = [], []
        for actor_id in self.roster.actor_ids:
            actor = f"character:{actor_id}"
            resolution = self._character_participation[actor]
            member = members[actor]
            lock = self._character_activation_authority.active_lock(world_ref=self.mode.world_ref, profile_ref=actor)
            admitted = (member.lifecycle == "active" and resolution.status == "resolved"
                        and "B0" in resolution.allowed_tiers
                        and cadence.window_end <= min(resolution.b0_expiry_tick, resolution.review_tick)
                        and dict(member.participation_policy_pins) == dict(resolution.source_policy_pins)
                        and lock is None)
            if admitted:
                self._check_member_actor_scope(actor)
                eligible.append(actor_id)
            pins.append((actor, resolution.model_dump(mode="json"), member.model_dump(mode="json"),
                         lock.model_dump(mode="json") if lock is not None else None))
        digest = simulation_digest(pins)
        previous = self._admission_previews.get(cadence.cadence_id)
        if previous is not None and previous != digest:
            raise ValueError("character_admission_stale")
        self._admission_previews[cadence.cadence_id] = digest
        return tuple(eligible), digest

    def member_ledger_stream(self, cohort_ref: str) -> str:
        return member_ledger_stream(self.mode.world_ref, cohort_ref)

    def read_member_ledger(self, cohort_ref: str, *, checkpoint=None) -> PopulationMemberLedger:
        return self._read_member_ledger_state(cohort_ref, checkpoint=checkpoint)[0]

    def _read_member_ledger_state(self, cohort_ref: str, *, checkpoint=None):
        return read_member_ledger_state(self.store, stream=self.member_ledger_stream(cohort_ref),
            world_ref=self.mode.world_ref, cohort_ref=cohort_ref, checkpoint=checkpoint)

    def create_member_ledger_checkpoint(self, cohort_ref: str):
        _, _, events = self._read_member_ledger_state(cohort_ref)
        checkpoint = member_ledger_replay(self.member_ledger_stream(cohort_ref)).create_checkpoint(events)
        self.store.save_projection_checkpoint(checkpoint)
        return checkpoint

    def _member_operation_key(self, cohort_ref: str, idempotency_key: str) -> str:
        if not cohort_ref or not idempotency_key:
            raise ValueError("member_operation_identity_invalid")
        return f"member-ledger:v1:{simulation_digest((self.mode.world_ref, cohort_ref, idempotency_key))}"

    def _prior_member_operation(self, cohort_ref: str, idempotency_key: str, digest: str):
        key = self._member_operation_key(cohort_ref, idempotency_key)
        previous = self.store.get_by_idempotency(MEMBER_LEDGER_OWNER, key)
        if previous is not None:
            event = self.store.get_event(previous.committed_event_ids[0])
            record = parse_member_record(self.store, event)
            recorded_cohort = record.ledger.cohort_ref if isinstance(record, (MemberLedgerRecord, MemberReentryRecord)) else record.cohort_ref
            if (record.world_ref != self.mode.world_ref or recorded_cohort != cohort_ref
                    or record.request_digest != digest):
                raise ValueError("member_idempotency_conflict")
            return previous.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
        return None

    def _check_member_actor_scope(self, actor_ref: str) -> None:
        if (actor_ref.removeprefix("character:") not in self.roster.actor_ids
                or (self.authorized_actor_refs is not None and actor_ref not in self.authorized_actor_refs)):
            raise ValueError("member_actor_scope_denied")

    def _append_member_record(self, record, *, stream: str, expected_revision: int,
                               idempotency_key: str, read_revisions: dict[str, int]):
        if self.mode.mode not in {"game", "simulation"}:
            raise ValueError("member_ledger_mode_denied")
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("member_revision_invalid")
        members = record.ledger.member_entries if isinstance(record, (MemberLedgerRecord, MemberReentryRecord)) else (record.member,)
        for member in members:
            self._check_member_actor_scope(member.actor_ref)
        cohort = record.ledger.cohort_ref if isinstance(record, (MemberLedgerRecord, MemberReentryRecord)) else record.cohort_ref
        key = self._member_operation_key(cohort, idempotency_key)
        event_type = (MEMBER_REENTRY_EVENT if isinstance(record, MemberReentryRecord) else
                      MEMBER_HANDOFF_EVENT if isinstance(record, MemberHandoffRecord) else MEMBER_LEDGER_EVENT)
        batch = build_multi_stream_atomic_event_batch(command_id=key, principal_ref=MEMBER_LEDGER_OWNER,
            expected_revisions={stream: expected_revision}, read_stream_revisions=read_revisions,
            event_specs={stream: ((event_type, record.model_dump(mode="json")),)},
            event_visibility_policies={stream: ("authority_only",)}, idempotency_key=key,
            causation_id=key, correlation_id=cohort)
        return self.store.append_batch(batch)

    def register_member_ledger(self, ledger: PopulationMemberLedger, *, continuity_runtime,
                                 idempotency_key: str):
        ledger = PopulationMemberLedger.model_validate(ledger)
        digest = simulation_digest(dict(operation="register", ledger=ledger.model_dump(mode="json")))
        previous = self._prior_member_operation(ledger.cohort_ref, idempotency_key, digest)
        if previous is not None:
            return previous
        stream = self.member_ledger_stream(ledger.cohort_ref)
        if self.store.get_stream_head(stream):
            raise ValueError("member_ledger_already_registered")
        if ledger.confirmed_results or any(entry.last_consumed_result_cursor or entry.lifecycle != "active"
                or entry.shard_ref == "unpartitioned" for entry in ledger.member_entries):
            raise ValueError("member_ledger_initial_results_denied")
        for entry in ledger.member_entries:
            actor_id = entry.actor_ref.removeprefix("character:")
            self._check_member_actor_scope(entry.actor_ref)
            if continuity_runtime.get_continuity_revision(actor_id) != entry.entry_character_revision:
                raise ValueError("member_character_anchor_stale")
        record = MemberLedgerRecord(world_ref=self.mode.world_ref, request_digest=digest, ledger=ledger)
        return self._append_member_record(record, stream=stream, expected_revision=0,
            idempotency_key=idempotency_key, read_revisions={})

    def register_member_reentry(self, *, source_cohort_ref: str, cohort_ref: str, actor_ref: str,
            resolution: ParticipationResolution, continuity_runtime, activation_authority, idempotency_key: str):
        """同一 World Owner 只重建返回者锚点，其余成员沿用原已确认历史。"""
        actor_id = actor_ref.removeprefix("character:")
        resolution = ParticipationResolution.model_validate(resolution.model_dump())
        revision = continuity_runtime.get_continuity_revision(actor_id)
        digest = simulation_digest(dict(operation="reentry", source_cohort_ref=source_cohort_ref,
            actor_ref=actor_ref, resolution=resolution.model_dump(mode="json"), character_revision=revision))
        previous = self._prior_member_operation(cohort_ref, idempotency_key, digest)
        if previous is not None:
            return previous
        old, source_vector, _ = self._read_member_ledger_state(source_cohort_ref)
        activation_stream = f"population:{self.mode.world_ref}"
        activation_revision = self.store.get_stream_head(activation_stream)
        member = next((item for item in old.member_entries if item.actor_ref == actor_ref), None)
        tick = self._confirmed_window_end
        if (cohort_ref == source_cohort_ref or member is None or member.lifecycle != "handoff"
                or activation_authority.store is not self.store or resolution.status != "resolved"
                or "B0" not in resolution.allowed_tiers or tick >= min(resolution.b0_expiry_tick, resolution.review_tick)
                or continuity_runtime.get_character_simulation_cursor(actor_id) != tick
                or activation_authority.active_lock(world_ref=self.mode.world_ref, profile_ref=actor_ref) is not None
                or pending_member_results(old, actor_ref=actor_ref)):
            raise ValueError("member_reentry_not_ready")
        if self.store.get_stream_head(self.member_ledger_stream(cohort_ref)):
            raise ValueError("member_ledger_already_registered")
        member = MemberEntry.model_validate({**member.model_dump(), "lifecycle": "active",
            "entry_character_revision": revision, "last_consumed_result_cursor": 0,
            "participation_policy_pins": resolution.source_policy_pins})
        # 原分片许可编译只用于返回者；其他成员不重新分片或清空结果。
        single = PopulationMemberLedger.model_validate({**old.model_dump(), "cohort_ref": cohort_ref,
            "member_entries": (member,), "confirmed_results": (), "receipt_refs": ()})
        member = partition_members(single, seed=old.seed, partition_revision=old.partition_revision).member_entries[0]
        ledger = PopulationMemberLedger.model_validate({**old.model_dump(), "cohort_ref": cohort_ref,
            "member_entries": tuple(member if item.actor_ref == actor_ref else item for item in old.member_entries),
            "confirmed_results": tuple(item for item in old.confirmed_results if item.actor_ref != actor_ref), "receipt_refs": ()})
        source_stream = self.member_ledger_stream(source_cohort_ref)
        vector = {source_stream: source_vector[source_stream]}
        vector.update({member_result_stream(source_stream, item.actor_ref): source_vector.get(
            member_result_stream(source_stream, item.actor_ref), 0) for item in old.member_entries})
        record = MemberReentryRecord(world_ref=self.mode.world_ref, source_cohort_ref=source_cohort_ref,
            source_revision_vector=vector, returning_actor_ref=actor_ref, request_digest=digest, ledger=ledger)
        return self._append_member_record(record, stream=self.member_ledger_stream(cohort_ref), expected_revision=0,
            idempotency_key=idempotency_key, read_revisions={**vector,
                activation_stream: activation_revision})

    def confirm_member_result(self, *, cohort_ref: str, actor_ref: str, result_ref: str,
                              expected_revision: int, idempotency_key: str):
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("member_revision_invalid")
        digest = simulation_digest(dict(operation="confirm", actor_ref=actor_ref, result_ref=result_ref))
        previous = self._prior_member_operation(cohort_ref, idempotency_key, digest)
        if previous is not None:
            return previous
        ledger, vector, _ = self._read_member_ledger_state(cohort_ref)
        member = next((entry for entry in ledger.member_entries if entry.actor_ref == actor_ref), None)
        if member is None:
            raise ValueError("member_actor_unknown")
        event, owner_receipt = actor_result_source(self.store, actor_ref=actor_ref, result_ref=result_ref)
        actor_results = tuple(item for item in ledger.confirmed_results if item.actor_ref == actor_ref)
        if result_ref not in {item.result_ref for item in actor_results}:
            if event.global_sequence <= member.last_consumed_result_cursor:
                raise ValueError("member_result_before_consumed_cursor")
            actor_results += (ConfirmedMemberResult(actor_ref=actor_ref, result_ref=result_ref,
                source_cursor=event.global_sequence, source_digest=simulation_digest(event.model_dump(mode="json")),
                source_revision_vector=owner_receipt.resulting_stream_revisions),)
        stream = member_result_stream(self.member_ledger_stream(cohort_ref), actor_ref)
        record = MemberResultRecord(world_ref=self.mode.world_ref, cohort_ref=cohort_ref,
            request_digest=digest, member=member, confirmed_results=actor_results)
        return self._append_member_record(record, stream=stream, expected_revision=vector.get(stream, 0),
            idempotency_key=idempotency_key, read_revisions={self.member_ledger_stream(cohort_ref): expected_revision})

    def consume_member_result(self, *, cohort_ref: str, actor_ref: str, result_ref: str,
            continuity_runtime, continuity_idempotency_key: str, expected_revision: int, idempotency_key: str):
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("member_revision_invalid")
        digest = simulation_digest(dict(operation="consume", actor_ref=actor_ref, result_ref=result_ref,
            continuity_idempotency_key=continuity_idempotency_key))
        previous = self._prior_member_operation(cohort_ref, idempotency_key, digest)
        if previous is not None:
            return previous
        ledger, vector, _ = self._read_member_ledger_state(cohort_ref)
        pending = pending_member_results(ledger, actor_ref=actor_ref)
        if not pending or pending[0] != result_ref:
            raise ValueError("member_consumption_out_of_order")
        receipt = continuity_runtime.get_character_continuity_receipt(actor_ref.removeprefix("character:"),
            idempotency_key=continuity_idempotency_key)
        if receipt is None:
            raise ValueError("member_core_receipt_unavailable")
        if receipt.actor_ref != actor_ref or receipt.status not in {"committed", "idempotent_replay"}:
            raise ValueError("member_core_receipt_invalid")
        if result_ref not in receipt.source_owner_receipt_refs:
            raise ValueError("member_core_source_mismatch")
        required_revisions = {}
        for source in ledger.confirmed_results:
            if source.actor_ref == actor_ref and source.result_ref in receipt.source_owner_receipt_refs:
                for stream, revision in source.source_revision_vector.items():
                    required_revisions[stream] = max(required_revisions.get(stream, 0), revision)
        if any(receipt.source_revision_vector.get(stream) != revision
               for stream, revision in required_revisions.items()):
            raise ValueError("member_core_source_revision_mismatch")
        member = next(entry for entry in ledger.member_entries if entry.actor_ref == actor_ref)
        if receipt.character_revision_before < member.entry_character_revision:
            raise ValueError("member_core_revision_stale")
        actor_results = []
        cursor = 0
        for item in ledger.confirmed_results:
            if item.actor_ref != actor_ref:
                continue
            if item.result_ref == result_ref:
                item = ConfirmedMemberResult.model_validate({**item.model_dump(),
                    "consumed_core_receipt_ref": receipt.receipt_ref,
                    "consumed_core_revision": receipt.character_revision_after})
                cursor = item.source_cursor
            actor_results.append(item)
        member = MemberEntry.model_validate({**member.model_dump(), "last_consumed_result_cursor": cursor})
        stream = member_result_stream(self.member_ledger_stream(cohort_ref), actor_ref)
        record = MemberResultRecord(world_ref=self.mode.world_ref, cohort_ref=cohort_ref,
            request_digest=digest, member=member, confirmed_results=tuple(actor_results))
        return self._append_member_record(record, stream=stream, expected_revision=vector.get(stream, 0),
            idempotency_key=idempotency_key, read_revisions={self.member_ledger_stream(cohort_ref): expected_revision})

    def read_member_handoff(self, *, cohort_ref: str, actor_ref: str):
        ledger = self.read_member_ledger(cohort_ref)
        if actor_ref not in {entry.actor_ref for entry in ledger.member_entries}:
            raise ValueError("member_actor_unknown")
        events = self.store.read_stream(member_result_stream(self.member_ledger_stream(cohort_ref), actor_ref),
            event_type=MEMBER_HANDOFF_EVENT)
        if events:
            return parse_member_record(self.store, events[-1]).intersection
        member = next(item for item in ledger.member_entries if item.actor_ref == actor_ref)
        root = parse_member_record(self.store, self.store.read_stream(self.member_ledger_stream(cohort_ref))[0])
        if member.lifecycle == "handoff" and isinstance(root, MemberReentryRecord):
            return self.read_member_handoff(cohort_ref=root.source_cohort_ref, actor_ref=actor_ref)
        return None

    def prepare_member_handoff(self, *, cohort_ref: str, frame: CharacterSimulationFrame,
            trigger_kind: str, target_fidelity: str, activation_authority, continuity_runtime,
            expected_revision: int, idempotency_key: str):
        """原 World Owner 记录交接凭据；调用方仍须检查原 append 结果才能接管。"""
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("member_revision_invalid")
        frame = CharacterSimulationFrame.model_validate(frame)
        digest = simulation_digest(dict(operation="handoff", frame=frame.model_dump(mode="json"),
            trigger_kind=trigger_kind, target_fidelity=target_fidelity))
        previous = self._prior_member_operation(cohort_ref, idempotency_key, digest)
        if previous is not None:
            record = parse_member_record(self.store, self.store.get_event(previous.committed_event_ids[0]))
            if not isinstance(record, MemberHandoffRecord):
                raise ValueError("member_idempotency_conflict")
            return record.intersection, previous
        ledger, vector, _ = self._read_member_ledger_state(cohort_ref)
        if activation_authority.store is not self.store:
            raise ValueError("handoff_authority_store_mismatch")
        lock = activation_authority.active_lock(world_ref=self.mode.world_ref, profile_ref=frame.actor_ref)
        if lock is None:
            raise ValueError("handoff_lock_stale")
        actor_id = frame.actor_ref.removeprefix("character:")
        if continuity_runtime.get_character_activation_lock(actor_id) != lock:
            raise ValueError("handoff_lock_stale")
        if (continuity_runtime.get_continuity_revision(actor_id) != frame.character_core_revision
                or continuity_runtime.get_character_simulation_cursor(actor_id) != frame.simulation_tick_cursor):
            raise ValueError("handoff_core_frame_stale")
        packet = prepare_intersection(frame=frame, ledger=ledger, trigger_kind=trigger_kind,
            target_fidelity=target_fidelity, lock=lock)
        member = next(entry for entry in ledger.member_entries if entry.actor_ref == frame.actor_ref)
        member = MemberEntry.model_validate({**member.model_dump(), "lifecycle": "handoff"})
        record = MemberHandoffRecord(world_ref=self.mode.world_ref, cohort_ref=cohort_ref, request_digest=digest,
            member=member, confirmed_results=tuple(item for item in ledger.confirmed_results
                if item.actor_ref == frame.actor_ref), intersection=packet)
        stream = member_result_stream(self.member_ledger_stream(cohort_ref), frame.actor_ref)
        read_revisions = dict(frame.source_revision_vector)
        read_revisions.setdefault(f"population:{self.mode.world_ref}",
            self.store.get_stream_head(f"population:{self.mode.world_ref}"))
        read_revisions[self.member_ledger_stream(cohort_ref)] = expected_revision
        result = self._append_member_record(record, stream=stream, expected_revision=vector.get(stream, 0),
            idempotency_key=idempotency_key, read_revisions=read_revisions)
        return packet, result

    def _recovery_context_digest(self) -> str:
        from .recovery import recovery_digest

        context = {"mode": self.mode.model_dump(mode="json"),
                                "roster": list(self.roster.actor_ids),
                                "authorized_actor_refs": (sorted(self.authorized_actor_refs)
                                                          if self.authorized_actor_refs is not None else None)}
        if self._character_participation is not None:
            # 窗口回执绑定推进合同；会变化的入组 pins 单独绑定恢复状态。
            context["character_participation_contract"] = "selective-b0@2"
        return recovery_digest(context)

    def _participation_digest(self) -> str:
        return simulation_digest(dict(cohort_ref=self._character_cohort_ref,
            resolutions={actor: value.model_dump(mode="json")
                for actor, value in self._character_participation.items()}))

    def export_recovery_state(self) -> dict[str, object]:
        """导出最近一次完整确认的派生态；不携带全历史 receipts 或预计算缓存。"""
        from .recovery import PopulationRecoveryState, SelectivePopulationRecoveryState

        model = SelectivePopulationRecoveryState if self._character_participation is not None else PopulationRecoveryState
        return model.model_validate_json(
            json.dumps(self._build_recovery_state_payload())
        ).model_dump(mode="json")

    def _build_recovery_state_payload(self) -> dict[str, object]:
        """构造独立快照；调用方须在公开输出或持久化前完整验证。"""
        from .recovery import recovery_digest

        receipt = self.last_population_confirmation
        state = {
            "schema_version": 2 if self._character_participation is not None else 1,
            "context_digest": self._recovery_context_digest(),
            "confirmed_tick": self._confirmed_window_end,
            "rule_identity": list(self._confirmed_rule_identity) if self._confirmed_rule_identity else None,
            "actors": [{"actor_id": actor_id, **row,
                        **{key: float(row[key]) for key in ("fatigue", "need_pressure", "starvation_credit")}}
                       for actor_id, row in self.population_hot_state.export_rows()],
            "due_entries": [dict(actor_id=actor_id, obligation_id=obligation_id, due_tick=tick, revision=revision)
                            for actor_id, obligation_id, tick, revision in self._population_due_index.export_entries()],
            "last_receipt": asdict(receipt) if receipt is not None else None,
            "last_fingerprint": self._confirmed_fingerprints[receipt.cadence_id] if receipt is not None else None,
        }
        if self._character_participation is not None:
            state["active_b0_actor_ids"] = list(self._active_b0_actor_ids)
            state["participation_digest"] = self._participation_digest()
            state["cohort_ref"] = self._character_cohort_ref
        state["state_digest"] = recovery_digest(state)
        return state

    def restore_recovery_state(self, state: dict[str, object]) -> None:
        """先完整验证并构建临时热表，成功后一次安装；不追加权威事实。"""
        from .recovery import PopulationRecoveryState, SelectivePopulationRecoveryState

        model = SelectivePopulationRecoveryState if self._character_participation is not None else PopulationRecoveryState
        parsed = model.model_validate_json(json.dumps(state, allow_nan=False))
        if parsed.context_digest != self._recovery_context_digest():
            raise ValueError("population_recovery_context_mismatch")
        if (self._character_participation is not None
                and (parsed.participation_digest != self._participation_digest()
                    or parsed.cohort_ref != self._character_cohort_ref)):
            raise ValueError("population_recovery_participation_mismatch")
        if tuple(actor.actor_id for actor in parsed.actors) != tuple(sorted(self.roster.actor_ids)):
            raise ValueError("population_recovery_roster_mismatch")
        hot = PopulationHotState()
        for actor in parsed.actors:
            hot.upsert(actor.actor_id, actor.model_dump(exclude={"actor_id", "revision"}), actor.revision)
        due = PopulationDueIndex()
        due.rebuild((entry.actor_id, entry.obligation_id, entry.due_tick, entry.revision) for entry in parsed.due_entries)
        self.population_hot_state = hot
        self._population_due_index = due
        self._confirmed_window_end = parsed.confirmed_tick
        self._confirmed_rule_identity = parsed.rule_identity
        self.last_population_confirmation = parsed.last_receipt
        self._confirmed_receipts = ({parsed.last_receipt.cadence_id: parsed.last_receipt}
                                    if parsed.last_receipt is not None else {})
        self._confirmed_fingerprints = ({parsed.last_receipt.cadence_id: parsed.last_fingerprint}
                                        if parsed.last_receipt is not None else {})
        self._cadence_cache.clear()
        self._projection_cache.clear()
        self._preview_results.clear()
        self._admission_previews.clear()
        self._active_b0_actor_ids = getattr(parsed, "active_b0_actor_ids", ())

    def pause(
        self, *, reason: str, expected_mode_revision: str | None = None
    ) -> WorldModeReceipt:
        return self._transition(
            "pause", reason, expected_mode_revision=expected_mode_revision
        )

    def resume(self, *, expected_mode_revision: str | None = None) -> WorldModeReceipt:
        return self._transition(
            "resume", "explicit-resume", expected_mode_revision=expected_mode_revision
        )

    def evaluate_due(
        self,
        *,
        actor_ref: str,
        obligation_refs: tuple[str, ...],
        overdue_refs: tuple[str, ...] = (),
    ) -> DueEvaluationReceipt:
        if (
            self.authorized_actor_refs is not None
            and actor_ref not in self.authorized_actor_refs
        ):
            return DueEvaluationReceipt(
                zero_write=True, stop_reason="profile_not_active"
            )
        envelopes = tuple(
            GameplayCommandEnvelope(
                command_id=f"due:{self.mode.world_ref}:{actor_ref}:{ref}",
                command_type="population.obligation.evaluate",
                command_version=1,
                principal_ref="world_runtime.cadence",
                actor_ref=actor_ref,
                project_ref=None,
                transaction_id=None,
                idempotency_key=f"due:{self.mode.world_ref}:{actor_ref}:{ref}",
                causation_id=f"cadence:{self.mode.revision}",
                correlation_id=f"world:{self.mode.world_ref}",
                source_ref="world_runtime.cadence",
                submitted_at="explicit-request",
                pinned_revisions={"mode": 1, "policy": 1},
                expected_revisions={},
                payload={
                    "obligation_ref": ref,
                    "survival_mode": self.mode.survival_mode,
                    "overdue": ref in overdue_refs,
                },
            )
            for ref in obligation_refs[: self.mode.batch_limit]
        )
        return DueEvaluationReceipt(
            envelopes=envelopes, zero_write=True, overdue_refs=overdue_refs
        )

    def select_actors(
        self,
        *,
        candidates: list[RuntimeWakeUpCandidate],
        policy: RuntimePopulationPolicy,
    ) -> tuple[str, ...]:
        return tuple(
            select_population_continuity_actor_ids(
                candidates=candidates,
                policy=policy,
                actor_population=len(candidates),
                wake_budget=self.mode.wake_budget,
            )
        )

    def is_paused(self) -> bool:
        """读取最近一次已提交的世界模式边界，不写入世界真相。"""
        stream = f"world:{self.mode.world_ref}"
        events = self.store.read_stream(stream, from_revision=self.store.get_stream_head(stream))
        return bool(events and events[-1].event_type == "population.world.pause")

    def build_population_cadence(
        self,
        *,
        window_start: int,
        window_end: int,
        cadence_id: str | None = None,
        policy_revision: str = "policy:population:v1",
        selector_revision: str = "selector:generic:population:v1",
        ruleset_revision: str = "rules:population:v1",
        report_scope: str = "public",
        budget: int | None = None,
    ) -> PopulationCadenceInput:
        """Build one deterministic window from the committed world stream."""
        if window_end <= window_start:
            raise ValueError("population_cadence_window_invalid")
        world_stream = f"world:{self.mode.world_ref}"
        source_revision = self.store.get_stream_head(world_stream)
        if source_revision <= 0:
            raise ValueError("population_cadence_source_missing")
        source_heads = {world_stream: source_revision}
        if self._character_participation is not None:
            root = self.member_ledger_stream(self._character_cohort_ref)
            streams = (root, f"population:{self.mode.world_ref}",
                *(member_result_stream(root, f"character:{actor}") for actor in self.roster.actor_ids))
            for stream in streams:
                source_heads[stream] = self.store.get_stream_head(stream)
        cache_key = (
            cadence_id,
            window_start,
            window_end,
            source_revision,
            policy_revision,
            selector_revision,
            ruleset_revision,
            report_scope,
            budget,
            source_revision,
            tuple(self.roster.actor_ids),
            tuple(sorted(self.authorized_actor_refs or ())),
            tuple(sorted(source_heads.items())),
        )
        cached = self._cadence_cache.get(cache_key)
        if cached is not None:
            return cached
        events = {"stream_heads": source_heads}
        digest = "sha256:" + hashlib.sha256(
            json.dumps(events, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        cadence = PopulationCadenceInput(
            cadence_id=cadence_id or f"cadence:{self.mode.world_ref}:{window_start}",
            world_ref=self.mode.world_ref,
            world_mode_ref=f"world-mode:{self.mode.world_ref}",
            world_mode_revision=self.mode.revision,
            cadence_source_ref=world_stream,
            cadence_source_revision=source_revision,
            window_start=window_start,
            window_end=window_end,
            base_checkpoint_ref=f"checkpoint:population:{self.mode.world_ref}:{source_revision}",
            base_checkpoint_digest=digest,
            base_revision_vector=source_heads,
            policy_revision=policy_revision,
            selector_revision=selector_revision,
            ruleset_revision=ruleset_revision,
            deterministic_seed=f"seed:{self.mode.world_ref}:{window_start}",
            catch_up_limit=self.mode.catch_up_limit,
            budget=self.mode.batch_limit if budget is None else budget,
            report_scope=report_scope,
        )
        self._cadence_cache = {cache_key: cadence}
        return cadence

    def build_population_projections(
        self,
        cadence: PopulationCadenceInput,
        *,
        workers: int = 1,
        batch_size: int = 256,
        population_views: Mapping[str, object] | None = None,
    ) -> tuple[PopulationProjection, ...]:
        """从已确认热状态构造只读 B0 预览；发布前不推进游标。"""
        self._validate_confirmation_context(cadence, pin_rules=False)
        admitted_actor_ids, _ = self._character_admission(cadence)
        cache_key = self._projection_cache_key(cadence, population_views=population_views)
        cached = self._projection_cache.get(cache_key)
        if cached is not None:
            return cached
        if (
            self._confirmed_window_end == cadence.window_start
            and all(
                key[0] in self._confirmed_receipts
                for key in self._projection_cache
            )
        ):
            # 已确认窗口可由 receipt 重放；新窗口计算前释放其万人预览。
            self._projection_cache.clear()
            self._preview_results.clear()
        evaluated = self.population_hot_state.map_readonly(
            admitted_actor_ids,
            lambda actor_id, row: advance_b0_row(
                actor_id=actor_id,
                row=row,
                window_start=cadence.window_start,
                window_end=cadence.window_end,
            ),
            workers=workers,
            batch_size=batch_size,
        )
        by_actor = {result.actor_id: result for result in evaluated}
        due_actor_ids = {
            actor_id
            for actor_id, obligation_id, _due_tick in self._population_due_index.due_items(
                cadence.window_end
            )
            if obligation_id == "b0:presentation-threshold"
        }
        actor_ids = admitted_actor_ids
        window_size = cadence.window_end - cadence.window_start
        start = (cadence.window_start // window_size) % len(actor_ids) if actor_ids else 0
        ordered_actor_ids = actor_ids[start:] + actor_ids[:start]
        results = tuple(by_actor[actor_id] for actor_id in ordered_actor_ids)
        projections = tuple(
            PopulationProjection(
                ref=f"projection:{result.actor_id}:{cadence.window_start}",
                scope="public",
                revision_vector=dict(cadence.base_revision_vector),
                payload={
                    "actor_ref": f"character:{result.actor_id}",
                    "candidate_kind": "routine_work",
                    "behavior_kind": "routine_work",
                    "fidelity_tier": "B0",
                    "from_tick": result.from_tick,
                    "to_tick": result.to_tick,
                    "simulation_tick_cursor": result.to_tick,
                    "actor_revision": result.actor_revision_before,
                    "source_revision_vector": dict(cadence.base_revision_vector),
                    "starvation_credit": result.values["starvation_credit"],
                    "state_deltas": dict(result.values),
                    "presentation_seed": {
                        "task": "daily_routine",
                        "activity_phase": result.values["activity_phase"],
                        "threshold_refs": tuple(
                            f"b0:presentation-threshold:{due_tick}"
                            for due_tick in (
                                result.due_ticks if result.actor_id in due_actor_ids else ()
                            )
                        ),
                    },
                    "due_obligation_refs": (),
                    "scope": "public",
                    "idempotency_key": (
                        f"b0:{cadence.cadence_id}:character:{result.actor_id}"
                    ),
                },
            )
            for result in results
        )
        if population_views:
            enriched: list[PopulationProjection] = []
            for projection in projections:
                actor_ref = str(projection.payload.get("actor_ref") or "")
                view = population_views.get(actor_ref)
                if view is None:
                    enriched.append(projection)
                    continue
                if getattr(view, "consumer", None) != "population":
                    raise ValueError("population_view_required")
                groups = getattr(view, "groups", None)
                if not isinstance(groups, Mapping):
                    raise ValueError("population_view_invalid")
                payload = dict(projection.payload)
                payload["population_state"] = {
                    str(group_id): _thaw_population_value(getattr(envelope, "payload", {}))
                    for group_id, envelope in sorted(groups.items(), key=lambda item: str(item[0]))
                    if isinstance(getattr(envelope, "payload", None), Mapping)
                }
                payload["population_state_source_revision_vector"] = _thaw_population_value(
                    getattr(view, "source_revision_vector", {})
                )
                payload["population_state_checksum"] = str(getattr(view, "view_checksum", ""))
                enriched.append(projection.model_copy(update={"payload": payload}))
            projections = tuple(enriched)
        self._projection_cache = {cache_key: projections}
        self._preview_results = {cache_key: results}
        return projections

    def confirm_population_cadence(
        self, cadence: PopulationCadenceInput
    ) -> PopulationCadenceConfirmationReceipt:
        """在 cadence 已发布后确认同一纯计算结果，重复确认保持幂等。"""
        fingerprint = self._cadence_fingerprint(cadence)
        previous = self._confirmed_receipts.get(cadence.cadence_id)
        if previous is None and self._confirmed_window_end is not None and cadence.window_end <= self._confirmed_window_end:
            from .recovery import durable_population_receipt

            previous = durable_population_receipt(self, cadence)
            if previous is not None:
                return replace(previous, status="idempotent_replay")
        if previous is not None:
            if self._confirmed_fingerprints[cadence.cadence_id] != fingerprint:
                raise ValueError("population_cadence_confirmation_conflict")
            return replace(previous, status="idempotent_replay")
        self._validate_confirmation_context(cadence, pin_rules=True)
        if (
            self._confirmed_window_end is not None
            and cadence.window_start != self._confirmed_window_end
        ):
            raise ValueError("population_cadence_confirmation_conflict")
        projections = self.build_population_projections(cadence)
        cache_key = self._projection_cache_key(cadence)
        results = self._preview_results[cache_key]
        active_ids = frozenset(result.actor_id for result in results)
        due_items = tuple(
            item
            for item in self._population_due_index.due_items(cadence.window_end)
            if item[1] == "b0:presentation-threshold" and item[0] in active_ids
        )
        expected_due_actors = {
            result.actor_id for result in results if result.due_ticks
        }
        if {actor_id for actor_id, _obligation_id, _due_tick in due_items} != expected_due_actors:
            raise ValueError("population_due_index_conflict")
        advanced_count = self.population_hot_state.commit_batch_atomic(
            (
                result.actor_id,
                result.values,
                result.actor_revision_before,
                result.actor_revision_before + 1,
            )
            for result in results
        )
        presentation_due_count = sum(len(result.due_ticks) for result in results)
        consumed_due = self._population_due_index.pop_due(
            cadence.window_end, obligation_id="b0:presentation-threshold", actor_ids=active_ids
        )
        if consumed_due != due_items:
            raise ValueError("population_due_index_conflict")
        if self._character_participation is not None:
            for actor_id in set(self.roster.actor_ids) - active_ids:
                self._population_due_index.cancel(actor_id, "b0:presentation-threshold")
        for result in results:
            self._population_due_index.schedule(
                result.actor_id,
                "b0:presentation-threshold",
                int(result.values["next_due_tick"]),
                result.actor_revision_before + 1,
            )
        backlog = self._population_due_index.due_items(cadence.window_end)
        projection_digest = "sha256:" + hashlib.sha256(
            json.dumps(
                [
                    projection.__dict__
                    for projection in projections
                ],
                check_circular=False,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        result_digest = "sha256:" + hashlib.sha256(
            json.dumps(
                {
                    "cadence": fingerprint,
                    "projection_digest": projection_digest,
                    "advanced_count": advanced_count,
                    "presentation_due_count": presentation_due_count,
                    "due_backlog_count": len(backlog),
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        receipt = PopulationCadenceConfirmationReceipt(
            cadence_id=cadence.cadence_id,
            status="committed",
            window_start=cadence.window_start,
            window_end=cadence.window_end,
            advanced_count=advanced_count,
            presentation_due_count=presentation_due_count,
            new_due_count=presentation_due_count,
            due_count=presentation_due_count,
            deferred_count=len(backlog),
            rejected_count=0,
            due_backlog_count=len(backlog),
            projection_digest=projection_digest,
            result_digest=result_digest,
        )
        self._confirmed_receipts[cadence.cadence_id] = receipt
        self._confirmed_fingerprints[cadence.cadence_id] = fingerprint
        while len(self._confirmed_receipts) > 2:
            oldest = next(iter(self._confirmed_receipts))
            self._confirmed_receipts.pop(oldest)
            self._confirmed_fingerprints.pop(oldest)
        self._confirmed_window_end = cadence.window_end
        self._confirmed_rule_identity = self._rule_identity(cadence)
        self.last_population_confirmation = receipt
        self._active_b0_actor_ids = tuple(sorted(active_ids))
        self._admission_previews = {key: value for key, value in self._admission_previews.items()
                                    if key in self._confirmed_receipts}
        return receipt

    def due_population_work(self, tick: int) -> tuple[tuple[str, str, int], ...]:
        return self._population_due_index.due_items(tick)

    def claim_due_population_work(
        self, tick: int, *, limit: int | None = None
    ) -> tuple[tuple[str, str, int], ...]:
        return self._population_due_index.pop_due(tick, limit=limit)

    def select_due_population_work(
        self, tick: int, *, limit: int | None = None
    ) -> tuple[tuple[str, str, int], ...]:
        due = self._population_due_index.due_items(tick)
        return due if limit is None else due[:limit]

    def complete_due_population_work(self, actor_id: str, obligation_id: str) -> None:
        self._population_due_index.cancel(actor_id, obligation_id)

    def requeue_due_population_work(
        self,
        actor_id: str,
        obligation_id: str,
        due_tick: int,
        *,
        revision: int,
    ) -> None:
        self._population_due_index.schedule(
            actor_id, obligation_id, due_tick, revision
        )

    def _validate_confirmation_context(
        self, cadence: PopulationCadenceInput, *, pin_rules: bool
    ) -> None:
        world_stream = f"world:{self.mode.world_ref}"
        source_events = self.store.read_stream(
            world_stream,
            from_revision=cadence.cadence_source_revision,
            to_revision=cadence.cadence_source_revision,
        )
        source_event = source_events[0] if len(source_events) == 1 else None
        if (
            cadence.world_ref != self.mode.world_ref
            or cadence.world_mode_revision != self.mode.revision
            or cadence.cadence_source_ref != world_stream
            or cadence.cadence_source_revision < 1
            or cadence.base_revision_vector.get(world_stream)
            != cadence.cadence_source_revision
            or self.store.get_stream_head(world_stream) < cadence.cadence_source_revision
            or source_event is None
            or source_event.event_type != "population.world.resume"
            or source_event.payload.get("world_ref") != self.mode.world_ref
            or source_event.payload.get("mode_revision") != self.mode.revision
            or cadence.report_scope != "public"
            or cadence.window_start < 0
            or cadence.window_end <= cadence.window_start
        ):
            raise ValueError("population_cadence_confirmation_context_invalid")
        if (
            pin_rules
            and self._confirmed_rule_identity is not None
            and self._confirmed_rule_identity != self._rule_identity(cadence)
        ):
            raise ValueError("population_cadence_confirmation_context_invalid")

    @staticmethod
    def _rule_identity(cadence: PopulationCadenceInput) -> tuple[str, str, str, str]:
        return (
            cadence.policy_revision,
            cadence.selector_revision,
            cadence.ruleset_revision,
            cadence.report_scope,
        )

    def _projection_cache_key(
        self,
        cadence: PopulationCadenceInput,
        *,
        population_views: Mapping[str, object] | None = None,
    ) -> tuple[object, ...]:
        return (
            cadence.cadence_id,
            cadence.window_start,
            cadence.window_end,
            tuple(sorted(cadence.base_revision_vector.items())),
            *self._rule_identity(cadence),
            tuple(self.roster.actor_ids),
            tuple(
                sorted(
                    (
                        str(actor_ref),
                        str(getattr(view, "view_checksum", "")),
                        repr(getattr(view, "groups", {})),
                    )
                    for actor_ref, view in (population_views or {}).items()
                )
            ),
        )
    @staticmethod
    def _cadence_fingerprint(cadence: PopulationCadenceInput) -> str:
        return "sha256:" + hashlib.sha256(
            json.dumps(
                cadence.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

    def replay_equivalence(self) -> tuple[str, str]:
        replay = GameplayProjectionReplay(
            projector_id="population-continuity", projector_version="1"
        )
        events = self.store.read_events()
        full = replay.full_replay(events)
        index = len(events) // 2
        checkpoint = replay.create_checkpoint(events[:index])
        tail = replay.checkpoint_plus_tail_replay(checkpoint, events[index:])
        return full.projection_hash, tail.projection_hash
    def _transition(
        self, action: str, reason: str, *, expected_mode_revision: str | None = None
    ) -> WorldModeReceipt:
        if (
            expected_mode_revision is not None
            and expected_mode_revision != self.mode.revision
        ):
            return WorldModeReceipt(
                committed=False,
                world_ref=self.mode.world_ref,
                mode_revision=self.mode.revision,
                action="rejected",
                zero_write=True,
                stop_reason="mode_revision_conflict",
            )
        stream = f"world:{self.mode.world_ref}"
        expected = self.store.get_stream_head(stream)
        command_id = f"world:{action}:{self.mode.world_ref}:{expected + 1}"
        batch = build_atomic_event_batch(
            command_id=command_id,
            principal_ref="world_runtime.cadence",
            stream_id=stream,
            expected_revision=expected,
            event_specs=[
                (
                    f"population.world.{action}",
                    {
                        "world_ref": self.mode.world_ref,
                        "mode_revision": self.mode.revision,
                        "reason": reason,
                        "survival_mode": self.mode.survival_mode,
                    },
                )
            ],
            idempotency_key=command_id,
            causation_id=command_id,
            correlation_id=f"world:{self.mode.world_ref}",
            pinned_revisions={"mode": 1},
        )
        result = self.store.append_batch(batch)
        return WorldModeReceipt(
            committed=result.committed,
            world_ref=self.mode.world_ref,
            mode_revision=self.mode.revision,
            action=action if result.committed else "rejected",
            committed_event_ids=tuple(result.committed_event_ids),
            revision_vector=dict(result.resulting_stream_revisions),
            zero_write=not result.committed,
            stop_reason=None
            if result.committed
            else (result.failure.error_code if result.failure else "append_rejected"),
        )


def _thaw_population_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _thaw_population_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_thaw_population_value(item) for item in value]
    return value
