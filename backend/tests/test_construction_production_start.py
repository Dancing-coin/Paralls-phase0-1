from __future__ import annotations

import pytest

from app.gameplay.construction_production_runtime import ConstructionProductionAuthority, Facility, Recipe
from app.gameplay.event_store import GameplayEventStore


def test_start_requires_available_facility_and_retains_only_reservation_refs() -> None:
    facility = Facility(facility_ref="facility:1", plot_ref="plot:1", facility_kind="bakery", condition=1)
    recipe = Recipe(recipe_ref="recipe:bread", inputs={"flour": 2}, output_item="bread", duration_ticks=2)
    run = ConstructionProductionAuthority.start_run(facility=facility, recipe=recipe, run_ref="run:1", tick=3, reservation_refs=("reservation:flour",))
    assert run.finish_tick == 5
    assert run.reservation_refs == ("reservation:flour",)
    with pytest.raises(ValueError, match="facility_unavailable"):
        ConstructionProductionAuthority.start_run(facility=facility.model_copy(update={"condition": 0}), recipe=recipe, run_ref="run:2", tick=3)


def test_settle_start_run_appends_canonical_event_and_rejects_without_write() -> None:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(facility_ref="facility:1", plot_ref="plot:1", facility_kind="bakery", condition=1)
    recipe = Recipe(recipe_ref="recipe:bread", inputs={"flour": 2}, output_item="bread", duration_ticks=2)
    result = authority.settle_start_run(
        facility=facility, recipe=recipe, run_ref="run:1", tick=3,
        reservation_refs=("reservation:flour",), command_id="command:production:start:1",
        idempotency_key="idem:production:start:1", causation_id="cause:production:start:1",
        correlation_id="corr:production:1",
    )
    assert result.committed is True
    assert [event.event_type for event in store.read_events()] == ["gameplay.construction_production.run_started"]
    before = len(store.read_events())
    with pytest.raises(ValueError, match="facility_unavailable"):
        authority.settle_start_run(
            facility=facility.model_copy(update={"condition": 0}), recipe=recipe, run_ref="run:2", tick=3,
            command_id="command:production:start:2", idempotency_key="idem:production:start:2",
            causation_id="cause:production:start:2", correlation_id="corr:production:2",
        )
    assert len(store.read_events()) == before
