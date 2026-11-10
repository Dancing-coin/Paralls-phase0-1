import pytest
from types import SimpleNamespace

from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.character_agent.models.simulation_seed import CharacterContinuityCommand
from app.gameplay.event_store import GameplayEventStore
from app.population_continuity.activation import ProfileActivationAuthority
from test_character_agent_activation_handoff import active_dialogue_decision
from test_character_agent_seed_continuity import command_for_char_a, command_with_memory_candidate


def test_activation_uses_confirmed_world_time_not_client_milliseconds():
    confirmed = {"world:bakery": 100}
    instance = CharacterAgentRuntime(memory_known_time_provider=confirmed.get)
    instance.set_activation_authority(
        ProfileActivationAuthority(registry=instance._profile_registry, store=GameplayEventStore())
    )
    command = command_for_char_a().model_copy(update={"world_ref": "world:bakery"})
    assert instance.apply_character_continuity_command(command).status == "committed"

    handle, receipt = instance.begin_actor_activation(
        "char_a", active_dialogue_decision(), producer_ts=100000
    )
    assert receipt.committed
    assert instance.get_memory_bundle("char_a")["event_memories"] == []
    assert instance.finish_actor_activation(handle, reason="completed").lock_released

    confirmed["world:bakery"] = 101
    handle, receipt = instance.begin_actor_activation(
        "char_a", active_dialogue_decision(), producer_ts=100001
    )
    assert receipt.committed
    assert len(instance.get_memory_bundle("char_a")["event_memories"]) == 1
    assert instance.finish_actor_activation(handle, reason="completed").lock_released
    instance.close()


def test_world_binding_survives_restart_and_rejects_changed_world(tmp_path):
    clock = {"world:bakery": 101}
    instance = CharacterAgentRuntime(storage_root=tmp_path, memory_known_time_provider=clock.get)
    command = command_for_char_a().model_copy(update={"world_ref": "world:bakery"})
    assert instance.apply_character_continuity_command(command).status == "committed"
    command = CharacterContinuityCommand.model_validate(command.model_dump(mode="json"))
    instance.close()

    instance = CharacterAgentRuntime(storage_root=tmp_path, memory_known_time_provider=clock.get)
    assert instance.apply_character_continuity_command(command).status == "idempotent_replay"
    with pytest.raises(ValueError, match="character_continuity_world_conflict"):
        instance.apply_character_continuity_command(command.model_copy(update={"world_ref": "world:other"}))
    receipt = instance.materialize_pending_seed_memories("char_a", producer_ts=1)[0]
    assert receipt.status == "committed"
    assert receipt.memory_cursor == 1
    assert len(instance.get_memory_bundle("char_a")["event_memories"]) == 1
    instance.close()


def test_missing_world_or_clock_defers_without_consuming_receipt():
    clock = {"world:other": 999999}
    instance = CharacterAgentRuntime(memory_known_time_provider=clock.get)
    command = command_for_char_a().model_copy(update={"world_ref": "world:bakery"})
    assert instance.apply_character_continuity_command(command).status == "committed"
    assert instance.materialize_pending_seed_memories("char_a", 100000)[0].refusal_reason == "temporal_knowledge_denied"
    clock["world:bakery"] = 101
    assert instance.materialize_pending_seed_memories("char_a", 100001)[0].status == "committed"
    instance.close()

    legacy = CharacterAgentRuntime(memory_known_time_provider=clock.get)
    assert legacy.apply_character_continuity_command(command_for_char_a()).status == "committed"
    assert legacy.materialize_pending_seed_memories("char_a", 100000)[0].refusal_reason == "temporal_knowledge_denied"
    assert legacy.get_memory_bundle("char_a")["event_memories"] == []
    legacy.close()


def test_exposure_denial_retains_precedence_when_world_time_unknown():
    instance = CharacterAgentRuntime(memory_known_time_provider=lambda _: None)
    command = command_with_memory_candidate(exposure_basis="not_observed")
    assert instance.apply_character_continuity_command(command).status == "committed"
    assert instance.materialize_pending_seed_memories("char_a", 100000)[0].refusal_reason == "memory_materialization_denied"
    assert instance.materialize_pending_seed_memories("char_a", 100001)[0].status == "idempotent_replay"
    instance.close()


def test_runtime_clock_provider_requires_matching_world_and_completed_migration(monkeypatch):
    from app import main

    driver = SimpleNamespace(world_runtime=SimpleNamespace(mode=SimpleNamespace(world_ref="world:bakery")),
                             migration_pending=False, current_tick=100)
    monkeypatch.setattr(main, "_population_runtime_driver", driver)
    assert main._character_memory_known_time("world:bakery") == 100
    assert main._character_memory_known_time("world:other") is None
    driver.migration_pending = True
    assert main._character_memory_known_time("world:bakery") is None
    monkeypatch.setattr(main, "_population_runtime_driver", None)
    assert main._character_memory_known_time("world:bakery") is None


def test_world_binding_cannot_be_attached_to_a_command_without_candidates():
    data = command_for_char_a().model_dump(mode="json")
    data["memory_candidate_refs"] = []
    data["exposure_evidence"]["memory_candidates"] = []
    data["world_ref"] = "world:bakery"
    with pytest.raises(ValueError, match="command_memory_world_without_candidates"):
        CharacterContinuityCommand.model_validate(data)
