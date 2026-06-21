from app.models.character_perceived import CharacterPerceivedEvent
from app.models.self_body_perceived import SelfBodyPerceivedEvent
from app.services.character_agent_runtime import CharacterAgentRuntime
from app.main import _handle_envelope, reset_runtime_state
from app.ws_protocol import Envelope
from pathlib import Path


def test_runtime_writes_character_perceived_event_into_session_timeline() -> None:
    runtime = CharacterAgentRuntime()
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="visual",
        producer_ts=1201,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/fixed_gaze_on_target",
        source_candidate_event_id="visual_fact:1201:char_a",
        clarity_score=1.0,
        certainty_score=1.0,
    )

    runtime.ingest_character_perceived_event(event)
    timeline = runtime.get_session_timeline("char_a")

    assert len(timeline) == 4
    assert timeline[0]["event_type"] == "character_perceived_event"
    assert timeline[0]["payload"]["summary"] == "visual_fact/fixed_gaze_on_target"
    assert timeline[1]["event_type"] == "l2_reasoning_request"
    assert timeline[2]["event_type"] == "character_interpretation_event"
    assert timeline[3]["event_type"] == "character_agent_execution_request"


def test_runtime_writes_self_body_event_into_working_memory_bundle() -> None:
    runtime = CharacterAgentRuntime()
    event = SelfBodyPerceivedEvent(
        actor_id="char_b",
        body_state_class="interaction_strain",
        producer_ts=1202,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="body_state_result/interaction_strain=engaged",
        source_body_result_id="body_result:char_b:1202",
    )

    runtime.ingest_self_body_perceived_event(event)
    bundle = runtime.get_memory_bundle("char_b")

    assert bundle["working_memory"]
    assert bundle["working_memory"][0]["event_type"] == "self_body_perceived_event"


def test_runtime_builds_episodic_memory_from_character_perceived_events() -> None:
    runtime = CharacterAgentRuntime()
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="auditory",
        producer_ts=1203,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="auditory_fact/speaker_active",
        source_candidate_event_id="auditory_fact:1203:char_a",
        clarity_score=0.75,
        certainty_score=0.6,
    )

    runtime.ingest_character_perceived_event(event)
    bundle = runtime.get_memory_bundle("char_a")

    assert bundle["episodic_memories"]
    assert bundle["episodic_memories"][0]["summary"] == "auditory_fact/speaker_active"


def test_runtime_records_l2_reasoning_request_and_interpretation_events() -> None:
    runtime = CharacterAgentRuntime()
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="visual",
        producer_ts=1204,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/fixed_gaze_on_target",
        source_candidate_event_id="visual_fact:1204:char_a",
        clarity_score=1.0,
        certainty_score=1.0,
    )

    runtime.ingest_character_perceived_event(event)
    timeline = runtime.get_session_timeline("char_a")

    event_types = [entry["event_type"] for entry in timeline]
    assert "l2_reasoning_request" in event_types
    assert "character_interpretation_event" in event_types


def test_runtime_reasoning_request_uses_current_memory_bundle() -> None:
    runtime = CharacterAgentRuntime()

    runtime.ingest_character_perceived_event(
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="auditory",
            producer_ts=1205,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="auditory_fact/speaker_active",
            source_candidate_event_id="auditory_fact:1205:char_a",
            clarity_score=0.8,
            certainty_score=0.65,
        )
    )
    runtime.ingest_character_perceived_event(
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="visual",
            producer_ts=1206,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="visual_fact/fixed_gaze_on_target",
            source_candidate_event_id="visual_fact:1206:char_a",
            clarity_score=1.0,
            certainty_score=1.0,
        )
    )

    timeline = runtime.get_session_timeline("char_a")
    reasoning_requests = [entry for entry in timeline if entry["event_type"] == "l2_reasoning_request"]

    assert reasoning_requests
    latest_request = reasoning_requests[-1]
    assert latest_request["payload"]["context"]["memory"]["episodic_memories"]
    assert latest_request["payload"]["context"]["working_memory_state"]["recent_perceived_events"]


