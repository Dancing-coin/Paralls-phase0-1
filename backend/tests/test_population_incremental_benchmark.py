from app.population_continuity.hot_state import PopulationHotState


def test_hot_state_benchmark_protocol_reports_full_and_tail_work() -> None:
    state = PopulationHotState(f"actor_{index}" for index in range(1000))
    for index in range(1000):
        state.upsert(
            f"actor_{index}",
            {"last_update_tick": index, "next_due_tick": index + 10},
            index,
        )

    full = state.export_rows()
    tail = tuple(row for actor_id, row in full if int(row["next_due_tick"]) >= 1000)

    assert len(full) == 1000
    assert len(tail) == 10
    assert len(tail) < len(full)
