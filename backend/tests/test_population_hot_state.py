from collections.abc import Iterator, Mapping

import pytest

from app.population_continuity.hot_state import PopulationDueIndex, PopulationHotState
from app.gameplay.runtime_state import CharacterGameRuntimeStateBuilder, StateGroupDefinition, StateGroupRegistry
from app.gameplay.state_group_views import StateGroupConsumerViewPolicy, StateGroupViewProjector


class _FailsWhenCopied(Mapping[str, object]):
    def __getitem__(self, key: str) -> object:
        if key != "fatigue":
            raise KeyError(key)
        raise RuntimeError("mapping_copy_failed")

    def __iter__(self) -> Iterator[str]:
        return iter(("fatigue",))

    def __len__(self) -> int:
        return 1

    def items(self):
        return (("fatigue", 0.3),)


def test_hot_state_keeps_stable_actor_identity_and_reuses_slots() -> None:
    state = PopulationHotState(("actor_a", "actor_b"))
    state.upsert("actor_a", {"last_update_tick": 10, "next_due_tick": 20, "fatigue": 0.2}, 1)
    state.remove("actor_a")
    state.upsert("actor_c", {"last_update_tick": 11, "next_due_tick": 12}, 1)

    assert state.read("actor_c")["last_update_tick"] == 11
    assert state.due_actor_ids(12) == ("actor_c",)
    rows = dict(state.export_rows())
    assert rows["actor_b"]["revision"] == 0
    assert rows["actor_c"]["last_update_tick"] == 11
    assert rows["actor_c"]["next_due_tick"] == 12
    assert rows["actor_c"]["revision"] == 1
    assert len(state._free_slots) == 0


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


def test_hot_state_returns_immutable_rows_and_rejects_same_revision_changes() -> None:
    state = PopulationHotState(("actor_a",))
    state.upsert("actor_a", {"fatigue": 0.1}, 1)
    row = state.read("actor_a")

    with pytest.raises(TypeError):
        row["fatigue"] = 0.2  # type: ignore[index]
    with pytest.raises(ValueError, match="hot_state_revision_conflict"):
        state.upsert("actor_a", {"next_due_tick": 9}, 1)

    state.upsert("actor_a", {"fatigue": 0.1}, 1)
    assert state.read("actor_a")["fatigue"] == 0.1


def test_atomic_batch_copies_every_mapping_before_any_actor_is_written() -> None:
    state = PopulationHotState(("actor_a", "actor_b"))

    with pytest.raises(RuntimeError, match="mapping_copy_failed"):
        state.commit_batch_atomic(
            (
                ("actor_a", {"fatigue": 0.4}, 0, 1),
                ("actor_b", _FailsWhenCopied(), 0, 1),
            )
        )

    assert state.read("actor_a")["revision"] == 0
    assert state.read("actor_a")["fatigue"] == 0.2
    assert state.read("actor_b")["revision"] == 0


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

    row = hot.read("character:char_a")
    assert row["character.commitments.next_due_tick"] == 120
    assert row["character.commitments.pressure"] == 0.8
    assert row["revision"] == 4
def test_due_index_same_revision_reschedule_invalidates_the_old_due_tick() -> None:
    index = PopulationDueIndex()
    index.schedule("actor_a", "obligation:1", 10, 1)
    index.schedule("actor_a", "obligation:1", 12, 1)

    assert index.due_items(10) == ()
    assert index.pop_due(10) == ()
    assert index.pop_due(12) == (("actor_a", "obligation:1", 12),)


def test_due_index_filtered_pop_preserves_independent_obligations() -> None:
    index = PopulationDueIndex()
    index.schedule("actor_a", "b0:presentation-threshold", 10, revision=0)
    index.schedule("actor_a", "b1:authorized-work", 10, revision=0)

    assert index.pop_due(10, obligation_id="b0:presentation-threshold") == (
        ("actor_a", "b0:presentation-threshold", 10),
    )
    assert index.due_items(10) == (("actor_a", "b1:authorized-work", 10),)


def test_readonly_map_rejects_a_result_when_actor_revision_changes() -> None:
    state = PopulationHotState(("actor_a",))
    state.upsert("actor_a", {"fatigue": 0.1}, 1)

    def stale(_actor_id, row):
        state.upsert("actor_a", {"fatigue": float(row["fatigue"]) + 0.1}, 2)
        return row

    with pytest.raises(ValueError, match="hot_state_revision_conflict"):
        state.map_readonly(("actor_a",), stale)


def test_readonly_map_detects_remove_and_reinsert_at_the_same_revision() -> None:
    state = PopulationHotState(("actor_a",))

    def replaced(actor_id, row):
        state.remove(actor_id)
        state.upsert(actor_id, {"fatigue": row["fatigue"]}, 0)
        return row

    with pytest.raises(ValueError, match="hot_state_revision_conflict"):
        state.map_readonly(("actor_a",), replaced)