def test_interact_intent_records_self_body_event_once() -> None:
    import app.main as main

    reset_runtime_state()
    _handle_envelope(
        Envelope(
            message_type="player_input",
            payload={
                "player_id": "p1",
                "room_id": "room_demo",
                "scene_id": "scene_demo",
                "zone_id": "zone_focus",
                "actor_id": "char_c",
                "intent_type": "interact_intent",
                "producer_ts": 456,
                "target_object_id": "obj_letter",
                "interaction_type": "inspect",
            },
        )
    )

    timeline = main.character_agent_runtime.get_session_timeline("char_c")

    self_body_events = [entry for entry in timeline if entry["event_type"] == "self_body_perceived_event"]
    l2_requests = [entry for entry in timeline if entry["event_type"] == "l2_reasoning_request"]
    interpretations = [entry for entry in timeline if entry["event_type"] == "character_interpretation_event"]

    assert len(self_body_events) == 1
    assert len(l2_requests) == 1
    assert len(interpretations) == 1


def test_runtime_can_recover_timeline_and_memory_bundle_from_optional_storage_root(tmp_path: Path) -> None:
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="visual",
        producer_ts=1207,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/object_state_changed",
        source_candidate_event_id="visual_fact:1207:char_a",
        clarity_score=1.0,
        certainty_score=1.0,
    )

    runtime.ingest_character_perceived_event(event)
    reloaded = CharacterAgentRuntime(storage_root=tmp_path)

    timeline = reloaded.get_session_timeline("char_a")
    bundle = reloaded.get_memory_bundle("char_a")

    assert timeline
    assert any(entry["event_type"] == "character_perceived_event" for entry in timeline)
    assert bundle["working_memory"]
    assert bundle["episodic_memories"]


def test_runtime_can_rebuild_memory_bundle_from_session_durability_path_only(tmp_path: Path) -> None:
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="visual",
        producer_ts=1207,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/object_state_changed",
        source_candidate_event_id="visual_fact:1207:char_a",
        clarity_score=1.0,
        certainty_score=1.0,
    )

    runtime.ingest_character_perceived_event(event)
    memory_path = tmp_path / "character_agent_memory_store.json"
    if memory_path.exists():
        memory_path.unlink()
    reloaded = CharacterAgentRuntime(storage_root=tmp_path)

    timeline = reloaded.get_session_timeline("char_a")
    bundle = reloaded.get_memory_bundle("char_a")

    assert timeline
    assert any(entry["event_type"] == "character_perceived_event" for entry in timeline)
    assert bundle["working_memory"]
    assert bundle["episodic_memories"]


def test_runtime_records_l4_execution_request_for_full_auto_actor() -> None:
    runtime = CharacterAgentRuntime()
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="visual",
        producer_ts=1208,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/fixed_gaze_on_target",
        source_candidate_event_id="visual_fact:1208:char_a",
        clarity_score=1.0,
        certainty_score=1.0,
    )

    runtime.ingest_character_perceived_event(event)
    timeline = runtime.get_session_timeline("char_a")

    assert any(entry["event_type"] == "character_agent_execution_request" for entry in timeline)


def test_runtime_still_returns_legacy_goal_commands_while_recording_execution_requests() -> None:
    runtime = CharacterAgentRuntime()
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="visual",
        producer_ts=1209,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/fixed_gaze_on_target",
        source_candidate_event_id="visual_fact:1209:char_a",
        clarity_score=1.0,
        certainty_score=1.0,
    )

    commands = runtime.ingest_character_perceived_event(event)
    timeline = runtime.get_session_timeline("char_a")

    assert commands
    assert commands[0].command_type in {"observe", "speak", "approach"}
    assert any(entry["event_type"] == "character_agent_execution_request" for entry in timeline)


