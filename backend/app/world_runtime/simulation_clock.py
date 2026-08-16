from __future__ import annotations

from dataclasses import dataclass

from app.gameplay.shared_contracts import ScheduledObligation


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


__all__ = ["ClockAdvance", "SimulationClock"]
