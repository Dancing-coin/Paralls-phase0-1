from pathlib import Path

from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketDisconnect

from app.models.player_input import DialogueSubmit, FocusTargetChange, InteractIntent, MoveIntent
from app.models.visual_fact import VisualFactEvent
from app.services.character_service import CharacterService
from app.services.character_runtime_state_service import CharacterRuntimeStateService
from app.services.conversation_relation_service import ConversationRelationService
from app.services.esm_service import ESMService
from app.services.event_trace_service import EventTraceService
from app.services.focus_state_service import FocusStateService
from app.services.siming_service import SimingService
from app.services.session_runtime import SessionRuntime
from app.ws_protocol import Envelope

app = FastAPI(title="Paralls Phase0 Backend")
BACKEND_BUILD = "paralls-phase0-backend-worktree-2026-06-02"
WORKTREE_ROOT = str(Path(__file__).resolve().parents[2])


def reset_runtime_state() -> None:
    global runtime
    global character_service
    global esm_service
    global siming_service
    global event_trace
    global focus_state
    global conversation_relation_service
    global character_runtime_state_service

    runtime = SessionRuntime()
    character_service = CharacterService()
    esm_service = ESMService()
    siming_service = SimingService()
    event_trace = EventTraceService()
    focus_state = FocusStateService()
    conversation_relation_service = ConversationRelationService()
    character_runtime_state_service = CharacterRuntimeStateService()


reset_runtime_state()


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "build": BACKEND_BUILD,
        "worktree_root": WORKTREE_ROOT,
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_json()
            envelope = Envelope(**raw)
            outbound = _handle_envelope(envelope)
            for message in outbound:
                await websocket.send_json(message)
    except WebSocketDisconnect:
        return


def _handle_envelope(envelope: Envelope) -> list[dict[str, object]]:
    if envelope.message_type == "visual_fact_event":
        event = VisualFactEvent(**envelope.payload)
        conversation_relation_service.apply_visual_fact(event)
        event_trace.record(event.fact_type)
        event_trace.record(event.relation_type)
        messages: list[dict[str, object]] = [
            {
                "message_type": "ack",
                "payload": {
                    "accepted": True,
                    "source_type": envelope.message_type,
                    "route": "authority_visual_fact",
                },
            }
        ]
        messages.extend(
            _ensure_runtime_snapshot(
                actor_id=event.actor_id,
                room_id=event.room_id,
                scene_id=event.scene_id,
                zone_id=event.zone_id,
                producer_ts=event.producer_ts,
            )
        )
        visual_delta = _project_runtime_delta(event.actor_id, event.producer_ts)
        if visual_delta is not None:
            messages.append(visual_delta)
        visual_fact_siming_output = siming_service.evaluate_visual_fact(event)
        if visual_fact_siming_output is not None:
            event_trace.record(visual_fact_siming_output.output_type)
            messages.append(_as_envelope("siming_output", visual_fact_siming_output.model_dump()))
        candidate = conversation_relation_service.build_candidate_event(
            actor_id=event.actor_id,
            causation_id=f"visual_fact:{event.producer_ts}",
            correlation_id=f"visual_fact:{event.producer_ts}",
        )
        messages.extend(_candidate_messages(candidate))
        return messages

    if envelope.message_type != "player_input":
        return [
            {
                "message_type": "ack",
                "payload": {
                    "accepted": False,
                    "source_type": envelope.message_type,
                    "route": "unknown",
                },
            }
        ]

    event = _parse_player_input(envelope.payload)
    route = runtime.accept_player_input(event)
    messages: list[dict[str, object]] = [
        {
            "message_type": "ack",
            "payload": {
                "accepted": route["accepted"],
                "source_type": envelope.message_type,
                "route": route["route"],
            },
        }
    ]

    event_trace.record(event.intent_type)

    if route["route"] == "character_service" and isinstance(event, DialogueSubmit):
        response = character_service.handle_dialogue(event)
        event_trace.record(response.output_type)
        messages.append(_as_envelope("dialogue_response", response.model_dump()))
        return messages

    if route["route"] == "character_service" and isinstance(event, FocusTargetChange):
        state = focus_state.update_focus(event)
        conversation_relation_service.apply_focus_state(
            actor_id=event.actor_id,
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            target_actor_id=event.target_actor_id or "",
            target_object_id=event.target_object_id or "",
            producer_ts=event.producer_ts,
        )
        summary = character_service.handle_focus_target_change(event)
        event_trace.record("focus_target_change")
        event_trace.record(summary["summary"])
        messages.append(_as_envelope("focus_state", state))
        messages.extend(_ensure_runtime_snapshot_messages(event))

        focus_delta = _project_runtime_delta(event.actor_id, event.producer_ts)
        if focus_delta is not None:
            messages.append(focus_delta)

        candidate = conversation_relation_service.build_candidate_event(
            actor_id=event.actor_id,
            causation_id=f"focus:{event.producer_ts}",
            correlation_id=f"focus:{event.producer_ts}",
        )
        messages.extend(_candidate_messages(candidate))
        return messages

    if route["route"] == "esm_service" and isinstance(event, InteractIntent):
        actor_position = runtime.get_actor_position(event.actor_id)
        world_result = esm_service.resolve_interaction(event, actor_position=actor_position)
        event_trace.record(world_result.result_type)
        messages.append(_as_envelope("world_result", world_result.model_dump()))

        if world_result.result_type == "object_interaction_result":
            environment_result = esm_service.emit_environment_shift(
                room_id=event.room_id,
                target_environment_id="env_lamp",
                previous_state="stable",
                current_state="alerted",
            )
            event_trace.record(environment_result.result_type)
            messages.append(_as_envelope("world_result", environment_result.model_dump()))

            siming_output = siming_service.evaluate_world_event(
                room_id=event.room_id,
                actor_id="char_b",
                object_id=event.target_object_id,
                event_type=world_result.result_type,
            )
            event_trace.record(siming_output.output_type)
            messages.append(_as_envelope("siming_output", siming_output.model_dump()))

            conversation_relation_service.apply_world_result(
                actor_id=event.actor_id,
                room_id=event.room_id,
                scene_id=event.scene_id,
                zone_id=event.zone_id,
                target_object_id=event.target_object_id,
                result_type=world_result.result_type,
                producer_ts=event.producer_ts,
            )
            messages.extend(_ensure_runtime_snapshot_messages(event))
            projection_delta = _project_runtime_delta(event.actor_id, event.producer_ts)
            if projection_delta is not None:
                messages.append(projection_delta)
            candidate = conversation_relation_service.build_candidate_event(
                actor_id=event.actor_id,
                causation_id=f"world:{event.producer_ts}",
                correlation_id=f"world:{event.producer_ts}",
            )
            messages.extend(_candidate_messages(candidate))
        return messages

    return messages


