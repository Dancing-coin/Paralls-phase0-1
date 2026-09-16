import pytest

from app.gameplay.event_store import GameplayEventStore
from app.population_continuity.models import WorldModeProfile
from app.population_continuity.roster import PopulationRoster
from app.population_continuity.world import WorldContinuityRuntime


def _world() -> WorldContinuityRuntime:
    world = WorldContinuityRuntime(
        store=GameplayEventStore(),
        mode=WorldModeProfile(
            world_ref="world:cache-release",
            mode="simulation",
            revision="mode:1",
            cadence_class="daily",
            batch_limit=3,
            catch_up_limit=3,
            wake_budget=3,
            survival_mode="simulation",
            degraded_threshold=6,
        ),
        roster=PopulationRoster(actor_ids=("resident-a", "resident-b", "resident-c")),
    )
    world.resume()
    return world


def test_population_cadence_and_projection_are_reused_for_same_source_window() -> None:
    store = GameplayEventStore()
    world = WorldContinuityRuntime(
        store=store,
        mode=WorldModeProfile(
            world_ref="world:cache",
            mode="simulation",
            revision="mode:1",
            cadence_class="daily",
            batch_limit=2,
            catch_up_limit=2,
            wake_budget=2,
            survival_mode="simulation",
            degraded_threshold=6,
        ),
    )
    world.resume()

    first = world.build_population_cadence(window_start=0, window_end=10, cadence_id="cadence:cache:0")
    second = world.build_population_cadence(window_start=0, window_end=10, cadence_id="cadence:cache:0")
    assert first is second
    assert world.build_population_projections(first) is world.build_population_projections(first)

    for start in range(10, 310, 10):
        cadence = world.build_population_cadence(window_start=start, window_end=start + 10)
        world.build_population_projections(cadence)
    assert len(world._cadence_cache) == 1
    assert len(world._projection_cache) == 1


def test_confirmed_preview_is_released_before_new_evaluation_and_retry_is_equivalent(
    monkeypatch,
) -> None:
    world = _world()
    first = world.build_population_cadence(
        window_start=0, window_end=10, cadence_id="cadence:cache-release:0"
    )
    world.build_population_projections(first)
    world.confirm_population_cadence(first)
    assert world._projection_cache
    assert world._preview_results

    second = world.build_population_cadence(
        window_start=10, window_end=20, cadence_id="cadence:cache-release:10"
    )
    original_map = world.population_hot_state.map_readonly
    failed_once = False

    def fail_after_evaluation(*args, **kwargs):
        nonlocal failed_once
        assert world._projection_cache == {}
        assert world._preview_results == {}
        evaluated = original_map(*args, **kwargs)
        if not failed_once:
            failed_once = True
            raise RuntimeError("new_window_evaluation_failed")
        return evaluated

    monkeypatch.setattr(world.population_hot_state, "map_readonly", fail_after_evaluation)
    with pytest.raises(RuntimeError, match="new_window_evaluation_failed"):
        world.build_population_projections(second)

    retried = world.build_population_projections(second)
    receipt = world.confirm_population_cadence(second)

    reference = _world()
    reference_first = reference.build_population_cadence(
        window_start=0, window_end=10, cadence_id="cadence:cache-release:0"
    )
    reference.confirm_population_cadence(reference_first)
    reference_second = reference.build_population_cadence(
        window_start=10, window_end=20, cadence_id="cadence:cache-release:10"
    )
    expected = reference.build_population_projections(reference_second)
    expected_receipt = reference.confirm_population_cadence(reference_second)

    assert [item.model_dump(mode="json") for item in retried] == [
        item.model_dump(mode="json") for item in expected
    ]
    assert receipt.projection_digest == expected_receipt.projection_digest
    assert receipt.result_digest == expected_receipt.result_digest


def test_unconfirmed_preview_is_retained_when_other_window_evaluation_fails(
    monkeypatch,
) -> None:
    world = _world()
    first = world.build_population_cadence(
        window_start=0, window_end=10, cadence_id="cadence:cache-unconfirmed:0"
    )
    preview = world.build_population_projections(first)
    projection_cache = dict(world._projection_cache)
    preview_results = dict(world._preview_results)
    second = world.build_population_cadence(
        window_start=10, window_end=20, cadence_id="cadence:cache-unconfirmed:10"
    )

    def fail_evaluation(*_args, **_kwargs):
        assert world._projection_cache == projection_cache
        assert world._preview_results == preview_results
        raise RuntimeError("unconfirmed_new_window_failed")

    monkeypatch.setattr(world.population_hot_state, "map_readonly", fail_evaluation)
    with pytest.raises(RuntimeError, match="unconfirmed_new_window_failed"):
        world.build_population_projections(second)

    assert world.build_population_projections(first) is preview


def test_unconfirmed_preview_after_prior_confirmation_survives_competing_failure(
    monkeypatch,
) -> None:
    world = _world()
    confirmed = world.build_population_cadence(
        window_start=0, window_end=10, cadence_id="cadence:cache-prior-confirmed:0"
    )
    world.confirm_population_cadence(confirmed)
    pending = world.build_population_cadence(
        window_start=10, window_end=20, cadence_id="cadence:cache-pending:10"
    )
    preview = world.build_population_projections(pending)
    projection_cache = dict(world._projection_cache)
    preview_results = dict(world._preview_results)
    competing = world.build_population_cadence(
        window_start=10, window_end=30, cadence_id="cadence:cache-competing:10"
    )

    def fail_evaluation(*_args, **_kwargs):
        assert world._projection_cache == projection_cache
        assert world._preview_results == preview_results
        raise RuntimeError("competing_window_failed")

    monkeypatch.setattr(world.population_hot_state, "map_readonly", fail_evaluation)
    with pytest.raises(RuntimeError, match="competing_window_failed"):
        world.build_population_projections(competing)

    assert world.build_population_projections(pending) is preview
