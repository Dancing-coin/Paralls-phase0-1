from __future__ import annotations

import pytest


def test_construction_records_are_strict_and_do_not_shadow_other_owners() -> None:
    from app.gameplay.construction_production_runtime import Facility, Plot, Recipe

    plot = Plot(plot_ref="plot:bakery:1", jurisdiction_ref="jurisdiction:demo", owner_ref="owner:bakery")
    facility = Facility(facility_ref="facility:bakery:1", plot_ref=plot.plot_ref, facility_kind="bakery", condition=1.0)
    recipe = Recipe(recipe_ref="recipe:bread:v1", inputs={"flour": 2}, output_item="bread", duration_ticks=1)
    assert facility.plot_ref == plot.plot_ref
    assert recipe.output_item == "bread"
    with pytest.raises(ValueError, match="extra|forbid"):
        Facility(facility_ref="facility:1", plot_ref="plot:1", facility_kind="bakery", condition=1, account_balance=1)


def test_facility_acquisition_is_an_event_sourced_construction_fact() -> None:
    from app.gameplay.construction_production_runtime import ConstructionProductionAuthority, Facility, Plot
    from app.gameplay.event_store import GameplayEventStore

    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    plot = Plot(plot_ref="plot:bakery:1", jurisdiction_ref="jurisdiction:demo", owner_ref="org:bakery")
    facility = Facility(facility_ref="facility:bakery:1", plot_ref=plot.plot_ref, facility_kind="bakery", condition=1.0)
    result = authority.settle_facility_acquisition(
        plot=plot,
        facility=facility,
        command_id="construction:acquire:bakery:1",
        idempotency_key="construction:acquire:bakery:1",
        causation_id="cause:acquire:1",
        correlation_id="corr:acquire:1",
    )
    assert result.committed
    assert store.read_events()[0].event_type == "gameplay.construction_production.facility_acquired"
