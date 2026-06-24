import pytest
from pydantic import ValidationError

from app.models.character_perceived import CharacterPerceivedEvent
from app.models.siming_character_bridge import SimingCharacterCompatibilityInput
from app.models.self_body_perceived import SelfBodyPerceivedEvent
from app.services.character_agent_runtime import CharacterAgentRuntime


def _siming_bridge_input(
    *,
    message_id: str,
    producer_ts: int,
    actor_id: str = "char_a",
    presentation_hint: str = "watch env_lamp",
    pressure_hint: str | None = None,
    salience_boost: float | None = None,
    reason_scope: str | None = None,
    target_object_id: str | None = None,
    target_environment_id: str | None = "env_lamp",
) -> SimingCharacterCompatibilityInput:
    return SimingCharacterCompatibilityInput(
        message_id=message_id,
        delivery_id=f"delivery:{message_id}:{actor_id}:1",
        actor_id=actor_id,
        input_type="siming_high_level_message",
        band="fact_reveal",
        producer_ts=producer_ts,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id=f"siming:{producer_ts}",
        correlation_id=f"siming:{producer_ts}",
        presentation_hint=presentation_hint,
        pressure_hint=pressure_hint,
        salience_boost=salience_boost,
        reason_scope=reason_scope,
        target_object_id=target_object_id,
        target_environment_id=target_environment_id,
    )


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
    observatory_messages = runtime.drain_observatory_messages("char_a")
    message_types = [message["message_type"] for message in observatory_messages]
    stages = [
        message["payload"]["stage"]
        for message in observatory_messages
        if message["message_type"] == "character_agent_debug_event"
    ]

    assert "character_agent_debug_snapshot" in message_types
    assert "character_perceived_event" in stages
    assert "interpretation" in stages
    assert "decision" in stages
    assert "execution_request" in stages


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
    observatory_messages = runtime.drain_observatory_messages("char_b")
    stages = [
        message["payload"]["stage"]
        for message in observatory_messages
        if message["message_type"] == "character_agent_debug_event"
    ]

    assert commands
    assert commands[0].actor_id == "char_b"
    assert "self_body_perceived_event" in stages
    assert "interpretation" in stages
    assert "decision" in stages


def test_character_agent_runtime_accepts_targeted_siming_output() -> None:
    runtime = CharacterAgentRuntime()
    payload = _siming_bridge_input(
        message_id="msg:siming:runtime:targeted",
        producer_ts=330,
        actor_id="char_b",
        presentation_hint="watch obj_letter",
        target_object_id="obj_letter",
        target_environment_id=None,
    ).model_dump(exclude_none=True)
    payload["target_actor_id"] = "char_b"

    commands = runtime.ingest_siming_output(payload)
    observatory_messages = runtime.drain_observatory_messages("char_b")
    stages = [
        message["payload"]["stage"]
        for message in observatory_messages
        if message["message_type"] == "character_agent_debug_event"
    ]
    snapshots = [
        message["payload"]
        for message in observatory_messages
        if message["message_type"] == "character_agent_debug_snapshot"
    ]

    assert commands
    assert commands[0].actor_id == "char_b"
    assert "siming_output_event" in stages
    assert "interpretation" in stages
    assert "decision" in stages
    assert snapshots[-1]["latest_siming_summary"] == "watch obj_letter"


def test_character_agent_runtime_accepts_actor_id_only_siming_dict() -> None:
    runtime = CharacterAgentRuntime()
    payload = _siming_bridge_input(
        message_id="msg:siming:runtime:actor-id-only",
        producer_ts=330,
        actor_id="char_b",
        presentation_hint="watch obj_letter",
        target_object_id="obj_letter",
        target_environment_id=None,
    ).model_dump(exclude_none=True)

    commands = runtime.ingest_siming_output(payload)

    snapshot = runtime.get_private_snapshot("char_b")
    timeline = runtime.get_session_timeline("char_b")

    assert commands
    assert commands[0].actor_id == "char_b"
    assert snapshot is not None
    assert snapshot.actor_id == "char_b"
    assert timeline[0]["event_type"] == "siming_output_event"