def test_runtime_execution_request_and_returned_commands_stay_causally_aligned() -> None:
    runtime = CharacterAgentRuntime()
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="visual",
        producer_ts=1210,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/fixed_gaze_on_target",
        source_candidate_event_id="visual_fact:1210:char_a",
        clarity_score=1.0,
        certainty_score=1.0,
    )

    commands = runtime.ingest_character_perceived_event(event)
    timeline = runtime.get_session_timeline("char_a")
    execution_requests = [entry for entry in timeline if entry["event_type"] == "character_agent_execution_request"]

    assert commands
    assert execution_requests
    latest_request = execution_requests[-1]
    assert latest_request["payload"]["actor_id"] == commands[0].actor_id


def test_player_priority_suggestion_packets_are_written_into_runtime_timeline() -> None:
    runtime = CharacterAgentRuntime()
    event = CharacterPerceivedEvent(
        actor_id="char_c",
        percept_channel="auditory",
        producer_ts=1211,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="auditory_fact/speaker_active",
        source_candidate_event_id="auditory_fact:1211:char_c",
        clarity_score=0.8,
        certainty_score=0.65,
    )

    runtime.ingest_character_perceived_event(event)
    _ = runtime.drain_suggestion_packets("char_c")
    timeline = runtime.get_session_timeline("char_c")

    assert any(entry["event_type"] == "character_agent_suggestion_packet" for entry in timeline)


def test_char_c_private_perception_path_records_snapshot_reasoning_and_suggestion_without_bypassing_to_commands() -> None:
    runtime = CharacterAgentRuntime()
    event = CharacterPerceivedEvent(
        actor_id="char_c",
        percept_channel="auditory",
        producer_ts=1212,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="auditory_fact/speaker_active",
        source_candidate_event_id="auditory_fact:1212:char_c",
        source_actor_id="char_a",
        target_actor_id="char_c",
        clarity_score=0.81,
        certainty_score=0.69,
    )

    commands = runtime.ingest_character_perceived_event(event)
    snapshot = runtime.get_private_snapshot("char_c")
    timeline = runtime.get_session_timeline("char_c")

    assert commands == []
    assert snapshot is not None
    assert snapshot.actor_id == "char_c"
    assert snapshot.audible_entities == ["auditory_fact/speaker_active"]
    assert snapshot.attention_targets == ["char_c"]
    assert snapshot.current_attention_targets == ["char_c"]
    event_types = [entry["event_type"] for entry in timeline]
    assert "character_perceived_event" in event_types
    assert "l2_reasoning_request" in event_types
    assert "character_interpretation_event" in event_types
    assert "character_agent_suggestion_packet" in event_types
    assert "character_agent_execution_request" not in event_types


def test_runtime_writes_relational_belief_event_for_targeted_actor_private_perception() -> None:
    runtime = CharacterAgentRuntime()
    event = CharacterPerceivedEvent(
        actor_id="char_c",
        percept_channel="auditory",
        producer_ts=1213,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="auditory_fact/speaker_active",
        source_candidate_event_id="auditory_fact:1213:char_c",
        source_actor_id="char_a",
        target_actor_id="char_c",
        clarity_score=0.81,
        certainty_score=0.69,
    )

    runtime.ingest_character_perceived_event(event)
    timeline = runtime.get_session_timeline("char_c")
    bundle = runtime.get_memory_bundle("char_c")

    relational_events = [entry for entry in timeline if entry["event_type"] == "relational_belief_event"]

    assert relational_events
    assert relational_events[-1]["payload"]["entity_id"] == "char_a"
    assert relational_events[-1]["payload"]["belief_type"] == "trust_level"
    assert relational_events[-1]["payload"]["value"] == "guarded"
    assert bundle["relational_memories"]
    assert bundle["relational_memories"][-1]["entity_id"] == "char_a"
    assert bundle["relational_memories"][-1]["belief_type"] == "trust_level"
    assert bundle["relational_memories"][-1]["value"] == "guarded"
