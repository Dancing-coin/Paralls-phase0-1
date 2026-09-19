from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable
from time import monotonic
from math import floor, isfinite

from app.models.authority_event import AuthorityEvent
from app.services.runtime_execution import RuntimeExecution
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
        wall_period_seconds: float | None = None,
    ) -> None:
        if window_size <= 0 or catch_up_limit < 0 or initial_tick < 0:
            raise ValueError("population_driver_invalid")
        if wall_period_seconds is not None and (not isfinite(wall_period_seconds) or wall_period_seconds <= 0):
            raise ValueError("population_driver_invalid")
        self.world_runtime = world_runtime
        self.publish_window = publish_window
        self.window_size = window_size
        self.catch_up_limit = catch_up_limit
        self.wall_period_seconds = wall_period_seconds
        self.clock = SimulationClock(
            world_ref=world_runtime.mode.world_ref,
            initial_tick=initial_tick,
            catch_up_budget=catch_up_limit,
        )
        self.clock.tick = int(getattr(publish_window, "confirmed_tick",
                              max(initial_tick, getattr(world_runtime, "_population_driver_confirmed_tick", initial_tick))))

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
        confirmed_tick = previous_tick
        selected = window_items[: self.catch_up_limit]
        deferred = tuple(item[0] for item in window_items[self.catch_up_limit :])
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
            published.append(cadence_id)
            confirmed_tick = window_end
            receipt = getattr(self.world_runtime, "last_population_confirmation", None)
            if receipt is not None and receipt.cadence_id == cadence_id:
                advanced_count += receipt.advanced_count
                due_count += receipt.due_count
                deferred_count += receipt.deferred_count
                rejected_count += receipt.rejected_count
        self.clock.tick = confirmed_tick
        self.world_runtime._population_driver_confirmed_tick = confirmed_tick
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
