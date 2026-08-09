from __future__ import annotations

import pytest

from app.gameplay.survival_runtime import NeedDefinition, NeedState, SurvivalAuthority, SurvivalMode, SurvivalPolicy


def test_food_consumption_requires_external_owner_reservations() -> None:
    definition = NeedDefinition(need_ref="need:food", category="food", decay_per_tick=0.2)
    state = NeedState(need_ref="need:food", value=0.6, last_tick=0)
    _, plan = SurvivalAuthority.tick(policy=SurvivalPolicy(policy_ref="p", mode=SurvivalMode.SIMULATION, revision="v1"), definition=definition, state=state, tick=1)
    assert plan is not None
    assert plan.required_owner_refs == ("inventory", "ownership")
    with pytest.raises(ValueError, match="revision_conflict"):
        SurvivalAuthority.tick(policy=SurvivalPolicy(policy_ref="p", mode=SurvivalMode.SIMULATION, revision="v1"), definition=definition, state=state, tick=-1)
