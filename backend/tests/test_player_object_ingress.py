"""Player object interaction must use bound spatial evidence and durable ESM."""
import pytest

from app import main
from app.services.websocket_session_auth_service import WebSocketConnectionContext
from app.ws_protocol import Envelope
from test_embodied_spatial_ingress import bind, configured, dispatch, payload


def interact(action, request_id, connection="spatial:c", **changes):
    context = WebSocketConnectionContext.direct_handler_compatibility()
    context.connection_ref = connection
    body = {"player_id": "p1", "room_id": "room_default", "scene_id": "scene_default",
            "zone_id": "zone_default", "actor_id": "char_a", "intent_type": "interact_intent",
            "producer_ts": 10, "target_object_id": "obj_worktable",
            "interaction_type": action, "request_id": request_id}
    body.update(changes)
    return main._handle_envelope(Envelope(message_type="player_input", payload=body), connection_context=context)


def test_bound_player_object_commit_retries_and_requires_engaged_state(configured):
    binding = bind()
    assert dispatch(payload(binding))[0]["payload"]["accepted"]
    before = main.gameplay_event_store.get_last_global_sequence()
    first = interact("use", "request:use")
    assert first[0]["payload"]["accepted"]
    started = next(m["payload"] for m in first if m.get("event_type") == "object_state_result")
    assert (started["previous_state"], started["current_state"], started["machine_id"]) == ("ready", "engaged", "work_surface")
    assert main.l1_occupancy_service.snapshot().object_states["obj_worktable"].state == "engaged"
    assert main.esm_service.interaction_state_for(room_id="room_default", scene_id="scene_default",
        zone_id="zone_default", target_object_id="obj_worktable") == "engaged"
    assert main.gameplay_event_store.get_last_global_sequence() == before + 1
    assert interact("use", "request:use")[0]["payload"]["accepted"]
    assert main.gameplay_event_store.get_last_global_sequence() == before + 1
    assert not interact("use", "request:use", producer_ts=11)[0]["payload"]["accepted"]
    assert main.gameplay_event_store.get_last_global_sequence() == before + 1
    finished = interact("finish_use", "request:finish")
    assert finished[0]["payload"]["accepted"]
    released = next(m["payload"] for m in finished if m.get("event_type") == "object_state_result")
    assert (released["previous_state"], released["current_state"]) == ("engaged", "ready")
    assert main.l1_occupancy_service.snapshot().object_states["obj_worktable"].state == "ready"
    replay = interact("use", "request:use")
    assert not any(m.get("event_type") == "object_state_result" for m in replay)
    assert main.l1_occupancy_service.snapshot().object_states["obj_worktable"].state == "ready"
    rejected = interact("finish_use", "request:again")
    constraint = next(m["payload"] for m in rejected if m.get("event_type") == "constraint_state_result")
    assert (constraint["constraint_type"], constraint["constraint_code"]) == ("interaction_state_constraint", "invalid_interaction_state")
    assert main.gameplay_event_store.get_last_global_sequence() == before + 2


def test_real_websocket_bound_sample_and_object_retry(configured):
    from time import time
    from types import SimpleNamespace
    from fastapi.testclient import TestClient

    now = int(time())
    credential = main.embodied_controller_auth_service.create_trusted_local_launch_credential(
        actor_id="char_a", controller_instance_id="controller:websocket-object",
        issued_at=now, expires_at=now + 60)
    client = TestClient(main.component_app, client=("127.0.0.1", 47111))
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json({"message_type": "embodied_controller_bind", "payload": {
            "credential_kind": "trusted_local_launch", "credential": credential,
            "actor_id": "char_a", "controller_instance_id": "controller:websocket-object",
            "protocol_version": 1,
        }})
        assert websocket.receive_json()["payload"]["accepted"]
        bound = websocket.receive_json()
        assert bound["message_type"] == "embodied_controller_bound"
        websocket.send_json({"message_type": "embodied_spatial_sample", "payload": payload(
            SimpleNamespace(connection_epoch=bound["payload"]["connection_epoch"]))})
        admitted = websocket.receive_json()
        assert admitted["message_type"] == "embodied_spatial_sample_result"
        assert admitted["payload"]["accepted"]
        body = {"player_id": "p1", "room_id": "room_default", "scene_id": "scene_default",
            "zone_id": "zone_default", "actor_id": "char_a", "intent_type": "interact_intent",
            "producer_ts": 10, "target_object_id": "obj_worktable", "interaction_type": "use",
            "request_id": "websocket:use"}
        before = main.gameplay_event_store.get_last_global_sequence()
        websocket.send_json({"message_type": "player_input", "payload": body})
        messages = []
        for _ in range(100):
            messages.append(websocket.receive_json())
            if messages[-1].get("event_type") == "object_state_result":
                break
        assert messages[0]["payload"]["accepted"]
        assert messages[-1].get("event_type") == "object_state_result"
        assert main.gameplay_event_store.get_last_global_sequence() == before + 1
        websocket.send_json({"message_type": "player_input", "payload": body})
        retry_ack = None
        for _ in range(100):
            message = websocket.receive_json()
            if message["message_type"] == "ack" and message["payload"].get("request_id") == body["request_id"]:
                retry_ack = message
                break
        assert retry_ack is not None and retry_ack["payload"]["accepted"]
        assert main.gameplay_event_store.get_last_global_sequence() == before + 1
    client.close()


