from app.population_continuity.hot_state import PopulationDueIndex, PopulationHotState
from app.gameplay.runtime_state import CharacterGameRuntimeStateBuilder, StateGroupDefinition, StateGroupRegistry
from app.gameplay.state_group_views import StateGroupConsumerViewPolicy, StateGroupViewProjector


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


def test_hot_state_accepts_only_explicitly_registered_extension_columns() -> None:
    state = PopulationHotState(additional_fields=("commitment_pressure", "work_role"))
    state.upsert(
        "actor_a",
        {"commitment_pressure": 0.8, "work_role": "miller"},
        1,
    )

    assert state.read("actor_a")["commitment_pressure"] == 0.8
    assert state.read("actor_a")["work_role"] == "miller"

    try:
        state.upsert("actor_a", {"private_memory": "hidden"}, 2)
        raise AssertionError("unregistered extension column accepted")
    except ValueError as exc:
        assert str(exc) == "hot_state_field_not_allowed"


def test_hot_state_can_register_columns_by_state_group() -> None:
    state = PopulationHotState()
    state.register_group_fields("character.commitments", ("pressure", "next_due_tick"))
    state.upsert(
        "actor_a",
        {"character.commitments.pressure": 0.5, "character.commitments.next_due_tick": 120},
        1,
    )

    assert state.read("actor_a")["character.commitments.next_due_tick"] == 120


def test_hot_state_compiles_only_population_view_fields_into_columns() -> None:
    registry = StateGroupRegistry()
    registry.register(StateGroupDefinition(group_id="character.commitments", definition_version="1", projection_schema_version=1))
    state = CharacterGameRuntimeStateBuilder(registry).build(
        actor_ref="character:char_a",
        enabled_group_ids=("character.commitments",),
        group_payloads={
            "character.commitments": {
                "next_due_tick": 120,
                "pressure": 0.8,
                "private_note": "do not expose",
            }
        },
        source_revision_vector={"world:bakery": 4},
        registry_revision="registry:test",
        world_config_revision="world:test",
        active_patch_set_revision="patch:test",
    )
    view = StateGroupViewProjector(
        [
            StateGroupConsumerViewPolicy(
                group_id="character.commitments",
                population_allowed_fields=("next_due_tick", "pressure"),
            )
        ]
    ).population_view(state, allowed_group_ids=("character.commitments",))
    hot = PopulationHotState()

    hot.upsert_population_view(view, revision=4)

    assert hot.read("character:char_a") == {
        "character.commitments.next_due_tick": 120,
        "character.commitments.pressure": 0.8,
        "revision": 4,
    }
