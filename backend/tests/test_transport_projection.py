from app.transport_projection import (
    OBSERVATORY_ONLY_MESSAGE_TYPES,
    is_known_stream_mode,
    normalize_stream_mode,
    project_outbound_messages,
)


OBSERVATORY_TYPES = {
    "character_agent_debug_event",
    "character_agent_debug_snapshot",
    "siming_debug_event",
    "siming_debug_snapshot",
    "world_outcome_trace",
    "scheduling_round_trace",
    "script_beat_event",
}


def _message(message_type: str) -> dict[str, object]:
    return {"message_type": message_type, "payload": {"marker": message_type}}


def test_runtime_only_filters_exact_observatory_families() -> None:
    messages = [_message("ack"), *[_message(name) for name in sorted(OBSERVATORY_TYPES)], _message("future_type")]

    projected = project_outbound_messages(messages, stream_mode="runtime_only")

    assert OBSERVATORY_ONLY_MESSAGE_TYPES == frozenset(OBSERVATORY_TYPES)
    assert [message["message_type"] for message in projected] == ["ack", "future_type"]


def test_full_mode_preserves_order_and_all_message_types() -> None:
    messages = [_message("ack"), _message("character_agent_debug_event"), _message("world_result")]

    projected = project_outbound_messages(messages, stream_mode="full")

    assert projected == messages
    assert projected is not messages


def test_missing_empty_and_unknown_stream_modes_normalize_to_full() -> None:
    assert normalize_stream_mode(None) == "full"
    assert normalize_stream_mode("") == "full"
    assert normalize_stream_mode("full") == "full"
    assert normalize_stream_mode("runtime_only") == "runtime_only"
    assert normalize_stream_mode("typo") == "full"
    assert is_known_stream_mode(None) is True
    assert is_known_stream_mode("") is True
    assert is_known_stream_mode("full") is True
    assert is_known_stream_mode("runtime_only") is True
    assert is_known_stream_mode("typo") is False
