"""Thin Status assembly at an explicitly admitted existing caller boundary."""
from __future__ import annotations

from fractions import Fraction
from typing import Mapping

from pydantic import ConfigDict, Field

from app.gameplay.models import StrictGameplayModel
from app.gameplay.status_tags import StatusTagAuthorityService, StatusTagTemporalContext
from app.world_runtime.scheduling import select_temporal_work
from app.world_runtime.temporal_contracts import SimulationTime, verify_temporal_authorization


class StatusTimeBinding(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    world_ref: str = Field(min_length=1)
    timeline_id: str = Field(min_length=1)
    profile_revision: str = Field(min_length=1)
    mapping_id: str = Field(min_length=1)
    mapping_revision: str = Field(min_length=1)
    source_clock_ref: str = Field(min_length=1)
    source_unit_ref: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    canonical_unit_ref: str = Field(min_length=1)
    step_duration: str = Field(min_length=1)
    window_ticks: int = Field(gt=0)


class StatusTemporalConsumer:
    def __init__(self, *, service: StatusTagAuthorityService, bindings: Mapping[str, StatusTimeBinding | None]):
        self.service = service
        self.bindings = dict(bindings)
        self.closed = False
        self.last_results = ()
        self.last_errors = ()
        # Replay admission happens during application assembly, before serving requests.
        self.pending_work()

    def close(self):
        self.closed = True
        self.service = None
        self.bindings.clear()

    def _check_open(self):
        if self.closed:
            raise RuntimeError("status_consumer_closed")

    def pending_work(self):
        self._check_open()
        work = []
        for actor in self.bindings:
            projection = self.service.projector.rebuild(actor, self.service._store.read_stream(f"gameplay:status_tags:{actor}"))
            work.extend(self.service.expiration_works(projection))
        return tuple(work)

    def context(self, driver, actor, *, require_grant=False):
        self._check_open()
        binding = self.bindings.get(actor)
        if binding is None:
            raise ValueError("status_time_binding_missing")
        pins = driver._time_pins(driver.current_tick)
        expected = dict(pins, world_ref=driver.world_runtime.mode.world_ref)
        if any(expected.get(key) != value for key, value in binding.model_dump().items()):
            raise ValueError("status_time_binding_mismatch")
        if require_grant and getattr(driver, "require_temporal_authorization", False):
            durable_pins = getattr(getattr(driver, "publish_window", None), "confirmed_time_pins", None)
            if callable(durable_pins):
                durable_pins = durable_pins()
            if not isinstance(durable_pins, dict) or not verify_temporal_authorization(
                pins=durable_pins, expected_participant="actor_gameplay.status_domain",
                expected_cutoff=driver.current_tick,
                expected_timeline=driver.clock.timeline.timeline_id,
                grant_key="status",
            ):
                raise ValueError("status_temporal_authorization_rejected")
            pins = durable_pins
        return StatusTagTemporalContext(
            now=SimulationTime(binding.timeline_id, driver.clock.tick, Fraction(driver.current_tick)),
            mapping=driver.mapping, profile_revision=binding.profile_revision,
            source_revision=binding.source_revision, evidence_freshness=0,
            step_duration=driver.clock.temporal_profile.step_duration,
        )

    def admit_driver(self, driver):
        self._check_open()
        for actor, binding in self.bindings.items():
            projection = self.service.projector.rebuild(actor, self.service._store.read_stream(f"gameplay:status_tags:{actor}"))
            if binding is None:
                if projection.active_instances:
                    raise ValueError("status_time_binding_missing")
                continue
            pins = driver._time_pins(driver.current_tick)
            expected = dict(pins, world_ref=driver.world_runtime.mode.world_ref)
            if any(expected.get(key) != value for key, value in binding.model_dump().items()):
                raise ValueError("status_time_binding_mismatch")
            context = None
            for instance in projection.active_instances.values():
                if instance.expiry is not None:
                    if context is None:
                        context = self.context(driver, actor)
                    context.validate_reference(instance.expiry)

    def advance(self, driver):
        """Reconstruct work from committed state; only an owner receipt removes it."""
        self._check_open()
        if driver.world_runtime.is_paused():
            return
        results, errors = [], []
        budget = driver.catch_up_limit
        # One work per fresh owner read. Earlier commits may change the same actor's revision.
        for actor, binding in self.bindings.items():
            if binding is None:
                continue
            try:
                temporal = self.context(driver, actor, require_grant=True)
                while budget > 0:
                    projection = self.service.projector.rebuild(actor, self.service._store.read_stream(f"gameplay:status_tags:{actor}"))
                    work = self.service.expiration_works(projection)
                    selected, _ = select_temporal_work(work, now=temporal.now, budget=1)
                    if not selected:
                        break
                    budget -= 1
                    result = self.service.submit_expiration_request(selected[0], temporal=temporal)
                    results.append(result)
                    if not result.accepted or result.append_result is None or not result.append_result.committed:
                        errors.append((selected[0].work_ref, result.reason_code))
                        break
            except Exception as exc:
                errors.append((actor, f"{type(exc).__name__}:{exc}"))
        self.last_results, self.last_errors = tuple(results), tuple(errors)
