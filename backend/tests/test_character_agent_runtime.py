import pytest
from pydantic import ValidationError

from app.character_agent.execution.l4_executor import CharacterAgentL4Executor
from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.models.dynamic_state import CharacterDynamicState
from app.character_agent.models.memory_record_bundle import CharacterMemoryRecordBundle
from app.character_agent.models.working_memory_state import CharacterWorkingMemoryState
from app.character_agent.planning.l3_planner import CharacterAgentL3Service
from app.character_agent.reasoning.l2_reasoner import CharacterAgentL2Service
from app.models.character_perceived import CharacterPerceivedEvent
from app.models.character_agent_runtime import (
    CharacterIntentDecision,
    CharacterInterpretation,
    CharacterPrivateWorldSnapshot,
)
from app.models.siming_character_bridge import SimingCharacterCompatibilityInput
from app.models.self_body_perceived import SelfBodyPerceivedEvent
from app.services.character_agent_runtime import CharacterAgentRuntime


class _LocalGateway:
    def __init__(self) -> None:
        self._gateway = CharacterModelGateway()

    def run_task(
        self,
        *,
        task_kind: str,
        context: dict[str, object],
        route_override: str | None = None,
    ) -> dict[str, object]:
        return self._gateway.run_task(
            task_kind=task_kind,
            context=context,
            route_override=route_override or "local_only",
        )

    def prepare_run_request(
        self,
        *,
        task_kind: str,
        context: dict[str, object],
        route_override: str | None = None,
    ) -> dict[str, object]:
        return self._gateway.prepare_run_request(
            task_kind=task_kind,
            context=context,
            route_override=route_override or "local_only",
        )


class _FailingGateway:
    def __init__(self) -> None:
        self._gateway = CharacterModelGateway()

    def run_task(
        self,
        *,
        task_kind: str,
        context: dict[str, object],
        route_override: str | None = None,
    ) -> dict[str, object]:
        raise ValueError(f"{task_kind}:model_unavailable")

    def prepare_run_request(
        self,
        *,
        task_kind: str,
        context: dict[str, object],
        route_override: str | None = None,
    ) -> dict[str, object]:
        return self._gateway.prepare_run_request(
            task_kind=task_kind,
            context=context,
            route_override=route_override or "online_default",
        )


def _local_runtime() -> CharacterAgentRuntime:
    runtime = CharacterAgentRuntime()
    local_gateway = _LocalGateway()
    runtime._l2 = CharacterAgentL2Service(gateway=local_gateway, profile_registry=runtime._profile_registry)
    runtime._l3 = CharacterAgentL3Service(gateway=local_gateway)
    return runtime


def _failing_runtime() -> CharacterAgentRuntime:
    runtime = CharacterAgentRuntime()
    failing_gateway = _FailingGateway()
    runtime._l2 = CharacterAgentL2Service(gateway=failing_gateway, profile_registry=runtime._profile_registry)
    runtime._l3 = CharacterAgentL3Service(gateway=failing_gateway)
    return runtime


def _execution_snapshot() -> CharacterPrivateWorldSnapshot:
    return CharacterPrivateWorldSnapshot(
        actor_id="char_a",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=1800,
        updated_at=1800,
        attention_targets=["char_b"],
    )


def _execution_interpretation() -> CharacterInterpretation:
    return CharacterInterpretation(
        actor_id="char_a",
        interpreted_summary="char_b may be open to greeting",
        interpretation_type="social_signal",
        salience_score=0.9,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="high",
        attention_target="char_b",
        inner_prompt_candidate="approach calmly",
    )


def _execution_decision() -> CharacterIntentDecision:
    return CharacterIntentDecision(
        actor_id="char_a",
        selected_intent="approach",
        persona_passed=True,
        logic_passed=True,
        gain_loss_passed=True,
        rationale="char_b may be open to greeting",
    )


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
    runtime = _local_runtime()
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


def test_runtime_enters_continuity_floor_when_model_cognition_fails() -> None:
    runtime = _failing_runtime()
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="visual",
        producer_ts=300,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/fixed_gaze_on_target",
        source_candidate_event_id="visual_fact:300:char_a",
        target_actor_id="char_b",
        clarity_score=1.0,
        certainty_score=1.0,
    )

    commands = runtime.ingest_character_perceived_event(event)

    assert commands
    assert commands[0].command_type == "observe"
    timeline = runtime.get_session_timeline("char_a")
    interpretation_events = [entry for entry in timeline if entry["event_type"] == "character_interpretation_event"]
    assert interpretation_events[-1]["payload"]["cognition_status"] == "continuity_floor"
    assert interpretation_events[-1]["payload"]["fallback_mode"] == "continuity_floor"
    assert not any(
        entry["event_type"] in {"knowledge_belief_event", "social_cognition_event", "higher_order_belief_event"}
        for entry in timeline
    )
    observatory_messages = runtime.drain_observatory_messages("char_a")
    stages = [
        message["payload"]["stage"]
        for message in observatory_messages
        if message["message_type"] == "character_agent_debug_event"
    ]
    assert "cognition_unavailable" in stages
    assert "planning_unavailable" in stages


