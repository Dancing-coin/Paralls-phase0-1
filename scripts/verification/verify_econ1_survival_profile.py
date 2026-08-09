from __future__ import annotations

from econ1_profile_common import run_profile
from app.gameplay.bakery_reference_runtime import BakeryReferenceScenario
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.survival_runtime import SurvivalMode


def main() -> int:
    scenario = BakeryReferenceScenario.default()
    disabled_store = GameplayEventStore()
    enabled_store = GameplayEventStore()
    disabled = scenario.run_three_periods(survival_mode=SurvivalMode.DISABLED, store=disabled_store)
    enabled = scenario.run_three_periods(survival_mode=SurvivalMode.SIMULATION, store=enabled_store)
    disabled_types = [event.event_type for event in disabled_store.read_events()]
    enabled_types = [event.event_type for event in enabled_store.read_events()]
    return run_profile(name="econ1-survival-profile", overall_key="overall_econ1_survival_profile_passed", predecessor="econ1-construction-production-report.json", checks={"disabled_periods": len(disabled) == 3 and not any(event_type.startswith("gameplay.survival.") for event_type in disabled_types), "enabled_periods": len(enabled) == 3 and enabled_types.count("gameplay.survival.need_tick") == 3})


if __name__ == "__main__":
    raise SystemExit(main())
