from __future__ import annotations

import pytest


def test_bakery_single_owner_scenario_has_no_npc_state() -> None:
    from app.gameplay.bakery_reference_runtime import BakeryReferenceScenario

    scenario = BakeryReferenceScenario.default()
    assert scenario.owner_character_ref == "character:char_a"
    assert scenario.period_count == 3
    assert scenario.employee_refs == ()
    with pytest.raises(ValueError, match="population_simulation_forbidden"):
        scenario.with_employee("npc:synthetic")