def test_runtime_assisted_mode_emits_continuity_floor_suggestion_when_model_planning_fails() -> None:
    runtime = _failing_runtime()
    event = CharacterPerceivedEvent(
        actor_id="char_c",
        percept_channel="auditory",
        producer_ts=301,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="auditory_fact/speaker_active",
        source_candidate_event_id="auditory_fact:301:char_c",
        target_actor_id="char_a",
        clarity_score=0.8,
        certainty_score=0.7,
    )

    commands = runtime.ingest_character_perceived_event(event)

    assert commands == []
    packets = runtime.drain_suggestion_packets("char_c")
    assert packets
    assert packets[0].planning_status == "continuity_floor"
    assert packets[0].fallback_mode == "continuity_floor"
    assert packets[0].recommended_intents[0] == "stay_silent"


def test_execution_plan_carries_contact_and_realization_semantic_keys() -> None:
    executor = CharacterAgentL4Executor()

    plan = executor.build_execution_plan(
        snapshot=_execution_snapshot(),
        interpretation=_execution_interpretation(),
        decision=_execution_decision(),
    )

    assert plan["execution_semantics"]["movement_intent"] == "approach"
    assert plan["execution_semantics"]["contact_phase"] == "greeting"
    assert plan["execution_semantics"]["speech_mode"] == "none"
    assert plan["execution_semantics"]["gesture_mode"] == "acknowledge"


def test_character_agent_runtime_accepts_char_c_into_the_shared_runtime_species() -> None:
    runtime = _local_runtime()
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


def test_character_agent_runtime_passes_profile_into_l3_decision_path() -> None:
    runtime = _local_runtime()
    captured: dict[str, object] = {}
    original = runtime._l3.select_intent

    def wrapped(*args, **kwargs):
        captured["kwargs"] = dict(kwargs)
        return original(*args, **kwargs)

    runtime._l3.select_intent = wrapped
    event = CharacterPerceivedEvent(
        actor_id="char_b",
        percept_channel="auditory",
        producer_ts=302,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="auditory_fact/speaker_active",
        source_candidate_event_id="auditory_fact:302:char_b",
        source_actor_id="char_a",
        target_actor_id="char_b",
        clarity_score=0.81,
        certainty_score=0.69,
    )

    runtime.ingest_character_perceived_event(event)

    kwargs = captured["kwargs"]
    assert "profile" in kwargs
    assert kwargs["profile"]["identity_core"]["character_id"] == "char_b"
    assert kwargs["profile"]["conversation_personality_layer"]["privacy_sensitivity"] == 0.71
    assert isinstance(kwargs["memory_bundle"], CharacterMemoryRecordBundle)
    assert isinstance(kwargs["working_memory_state"], CharacterWorkingMemoryState)
    assert kwargs["working_memory_state"].dynamic_state is not None
    assert isinstance(kwargs["working_memory_state"].dynamic_state, CharacterDynamicState)


def test_character_agent_runtime_player_suggestion_path_uses_continuity_floor_under_local_only_planner() -> None:
    runtime = _local_runtime()
    event = CharacterPerceivedEvent(
        actor_id="char_c",
        percept_channel="auditory",
        producer_ts=303,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="auditory_fact/speaker_active",
        source_candidate_event_id="auditory_fact:303:char_c",
        source_actor_id="char_a",
        target_actor_id="char_c",
        clarity_score=0.81,
        certainty_score=0.69,
    )

    runtime.ingest_character_perceived_event(event)

    packets = runtime.drain_suggestion_packets("char_c")
    assert packets
    assert packets[0].planning_status == "continuity_floor"
    assert packets[0].fallback_mode == "continuity_floor"
    assert packets[0].recommended_intents[0] == "observe_target"


def test_character_agent_runtime_passes_typed_working_memory_state_into_l2_reasoning_path() -> None:
    runtime = _local_runtime()
    captured: dict[str, object] = {}
    original = runtime._l2.interpret_perceived_event

    def wrapped(*args, **kwargs):
        captured["kwargs"] = dict(kwargs)
        return original(*args, **kwargs)

    runtime._l2.interpret_perceived_event = wrapped
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="auditory",
        producer_ts=304,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="auditory_fact/speaker_active",
        source_candidate_event_id="auditory_fact:304:char_a",
        source_actor_id="char_b",
        target_actor_id="char_a",
        clarity_score=0.81,
        certainty_score=0.69,
    )

    runtime.ingest_character_perceived_event(event)

    kwargs = captured["kwargs"]
    assert isinstance(kwargs["memory_bundle"], CharacterMemoryRecordBundle)
    assert isinstance(kwargs["working_memory_state"], CharacterWorkingMemoryState)
    assert kwargs["working_memory_state"].dynamic_state is not None


def test_character_agent_runtime_accepts_self_body_input() -> None:
    runtime = _local_runtime()
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
    runtime = _local_runtime()
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
    runtime = _local_runtime()
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
    runtime = _local_runtime()

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
    runtime = _local_runtime()
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
    runtime = _local_runtime()

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
    assert interpretation["ambiguity_level"] == "high"
    assert interpretation["cognition_status"] == "continuity_floor"
    assert observatory_snapshots[-1]["latest_siming_summary"] == ""


