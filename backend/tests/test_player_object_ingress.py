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
    replay = interact("use", "request:use")
    assert not any(m.get("event_type") == "object_state_result" for m in replay)
    rejected = interact("finish_use", "request:again")
    constraint = next(m["payload"] for m in rejected if m.get("event_type") == "constraint_state_result")
    assert (constraint["constraint_type"], constraint["constraint_code"]) == ("interaction_state_constraint", "invalid_interaction_state")
    assert main.gameplay_event_store.get_last_global_sequence() == before + 2


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
