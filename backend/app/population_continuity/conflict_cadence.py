"""每个新确认窗口按预算把真实冲突交给 Character；复用源与子入站的持久恢复。"""
from dataclasses import asdict
import json
import math
import time

from app.population_continuity.conflict_activation import prepare_conflict_activation
from app.population_continuity.recovery import durable_population_receipt
from app.population_continuity.siming_contracts import PopulationCadenceInput


class PopulationConflictPump:
    def __init__(self, *, source, store, world, admissions, ttl_seconds, wall_clock=time.time):
        if isinstance(ttl_seconds, bool) or not math.isfinite(ttl_seconds) or ttl_seconds <= 0:
            raise ValueError("conflict_cognition_ttl_invalid")
        self.source, self.store, self.world, self.admissions = source, store, world, admissions
        self.ttl_seconds, self.wall_clock = ttl_seconds, wall_clock

    def validate_admission(self, entry):
        """原入站与后续 prepare 共用来源校验；过时来源不能开始私有认知。"""
        cadence = PopulationCadenceInput.model_validate(entry.source_pins.get("population_cadence"))
        if (entry.source_kind != "run_background_cognition_tick" or entry.payload or entry.parent_effect_key
                or entry.producer_ts != cadence.window_end
                or cadence.world_ref != self.world.mode.world_ref
                or cadence.world_mode_revision != self.world.mode.revision
                or cadence.report_scope != "public" or durable_population_receipt(self.world, cadence) is None):
            raise ValueError("conflict_cognition_cadence_invalid")
        event = self.store.get_event(entry.source_event["event_id"])
        if event.model_dump(mode="json") != entry.source_event:
            raise ValueError("conflict_cognition_source_invalid")
        wake = prepare_conflict_activation(store=self.store, package_registry=self.source._packages,
            profiles=self.source._profiles, policy=self.source._policy,
            source_event_id=event.event_id, actor_id=entry.actor_id, budget=4)
        if (entry.actor_id not in self.world.roster.actor_ids or entry.delivery_id != wake.candidate_key
                or entry.source_pins.get("population_wake") != json.loads(json.dumps(asdict(wake)))):
            raise ValueError("conflict_cognition_wake_invalid")

    def __call__(self, cadence):
        if durable_population_receipt(self.world, cadence) is None:
            raise ValueError("conflict_cognition_public_unconfirmed")
        budget = min(4, self.world.mode.wake_budget)
        if budget <= 0:
            return ()
        admitted, actors = [], set()
        for wake in self.source.read().wakes:
            if wake.actor_id in actors:
                continue
            now = self.wall_clock()
            entry = self.admissions.admit(source_event=self.store.get_event(wake.source_event_id),
                actor_id=wake.actor_id, delivery_id=wake.candidate_key, source_kind=wake.source_kind, payload={},
                source_pins={"population_wake": json.loads(json.dumps(asdict(wake))),
                             "population_cadence": cadence.model_dump(mode="json")},
                now=now, expires_at=now + self.ttl_seconds, producer_ts=cadence.window_end)
            admitted.append(entry)
            actors.add(wake.actor_id)
            if len(actors) >= budget:
                break
        # 不抢 activation lease；admitted 仅代表 durable 接管，执行由 Character 的原队列完成。
        return tuple(admitted)
