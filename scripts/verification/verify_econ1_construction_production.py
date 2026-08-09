from __future__ import annotations

from econ1_profile_common import run_profile
from app.gameplay.bakery_reference_runtime import BakeryReferenceScenario
from app.gameplay.construction_production_runtime import ConstructionProductionAuthority
from app.gameplay.event_store import GameplayEventStore


def main() -> int:
    store = GameplayEventStore()
    scenario = BakeryReferenceScenario.default()
    periods = scenario.run_three_periods(store=store)
    production = ConstructionProductionAuthority(store=store)
    run = production.projector().runs["run:bakery:1"]
    maintenance = production.settle_maintenance_obligation(
        run,
        obligation_ref="obligation:maintenance:facility:bakery",
        command_id="maintenance:facility:bakery",
        idempotency_key="maintenance:facility:bakery",
        causation_id="causation:maintenance:facility:bakery",
        correlation_id="correlation:bakery:maintenance",
    )
    event_types = [event.event_type for event in store.read_events()]
    return run_profile(name="econ1-construction-production", overall_key="overall_econ1_construction_production_passed", predecessor="phase1c-frost-farm-report.json", checks={"facility_acquired": event_types.count("gameplay.construction_production.facility_acquired") == 1, "facility_runs": event_types.count("gameplay.construction_production.run_started") == 3, "finished_output_receipt": event_types.count("gameplay.construction_production.run_finished") == 3 and event_types.count("gameplay.inventory.output_received") == 3, "material_reservations": event_types.count("gameplay.inventory.reservation_created") == 6 and event_types.count("gameplay.inventory.reservation_consumed") == 6, "maintenance_obligation": maintenance.committed and event_types.count("gameplay.construction_production.maintenance_obligation_created") == 1, "terminal_periods": all(period.closed for period in periods)})


if __name__ == "__main__":
    raise SystemExit(main())