def test_another_bound_controller_cannot_borrow_spatial_sample(configured):
    first = bind()
    assert dispatch(payload(first))[0]["payload"]["accepted"]
    auth = main.embodied_controller_auth_service
    from app.services.embodied_controller_auth_service import EmbodiedControllerEnrollment
    credential = auth.create_trusted_local_launch_credential(actor_id="char_a", controller_instance_id="second",
        issued_at=100, expires_at=200)
    assert auth.bind_controller(EmbodiedControllerEnrollment(credential_kind="trusted_local_launch",
        credential=credential, actor_id="char_a", controller_instance_id="second", protocol_version=1),
        remote_host="127.0.0.1", now=110, connection_ref="spatial:other").accepted
    before = main.gameplay_event_store.get_last_global_sequence()
    assert not interact("use", "request:other", connection="spatial:other")[0]["payload"]["accepted"]
    assert main.gameplay_event_store.get_last_global_sequence() == before


def test_failed_object_append_does_not_publish_object_success(configured, monkeypatch):
    binding = bind()
    assert dispatch(payload(binding))[0]["payload"]["accepted"]
    before = main.gameplay_event_store.get_last_global_sequence()
    def fail(_batch):
        raise OSError("storage unavailable")
    monkeypatch.setattr(main.gameplay_event_store, "append_batch", fail)
    with pytest.raises(OSError, match="storage unavailable"):
        interact("use", "request:use")
    assert main.gameplay_event_store.get_last_global_sequence() == before
    assert main.esm_service.interaction_state_for(room_id="room_default", scene_id="scene_default",
        zone_id="zone_default", target_object_id="obj_worktable") == "ready"


def test_retry_repairs_projection_after_committed_response_is_lost(configured, monkeypatch):
    binding = bind()
    assert dispatch(payload(binding))[0]["payload"]["accepted"]
    before = main.gameplay_event_store.get_last_global_sequence()
    original = main.l1_occupancy_service.apply_object_state_update
    def fail(**_kwargs):
        raise OSError("projection unavailable")
    monkeypatch.setattr(main.l1_occupancy_service, "apply_object_state_update", fail)
    with pytest.raises(OSError, match="projection unavailable"):
        interact("use", "request:use")
    assert main.gameplay_event_store.get_last_global_sequence() == before + 1
    monkeypatch.setattr(main.l1_occupancy_service, "apply_object_state_update", original)
    assert interact("use", "request:use")[0]["payload"]["accepted"]
    assert main.gameplay_event_store.get_last_global_sequence() == before + 1
    assert main.l1_occupancy_service.snapshot().object_states["obj_worktable"].state == "engaged"


@pytest.mark.parametrize("case", ["unbound", "missing_sample", "missing_request", "foreign_actor", "foreign_scope"])
def test_invalid_player_source_never_commits(configured, case):
    binding = bind()
    if case != "missing_sample":
        assert dispatch(payload(binding))[0]["payload"]["accepted"]
    before = main.gameplay_event_store.get_last_global_sequence()
    args = {"connection": "foreign"} if case == "unbound" else {}
    if case == "foreign_actor":
        args["actor_id"] = "char_b"
    if case == "foreign_scope":
        args["scene_id"] = "other"
    result = interact("use", "" if case == "missing_request" else "request:use", **args)
    assert result[0]["payload"]["accepted"] is False
    assert main.gameplay_event_store.get_last_global_sequence() == before
