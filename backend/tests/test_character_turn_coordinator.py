from pathlib import Path

from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.character_agent.storage.session_store import CharacterAgentSessionStore
from app.models.character_perceived import CharacterPerceivedEvent


def perceived_event(*, actor_id: str, event_id: str) -> CharacterPerceivedEvent:
    return CharacterPerceivedEvent(
        actor_id=actor_id,
        percept_channel="visual",
        producer_ts=101,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="obj_letter is visible",
        source_candidate_event_id=event_id,
    )


def test_runtime_attaches_one_turn_id_to_every_pre_settlement_stage(
    tmp_path: Path,
) -> None:
    runtime = CharacterAgentRuntime(
        session_store=CharacterAgentSessionStore(tmp_path)
    )

    runtime.ingest_character_perceived_event(
        perceived_event(actor_id="char_b", event_id="p-1")
    )

    entries = runtime.get_session_timeline("char_b")
    stages = [
        entry
        for entry in entries
        if entry["event_type"] == "character_turn_stage_recorded"
    ]
    assert [entry["payload"]["stage"] for entry in stages] == [
        "context",
        "interpretation",
        "goal",
        "intent",
        "execution",
    ]
    assert {entry["payload"]["turn_id"] for entry in stages} == {
        "turn:char_b:p-1"
    }


def test_duplicate_source_event_does_not_issue_a_second_execution(
    tmp_path: Path,
) -> None:
    runtime = CharacterAgentRuntime(
        session_store=CharacterAgentSessionStore(tmp_path)
    )
    event = perceived_event(actor_id="char_b", event_id="p-duplicate")

    runtime.ingest_character_perceived_event(event)
    runtime.ingest_character_perceived_event(event)

    entries = runtime.get_session_timeline("char_b")
    assert len(
        [
            entry
            for entry in entries
            if entry["event_type"] == "character_agent_execution_request"
        ]
    ) == 1
    assert len(
        [
            entry
            for entry in entries
            if entry["event_type"] == "character_turn_context_created"
        ]
    ) == 1
