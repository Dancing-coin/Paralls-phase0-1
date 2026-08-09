from __future__ import annotations

import pytest

from app.gameplay.econ1_economy_runtime import BusinessPeriod, EconomyAuthority
from app.gameplay.event_store import GameplayEventStore


def test_period_close_is_deterministic_and_terminal() -> None:
    period = BusinessPeriod(period_ref="period:1", sequence=1, policy_revision="policy:v1", revenue=10, cost=4, tax=1)
    closed = EconomyAuthority.close_period(period)
    assert closed.closed is True
    assert closed.result_digest.startswith("sha256:")
    with pytest.raises(ValueError, match="period_already_closed"):
        EconomyAuthority.close_period(closed)


def test_settle_period_close_appends_period_and_obligation_events() -> None:
    store = GameplayEventStore()
    authority = EconomyAuthority(store=store)
    period = BusinessPeriod(period_ref="period:1", sequence=1, policy_revision="policy:v1", revenue=10, cost=4, tax=1)
    result = authority.settle_period_close(
        period, command_id="command:economy:period:1", idempotency_key="idem:economy:period:1",
        causation_id="cause:economy:period:1", correlation_id="corr:economy:period:1",
    )
    assert result.committed is True
    assert store.read_events()[-1].event_type == "gameplay.economy.business_period_closed"
