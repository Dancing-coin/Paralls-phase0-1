from app.main import _handle_envelope, reset_runtime_state
from app.gameplay.runtime_state import CharacterGameRuntimeStateBuilder, StateGroupDefinition, StateGroupRegistry
from app.gameplay.state_group_views import StateGroupConsumerViewPolicy, StateGroupViewProjector
from app.services.websocket_session_auth_service import WebSocketConnectionContext
from app.ws_protocol import Envelope


def test_websocket_session_bind_keeps_backend_granted_multi_actor_scope_on_connection() -> None:
    import app.main as main

    reset_runtime_state()
    credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
        principal_ref="principal:player:1",
        allowed_actor_refs=("actor:a", "actor:b"),
        issued_at=10,
        expires_at=20,
    )
    context = WebSocketConnectionContext(remote_host="127.0.0.1", observed_at=20)

    messages = _handle_envelope(
        Envelope(
            message_type="websocket_session_bind",
            payload={
                "credential_kind": "trusted_local_launch",
                "credential": credential,
                "protocol_version": 1,
            },
        ),
        connection_context=context,
    )

    assert messages[0]["payload"]["accepted"] is True
    assert messages[1]["payload"]["allowed_actor_refs"] == ["actor:a", "actor:b"]
    assert context.binding is not None
    assert context.binding.allowed_actor_refs == ("actor:a", "actor:b")


def test_websocket_session_bind_rejects_non_loopback_peer_without_client_scope_fallback() -> None:
    import app.main as main

    reset_runtime_state()
    credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
        principal_ref="principal:player:1",
        allowed_actor_refs=("actor:a",),
        issued_at=10,
        expires_at=20,
    )

    messages = _handle_envelope(
        Envelope(
            message_type="websocket_session_bind",
            payload={
                "credential_kind": "trusted_local_launch",
                "credential": credential,
                "protocol_version": 1,
            },
        ),
        connection_context=WebSocketConnectionContext(remote_host="198.51.100.8", observed_at=11),
    )

    assert messages[0]["payload"]["accepted"] is False
    assert messages[0]["payload"]["error_code"] == "trusted_local_launch_requires_loopback"


def test_embodied_controller_bind_uses_connection_peer_host_not_default_loopback() -> None:
    import app.main as main

    reset_runtime_state()
    credential = main.embodied_controller_auth_service.create_trusted_local_launch_credential(
        actor_id="actor:a",
        controller_instance_id="controller:a",
        issued_at=10,
        expires_at=20,
    )

    messages = _handle_envelope(
        Envelope(
            message_type="embodied_controller_bind",
            payload={
                "credential_kind": "trusted_local_launch",
                "credential": credential,
                "actor_id": "actor:a",
                "controller_instance_id": "controller:a",
                "protocol_version": 1,
            },
        ),
        connection_context=WebSocketConnectionContext(remote_host="198.51.100.8", observed_at=11),
    )

    assert messages[0]["payload"]["accepted"] is False
    assert messages[0]["payload"]["error_code"] == "trusted_local_launch_requires_loopback"


def test_gameplay_mirror_websocket_routes_use_backend_published_view_and_bound_scope() -> None:
    import app.main as main

    reset_runtime_state()
    credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
        principal_ref="principal:player:1",
        allowed_actor_refs=("actor:visible",),
        issued_at=10,
        expires_at=20,
    )
    context = WebSocketConnectionContext(remote_host="127.0.0.1", observed_at=11)
    _handle_envelope(
        Envelope(
            message_type="websocket_session_bind",
            payload={"credential_kind": "trusted_local_launch", "credential": credential, "protocol_version": 1},
        ),
        connection_context=context,
    )
    main.gameplay_godot_projection_repository.publish(_godot_view("actor:visible"))

    subscribed = _handle_envelope(
        Envelope(
            message_type="gameplay_mirror_subscribe",
            payload={"actor_ref": "actor:visible", "requested_state_group_ids": ("core.resources",)},
        ),
        connection_context=context,
    )

    assert subscribed[0]["payload"]["accepted"] is True
    assert subscribed[1]["message_type"] == "gameplay_runtime_state_projection"
    assert subscribed[1]["actor_ref"] == "actor:visible"
    assert subscribed[1]["groups"]["core.resources"]["payload"] == {"current": 7}

    unauthorized = _handle_envelope(
        Envelope(message_type="gameplay_mirror_snapshot_request", payload={"actor_ref": "actor:hidden"}),
        connection_context=context,
    )
    assert unauthorized[0]["payload"]["error_code"] == "mirror_scope_unauthorized"

    unsubscribed = _handle_envelope(
        Envelope(message_type="gameplay_mirror_unsubscribe", payload={"actor_ref": "actor:visible"}),
        connection_context=context,
    )
    assert unsubscribed[0]["payload"]["subscription_removed"] is True
    resync = _handle_envelope(
        Envelope(message_type="gameplay_mirror_snapshot_request", payload={"actor_ref": "actor:visible"}),
        connection_context=context,
    )
    assert resync[0]["payload"]["error_code"] == "mirror_subscription_required"


def test_gameplay_mirror_subscription_fails_closed_without_backend_projection() -> None:
    import app.main as main

    reset_runtime_state()
    credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
        principal_ref="principal:player:1",
        allowed_actor_refs=("actor:visible",),
        issued_at=10,
        expires_at=20,
    )
    context = WebSocketConnectionContext(remote_host="127.0.0.1", observed_at=11)
    _handle_envelope(
        Envelope(
            message_type="websocket_session_bind",
            payload={"credential_kind": "trusted_local_launch", "credential": credential, "protocol_version": 1},
        ),
        connection_context=context,
    )

    messages = _handle_envelope(
        Envelope(message_type="gameplay_mirror_subscribe", payload={"actor_ref": "actor:visible"}),
        connection_context=context,
    )

    assert messages[0]["payload"]["accepted"] is False
    assert messages[0]["payload"]["error_code"] == "mirror_projection_unavailable"


def _godot_view(actor_ref: str):
    registry = StateGroupRegistry()
    registry.register(StateGroupDefinition(group_id="core.resources", definition_version="1", projection_schema_version=1))
    state = CharacterGameRuntimeStateBuilder(registry).build(
        actor_ref=actor_ref,
        enabled_group_ids=("core.resources",),
        group_payloads={"core.resources": {"current": 7, "private": "hidden"}},
        source_revision_vector={actor_ref: 1},
        registry_revision="registry:v1",
        world_config_revision="world:v1",
        active_patch_set_revision="patch:v1",
    )
    return StateGroupViewProjector(
        [StateGroupConsumerViewPolicy(group_id="core.resources", godot_allowed_fields=("current",))]
    ).godot_view(state, allowed_group_ids=("core.resources",))
