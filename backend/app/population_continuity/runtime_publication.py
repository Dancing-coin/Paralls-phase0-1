from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
from datetime import datetime, timezone
from types import MethodType

from pydantic import ConfigDict, ValidationError

from app.gameplay.dispatcher import GameplayOutboxDispatcher
from app.gameplay.event_store import GameplayEventStoreSnapshotError
from app.gameplay.event_store import GameplayEventStore, DurableGameplayEventStore
from app.gameplay.models import GameplayOutboxEntry, ProjectionCheckpoint
from app.gameplay.organization_government_runtime import OrganizationAuthority, OperatingWindowDueRequest
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.models.authority_event import AuthorityEvent
from app.population_continuity.publication import publish_authorized_population_cadence
from app.population_continuity.organization_due_source import OrganizationWindowDueSource
from app.population_continuity.decision_surface import PopulationDecisionPlanner
from app.population_continuity.siming_contracts import PopulationCadenceInput, PopulationReadSet, dump_population_projections
from app.population_continuity.world import WorldContinuityRuntime
from app.population_continuity.recovery import (
    PopulationRecoveryCheckpoint, durable_population_receipt, parse_population_checkpoint,
    recovery_digest,
)
from app.services.authority_event_bus import AuthorityEventBusPort
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.population_continuity.prepared_frame import capture_publication, encode_captured_projections, native_method
from app.population_continuity.continuous import advance_b0_row
from app.population_continuity.member_ledger import MemberReentryRecord, parse_member_record
from app.population_continuity.simulation_contracts import simulation_digest
from app.services.siming_population_capability import PopulationSimulationCapability


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class _ReceiptCheckpoint(PopulationRecoveryCheckpoint):
    # Python 输入中的现成 dataclass 仍须逐字段校验，保持原 JSON 路径的拒绝语义。
    model_config = ConfigDict(revalidate_instances="always")


