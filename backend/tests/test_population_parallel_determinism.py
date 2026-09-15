from app.population_continuity.hot_state import PopulationHotState


def test_parallel_readonly_evaluation_is_deterministic_and_sorted() -> None:
    state = PopulationHotState(("actor_c", "actor_a", "actor_b"))
    for index, actor_id in enumerate(("actor_a", "actor_b", "actor_c"), 1):
        state.upsert(actor_id, {"fatigue": index / 10}, index)

    def evaluate(actor_id: str, row: dict[str, object]) -> tuple[str, float]:
        return actor_id, float(row["fatigue"]) * 2

    assert state.map_readonly(("actor_c", "actor_a", "actor_b"), evaluate, workers=1) == state.map_readonly(
        ("actor_c", "actor_a", "actor_b"), evaluate, workers=3
    )