def test_character_agent_runtime_routes_siming_high_level_hints_through_reasoning_and_planning() -> None:
    base_runtime = _local_runtime()
    hinted_runtime = _local_runtime()

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
    assert hinted_interpretation["risk_level"] == "low"
    assert base_interpretation["ambiguity_level"] == "high"
    assert hinted_interpretation["ambiguity_level"] == "high"
    assert hinted_interpretation["salience_score"] == 0.85
    assert hinted_interpretation["salience_score"] != base_interpretation["salience_score"]
    assert base_interpretation["inner_prompt_candidate"] == "local_only_stub"
    assert hinted_interpretation["inner_prompt_candidate"] == "local_only_stub"
    assert base_interpretation["cognition_status"] == "continuity_floor"
    assert hinted_interpretation["cognition_status"] == "continuity_floor"

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
    assert hinted_execution["physiology_channel"]["guarding"] == "low"
    assert base_execution["speech_channel"]["dialogue_act"] == base_decision["detail"]["selected_intent"]
    assert hinted_execution["speech_channel"]["dialogue_act"] == hinted_decision["detail"]["selected_intent"]


def test_character_agent_runtime_local_l2_stays_in_stub_mode_without_writing_cognition_deltas() -> None:
    runtime = _local_runtime()
    event = CharacterPerceivedEvent(
        actor_id="char_c",
        percept_channel="auditory",
        producer_ts=335,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="auditory_fact/speaker_active",
        source_candidate_event_id="auditory_fact:335:char_c",
        source_actor_id="char_a",
        target_actor_id="char_c",
        clarity_score=0.96,
        certainty_score=0.94,
    )

    runtime.ingest_character_perceived_event(event)

    timeline = runtime.get_session_timeline("char_c")
    memory_bundle = runtime.get_memory_bundle("char_c")
    dynamic_state = runtime.get_dynamic_state("char_c")
    interpretation = next(entry["payload"] for entry in timeline if entry["event_type"] == "character_interpretation_event")

    assert interpretation["belief_deltas"] == []
    assert interpretation["social_deltas"] == []
    assert interpretation["higher_order_deltas"] == []
    assert not any(value is not None for value in interpretation["dynamic_state_delta"].values())
    assert interpretation["cognition_status"] == "continuity_floor"
    assert interpretation["fallback_mode"] == "local_only_stub"
    assert not any(entry["event_type"] == "knowledge_belief_event" for entry in timeline)
    assert not any(entry["event_type"] == "social_cognition_event" for entry in timeline)
    assert not any(entry["event_type"] == "higher_order_belief_event" for entry in timeline)
    assert not any(entry["event_type"] == "dynamic_state_event" for entry in timeline)
    assert memory_bundle["higher_order_memories"] == []
    assert dynamic_state["actor_id"] == "char_c"
    assert dynamic_state["social_pressure"] == 0.0
    assert dynamic_state["masking_pressure"] == 0.0
    assert dynamic_state["stress_load"] == 0.0


def test_character_agent_runtime_persists_goal_state_from_latest_decision() -> None:
    runtime = _local_runtime()
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="auditory",
        producer_ts=336,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="auditory_fact/speaker_active",
        source_candidate_event_id="auditory_fact:336:char_a",
        source_actor_id="char_b",
        target_actor_id="char_a",
        clarity_score=0.81,
        certainty_score=0.69,
    )

    runtime.ingest_character_perceived_event(event)

    goal_state = runtime.get_goal_state("char_a")
    goal_state_record = runtime.get_goal_state_record("char_a")
    timeline = runtime.get_session_timeline("char_a")

    assert goal_state["primary_goal"]
    assert goal_state["long_term_goal"]
    assert goal_state["mid_term_strategy"]
    assert goal_state_record is not None
    assert goal_state_record.primary_goal == goal_state["primary_goal"]
    assert goal_state_record.mid_term_strategy == goal_state["mid_term_strategy"]
    assert goal_state["urgency"] in {"low", "medium", "high"}
    assert any(entry["event_type"] == "goal_state_event" for entry in timeline)


