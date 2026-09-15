from app.gameplay.event_store import GameplayEventStore
from app.population_continuity.models import WorldModeProfile
from app.population_continuity.world import WorldContinuityRuntime


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
