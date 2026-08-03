from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.embodied_interaction import (
    EmbodiedActionRequest,
    EmbodiedEvidenceEvent,
    EmbodiedProjectionPolicy,
    EmbodiedSettlementWriterSelector,
    LocalExecutionOutcome,
    SceneAffordanceRecord,
)


def _registry_record(**overrides: object) -> SceneAffordanceRecord:
    payload: dict[str, object] = {
        "entity_ref": "entity:scene_demo:chair_01",
        "scene_id": "scene_demo",
        "scene_instance_id": "scene_instance:main_demo:1",
        "binding_revision": 7,
        "semantic_type": "chair",
        "semantic_tags": ["chair", "kickable"],
        "authoritative_state_ref": "esm:object:chair_01",
        "local_binding": {
            "node_ref": "node:chair_01",
            "collider_refs": ["collider:chair_01:body"],
            "navigation_footprint_ref": "nav:chair_01:footprint",
        },
        "anchors": [
            {"anchor_id": "anchor:chair_01:stance", "role": "approach_stance"},
            {"anchor_id": "anchor:chair_01:contact", "role": "contact"},
        ],
        "affordances": [
            {
                "affordance_id": "affordance:chair_01:kick",
                "action_semantic": "kick",
                "preconditions": ["upright"],
                "execution_profile_ref": "execution_profile:kick:v1",
                "observation_rule_ref": "observation_rule:chair_tipped:v1",
                "policy_ref": "authority_policy:kick_chair:v1",
            }
        ],
        "grounding_catalog_refs": {
            "entity_ref": "entity:scene_demo:chair_01",
            "collider_refs": ["collider:chair_01:body"],
            "anchor_refs": ["anchor:chair_01:stance", "anchor:chair_01:contact"],
        },
        "visibility_policy": "public_safe",
        "binding_health": "healthy",
    }
    payload.update(overrides)
    return SceneAffordanceRecord.model_validate(payload)


def _request(**overrides: object) -> EmbodiedActionRequest:
    payload: dict[str, object] = {
        "request_id": "embodied_request:kick:1",
        "interaction_attempt_id": "attempt:kick-chair:1",
        "actor_id": "char_a",
        "target_ref": "entity:scene_demo:chair_01",
        "action_semantic": "kick",
        "affordance_id": "affordance:chair_01:kick",
        "authority_preflight_ref": "preflight:kick-chair:1",
        "policy_revision": 2,
        "scene_revision": 5,
        "binding_revision": 7,
        "required_anchor_roles": ["approach_stance", "contact"],
        "execution_profile_ref": "execution_profile:kick:v1",
        "expiration_tick": 1000,
        "causation_id": "cause:kick-chair:1",
        "correlation_id": "corr:kick-chair:1",
        "realization_route": "embodied_controller_v1",
        "settlement_writer_kind": "esm_compatibility_adapter",
    }
    payload.update(overrides)
    return EmbodiedActionRequest.model_validate(payload)


def _outcome(**overrides: object) -> LocalExecutionOutcome:
    payload: dict[str, object] = {
        "interaction_attempt_id": "attempt:kick-chair:1",
        "phase": "terminal",
        "terminal_status": "contact_observed",
        "observed_at": 1234,
        "actor_pose_ref": "pose:char_a:bounded:1",
        "target_binding_ref": "binding:chair_01:7",
        "contact_observation": {
            "contact_ref": "contact:attempt:kick-chair:1",
            "actor_contact_ref": "collider:char_a:foot_r",
            "target_collider_ref": "collider:chair_01:body",
            "contact_window_ref": "window:kick:1",
        },
        "object_observation": {
            "object_ref": "entity:scene_demo:chair_01",
            "previous_state": "upright",
            "observed_state": "tipped",
            "observation_rule_ref": "observation_rule:chair_tipped:v1",
        },
        "trace_refs": ["trace:phase:1"],
        "causation_id": "cause:kick-chair:1",
        "correlation_id": "corr:kick-chair:1",
        "controller_grant_id": "grant:kick-chair:1",
        "connection_epoch": 3,
        "terminal_sequence": 9,
        "outcome_nonce": "nonce:kick-chair:1",
        "payload_digest": "sha256:terminal",
    }
    payload.update(overrides)
    return LocalExecutionOutcome.model_validate(payload)


def test_scene_affordance_record_reuses_grounding_catalog_identity() -> None:
    record = _registry_record()

    assert record.entity_ref == record.grounding_catalog_refs.entity_ref
    assert record.local_binding.collider_refs == record.grounding_catalog_refs.collider_refs
    assert [anchor.anchor_id for anchor in record.anchors] == record.grounding_catalog_refs.anchor_refs


def test_scene_affordance_record_rejects_parallel_identity_alias() -> None:
    with pytest.raises(ValidationError, match="grounding catalog identity mismatch"):
        _registry_record(entity_ref="entity:private_alias:chair_01")


