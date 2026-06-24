import pytest

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
    assert "hesitation_hint" in plan["body_channel"]
    assert "spacing_behavior" in plan["social_spatial_channel"]
    assert "orientation_mode" in plan["social_spatial_channel"]
    assert "breath" in plan["physiology_channel"]
    assert "state_band" in plan["physiology_channel"]


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
    assert "motion_state" in presentation_plan
    assert "action_state" in presentation_plan
    assert "speech_state" in presentation_plan
    assert "physiology_state" in presentation_plan


def test_execution_channels_raise_guarding_for_medium_risk_interpretation() -> None:
    executor = CharacterAgentL4Executor()

    plan = executor.build_execution_plan(
        snapshot=_snapshot(),
        interpretation=_interpretation().model_copy(update={"risk_level": "medium"}),
        decision=_decision(),
    )

    assert plan["physiology_channel"]["guarding"] == "elevated"
    assert plan["presentation_plan"]["physiology_hint"] == "elevated"
    assert plan["physiology_channel"]["state_band"] == "elevated"


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
    assert plan["physiology_channel"]["state_band"] == "guarded"
    assert plan["social_spatial_channel"]["orientation_mode"] == "increase_distance"


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
    assert plan["social_spatial_channel"]["orientation_mode"] == "hold_attention"


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
    assert plan["physiology_channel"]["state_band"] == "guarded"


def test_execution_channels_surface_hesitation_from_ambiguity_without_new_actions() -> None:
    executor = CharacterAgentL4Executor()

    plan = executor.build_execution_plan(
        snapshot=_snapshot(),
        interpretation=_interpretation().model_copy(update={"ambiguity_level": "medium"}),
        decision=_decision().model_copy(update={"selected_intent": "observe_target"}),
    )

    assert plan["action_request_bundle"]["requested_actions"] == []
    assert plan["body_channel"]["hesitation_hint"] == "brief_hesitation"
    assert plan["social_spatial_channel"]["orientation_mode"] == "hold_attention"
    assert plan["physiology_channel"]["state_band"] == "hesitant"
    assert plan["presentation_plan"]["motion_state"]["hesitation_hint"] == "brief_hesitation"
    assert plan["presentation_plan"]["physiology_state"]["state_band"] == "hesitant"


def test_execution_channels_surface_pause_as_visible_hold_semantics() -> None:
    executor = CharacterAgentL4Executor()

    plan = executor.build_execution_plan(
        snapshot=_snapshot(),
        interpretation=_interpretation(),
        decision=_decision().model_copy(update={"selected_intent": "pause"}),
    )

    assert plan["action_request_bundle"]["requested_actions"] == []
    assert plan["body_channel"]["posture"] == "paused"
    assert plan["body_channel"]["gesture_hint"] == "hold"
    assert plan["social_spatial_channel"]["spacing_behavior"] == "hold"
    assert plan["social_spatial_channel"]["orientation_mode"] == "hold"
    assert plan["presentation_plan"]["focus_state"]["focus_mode"] == "hold"
    assert plan["physiology_channel"]["state_band"] == "stable"


def test_execution_channels_surface_inspect_object_as_explicit_focus_pose() -> None:
    executor = CharacterAgentL4Executor()

    plan = executor.build_execution_plan(
        snapshot=_snapshot().model_copy(update={"attention_targets": ["obj_letter"]}),
        interpretation=_interpretation().model_copy(
            update={
                "attention_target": "obj_letter",
                "interpreted_summary": "inspect the letter quietly",
            }
        ),
        decision=_decision().model_copy(update={"selected_intent": "inspect_object"}),
    )

    assert plan["action_request_bundle"]["requested_actions"] == [
        {
            "request_type": "interact",
            "actor_id": "char_c",
            "target_object_id": "obj_letter",
            "interaction_type": "inspect",
        }
    ]
    assert plan["body_channel"]["posture"] == "inspect"
    assert plan["body_channel"]["gesture_hint"] == "inspect"
    assert plan["social_spatial_channel"]["spacing_behavior"] == "hold_attention"
    assert plan["social_spatial_channel"]["orientation_mode"] == "hold_attention"
    assert plan["presentation_plan"]["focus_state"]["target_id"] == "obj_letter"
    assert plan["presentation_plan"]["focus_state"]["focus_mode"] == "inspect"
    assert plan["presentation_plan"]["motion_state"]["posture"] == "inspect"
    assert plan["physiology_channel"]["state_band"] == "stable"


