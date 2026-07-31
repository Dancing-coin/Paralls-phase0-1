from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.character_agent.skills.models import PrimitiveActionPlan, SkillEvaluationResult
from app.main import app
from app.services.interaction_orchestration_service import InteractionOrchestrationService, StructuredInteractionRequest
from app.world_runtime.intelligence_upgrade import InteractionIntentFrame


def _request(**overrides: object) -> StructuredInteractionRequest:
    payload = {
        "intent": InteractionIntentFrame(
            intent_id="intent:inspect",
            actor_id="char_a",
            target_refs={"object_ids": ["obj_box"]},
            semantic_intent="inspect",
        ),
        "player_id": "player",
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "producer_ts": 1,
        "target_object_id": "obj_box",
    }
    payload.update(overrides)
    return StructuredInteractionRequest(**payload)


def _skill_evaluation_result(*, selected: bool = True) -> SkillEvaluationResult:
    selected_path = {"binding_id": "first_aid_to_stabilize", "skill_id": "first_aid"} if selected else {}
    blocked_paths = (
        []
        if selected
        else [{"binding_id": "fallback_path", "missing_requirements": ["tool.bandage", "stance.stable"]}]
    )
    return SkillEvaluationResult(
        actor_id="char_a",
        action_id="stabilize_injured_actor",
        selected_path=selected_path,
        viable_paths=(
            [{"binding_id": "first_aid_to_stabilize", "skill_id": "first_aid", "expected_quality": "clean_success"}]
            if selected
            else []
        ),
        blocked_paths=blocked_paths,
        recommendation_reason=["prefer_low_risk_path"] if selected else ["fallback_blocked"],
        learning_policy_snapshot={"promotion_enabled": False},
    )


def _primitive_action_plan() -> PrimitiveActionPlan:
    return PrimitiveActionPlan(
        composite_action_id="stabilize_injured_actor",
        skill_path_id="first_aid_to_stabilize",
        primitive_actions=["approach_target", "inspect_wound", "apply_pressure"],
        realization_keys=["approach_careful", "apply_pressure"],
    )


def test_orchestration_covers_six_policy_shapes() -> None:
    service = InteractionOrchestrationService()

    semantic = service.plan(_request())
    physical = service.plan(
        _request(
            intent=InteractionIntentFrame(
                intent_id="intent:contact",
                actor_id="char_a",
                target_refs={"object_ids": ["obj_box"]},
                semantic_intent="physical_only",
                physical_affordance="contact",
            )
        )
    )
    mixed = service.plan(
        _request(
            intent=InteractionIntentFrame(
                intent_id="intent:push",
                actor_id="char_a",
                target_refs={"object_ids": ["obj_box"]},
                semantic_intent="move_obstacle",
                physical_affordance="push",
            )
        )
    )
    denied = service.plan(_request(constraint_refs=["constraint:locked"]))
    active = service.plan(_request(perception_ready=False))
    confirm = service.plan(_request(authority_confirmed=False))

    assert semantic.policy == "semantic-only"
    assert physical.policy == "physical-only"
    assert mixed.policy == "semantic-goal-physical-effect-mixed"
    assert denied.policy == "denied-by-constraint"
    assert active.policy == "requires-active-perception"
    assert confirm.policy == "requires-authority-confirmation"


def test_mixed_path_calls_semantic_and_physical_then_merges_one_unified_result_family() -> None:
    service = InteractionOrchestrationService()
    result = service.execute(
        _request(
            intent=InteractionIntentFrame(
                intent_id="intent:push",
                actor_id="char_a",
                target_refs={"object_ids": ["obj_box"]},
                semantic_intent="move_obstacle",
                physical_affordance="push",
            )
        )
    )

    result_types = {entry["result_type"] for entry in result.unified_result_family}
    assert result.plan.selected_channels == ["semantic", "physical"]
    assert "action_resolution_result" in result_types
    assert {"object_state_result", "body_state_result", "environment_state_result"}.issubset(result_types)
    assert len(result.unified_result_family) == 4


def test_degrade_paths_do_not_apply_physical_effects_or_bypass_authority() -> None:
    service = InteractionOrchestrationService()
    active = service.execute(_request(perception_ready=False))
    confirm = service.execute(_request(authority_confirmed=False))

    assert active.status == "degraded"
    assert active.unified_result_family == []
    assert active.plan.active_perception_request_ref.startswith("active_perception:")
    assert confirm.status == "degraded"
    assert confirm.unified_result_family == []
    assert confirm.plan.authority_confirmation_request_ref.startswith("authority_confirmation:")


def test_route_accepts_structured_intent_and_rejects_raw_input_noise() -> None:
    client = TestClient(app)
    response = client.post(
        "/interaction/orchestrate",
        json={
            "intent": {
                "intent_id": "intent:inspect",
                "actor_id": "char_a",
                "target_refs": {"object_ids": ["obj_box"]},
                "semantic_intent": "inspect",
            },
            "player_id": "player",
            "target_object_id": "obj_box",
            "producer_ts": 1,
        },
    )
    rejected = client.post(
        "/interaction/orchestrate",
        json={
            "intent": {
                "intent_id": "intent:bad",
                "actor_id": "char_a",
                "semantic_intent": "inspect",
            },
            "raw_keyboard": {"space": True},
        },
    )

    assert response.status_code == 200
    assert response.json()["plan"]["policy"] == "semantic-only"
    assert rejected.status_code == 422
    assert "raw input" in rejected.text


def test_structured_request_requires_physical_target_ref() -> None:
    with pytest.raises(ValueError, match="target_object_id"):
        StructuredInteractionRequest(
            intent=InteractionIntentFrame(
                intent_id="intent:bad",
                actor_id="char_a",
                semantic_intent="move_obstacle",
                physical_affordance="push",
            )
        )


def test_interaction_orchestration_carries_advisory_skill_metadata_without_changing_authority_status() -> None:
    service = InteractionOrchestrationService()
    base_result = service.execute(
        _request(
            intent=InteractionIntentFrame(
                intent_id="intent:push",
                actor_id="char_a",
                target_refs={"object_ids": ["obj_box"]},
                semantic_intent="move_obstacle",
                physical_affordance="push",
            )
        )
    )
    metadata_request = _request(
        intent=InteractionIntentFrame(
            intent_id="intent:push",
            actor_id="char_a",
            target_refs={"object_ids": ["obj_box"]},
            semantic_intent="move_obstacle",
            physical_affordance="push",
        ),
        skill_evaluation_result=_skill_evaluation_result(),
        primitive_action_plan=_primitive_action_plan(),
    )

    result = service.execute(metadata_request)

    assert result.status == base_result.status == "completed"
    assert result.unified_result_family == base_result.unified_result_family
    assert [entry.payload for entry in result.channel_results] == [entry.payload for entry in base_result.channel_results]
    assert result.plan.skill_evaluation_result == metadata_request.skill_evaluation_result
    assert result.plan.primitive_action_plan == metadata_request.primitive_action_plan
    assert result.skill_evaluation_result == metadata_request.skill_evaluation_result
    assert result.primitive_action_plan == metadata_request.primitive_action_plan
    assert result.action_settlement_result is not None
    assert result.action_settlement_result.outcome_band == "success_with_cost"
    assert result.action_settlement_result.primary_failure_domain == "none"
    assert "missing_requirement" not in result.action_settlement_result.failure_domains
