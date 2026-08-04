from __future__ import annotations

import inspect
from time import time

import app.main as main
from fastapi.testclient import TestClient
import pytest
from starlette.websockets import WebSocketDisconnect
from app.gameplay.runtime_state import CharacterGameRuntimeStateBuilder, StateGroupDefinition, StateGroupRegistry
from app.gameplay.state_group_views import StateGroupConsumerViewPolicy, StateGroupViewProjector
from app.main import _handle_envelope, reset_runtime_state
from app.services.websocket_session_auth_service import WebSocketSessionAuthService, WebSocketSessionEnrollment
from app.services.websocket_session_auth_service import WebSocketConnectionContext
from app.ws_protocol import Envelope


def _bind(service: WebSocketSessionAuthService):
    credential = service.create_trusted_local_launch_credential(
        principal_ref="principal:player",
        allowed_actor_refs=("actor:visible", "actor:old"),
        issued_at=100,
        expires_at=200,
    )
    result = service.bind_session(
        WebSocketSessionEnrollment(credential_kind="trusted_local_launch", credential=credential, protocol_version=1),
        remote_host="127.0.0.1",
        now=101,
    )
    assert result.binding is not None
    return result.binding


def test_server_owned_renewal_issues_one_time_replacement_without_client_scope_arguments() -> None:
    service = WebSocketSessionAuthService()
    original = _bind(service)

    replacement = service.issue_replacement_enrollment(session_ref=original.session_ref, now=110)

    assert set(inspect.signature(service.issue_replacement_enrollment).parameters) == {"session_ref", "now"}
    assert replacement.credential_kind == "trusted_local_launch"
    assert replacement.credential.startswith("trusted_local_launch:")


def test_fresh_reconnect_binding_uses_new_epoch_and_revokes_the_old_binding() -> None:
    service = WebSocketSessionAuthService()
    original = _bind(service)
    replacement = service.issue_replacement_enrollment(session_ref=original.session_ref, now=110)

    renewed = service.bind_session(replacement, remote_host="127.0.0.1", now=111)

    assert renewed.accepted is True
    assert renewed.binding is not None
    assert renewed.binding.session_ref != original.session_ref
    assert renewed.binding.connection_epoch > original.connection_epoch
    assert service.resolve_binding(original.session_ref) is None
    assert service.resolve_binding(renewed.binding.session_ref) == renewed.binding


def test_server_can_revoke_an_unconsumed_replacement_enrollment_before_reconnect() -> None:
    service = WebSocketSessionAuthService()
    original = _bind(service)
    replacement = service.issue_replacement_enrollment(session_ref=original.session_ref, now=110)

    assert service.revoke_enrollment(replacement.credential) is True
    denied = service.bind_session(replacement, remote_host="127.0.0.1", now=111)

    assert denied.accepted is False
    assert denied.error_code == "trusted_local_launch_revoked"


def test_server_policy_can_narrow_replacement_scope_without_client_input() -> None:
    service = WebSocketSessionAuthService(
        renewal_scope_selector=lambda _binding: ("actor:visible",),
    )
    original = _bind(service)

    replacement = service.issue_replacement_enrollment(session_ref=original.session_ref, now=110)
    renewed = service.bind_session(replacement, remote_host="127.0.0.1", now=111)

    assert renewed.binding is not None
    assert renewed.binding.allowed_actor_refs == ("actor:visible",)
    assert "actor:old" not in renewed.binding.allowed_actor_refs


def test_websocket_renewal_control_discards_old_transport_scope_and_returns_only_replacement_enrollment() -> None:
    reset_runtime_state()
    credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
        principal_ref="principal:player",
        allowed_actor_refs=("actor:visible",),
        issued_at=10,
        expires_at=200,
    )
    context = WebSocketConnectionContext(remote_host="127.0.0.1", observed_at=11, connection_ref="connection:old")
    _handle_envelope(
        Envelope(
            message_type="websocket_session_bind",
            payload={"credential_kind": "trusted_local_launch", "credential": credential, "protocol_version": 1},
        ),
        connection_context=context,
    )
    assert context.binding is not None
    old_session_ref = context.binding.session_ref
    main.gameplay_godot_projection_repository.publish(_godot_view("actor:visible"))
    _handle_envelope(
        Envelope(message_type="gameplay_mirror_subscribe", payload={"actor_ref": "actor:visible"}),
        connection_context=context,
    )

    messages = _handle_envelope(
        Envelope(message_type="websocket_session_renewal", payload={"protocol_version": 2}),
        connection_context=context,
    )

    assert messages[0]["payload"]["accepted"] is True
    assert messages[1]["message_type"] == "websocket_session_renewal_enrollment"
    assert set(messages[1]["payload"]) == {"credential_kind", "credential", "protocol_version"}
    assert context.binding is None
    assert main.websocket_session_auth_service.resolve_binding(old_session_ref) is None
    assert main.gameplay_mirror_subscription_registry.after_commit_snapshots(affected_actor_refs=("actor:visible",)) == []
    denied = _handle_envelope(
        Envelope(message_type="gameplay_mirror_snapshot_request", payload={"actor_ref": "actor:visible"}),
        connection_context=context,
    )
    assert denied[0]["payload"]["error_code"] == "websocket_session_required"


def test_websocket_renewal_control_rejects_client_scope_fields_and_unbound_context() -> None:
    reset_runtime_state()
    context = WebSocketConnectionContext(remote_host="127.0.0.1", observed_at=11)

    malformed = _handle_envelope(
        Envelope(
            message_type="websocket_session_renewal",
            payload={"protocol_version": 2, "allowed_actor_refs": ["actor:forbidden"]},
        ),
        connection_context=context,
    )
    unbound = _handle_envelope(
        Envelope(message_type="websocket_session_renewal", payload={"protocol_version": 2}),
        connection_context=context,
    )

    assert malformed[0]["payload"]["error_code"] == "invalid_payload:extra_forbidden"
    assert unbound[0]["payload"]["error_code"] == "renewal_enrollment_required"


