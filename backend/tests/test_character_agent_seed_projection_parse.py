from __future__ import annotations

import pytest

from app.character_agent.models.simulation_seed import (
    CharacterMemoryCandidate,
    CharacterSimulationSeedCandidate,
)
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime


def _seed(**updates: object) -> CharacterSimulationSeedCandidate:
    values: dict[str, object] = {
        "seed_id": "seed:character:char_a:projection:char_a:W0",
        "actor_ref": "character:char_a",
        "world_ref": "world:bakery",
        "from_tick": 100,
        "to_tick": 101,
        "source_event_refs": ("evt:frost:101",),
        "source_owner_receipt_refs": ("receipt:frost:101",),
        "state_deltas": {"supply_pressure": 0.08},
        "visibility_scope": "actor:self",
        "privacy_disposition": "actor_private",
        "source_revision_vector": {"world:bakery": 101},
        "ruleset_revision": "ruleset:v1",
        "selector_revision": "selector:v1",
        "deterministic_seed": "sha256:seed",
        "owner_effect_status": "settled",
        "idempotency_key": "seed:char_a:101",
        "presentation_seed": {"behavior_kind": "schedule_gated_supply"},
    }
    values.update(updates)
    return CharacterSimulationSeedCandidate(**values)


def test_seed_without_declared_command_type_yields_no_goal_command() -> None:
    runtime = CharacterAgentRuntime()
    # Presentation-only seeds carry hints, not actions: no command is invented.
    assert runtime.ingest_seed_projection(_seed()) == []


def test_seed_with_declared_command_type_parses_into_actor_local_command() -> None:
    runtime = CharacterAgentRuntime()
    seed = _seed(
        presentation_seed={
            "behavior_kind": "schedule_gated_supply",
            "command_type": "go_to",
            "target_environment_id": "env:bakery",
            "ttl_ms": 2500,
        }
    )

    commands = runtime.ingest_seed_projection(seed)

    assert len(commands) == 1
    command = commands[0]
    assert command.actor_id == "char_a"
    assert command.command_type == "go_to"
    assert command.target_environment_id == "env:bakery"
    assert command.ttl_ms == 2500
    assert command.producer_ts == 101
    assert command.idempotency_key == "seed:char_a:101"
    assert command.causation_id == seed.seed_id


def test_seed_projection_is_idempotent_for_the_same_seed() -> None:
    runtime = CharacterAgentRuntime()
    seed = _seed(presentation_seed={"command_type": "observe", "target_object_id": "obj:bread"})

    first = runtime.ingest_seed_projection(seed)
    second = runtime.ingest_seed_projection(seed)

    assert [command.model_dump() for command in first] == [
        command.model_dump() for command in second
    ]


def test_seed_projection_accepts_mapping_payload() -> None:
    runtime = CharacterAgentRuntime()
    seed = _seed(presentation_seed={"command_type": "observe"})

    commands = runtime.ingest_seed_projection(seed.model_dump(mode="json"))

    assert len(commands) == 1
    assert commands[0].command_type == "observe"


def test_seed_projection_rejects_unsupported_actor() -> None:
    runtime = CharacterAgentRuntime()
    seed = _seed(
        seed_id="seed:character:char_unknown:1",
        actor_ref="character:char_unknown",
        presentation_seed={"command_type": "observe"},
    )

    assert runtime.ingest_seed_projection(seed) == []


def test_seed_projection_ignores_invalid_payload() -> None:
    runtime = CharacterAgentRuntime()

    assert runtime.ingest_seed_projection({"actor_ref": "character:char_a"}) == []


def test_seed_projection_rejects_unregistered_command_type() -> None:
    runtime = CharacterAgentRuntime()
    seed = _seed(presentation_seed={"command_type": "teleport_boss"})

    assert runtime.ingest_seed_projection(seed) == []


def test_seed_projection_does_not_materialize_memory() -> None:
    runtime = CharacterAgentRuntime()
    candidate = CharacterMemoryCandidate(
        candidate_id="memory:char_a:101",
        actor_ref="character:char_a",
        candidate_kind="event_experience",
        source_event_refs=("evt:frost:101",),
        event_valid_at=101,
        event_recorded_at=101,
        knowledge_available_at=101,
        exposure_basis="affected_directly",
        summary="frost reduced the crop supply",
        confidence=0.8,
        salience=0.7,
        visibility_scope="actor:self",
        privacy_disposition="actor_private",
        materialization_policy="on_activation",
        dedup_key="char_a:frost:seed",
    )
    seed = _seed(
        memory_candidates=(candidate,),
        presentation_seed={"command_type": "observe"},
    )

    runtime.ingest_seed_projection(seed)

    # Parsing a seed is a projection read; it must never stage five-pool memory.
    assert runtime.get_pending_seed_candidates("char_a") == []