@pytest.mark.parametrize(
    "selected_intent, expected_posture, expected_gesture, expected_spacing, expected_orientation, expected_focus_mode, expected_request_type",
    [
        ("approach", "advancing", "reach_forward", "close_distance", "close_distance", "track_target", "approach"),
        ("follow_target", "advancing", "trail", "close_distance", "close_distance", "track_target", "follow_target"),
        ("break_contact", "guarded", "draw_back", "increase_distance", "increase_distance", "pull_back", "break_contact"),
        ("speak_private", "attentive", "present", "hold_attention", "hold_attention", "hold_attention", "speak_private"),
    ],
)
def test_execution_channels_surface_stage2_actor_family_semantics(
    selected_intent: str,
    expected_posture: str,
    expected_gesture: str,
    expected_spacing: str,
    expected_orientation: str,
    expected_focus_mode: str,
    expected_request_type: str,
) -> None:
    executor = CharacterAgentL4Executor()

    plan = executor.build_execution_plan(
        snapshot=_snapshot().model_copy(update={"attention_targets": ["char_a"]}),
        interpretation=_interpretation().model_copy(update={"attention_target": "char_a"}),
        decision=_decision().model_copy(update={"selected_intent": selected_intent}),
    )

    assert plan["body_channel"]["posture"] == expected_posture
    assert plan["body_channel"]["gesture_hint"] == expected_gesture
    assert plan["social_spatial_channel"]["spacing_behavior"] == expected_spacing
    assert plan["social_spatial_channel"]["orientation_mode"] == expected_orientation
    assert plan["presentation_plan"]["focus_state"]["focus_mode"] == expected_focus_mode
    assert plan["action_request_bundle"]["requested_actions"]
    assert plan["action_request_bundle"]["requested_actions"][0]["request_type"] == expected_request_type
    assert plan["action_request_bundle"]["requested_actions"][0]["target_actor_id"] == "char_a"


@pytest.mark.parametrize("selected_intent", ["approach", "follow_target"])
def test_execution_channels_fall_back_to_hold_semantics_when_target_is_missing(
    selected_intent: str,
) -> None:
    executor = CharacterAgentL4Executor()

    plan = executor.build_execution_plan(
        snapshot=_snapshot().model_copy(update={"attention_targets": []}),
        interpretation=_interpretation().model_copy(update={"attention_target": None}),
        decision=_decision().model_copy(update={"selected_intent": selected_intent}),
    )

    assert plan["action_request_bundle"]["requested_actions"] == []
    assert plan["body_channel"]["posture"] == "attentive"
    assert plan["body_channel"]["gesture_hint"] == "steady_point"
    assert plan["social_spatial_channel"]["spacing_behavior"] == "hold"
    assert plan["social_spatial_channel"]["orientation_mode"] == "hold"
    assert plan["presentation_plan"]["focus_state"]["focus_mode"] == "hold"


@pytest.mark.parametrize("selected_intent", ["approach", "follow_target"])
def test_execution_channels_fall_back_to_hold_semantics_when_target_is_object(
    selected_intent: str,
) -> None:
    executor = CharacterAgentL4Executor()

    plan = executor.build_execution_plan(
        snapshot=_snapshot().model_copy(update={"attention_targets": ["obj_letter"]}),
        interpretation=_interpretation().model_copy(update={"attention_target": "obj_letter"}),
        decision=_decision().model_copy(update={"selected_intent": selected_intent}),
    )

    assert plan["action_request_bundle"]["requested_actions"] == []
    assert plan["body_channel"]["posture"] == "attentive"
    assert plan["body_channel"]["gesture_hint"] == "steady_point"
    assert plan["social_spatial_channel"]["spacing_behavior"] == "hold"
    assert plan["social_spatial_channel"]["orientation_mode"] == "hold"
    assert plan["presentation_plan"]["focus_state"]["focus_mode"] == "hold"


def test_execution_channels_map_withdraw_to_visible_backoff_semantics() -> None:
    executor = CharacterAgentL4Executor()

    plan = executor.build_execution_plan(
        snapshot=_snapshot().model_copy(update={"attention_targets": ["char_a"]}),
        interpretation=_interpretation().model_copy(update={"attention_target": "char_a"}),
        decision=_decision().model_copy(update={"selected_intent": "withdraw"}),
    )

    assert plan["social_spatial_channel"]["spacing_behavior"] == "increase_distance"
    assert plan["social_spatial_channel"]["orientation_mode"] == "increase_distance"
    assert plan["body_channel"]["posture"] == "withdrawn"
    assert plan["body_channel"]["gesture_hint"] == "draw_back"
    assert plan["physiology_channel"]["state_band"] == "guarded"
    assert plan["presentation_plan"]["motion_state"]["posture"] == "withdrawn"
    assert plan["presentation_plan"]["focus_state"]["orientation_mode"] == "increase_distance"
    assert plan["action_request_bundle"]["requested_actions"] == [
        {
            "request_type": "withdraw",
            "actor_id": "char_c",
            "target_actor_id": "char_a",
        }
    ]
