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


def test_settle_finish_run_rejects_stale_run_snapshot_before_append() -> None:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(facility_ref="facility:stale-finish", plot_ref="plot:stale-finish", facility_kind="bakery", condition=1)
    recipe = Recipe(recipe_ref="recipe:stale-finish", inputs={}, output_item="bread", duration_ticks=1)
    assert authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:stale-finish",
        tick=0,
        command_id="command:stale-finish:start",
        idempotency_key="idempotency:stale-finish:start",
        causation_id="cause:stale-finish:start",
        correlation_id="corr:stale-finish:start",
    ).committed
    run = authority.projector().runs["run:stale-finish"]
    stale = run.model_copy(update={"recipe_ref": "recipe:other"})
    before = tuple(store.read_events())
    result = authority.settle_finish_run(
        stale,
        tick=1,
        recipe=recipe,
        command_id="command:stale-finish:finish",
        idempotency_key="idempotency:stale-finish:finish",
        causation_id="cause:stale-finish:finish",
        correlation_id="corr:stale-finish:finish",
    )
    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "production_run_source_conflict"
    assert tuple(store.read_events()) == before


def test_production_run_finish_replay_rejects_identity_tamper() -> None:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(facility_ref="facility:finish-tamper", plot_ref="plot:finish-tamper", facility_kind="bakery", condition=1)
    recipe = Recipe(recipe_ref="recipe:finish-tamper", inputs={}, output_item="bread", duration_ticks=1)
    assert authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:finish-tamper",
        tick=0,
        command_id="command:finish-tamper:start",
        idempotency_key="idempotency:finish-tamper:start",
        causation_id="cause:finish-tamper:start",
        correlation_id="corr:finish-tamper:start",
    ).committed
    run = authority.projector().runs["run:finish-tamper"]
    assert authority.settle_finish_run(
        run,
        tick=1,
        recipe=recipe,
        command_id="command:finish-tamper:finish",
        idempotency_key="idempotency:finish-tamper:finish",
        causation_id="cause:finish-tamper:finish",
        correlation_id="corr:finish-tamper:finish",
    ).committed
    finish = store.read_events()[-1]
    tampered = finish.model_copy(update={"payload": {**finish.payload, "recipe_ref": "recipe:other"}}, deep=True)
    with pytest.raises(ValueError, match="production_run_finish_identity_conflict"):
        authority._projector.rebuild([*store.read_events()[:-1], tampered])


def test_production_run_finish_replay_rejects_stream_or_privacy_tamper() -> None:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(facility_ref="facility:finish-source", plot_ref="plot:finish-source", facility_kind="bakery", condition=1)
    recipe = Recipe(recipe_ref="recipe:finish-source", inputs={}, output_item="bread", duration_ticks=1)
    assert authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:finish-source",
        tick=0,
        command_id="command:finish-source:start",
        idempotency_key="idempotency:finish-source:start",
        causation_id="cause:finish-source:start",
        correlation_id="corr:finish-source:start",
    ).committed
    run = authority.projector().runs["run:finish-source"]
    assert authority.settle_finish_run(
        run,
        tick=1,
        recipe=recipe,
        command_id="command:finish-source:finish",
        idempotency_key="idempotency:finish-source:finish",
        causation_id="cause:finish-source:finish",
        correlation_id="corr:finish-source:finish",
    ).committed
    finish = store.read_events()[-1]
    wrong_stream = finish.model_copy(update={"stream_id": "gameplay:construction_production:facility:other"}, deep=True)
    with pytest.raises(ValueError, match="production_run_finish_source_conflict"):
        authority._projector.rebuild([*store.read_events()[:-1], wrong_stream])
    private = finish.model_copy(update={"visibility_policy": "authority_only"}, deep=True)
    with pytest.raises(ValueError, match="production_run_finish_source_conflict"):
        authority._projector.rebuild([*store.read_events()[:-1], private])


@pytest.mark.parametrize(
    "mutation",
    [
        {"output_quantity": 0},
        {"output_quantity": -1},
        {"output_quality": 1.1},
        {"output_quality": -0.1},
    ],
)
def test_production_run_finish_replay_rejects_output_bounds_tamper(mutation: dict[str, object]) -> None:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(facility_ref="facility:finish-bounds", plot_ref="plot:finish-bounds", facility_kind="bakery", condition=1)
    recipe = Recipe(recipe_ref="recipe:finish-bounds", inputs={}, output_item="bread", duration_ticks=1)
    assert authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:finish-bounds",
        tick=0,
        command_id="command:finish-bounds:start",
        idempotency_key="idempotency:finish-bounds:start",
        causation_id="cause:finish-bounds:start",
        correlation_id="corr:finish-bounds:start",
    ).committed
    run = authority.projector().runs["run:finish-bounds"]
    assert authority.settle_finish_run(
        run,
        tick=1,
        recipe=recipe,
        output_quantity=2,
        output_quality=0.5,
        command_id="command:finish-bounds:finish",
        idempotency_key="idempotency:finish-bounds:finish",
        causation_id="cause:finish-bounds:finish",
        correlation_id="corr:finish-bounds:finish",
    ).committed
    finish = store.read_events()[-1]
    tampered = finish.model_copy(update={"payload": {**finish.payload, **mutation}}, deep=True)
    with pytest.raises(ValueError, match="production_run_finish_output_invalid"):
        authority._projector.rebuild([*store.read_events()[:-1], tampered])


def test_finish_run_rejects_recipe_identity_mismatch() -> None:
    facility = Facility(facility_ref="facility:recipe-mismatch", plot_ref="plot:recipe-mismatch", facility_kind="bakery", condition=1)
    original = Recipe(recipe_ref="recipe:original", inputs={}, output_item="bread", duration_ticks=1)
    other = Recipe(recipe_ref="recipe:other", inputs={}, output_item="cake", duration_ticks=1)
    run = ConstructionProductionAuthority.start_run(facility=facility, recipe=original, run_ref="run:recipe-mismatch", tick=0)
    with pytest.raises(ValueError, match="production_recipe_conflict"):
        ConstructionProductionAuthority.finish_run(run, tick=1, recipe=other)
