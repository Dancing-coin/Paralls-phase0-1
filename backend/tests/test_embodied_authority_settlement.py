from __future__ import annotations

from app.models.embodied_interaction import EmbodiedActionRequest
from app.services.embodied_authority_settlement_service import EmbodiedAuthoritySettlementService
from app.services.embodied_controller_auth_service import (
    EmbodiedControllerAuthService,
    EmbodiedControllerEnrollment,
)


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
        "expiration_tick": 2000,
        "causation_id": "cause:kick-chair:1",
        "correlation_id": "corr:kick-chair:1",
        "realization_route": "embodied_controller_v1",
        "settlement_writer_kind": "esm_compatibility_adapter",
    }
    payload.update(overrides)
    return EmbodiedActionRequest.model_validate(payload)


def _auth_binding_and_grant(auth: EmbodiedControllerAuthService, request: EmbodiedActionRequest):
    credential = auth.create_trusted_local_launch_credential(
        actor_id=request.actor_id,
        controller_instance_id="controller:char_a:1",
        issued_at=100,
        expires_at=200,
    )
    binding = auth.bind_controller(
        EmbodiedControllerEnrollment(
            credential_kind="trusted_local_launch",
            credential=credential,
            actor_id=request.actor_id,
            controller_instance_id="controller:char_a:1",
            protocol_version=1,
        ),
        remote_host="127.0.0.1",
        now=110,
    ).binding
    assert binding is not None
    return binding, auth.issue_execution_grant(binding=binding, request=request, issued_at=120, ttl=100)


def _outcome(grant_id: str, epoch: int, nonce: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "interaction_attempt_id": "attempt:kick-chair:1",
        "phase": "terminal",
        "terminal_status": "contact_observed",
        "observed_at": 130,
        "actor_pose_ref": "pose:char_a:bounded",
        "target_binding_ref": "binding:entity:scene_demo:chair_01:7",
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
        "controller_grant_id": grant_id,
        "connection_epoch": epoch,
        "terminal_sequence": 2,
        "outcome_nonce": nonce,
        "payload_digest": "sha256:terminal",
    }
    payload.update(overrides)
    return payload


def _service_with_attempt():
    auth = EmbodiedControllerAuthService()
    request = _request()
    _binding, grant = _auth_binding_and_grant(auth, request)
    service = EmbodiedAuthoritySettlementService(auth_service=auth)
    service.register_attempt(request=request, grant=grant)
    return service, grant


def test_attested_contact_observation_settles_once_through_esm_compatibility_adapter() -> None:
    service, grant = _service_with_attempt()
    payload = _outcome(grant.grant_id, grant.connection_epoch, grant.one_time_outcome_nonce)

    first = service.settle_local_outcome(payload, now=130)
    duplicate = service.settle_local_outcome(payload, now=131)

    assert first.outcome == "committed"
    assert first.error_code == ""
    assert first.settlement_writer_kind == "esm_compatibility_adapter"
    assert len(first.authority_results) == 3
    assert service.mutation_count == 1
    assert duplicate.outcome == "committed"
    assert duplicate.idempotent is True
    assert service.mutation_count == 1


def test_fabricated_or_stale_observation_produces_zero_mutation() -> None:
    service, grant = _service_with_attempt()

    fabricated = service.settle_local_outcome(
        _outcome("grant:fake", grant.connection_epoch, grant.one_time_outcome_nonce),
        now=130,
    )
    stale_epoch = service.settle_local_outcome(
        _outcome(grant.grant_id, grant.connection_epoch + 1, grant.one_time_outcome_nonce),
        now=130,
    )

    assert fabricated.outcome == "observation_rejected"
    assert fabricated.error_code == "outcome_attestation_invalid"
    assert stale_epoch.outcome == "observation_rejected"
    assert stale_epoch.error_code == "outcome_attestation_invalid"
    assert service.mutation_count == 0


def test_missing_contact_or_target_mismatch_rejects_observation_without_mutation() -> None:
    service, grant = _service_with_attempt()

    no_contact = service.settle_local_outcome(
        _outcome(grant.grant_id, grant.connection_epoch, grant.one_time_outcome_nonce, contact_observation=None),
        now=130,
    )

    assert no_contact.outcome == "observation_rejected"
    assert no_contact.error_code == "observation_rule_failed"
    assert service.mutation_count == 0


def test_revision_mismatch_rejects_without_consuming_world_mutation() -> None:
    auth = EmbodiedControllerAuthService()
    request = _request(binding_revision=8)
    _binding, grant = _auth_binding_and_grant(auth, request)
    service = EmbodiedAuthoritySettlementService(auth_service=auth)
    service.register_attempt(request=_request(binding_revision=7), grant=grant)

    result = service.settle_local_outcome(
        _outcome(grant.grant_id, grant.connection_epoch, grant.one_time_outcome_nonce),
        now=130,
    )

    assert result.outcome == "rejected"
    assert result.error_code == "revision_conflict"
    assert service.mutation_count == 0


def test_cross_domain_writer_is_blocked_until_gameplay_event_batch_writer_exists() -> None:
    auth = EmbodiedControllerAuthService()
    request = _request(
        action_semantic="handoff",
        settlement_writer_kind="gameplay_event_batch_writer",
        affordance_id="affordance:chair_01:handoff",
    )
    _binding, grant = _auth_binding_and_grant(auth, request)
    service = EmbodiedAuthoritySettlementService(auth_service=auth, gameplay_event_batch_writer_available=False)
    service.register_attempt(request=request, grant=grant, effect_scope="ownership_transfer")

    result = service.settle_local_outcome(
        _outcome(grant.grant_id, grant.connection_epoch, grant.one_time_outcome_nonce),
        now=130,
    )

    assert result.outcome == "not_committed"
    assert result.error_code == "gameplay_event_batch_writer_unavailable"
    assert service.mutation_count == 0
