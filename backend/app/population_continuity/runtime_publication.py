from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
from datetime import datetime, timezone

from pydantic import ValidationError

from app.gameplay.dispatcher import GameplayOutboxDispatcher
from app.gameplay.event_store import GameplayEventStoreSnapshotError
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
from app.services.siming_population_capability import PopulationSimulationCapability


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


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
        self._conflict_pump = conflict_pump
        self.last_conflict_error: str | None = None
        self.dispatcher = GameplayOutboxDispatcher(store=self.store, bus=self.bus, event_transform=self._hydrate)
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
            try:
                data = parse_population_checkpoint(self.world, checkpoint)
                if data.recovery_state is None or durable_population_receipt(self.world, data.cadence) != data.receipt:
                    raise ValueError("population_recovery_checkpoint_receipt")
                self.world.restore_recovery_state(data.recovery_state.model_dump(mode="json"))
            except GameplayEventStoreSnapshotError as error:
                if not isinstance(error.__cause__, ValidationError):
                    raise
                failure = error
                continue
            except (ValueError, KeyError) as error:
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
                      kernel_digest=self.kernel_digest, cadence=cadence.model_dump(mode="json"), event_id=event.event_id,
                      cadence_stream_revision=event.stream_revision, global_sequence=event.global_sequence,
                      record_digest=record["record_digest"], receipt=asdict(receipt), fingerprint=self.world._cadence_fingerprint(cadence),
                      recovery_state=None)

        def checkpoint(*, full: bool) -> ProjectionCheckpoint:
            state = {**values, "recovery_state": self.world._build_recovery_state_payload() if full else None}
            parsed = PopulationRecoveryCheckpoint.model_validate_json(json.dumps(state))
            projector = ("population-recovery:" if full else "population-receipt:") + self.world.mode.world_ref
            identity = f"{projector}:{(event.stream_revision // 16) % 2}" if full else f"{projector}:{cadence.cadence_id}"
            container = ProjectionCheckpoint(checkpoint_id=identity, projector_id=projector, projector_version="1",
                projection_schema_version=1, source_revision_vector={self.stream_id: event.stream_revision},
                last_global_sequence=event.global_sequence, applied_event_ids=[event.event_id],
                state=parsed.model_dump(mode="json"), projection_hash="pending")
            return container.model_copy(update={"projection_hash": recovery_digest(container.model_dump(mode="json", exclude={"projection_hash"}))})

        checkpoints = [checkpoint(full=False)]
        if event.stream_revision % 16 == 0:
            checkpoints.append(checkpoint(full=True))
        self.store.save_projection_checkpoints_atomic(checkpoints)
        # 本事务没有其他投影订阅时，热表与检查点就是它的刷新工作，不能积压到下次全局启动。
        transaction = self.store.get_transaction(event.transaction_id)
        if transaction is not None and not transaction.projection_refresh_hints:
            self.store.mark_projection_refreshed(event.transaction_id)
        self.confirmed_tick = cadence.window_end

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

    def __call__(self, cadence: PopulationCadenceInput) -> AuthorityEvent | None:
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
            prepared = publish_authorized_population_cadence(
                cadence=cadence, store=self.store, organization_projection={},
                population_projections=self.world.build_population_projections(cadence),
                event_bus=self.bus, publish_event=False, **self.location,
                causation_id=f"population-runtime:{cadence.cadence_id}",
                correlation_id=f"population-runtime:{cadence.cadence_id}",
            )
            if prepared is None:
                return None
            all_projections = prepared.payload["population_projections"]
            template = prepared.model_dump(mode="json", exclude={"payload": {"population_projections"}})
            projection_digest = _digest(all_projections)
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
                topic="population_cadence_event", audience="broadcast",
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
        self._last_event = None
        try:
            result = self.dispatcher.dispatch_pending(topic="population_cadence_event", limit=1)
        finally:
            self._prepared_event = None
            published_event = self._last_event
            self._last_event = None
        if result.failed_count or result.published_count != 1:
            return None
        self._confirm(cadence, self._record_for(cadence.cadence_id))
        if domain_ready:
            self._dispatch_domains()
        self._admit_conflicts(cadence)
        return published_event