def test_server_revocation_drops_only_mirror_transport_state_without_mutating_authority_store() -> None:
    reset_runtime_state()
    credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
        principal_ref="principal:player",
        allowed_actor_refs=("actor:visible",),
        issued_at=10,
        expires_at=200,
    )
    context = WebSocketConnectionContext(remote_host="127.0.0.1", observed_at=11, connection_ref="connection:revoked")
    _handle_envelope(
        Envelope(
            message_type="websocket_session_bind",
            payload={"credential_kind": "trusted_local_launch", "credential": credential, "protocol_version": 1},
        ),
        connection_context=context,
    )
    assert context.binding is not None
    session_ref = context.binding.session_ref
    main.gameplay_godot_projection_repository.publish(_godot_view("actor:visible"))
    _handle_envelope(
        Envelope(message_type="gameplay_mirror_subscribe", payload={"actor_ref": "actor:visible"}),
        connection_context=context,
    )
    main.gameplay_mirror_connection_registry.register(
        session_ref=session_ref,
        connection_ref=context.connection_ref,
        deliver=lambda _payload: None,
    )
    authority_snapshot = main.gameplay_event_store.export_snapshot()

    assert main.revoke_websocket_session_for_transport(
        session_ref=session_ref,
        connection_ref=context.connection_ref,
        reason_code="session_revoked",
        now=12,
    ) is True

    assert main.websocket_session_auth_service.resolve_binding(session_ref) is None
    assert main.websocket_session_auth_service.lifecycle_record(session_ref).binding_state == "revoked"
    assert main.gameplay_mirror_subscription_registry.after_commit_snapshots(affected_actor_refs=("actor:visible",)) == []
    assert main.gameplay_event_store.export_snapshot() == authority_snapshot


def test_transport_revocation_requests_a_typed_close_from_the_live_connection() -> None:
    reset_runtime_state()
    credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
        principal_ref="principal:player",
        allowed_actor_refs=("actor:visible",),
        issued_at=10,
        expires_at=200,
    )
    context = WebSocketConnectionContext(remote_host="127.0.0.1", observed_at=11, connection_ref="connection:close-request")
    _handle_envelope(
        Envelope(
            message_type="websocket_session_bind",
            payload={"credential_kind": "trusted_local_launch", "credential": credential, "protocol_version": 1},
        ),
        connection_context=context,
    )
    assert context.binding is not None
    close_requests: list[str] = []
    main.websocket_transport_closers[context.connection_ref] = close_requests.append

    assert main.revoke_websocket_session_for_transport(
        session_ref=context.binding.session_ref,
        connection_ref=context.connection_ref,
        reason_code="mirror_delivery_unrecoverable",
        now=12,
    ) is True

    assert close_requests == ["mirror_delivery_unrecoverable"]


def test_live_websocket_receives_typed_revocation_before_controlled_close() -> None:
    reset_runtime_state()
    now = int(time())
    credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
        principal_ref="principal:player",
        allowed_actor_refs=("actor:visible",),
        issued_at=now,
        expires_at=now + 60,
    )

    with TestClient(main.app, client=("127.0.0.1", 47111)) as client:
        with client.websocket_connect("/ws") as websocket:
            websocket.send_json(
                {
                    "message_type": "websocket_session_bind",
                    "payload": {
                        "credential_kind": "trusted_local_launch",
                        "credential": credential,
                        "protocol_version": 1,
                    },
                }
            )
            first_response = websocket.receive_json()
            bound = websocket.receive_json()
            assert first_response["message_type"] == "ack"
            assert bound["message_type"] == "websocket_session_bound"
            session_ref = str(bound["payload"]["session_ref"])
            connection_ref = main.gameplay_mirror_connection_registry.connection_ref_for(session_ref=session_ref)
            assert connection_ref is not None

            assert main.revoke_websocket_session_for_transport(
                session_ref=session_ref,
                connection_ref=connection_ref,
                reason_code="mirror_delivery_unrecoverable",
                now=12,
            ) is True

            revoked = websocket.receive_json()
            assert revoked == {
                "message_type": "websocket_session_revoked",
                "payload": {
                    "reason_code": "mirror_delivery_unrecoverable",
                    "route": "gameplay_mirror_transport",
                },
            }
            websocket.send_json(
                {
                    "message_type": "websocket_session_revocation_received",
                    "payload": {
                        "reason_code": "mirror_delivery_unrecoverable",
                        "route": "gameplay_mirror_transport",
                    },
                }
            )
            with pytest.raises(WebSocketDisconnect) as closed:
                websocket.receive_json()
            assert closed.value.code == 4403


def _godot_view(actor_ref: str):
    registry = StateGroupRegistry()
    registry.register(StateGroupDefinition(group_id="core.resources", definition_version="1", projection_schema_version=1))
    state = CharacterGameRuntimeStateBuilder(registry).build(
        actor_ref=actor_ref,
        enabled_group_ids=("core.resources",),
        group_payloads={"core.resources": {"current": 7}},
        source_revision_vector={actor_ref: 1},
        registry_revision="registry:v1",
        world_config_revision="world:v1",
        active_patch_set_revision="patch:v1",
    )
    return StateGroupViewProjector(
        [StateGroupConsumerViewPolicy(group_id="core.resources", godot_allowed_fields=("current",))]
    ).godot_view(state, allowed_group_ids=("core.resources",))
