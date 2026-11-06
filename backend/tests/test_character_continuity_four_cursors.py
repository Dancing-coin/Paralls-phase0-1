from __future__ import annotations

from app.character_agent.models.simulation_seed import (
    CharacterContinuityCommand,
    CharacterMemoryCandidate,
)
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime


def _candidate(*, candidate_id: str = "memory:char_a:101") -> CharacterMemoryCandidate:
    return CharacterMemoryCandidate(
        candidate_id=candidate_id,
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
        dedup_key="char_a:frost:101",
        source_revision_vector={"world:bakery": 101},
    )


def _command(**updates: object) -> CharacterContinuityCommand:
    candidate = _candidate()
    values: dict[str, object] = {
        "command_id": "continuity:char_a:101",
        "actor_ref": "character:char_a",
        "source_owner_receipt_refs": ("receipt:frost:101",),
        "expected_character_revision": 0,
        "from_tick": 100,
        "to_tick": 101,
        "simulation_tick_cursor": 101,
        "source_revision_vector": {"world:bakery": 101, "world:organization": 55},
        "state_delta": {"need_tension": {"physiological_pressure": 0.12}},
        "memory_candidate_refs": (candidate.candidate_id,),
        "exposure_evidence": {
            "exposure_basis": "affected_directly",
            "memory_candidates": [candidate.model_dump(mode="json")],
        },
        "policy_revision": "policy:character-continuity:v1",
        "idempotency_key": "continuity:char_a:101",
    }
    values.update(updates)
    return CharacterContinuityCommand(**values)


def test_cursor_vector_carries_all_four_cursors() -> None:
    receipt = CharacterAgentRuntime().apply_character_continuity_command(_command())

    assert set(receipt.cursor_vector) == {
        "owner_cursor",
        "state_cursor",
        "experience_cursor",
        "memory_cursor",
    }


def test_owner_cursor_tracks_the_owner_stream_not_the_world_tick() -> None:
    receipt = CharacterAgentRuntime().apply_character_continuity_command(_command())

    # Highest owner revision (101), not the simulation tick (also 101) — but the
    # point is it is derived from the owner vector at all.
    assert receipt.cursor_vector["owner_cursor"] == 101


def test_owner_cursor_ignores_the_simulation_tick() -> None:
    receipt = CharacterAgentRuntime().apply_character_continuity_command(
        _command(
            command_id="continuity:char_a:201",
            idempotency_key="continuity:char_a:201",
            from_tick=200,
            to_tick=201,
            simulation_tick_cursor=201,
            source_revision_vector={"world:bakery": 7},
        )
    )

    # Owner stream is at 7 while the world tick is 201: they are not the same axis.
    assert receipt.cursor_vector["owner_cursor"] == 7
    assert receipt.cursor_vector["state_cursor"] == 201


def test_memory_cursor_stays_zero_until_materialization_commits() -> None:
    runtime = CharacterAgentRuntime()
    receipt = runtime.apply_character_continuity_command(_command())

    assert receipt.cursor_vector["memory_cursor"] == 0

    runtime.materialize_pending_seed_memories("char_a", producer_ts=101)

    assert runtime.get_character_memory_cursor("char_a") == 101


def test_experience_cursor_is_not_frozen_to_the_simulation_tick() -> None:
    runtime = CharacterAgentRuntime()
    first = runtime.apply_character_continuity_command(_command())
    second = runtime.apply_character_continuity_command(
        _command(
            command_id="continuity:char_a:201",
            idempotency_key="continuity:char_a:201",
            expected_character_revision=first.character_revision_after,
            from_tick=200,
            to_tick=201,
            simulation_tick_cursor=201,
            source_revision_vector={"world:bakery": 201},
        )
    )

    # Experience is tracked against recorded history, so it moves between commands
    # rather than being a copy of the world tick.
    assert second.cursor_vector["experience_cursor"] != first.cursor_vector["experience_cursor"]


def test_owner_cursor_reflects_a_zero_revision_vector() -> None:
    # A zeroed owner vector is legal; owner_cursor must follow it to zero rather
    # than mirroring the (much larger) simulation tick.
    receipt = CharacterAgentRuntime().apply_character_continuity_command(
        _command(
            command_id="continuity:char_a:owner0",
            idempotency_key="continuity:char_a:owner0",
            source_owner_receipt_refs=(),
            source_revision_vector={"world:bakery": 0},
            state_delta={},
            memory_candidate_refs=(),
            exposure_evidence={"exposure_basis": "affected_directly", "memory_candidates": []},
        )
    )

    assert receipt.cursor_vector["owner_cursor"] == 0
    assert receipt.cursor_vector["state_cursor"] == 101


def test_memory_cursor_never_exceeds_materialized_ticks() -> None:
    runtime = CharacterAgentRuntime()
    runtime.apply_character_continuity_command(_command())

    # Nothing materialized yet, so no cursor may claim memory progress.
    assert runtime.get_character_memory_cursor("char_a") == 0
