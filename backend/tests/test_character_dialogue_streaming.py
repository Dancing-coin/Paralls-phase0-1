from fastapi.testclient import TestClient
from threading import Event, Timer
import time
import pytest

import app.main as main
from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.gateway.model_provider import CharacterModelProvider
from app.config import settings
from app.models.player_input import DialogueSubmit
from test_character_agent_activation_handoff import active_dialogue_decision


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
    assert payload["thinking"] == {"type": "disabled"}
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
    client = TestClient(main.component_app)

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


def test_websocket_dialogue_waits_for_background_activation_lease(monkeypatch) -> None:
    """A transient background lease must not discard a player dialogue request."""
    monkeypatch.setattr(settings, "dialogue_mode", "stub")
    main.reset_runtime_state()
    released = Event()

    with TestClient(main.component_app) as client:
        execution = main.runtime_execution
        handle, receipt = execution.submit(
            lambda: main.character_agent_runtime.begin_actor_activation(
                "char_a", active_dialogue_decision(), producer_ts=90209,
                activation_kind="background"
            )
        ).result(2)
        assert handle is not None and receipt.committed

        def release_background_activation() -> None:
            try:
                execution.submit(
                    lambda: main.character_agent_runtime.finish_actor_activation(
                        handle, reason="completed"
                    )
                ).result(2)
            finally:
                released.set()

        release_timer = Timer(0.2, release_background_activation)
        release_timer.start()
        try:
            with client.websocket_connect("/ws") as websocket:
                websocket.send_json(_dialogue_envelope("dialogue-background-requeue-1"))
                first = websocket.receive_json()
                assert first["message_type"] == "ack"
                assert first["payload"]["accepted"] is True
                messages = [first]
                while messages[-1]["message_type"] != "dialogue_stream_end":
                    messages.append(websocket.receive_json())
                assert messages[-1]["payload"]["status"] == "completed"
                assert any(message["message_type"] == "dialogue_response" for message in messages)
        finally:
            release_timer.cancel()
            if not released.is_set():
                release_background_activation()
            assert released.wait(2)


def test_completed_dialogue_response_produces_observatory_writeback_and_dialogue_pair() -> None:
    main.reset_runtime_state()
    event = DialogueSubmit(**_dialogue_envelope()["payload"])

    main._handle_player_dialogue_submit(event)
    observatory_messages = main._observatory_messages_from_outbound([])

    assert any(
        message["message_type"] == "character_agent_debug_event"
        and message["payload"]["stage"] == "dialogue_writeback"
        for message in observatory_messages
    )
    script_beat = next(
        message["payload"]
        for message in observatory_messages
        if message["message_type"] == "script_beat_event"
    )
    assert script_beat["dialogue_pairs"]
    assert any(pair["pair_key"] == "char_a<->char_c" for pair in script_beat["dialogue_pairs"])


def test_websocket_dialogue_stream_sends_queued_observatory_writeback() -> None:
    main.reset_runtime_state()
    client = TestClient(main.component_app)

    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(_dialogue_envelope("dialogue-observatory-1"))
        [websocket.receive_json() for _ in range(5)]
        first_observatory_message = websocket.receive_json()

    assert first_observatory_message["message_type"] == "character_agent_debug_event"


def test_cancelled_dialogue_stream_has_no_completed_authority_result() -> None:
    provider = CharacterModelProvider(provider_kind="local")

    events = list(provider.stream_dialogue(_dialogue_request(), cancelled=lambda: True))

    assert events == [{"event": "cancelled"}]


def test_websocket_cancelled_dialogue_stream_does_not_write_partial_text(monkeypatch) -> None:
    monkeypatch.setattr(settings, "dialogue_mode", "stub")
    main.reset_runtime_state()

    def slow_stream(_request_json, *, cancelled):
        yield {"event": "delta", "delta": "Partial"}
        while not cancelled():
            time.sleep(0.01)
        yield {"event": "cancelled"}

    monkeypatch.setattr(main.character_service.dialogue._gateway, "stream_prepared_request", slow_stream)
    client = TestClient(main.component_app)
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


@pytest.mark.parametrize("activation_kind,accepted", [("background", True), ("siming", True), ("foreground", False)])
def test_dialogue_conflict_classification_survives_lease_release_before_delivery(
    monkeypatch, activation_kind, accepted
) -> None:
    """Release the real conflicting lease between owner admission and delivery."""
    monkeypatch.setattr(settings, "dialogue_mode", "stub")
    main.reset_runtime_state()
    conflict = Event()
    trace = []

    with TestClient(main.component_app) as client:
        execution = main.runtime_execution
        instance = main.character_agent_runtime
        handle, receipt = execution.submit(
            lambda: instance.begin_actor_activation(
                "char_a", active_dialogue_decision(), producer_ts=90209,
                activation_kind=activation_kind
            )
        ).result(2)
        assert handle is not None and receipt.committed
        original_begin = instance.begin_actor_activation
        original_non_player = instance.activation_is_non_player
        original_owner_call = main._dialogue_owner_call

        def begin(*args, **kwargs):
            result = original_begin(*args, **kwargs)
            if result[0] is None and result[1].stop_reason == "activation_lock_conflict":
                trace.append(("conflict", instance.activation_lock_is_active("char_a")))
                conflict.set()
            return result

        def non_player(actor_id):
            result = original_non_player(actor_id)
            trace.append(("non_player", result))
            return result

        def release():
            receipt = instance.finish_actor_activation(handle, reason="completed")
            trace.append(("release", receipt.lock_released))
            return receipt

        async def deliver_after_release(owner, command):
            result = await original_owner_call(owner, command)
            if conflict.is_set():
                conflict.clear()
                receipt = await original_owner_call(owner, release)
                assert receipt.lock_released
            return result

        monkeypatch.setattr(instance, "begin_actor_activation", begin)
        monkeypatch.setattr(instance, "activation_is_non_player", non_player)
        monkeypatch.setattr(main, "_dialogue_owner_call", deliver_after_release)
        try:
            with client.websocket_connect("/ws") as websocket:
                websocket.send_json(_dialogue_envelope(f"dialogue-release-before-delivery-{activation_kind}"))
                first = websocket.receive_json()
                assert first["message_type"] == "ack"
                assert first["payload"]["accepted"] is accepted, trace
                messages = [first]
                while messages[-1]["message_type"] != "dialogue_stream_end":
                    messages.append(websocket.receive_json())
                assert messages[-1]["payload"]["status"] == ("completed" if accepted else "requeued"), trace
                assert sum(message["message_type"] == "dialogue_response" for message in messages) == int(accepted)
            def response_count():
                return sum(entry["event_type"] == "character_agent_dialogue_response"
                           for entry in instance.get_session_timeline("char_a"))
            assert execution.submit(response_count).result(2) == int(accepted)
            assert execution.submit(lambda: instance.activation_lock_is_active("char_a")).result(2) is False
            print(f"controlled {activation_kind} schedule: {trace}; accepted={accepted}")
        finally:
            execution.submit(lambda: instance.finish_actor_activation(handle, reason="completed")).result(2)