class RuntimeCadencePublisher:
    """既有 Gameplay 日志确认窗口，outbox 重试投递；热表仅为可重建投影。"""

    DOMAIN_TOPIC = "population_domain_cadence_event"

    def __init__(self, *, world_runtime: WorldContinuityRuntime, event_bus: AuthorityEventBusPort,
                 room_id: str, scene_id: str, zone_id: str, conflict_pump=None) -> None:
        self.world = world_runtime
        self.store = world_runtime.store
        self.bus = event_bus
        self.location = dict(room_id=room_id, scene_id=scene_id, zone_id=zone_id)
        self.stream_id = f"population-cadence:{self.world.mode.world_ref}"
        self.roster_digest = _digest(self.world.roster.actor_ids)
        self.confirmed_tick = 0
        self.replayed_windows = 0
        self.kernel_digest = self.world._population_kernel_digest
        self._records: dict[str, dict] = {}
        self._last_event: AuthorityEvent | None = None
        self._prepared_event: tuple[str, AuthorityEvent] | None = None
        self._prepared_frame = None
        self._conflict_pump = conflict_pump
        self.last_conflict_error: str | None = None
        self.dispatcher = GameplayOutboxDispatcher(store=self.store, bus=self.bus, event_transform=self._hydrate,
            event_publisher=self._publish_prepared_population)
        self._restore()
        self._domain_source = OrganizationWindowDueSource(store=self.store, world_ref=self.world.mode.world_ref,
                                                         roster=self.world.roster)
        self._domain_dispatcher = GameplayOutboxDispatcher(store=self.store, bus=self.bus,
            event_transform=self._hydrate_domain, delivery_validator=self._validate_domain_delivery)

    def _admit_conflicts(self, cadence):
        if self._conflict_pump is None:
            return
        try:
            self._conflict_pump(cadence)
        except Exception as error:
            # 源仍持久待办，下一新窗口只补未接管角色；不因角色链故障停掉已确认 B0。
            self.last_conflict_error = type(error).__name__
        else:
            self.last_conflict_error = None

    def _prepare_domain(self, public: PopulationCadenceInput) -> AuthorityEvent | None:
        source = self._domain_source.read(window_end=public.window_end,
            observed_at=datetime.now(timezone.utc).isoformat(), scope="organization:summary")
        current = {projection.ref: projection for projection in source.projections}
        for actor, obligation, _ in self.world.select_due_population_work(public.window_end):
            if obligation.startswith("projection:organization-window-due:") and obligation not in current:
                self.world.complete_due_population_work(actor, obligation)
        for projection in source.projections:
            self.world.requeue_due_population_work(projection.payload["actor_ref"].removeprefix("character:"),
                projection.ref, projection.payload["due_tick"], revision=projection.payload["closed_event_revision"])
        if not current:
            return None
        vector = dict(public.base_revision_vector)
        for projection in source.projections:
            vector.update(projection.revision_vector)
        domain = public.model_copy(update=dict(cadence_id=public.cadence_id + ":organization-due",
            report_scope="organization:summary", base_revision_vector=vector))
        policy = PopulationSimulationCapability.default_decision_policy(domain)
        capabilities = PopulationSimulationCapability.default_capabilities(domain)
        planner = PopulationDecisionPlanner()
        candidates = planner.filter_registered(planner.evaluate(PopulationReadSet.from_inputs(domain, source.projections),
                                                                 capabilities, policy), capabilities)
        selected = planner.select(candidates, policy).selected_candidates
        if not selected:
            return None
        # 原始请求与公共 admission 同事务冻结；重试只投递这个事件，不以新 cadence 重签 CAS。
        requests = {}
        for candidate in selected:
            projection = current[candidate.source_projection_refs[0]]
            request = OperatingWindowDueRequest(command_id=candidate.candidate_ref, idempotency_key=candidate.idempotency_key,
                causation_id=domain.cadence_id, correlation_id=domain.cadence_id,
                organization_ref=projection.payload["organization_ref"], window_ref=projection.payload["window_ref"],
                expected_stream_revision=projection.revision_vector[projection.payload["stream_ref"]], visibility_scope="project")
            requests[projection.ref] = request.model_dump(mode="json")
        event = publish_authorized_population_cadence(cadence=domain, store=self.store, organization_projection={},
            population_projections=source.projections, event_bus=self.bus, publish_event=False, **self.location,
            causation_id=f"population-runtime:{public.cadence_id}", correlation_id=domain.cadence_id)
        if event is None:
            raise ValueError("population_domain_source_changed")
        event.routing.audience_mode = "targeted"
        event.routing.target_ids = ["siming"]
        event.payload.update(public_population_cadence=public.model_dump(mode="json"),
            population_owner_requests=requests,
            population_decision=dict(policy=policy.model_dump(mode="json"),
                capabilities=[item.model_dump(mode="json") for item in capabilities]))
        return event

    def _hydrate_domain(self, outgoing: AuthorityEvent) -> AuthorityEvent:
        record = outgoing.payload["committed_payload"]
        public = self._validate_record(record)
        if public.window_end > self.confirmed_tick or durable_population_receipt(self.world, public) is None:
            raise ValueError("population_domain_public_receipt_missing")
        event = AuthorityEvent.model_validate(record["domain_authority_event"])
        domain = PopulationCadenceInput.from_authority_event(event)
        if (event.payload.get("public_population_cadence") != public.model_dump(mode="json")
                or domain.cadence_id != public.cadence_id + ":organization-due"
                or domain.report_scope != "organization:summary"
                or (domain.world_ref, domain.window_start, domain.window_end) != (public.world_ref, public.window_start, public.window_end)):
            raise ValueError("population_domain_admission_invalid")
        return event

    def _validate_domain_delivery(self, event: AuthorityEvent) -> None:
        requests = event.payload.get("population_owner_requests")
        if not isinstance(requests, dict) or not requests:
            raise ValueError("population_domain_owner_requests_missing")
        authority = OrganizationAuthority(store=self.store)
        projections = {row["ref"]: row for row in event.payload["population_projections"]}
        completed = []
        for ref, raw in requests.items():
            request = OperatingWindowDueRequest.model_validate(raw)
            result = authority._operating_window_due_event_replay(request)
            if result is None or not result.committed:
                raise ValueError("population_domain_owner_receipt_missing")
            proof = self.store.get_event(result.committed_event_ids[0])
            if not self.store.transaction_owns_event(
                    transaction_id=proof.transaction_id,
                    event_id=proof.event_id,
                    principal_ref=authority._PRINCIPAL):
                raise ValueError("population_domain_owner_receipt_invalid")
            completed.append((projections[ref]["payload"]["actor_ref"].removeprefix("character:"), ref))
        for actor, ref in completed:
            self.world.complete_due_population_work(actor, ref)

    def _dispatch_domains(self) -> bool:
        pending = self.store.list_outbox(include_delivered=False, topic=self.DOMAIN_TOPIC, limit=1)
        if not pending:
            return True
        record = self.store.get_event(pending[0].event_id).payload
        public = self._validate_record(record)
        if public.window_end > self.confirmed_tick or durable_population_receipt(self.world, public) is None:
            return False
        result = self._domain_dispatcher.dispatch_pending(topic=self.DOMAIN_TOPIC, limit=1)
        delivered = result.published_count == 1 and not result.failed_count
        if delivered:
            transaction = self.store.get_transaction(pending[0].transaction_id)
            if transaction is not None and not transaction.projection_refresh_hints:
                # public 确认时 domain 尚未 delivered；此处补原无投影义务的终态。
                self.store.mark_projection_refreshed(transaction.transaction_id)
        return delivered

    def _remember_record(self, record: dict) -> None:
        self._records[record["cadence"]["cadence_id"]] = record
        while len(self._records) > 2:
            self._records.pop(next(iter(self._records)))

    def _record_for(self, cadence_id: str) -> dict | None:
        cached = self._records.get(cadence_id)
        if cached is not None:
            return cached
        result = self.store.get_by_idempotency("world_runtime.cadence", f"population-runtime:{cadence_id}")
        if result is None:
            return None
        record = self.store.get_event(result.committed_event_ids[0]).payload
        self._validate_record(record)
        self._remember_record(record)
        return record

    def _restore(self) -> None:
        checkpoints = []
        failure = None
        # 两个固定代次独立解码；坏容器不能阻止读取另一代，数据库读故障仍直接上抛。
        for slot in range(2):
            try:
                checkpoint = self.store.get_projection_checkpoint(f"population-recovery:{self.world.mode.world_ref}:{slot}")
            except GameplayEventStoreSnapshotError as error:
                if not isinstance(error.__cause__, ValidationError):
                    raise
                failure = error
                continue
            if checkpoint is not None:
                checkpoints.append(checkpoint)
        checkpoints.sort(key=lambda item: (item.last_global_sequence, item.checkpoint_id), reverse=True)
        revision = 0
        tail_limit = 16
        for index, checkpoint in enumerate(checkpoints):
            previous_cohort = self.world._character_cohort_ref
            try:
                data = parse_population_checkpoint(self.world, checkpoint)
                if data.recovery_state is None or durable_population_receipt(self.world, data.cadence) != data.receipt:
                    raise ValueError("population_recovery_checkpoint_receipt")
                if self.world._character_participation is not None:
                    state = data.recovery_state
                    if state.schema_version != 2:
                        raise ValueError("population_recovery_participation_mismatch")
                    candidate = state.cohort_ref
                    # checkpoint 只选择已提交的成员锚点，不授予新策略或新角色权限。
                    if simulation_digest(dict(cohort_ref=candidate, resolutions={actor: value.model_dump(mode="json")
                            for actor, value in self.world._character_participation.items()})) != state.participation_digest:
                        raise ValueError("population_recovery_participation_mismatch")
                    ancestor = candidate
                    while ancestor != previous_cohort:
                        roots = self.store.read_stream(self.world.member_ledger_stream(ancestor))
                        if len(roots) != 1:
                            raise ValueError("population_recovery_participation_mismatch")
                        root = parse_member_record(self.store, roots[0])
                        if not isinstance(root, MemberReentryRecord):
                            raise ValueError("population_recovery_participation_mismatch")
                        self.world.read_member_ledger(ancestor)
                        ancestor = root.source_cohort_ref
                    self.world.configure_character_participation(resolutions=self.world._character_participation,
                        activation_authority=self.world._character_activation_authority, cohort_ref=candidate)
                self.world.restore_recovery_state(data.recovery_state.model_dump(mode="json"))
            except GameplayEventStoreSnapshotError as error:
                if not isinstance(error.__cause__, ValidationError):
                    raise
                failure = error
                continue
            except (ValueError, KeyError) as error:
                if self.world._character_participation is not None:
                    self.world.configure_character_participation(resolutions=self.world._character_participation,
                        activation_authority=self.world._character_activation_authority, cohort_ref=previous_cohort)
                failure = error
                continue
            self.confirmed_tick = data.cadence.window_end
            revision = data.cadence_stream_revision
            tail_limit = 32 if index or failure is not None else 16
            break
        else:
            if checkpoints or failure is not None:
                raise ValueError("population_recovery_checkpoint_unavailable") from failure
        tail = self.store.read_stream(self.stream_id, from_revision=revision + 1, limit=tail_limit + 1)
        if len(tail) > tail_limit:
            raise ValueError("population_recovery_checkpoint_rebuild_required")
        expected_start = self.confirmed_tick
        pending = False
        for event in tail:
            record = event.payload
            cadence = self._validate_record(record)
            if cadence.window_start != expected_start or event.stream_revision != revision + 1:
                raise ValueError("population_cadence_history_gap")
            revision = event.stream_revision
            expected_start = cadence.window_end
            self._remember_record(record)
            outbox = self.store.get_outbox(f"outbox:population-runtime:{cadence.cadence_id}")
            if outbox.event_id != event.event_id:
                raise ValueError("population_cadence_outbox_anchor")
            if outbox.delivery_state != "delivered":
                pending = True
            elif pending:
                raise ValueError("population_cadence_delivery_gap")
            else:
                self._event_from_record(record)
                self._confirm(cadence, record)
                self.replayed_windows += 1
        # 完整检查点在 public 确认时保存；同窗域 Owner 可能随后才提交，按真实 receipt 收敛派生待办。
        latest = self.world.latest_confirmation
        if latest is not None:
            record = self._record_for(latest.cadence_id)
            if record is not None:
                domain_id = record.get("domain_admission_cadence_id")
                if domain_id is None and "domain_authority_event" in record:
                    domain_id = latest.cadence_id
                if domain_id is not None:
                    original = self._record_for(domain_id)
                    if (original is None or "domain_authority_event" not in original
                            or self._validate_record(original).window_end > latest.window_end):
                        raise ValueError("population_domain_admission_anchor_invalid")
                    domain_outbox = self.store.get_outbox(f"outbox:population-runtime:{domain_id}:organization-due")
                    admission = self.store.get_by_idempotency("world_runtime.cadence", f"population-runtime:{domain_id}")
                    if domain_outbox.event_id not in admission.committed_event_ids:
                        raise ValueError("population_domain_admission_anchor_invalid")
                    if domain_outbox.delivery_state == "delivered":
                        self._validate_domain_delivery(AuthorityEvent.model_validate(original["domain_authority_event"]))

    def _confirm(self, cadence: PopulationCadenceInput, record: dict) -> None:
        old_receipt = durable_population_receipt(self.world, cadence)
        if "domain_due_entries" in record:
            for actor, obligation, _, _ in self.world._population_due_index.export_entries():
                if obligation.startswith("projection:organization-window-due:"):
                    self.world.complete_due_population_work(actor, obligation)
            for actor, obligation, due_tick, revision in record["domain_due_entries"]:
                if actor not in self.world.roster.actor_ids or not obligation.startswith("projection:organization-window-due:"):
                    raise ValueError("population_domain_due_entry_invalid")
                self.world.requeue_due_population_work(actor, obligation, due_tick, revision=revision)
        receipt = replace(self.world.confirm_population_cadence(cadence), status="committed")
        if old_receipt is not None and old_receipt != receipt:
            raise ValueError("population_recovery_checkpoint_receipt_mismatch")
        result = self.store.get_by_idempotency("world_runtime.cadence", f"population-runtime:{cadence.cadence_id}")
        event = self.store.get_event(result.committed_event_ids[0])
        values = dict(schema_version=1, canonical_version=1, context_digest=self.world._recovery_context_digest(),
                      kernel_digest=self.kernel_digest, cadence=cadence.model_dump(mode="python"), event_id=event.event_id,
                      cadence_stream_revision=event.stream_revision, global_sequence=event.global_sequence,
                      record_digest=record["record_digest"], receipt=receipt, fingerprint=self.world._cadence_fingerprint(cadence),
                      recovery_state=None)

        def checkpoint(*, full: bool) -> ProjectionCheckpoint:
            state = {**values, "recovery_state": self.world._build_recovery_state_payload() if full else None}
            if full:
                state.update(cadence=cadence.model_dump(mode="json"), receipt=asdict(receipt))
                parsed = PopulationRecoveryCheckpoint.model_validate_json(json.dumps(state))
            else:
                # 新回执直接严格校验；完整恢复与持久数据读取保留原 JSON 校验。
                parsed = _ReceiptCheckpoint.model_validate(state)
            projector = ("population-recovery:" if full else "population-receipt:") + self.world.mode.world_ref
            identity = f"{projector}:{(event.stream_revision // 16) % 2}" if full else f"{projector}:{cadence.cadence_id}"
            container = ProjectionCheckpoint(checkpoint_id=identity, projector_id=projector, projector_version="1",
                projection_schema_version=1, source_revision_vector={self.stream_id: event.stream_revision},
                last_global_sequence=event.global_sequence, applied_event_ids=[event.event_id],
                state=parsed.model_dump(mode="json"), projection_hash="pending")
            return container.model_copy(update={"projection_hash": recovery_digest(container.model_dump(mode="json", exclude={"projection_hash"}))})

        checkpoints = [checkpoint(full=False)]
        if event.stream_revision % 16 == 0 or self.world._character_participation is not None:
            checkpoints.append(checkpoint(full=True))
        self.store.save_projection_checkpoints_atomic(checkpoints)
        # 本事务没有其他投影订阅时，热表与检查点就是它的刷新工作，不能积压到下次全局启动。
        transaction = self.store.get_transaction(event.transaction_id)
        if transaction is not None and not transaction.projection_refresh_hints:
            self.store.mark_projection_refreshed(event.transaction_id)
        self.confirmed_tick = cadence.window_end

    def replace_character_participation(self, *, resolutions, cohort_ref, continuity_runtime) -> None:
        """新成员 Owner 锚点到位后刷新同一确认窗的恢复投影，不推进时钟。"""
        previous_cohort = self.world._character_cohort_ref
        latest = self.world.latest_confirmation
        if previous_cohort is None or latest is None or cohort_ref == previous_cohort:
            raise ValueError("character_readmission_context_invalid")
        if self.store.list_outbox(include_delivered=False, topic="population_cadence_event", limit=1):
            raise ValueError("character_readmission_pending_window")
        record = self._record_for(latest.cadence_id)
        cadence = self._validate_record(record)
        if durable_population_receipt(self.world, cadence) != latest:
            raise ValueError("character_readmission_confirmation_missing")
        old = self.world.read_member_ledger(previous_cohort)
        new = self.world.read_member_ledger(cohort_ref)
        updates = []
        for entry in new.member_entries:
            actor_id = entry.actor_ref.removeprefix("character:")
            prior = next(item for item in old.member_entries if item.actor_ref == entry.actor_ref)
            returning = prior.lifecycle == "handoff" and entry.lifecycle == "active"
            if (dict(entry.participation_policy_pins) != dict(resolutions[entry.actor_ref].source_policy_pins)
                    or (returning and entry.entry_character_revision != continuity_runtime.get_continuity_revision(actor_id))
                    or (not returning and entry != prior)):
                raise ValueError("character_readmission_anchor_stale")
            if returning:
                resolution = resolutions[entry.actor_ref]
                if (self.world._character_activation_authority.active_lock(
                        world_ref=self.world.mode.world_ref, profile_ref=entry.actor_ref) is not None
                        or resolution.status != "resolved" or "B0" not in resolution.allowed_tiers
                        or self.confirmed_tick >= min(resolution.b0_expiry_tick, resolution.review_tick)
                        or continuity_runtime.get_character_simulation_cursor(actor_id) != self.confirmed_tick
                        or any(result.actor_ref == entry.actor_ref and result.consumed_core_receipt_ref is None
                            for result in old.confirmed_results)):
                    raise ValueError("character_readmission_pending_personal_work")
                # 只允许当前自身确认态；不把群体统计分配给个体。
                row = self.world.population_hot_state.read(actor_id)
                projection = continuity_runtime.get_seed_projection(actor_id).get("state_deltas", {})
                if (row["last_update_tick"] > self.confirmed_tick or any(
                        type(projection.get(field)) not in {int, float} or not 0 <= projection[field] <= 1
                        for field in ("fatigue", "need_pressure"))):
                    raise ValueError("character_readmission_personal_state_unsynchronized")
                values = dict(row)
                if row["last_update_tick"] < self.confirmed_tick:
                    values.update(advance_b0_row(actor_id=actor_id, row=row,
                        window_start=row["last_update_tick"], window_end=self.confirmed_tick).values)
                # 只同步该角色自身的已确认 needs，其他热字段沿用原客观推进规则。
                values.update({field: projection[field] for field in ("fatigue", "need_pressure")})
                values.pop("revision")
                updates.append((actor_id, values, row["revision"], row["revision"] + 1))
        previous = self.world._character_participation
        previous_state = self.world.export_recovery_state()
        try:
            self.world.population_hot_state.commit_batch_atomic(updates)
            for actor_id, values, _, revision in updates:
                self.world.requeue_due_population_work(actor_id, "b0:presentation-threshold",
                    values["next_due_tick"], revision=revision)
            self.world.configure_character_participation(resolutions=resolutions,
                activation_authority=self.world._character_activation_authority, cohort_ref=cohort_ref)
            event = self.store.get_event(self.store.get_by_idempotency("world_runtime.cadence",
                f"population-runtime:{cadence.cadence_id}").committed_event_ids[0])
            identity = f"population-recovery:{self.world.mode.world_ref}:{(event.stream_revision // 16) % 2}"
            checkpoint = self.store.get_projection_checkpoint(identity)
            if checkpoint is None:
                raise ValueError("character_readmission_checkpoint_missing")
            data = parse_population_checkpoint(self.world, checkpoint)
            state = {**data.model_dump(mode="json"), "recovery_state": self.world._build_recovery_state_payload()}
            updated = checkpoint.model_copy(update={"state": PopulationRecoveryCheckpoint.model_validate_json(
                json.dumps(state)).model_dump(mode="json")})
            updated = updated.model_copy(update={"projection_hash": recovery_digest(
                updated.model_dump(mode="json", exclude={"projection_hash"}))})
            self.store.save_projection_checkpoints_atomic([updated])
        except Exception:
            self.world.configure_character_participation(resolutions=previous,
                activation_authority=self.world._character_activation_authority, cohort_ref=previous_cohort)
            self.world.restore_recovery_state(previous_state)
            raise

    def _validate_record(self, record: dict) -> PopulationCadenceInput:
        if record.get("roster_digest") != self.roster_digest:
            raise ValueError("population_roster_mismatch")
        cadence = PopulationCadenceInput.model_validate(record.get("cadence"))
        if (record.get("schema_version") != 1 or cadence.world_ref != self.world.mode.world_ref
                or cadence.world_mode_revision != self.world.mode.revision):
            raise ValueError("population_cadence_context_mismatch")
        if record.get("record_digest") != _digest({key: value for key, value in record.items() if key != "record_digest"}):
            raise ValueError("population_cadence_record_corrupt")
        return cadence

    def _hydrate(self, outgoing: AuthorityEvent) -> AuthorityEvent:
        record = outgoing.payload["committed_payload"]
        cadence = self._validate_record(record)
        if cadence.window_start != self.confirmed_tick:
            raise ValueError("population_cadence_delivery_gap")
        if self._prepared_event is not None and self._prepared_event[0] == record["record_digest"]:
            # 首发复用刚通过授权且摘要已提交的事件；重试/重开仍完整重建校验。
            event = self._prepared_event[1]
        else:
            _cadence, event = self._event_from_record(record)
        self._last_event = event
        return event

    def _publish_prepared_population(self, event: AuthorityEvent) -> None:
        prepared = self._prepared_event
        dispatcher = self.dispatcher
        callbacks = getattr(dispatcher, "_delivery_callbacks", None)
        store_bindings = _NATIVE_DELIVERY_STORE_BINDINGS.get(type(self.store), ())
        if (self._prepared_frame is not None and prepared is not None and prepared[1] is event
                and type(self) is RuntimeCadencePublisher and type(self.bus) is InMemoryAuthorityEventBus
                and native_method(self, "__call__", _NATIVE_PUBLISHER_CALL)
                and native_method(self, "_hydrate", _NATIVE_HYDRATE)
                and native_method(self, "_validate_record", _NATIVE_VALIDATE_RECORD)
                and type(dispatcher) is GameplayOutboxDispatcher
                and native_method(dispatcher, "dispatch_pending", _NATIVE_DISPATCH)
                and dispatcher._authority_event_for is _NATIVE_OUTGOING_EVENT
                and type(dispatcher._event_publisher) is MethodType
                and dispatcher._event_publisher.__self__ is self
                and dispatcher._event_publisher.__func__ is _NATIVE_PREPARED_SENDER
                and type(dispatcher._event_transform) is MethodType
                and dispatcher._event_transform.__self__ is self
                and dispatcher._event_transform.__func__ is _NATIVE_HYDRATE
                and callbacks is not None
                and type(callbacks[0]) is MethodType and callbacks[0].__self__ is self
                and callbacks[0].__func__ is _NATIVE_HYDRATE
                and type(callbacks[1]) is MethodType and callbacks[1].__self__ is self
                and callbacks[1].__func__ is _NATIVE_PREPARED_SENDER
                and store_bindings and all(native_method(self.store, name, function) for name, function in store_bindings)
                and native_method(self.bus, "_publish_prepared_population", _NATIVE_BUS_PREPARED)):
            return self.bus._publish_prepared_population(event, self._prepared_frame)
        return self.bus.publish(event)

    def _event_from_record(self, record: dict) -> tuple[PopulationCadenceInput, AuthorityEvent]:
        """重建 compact record 的完整事件，并在任何热表确认前校验规则输出。"""
        cadence = self._validate_record(record)
        if cadence.window_start != self.confirmed_tick:
            raise ValueError("population_cadence_delivery_gap")
        # 常驻 B0 由已确认前缀和固定规则重建；只存稀疏领域投影，不落万人数组。
        template = record["authority_event"]
        projections = list(template["payload"]["population_projections"])
        projections.extend(dump_population_projections(self.world.build_population_projections(cadence)))
        projections.sort(key=lambda item: item["ref"])
        if _digest(projections) != record["projection_digest"]:
            raise ValueError("population_cadence_projection_mismatch")
        event = AuthorityEvent.model_validate({**template, "payload": {**template["payload"], "population_projections": projections}})
        return cadence, event

    def __call__(self, cadence: PopulationCadenceInput, *, population_projections=()) -> AuthorityEvent | None:
        existing = self._record_for(cadence.cadence_id)
        if existing is not None:
            committed = self._validate_record(existing)
            # 重试消费已确认输入，不用此刻的新 source revision 改写原窗口。
            keys = (
                "world_ref",
                "world_mode_ref",
                "world_mode_revision",
                "cadence_source_ref",
                "window_start",
                "window_end",
                "policy_revision",
                "selector_revision",
                "ruleset_revision",
                "deterministic_seed",
                "catch_up_limit",
                "budget",
                "report_scope",
            )
            if any(getattr(committed, key) != getattr(cadence, key) for key in keys):
                raise ValueError("population_cadence_confirmation_conflict")
            if committed.window_end <= self.confirmed_tick:
                if durable_population_receipt(self.world, committed) is None:
                    raise ValueError("population_recovery_checkpoint_receipt_missing")
                return AuthorityEvent.model_validate(existing["authority_event"])
            domain_ready = self._dispatch_domains()
            cadence = committed
            # outbox 确认后热表重建仍可能失败；重试只补派生表，不重复投递。
            outbox_id = f"outbox:population-runtime:{cadence.cadence_id}"
            if self.store.get_outbox(outbox_id).delivery_state == "delivered":
                latest = self.world.latest_confirmation
                if latest is not None and latest.cadence_id == cadence.cadence_id:
                    event = AuthorityEvent.model_validate(existing["authority_event"])
                else:
                    _committed, event = self._event_from_record(existing)
                self._confirm(cadence, existing)
                self._dispatch_domains()
                self._admit_conflicts(cadence)
                return event
        else:
            if cadence.window_start != self.confirmed_tick:
                raise ValueError("population_cadence_history_gap")
            domain_ready = self._dispatch_domains()
            with capture_publication() as capture:
                prepared = publish_authorized_population_cadence(
                    cadence=cadence, store=self.store, organization_projection={},
                    population_projections=(*self.world.build_population_projections(cadence), *population_projections),
                    event_bus=self.bus, publish_event=False, **self.location,
                    causation_id=f"population-runtime:{cadence.cadence_id}",
                    correlation_id=f"population-runtime:{cadence.cadence_id}",
                )
            if prepared is None:
                return None
            if population_projections:
                # 稀疏个人输入只在原后端总线投递给 Siming，不广播个人上下文。
                prepared.routing.audience_mode = "targeted"
                prepared.routing.target_ids = ["siming"]
            all_projections = prepared.payload["population_projections"]
            template = prepared.model_dump(mode="json", exclude={"payload": {"population_projections"}})
            if publish_authorized_population_cadence is _NATIVE_PUBLICATION and _digest is _NATIVE_DIGEST:
                projection_digest, prepared_frame = encode_captured_projections(prepared, capture)
            else:
                projection_digest, prepared_frame = _digest(all_projections), None
            template["payload"]["population_projections"] = [
                item for item in all_projections if item["payload"].get("fidelity_tier") != "B0"
            ]
            record = dict(schema_version=1, cadence=cadence.model_dump(mode="json"), roster_digest=self.roster_digest,
                          projection_digest=projection_digest, authority_event=template)
            domain = self._prepare_domain(cadence) if domain_ready else None
            if domain is not None:
                record["domain_authority_event"] = domain.model_dump(mode="json")
                record["domain_admission_cadence_id"] = cadence.cadence_id
            elif not domain_ready:
                # 最多一个未交付域；后窗冻结其原 admission 关联，跨检查点仍可点读真实完成证据。
                pending = self.store.list_outbox(include_delivered=False, topic=self.DOMAIN_TOPIC, limit=1)
                if pending:
                    original = self.store.get_event(pending[0].event_id).payload
                    record["domain_admission_cadence_id"] = self._validate_record(original).cadence_id
            record["domain_due_entries"] = [list(row) for row in self.world._population_due_index.export_entries()
                                             if row[1].startswith("projection:organization-window-due:")]
            record["record_digest"] = _digest(record)
            command = f"population-runtime:{cadence.cadence_id}"
            batch = build_atomic_event_batch(
                command_id=command, principal_ref="world_runtime.cadence", stream_id=self.stream_id,
                expected_revision=self.store.get_stream_head(self.stream_id),
                event_specs=[("population.cadence.admitted", record)], idempotency_key=command,
                causation_id=command, correlation_id=command,
                read_stream_revisions=(PopulationCadenceInput.from_authority_event(domain).base_revision_vector
                                       if domain is not None else cadence.base_revision_vector),
            )
            batch.outbox_entries.append(GameplayOutboxEntry(
                outbox_id=f"outbox:{command}", transaction_id=batch.transaction_id,
                event_id=batch.events[0].event_id, global_sequence=0,
                topic="population_cadence_event", audience="siming" if population_projections else "broadcast",
                payload_projection={"projection_kind": "population-runtime"},
            ))
            if domain is not None:
                batch.outbox_entries.append(GameplayOutboxEntry(outbox_id=f"outbox:{command}:organization-due",
                    transaction_id=batch.transaction_id, event_id=batch.events[0].event_id, global_sequence=0,
                    topic=self.DOMAIN_TOPIC, audience="targeted", payload_projection={"projection_kind": "population-runtime"}))
            result = self.store.append_batch(batch)
            if not result.committed:
                return None
            self._remember_record(record)
            self._prepared_event = (record["record_digest"], prepared)
            self._prepared_frame = prepared_frame
        self._last_event = None
        try:
            result = self.dispatcher.dispatch_pending(topic="population_cadence_event", limit=1)
        finally:
            self._prepared_event = None
            self._prepared_frame = None
            published_event = self._last_event
            self._last_event = None
        if result.failed_count or result.published_count != 1:
            return None
        self._confirm(cadence, self._record_for(cadence.cadence_id))
        if domain_ready:
            self._dispatch_domains()
        self._admit_conflicts(cadence)
        return published_event


_NATIVE_PUBLICATION = publish_authorized_population_cadence
_NATIVE_DIGEST = _digest
_NATIVE_PUBLISHER_CALL = RuntimeCadencePublisher.__call__
_NATIVE_HYDRATE = RuntimeCadencePublisher._hydrate
_NATIVE_VALIDATE_RECORD = RuntimeCadencePublisher._validate_record
_NATIVE_DISPATCH = GameplayOutboxDispatcher.dispatch_pending
_NATIVE_OUTGOING_EVENT = GameplayOutboxDispatcher._authority_event_for
_NATIVE_PREPARED_SENDER = RuntimeCadencePublisher._publish_prepared_population
_NATIVE_BUS_PREPARED = InMemoryAuthorityEventBus._publish_prepared_population
_NATIVE_DELIVERY_STORE_BINDINGS = {kind: tuple((name, getattr(kind, name))
    for name in ("get_last_global_sequence", "list_outbox", "get_event"))
    for kind in (GameplayEventStore, DurableGameplayEventStore)}
