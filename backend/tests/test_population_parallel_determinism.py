from app.population_continuity.continuous import advance_b0_row
from app.population_continuity.daily_rhythm_projection import DailyRhythmProjection
from app.population_continuity.hot_state import PopulationHotState
from app.gameplay.daily_rhythm_runtime import DailyRhythmRuntime, create_daily_rhythm_event_schema_registry
from app.gameplay.event_store import GameplayEventStore


def make_projection(actor_ids):
    store = GameplayEventStore(event_schema_registry=create_daily_rhythm_event_schema_registry())

    class Bus:
        def publish(self, _event):
            pass

    runtime = DailyRhythmRuntime(Bus(), store=store)
    for actor_id in actor_ids:
        runtime.initialize(actor_id)
    return DailyRhythmProjection(store)


def test_parallel_readonly_evaluation_is_deterministic_and_sorted() -> None:
    actor_ids = ("actor_c", "actor_a", "actor_b")
    state = PopulationHotState(actor_ids, daily_rhythm_projection=make_projection(actor_ids))

    def evaluate(actor_id: str, row: dict[str, object]) -> tuple[str, float]:
        return actor_id, float(row["fatigue"]) * 2

    assert state.map_readonly(("actor_c", "actor_a", "actor_b"), evaluate, workers=1) == state.map_readonly(
        ("actor_c", "actor_a", "actor_b"), evaluate, workers=3
    )


def test_real_b0_rule_is_equal_across_worker_and_batch_shapes() -> None:
    actor_ids = tuple(f"actor_{index:04d}" for index in range(1_000))
    state = PopulationHotState(actor_ids, daily_rhythm_projection=make_projection(actor_ids))

    def evaluate(actor_id, row):
        return advance_b0_row(
            actor_id=actor_id,
            row=row,
            window_start=7_200,
            window_end=93_600,
        )

    serial = state.map_readonly(actor_ids, evaluate, workers=1, batch_size=1_000)
    parallel_small = state.map_readonly(actor_ids, evaluate, workers=4, batch_size=17)
    parallel_large = state.map_readonly(reversed(actor_ids), evaluate, workers=3, batch_size=256)

    assert serial == parallel_small == parallel_large
    assert all(result.to_tick == 93_600 for result in serial)
    assert all(result.actor_revision_before == 0 for result in serial)
