from __future__ import annotations

from pathlib import Path

import pytest

from app.models.embodied_interaction import EmbodiedActionRequest
from app.services.embodied_controller_auth_service import (
    EmbodiedControllerAuthService,
    EmbodiedControllerEnrollment,
)
from app.services.embodied_execution_ingress import (
    EmbodiedExecutionIngress,
    EmbodiedRealizationRouteGate,
)
from app.ws_protocol import Envelope
import app.main as main


def _request(attempt_id: str = "attempt:kick-chair:1") -> EmbodiedActionRequest:
    return EmbodiedActionRequest.model_validate(
        {
            "request_id": f"embodied_request:{attempt_id}",
            "interaction_attempt_id": attempt_id,
            "actor_id": "char_a",
            "target_ref": "entity:scene_demo:chair_01",
            "action_semantic": "kick",
            "affordance_id": "affordance:chair_01:kick",
            "authority_preflight_ref": f"preflight:{attempt_id}",
            "policy_revision": 2,
            "scene_revision": 5,
            "binding_revision": 7,
            "required_anchor_roles": ["approach_stance", "contact"],
            "execution_profile_ref": "execution_profile:kick:v1",
            "expiration_tick": 2000,
            "causation_id": f"cause:{attempt_id}",
            "correlation_id": f"corr:{attempt_id}",
            "realization_route": "embodied_controller_v1",
            "settlement_writer_kind": "esm_compatibility_adapter",
        }
    )


def _bind(auth: EmbodiedControllerAuthService):
    credential = auth.create_trusted_local_launch_credential(
        actor_id="char_a",
        controller_instance_id="controller:char_a:1",
        issued_at=100,
        expires_at=200,
    )
    return auth.bind_controller(
        EmbodiedControllerEnrollment(
            credential_kind="trusted_local_launch",
            credential=credential,
            actor_id="char_a",
            controller_instance_id="controller:char_a:1",
            protocol_version=1,
        ),
        remote_host="127.0.0.1",
        now=110,
    )


def test_trusted_local_launch_is_loopback_only_and_one_time() -> None:
    auth = EmbodiedControllerAuthService()
    credential = auth.create_trusted_local_launch_credential(
        actor_id="char_a",
        controller_instance_id="controller:char_a:1",
        issued_at=100,
        expires_at=200,
    )

    rejected = auth.bind_controller(
        EmbodiedControllerEnrollment(
            credential_kind="trusted_local_launch",
            credential=credential,
            actor_id="char_a",
            controller_instance_id="controller:char_a:1",
            protocol_version=1,
        ),
        remote_host="10.0.0.4",
        now=110,
    )
    accepted = auth.bind_controller(
        EmbodiedControllerEnrollment(
            credential_kind="trusted_local_launch",
            credential=credential,
            actor_id="char_a",
            controller_instance_id="controller:char_a:1",
            protocol_version=1,
        ),
        remote_host="127.0.0.1",
        now=110,
    )
    replay = auth.bind_controller(
        EmbodiedControllerEnrollment(
            credential_kind="trusted_local_launch",
            credential=credential,
            actor_id="char_a",
            controller_instance_id="controller:char_a:1",
            protocol_version=1,
        ),
        remote_host="127.0.0.1",
        now=111,
    )

    assert rejected.accepted is False
    assert rejected.error_code == "trusted_local_launch_requires_loopback"
    assert accepted.accepted is True
    assert accepted.binding is not None
    assert accepted.binding.connection_epoch == 1
    assert replay.accepted is False
    assert replay.error_code == "trusted_local_launch_already_used"


def test_authenticated_session_fails_closed_without_configured_adapter() -> None:
    auth = EmbodiedControllerAuthService(authenticated_session_adapter_configured=False)

    result = auth.bind_controller(
        EmbodiedControllerEnrollment(
            credential_kind="authenticated_session",
            credential="signed-but-no-adapter",
            actor_id="char_a",
            controller_instance_id="controller:char_a:1",
            protocol_version=1,
        ),
        remote_host="127.0.0.1",
        now=100,
    )

    assert result.accepted is False
    assert result.error_code == "authenticated_session_adapter_unavailable"


