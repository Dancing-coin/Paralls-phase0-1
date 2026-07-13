from __future__ import annotations

from app.services.interaction_orchestration_service import InteractionOrchestrationService, StructuredInteractionRequest
from app.world_runtime.intelligence_upgrade import InteractionIntentFrame


def _weak_skill_evaluation() -> dict[str, object]:
    return {
        "actor_id": "char_a",
        "action_id": "inspect",
        "selected_path": {},
        "viable_paths": [],
        "blocked_paths": [{"binding_id": "observe_to_inspect", "reason": "advisory only"}],
        "recommendation_reason": ["no viable skill path"],
        "learning_policy_snapshot": {"advisory": True},
    }


def _strong_skill_evaluation() -> dict[str, object]:
    return {
        "actor_id": "char_a",
        "action_id": "move_obstacle",
        "selected_path": {
            "binding_id": "labor_to_move_obstacle",
            "action_id": "move_obstacle",
            "preference_score": 1,
        },
        "viable_paths": [
            {
                "binding_id": "labor_to_move_obstacle",
                "action_id": "move_obstacle",
                "skill_id": "labor",
            }
        ],
        "blocked_paths": [],
        "recommendation_reason": ["recommended by advisory skill evaluation"],
        "learning_policy_snapshot": {"advisory": True},
    }


def _primitive_action_plan() -> dict[str, object]:
    return {
        "composite_action_id": "move_obstacle",
        "skill_path_id": "labor_to_move_obstacle",
        "primitive_actions": ["brace", "push", "recover_balance"],
        "realization_keys": ["stable_stance"],
    }


def _semantic_request(**overrides: object) -> StructuredInteractionRequest:
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


def _mixed_request(**overrides: object) -> StructuredInteractionRequest:
    payload = {
        "intent": InteractionIntentFrame(
            intent_id="intent:push",
            actor_id="char_a",
            target_refs={"object_ids": ["obj_letter"]},
            semantic_intent="move_obstacle",
            physical_affordance="push",
        ),
        "player_id": "player",
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "producer_ts": 1,
        "target_object_id": "obj_letter",
        "actor_position": (0.0, 1.0, 0.0),
    }
    payload.update(overrides)
    return StructuredInteractionRequest(**payload)


def test_weak_skill_metadata_preserves_semantic_only_status_semantics() -> None:
    service = InteractionOrchestrationService()

    baseline = service.execute(_semantic_request())
    advisory = service.execute(_semantic_request(skill_evaluation_result=_weak_skill_evaluation()))

    assert baseline.status == advisory.status == "completed"
    assert baseline.plan.policy == advisory.plan.policy == "semantic-only"
    assert baseline.plan.selected_channels == advisory.plan.selected_channels == ["semantic"]
    assert [entry.status for entry in baseline.channel_results] == [entry.status for entry in advisory.channel_results] == ["accepted"]
    assert [entry["result_type"] for entry in baseline.unified_result_family] == [
        entry["result_type"] for entry in advisory.unified_result_family
    ] == ["action_resolution_result"]


def test_mixed_request_skill_metadata_does_not_override_semantic_gate_for_physical_effects() -> None:
    service = InteractionOrchestrationService()

    applied = service.execute(
        _mixed_request(
            skill_evaluation_result=_strong_skill_evaluation(),
            primitive_action_plan=_primitive_action_plan(),
        )
    )
    blocked = service.execute(
        _mixed_request(
            actor_position=(10.0, 1.0, 10.0),
            skill_evaluation_result=_strong_skill_evaluation(),
            primitive_action_plan=_primitive_action_plan(),
        )
    )

    assert applied.plan.policy == "semantic-goal-physical-effect-mixed"
    assert [entry.status for entry in applied.channel_results] == ["accepted", "applied"]
    assert any(entry["result_type"] == "object_state_result" for entry in applied.unified_result_family)

    assert blocked.plan.policy == "semantic-goal-physical-effect-mixed"
    assert [entry.status for entry in blocked.channel_results] == ["rejected", "rejected"]
    assert blocked.unified_result_family[0]["result_type"] == "constraint_state_result"
    assert blocked.unified_result_family[-1]["constraint_code"] == "semantic_authority_required"


def test_strong_skill_metadata_cannot_override_authority_or_constraint_gates() -> None:
    service = InteractionOrchestrationService()

    authority_blocked = service.execute(
        _mixed_request(
            authority_confirmed=False,
            skill_evaluation_result=_strong_skill_evaluation(),
            primitive_action_plan=_primitive_action_plan(),
        )
    )
    constraint_blocked = service.execute(
        _mixed_request(
            constraint_refs=["constraint:locked"],
            skill_evaluation_result=_strong_skill_evaluation(),
            primitive_action_plan=_primitive_action_plan(),
        )
    )

    assert authority_blocked.status == "degraded"
    assert authority_blocked.plan.policy == "requires-authority-confirmation"
    assert authority_blocked.unified_result_family == []

    assert constraint_blocked.status == "denied"
    assert constraint_blocked.plan.policy == "denied-by-constraint"
    assert constraint_blocked.unified_result_family[0]["constraint_code"] == "denied_by_constraint"


def test_skill_metadata_stays_in_advisory_fields_not_world_result_authority_payloads() -> None:
    service = InteractionOrchestrationService()

    result = service.execute(
        _mixed_request(
            skill_evaluation_result=_strong_skill_evaluation(),
            primitive_action_plan=_primitive_action_plan(),
        )
    )

    assert result.plan.advisory_metadata == result.advisory_metadata
    assert result.advisory_metadata["skill_evaluation_result"]["selected_path"]["binding_id"] == "labor_to_move_obstacle"
    assert result.advisory_metadata["primitive_action_plan"]["primitive_actions"] == ["brace", "push", "recover_balance"]

    for entry in result.unified_result_family:
        assert "skill_evaluation_result" not in entry
        assert "primitive_action_plan" not in entry
        assert entry["result_type"] in {
            "action_resolution_result",
            "object_state_result",
            "body_state_result",
            "environment_state_result",
            "constraint_state_result",
        }

    for channel in result.channel_results:
        assert "skill_evaluation_result" not in channel.payload
        assert "primitive_action_plan" not in channel.payload