def test_character_agent_runtime_accepts_bridge_input_without_optional_target_actor_id() -> None:
    runtime = CharacterAgentRuntime()

    commands = runtime.ingest_siming_output(
        SimingCharacterCompatibilityInput(
            message_id="msg:siming:runtime:1",
            delivery_id="delivery:msg:siming:runtime:1:char_a:1",
            actor_id="char_a",
            input_type="siming_high_level_message",
            band="impulse",
            producer_ts=331,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            causation_id="siming:331",
            correlation_id="siming:331",
            presentation_hint="watch obj_letter",
            target_object_id="obj_letter",
        )
    )

    snapshot = runtime.get_private_snapshot("char_a")

    assert commands
    assert commands[0].actor_id == "char_a"
    assert snapshot is not None
    assert snapshot.actor_id == "char_a"
    assert snapshot.last_siming_catalyst == "watch obj_letter"


def test_character_agent_runtime_rejects_raw_siming_dict_with_forbidden_low_level_field() -> None:
    runtime = CharacterAgentRuntime()
    payload = _siming_bridge_input(
        message_id="msg:siming:runtime:forbidden",
        producer_ts=332,
    ).model_dump(exclude_none=True)
    payload["go_to_position"] = [1.0, 2.0, 3.0]

    with pytest.raises((ValueError, ValidationError), match="forbidden compatibility input field"):
        runtime.ingest_siming_output(payload)

    assert runtime.get_session_timeline("char_a") == []
    assert runtime.drain_observatory_messages("char_a") == []


def test_character_agent_runtime_normalizes_whitespace_only_siming_hints() -> None:
    runtime = CharacterAgentRuntime()

    commands = runtime.ingest_siming_output(
        _siming_bridge_input(
            message_id="msg:siming:runtime:whitespace",
            producer_ts=332,
            presentation_hint="   ",
            pressure_hint=" \n\t ",
            reason_scope="   ",
        )
    )

    timeline = runtime.get_session_timeline("char_a")
    snapshot = runtime.get_private_snapshot("char_a")
    observatory_messages = runtime.drain_observatory_messages("char_a")
    siming_event = next(entry for entry in timeline if entry["event_type"] == "siming_output_event")
    reasoning_request = next(entry for entry in timeline if entry["event_type"] == "l2_reasoning_request")
    interpretation = next(entry["payload"] for entry in timeline if entry["event_type"] == "character_interpretation_event")
    observatory_snapshots = [
        message["payload"]
        for message in observatory_messages
        if message["message_type"] == "character_agent_debug_snapshot"
    ]

    assert commands
    assert snapshot is not None
    assert snapshot.last_siming_catalyst is None
    assert snapshot.distraction_level == "baseline"
    assert not any(signal.startswith("siming_pressure:") for signal in snapshot.unresolved_signals)
    assert not any(tag.startswith("siming_reason_scope:") for tag in snapshot.bias_tags)
    assert siming_event["payload"]["summary"] == ""
    assert siming_event["payload"]["pressure_hint"] == ""
    assert siming_event["payload"]["reason_scope"] == ""
    assert reasoning_request["payload"]["context"]["event"]["pressure_hint"] == ""
    assert reasoning_request["payload"]["context"]["event"]["reason_scope"] == ""
    assert interpretation["risk_level"] == "low"
    assert interpretation["ambiguity_level"] == "low"
    assert observatory_snapshots[-1]["latest_siming_summary"] == ""


