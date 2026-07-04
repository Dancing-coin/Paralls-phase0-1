from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

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
