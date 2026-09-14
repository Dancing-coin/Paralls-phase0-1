from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable

from app.models.authority_event import AuthorityEvent
from app.population_continuity.siming_contracts import PopulationCadenceInput
from app.population_continuity.world import WorldContinuityRuntime

from .simulation_clock import SimulationClock, calculate_window_bounds


@dataclass(frozen=True)
class PopulationDriverTickResult:
    published_cadence_ids: tuple[str, ...] = ()
    deferred_windows: tuple[str, ...] = ()
    rejected_windows: tuple[tuple[str, str], ...] = ()


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
        pending = [
            (f"cadence:{self.world_runtime.mode.world_ref}:{start}", start, end)
            for start, end in windows
            if f"cadence:{self.world_runtime.mode.world_ref}:{start}"
            not in self._published_cadence_ids
        ]
        selected = pending[: self.catch_up_limit]
        deferred = tuple(item[0] for item in pending[self.catch_up_limit :])
        published: list[str] = []
        rejected: list[tuple[str, str]] = []
        confirmed_tick = previous_tick
        for cadence_id, window_start, window_end in selected:
            try:
                cadence = self.world_runtime.build_population_cadence(
                    window_start=window_start,
                    window_end=window_end,
                    cadence_id=cadence_id,
                )
                event = self.publish_window(cadence)
            except ValueError as exc:
                rejected.append((cadence_id, str(exc)))
                break
            if event is None:
                rejected.append((cadence_id, "publisher_rejected"))
                break
            self._published_cadence_ids.add(cadence_id)
            self._runtime_history.add(cadence_id)
            published.append(cadence_id)
            confirmed_tick = window_end
        if not rejected:
            confirmed_tick = target_tick
        self.clock.tick = confirmed_tick
        return PopulationDriverTickResult(
            published_cadence_ids=tuple(published),
            deferred_windows=deferred,
            rejected_windows=tuple(rejected),
        )

    async def run_forever(
        self,
        stop_event: asyncio.Event,
        sleep: Callable[[float], Awaitable[None]],
    ) -> None:
        while not stop_event.is_set():
            self.tick(self.clock.tick + self.window_size)
            await sleep(self.window_size)

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


__all__ = ["PopulationCadenceDriver", "PopulationDriverTickResult"]
