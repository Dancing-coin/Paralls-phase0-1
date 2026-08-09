from __future__ import annotations

import pytest


def test_survival_modes_and_need_records_are_strict() -> None:
    from app.gameplay.survival_runtime import NeedDefinition, NeedState, SurvivalMode, SurvivalPolicy

    policy = SurvivalPolicy(policy_ref="survival:food:v1", mode=SurvivalMode.DISABLED, revision="policy:1")
    need = NeedDefinition(need_ref="need:food", category="food", decay_per_tick=0.2)
    state = NeedState(need_ref=need.need_ref, value=1.0, last_tick=0)
    assert policy.mode == SurvivalMode.DISABLED
    assert state.need_ref == need.need_ref
    with pytest.raises(ValueError, match="extra|forbid"):
        NeedDefinition(need_ref="need:x", category="food", decay_per_tick=0.2, inventory_balance=1)