@pytest.mark.parametrize(
    "forbidden_field",
    [
        "raw_keyboard",
        "raw_mouse",
        "raw_camera",
        "bone_transforms",
        "bone_stream",
        "rigid_body_velocity",
        "rigid_body_impulse",
        "node_path",
        "final_world_state",
        "world_truth_claim",
    ],
)
def test_embodied_request_rejects_raw_input_control_and_world_truth_fields(forbidden_field: str) -> None:
    with pytest.raises(ValidationError, match=forbidden_field):
        _request(**{forbidden_field: {"unsafe": True}})


def test_embodied_request_requires_one_writer_and_one_realization_route() -> None:
    request = _request()

    assert request.settlement_writer_kind == "esm_compatibility_adapter"
    assert request.realization_route == "embodied_controller_v1"

    with pytest.raises(ValidationError, match="single settlement writer"):
        _request(settlement_writer_kind=["esm_compatibility_adapter", "gameplay_event_batch_writer"])

    with pytest.raises(ValidationError, match="single realization route"):
        _request(realization_route=["legacy_character_replica", "embodied_controller_v1"])


def test_writer_selector_uses_esm_compatibility_only_for_kick_chair_first_closure() -> None:
    selector = EmbodiedSettlementWriterSelector(gameplay_event_batch_writer_available=False)

    selected = selector.select(
        action_semantic="kick",
        effect_scope="single_object_physical",
        requested_writer_kind="esm_compatibility_adapter",
    )
    rejected = selector.select(
        action_semantic="handoff",
        effect_scope="ownership_transfer",
        requested_writer_kind="gameplay_event_batch_writer",
    )

    assert selected.writer_kind == "esm_compatibility_adapter"
    assert selected.accepted is True
    assert selected.dual_write is False
    assert rejected.accepted is False
    assert rejected.error_code == "gameplay_event_batch_writer_unavailable"


@pytest.mark.parametrize(
    "forbidden_field",
    [
        "bone_transforms",
        "bone_stream",
        "rigid_body_stream",
        "raw_physics_dump",
        "applied_world_state",
        "character_actor_status",
    ],
)
def test_local_outcome_rejects_debug_streams_world_claims_and_legacy_channel(forbidden_field: str) -> None:
    with pytest.raises(ValidationError, match=forbidden_field):
        _outcome(**{forbidden_field: {"unsafe": True}})


def test_local_outcome_requires_attestation_fields() -> None:
    with pytest.raises(ValidationError, match="controller_grant_id"):
        _outcome(controller_grant_id="")
    with pytest.raises(ValidationError, match="connection_epoch"):
        _outcome(connection_epoch=0)
    with pytest.raises(ValidationError, match="outcome_nonce"):
        _outcome(outcome_nonce="")
    with pytest.raises(ValidationError, match="terminal_sequence"):
        _outcome(terminal_sequence=0)


def test_projection_policy_is_default_deny_and_filters_private_fields() -> None:
    policy = EmbodiedProjectionPolicy.public_observatory()

    projected = policy.project(
        {
            "interaction_attempt_id": "attempt:kick-chair:1",
            "settlement_status": "committed",
            "public_effect_summary": "chair_01 tipped",
            "private_participant_terms": {"char_b": "hidden"},
            "vla_prompt_context": "hidden",
            "raw_skeletal_debug_artifact": "debug://bones",
        }
    )

    assert projected == {
        "interaction_attempt_id": "attempt:kick-chair:1",
        "settlement_status": "committed",
        "public_effect_summary": "chair_01 tipped",
    }


def test_evidence_event_requires_backend_server_ledger_sequence() -> None:
    event = EmbodiedEvidenceEvent.model_validate(
        {
            "attempt_id": "attempt:kick-chair:1",
            "event_kind": "local_phase",
            "emitter_kind": "controller",
            "emitter_id": "controller:char_a:1",
            "emitter_epoch": 3,
            "source_sequence": 1,
            "server_ledger_sequence": 1,
            "payload_digest": "sha256:phase1",
            "occurred_at": 123,
            "recorded_at": 124,
            "projection_policy_ref": "projection:public_observatory:v1",
        }
    )

    assert event.server_ledger_sequence == 1

    with pytest.raises(ValidationError, match="server_ledger_sequence"):
        EmbodiedEvidenceEvent.model_validate(
            {
                "attempt_id": "attempt:kick-chair:1",
                "event_kind": "local_phase",
                "emitter_kind": "controller",
                "emitter_id": "controller:char_a:1",
                "emitter_epoch": 3,
                "source_sequence": 1,
                "payload_digest": "sha256:phase1",
                "occurred_at": 123,
                "recorded_at": 124,
                "projection_policy_ref": "projection:public_observatory:v1",
            }
        )
