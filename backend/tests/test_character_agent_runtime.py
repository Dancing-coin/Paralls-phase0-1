from app.models.character_perceived import CharacterPerceivedEvent
from app.models.self_body_perceived import SelfBodyPerceivedEvent
from app.services.character_agent_runtime import CharacterAgentRuntime


def test_character_agent_runtime_turns_perceived_event_into_output() -> None:
    runtime = CharacterAgentRuntime()
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="visual",
        producer_ts=300,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/fixed_gaze_on_target",
        source_candidate_event_id="visual_fact:300:char_a",
        clarity_score=1.0,
        certainty_score=1.0,
    )

    commands = runtime.ingest_character_perceived_event(event)

    assert commands
    assert commands[0].actor_id == "char_a"
    assert commands[0].command_type in {
        "look_at",
        "approach",
        "observe",
        "interact",
        "speak",
    }


def test_character_agent_runtime_accepts_char_c_into_the_shared_runtime_species() -> None:
    runtime = CharacterAgentRuntime()
    event = CharacterPerceivedEvent(
        actor_id="char_c",
        percept_channel="visual",
        producer_ts=301,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/fixed_gaze_on_target",
        source_candidate_event_id="visual_fact:301:char_c",
        clarity_score=1.0,
        certainty_score=1.0,
    )

    commands = runtime.ingest_character_perceived_event(event)
    snapshot = runtime.get_private_snapshot("char_c")

    assert runtime.supports_actor("char_c")
    assert snapshot is not None
    assert snapshot.actor_id == "char_c"
    assert commands == []


def test_character_agent_runtime_accepts_self_body_input() -> None:
    runtime = CharacterAgentRuntime()
    event = SelfBodyPerceivedEvent(
        actor_id="char_b",
        body_state_class="interaction_strain",
        producer_ts=320,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="body_state_result/interaction_strain=engaged",
        source_body_result_id="body_result:char_b:320",
    )

    commands = runtime.ingest_self_body_perceived_event(event)

    assert commands
    assert commands[0].actor_id == "char_b"


def test_character_agent_runtime_accepts_targeted_siming_output() -> None:
    runtime = CharacterAgentRuntime()

    commands = runtime.ingest_siming_output(
        {
            "room_id": "room_demo",
            "scene_id": "scene_demo",
            "zone_id": "zone_focus",
            "target_actor_id": "char_b",
            "target_object_id": "obj_letter",
            "presentation_hint": "watch obj_letter",
            "producer_ts": 330,
            "causation_id": "siming:330",
            "correlation_id": "siming:330",
        }
    )

    assert commands
    assert commands[0].actor_id == "char_b"
