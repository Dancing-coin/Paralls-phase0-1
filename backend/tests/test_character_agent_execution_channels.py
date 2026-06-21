from app.models.character_agent_runtime import CharacterInterpretation, CharacterIntentDecision, CharacterPrivateWorldSnapshot
from app.character_agent.execution.l4_executor import CharacterAgentL4Executor


def _snapshot() -> CharacterPrivateWorldSnapshot:
    return CharacterPrivateWorldSnapshot(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=1401,
        updated_at=1401,
        attention_targets=["obj_letter"],
    )


def _interpretation() -> CharacterInterpretation:
    return CharacterInterpretation(
        actor_id="char_c",
        interpreted_summary="the letter should be inspected",
        interpretation_type="opportunity",
        salience_score=0.9,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="high",
        attention_target="obj_letter",
        inner_prompt_candidate="inspect before speaking",
    )


def _decision() -> CharacterIntentDecision:
    return CharacterIntentDecision(
        actor_id="char_c",
        selected_intent="observe_target",
        persona_passed=True,
        logic_passed=True,
        gain_loss_passed=True,
        rationale="the letter should be inspected",
    )


def test_execution_channels_include_dialogue_body_and_physiology_shapes() -> None:
    executor = CharacterAgentL4Executor()

    plan = executor.build_execution_plan(
        snapshot=_snapshot(),
        interpretation=_interpretation(),
        decision=_decision(),
    )

    assert "dialogue_act" in plan["speech_channel"]
    assert "expression_hint" in plan["face_channel"]
    assert "posture" in plan["body_channel"]
    assert "spacing_behavior" in plan["social_spatial_channel"]
    assert "breath" in plan["physiology_channel"]


def test_execution_channels_stay_close_to_shared_actor_contracts() -> None:
    executor = CharacterAgentL4Executor()

    plan = executor.build_execution_plan(
        snapshot=_snapshot(),
        interpretation=_interpretation(),
        decision=_decision(),
    )

    first_frame = plan["actor_control_frames"][0]
    presentation_plan = plan["presentation_plan"]

    assert first_frame["controller_source"] == "agent"
    assert first_frame["control_mode"] == "agent_controlled"
    assert "action" in first_frame
    assert "focus_state" in presentation_plan
    assert "action_state" in presentation_plan
    assert "speech_state" in presentation_plan


def test_execution_channels_raise_guarding_for_medium_risk_interpretation() -> None:
    executor = CharacterAgentL4Executor()

    plan = executor.build_execution_plan(
        snapshot=_snapshot(),
        interpretation=_interpretation().model_copy(update={"risk_level": "medium"}),
        decision=_decision(),
    )

    assert plan["physiology_channel"]["guarding"] == "elevated"
    assert plan["presentation_plan"]["physiology_hint"] == "elevated"


def test_execution_channels_use_constraint_history_to_increase_distance_behavior() -> None:
    executor = CharacterAgentL4Executor()

    plan = executor.build_execution_plan(
        snapshot=_snapshot().model_copy(
            update={"recent_constraint_results": ["target is too far away"]}
        ),
        interpretation=_interpretation(),
        decision=_decision().model_copy(update={"selected_intent": "self_protect"}),
    )

    assert plan["social_spatial_channel"]["spacing_behavior"] == "increase_distance"
    assert plan["body_channel"]["posture"] == "guarded"
    assert plan["physiology_channel"]["guarding"] == "elevated"
    assert plan["presentation_plan"]["physiology_hint"] == "elevated"


def test_execution_channels_use_world_change_and_vigilance_to_keep_attention_hot() -> None:
    executor = CharacterAgentL4Executor()

    plan = executor.build_execution_plan(
        snapshot=_snapshot().model_copy(
            update={
                "recent_world_changes": ["dialogue_response:keep watch"],
                "vigilance_level": "elevated",
            }
        ),
        interpretation=_interpretation(),
        decision=_decision().model_copy(update={"selected_intent": "observe_target"}),
    )

    assert plan["social_spatial_channel"]["spacing_behavior"] == "orient_to_target"
    assert plan["face_channel"]["expression_hint"] == "heightened_vigilance"
    assert plan["body_channel"]["posture"] == "attentive_guard"
    assert plan["physiology_channel"]["breath"] == "elevated"
    assert plan["presentation_plan"]["physiology_hint"] == "elevated"


def test_execution_channels_use_body_state_hints_to_raise_physiology_without_new_requests() -> None:
    executor = CharacterAgentL4Executor()

    plan = executor.build_execution_plan(
        snapshot=_snapshot().model_copy(
            update={
                "body_state_hints": [
                    "interaction_strain:body_state_result/interaction_strain=engaged"
                ]
            }
        ),
        interpretation=_interpretation().model_copy(update={"risk_level": "low"}),
        decision=_decision(),
    )

    assert plan["action_request_bundle"]["requested_actions"] == []
    assert plan["body_channel"]["posture"] == "guarded"
    assert plan["physiology_channel"]["guarding"] == "elevated"
    assert plan["presentation_plan"]["physiology_hint"] == "elevated"
