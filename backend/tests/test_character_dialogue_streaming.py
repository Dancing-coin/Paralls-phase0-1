from fastapi.testclient import TestClient
import time
import pytest

import app.main as main
from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.gateway.model_provider import CharacterModelProvider
from app.config import settings


class _StreamingProvider:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    def stream_dialogue(self, request: dict[str, object], *, cancelled) -> object:
        self.requests.append(request)
        yield {"event": "delta", "delta": "I am "}
        yield {"event": "delta", "delta": "here."}
        yield {
            "event": "completed",
            "output": {"content": "I am here.", "tone": "neutral"},
            "fallback_used": False,
        }


def _dialogue_request() -> dict[str, object]:
    return {
        "task_kind": "dialogue_generation",
        "route": {"route_mode": "local_only", "provider_kind": "local"},
        "context": {
            "actor_id": "char_a",
            "control_mode": "dialogue_service",
            "snapshot": {},
            "memory": {"working_memory": [], "episodic_memories": [], "relational_memories": []},
            "event": {"content": "Hello", "target_actor_id": "char_a", "intent_type": "dialogue_submit"},
        },
        "prompt": {},
        "policy": {},
    }


def _dialogue_envelope(request_id: str = "dialogue-test-1") -> dict[str, object]:
    return {
        "message_type": "player_input",
        "payload": {
            "player_id": "p1",
            "room_id": "room_demo",
            "actor_id": "char_c",
            "intent_type": "dialogue_submit",
            "producer_ts": 90210,
            "target_actor_id": "char_a",
            "content": "Hello",
            "request_id": request_id,
        },
    }


def test_dialogue_stream_gateway_validates_only_completed_output() -> None:
    provider = _StreamingProvider()
    gateway = CharacterModelGateway(provider=provider)  # type: ignore[arg-type]

    events = list(
        gateway.stream_dialogue_task(
            context=_dialogue_request()["context"],  # type: ignore[arg-type]
            route_override="local_only",
            cancelled=lambda: False,
        )
    )

    assert provider.requests
    assert [event["event"] for event in events] == ["delta", "delta", "completed"]
    assert "output" not in events[0]
    assert events[-1]["output"] == {"content": "I am here.", "tone": "neutral"}


def test_local_dialogue_stream_produces_deltas_then_a_completed_fallback() -> None:
    provider = CharacterModelProvider(provider_kind="local")

    events = list(provider.stream_dialogue(_dialogue_request(), cancelled=lambda: False))

    assert [event["event"] for event in events[:-1]]
    assert all(event["event"] == "delta" for event in events[:-1])
    assert events[-1]["event"] == "completed"
    assert events[-1]["fallback_used"] is True
    assert events[-1]["output"]["content"] == "I am here. What do you need?"


def test_provider_stream_request_is_dialogue_text_sse_not_a_structured_l2_l3_request() -> None:
    provider = CharacterModelProvider(provider_kind="deepseek", api_key="test-key")

    payload = provider._build_deepseek_stream_request(
        {
            "prompt": {"system_instruction": "system", "user_instruction": "user"},
            "policy": {"temperature": 0.2, "max_tokens": 120},
        }
    )

    assert payload["stream"] is True
    assert "response_format" not in payload
    assert "spoken dialogue text" in payload["messages"][0]["content"]


@pytest.mark.parametrize("task_kind", ["l2_reasoning", "l3_planning"])
def test_provider_rejects_streaming_for_l2_and_l3(task_kind: str) -> None:
    provider = CharacterModelProvider(provider_kind="local")
    request = _dialogue_request()
    request["task_kind"] = task_kind

    with pytest.raises(ValueError, match="only supports dialogue_generation"):
        next(provider.stream_dialogue(request, cancelled=lambda: False))


def test_websocket_dialogue_stream_keeps_final_response_as_the_only_written_result(monkeypatch) -> None:
    monkeypatch.setattr(settings, "dialogue_mode", "stub")
    main.reset_runtime_state()
    client = TestClient(main.app)

    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(_dialogue_envelope())
        messages = [websocket.receive_json() for _ in range(5)]

    assert [message["message_type"] for message in messages] == [
        "ack",
        "dialogue_stream_start",
        "dialogue_stream_delta",
        "dialogue_response",
        "dialogue_stream_end",
    ]
    assert messages[2]["payload"]["request_id"] == "dialogue-test-1"
    assert messages[3]["payload"]["request_id"] == "dialogue-test-1"
    assert messages[4]["payload"] == {
        "request_id": "dialogue-test-1",
        "status": "completed",
        "partial_chars": len(messages[3]["payload"]["content"]),
        "fallback_used": True,
    }
    bundle = main.character_agent_runtime.get_memory_bundle("char_a")
    assert [entry["event_type"] for entry in bundle["working_memory"]].count("character_agent_dialogue_response") == 1


def test_cancelled_dialogue_stream_has_no_completed_authority_result() -> None:
    provider = CharacterModelProvider(provider_kind="local")

    events = list(provider.stream_dialogue(_dialogue_request(), cancelled=lambda: True))

    assert events == [{"event": "cancelled"}]


def test_websocket_cancelled_dialogue_stream_does_not_write_partial_text(monkeypatch) -> None:
    monkeypatch.setattr(settings, "dialogue_mode", "stub")
    main.reset_runtime_state()

    def slow_stream(_event, *, cancelled):
        yield {"event": "delta", "delta": "Partial"}
        while not cancelled():
            time.sleep(0.01)
        yield {"event": "cancelled"}

    monkeypatch.setattr(main.character_service, "stream_dialogue", slow_stream)
    client = TestClient(main.app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(_dialogue_envelope("dialogue-cancel-1"))
        assert websocket.receive_json()["message_type"] == "ack"
        assert websocket.receive_json()["message_type"] == "dialogue_stream_start"
        assert websocket.receive_json()["message_type"] == "dialogue_stream_delta"
        websocket.send_json({"message_type": "dialogue_stream_cancel", "payload": {"request_id": "dialogue-cancel-1"}})
        assert websocket.receive_json()["payload"]["route"] == "dialogue_stream_cancel"
        terminal = websocket.receive_json()

    assert terminal["message_type"] == "dialogue_stream_end"
    assert terminal["payload"]["status"] == "cancelled"
    bundle = main.character_agent_runtime.get_memory_bundle("char_a")
    assert not any(entry["event_type"] == "character_agent_dialogue_response" for entry in bundle["working_memory"])
