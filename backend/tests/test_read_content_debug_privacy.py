import json

from fastapi.testclient import TestClient

import app.main as main
from app.services.esm_service import ESMService
from app.ws_protocol import Envelope


def test_read_content_stays_in_actor_memory_and_out_of_debug_websocket(monkeypatch):
    main.reset_runtime_state()
    content = "Only the reader can see this document."
    source_ref = "record:private-letter:v1"
    monkeypatch.setattr(main, "esm_service", ESMService(readable_records={
        "obj_letter": {"content": content, "source_ref": source_ref, "allowed_actor_ids": {"char_c"}},
    }))
    messages = main._handle_envelope(Envelope(message_type="player_input", payload={
        "player_id": "p1", "room_id": "room_demo", "actor_id": "char_c",
        "intent_type": "interact_intent", "producer_ts": 456,
        "target_object_id": "obj_letter", "interaction_type": "read",
    }))

    timeline = main.character_agent_runtime.get_session_timeline("char_c")
    assert any(content in json.dumps(event) for event in timeline)
    assert content not in json.dumps(messages)
    assert source_ref not in json.dumps(messages)
    runtime = main.character_agent_runtime
    runtime._queue_observatory_snapshot(
        actor_id="char_c", producer_ts=500, snapshot=runtime.get_private_snapshot("char_c"),
        memory_bundle=runtime.get_memory_bundle("char_c"),
    )
    later_messages = main._observatory_messages_from_outbound([])
    main._emit_debug_from_messages(later_messages)
    assert content not in json.dumps(later_messages)
    assert source_ref not in json.dumps(later_messages)
    history = main.debug_stream.history()
    assert history
    with TestClient(main.component_app).websocket_connect("/debug/ws") as websocket:
        received = [websocket.receive_json() for _ in history]
    public = json.dumps(received)
    assert content not in public
    assert source_ref not in public
