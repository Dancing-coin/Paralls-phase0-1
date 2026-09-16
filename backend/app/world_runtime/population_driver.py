from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable
from time import monotonic

from app.models.authority_event import AuthorityEvent
from app.population_continuity.siming_contracts import PopulationCadenceInput
from app.population_continuity.world import WorldContinuityRuntime

from .simulation_clock import SimulationClock, calculate_window_bounds


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
    ) -> None:
        if window_size <= 0 or catch_up_limit < 0 or initial_tick < 0:
            raise ValueError("population_driver_invalid")
        self.world_runtime = world_runtime
        self.publish_window = publish_window
        self.window_size = window_size
        self.catch_up_limit = catch_up_limit
        self.clock = SimulationClock(
            world_ref=world_runtime.mode.world_ref,
            initial_tick=initial_tick,
            catch_up_budget=catch_up_limit,
        )
        self._runtime_history = set(
            getattr(world_runtime, "published_population_cadence_ids", ())
        )
        setattr(world_runtime, "published_population_cadence_ids", self._runtime_history)
        self._published_cadence_ids = self._history_ids()
        self.clock.tick = self._confirmed_history_tick(initial_tick)

    @property
    def current_tick(self) -> int:
        return self.clock.tick

    def tick(self, target_tick: int) -> PopulationDriverTickResult:
        previous_tick = self.clock.tick
        try:
            windows = calculate_window_bounds(previous_tick, target_tick, self.window_size)
        except ValueError as exc:
            cadence_id = f"cadence:{self.world_runtime.mode.world_ref}:{target_tick}"
            return PopulationDriverTickResult(
                rejected_windows=((cadence_id, str(exc)),)
            )
        window_items = [
            (f"cadence:{self.world_runtime.mode.world_ref}:{start}", start, end)
            for start, end in windows
        ]
        if self.world_runtime.is_paused():
            return PopulationDriverTickResult(
                deferred_windows=tuple(item[0] for item in window_items)
            )
        pending = []
        deferred_after_gap: list[str] = []
        confirmed_tick = previous_tick
        for item in window_items:
            if item[0] in self._published_cadence_ids and not pending:
                confirmed_tick = item[2]
                continue
            if item[0] in self._published_cadence_ids:
                deferred_after_gap.append(item[0])
            else:
                pending.append(item)
        selected = pending[: self.catch_up_limit]
        deferred = tuple(item[0] for item in pending[self.catch_up_limit :]) + tuple(deferred_after_gap)
        published: list[str] = []
        rejected: list[tuple[str, str]] = []
        advanced_count = due_count = deferred_count = rejected_count = 0
        for index, (cadence_id, window_start, window_end) in enumerate(selected):
            try:
                cadence = self.world_runtime.build_population_cadence(
                    window_start=window_start,
                    window_end=window_end,
                    cadence_id=cadence_id,
                )
                event = self.publish_window(cadence)
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
            self._published_cadence_ids.add(cadence_id)
            self._runtime_history.add(cadence_id)
            published.append(cadence_id)
            confirmed_tick = window_end
            receipt = getattr(self.world_runtime, "last_population_confirmation", None)
            if receipt is not None and receipt.cadence_id == cadence_id:
                advanced_count += receipt.advanced_count
                due_count += receipt.due_count
                deferred_count += receipt.deferred_count
                rejected_count += receipt.rejected_count
        self.clock.tick = confirmed_tick
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
    ) -> None:
        started_at = monotonic()
        origin_tick = self.current_tick
        while not stop_event.is_set():
            iteration_started = monotonic()
            due_tick = origin_tick + int((iteration_started - started_at) // self.window_size) * self.window_size
            current = max(self.current_tick, due_tick)
            target = advance_clock(current, self.window_size) if advance_clock else current + self.window_size
            self.tick(target)
            # 处理耗时包含在窗口周期内；过载时由下一轮有限 catch-up 追赶。
            await sleep(max(0.0, self.window_size - (monotonic() - iteration_started)))

    def _history_ids(self) -> set[str]:
        existing = getattr(self.world_runtime, "published_population_cadence_ids", ())
        ids = {str(value) for value in existing}
        history = getattr(self.publish_window, "published_events", ())
        for event in history:
            payload = getattr(event, "payload", {})
            cadence = payload.get("population_cadence", {}) if isinstance(payload, dict) else {}
            cadence_id = cadence.get("cadence_id") if isinstance(cadence, dict) else None
            if isinstance(cadence_id, str):
                ids.add(cadence_id)
        return ids

    def _confirmed_history_tick(self, initial_tick: int) -> int:
        cursor = initial_tick
        prefix = f"cadence:{self.world_runtime.mode.world_ref}:"
        while f"{prefix}{cursor}" in self._published_cadence_ids:
            cursor += self.window_size
        return cursor


__all__ = ["PopulationCadenceDriver", "PopulationDriverTickResult"]