def test_character_agent_runtime_feeds_previous_goal_portfolio_back_into_next_model_turn() -> None:
    class _GoalLoopGateway:
        def __init__(self) -> None:
            self.l3_calls = 0
            self.second_turn_goal_state: dict[str, object] | None = None

        def run_task(
            self,
            *,
            task_kind: str,
            context: dict[str, object],
            route_override: str | None = None,
        ) -> dict[str, object]:
            if task_kind == "l2_reasoning":
                if context.get("event", {}).get("source_candidate_event_id") == "auditory_fact:402:char_a":
                    self.second_turn_goal_state = dict(context.get("current_goal_state", {}))
                return {
                    "interpreted_summary": str(context.get("event", {}).get("perceived_summary", "") or "state_change"),
                    "interpretation_type": "social_signal",
                    "salience_score": 0.82,
                    "ambiguity_level": "medium",
                    "risk_level": "low",
                    "opportunity_level": "medium",
                    "attention_target": str(context.get("event", {}).get("source_actor_id", "") or "char_b"),
                    "inner_prompt_candidate": "model_reasoning",
                    "belief_deltas": [],
                    "social_deltas": [],
                    "higher_order_deltas": [],
                    "dynamic_state_delta": {},
                    "goal_hints": [],
                    "reasoning_trace_summary": "model_reasoning",
                    "cognition_status": "model",
                    "fallback_mode": None,
                }
            self.l3_calls += 1
            if self.l3_calls == 1:
                return {
                    "candidate_intents": ["share_info", "observe"],
                    "selected_intent": "share_info",
                    "recommended_intents": ["share_info"],
                    "risk_notes": [],
                    "why_this_now": "controlled disclosure keeps several motives aligned",
                    "role_consistency_hint": "speak narrowly",
                    "active_goal_tags": ["protect_secret", "clarify_intent"],
                    "active_goal_frame": {
                        "primary_goal": "protect_secret",
                        "long_term_goal": "preserve_order",
                        "mid_term_strategy": "contain_exposure",
                        "immediate_goal": "protect_secret",
                        "supporting_goals": ["clarify_intent"],
                        "blockers": [],
                        "goal_sources": ["model_deliberation"],
                        "urgency": "high",
                        "dominant_goal_id": "goal_protect_secret",
                        "preserved_goal_ids": ["goal_clarify_intent"],
                        "suppressed_goal_ids": ["goal_social_ease"],
                        "goal_arbitration_summary": "safety dominates while clarification stays active",
                        "goal_portfolio": [
                            {
                                "goal_id": "goal_protect_secret",
                                "goal": "protect_secret",
                                "horizon": "long",
                                "status": "active",
                                "priority": 0.94,
                                "urgency": "high",
                                "source": "model_deliberation",
                            },
                            {
                                "goal_id": "goal_clarify_intent",
                                "goal": "clarify_intent",
                                "horizon": "mid",
                                "status": "active",
                                "priority": 0.72,
                                "urgency": "medium",
                                "source": "model_deliberation",
                            },
                        ],
                    },
                }
            return {
                "candidate_intents": ["ask_probe", "observe"],
                "selected_intent": "ask_probe",
                "recommended_intents": ["ask_probe"],
                "risk_notes": [],
                "why_this_now": "previous safety goal remains, but clarification now takes the lead",
                "role_consistency_hint": "probe softly",
                "active_goal_tags": ["clarify_intent", "protect_secret"],
                "active_goal_frame": {
                    "primary_goal": "clarify_intent",
                    "long_term_goal": "preserve_order",
                    "mid_term_strategy": "probe_safely",
                    "immediate_goal": "clarify_intent",
                    "supporting_goals": ["protect_secret"],
                    "blockers": [],
                    "goal_sources": ["model_deliberation", "goal_state_store"],
                    "urgency": "medium",
                    "dominant_goal_id": "goal_clarify_intent",
                    "preserved_goal_ids": ["goal_protect_secret"],
                    "suppressed_goal_ids": ["goal_social_ease"],
                    "goal_arbitration_summary": "clarification temporarily dominates while secrecy remains preserved",
                    "goal_portfolio": [
                        {
                            "goal_id": "goal_clarify_intent",
                            "goal": "clarify_intent",
                            "horizon": "mid",
                            "status": "active",
                            "priority": 0.81,
                            "urgency": "medium",
                            "source": "model_deliberation",
                        },
                        {
                            "goal_id": "goal_protect_secret",
                            "goal": "protect_secret",
                            "horizon": "long",
                            "status": "active",
                            "priority": 0.78,
                            "urgency": "high",
                            "source": "goal_state_store",
                        },
                    ],
                },
            }

        def prepare_run_request(
            self,
            *,
            task_kind: str,
            context: dict[str, object],
            route_override: str | None = None,
        ) -> dict[str, object]:
            return {"task_kind": task_kind, "context": context, "route_override": route_override}

    runtime = CharacterAgentRuntime()
    gateway = _GoalLoopGateway()
    runtime._l2 = CharacterAgentL2Service(gateway=gateway, profile_registry=runtime._profile_registry)
    runtime._l3 = CharacterAgentL3Service(gateway=gateway)

    first_event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="auditory",
        producer_ts=401,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="auditory_fact/speaker_active",
        source_candidate_event_id="auditory_fact:401:char_a",
        source_actor_id="char_b",
        target_actor_id="char_a",
        clarity_score=0.82,
        certainty_score=0.71,
    )
    second_event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="auditory",
        producer_ts=402,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="auditory_fact/speaker_active",
        source_candidate_event_id="auditory_fact:402:char_a",
        source_actor_id="char_b",
        target_actor_id="char_a",
        clarity_score=0.91,
        certainty_score=0.94,
    )

    runtime.ingest_character_perceived_event(first_event)
    runtime.ingest_character_perceived_event(second_event)

    goal_state = runtime.get_goal_state("char_a")

    assert gateway.second_turn_goal_state is not None
    assert gateway.second_turn_goal_state["dominant_goal_id"] == "goal_protect_secret"
    assert gateway.second_turn_goal_state["goal_portfolio"][0]["goal_id"] == "goal_protect_secret"
    assert goal_state["dominant_goal_id"] == "goal_clarify_intent"
    assert goal_state["goal_portfolio"][1]["goal_id"] == "goal_protect_secret"


def test_background_cognition_tick_stays_off_until_enabled() -> None:
    runtime = _local_runtime()
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="auditory",
        producer_ts=470,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="auditory_fact/speaker_active",
        source_candidate_event_id="auditory_fact:470:char_a",
        source_actor_id="char_b",
        target_actor_id="char_a",
        clarity_score=0.72,
        certainty_score=0.74,
    )

    runtime.ingest_character_perceived_event(event)
    result = runtime.run_background_cognition_tick(actor_id="char_a", producer_ts=9000)

    assert result.ran is False
    assert result.reason == "background_disabled"


