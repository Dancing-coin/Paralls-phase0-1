from __future__ import annotations

import json
from pathlib import Path


MARKERS: tuple[tuple[str, str, str], ...] = (
    ("backend_connected:ws://127.0.0.1:8000/ws", "backend_connected", "backend_connectivity"),
    ('"message_type":"world_result"', "world_result_observed", "successful_interaction"),
    ('"message_type":"character_agent_execution"', "character_agent_execution_observed", "character_agent_execution_contract"),
    ("phase0_dialogue_target:", "dialogue_target_selected", "dialogue_loop"),
    ("dialogue_applied:", "dialogue_applied", "dialogue_loop"),
    ("object_state:", "object_state_changed", "successful_interaction"),
    ("constraint_state_result", "constraint_result_observed", "failed_interaction"),
    ("constraint_type", "constraint_result_observed", "failed_interaction"),
    ("environment_state:alerted", "environment_state_changed", "visible_world_state_change"),
    ("attention_applied:char_b", "siming_attention_applied", "siming_reaction"),
    ("voice_stub_played", "voice_stub_played", "voice_stub_path"),
    ("play_stub_voice", "voice_stub_played", "voice_stub_path"),
    ("phase0_visual_fact_emitter:", "visual_fact_emitted", "visual_fact_pipeline"),
    ('"route":"authority_visual_fact"', "authority_visual_fact_ack", "authority_ack_observed"),
    ("character_runtime_state_delta", "runtime_projection_observed", "runtime_projection_observed"),
    ("conversation_candidate_event", "conversation_candidate_observed", "candidate_and_siming_observed"),
    ("backend_message_type:siming_output", "siming_output_observed", "candidate_and_siming_observed"),
    ("backend_message_type:authority_event", "siming_authority_event_observed", "siming_event_bus_return_path"),
    (
        "siming_visual_observability_request:",
        "siming_visual_observability_requested",
        "siming_event_bus_return_path",
    ),
    (
        "siming_visual_observability_applied:",
        "siming_visual_observability_applied",
        "siming_event_bus_return_path",
    ),
)

PROJECTED_PAYLOAD_FIELDS = (
    "actor_id",
    "room_id",
    "scene_id",
    "zone_id",
    "target_actor_id",
    "target_object_id",
    "target_environment_id",
    "candidate_actor_ids",
    "candidate_object_ids",
    "candidate_environment_ids",
    "result_type",
    "output_type",
    "current_state",
    "causation_id",
    "correlation_id",
    "controller_source",
    "control_mode",
    "action",
)


def extract_runtime_trace(logs: dict[str, str]) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    sequence = 0
    for source, text in logs.items():
        for line_number, line in enumerate(text.splitlines(), start=1):
            for marker, event_type, result_id in MARKERS:
                if marker not in line:
                    continue
                sequence += 1
                event = {
                    "sequence": sequence,
                    "source": source,
                    "line_number": line_number,
                    "event_type": event_type,
                    "result_id": result_id,
                    "subject": _extract_subject(line, marker),
                    "raw": line.strip(),
                }
                event.update(_extract_structured_fields(line))
                events.append(event)
                break
    return events


def write_runtime_trace(path: Path, logs: dict[str, str]) -> Path:
    events = extract_runtime_trace(logs)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(event, ensure_ascii=False, sort_keys=True) for event in events]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path


def _extract_subject(line: str, marker: str) -> str:
    if marker.endswith(":") and marker in line:
        return line.split(marker, 1)[1].split(":", 1)[0].strip()
    if ":" in line:
        return line.rsplit(":", 1)[-1].strip()
    return ""


def _extract_structured_fields(line: str) -> dict[str, object]:
    fields: dict[str, object] = {}
    if "backend_message_type:" in line:
        fields["message_type"] = line.rsplit("backend_message_type:", 1)[-1].strip()

    payload = _extract_json_payload(line)
    if not payload:
        return fields

    message_type = payload.get("message_type")
    if isinstance(message_type, str):
        fields["message_type"] = message_type

    body = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload
    if not isinstance(body, dict):
        return fields

    for key in PROJECTED_PAYLOAD_FIELDS:
        if key in body:
            fields[key] = body[key]

    if fields.get("message_type") == "character_agent_execution":
        actor_control_frames = body.get("actor_control_frames")
        if isinstance(actor_control_frames, list) and actor_control_frames and isinstance(actor_control_frames[0], dict):
            first_frame = actor_control_frames[0]
            for key in ("controller_source", "control_mode", "action"):
                if key in first_frame:
                    fields[key] = first_frame[key]
        presentation_plan = body.get("presentation_plan")
        if isinstance(presentation_plan, dict):
            fields["has_focus_state"] = "focus_state" in presentation_plan
            fields["has_action_state"] = "action_state" in presentation_plan
            fields["has_speech_state"] = "speech_state" in presentation_plan
    return fields


def _extract_json_payload(line: str) -> dict[str, object]:
    start = line.find("{")
    if start < 0:
        return {}
    try:
        payload = json.loads(line[start:])
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}
