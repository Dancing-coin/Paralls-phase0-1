"""Production sample ingress; no Godot scene or model quality claim."""
import pytest

from app import main
from app.config import Settings
from app.services.websocket_session_auth_service import WebSocketConnectionContext
from app.ws_protocol import Envelope
from app.world_runtime.embodied_spatial_source import EmbodiedSpatialScope


def scope():
    return EmbodiedSpatialScope(actor_id="char_a", room_id="room_default", scene_id="scene_default",
        scene_instance_id="scene_default:1", zone_id="zone_default", scene_revision=1,
        source_ref="authored:test@1", spawn_position=(0, 0, 0), bounds_min=(-10, -1, -10),
        bounds_max=(10, 2, 10), max_speed_mps=4, physics_ticks_per_second=60, max_age_ms=500)


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(main.settings, "embodied_spatial_scopes", [scope()])
    main.reset_runtime_state()
    return main.embodied_spatial_source


def bind(connection="spatial:c"):
    from app.services.embodied_controller_auth_service import EmbodiedControllerEnrollment
    auth = main.embodied_controller_auth_service
    credential = auth.create_trusted_local_launch_credential(actor_id="char_a", controller_instance_id="spatial:a",
        issued_at=100, expires_at=200)
    result = auth.bind_controller(EmbodiedControllerEnrollment(credential_kind="trusted_local_launch",
        credential=credential, actor_id="char_a", controller_instance_id="spatial:a", protocol_version=1),
        remote_host="127.0.0.1", now=110, connection_ref=connection)
    assert result.accepted
    return result.binding


def payload(binding):
    return dict(actor_id="char_a", room_id="room_default", scene_id="scene_default",
        scene_instance_id="scene_default:1", zone_id="zone_default", scene_revision=1,
        connection_epoch=binding.connection_epoch, physics_tick=1, position=[0, 0, 0])


def dispatch(body, connection="spatial:c"):
    context = WebSocketConnectionContext.direct_handler_compatibility()
    context.connection_ref = connection
    return main._handle_envelope(Envelope(message_type="embodied_spatial_sample", payload=body),
        connection_context=context)


def test_settings_register_only_strict_internal_scopes():
    configured = Settings(embodied_spatial_scopes=[scope().model_dump()])
    assert configured.embodied_spatial_scopes == [scope()]
    with pytest.raises(ValueError):
        Settings(embodied_spatial_scopes=[{**scope().model_dump(), "max_age_ms": 0}])


def test_production_ingress_commits_shared_source_and_exact_retry(configured):
    binding = bind()
    before = main.gameplay_event_store.get_last_global_sequence()
    first = dispatch(payload(binding))
    assert len(first) == 1 and first[0]["message_type"] == "embodied_spatial_sample_result"
    body = first[0]["payload"]
    assert body["accepted"] and body["receipt"]["committed"]
    assert dispatch(payload(binding)) == first
    assert main.gameplay_event_store.get_last_global_sequence() == before + 1
    evidence = configured.read(actor_id="char_a", room_id="room_default", scene_id="scene_default",
        scene_instance_id="scene_default:1", zone_id="zone_default", scene_revision=1)
    assert evidence.event_ref == body["receipt"]["committed_event_ids"][0]
    assert main.gameplay_event_store.get_event(evidence.event_ref).event_type == "world.embodied.spatial_sample_admitted"


@pytest.mark.parametrize("change,connection", [({}, "foreign"), ({"scene_revision": 2}, "spatial:c"),
    ({"scope": scope().model_dump(mode="json")}, "spatial:c"), ({"position": [float("nan"), 0, 0]}, "spatial:c")])
def test_production_rejects_foreign_malformed_and_client_scope_without_writes(configured, change, connection):
    binding = bind()
    before = main.gameplay_event_store.get_last_global_sequence()
    messages = dispatch({**payload(binding), **change}, connection)
    assert len(messages) == 1 and messages[0]["message_type"] == "embodied_spatial_sample_result"
    assert messages[0]["payload"]["accepted"] is False
    assert main.gameplay_event_store.get_last_global_sequence() == before


def test_transport_disconnect_revokes_spatial_source(configured):
    from types import SimpleNamespace
    binding = bind()
    assert dispatch(payload(binding))[0]["payload"]["accepted"]
    context = WebSocketConnectionContext.direct_handler_compatibility()
    context.connection_ref = "spatial:c"
    main._disconnect_dialogue_connection(SimpleNamespace(disconnect=lambda _: None), context)
    assert dispatch({**payload(binding), "physics_tick": 2})[0]["payload"]["accepted"] is False


def test_network_binding_uses_backend_clock_not_payload_time(configured):
    credential = main.embodied_controller_auth_service.create_trusted_local_launch_credential(
        actor_id="char_a", controller_instance_id="spatial:a", issued_at=100, expires_at=200)
    context = WebSocketConnectionContext.direct_handler_compatibility()
    context.connection_ref = "network:expired"
    messages = main._handle_envelope(Envelope(message_type="embodied_controller_bind", payload={
        "credential_kind": "trusted_local_launch", "credential": credential, "actor_id": "char_a",
        "controller_instance_id": "spatial:a", "protocol_version": 1,
    }), connection_context=context)
    assert any(message["payload"].get("error_code") == "trusted_local_launch_expired" for message in messages)