def test_siming_output_refreshes_weak_supervision_state() -> None:
    runtime = _local_runtime()

    runtime.ingest_siming_output(
        _siming_bridge_input(
            message_id="msg:siming:runtime:supervision",
            producer_ts=520,
            actor_id="char_a",
            presentation_hint="watch obj_letter",
            pressure_hint="crowd closing in",
            reason_scope="threat_scan",
            salience_boost=0.6,
        )
    )

    supervision_state = runtime.get_supervision_state("char_a")

    assert supervision_state["current_level"] == "weak"
    assert supervision_state["source"] == "siming_weak_default"
    assert supervision_state["active_constraints"]["pressure_theme"] == "crowd closing in"
    assert "threat_scan" in supervision_state["active_constraints"]["attention_theme"]
    assert supervision_state["active_constraints"]["caution_bias"] == "high"


def test_background_cognition_tick_runs_under_authorized_quiet_supervision_without_emitting_commands() -> None:
    class _BackgroundGateway:
        def __init__(self) -> None:
            self.l2_background_supervision: dict[str, object] | None = None
            self.l3_background_supervision: dict[str, object] | None = None

        def run_task(
            self,
            *,
            task_kind: str,
            context: dict[str, object],
            route_override: str | None = None,
        ) -> dict[str, object]:
            if task_kind == "l2_reasoning":
                if context.get("event", {}).get("event_type") == "background_reappraisal":
                    self.l2_background_supervision = dict(context.get("supervision_state", {}))
                return {
                    "interpreted_summary": "obj_letter remains unresolved after the failed attempt",
                    "interpretation_type": "background_reappraisal",
                    "salience_score": 0.66,
                    "ambiguity_level": "medium",
                    "risk_level": "low",
                    "opportunity_level": "low",
                    "attention_target": "obj_letter",
                    "inner_prompt_candidate": "recheck quietly",
                    "belief_deltas": [],
                    "social_deltas": [],
                    "higher_order_deltas": [],
                    "dynamic_state_delta": {},
                    "goal_hints": [],
                    "reasoning_trace_summary": "background_reflection",
                    "cognition_status": "model",
                    "fallback_mode": None,
                }
            self.l3_background_supervision = dict(context.get("supervision_state", {}))
            return {
                "candidate_intents": ["observe", "withhold"],
                "selected_intent": "observe",
                "recommended_intents": ["observe"],
                "risk_notes": [],
                "why_this_now": "quiet supervision allows only low-risk reappraisal",
                "role_consistency_hint": "stay cautious",
                "active_goal_tags": ["preserve_continuity", "clarify_intent"],
                "active_goal_frame": {
                    "primary_goal": "clarify_intent",
                    "long_term_goal": "preserve_order",
                    "mid_term_strategy": "probe_safely",
                    "immediate_goal": "clarify_intent",
                    "supporting_goals": ["preserve_continuity"],
                    "blockers": [],
                    "goal_sources": ["model_deliberation", "background_reflection"],
                    "urgency": "medium",
                    "dominant_goal_id": "goal_clarify_intent",
                    "preserved_goal_ids": ["goal_preserve_continuity"],
                    "suppressed_goal_ids": ["goal_conflict_escalation"],
                    "goal_arbitration_summary": "clarification survives while escalation stays suppressed",
                    "goal_portfolio": [
                        {
                            "goal_id": "goal_clarify_intent",
                            "goal": "clarify_intent",
                            "horizon": "mid",
                            "status": "active",
                            "priority": 0.78,
                            "urgency": "medium",
                            "source": "model_deliberation",
                        }
                    ],
                },
                "planning_status": "model",
                "fallback_mode": None,
            }

        def prepare_run_request(
            self,
            *,
            task_kind: str,
            context: dict[str, object],
            route_override: str | None = None,
        ) -> dict[str, object]:
            return {"task_kind": task_kind, "context": context, "route_override": route_override}

    runtime = CharacterAgentRuntime()
    gateway = _BackgroundGateway()
    runtime._l2 = CharacterAgentL2Service(gateway=gateway, profile_registry=runtime._profile_registry)
    runtime._l3 = CharacterAgentL3Service(gateway=gateway)
    runtime.set_background_cognition_enabled(True)
    runtime.set_background_mode("char_a", "active")
    runtime.ingest_character_perceived_event(
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="auditory",
            producer_ts=521,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="auditory_fact/metal_click",
            source_candidate_event_id="auditory_fact:521:char_a",
            target_object_id="obj_letter",
            clarity_score=0.71,
            certainty_score=0.73,
        )
    )
    runtime.apply_supervision_authorization(
        {
            "authorization_id": "auth:bg:1",
            "actor_id": "char_a",
            "approved_level": "medium",
            "approved_by": "strategy_service",
            "approval_reason": "contain the room and keep reflection low-cost",
            "constraints": {
                "allow_background_loop": True,
                "background_mode": "quiet",
                "min_tick_interval_ms": 1000,
                "max_tick_budget_tokens": 180,
                "attention_theme": ["safety_watch"],
                "blocked_goal_classes": ["conflict_escalation"],
                "allow_proactive_initiation": False,
                "allow_proactive_tendency_generation": False,
                "constraint_summary": "authorized quiet supervision window",
            },
            "effective_from_ts": 600,
            "expires_at_ts": 4000,
            "producer_ts": 600,
        }
    )

    result = runtime.run_background_cognition_tick(actor_id="char_a", producer_ts=2000)
    timeline = runtime.get_session_timeline("char_a")
    background_events = [entry for entry in timeline if entry["event_type"] == "character_background_cognition_event"]
    agenda_state = runtime.get_background_agenda_state("char_a")

    assert result.ran is True
    assert result.selected_intent == "observe"
    assert gateway.l2_background_supervision is not None
    assert gateway.l2_background_supervision["current_level"] == "medium"
    assert gateway.l3_background_supervision is not None
    assert gateway.l3_background_supervision["active_constraints"]["background_mode"] == "quiet"
    assert background_events
    assert agenda_state["latent_tendency"] == "observe"
    assert agenda_state["agenda_phase"] == "quiet"
    assert agenda_state["dominant_agenda_id"]
    assert agenda_state["agenda_entries"]
    assert not runtime.drain_suggestion_packets("char_a")


