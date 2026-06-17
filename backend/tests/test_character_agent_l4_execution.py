from app.models.character_agent_runtime import CharacterInterpretation, CharacterIntentDecision, CharacterPrivateWorldSnapshot
from app.character_agent.execution.l4_executor import CharacterAgentL4Executor
from app.character_agent.execution.l4_adapter import CharacterAgentL4Adapter


def _snapshot() -> CharacterPrivateWorldSnapshot:
    return CharacterPrivateWorldSnapshot(
        actor_id="char_b",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=1400,
        updated_at=1400,
        attention_targets=["char_a"],
    )


def _interpretation() -> CharacterInterpretation:
    return CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="char_a may be speaking nearby",
        interpretation_type="social_signal",
        salience_score=0.88,
        ambiguity_level="medium",
        risk_level="low",
        opportunity_level="medium",
        attention_target="char_a",
        inner_prompt_candidate="listen before responding",
    )


def _decision() -> CharacterIntentDecision:
    return CharacterIntentDecision(
        actor_id="char_b",
        selected_intent="speak_public",
        persona_passed=True,
        logic_passed=True,
        gain_loss_passed=True,
        rationale="char_a may be speaking nearby",
    )


def test_l4_executor_builds_five_channel_execution_plan() -> None:
    executor = CharacterAgentL4Executor()

    plan = executor.build_execution_plan(
        snapshot=_snapshot(),
        interpretation=_interpretation(),
        decision=_decision(),
    )

    assert plan["actor_id"] == "char_b"
    assert "speech_channel" in plan
    assert "face_channel" in plan
    assert "body_channel" in plan
    assert "social_spatial_channel" in plan
    assert "physiology_channel" in plan


def test_l4_executor_keeps_actor_facing_ingress_explicit() -> None:
    executor = CharacterAgentL4Executor()

    plan = executor.build_execution_plan(
        snapshot=_snapshot(),
        interpretation=_interpretation(),
        decision=_decision(),
    )

    assert "actor_control_frames" in plan
    assert "presentation_plan" in plan
    assert "action_request_bundle" in plan


def test_l4_adapter_derives_legacy_commands_from_executor_bundle() -> None:
    executor = CharacterAgentL4Executor()
    adapter = CharacterAgentL4Adapter()

    plan = executor.build_execution_plan(
        snapshot=_snapshot(),
        interpretation=_interpretation(),
        decision=_decision(),
    )

    commands = adapter.build_commands_from_execution_plan(plan)

    assert commands
    assert commands[0].command_type == "speak"
    assert commands[0].actor_id == "char_b"
    assert commands[0].target_actor_id == "char_a"
    assert commands[0].producer_ts == 1400
    assert commands[0].causation_id == "character_agent:1400:char_b"
    assert commands[0].correlation_id == "character_agent:1400:char_b"
    assert commands[0].causation_id == commands[0].correlation_id
    assert commands[0].role_state_hint == "speak"


def test_l4_adapter_uses_frame_trace_fields_when_present() -> None:
    adapter = CharacterAgentL4Adapter()
    plan = {
        "actor_id": "char_b",
        "actor_control_frames": [
            {
                "actor_id": "char_b",
                "producer_ts": 1505,
                "causation_id": "character_agent:1505:char_b",
                "correlation_id": "character_agent:1505:char_b",
                "controller_source": "agent",
                "control_mode": "agent_controlled",
                "target_ref": "char_a",
                "action": "speak_public",
                "gait": "walk",
            }
        ],
        "presentation_plan": {
            "physiology_hint": "stable",
        },
        "action_request_bundle": {
            "requested_actions": [
                {
                    "request_type": "speak_public",
                    "actor_id": "char_b",
                    "target_actor_id": "char_a",
                }
            ]
        },
    }

    commands = adapter.build_commands_from_execution_plan(plan)

    assert commands[0].producer_ts == 1505
    assert commands[0].causation_id == "character_agent:1505:char_b"
    assert commands[0].correlation_id == "character_agent:1505:char_b"


def test_l4_adapter_preserves_role_state_hint_from_plan_when_present() -> None:
    adapter = CharacterAgentL4Adapter()
    plan = {
        "actor_id": "char_b",
        "actor_control_frames": [
            {
                "actor_id": "char_b",
                "producer_ts": 1506,
                "causation_id": "character_agent:1506:char_b",
                "correlation_id": "character_agent:1506:char_b",
                "controller_source": "agent",
                "control_mode": "agent_controlled",
                "target_ref": "char_a",
                "action": "observe_target",
                "gait": "walk",
            }
        ],
        "presentation_plan": {
            "physiology_hint": "stable",
        },
        "action_request_bundle": {
            "requested_actions": [
                {
                    "request_type": "interact",
                    "actor_id": "char_b",
                    "target_object_id": "obj_letter",
                    "interaction_type": "inspect",
                }
            ]
        },
    }

    commands = adapter.build_commands_from_execution_plan(plan)

    assert commands[0].role_state_hint == "inspect"


def test_l4_adapter_preserves_dialogue_text_for_speech_requests() -> None:
    adapter = CharacterAgentL4Adapter()
    plan = {
        "actor_id": "char_b",
        "actor_control_frames": [
            {
                "actor_id": "char_b",
                "producer_ts": 1507,
                "causation_id": "character_agent:1507:char_b",
                "correlation_id": "character_agent:1507:char_b",
                "controller_source": "agent",
                "control_mode": "agent_controlled",
                "target_ref": "char_a",
                "action": "speak_public",
                "gait": "walk",
            }
        ],
        "presentation_plan": {
            "physiology_hint": "stable",
            "speech_state": {
                "utterance_request": "Look at the letter.",
            },
        },
        "action_request_bundle": {
            "requested_actions": [
                {
                    "request_type": "speak_public",
                    "actor_id": "char_b",
                    "target_actor_id": "char_a",
                    "content": "Look at the letter.",
                }
            ]
        },
    }

    commands = adapter.build_commands_from_execution_plan(plan)

    assert commands[0].dialogue_text == "Look at the letter."
