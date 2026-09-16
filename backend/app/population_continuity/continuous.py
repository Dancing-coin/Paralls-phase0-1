from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


SECONDS_PER_HOUR = 3_600
SECONDS_PER_DAY = 86_400
DUE_INTERVAL_SECONDS = 21_600


@dataclass(frozen=True)
class B0ContinuousResult:
    actor_id: str
    from_tick: int
    to_tick: int
    actor_revision_before: int
    values: Mapping[str, object]
    due_ticks: tuple[int, ...]


def _phase_at(tick: int) -> str:
    local = tick % SECONDS_PER_DAY
    if local < 6 * SECONDS_PER_HOUR:
        return "rest"
    if local < 18 * SECONDS_PER_HOUR:
        return "routine_work"
    return "leisure"


def _next_phase_boundary(tick: int) -> int:
    day_start = tick - tick % SECONDS_PER_DAY
    for offset in (6 * SECONDS_PER_HOUR, 18 * SECONDS_PER_HOUR, SECONDS_PER_DAY):
        boundary = day_start + offset
        if boundary > tick:
            return boundary
    return day_start + SECONDS_PER_DAY


def _fatigue_after(value: float, from_tick: int, to_tick: int) -> float:
    rates = {"rest": -0.04, "routine_work": 0.02, "leisure": -0.01}
    cursor = from_tick
    result = value
    while cursor < to_tick:
        boundary = min(to_tick, _next_phase_boundary(cursor))
        result += rates[_phase_at(cursor)] * ((boundary - cursor) / SECONDS_PER_HOUR)
        result = min(1.0, max(0.0, result))
        cursor = boundary
    return round(min(1.0, max(0.0, result)), 9)


def advance_b0_row(
    *,
    actor_id: str,
    row: Mapping[str, object],
    window_start: int,
    window_end: int,
) -> B0ContinuousResult:
    """按真实秒数推进一行 B0 客观状态，不执行任何外部写入。"""
    if not actor_id or window_start < 0 or window_end <= window_start:
        raise ValueError("population_b0_window_invalid")
    stored_tick = int(row.get("last_update_tick", 0))
    revision = int(row.get("revision", 0))
    if stored_tick != window_start and not (stored_tick == 0 and revision == 0):
        raise ValueError("population_b0_cursor_conflict")
    from_tick = stored_tick
    elapsed = window_end - from_tick
    fatigue = _fatigue_after(float(row.get("fatigue", 0.2)), from_tick, window_end)
    need_pressure = round(
        min(1.0, max(0.0, float(row.get("need_pressure", 0.1)) + elapsed / SECONDS_PER_HOUR * 0.01)),
        9,
    )
    starvation_credit = round(
        min(1.0, max(0.0, float(row.get("starvation_credit", 0.0)) + elapsed / SECONDS_PER_DAY * 0.1)),
        9,
    )
    raw_next_due = row.get("next_due_tick")
    next_due = int(raw_next_due) if isinstance(raw_next_due, int) else 0
    if next_due <= from_tick:
        next_due = (from_tick // DUE_INTERVAL_SECONDS + 1) * DUE_INTERVAL_SECONDS
    due_ticks: list[int] = []
    while next_due <= window_end:
        due_ticks.append(next_due)
        next_due += DUE_INTERVAL_SECONDS
    values = MappingProxyType(
        {
            "last_update_tick": window_end,
            "activity_phase": _phase_at(window_end),
            "fatigue": fatigue,
            "need_pressure": need_pressure,
            "next_due_tick": next_due,
            "starvation_credit": starvation_credit,
        }
    )
    return B0ContinuousResult(
        actor_id=actor_id,
        from_tick=from_tick,
        to_tick=window_end,
        actor_revision_before=revision,
        values=values,
        due_ticks=tuple(due_ticks),
    )


__all__ = [
    "B0ContinuousResult",
    "DUE_INTERVAL_SECONDS",
    "SECONDS_PER_DAY",
    "SECONDS_PER_HOUR",
    "advance_b0_row",
]