def test_background_cognition_tick_builds_persistent_agenda_pool_from_goals_and_tensions() -> None:
    runtime = _local_runtime()
    runtime.set_background_cognition_enabled(True)
    runtime.set_background_mode("char_a", "active")
    runtime.ingest_character_perceived_event(
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="auditory",
            producer_ts=522,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="auditory_fact/metal_click",
            source_candidate_event_id="auditory_fact:522:char_a",
            target_object_id="obj_letter",
            clarity_score=0.71,
            certainty_score=0.73,
        )
    )

    result = runtime.run_background_cognition_tick(actor_id="char_a", producer_ts=3000)
    agenda_state = runtime.get_background_agenda_state("char_a")

    assert result.ran is True
    assert agenda_state["agenda_entries"]
    assert any(entry["agenda_kind"] == "goal" for entry in agenda_state["agenda_entries"])
    assert any(entry["agenda_kind"] == "tension_watch" for entry in agenda_state["agenda_entries"])
    assert agenda_state["dominant_agenda_id"]


def test_run_scheduled_background_cognition_ticks_respects_schedulable_actor_ids() -> None:
    class _ScheduledGateway:
        def run_task(
            self,
            *,
            task_kind: str,
            context: dict[str, object],
            route_override: str | None = None,
        ) -> dict[str, object]:
            if task_kind == "l2_reasoning":
                return {
                    "interpreted_summary": "scheduled background reappraisal",
                    "interpretation_type": "background_reappraisal",
                    "salience_score": 0.4,
                    "ambiguity_level": "low",
                    "risk_level": "low",
                    "opportunity_level": "low",
                    "attention_target": None,
                    "inner_prompt_candidate": "hold",
                    "belief_deltas": [],
                    "social_deltas": [],
                    "higher_order_deltas": [],
                    "dynamic_state_delta": {},
                    "goal_hints": [],
                    "reasoning_trace_summary": "scheduled_background",
                    "cognition_status": "model",
                    "fallback_mode": None,
                }
            return {
                "candidate_intents": ["observe"],
                "selected_intent": "observe",
                "recommended_intents": ["observe"],
                "risk_notes": [],
                "why_this_now": "scheduled background review stays passive",
                "role_consistency_hint": "hold",
                "active_goal_tags": ["preserve_continuity"],
                "active_goal_frame": {
                    "primary_goal": "preserve_continuity",
                    "long_term_goal": "preserve_continuity",
                    "mid_term_strategy": "hold_position",
                    "immediate_goal": "preserve_continuity",
                    "supporting_goals": [],
                    "blockers": [],
                    "goal_sources": ["background_schedule"],
                    "urgency": "low",
                    "dominant_goal_id": "goal_preserve_continuity",
                    "preserved_goal_ids": [],
                    "suppressed_goal_ids": [],
                    "goal_arbitration_summary": "scheduled review keeps continuity stable",
                    "goal_portfolio": [],
                },
                "planning_status": "model",
                "fallback_mode": None,
            }

        def prepare_run_request(
            self,
            *,
            task_kind: str,
            context: dict[str, object],
            route_override: str | None = None,
        ) -> dict[str, object]:
            return {"task_kind": task_kind, "context": context, "route_override": route_override}

    runtime = CharacterAgentRuntime()
    gateway = _ScheduledGateway()
    runtime._l2 = CharacterAgentL2Service(gateway=gateway, profile_registry=runtime._profile_registry)
    runtime._l3 = CharacterAgentL3Service(gateway=gateway)
    runtime.set_background_cognition_enabled(True)
    runtime.set_background_mode("char_a", "active")
    runtime.set_background_mode("char_b", "active")
    runtime.ingest_character_perceived_event(
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="visual",
            producer_ts=530,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="visual_fact/object_state_changed",
            source_candidate_event_id="visual_fact:530:char_a",
            clarity_score=1.0,
            certainty_score=1.0,
        )
    )
    runtime.ingest_character_perceived_event(
        CharacterPerceivedEvent(
            actor_id="char_b",
            percept_channel="visual",
            producer_ts=531,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="visual_fact/object_state_changed",
            source_candidate_event_id="visual_fact:531:char_b",
            clarity_score=1.0,
            certainty_score=1.0,
        )
    )
    runtime.get_schedulable_actor_ids = lambda: ["char_b"]  # type: ignore[method-assign]

    results = runtime.run_scheduled_background_cognition_ticks(9000)

    assert len(results) == 1
    assert results[0].actor_id == "char_b"
    assert results[0].ran is True


