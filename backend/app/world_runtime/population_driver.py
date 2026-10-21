from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from fractions import Fraction
from typing import Awaitable, Callable
from time import monotonic
from math import floor, isfinite

from app.models.authority_event import AuthorityEvent
from app.services.runtime_execution import RuntimeExecution
from app.population_continuity.siming_contracts import PopulationCadenceInput
from app.population_continuity.world import WorldContinuityRuntime

from .simulation_clock import SimulationClock, calculate_window_bounds
from .temporal_contracts import (ClockMapping, ScheduledWork, SimulationTime, SimulationTimeline,
                                  TemporalAuthorization, TemporalProfile)
from .scheduling import select_temporal_work


@dataclass(frozen=True)
class PopulationDriverTickResult:
    published_cadence_ids: tuple[str, ...] = ()
    deferred_windows: tuple[str, ...] = ()
    rejected_windows: tuple[tuple[str, str], ...] = ()
    b0_advanced_count: int = 0
    due_item_count: int = 0
    deferred_item_count: int = 0
    rejected_item_count: int = 0


class PopulationCadenceDriver:
    def __init__(
        self,
        *,
        world_runtime: WorldContinuityRuntime,
        publish_window: Callable[[PopulationCadenceInput], AuthorityEvent | None],
        window_size: int,
        catch_up_limit: int,
        initial_tick: int = 0,
        wall_period_seconds: float | None = None,
        mapping_revision: str = "population-seconds:v1",
    ) -> None:
        if window_size <= 0 or catch_up_limit < 0 or initial_tick < 0:
            raise ValueError("population_driver_invalid")
        if wall_period_seconds is not None and (not isfinite(wall_period_seconds) or wall_period_seconds <= 0):
            raise ValueError("population_driver_invalid")
        if not mapping_revision:
            raise ValueError("population_time_mapping_missing")
        self.on_confirmed_time = None
        self.migration_pending = False
        self.world_runtime = world_runtime
        self.publish_window = publish_window
        self.window_size = window_size
        self.catch_up_limit = catch_up_limit
        self.wall_period_seconds = wall_period_seconds
        world_ref = world_runtime.mode.world_ref
        confirmed = int(getattr(publish_window, "confirmed_tick",
                        max(initial_tick, getattr(world_runtime, "_population_driver_confirmed_tick", initial_tick))))
        if hasattr(publish_window, "confirmed_tick") and initial_tick > confirmed:
            raise ValueError("population_time_cursor_stale")
        self._pinned_publisher = getattr(publish_window, "publish_pinned", None)
        self.mapping = ClockMapping(
            mapping_id=f"population-seconds:{world_ref}", revision=mapping_revision,
            source_clock_ref=f"population-driver:{world_ref}", source_unit_ref="second",
            target_timeline_ref=f"population:{world_ref}", target_profile_revision="population-seconds:v1",
            source_origin=0, target_origin=0, ratio=Fraction(1), rounding_policy="exact",
            valid_source_interval=(0, 2**63 - 1), max_lateness=0,
            evidence_source_policy_ref="population-cadence-driver",
        )
        profile = TemporalProfile(
            profile_id="population-seconds", revision="population-seconds:v1",
            content_package_ref="population-runtime", advancement_policy="caller-driven",
            resolution_quantum="fixed_step", scheduling_policy="scheduled_event",
            settlement_policy="confirmed_window", time_control_policy="world",
            determinism_policy="best_effort", rewind_policy="disabled",
            canonical_unit_ref="second", step_duration=Fraction(1),
            supported_clock_mappings=(self.mapping.mapping_id,), rounding_policy="exact",
            activation_boundary="window", compatibility_constraints=(),
        )
        timeline = SimulationTimeline(
            timeline_id=f"population:{world_ref}", world_scope_ref=world_ref,
            advancement_owner_ref=self.mapping.source_clock_ref, profile_ref=profile.profile_id,
            profile_revision=profile.revision, epoch_ref="population-runtime:v1",
            current_step=confirmed, current_phase=None, authoritative_revision=0, status="active",
        )
        self.clock = SimulationClock(
            world_ref=world_runtime.mode.world_ref,
            initial_tick=confirmed,
            catch_up_budget=catch_up_limit,
            temporal_profile=profile,
            timeline=timeline,
        )
        if self._pinned_publisher is not None and confirmed:
            saved = getattr(publish_window, "confirmed_time_pins", None)
            if callable(saved):
                saved = saved()
            if saved is None:
                raise ValueError("population_time_mapping_missing")
            if saved.get("window_ticks") != window_size or saved.get("canonical_unit_ref") != "second":
                raise ValueError("population_time_migration_required")
            if saved.get("step_duration") == "1/1":
                if any(saved.get(key) != value for key, value in self._time_pins(confirmed).items()):
                    raise ValueError("population_time_mapping_stale")
            elif not self.world_runtime.store.read_stream(f"temporal-activation:{self.clock.timeline.timeline_id}"):
                raise ValueError("population_time_migration_required")

    def _time_pins(self, window_end: int) -> dict[str, str | int]:
        pins: dict[str, str | int] = {
            "timeline_id": self.clock.timeline.timeline_id,
            "profile_revision": self.clock.temporal_profile.revision,
            "mapping_id": self.mapping.mapping_id,
            "mapping_revision": self.mapping.revision,
            "source_clock_ref": self.mapping.source_clock_ref,
            "source_unit_ref": self.mapping.source_unit_ref,
            "source_revision": self.mapping.revision,
            "sampled_at": window_end,
            "received_at": window_end,
            "freshness": 0,
            "activation_revision": f"population-window:{self.window_size}:v1",
            # Persist both boundaries.  Consumers must not reconstruct the
            # opening boundary from an operational deadline or wall clock.
            "window_start": window_end - self.window_size,
            "window_ticks": self.window_size,
            "canonical_unit_ref": self.clock.temporal_profile.canonical_unit_ref,
            "step_duration": f"{self.clock.temporal_profile.step_duration.numerator}/{self.clock.temporal_profile.step_duration.denominator}",
            # Population -> Inventory custody is the currently admitted
            # settlement participant. These pins are issued with the durable
            # cadence authority record and rechecked by the Inventory owner.
            "settlement_participant_scope": "actor_gameplay.inventory_domain",
            "input_cutoff": window_end,
            "late_input_policy_ref": "reject_after_cutoff",
            "confirmation_boundary": window_end,
            "ordering_policy_ref": "source_revision_then_event_ref",
            "temporal_authorization_ref": "authorization:population-inventory-output-custody@1",
            "temporal_authorization_revision": "authorization:population-inventory-output-custody@1",
            "temporal_authorization_issuer_ref": f"world_runtime.population_cadence:{self.world_runtime.mode.world_ref}",
            "temporal_authorization_valid_until": window_end,
        }
        authorization = TemporalAuthorization(
            authorization_ref=str(pins["temporal_authorization_ref"]),
            revision=str(pins["temporal_authorization_revision"]),
            issuer_ref=str(pins["temporal_authorization_issuer_ref"]),
            timeline_id=str(pins["timeline_id"]),
            participant_scope=(str(pins["settlement_participant_scope"]),),
            input_cutoff=int(pins["input_cutoff"]),
            confirmation_boundary=int(pins["confirmation_boundary"]),
            late_input_policy_ref=str(pins["late_input_policy_ref"]),
            ordering_policy_ref=str(pins["ordering_policy_ref"]),
            valid_until=int(pins["temporal_authorization_valid_until"]),
        )
        pins["temporal_authorization_digest"] = authorization.digest
        # Each admitted temporal consumer receives its own bounded grant. The
        # cadence event remains the sole durable issuer and revocation source.
        grants = {}
        for key, participant in (
            ("economy", "actor_gameplay.economy_domain"),
            ("ecology", "actor_gameplay.ecology_domain"),
            ("status", "actor_gameplay.status_domain"),
            # Character background cognition is an admitted cadence consumer.
            # Its grant authorizes wake admission only; it never authorizes
            # cognition writeback or world-fact mutation.
            ("character", "actor_gameplay.character_cognition"),
            ("social", "authority:p5:social-delivery"),
            # Resource recovery is a distinct admitted participant.  It uses
            # the same Population cadence issuer, but never inherits custody
            # or another domain's grant.
            ("resource", "actor_gameplay.resource_domain"),
        ):
            grant = TemporalAuthorization(
                authorization_ref=f"authorization:population-{key}-temporal@1",
                revision="authorization:population-temporal@1",
                issuer_ref=str(pins["temporal_authorization_issuer_ref"]),
                timeline_id=str(pins["timeline_id"]),
                participant_scope=(participant,),
                input_cutoff=int(pins["input_cutoff"]),
                confirmation_boundary=int(pins["confirmation_boundary"]),
                late_input_policy_ref=str(pins["late_input_policy_ref"]),
                ordering_policy_ref=str(pins["ordering_policy_ref"]),
                valid_until=int(pins["temporal_authorization_valid_until"]),
            )
            grants[key] = {**grant.payload(), "digest": grant.digest}
        pins["temporal_authorizations"] = json.dumps(grants, sort_keys=True, separators=(",", ":"))
        return pins

    @property
    def current_tick(self) -> int:
        return int(self.clock.tick * self.clock.temporal_profile.step_duration)

    def activate_migration(self, profile: TemporalProfile, mapping: ClockMapping, *, boundary: str) -> None:
        self.clock.activate_temporal_profile(profile, advancement_owner_ref=self.clock.timeline.advancement_owner_ref,
                                             boundary=boundary, migration_mapping=mapping)
        self.mapping = mapping

    def tick(self, target_tick: int) -> PopulationDriverTickResult:
        if self.migration_pending:
            raise ValueError("temporal_migration_pending")
        previous_tick = self.current_tick
        try:
            windows = calculate_window_bounds(previous_tick, target_tick, self.window_size)
        except ValueError as exc:
            cadence_id = f"cadence:{self.world_runtime.mode.world_ref}:{target_tick}"
            return PopulationDriverTickResult(
                rejected_windows=((cadence_id, str(exc)),)
            )
        window_items = [(f"cadence:{self.world_runtime.mode.world_ref}:{start}", start, end)
                        for start, end in windows]
        if self.world_runtime.is_paused():
            return PopulationDriverTickResult(
                deferred_windows=tuple(item[0] for item in window_items)
            )
        confirmed_tick = previous_tick
        work = tuple(ScheduledWork(work_ref=item[0], domain_ref="population",
                                    due_time=SimulationTime(self.clock.timeline.timeline_id, item[2], Fraction(item[2])),
                                    trigger_ref=item[0], ordering_key=(f"{item[1]:020d}",),
                                    expected_revision_vector=(), owner_contract_ref="world_runtime.cadence",
                                    time_pins=tuple(sorted(self._time_pins(item[2]).items())))
                     for item in window_items)
        selected_work, deferred_work = select_temporal_work(
            work, now=SimulationTime(self.clock.timeline.timeline_id, target_tick, Fraction(target_tick)),
            budget=self.catch_up_limit)
        by_ref = {item[0]: item for item in window_items}
        selected = [by_ref[item.work_ref] for item in selected_work]
        deferred = tuple(item.work_ref for item in deferred_work)
        published: list[str] = []
        rejected: list[tuple[str, str]] = []
        advanced_count = due_count = deferred_count = rejected_count = 0
        for index, (cadence_id, window_start, window_end) in enumerate(selected):
            try:
                if (self.mapping.source_unit_ref != "second"
                        or self.mapping.source_clock_ref != f"population-driver:{self.world_runtime.mode.world_ref}"
                        or self.mapping.target_timeline_ref != self.clock.timeline.timeline_id
                        or self.mapping.ratio != 1 / self.clock.temporal_profile.step_duration):
                    raise ValueError("population_time_unit_mismatch")
                with self.world_runtime.store.group_commit():
                    cadence = self.world_runtime.build_population_cadence(
                        window_start=window_start,
                        window_end=window_end,
                        cadence_id=cadence_id,
                    )
                pins = self._time_pins(window_end)
                mapped = self.clock.map_source_time(
                    mapping=self.mapping, source_clock_ref=pins["source_clock_ref"],
                    source_unit_ref=pins["source_unit_ref"], source_revision=pins["source_revision"],
                    expected_source_revision=self.mapping.revision, mapping_revision=pins["mapping_revision"],
                    sampled_at=window_end, received_at=window_end)
                event = (self._pinned_publisher(cadence, pins) if self._pinned_publisher is not None
                         else self.publish_window(cadence))
            except Exception as exc:
                rejected.append(
                    (cadence_id, f"publisher_exception:{type(exc).__name__}:{exc}")
                    if not isinstance(exc, ValueError)
                    else (cadence_id, str(exc))
                )
                deferred = tuple(item[0] for item in selected[index + 1 :]) + deferred
                break
            if event is None:
                rejected.append((cadence_id, "publisher_rejected"))
                deferred = tuple(item[0] for item in selected[index + 1 :]) + deferred
                break
            published.append(cadence_id)
            confirmed_tick = window_end
            self.clock.advance_mapped(mapped, advancement_owner_ref=self.mapping.source_clock_ref,
                                      source_mapping=self.mapping)
            receipt = getattr(self.world_runtime, "last_population_confirmation", None)
            if receipt is not None and receipt.cadence_id == cadence_id:
                advanced_count += receipt.advanced_count
                due_count += receipt.due_count
                deferred_count += receipt.deferred_count
                rejected_count += receipt.rejected_count
        self.world_runtime._population_driver_confirmed_tick = confirmed_tick
        if self.on_confirmed_time is not None:
            self.on_confirmed_time(self)
        return PopulationDriverTickResult(
            published_cadence_ids=tuple(published),
            deferred_windows=deferred,
            rejected_windows=tuple(rejected),
            b0_advanced_count=advanced_count,
            due_item_count=due_count,
            deferred_item_count=deferred_count,
            rejected_item_count=rejected_count,
        )

    async def run_forever(
        self,
        stop_event: asyncio.Event,
        sleep: Callable[[float], Awaitable[None]],
        advance_clock: Callable[[int, int], int] | None = None,
        *,
        execution: RuntimeExecution | None = None,
    ) -> None:
        if self.wall_period_seconds is not None and advance_clock is not None:
            raise ValueError("population_wall_clock_override_forbidden")

        async def command(fn):
            if execution is None:
                return fn()  # 保留独立驱动器的同步测试入口。
            return await asyncio.wrap_future(execution.submit(fn))

        world_stream = f"world:{self.world_runtime.mode.world_ref}"
        origin_tick, mode_revision, started_at = await command(lambda: (
            self.current_tick, self.world_runtime.store.get_stream_head(world_stream), monotonic()
        ))
        was_paused = False
        period = self.wall_period_seconds or self.window_size
        while not stop_event.is_set():
            iteration_started = monotonic()
            cursor, paused, revision, observed_at = await command(lambda: (
                self.current_tick, self.world_runtime.is_paused(),
                self.world_runtime.store.get_stream_head(world_stream),
                iteration_started if self.wall_period_seconds is None else monotonic(),
            ))
            if paused or was_paused or revision != mode_revision:
                # 暂停的墙钟时间不计入恢复后的追赶预算。
                started_at, origin_tick = observed_at, cursor
            was_paused = paused
            mode_revision = revision
            due_tick = origin_tick + floor((observed_at - started_at) / period) * self.window_size
            current = max(cursor, due_tick)
            target = (current if self.wall_period_seconds is not None else
                      advance_clock(current, self.window_size) if advance_clock else current + self.window_size)
            if not paused:
                if target < cursor + self.window_size or not self.catch_up_limit:
                    # Retry recoverable owner work at the already confirmed boundary.
                    await command(lambda: self.tick(self.current_tick))
                for _ in range(self.catch_up_limit):
                    if stop_event.is_set():
                        break

                    def window():
                        nonlocal started_at, origin_tick, mode_revision
                        boundary_revision = self.world_runtime.store.get_stream_head(world_stream)
                        if boundary_revision != mode_revision:
                            # 窗间即使已 pause 后 resume，也必须丢弃旧追赶目标。
                            started_at, origin_tick = monotonic(), self.current_tick
                            mode_revision = boundary_revision
                            return None
                        if self.world_runtime.is_paused() or self.current_tick + self.window_size > target:
                            return None
                        result = self.tick(self.current_tick + self.window_size)
                        if result.rejected_windows:
                            raise RuntimeError("population_window_failed")
                        return result

                    result = await command(window)
                    if result is None or not result.published_cadence_ids:
                        break
                    # 每个完整窗口独立入队，让其他已接纳命令先执行。
                    await asyncio.sleep(0)
            # 处理耗时包含在窗口周期内；过载时由下一轮有限 catch-up 追赶。
            if self.wall_period_seconds is None:
                await sleep(max(0.0, self.window_size - (monotonic() - iteration_started)))
            else:
                cursor = await command(lambda: self.current_tick)
                now = monotonic()
                # 墙钟已到期的窗立即进入下一轮有限追赶；暂停或零预算不能忙等。
                next_window = (floor((now - started_at) / period) + 1 if paused or not self.catch_up_limit
                               else (cursor - origin_tick) // self.window_size + 1)
                await sleep(max(0.0, started_at + next_window * period - now))

__all__ = ["PopulationCadenceDriver", "PopulationDriverTickResult"]
