from __future__ import annotations

import pytest

from app.gameplay.construction_production_runtime import ConstructionProductionAuthority, Facility, Recipe
from app.gameplay.event_store import GameplayEventStore


def test_finish_is_explicit_and_terminal_delivery_is_idempotent_fail_closed() -> None:
    facility = Facility(facility_ref="facility:1", plot_ref="plot:1", facility_kind="bakery", condition=1)
    recipe = Recipe(recipe_ref="recipe:bread", inputs={"flour": 2}, output_item="bread", duration_ticks=1)
    run = ConstructionProductionAuthority.start_run(facility=facility, recipe=recipe, run_ref="run:1", tick=3)
    with pytest.raises(ValueError, match="production_not_due"):
        ConstructionProductionAuthority.finish_run(run, tick=3, recipe=recipe)
    completed = ConstructionProductionAuthority.finish_run(run, tick=4, recipe=recipe)
    assert completed.status == "completed"
    with pytest.raises(ValueError, match="production_run_final"):
        ConstructionProductionAuthority.finish_run(completed, tick=4, recipe=recipe)


def test_settle_finish_run_appends_output_event_after_start() -> None:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(facility_ref="facility:1", plot_ref="plot:1", facility_kind="bakery", condition=1)
    recipe = Recipe(recipe_ref="recipe:bread", inputs={"flour": 2}, output_item="bread", duration_ticks=1)
    run_result = authority.settle_start_run(
        facility=facility, recipe=recipe, run_ref="run:1", tick=3,
        command_id="command:production:start:1", idempotency_key="idem:production:start:1",
        causation_id="cause:production:start:1", correlation_id="corr:production:1",
    )
    run = authority.projector().runs["run:1"]
    result = authority.settle_finish_run(
        run, tick=4, recipe=recipe, command_id="command:production:finish:1",
        idempotency_key="idem:production:finish:1", causation_id="cause:production:finish:1",
        correlation_id="corr:production:1",
    )
    assert run_result.committed and result.committed
    assert store.read_events()[-1].event_type == "gameplay.construction_production.run_finished"
