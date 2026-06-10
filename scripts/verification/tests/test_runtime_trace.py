from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime_trace import extract_runtime_trace, write_runtime_trace


def test_extract_runtime_trace_maps_phase0_markers_to_events() -> None:
    logs = {
        "main": "\n".join(
            [
                "backend_connected:ws://127.0.0.1:8000/ws",
                "phase0_dialogue_target:char_a",
                "dialogue_applied:char_a",
                "object_state:obj_letter:object interaction accepted",
                "constraint_state_result:too far",
                "environment_state:alerted",
                "attention_applied:char_b",
                "voice_stub_played:char_a",
            ]
        )
    }

    events = extract_runtime_trace(logs)

    assert [event["event_type"] for event in events] == [
        "backend_connected",
        "dialogue_target_selected",
        "dialogue_applied",
        "object_state_changed",
        "constraint_result_observed",
        "environment_state_changed",
        "siming_attention_applied",
        "voice_stub_played",
    ]
    assert events[0]["source"] == "main"
    assert events[0]["result_id"] == "backend_connectivity"
    assert events[1]["subject"] == "char_a"


def test_write_runtime_trace_outputs_ndjson(tmp_path: Path) -> None:
    trace_path = tmp_path / "runtime-trace.ndjson"

    write_runtime_trace(
        trace_path,
        {
            "focus": "\n".join(
                [
                    'phase0_visual_fact_emitter:fixed_gaze_on_target:actor_looks_at_actor',
                    '"route":"authority_visual_fact"',
                    "character_runtime_state_delta",
                    "conversation_candidate_event",
                    "backend_message_type:siming_output",
                ]
            )
        },
    )

    rows = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    assert [row["event_type"] for row in rows] == [
        "visual_fact_emitted",
        "authority_visual_fact_ack",
        "runtime_projection_observed",
        "conversation_candidate_observed",
        "siming_output_observed",
    ]
    assert rows[0]["source"] == "focus"


def test_extract_runtime_trace_projects_backend_payload_fields() -> None:
    logs = {
        "main": "\n".join(
            [
                '[LocalPresentationBus] backend_message_raw:{"message_type":"conversation_candidate_event","payload":{"actor_id":"char_c","room_id":"room_demo","scene_id":"scene_demo","zone_id":"zone_focus","candidate_actor_ids":["char_a"],"candidate_object_ids":["obj_letter"],"causation_id":"focus:123","correlation_id":"focus:123"}}',
                '[LocalPresentationBus] backend_message_raw:{"message_type":"world_result","payload":{"actor_id":"char_c","target_object_id":"obj_letter","result_type":"object_state_result","current_state":"open"}}',
            ]
        )
    }

    events = extract_runtime_trace(logs)

    candidate_event = events[0]
    assert candidate_event["message_type"] == "conversation_candidate_event"
    assert candidate_event["actor_id"] == "char_c"
    assert candidate_event["room_id"] == "room_demo"
    assert candidate_event["scene_id"] == "scene_demo"
    assert candidate_event["zone_id"] == "zone_focus"
    assert candidate_event["candidate_actor_ids"] == ["char_a"]
    assert candidate_event["candidate_object_ids"] == ["obj_letter"]
    assert candidate_event["causation_id"] == "focus:123"
    assert candidate_event["correlation_id"] == "focus:123"

    world_event = events[1]
    assert world_event["message_type"] == "world_result"
    assert world_event["actor_id"] == "char_c"
    assert world_event["target_object_id"] == "obj_letter"
    assert world_event["result_type"] == "object_state_result"
