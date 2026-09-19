from __future__ import annotations

from dataclasses import dataclass

from app.gameplay.shared_contracts import ScheduledObligation


def population_clock_profile(name: str) -> dict[str, str | int]:
    """启动时固定的时间语义；生产兼容窗口不伪装成一秒benchmark。"""
    if name not in ("production", "benchmark_1x", "benchmark_10x"):
        raise ValueError("population_clock_profile_unknown")
    window = 86400 if name == "production" else 1
    return dict(simulation_tick_unit="second", window_ticks=window,
                wall_period_seconds=window, speed=10 if name == "benchmark_10x" else 1)


def calculate_window_bounds(
    previous_tick: int, target_tick: int, window_size: int
) -> tuple[tuple[int, int], ...]:
    if previous_tick < 0 or target_tick < 0 or window_size <= 0:
        raise ValueError("simulation_clock_invalid_window")
    if target_tick < previous_tick:
        raise ValueError("simulation_clock_cannot_rewind")
    return tuple(
        (window_start, window_start + window_size)
        for window_start in range(previous_tick, target_tick - window_size + 1, window_size)
    )


@dataclass(frozen=True)
class ClockAdvance:
    previous_tick: int
    current_tick: int
    due: tuple[ScheduledObligation, ...]
    deferred: tuple[ScheduledObligation, ...]


class SimulationClock:
    """Caller-driven clock facade; it never starts a background loop or writes truth."""

    def __init__(self, *, world_ref: str, initial_tick: int = 0, catch_up_budget: int = 100) -> None:
        if not world_ref or initial_tick < 0 or catch_up_budget < 0:
            raise ValueError("simulation_clock_invalid")
        self.world_ref = world_ref
        self.tick = initial_tick
        self.catch_up_budget = catch_up_budget

    def advance(self, target_tick: int, obligations: tuple[ScheduledObligation, ...] = ()) -> ClockAdvance:
        if target_tick < self.tick:
            raise ValueError("simulation_clock_cannot_rewind")
        due = tuple(sorted((item for item in obligations if item.due_tick <= target_tick and item.status in {"open", "due", "retry", "retryable"}), key=lambda item: (item.due_tick, item.obligation_id)))
        selected = due[: self.catch_up_budget]
        deferred = due[self.catch_up_budget :]
        previous = self.tick
        self.tick = target_tick
        return ClockAdvance(previous_tick=previous, current_tick=target_tick, due=selected, deferred=deferred)


__all__ = ["ClockAdvance", "SimulationClock", "calculate_window_bounds"]
