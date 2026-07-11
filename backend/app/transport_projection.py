from __future__ import annotations

from typing import Literal


StreamMode = Literal["full", "runtime_only"]

OBSERVATORY_ONLY_MESSAGE_TYPES = frozenset(
    {
        "character_agent_debug_event",
        "character_agent_debug_snapshot",
        "siming_debug_event",
        "siming_debug_snapshot",
        "world_outcome_trace",
        "scheduling_round_trace",
        "script_beat_event",
    }
)


def normalize_stream_mode(raw_mode: str | None) -> StreamMode:
    if raw_mode == "runtime_only":
        return "runtime_only"
    return "full"


def is_known_stream_mode(raw_mode: str | None) -> bool:
    return raw_mode in {None, "", "full", "runtime_only"}


def project_outbound_messages(
    messages: list[dict[str, object]],
    *,
    stream_mode: StreamMode,
) -> list[dict[str, object]]:
    if stream_mode == "full":
        return list(messages)
    return [
        message
        for message in messages
        if str(message.get("message_type", "") or "") not in OBSERVATORY_ONLY_MESSAGE_TYPES
    ]