def test_character_agent_runtime_exposes_typed_dynamic_state_record() -> None:
    runtime = _local_runtime()
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="auditory",
        producer_ts=346,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="auditory_fact/speaker_active",
        source_candidate_event_id="auditory_fact:346:char_a",
        source_actor_id="char_b",
        target_actor_id="char_a",
        clarity_score=0.81,
        certainty_score=0.69,
    )

    runtime.ingest_character_perceived_event(event)

    dynamic_state_record = runtime.get_dynamic_state_record("char_a")

    assert dynamic_state_record is not None
    assert dynamic_state_record.actor_id == "char_a"
    assert dynamic_state_record.social_pressure >= 0.0


def test_character_agent_runtime_goal_state_event_records_changed_fields() -> None:
    class _GoalShiftGateway:
        def __init__(self) -> None:
            self._l3_calls = 0

        def run_task(
            self,
            *,
            task_kind: str,
            context: dict[str, object],
            route_override: str | None = None,
        ) -> dict[str, object]:
            if task_kind == "l2_reasoning":
                return {
                    "interpreted_summary": str(context.get("event", {}).get("perceived_summary", "") or "state_change"),
                    "interpretation_type": "state_change",
                    "salience_score": 1.0,
                    "ambiguity_level": "low",
                    "risk_level": "low",
                    "opportunity_level": "medium",
                    "attention_target": str(context.get("event", {}).get("target_environment_id", "") or "") or None,
                    "inner_prompt_candidate": "model_reasoning",
                    "belief_deltas": [],
                    "social_deltas": [],
                    "higher_order_deltas": [],
                    "dynamic_state_delta": {},
                    "goal_hints": [],
                    "reasoning_trace_summary": "model_reasoning",
                    "cognition_status": "model",
                    "fallback_mode": None,
                }
            self._l3_calls += 1
            if self._l3_calls == 1:
                return {
                    "candidate_intents": ["observe"],
                    "selected_intent": "observe",
                    "recommended_intents": ["observe"],
                    "risk_notes": [],
                    "why_this_now": "hold baseline",
                    "role_consistency_hint": "hold position",
                    "active_goal_tags": ["preserve_optionality"],
                    "active_goal_frame": {
                        "primary_goal": "preserve_optionality",
                        "long_term_goal": "preserve_continuity",
                        "mid_term_strategy": "hold_position",
                        "immediate_goal": "preserve_optionality",
                        "supporting_goals": [],
                        "blockers": [],
                        "goal_sources": ["model_deliberation"],
                        "urgency": "low",
                    },
                }
            return {
                "candidate_intents": ["speak_public"],
                "selected_intent": "speak_public",
                "recommended_intents": ["speak_public"],
                "risk_notes": [],
                "why_this_now": "state change needs a public reaction",
                "role_consistency_hint": "stabilize the situation",
                "active_goal_tags": ["stabilize_situation"],
                "active_goal_frame": {
                    "primary_goal": "stabilize_situation",
                    "long_term_goal": "preserve_clarity",
                    "mid_term_strategy": "reestablish_control",
                    "immediate_goal": "stabilize_situation",
                    "supporting_goals": [],
                    "blockers": [],
                    "goal_sources": ["model_deliberation"],
                    "urgency": "medium",
                },
            }

        def prepare_run_request(
            self,
            *,
            task_kind: str,
            context: dict[str, object],
            route_override: str | None = None,
        ) -> dict[str, object]:
            return CharacterModelGateway().prepare_run_request(
                task_kind=task_kind,
                context=context,
                route_override=route_override or "online_default",
            )

    runtime = CharacterAgentRuntime()
    gateway = _GoalShiftGateway()
    runtime._l2 = CharacterAgentL2Service(gateway=gateway, profile_registry=runtime._profile_registry)
    runtime._l3 = CharacterAgentL3Service(gateway=gateway)
    first_event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="auditory",
        producer_ts=337,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="auditory_fact/speaker_active",
        source_candidate_event_id="auditory_fact:337:char_a",
        source_actor_id="char_b",
        target_actor_id="char_a",
        clarity_score=0.81,
        certainty_score=0.69,
    )
    second_event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="visual",
        producer_ts=338,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/light_level_drop",
        source_candidate_event_id="visual_fact:338:char_a",
        target_environment_id="env_lamp",
        clarity_score=1.0,
        certainty_score=1.0,
    )

    runtime.ingest_character_perceived_event(first_event)
    runtime.ingest_character_perceived_event(second_event)

    goal_events = [entry for entry in runtime.get_session_timeline("char_a") if entry["event_type"] == "goal_state_event"]

    assert len(goal_events) >= 2
    assert "goal_changed" in goal_events[-1]["payload"]
    assert "changed_fields" in goal_events[-1]["payload"]
    assert goal_events[0]["payload"]["transition_kind"] == "initial"
    assert goal_events[-1]["payload"]["transition_kind"] == "shifted"
    assert "transition_reason_tags" in goal_events[-1]["payload"]
    assert "primary_goal_changed" in goal_events[-1]["payload"]["transition_reason_tags"]