def test_execution_grant_requires_epoch_nonce_sequence_and_revocation() -> None:
    auth = EmbodiedControllerAuthService()
    binding = _bind(auth).binding
    assert binding is not None
    request = _request()
    grant = auth.issue_execution_grant(binding=binding, request=request, issued_at=120, ttl=100)
    ingress = EmbodiedExecutionIngress(auth_service=auth)

    phase_ack = ingress.handle_phase_event(
        {
            "grant_id": grant.grant_id,
            "connection_epoch": binding.connection_epoch,
            "source_sequence": 1,
            "payload_digest": "sha256:phase1",
            "phase": "acquire_target",
            "interaction_attempt_id": request.interaction_attempt_id,
        }
    )
    duplicate_phase = ingress.handle_phase_event(
        {
            "grant_id": grant.grant_id,
            "connection_epoch": binding.connection_epoch,
            "source_sequence": 1,
            "payload_digest": "sha256:phase1",
            "phase": "acquire_target",
            "interaction_attempt_id": request.interaction_attempt_id,
        }
    )
    gap_phase = ingress.handle_phase_event(
        {
            "grant_id": grant.grant_id,
            "connection_epoch": binding.connection_epoch,
            "source_sequence": 3,
            "payload_digest": "sha256:phase3",
            "phase": "navigate",
            "interaction_attempt_id": request.interaction_attempt_id,
        }
    )
    outcome = ingress.handle_local_outcome(
        {
            "interaction_attempt_id": request.interaction_attempt_id,
            "phase": "terminal",
            "terminal_status": "contact_observed",
            "observed_at": 130,
            "actor_pose_ref": "pose:char_a:bounded",
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
            "causation_id": request.causation_id,
            "correlation_id": request.correlation_id,
            "controller_grant_id": grant.grant_id,
            "connection_epoch": binding.connection_epoch,
            "terminal_sequence": 2,
            "outcome_nonce": grant.one_time_outcome_nonce,
            "payload_digest": "sha256:terminal",
        },
        now=130,
    )
    replay = ingress.handle_local_outcome(outcome.accepted_payload, now=131)
    bad_nonce = ingress.handle_local_outcome({**outcome.accepted_payload, "outcome_nonce": "nonce:bad"}, now=132)

    assert phase_ack.accepted is True
    assert duplicate_phase.accepted is True
    assert duplicate_phase.idempotent is True
    assert gap_phase.accepted is False
    assert gap_phase.error_code == "source_sequence_gap"
    assert outcome.accepted is True
    assert replay.accepted is True
    assert replay.idempotent is True
    assert bad_nonce.accepted is False
    assert bad_nonce.error_code == "grant_consumed"


def test_reconnect_revokes_old_epoch_grants() -> None:
    auth = EmbodiedControllerAuthService()
    binding = _bind(auth).binding
    assert binding is not None
    grant = auth.issue_execution_grant(binding=binding, request=_request(), issued_at=120, ttl=100)

    auth.revoke_controller_epoch(controller_instance_id=binding.controller_instance_id, connection_epoch=binding.connection_epoch)
    result = EmbodiedExecutionIngress(auth_service=auth).handle_phase_event(
        {
            "grant_id": grant.grant_id,
            "connection_epoch": binding.connection_epoch,
            "source_sequence": 1,
            "payload_digest": "sha256:phase1",
            "phase": "acquire_target",
            "interaction_attempt_id": "attempt:kick-chair:1",
        }
    )

    assert result.accepted is False
    assert result.error_code == "grant_revoked"


def test_realization_route_gate_prevents_double_control_and_drains_on_rollback() -> None:
    gate = EmbodiedRealizationRouteGate()

    first = gate.start_attempt("attempt:kick-chair:1", "embodied_controller_v1")
    duplicate = gate.start_attempt("attempt:kick-chair:1", "legacy_character_replica")
    cancellations = gate.disable_embodied_controller_route("operator_rollback")

    assert first.accepted is True
    assert duplicate.accepted is False
    assert duplicate.error_code == "realization_route_already_selected"
    assert cancellations == [
        {
            "interaction_attempt_id": "attempt:kick-chair:1",
            "directive": "cancel_and_recover",
            "reason": "operator_rollback",
        }
    ]


def test_backend_ws_dispatch_handles_embodied_bind_without_legacy_status_channel() -> None:
    main.reset_runtime_state()
    credential = main.embodied_controller_auth_service.create_trusted_local_launch_credential(
        actor_id="char_a",
        controller_instance_id="controller:char_a:1",
        issued_at=100,
        expires_at=200,
    )

    messages = main._handle_envelope(
        Envelope(
            message_type="embodied_controller_bind",
            payload={
                "credential_kind": "trusted_local_launch",
                "credential": credential,
                "actor_id": "char_a",
                "controller_instance_id": "controller:char_a:1",
                "protocol_version": 1,
            },
        )
    )

    assert messages[0]["message_type"] == "ack"
    assert messages[0]["payload"]["route"] == "embodied_controller_auth"
    assert messages[1]["message_type"] == "embodied_controller_bound"
    assert messages[1]["payload"]["connection_epoch"] == 1

    legacy = main._handle_envelope(Envelope(message_type="character_actor_status", payload={"interaction_attempt_id": "attempt:kick-chair:1"}))
    assert legacy[0]["payload"]["route"] == "character_actor_runtime_status"


def test_ws_envelope_rejects_unknown_top_level_fields() -> None:
    with pytest.raises(ValueError):
        Envelope(message_type="embodied_phase_event", payload={}, extra_field=True)  # type: ignore[call-arg]


def test_godot_backend_bridge_has_dedicated_embodied_routes() -> None:
    project_root = Path(__file__).resolve().parents[2]
    bridge_source = (project_root / "scripts" / "autoload" / "BackendBridge.gd").read_text(encoding="utf-8")
    bus_source = (project_root / "scripts" / "autoload" / "LocalPresentationBus.gd").read_text(encoding="utf-8")

    assert "signal embodied_phase_event_emitted(payload)" in bus_source
    assert "signal embodied_local_outcome_emitted(payload)" in bus_source
    assert "signal embodied_action_request_received(payload)" in bus_source
    assert '"embodied_phase_event"' in bridge_source
    assert '"embodied_local_outcome"' in bridge_source
    assert '"embodied_action_request"' in bridge_source
    embodied_section = bridge_source[
        bridge_source.index("func _on_embodied_phase_event_emitted") :
        bridge_source.index("func _get_bus")
    ]
    assert "character_actor_status" not in embodied_section
