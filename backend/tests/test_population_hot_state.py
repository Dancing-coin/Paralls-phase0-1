from app.population_continuity.hot_state import PopulationDueIndex, PopulationHotState


def test_hot_state_keeps_stable_actor_identity_and_reuses_slots() -> None:
    state = PopulationHotState(("actor_a", "actor_b"))
    state.upsert("actor_a", {"last_update_tick": 10, "next_due_tick": 20, "fatigue": 0.2}, 1)
    state.remove("actor_a")
    state.upsert("actor_c", {"last_update_tick": 11, "next_due_tick": 12}, 1)

    assert state.read("actor_c")["last_update_tick"] == 11
    assert state.due_actor_ids(12) == ("actor_c",)
    assert dict(state.export_rows()) == {
        "actor_b": {},
        "actor_c": {"last_update_tick": 11, "next_due_tick": 12, "revision": 1},
    }


def test_hot_state_rejects_unknown_fields_and_stale_revision() -> None:
    state = PopulationHotState()
    state.upsert("actor_a", {"fatigue": 0.1}, 2)

    try:
        state.upsert("actor_a", {"memory": "forbidden"}, 3)
        raise AssertionError("unknown field accepted")
    except ValueError as exc:
        assert str(exc) == "hot_state_field_not_allowed"
    try:
        state.upsert("actor_a", {"fatigue": 0.2}, 1)
        raise AssertionError("stale revision accepted")
    except ValueError as exc:
        assert str(exc) == "hot_state_revision_conflict"


def test_due_index_is_stable_and_cancellation_is_revision_safe() -> None:
    index = PopulationDueIndex()
    index.schedule("actor_b", "obligation:2", 10, 1)
    index.schedule("actor_a", "obligation:1", 10, 1)
    index.schedule("actor_a", "obligation:1", 12, 2)
    index.cancel("actor_b", "obligation:2")

    assert index.pop_due(10) == ()
    assert index.pop_due(12) == (("actor_a", "obligation:1", 12),)
