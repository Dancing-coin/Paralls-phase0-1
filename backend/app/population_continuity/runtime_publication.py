from __future__ import annotations

import hashlib
import json

from app.gameplay.dispatcher import GameplayOutboxDispatcher
from app.gameplay.models import GameplayOutboxEntry
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.models.authority_event import AuthorityEvent
from app.population_continuity.publication import publish_authorized_population_cadence
from app.population_continuity.siming_contracts import PopulationCadenceInput, dump_population_projections
from app.population_continuity.world import WorldContinuityRuntime
from app.services.authority_event_bus import AuthorityEventBusPort


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class RuntimeCadencePublisher:
    """既有 Gameplay 日志确认窗口，outbox 重试投递；热表仅为可重建投影。"""

    def __init__(self, *, world_runtime: WorldContinuityRuntime, event_bus: AuthorityEventBusPort,
                 room_id: str, scene_id: str, zone_id: str) -> None:
        self.world = world_runtime
        self.store = world_runtime.store
        self.bus = event_bus
        self.location = dict(room_id=room_id, scene_id=scene_id, zone_id=zone_id)
        self.stream_id = f"population-cadence:{self.world.mode.world_ref}"
        self.roster_digest = _digest(self.world.roster.actor_ids)
        self.confirmed_tick = 0
        self._records: dict[str, dict] = {}
        self._last_event: AuthorityEvent | None = None
        self._prepared_event: tuple[str, AuthorityEvent] | None = None
        self.dispatcher = GameplayOutboxDispatcher(store=self.store, bus=self.bus, event_transform=self._hydrate)
        delivered = {entry.event_id for entry in self.store.list_outbox() if entry.delivery_state == "delivered"}
        expected_start = 0
        pending = False
        for event in self.store.read_stream(self.stream_id):
            record = event.payload
            cadence = self._validate_record(record)
            if cadence.window_start != expected_start:
                raise ValueError("population_cadence_history_gap")
            expected_start = cadence.window_end
            self._records[cadence.cadence_id] = record
            if event.event_id not in delivered:
                pending = True
            elif pending:
                raise ValueError("population_cadence_delivery_gap")
            else:
                self._event_from_record(record)
                self.world.confirm_population_cadence(cadence)
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
        existing = self._records.get(cadence.cadence_id)
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
                return AuthorityEvent.model_validate(existing["authority_event"])
            cadence = committed
            # outbox 确认后热表重建仍可能失败；重试只补派生表，不重复投递。
            outbox_id = f"outbox:population-runtime:{cadence.cadence_id}"
            if self.store.get_outbox(outbox_id).delivery_state == "delivered":
                _committed, event = self._event_from_record(existing)
                self.world.confirm_population_cadence(cadence)
                self.confirmed_tick = cadence.window_end
                return event
        else:
            if cadence.window_start != self.confirmed_tick:
                raise ValueError("population_cadence_history_gap")
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
            record["record_digest"] = _digest(record)
            command = f"population-runtime:{cadence.cadence_id}"
            batch = build_atomic_event_batch(
                command_id=command, principal_ref="world_runtime.cadence", stream_id=self.stream_id,
                expected_revision=self.store.get_stream_head(self.stream_id),
                event_specs=[("population.cadence.admitted", record)], idempotency_key=command,
                causation_id=command, correlation_id=command, read_stream_revisions=cadence.base_revision_vector,
            )
            batch.outbox_entries.append(GameplayOutboxEntry(
                outbox_id=f"outbox:{command}", transaction_id=batch.transaction_id,
                event_id=batch.events[0].event_id, global_sequence=0,
                topic="population_cadence_event", audience="broadcast",
                payload_projection={"projection_kind": "population-runtime"},
            ))
            result = self.store.append_batch(batch)
            if not result.committed:
                return None
            self._records[cadence.cadence_id] = record
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
        self.world.confirm_population_cadence(cadence)
        self.confirmed_tick = cadence.window_end
        return published_event
