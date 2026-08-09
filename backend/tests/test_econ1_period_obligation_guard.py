from __future__ import annotations

import pytest

from app.gameplay.econ1_economy_runtime import BusinessPeriod, EconomicObligation, EconomyAuthority


def test_period_close_rejects_overdue_obligation_without_closing_period() -> None:
    period = BusinessPeriod(
        period_ref="period:overdue",
        sequence=1,
        policy_revision="policy:v1",
        obligations=(EconomicObligation(obligation_ref="obligation:overdue", owner_ref="org:bakery", kind="tax", amount=1, due_tick=1, status="overdue"),),
    )

    with pytest.raises(ValueError, match="overdue_obligation"):
        EconomyAuthority.close_period(period)

    assert period.closed is False
