from __future__ import annotations

import pytest

from app.gameplay.bakery_reference_runtime import BakeryReferenceScenario
from app.gameplay.organization_government_runtime import GovernmentAuthority


def test_bakery_rejects_expired_permit_before_period_settlement() -> None:
    scenario = BakeryReferenceScenario.default()
    with pytest.raises(ValueError, match="permit_expired"):
        GovernmentAuthority.require_permit(scenario.permit, tick=101, policy_revision="policy:v1")


def test_existing_character_employee_path_is_allowed() -> None:
    scenario = BakeryReferenceScenario.default().with_employee("character:employee:1")
    assert scenario.employee_refs == ("character:employee:1",)


def test_existing_profile_backed_employee_path_rejects_synthetic_character_refs() -> None:
    scenario = BakeryReferenceScenario.default()
    employee = scenario.with_existing_character_employee("character:char_b")
    assert employee.employee_refs == ("character:char_b",)
    with pytest.raises(ValueError, match="character_record_required"):
        scenario.with_existing_character_employee("character:synthetic")
