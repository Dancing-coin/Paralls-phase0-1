from app.models.character_agent_runtime import (
    CharacterIntentDecision,
    CharacterInterpretation,
    CharacterGoalCommand,
    CharacterIntentFrame,
    CharacterPrivateWorldSnapshot,
)


def test_character_private_world_snapshot_defaults() -> None:
    snapshot = CharacterPrivateWorldSnapshot(
        actor_id="char_a",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=100,
        updated_at=100,
    )

    assert snapshot.visible_entities == []
    assert snapshot.body_state_hints == []
    assert snapshot.unresolved_signals == []
    assert snapshot.active_anomalies == []
    assert snapshot.clarity_score == 1.0
    assert snapshot.certainty_score == 1.0


def test_character_goal_command_shape() -> None:
    command = CharacterGoalCommand(
        actor_id="char_b",
        command_type="observe",
        ttl_ms=1200,
        causation_id="character_agent:120",
        correlation_id="character_agent:120",
        producer_ts=120,
        target_actor_id="char_c",
        execution_payload={
            "actor_id": "char_b",
            "actor_control_frames": [{"actor_id": "char_b"}],
            "presentation_plan": {"actor_id": "char_b"},
            "action_request_bundle": {"requested_actions": []},
        },
    )

    payload = command.model_dump(exclude_none=True)

    assert payload["command_type"] == "observe"
    assert payload["target_actor_id"] == "char_c"
    assert payload["execution_payload"]["actor_id"] == "char_b"


def test_character_intent_frame_shape() -> None:
    frame = CharacterIntentFrame(
        actor_id="char_c",
        controller_source="agent",
        ttl_ms=300,
        causation_id="intent:300",
        correlation_id="intent:300",
        move_local=[0.0, 1.0],
        gait="walk",
        action="observe",
    )

    payload = frame.model_dump(exclude_none=True)

    assert payload["controller_source"] == "agent"
    assert payload["gait"] == "walk"


def test_character_interpretation_and_intent_decision_shape() -> None:
    interpretation = CharacterInterpretation(
        actor_id="char_a",
        interpreted_summary="visual_fact/fixed_gaze_on_target",
        interpretation_type="opportunity",
        salience_score=0.7,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="medium",
        attention_target="char_c",
        inner_prompt_candidate="char_a:visual_fact/fixed_gaze_on_target",
    )
    decision = CharacterIntentDecision(
        actor_id="char_a",
        selected_intent="observe_target",
        persona_passed=True,
        logic_passed=True,
        gain_loss_passed=True,
        rationale=interpretation.interpreted_summary,
    )

    assert interpretation.actor_id == "char_a"
    assert decision.selected_intent == "observe_target"
