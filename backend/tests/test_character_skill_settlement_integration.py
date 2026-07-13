from __future__ import annotations

from app.services.interaction_orchestration_service import InteractionOrchestrationService, StructuredInteractionRequest
from app.services.character_agent_runtime import CharacterAgentRuntime
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


def _missing_requirement_skill_evaluation() -> dict[str, object]:
    return {
        "actor_id": "char_a",
        "action_id": "move_obstacle",
        "selected_path": {},
        "viable_paths": [],
        "blocked_paths": [
            {
                "binding_id": "labor_to_move_obstacle",
                "action_id": "move_obstacle",
                "skill_id": "labor",
                "eligibility_status": "blocked",
                "missing_requirements": ["labor.trained"],
            }
        ],
        "recommendation_reason": ["labor training is required before the action is viable"],
        "learning_policy_snapshot": {"advisory": True},
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
    blocked_result_types = {entry["result_type"] for entry in blocked.unified_result_family}
    blocked_constraint_codes = {
        entry["constraint_code"]
        for entry in blocked.unified_result_family
        if entry["result_type"] == "constraint_state_result"
    }
    assert "constraint_state_result" in blocked_result_types
    assert "semantic_authority_required" in blocked_constraint_codes


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


def test_result_advisory_metadata_mutations_do_not_alias_plan_snapshot() -> None:
    service = InteractionOrchestrationService()

    result = service.execute(
        _mixed_request(
            skill_evaluation_result=_strong_skill_evaluation(),
            primitive_action_plan=_primitive_action_plan(),
        )
    )

    result.advisory_metadata["skill_evaluation_result"]["selected_path"]["binding_id"] = "mutated_binding"
    result.advisory_metadata["primitive_action_plan"]["primitive_actions"].append("mutated_action")

    assert result.plan.advisory_metadata["skill_evaluation_result"]["selected_path"]["binding_id"] == (
        "labor_to_move_obstacle"
    )
    assert result.plan.advisory_metadata["primitive_action_plan"]["primitive_actions"] == [
        "brace",
        "push",
        "recover_balance",
    ]


def test_settlement_metadata_maps_success_outcome_bands_without_overwriting_world_status() -> None:
    service = InteractionOrchestrationService()
    runtime = CharacterAgentRuntime()

    semantic = service.execute(_semantic_request())
    mixed = service.execute(
        _mixed_request(
            skill_evaluation_result=_strong_skill_evaluation(),
            primitive_action_plan=_primitive_action_plan(),
        )
    )

    semantic_payload = semantic.unified_result_family[0]
    body_payload = next(
        entry for entry in mixed.unified_result_family if entry["result_type"] == "body_state_result"
    )

    semantic_metadata = runtime._action_settlement_result_metadata(semantic_payload)  # type: ignore[attr-defined]
    body_metadata = runtime._action_settlement_result_metadata(  # type: ignore[attr-defined]
        {
            **body_payload,
            "advisory_metadata": mixed.advisory_metadata,
        }
    )

    assert semantic_metadata["outcome_band"] == "clean_success"
    assert semantic_metadata["failure_domains"] == []
    assert semantic_payload["settlement_status"] == "accepted"
    assert [entry.status for entry in semantic.channel_results] == ["accepted"]
    assert [entry["result_type"] for entry in semantic.unified_result_family] == ["action_resolution_result"]

    assert body_metadata["outcome_band"] == "success_with_cost"
    assert body_metadata["failure_domains"] == []
    assert body_payload["settlement_status"] == "applied"
    assert [entry.status for entry in mixed.channel_results] == ["accepted", "applied"]
    assert any(entry["result_type"] == "body_state_result" for entry in mixed.unified_result_family)


def test_settlement_metadata_maps_world_constraint_and_physical_failure_domains() -> None:
    service = InteractionOrchestrationService()
    runtime = CharacterAgentRuntime()

    blocked = service.execute(
        _mixed_request(
            actor_position=(10.0, 1.0, 10.0),
            skill_evaluation_result=_strong_skill_evaluation(),
            primitive_action_plan=_primitive_action_plan(),
        )
    )
    world_constraint_payload = blocked.unified_result_family[0]
    physical_failure_payload = {
        "request_ref": "physical:intent:push",
        "result_id": "body_state:physical:intent:push",
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "actor_id": "char_a",
        "source_type": "esm_physical_channel",
        "entity_id": "char_a",
        "result_type": "body_state_result",
        "causation_id": "physical:intent:push",
        "correlation_id": "physical:intent:push",
        "producer_ts": 3,
        "target_object_id": "obj_letter",
        "settlement_status": "rejected",
        "body_state_class": "physical_push",
        "previous_state": "ready",
        "current_state": "contact_failed",
        "change_summary": "char_a lost footing while applying push",
    }

    world_constraint_metadata = runtime._action_settlement_result_metadata(  # type: ignore[attr-defined]
        world_constraint_payload
    )
    physical_failure_metadata = runtime._action_settlement_result_metadata(  # type: ignore[attr-defined]
        physical_failure_payload
    )

    assert world_constraint_metadata["outcome_band"] == "blocked"
    assert world_constraint_metadata["failure_domains"] == ["world_constraint"]
    assert world_constraint_payload["settlement_status"] == "rejected"

    assert physical_failure_metadata["outcome_band"] == "failed"
    assert physical_failure_metadata["failure_domains"] == ["physical_failure"]
    assert physical_failure_payload["settlement_status"] == "rejected"


def test_skill_advisory_metadata_contributes_descriptive_fields_without_overwriting_world_status() -> None:
    service = InteractionOrchestrationService()
    runtime = CharacterAgentRuntime()

    applied = service.execute(
        _mixed_request(
            skill_evaluation_result={
                **_strong_skill_evaluation(),
                "selected_path": {
                    **_strong_skill_evaluation()["selected_path"],
                    "risk_tags": ["overextension"],
                },
            },
            primitive_action_plan=_primitive_action_plan(),
        )
    )
    applied_payload = next(
        entry for entry in applied.unified_result_family if entry["result_type"] == "object_state_result"
    )
    applied_metadata = runtime._action_settlement_result_metadata(  # type: ignore[attr-defined]
        {
            **applied_payload,
            "advisory_metadata": applied.advisory_metadata,
        }
    )

    blocked_metadata = runtime._action_settlement_result_metadata(  # type: ignore[attr-defined]
        {
            "request_ref": "interact:missing",
            "result_id": "constraint:missing",
            "room_id": "room_demo",
            "scene_id": "scene_demo",
            "zone_id": "zone_focus",
            "actor_id": "char_a",
            "source_type": "player",
            "entity_id": "obj_letter",
            "result_type": "constraint_state_result",
            "causation_id": "interact:missing",
            "correlation_id": "interact:missing",
            "producer_ts": 8,
            "target_object_id": "obj_letter",
            "settlement_status": "rejected",
            "constraint_type": "interaction_orchestration_policy",
            "constraint_code": "denied_by_constraint",
            "constraint_summary": "interaction denied until training requirement is met",
            "blocking_entity_refs": ["obj_letter"],
            "advisory_metadata": {
                "skill_evaluation_result": _missing_requirement_skill_evaluation(),
            },
        }
    )

    assert applied_metadata["skill_path_id"] == "labor_to_move_obstacle"
    assert applied_metadata["skill_contributions"] == ["brace", "push", "recover_balance"]
    assert applied_metadata["risk_tags"] == ["overextension"]
    assert applied_metadata["realization_hints"] == ["stable_stance"]
    assert applied_payload["settlement_status"] == "applied"

    assert blocked_metadata["failure_domains"] == ["world_constraint", "missing_requirement"]
    assert blocked_metadata["missing_requirements"] == ["labor.trained"]
    assert blocked_metadata["skill_path_id"] == ""


def test_record_settlement_result_adds_structured_metadata_without_breaking_existing_payload_shape() -> None:
    service = InteractionOrchestrationService()
    runtime = CharacterAgentRuntime()
    result = service.execute(
        _mixed_request(
            skill_evaluation_result=_strong_skill_evaluation(),
            primitive_action_plan=_primitive_action_plan(),
        )
    )
    payload = {
        **next(entry for entry in result.unified_result_family if entry["result_type"] == "body_state_result"),
        "advisory_metadata": result.advisory_metadata,
    }

    runtime.record_settlement_result(
        actor_id="char_a",
        producer_ts=int(payload["producer_ts"]),
        payload=payload,
    )

    timeline = runtime.get_session_timeline("char_a")
    stored = timeline[-1]["payload"]

    assert payload["result_type"] == "body_state_result"
    assert payload["settlement_status"] == "applied"
    assert "action_settlement_result" not in payload
    assert stored["result_type"] == "body_state_result"
    assert stored["settlement_status"] == "applied"
    assert stored["advisory_metadata"] == result.advisory_metadata
    assert stored["action_settlement_result"]["outcome_band"] == "success_with_cost"
