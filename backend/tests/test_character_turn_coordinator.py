from pathlib import Path

from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.character_agent.models.mind_frame import CharacterMindFrame
from app.character_agent.models.turn_context import CharacterTurnContext
from app.character_agent.services.character_turn_coordinator import CharacterTurnCoordinator
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


def test_coordinator_freezes_frame_at_turn_boundary(tmp_path: Path) -> None:
    store = CharacterAgentSessionStore(tmp_path)
    coordinator = CharacterTurnCoordinator(store)
    turn = CharacterTurnContext.begin(
        actor_id="char_a", source_event_ref="event:1", producer_ts=1,
        causation_id="cause:1", correlation_id="corr:1",
        input_revision_vector={"l1": 1}, memory_revision_vector={"memory": 1},
        policy_revision="policy:1", snapshot_revision=1, branch_id="branch:main",
    )
    frame = CharacterMindFrame(actor_id="char_a", mind_turn_id="mind_turn:char_a:1")

    frozen = coordinator.freeze_frame(context=turn, frame=frame)

    assert frozen.turn_id == turn.turn_id
    assert frozen.frame_digest


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