def test_character_agent_runtime_routes_siming_high_level_hints_through_reasoning_and_planning() -> None:
    base_runtime = CharacterAgentRuntime()
    hinted_runtime = CharacterAgentRuntime()

    base_commands = base_runtime.ingest_siming_output(
        _siming_bridge_input(
            message_id="msg:siming:runtime:ab:base",
            producer_ts=333,
        )
    )
    hinted_commands = hinted_runtime.ingest_siming_output(
        _siming_bridge_input(
            message_id="msg:siming:runtime:ab:hinted",
            producer_ts=334,
            pressure_hint="crowd closing in",
            salience_boost=0.85,
            reason_scope="threat_scan",
        )
    )

    base_observatory_messages = base_runtime.drain_observatory_messages("char_a")
    hinted_observatory_messages = hinted_runtime.drain_observatory_messages("char_a")
    base_timeline = base_runtime.get_session_timeline("char_a")
    hinted_timeline = hinted_runtime.get_session_timeline("char_a")
    base_snapshot = base_runtime.get_private_snapshot("char_a")
    hinted_snapshot = hinted_runtime.get_private_snapshot("char_a")

    assert base_commands
    assert hinted_commands
    assert base_snapshot is not None
    assert hinted_snapshot is not None
    assert base_snapshot.last_siming_catalyst == "watch env_lamp"
    assert hinted_snapshot.last_siming_catalyst == "watch env_lamp"
    assert base_snapshot.distraction_level == "baseline"
    assert hinted_snapshot.distraction_level == "elevated"
    assert hinted_snapshot.current_attention_targets == ["env_lamp"]
    assert "siming_pressure:crowd closing in" in hinted_snapshot.unresolved_signals
    assert "siming_reason_scope:threat_scan" in hinted_snapshot.bias_tags
    assert hinted_snapshot.local_spatial_confidence_map["env_lamp"] == 0.85

    base_reasoning_request = next(entry for entry in base_timeline if entry["event_type"] == "l2_reasoning_request")
    hinted_reasoning_request = next(entry for entry in hinted_timeline if entry["event_type"] == "l2_reasoning_request")
    base_request_event = base_reasoning_request["payload"]["context"]["event"]
    hinted_request_event = hinted_reasoning_request["payload"]["context"]["event"]
    assert base_request_event["percept_channel"] == "siming"
    assert hinted_request_event["percept_channel"] == "siming"
    assert base_request_event["perceived_summary"] == "watch env_lamp"
    assert hinted_request_event["perceived_summary"] == "watch env_lamp"
    assert base_request_event["pressure_hint"] == ""
    assert hinted_request_event["pressure_hint"] == "crowd closing in"
    assert base_request_event["salience_boost"] is None
    assert hinted_request_event["salience_boost"] == 0.85
    assert base_request_event["reason_scope"] == ""
    assert hinted_request_event["reason_scope"] == "threat_scan"

    base_interpretation = next(entry["payload"] for entry in base_timeline if entry["event_type"] == "character_interpretation_event")
    hinted_interpretation = next(entry["payload"] for entry in hinted_timeline if entry["event_type"] == "character_interpretation_event")
    assert base_interpretation["risk_level"] == "low"
    assert hinted_interpretation["risk_level"] == "medium"
    assert base_interpretation["ambiguity_level"] == "low"
    assert hinted_interpretation["ambiguity_level"] == "medium"
    assert hinted_interpretation["salience_score"] == 0.85
    assert hinted_interpretation["salience_score"] != base_interpretation["salience_score"]
    assert base_interpretation["inner_prompt_candidate"] == "char_a:watch env_lamp"
    assert hinted_interpretation["inner_prompt_candidate"] == "char_a:threat_scan:crowd closing in:watch env_lamp"
    assert "threat_scan" in hinted_interpretation["inner_prompt_candidate"]

    base_decision = next(message["payload"] for message in base_observatory_messages if message["message_type"] == "character_agent_debug_event" and message["payload"]["stage"] == "decision")
    hinted_decision = next(message["payload"] for message in hinted_observatory_messages if message["message_type"] == "character_agent_debug_event" and message["payload"]["stage"] == "decision")
    base_execution = next(entry["payload"] for entry in base_timeline if entry["event_type"] == "character_agent_execution_request")
    hinted_execution = next(entry["payload"] for entry in hinted_timeline if entry["event_type"] == "character_agent_execution_request")

    assert base_timeline.index(base_reasoning_request) < next(index for index, entry in enumerate(base_timeline) if entry["event_type"] == "character_agent_execution_request")
    assert hinted_timeline.index(hinted_reasoning_request) < next(index for index, entry in enumerate(hinted_timeline) if entry["event_type"] == "character_agent_execution_request")
    assert base_decision["detail"]["selected_intent"]
    assert hinted_decision["detail"]["selected_intent"]
    assert base_decision["intent_label"] == base_decision["detail"]["selected_intent"]
    assert hinted_decision["intent_label"] == hinted_decision["detail"]["selected_intent"]
    assert base_execution["actor_control_frames"][0]["action"] == base_decision["detail"]["selected_intent"]
    assert hinted_execution["actor_control_frames"][0]["action"] == hinted_decision["detail"]["selected_intent"]
    assert base_execution["presentation_plan"]["action_state"]["requested_action"] == base_decision["detail"]["selected_intent"]
    assert hinted_execution["presentation_plan"]["action_state"]["requested_action"] == hinted_decision["detail"]["selected_intent"]
    assert base_execution["physiology_channel"]["guarding"] == "low"
    assert hinted_execution["physiology_channel"]["guarding"] == "elevated"
    assert base_execution["speech_channel"]["dialogue_act"] == base_decision["detail"]["selected_intent"]
    assert hinted_execution["speech_channel"]["dialogue_act"] == hinted_decision["detail"]["selected_intent"]
