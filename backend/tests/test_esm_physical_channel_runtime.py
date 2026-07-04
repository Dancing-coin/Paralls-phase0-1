from __future__ import annotations

from pathlib import Path

from app.services.interaction_orchestration_service import InteractionOrchestrationService, StructuredInteractionRequest
from app.services.physical_interaction_channel import (
    PhysicalContactObservation,
    PhysicalInteractionChannel,
    PhysicalInteractionRequest,
)
from app.world_runtime.intelligence_upgrade import InteractionIntentFrame


ROOT = Path(__file__).resolve().parents[2]


def test_physical_channel_supports_effect_kinds_with_structured_observation_refs() -> None:
    channel = PhysicalInteractionChannel()
    for kind in ("contact", "push", "pull", "carry", "grab", "blocking"):
        result = channel.apply(
            PhysicalInteractionRequest(
                request_id=f"physical:{kind}",
                actor_id="char_a",
                room_id="room_demo",
                target_object_id="obj_box",
                effect_kind=kind,
                semantic_approved=True,
                authority_ref="action_resolution:semantic",
                contact_observation=PhysicalContactObservation(
                    contact_ref=f"contact:{kind}",
                    body_ref="body:char_a:right_hand",
                    object_ref="object:obj_box",
                    environment_ref="env:zone_focus",
                    sampled_by="godot_physical_interaction_probe",
                ),
                producer_ts=1,
            )
        )

        assert result.effect_applied is True
        assert result.structured_physical_effect_refs[0].startswith(f"physical_effect:{kind}:")
        assert result.object_state_observation_refs
        assert result.environment_state_observation_refs
        assert result.body_state_observation_refs
        assert {entry["result_type"] for entry in result.unified_results} == {
            "object_state_result",
            "body_state_result",
            "environment_state_result",
        }


def test_constraint_failure_prevents_physical_effect_application() -> None:
    result = PhysicalInteractionChannel().apply(
        PhysicalInteractionRequest(
            request_id="physical:blocked",
            actor_id="char_a",
            room_id="room_demo",
            target_object_id="obj_box",
            effect_kind="push",
            semantic_approved=False,
            constraint_refs=["constraint:locked"],
            producer_ts=1,
        )
    )

    assert result.effect_applied is False
    assert result.structured_physical_effect_refs == []
    assert result.constraint_result is not None
    assert result.unified_results[0]["result_type"] == "constraint_state_result"


def test_physical_effects_merge_through_orchestration_unified_result_family() -> None:
    service = InteractionOrchestrationService()
    result = service.execute(
        StructuredInteractionRequest(
            intent=InteractionIntentFrame(
                intent_id="intent:grab",
                actor_id="char_a",
                target_refs={"object_ids": ["obj_box"]},
                semantic_intent="take_object",
                physical_affordance="grab",
            ),
            player_id="player",
            room_id="room_demo",
            target_object_id="obj_box",
            producer_ts=1,
        )
    )

    assert result.plan.policy == "semantic-goal-physical-effect-mixed"
    assert len([entry for entry in result.unified_result_family if entry["result_type"] == "action_resolution_result"]) == 1
    assert any(entry["result_type"] == "object_state_result" for entry in result.unified_result_family)


def test_semantic_only_behavior_remains_unchanged_when_physical_channel_exists() -> None:
    result = InteractionOrchestrationService().execute(
        StructuredInteractionRequest(
            intent=InteractionIntentFrame(
                intent_id="intent:inspect",
                actor_id="char_a",
                target_refs={"object_ids": ["obj_box"]},
                semantic_intent="inspect",
            ),
            player_id="player",
            room_id="room_demo",
            target_object_id="obj_box",
            producer_ts=1,
        )
    )

    assert result.plan.policy == "semantic-only"
    assert [entry["result_type"] for entry in result.unified_result_family] == ["action_resolution_result"]


def test_godot_physical_adapter_probe_emit_structured_refs_only() -> None:
    probe = (ROOT / "scripts" / "interaction" / "PhysicalInteractionProbe.gd").read_text(encoding="utf-8")
    adapter = (ROOT / "scripts" / "interaction" / "PhysicalInteractionAdapter.gd").read_text(encoding="utf-8")

    assert "sample_contact_ref" in probe
    assert "semantic_success_decision_allowed := false" in probe
    assert "raw_physics_stream_to_backend_allowed := false" in probe
    assert "structured_refs_only := true" in adapter
    assert "bypass_semantic_authority_allowed := false" in adapter
    assert "second_world_result_protocol_allowed := false" in adapter
    assert "object_state_observation_refs" in adapter
    assert "environment_state_observation_refs" in adapter
    assert "body_state_observation_refs" in adapter
