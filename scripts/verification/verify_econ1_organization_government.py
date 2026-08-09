from __future__ import annotations

from econ1_profile_common import run_profile
from app.gameplay.bakery_reference_runtime import BakeryReferenceScenario
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.organization_government_runtime import GovernmentAuthority


def main() -> int:
    scenario = BakeryReferenceScenario.default()
    store = GameplayEventStore()
    scenario.run_three_periods(store=store)
    event_types = [event.event_type for event in store.read_events()]
    GovernmentAuthority.require_permit(scenario.permit, tick=1, policy_revision="policy:v1")
    return run_profile(name="econ1-organization-government", overall_key="overall_econ1_organization_government_passed", predecessor="econ1-economy-period-settlement-report.json", checks={"permit": event_types.count("gameplay.government.permit_verified") == 3, "tax_assessments": event_types.count("gameplay.government.tax_assessed") == 3, "no_synthetic_npc": all(ref.startswith("character:") for ref in scenario.employee_refs)})


if __name__ == "__main__":
    raise SystemExit(main())
