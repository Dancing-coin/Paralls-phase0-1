from __future__ import annotations

import pytest

from app.gameplay.shared_contracts import ScheduledObligation
from app.world_runtime.simulation_clock import SimulationClock


def obligation(ref: str, due: int, status: str = "open") -> ScheduledObligation:
    return ScheduledObligation(obligation_id=ref, owner_ref="owner:1", due_tick=due, policy_revision="policy:1", status=status)


def test_clock_is_explicit_and_budgeted() -> None:
    clock = SimulationClock(world_ref="world:1", initial_tick=2, catch_up_budget=1)
    result = clock.advance(10, (obligation("obl:late", 8), obligation("obl:early", 3)))
    assert result.previous_tick == 2
    assert result.current_tick == 10
    assert tuple(item.obligation_id for item in result.due) == ("obl:early",)
    assert tuple(item.obligation_id for item in result.deferred) == ("obl:late",)


def test_clock_filters_closed_and_rejects_rewind() -> None:
    clock = SimulationClock(world_ref="world:1", initial_tick=4)
    result = clock.advance(4, (obligation("obl:closed", 1, "closed"), obligation("obl:open", 4)))
    assert tuple(item.obligation_id for item in result.due) == ("obl:open",)
    with pytest.raises(ValueError, match="rewind"):
        clock.advance(3)