def test_character_agent_runtime_marks_goal_reorganization_when_primary_goal_holds_but_supporting_structure_changes() -> None:
    runtime = _local_runtime()
    first_event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="auditory",
        producer_ts=342,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="auditory_fact/speaker_active",
        source_candidate_event_id="auditory_fact:342:char_a",
        source_actor_id="char_b",
        target_actor_id="char_a",
        clarity_score=0.82,
        certainty_score=0.61,
    )
    second_event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="auditory",
        producer_ts=343,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="auditory_fact/speaker_active",
        source_candidate_event_id="auditory_fact:343:char_a",
        source_actor_id="char_b",
        target_actor_id="char_a",
        clarity_score=0.92,
        certainty_score=0.94,
    )

    runtime.ingest_character_perceived_event(first_event)
    runtime.ingest_character_perceived_event(second_event)

    goal_events = [entry for entry in runtime.get_session_timeline("char_a") if entry["event_type"] == "goal_state_event"]

    assert len(goal_events) >= 2
    assert goal_events[-1]["payload"]["transition_kind"] in {"reorganized", "maintained", "shifted", "escalated", "deescalated"}


def test_goal_transition_kind_returns_reorganized_for_same_primary_with_changed_supporting_structure() -> None:
    runtime = _local_runtime()

    transition_kind = runtime._goal_transition_kind(  # type: ignore[attr-defined]
        {
            "primary_goal": "protect_secret",
            "supporting_goals": ["clarify_intent"],
            "blockers": ["high_masking_pressure"],
            "urgency": "high",
        },
        {
            "primary_goal": "protect_secret",
            "supporting_goals": ["preserve_optionality"],
            "blockers": [],
            "urgency": "high",
        },
    )

    assert transition_kind == "reorganized"


def test_goal_transition_kind_returns_repairing_for_same_primary_when_strategy_changes_under_pressure() -> None:
    runtime = _local_runtime()

    transition_kind = runtime._goal_transition_kind(  # type: ignore[attr-defined]
        {
            "primary_goal": "protect_secret",
            "mid_term_strategy": "contain_exposure",
            "blockers": ["high_masking_pressure"],
            "urgency": "high",
        },
        {
            "primary_goal": "protect_secret",
            "mid_term_strategy": "repair_cover_story",
            "blockers": ["high_masking_pressure"],
            "urgency": "high",
        },
    )

    assert transition_kind == "repairing"


def test_goal_transition_kind_returns_recovering_for_same_primary_when_blockers_clear_after_strategy_shift() -> None:
    runtime = _local_runtime()

    transition_kind = runtime._goal_transition_kind(  # type: ignore[attr-defined]
        {
            "primary_goal": "protect_secret",
            "mid_term_strategy": "repair_cover_story",
            "blockers": ["high_masking_pressure"],
            "urgency": "high",
        },
        {
            "primary_goal": "protect_secret",
            "mid_term_strategy": "contain_exposure",
            "blockers": [],
            "urgency": "medium",
        },
    )

    assert transition_kind == "recovering"


def test_goal_transition_reason_tags_include_higher_level_reappraisal_markers() -> None:
    runtime = _local_runtime()

    tags = runtime._goal_transition_reason_tags(  # type: ignore[attr-defined]
        ["goal_sources", "supporting_goals"],
        "reorganized",
        previous_goal_state={"goal_sources": ["dynamic_state", "knowledge_state"]},
        goal_state={"goal_sources": ["dynamic_state", "l2_goal_hint:social_signal"]},
    )

    assert "goal_sources_changed" in tags
    assert "social_signal_reappraisal" in tags or "knowledge_state_reappraisal" in tags


def test_character_agent_runtime_exposes_goal_state_history_tail() -> None:
    runtime = _local_runtime()
    events = [
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="auditory",
            producer_ts=339,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="auditory_fact/speaker_active",
            source_candidate_event_id="auditory_fact:339:char_a",
            source_actor_id="char_b",
            target_actor_id="char_a",
            clarity_score=0.81,
            certainty_score=0.69,
        ),
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="visual",
            producer_ts=340,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="visual_fact/light_level_drop",
            source_candidate_event_id="visual_fact:340:char_a",
            target_environment_id="env_lamp",
            clarity_score=1.0,
            certainty_score=1.0,
        ),
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="auditory",
            producer_ts=341,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="auditory_fact/speaker_active",
            source_candidate_event_id="auditory_fact:341:char_a",
            source_actor_id="char_b",
            target_actor_id="char_a",
            clarity_score=0.92,
            certainty_score=0.94,
        ),
    ]

    for event in events:
        runtime.ingest_character_perceived_event(event)

    history = runtime.get_goal_state_history("char_a")

    assert len(history) >= 3
    assert history[0]["primary_goal"]
    assert history[-1]["primary_goal"]


def test_character_agent_runtime_exposes_typed_goal_state_history_records() -> None:
    runtime = _local_runtime()
    events = [
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="auditory",
            producer_ts=344,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="auditory_fact/speaker_active",
            source_candidate_event_id="auditory_fact:344:char_a",
            source_actor_id="char_b",
            target_actor_id="char_a",
            clarity_score=0.81,
            certainty_score=0.69,
        ),
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="visual",
            producer_ts=345,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="visual_fact/light_level_drop",
            source_candidate_event_id="visual_fact:345:char_a",
            target_environment_id="env_lamp",
            clarity_score=1.0,
            certainty_score=1.0,
        ),
    ]

    for event in events:
        runtime.ingest_character_perceived_event(event)

    current = runtime.get_goal_state_record("char_a")
    history = runtime.get_goal_state_history_records("char_a")

    assert current is not None
    assert current.actor_id == "char_a"
    assert current.primary_goal
    assert history
    assert history[-1].actor_id == "char_a"
    assert history[-1].primary_goal