def _parse_player_input(payload: dict) -> MoveIntent | DialogueSubmit | InteractIntent | FocusTargetChange:
    intent_type = payload.get("intent_type", "")
    if intent_type == "dialogue_submit":
        return DialogueSubmit(**payload)
    if intent_type == "interact_intent":
        return InteractIntent(**payload)
    if intent_type == "move_intent":
        return MoveIntent(**payload)
    if intent_type == "focus_target_change":
        return FocusTargetChange(**payload)
    raise ValueError(f"unsupported intent_type: {intent_type}")


def _as_envelope(message_type: str, payload: dict[str, object]) -> dict[str, object]:
    return {
        "message_type": message_type,
        "payload": payload,
    }


def _ensure_runtime_snapshot_messages(event: MoveIntent | DialogueSubmit | InteractIntent | FocusTargetChange) -> list[dict[str, object]]:
    return _ensure_runtime_snapshot(
        actor_id=event.actor_id,
        room_id=event.room_id,
        scene_id=event.scene_id,
        zone_id=event.zone_id,
        producer_ts=event.producer_ts,
    )


def _ensure_runtime_snapshot(*, actor_id: str, room_id: str, scene_id: str, zone_id: str, producer_ts: int) -> list[dict[str, object]]:
    if character_runtime_state_service.get_snapshot(actor_id) is not None:
        return []

    snapshot = character_runtime_state_service.get_or_create_snapshot(
        actor_id=actor_id,
        room_id=room_id,
        scene_id=scene_id,
        zone_id=zone_id,
        producer_ts=producer_ts,
    )
    event_trace.record("character_runtime_state_snapshot")
    return [_as_envelope("character_runtime_state_snapshot", snapshot.model_dump())]


def _project_runtime_delta(actor_id: str, fallback_producer_ts: int) -> dict[str, object] | None:
    projection = conversation_relation_service.project_runtime_state(actor_id)
    if not isinstance(projection, dict):
        return None

    runtime_delta = character_runtime_state_service.apply_runtime_projection(
        actor_id=actor_id,
        room_id=str(projection.get("room_id", "")),
        scene_id=str(projection.get("scene_id", "")),
        zone_id=str(projection.get("zone_id", "")),
        producer_ts=int(projection.get("producer_ts", fallback_producer_ts)),
        current_focus_target=str(projection.get("current_focus_target", "")),
        current_attention_source=str(projection.get("current_attention_source", "")),
        nearby_actor_refs=[str(entry) for entry in projection.get("nearby_actor_refs", [])],
        nearby_object_refs=[str(entry) for entry in projection.get("nearby_object_refs", [])],
        nearby_environment_refs=[str(entry) for entry in projection.get("nearby_environment_refs", [])],
        conversation_candidate_refs=[str(entry) for entry in projection.get("conversation_candidate_refs", [])],
        engagement_pressure=str(projection.get("engagement_pressure", "")),
        privacy_risk_hint=str(projection.get("privacy_risk_hint", "")),
    )
    if runtime_delta is None:
        return None

    event_trace.record("character_runtime_state_delta")
    return _as_envelope("character_runtime_state_delta", runtime_delta.model_dump(exclude_none=True))


def _candidate_messages(candidate: object) -> list[dict[str, object]]:
    from app.models.runtime_state import ConversationCandidateEvent

    if not isinstance(candidate, ConversationCandidateEvent):
        return []
    if not conversation_relation_service.should_emit_candidate(candidate):
        return []

    event_trace.record("conversation_candidate_event")
    messages = [_as_envelope("conversation_candidate_event", candidate.model_dump())]

    conversation_relation_service.apply_candidate_summary(candidate)
    runtime_delta = _project_runtime_delta(candidate.actor_id, candidate.producer_ts)
    if runtime_delta is not None:
        messages.append(runtime_delta)

    siming_candidate_output = siming_service.evaluate_candidate_relationship(candidate)
    event_trace.record(siming_candidate_output.output_type)
    messages.append(_as_envelope("siming_output", siming_candidate_output.model_dump()))
    return messages
