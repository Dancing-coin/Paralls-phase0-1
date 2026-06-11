import asyncio
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, Response
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from app.debug_narration import (
    build_debug_event,
    summarize_backend_route,
    summarize_character_input_from_candidate,
    summarize_character_input_from_character_perceived,
    summarize_character_input_from_self_body_perceived,
    summarize_character_candidate,
    summarize_character_input,
    summarize_character_input_from_fact,
    summarize_character_input_from_siming_output,
    summarize_character_input_from_world_result,
    summarize_character_interpretation,
    summarize_character_output,
    summarize_raw_fact_event,
    summarize_siming_output,
    summarize_world_result,
)
from app.debug_stream import debug_stream
from app.models.environment_request import EnvironmentRequest
from app.models.player_input import DialogueSubmit, FocusTargetChange, InteractIntent, MoveIntent
from app.models.raw_fact import RawFactEvent
from app.models.runtime_state import ConversationCandidateEvent
from app.models.self_body_perceived import SelfBodyPerceivedEvent
from app.models.visual_fact import VisualFactEvent
from app.models.world_result import WorldResultBase
from app.services.candidate_percept_service import compile_candidate_percepts
from app.services.character_service import CharacterService
from app.services.character_perceived_input_service import CharacterPerceivedInputService
from app.services.character_agent_runtime import CharacterAgentRuntime
from app.services.character_runtime_state_service import CharacterRuntimeStateService
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.conversation_relation_service import ConversationRelationService
from app.services.esm_service import ESMService
from app.services.event_trace_service import EventTraceService
from app.services.fact_handlers.visual_fact_handler import (
    VisualFactHandlerContext,
    handle_visual_fact_event,
)
from app.services.fact_router import route_raw_fact_event
from app.services.focus_state_service import FocusStateService
from app.services.frontend_authority_event_projection import (
    FRONTEND_AUTHORITY_EVENT_TYPES,
    FrontendAuthorityEventProjector,
)
from app.services.per_character_percept_filter import filter_candidate_for_actor
from app.services.phase0_authority_event_adapter import Phase0AuthorityEventAdapter
from app.services.session_runtime import SessionRuntime
from app.services.siming_audit_writer import SimingAuditWriter
from app.services.siming_event_consumer import SimingEventConsumer
from app.services.siming_event_pipeline import SimingEventPipeline
from app.services.siming_event_producer import SimingEventProducer
from app.services.siming_runtime import SimingRuntime
from app.ws_protocol import Envelope

app = FastAPI(title="Paralls Phase0 Backend")
BACKEND_BUILD = "paralls-phase0-backend-worktree-2026-06-02"
WORKTREE_ROOT = str(Path(__file__).resolve().parents[2])
STATIC_DIR = Path(__file__).resolve().parent / "static"


def reset_runtime_state() -> None:
    global runtime
    global character_service
    global character_perceived_input_service
    global character_agent_runtime
    global esm_service
    global event_trace
    global focus_state
    global conversation_relation_service
    global character_runtime_state_service
    global authority_event_adapter
    global authority_event_bus
    global siming_audit_writer
    global siming_event_pipeline
    global frontend_authority_event_projector

    runtime = SessionRuntime()
    character_service = CharacterService()
    if "character_perceived_input_service" not in globals():
        character_perceived_input_service = CharacterPerceivedInputService()
    else:
        character_perceived_input_service.clear()
    character_agent_runtime = CharacterAgentRuntime()
    esm_service = ESMService()
    event_trace = EventTraceService()
    focus_state = FocusStateService()
    conversation_relation_service = ConversationRelationService()
    character_runtime_state_service = CharacterRuntimeStateService()
    authority_event_adapter = Phase0AuthorityEventAdapter()
    authority_event_bus = InMemoryAuthorityEventBus()
    siming_audit_writer = SimingAuditWriter()
    siming_event_pipeline = SimingEventPipeline(
        bus=authority_event_bus,
        consumer=SimingEventConsumer(),
        runtime=SimingRuntime(),
        producer=SimingEventProducer(authority_event_bus),
        audit_writer=siming_audit_writer,
    )
    for event_type in SimingEventConsumer.ALLOWED_EVENT_TYPES:
        authority_event_bus.subscribe(event_type, siming_event_pipeline.handle_event)
    frontend_authority_event_projector = FrontendAuthorityEventProjector()
    for event_type in FRONTEND_AUTHORITY_EVENT_TYPES:
        authority_event_bus.subscribe(event_type, frontend_authority_event_projector.handle_event)
    debug_stream.clear()


reset_runtime_state()


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "build": BACKEND_BUILD,
        "worktree_root": WORKTREE_ROOT,
    }


@app.get("/debug/panel", response_class=HTMLResponse)
def debug_panel() -> str:
    return (STATIC_DIR / "debug-panel.html").read_text(encoding="utf-8")


@app.get("/debug/static/debug-panel.js")
def debug_panel_js() -> Response:
    return Response(
        content=(STATIC_DIR / "debug-panel.js").read_text(encoding="utf-8"),
        media_type="application/javascript",
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            try:
                raw = await websocket.receive_json()
                envelope = Envelope(**raw)
                outbound = _handle_envelope(envelope)
            except (ValidationError, ValueError, TypeError) as exc:
                source_type = "unknown"
                if isinstance(raw, dict):
                    source_type = str(raw.get("message_type", "unknown"))
                outbound = [_as_error_ack(source_type=source_type, route="invalid_payload", error=exc)]
            for message in outbound:
                await websocket.send_json(message)
    except WebSocketDisconnect:
        return


@app.websocket("/debug/ws")
async def debug_websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    history, queue = debug_stream.snapshot_and_subscribe()
    for event in history:
        await websocket.send_json(event)
    try:
        while True:
            event_task = asyncio.create_task(queue.get())
            disconnect_task = asyncio.create_task(websocket.receive_text())
            done, pending = await asyncio.wait(
                {event_task, disconnect_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()

            if disconnect_task in done:
                disconnect_task.result()
                continue

            event = event_task.result()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        return
    finally:
        debug_stream.unsubscribe(queue)


def _handle_envelope(envelope: Envelope) -> list[dict[str, object]]:
    if envelope.message_type == "visual_fact_event":
        event = VisualFactEvent(**envelope.payload)
        _publish_debug_event(
            build_debug_event(
                producer_ts=event.producer_ts,
                domain="world",
                stage="l1_raw_fact_ingress",
                actor_id=event.actor_id,
                summary=summarize_raw_fact_event(event),
                detail=event.to_legacy_payload(),
            )
        )
        _publish_debug_event(
            build_debug_event(
                producer_ts=event.producer_ts,
                domain="character",
                stage="character_input_received",
                actor_id=event.actor_id,
                summary=summarize_character_input_from_fact(event),
                detail=event.to_legacy_payload(),
            )
        )
        messages = handle_visual_fact_event(
            event,
            envelope.message_type,
            _build_visual_fact_handler_context(),
        )
        _publish_route_event(event, messages)
        return _finalize_outbound_messages(messages)

    if envelope.message_type == "raw_fact_event":
        event = RawFactEvent(**envelope.payload)
        _publish_debug_event(
            build_debug_event(
                producer_ts=event.producer_ts,
                domain="world",
                stage="l1_raw_fact_ingress",
                actor_id=event.source.actor_id or None,
                summary=summarize_raw_fact_event(event),
                detail=event.model_dump(),
            )
        )
        if event.source.actor_id != "":
            _publish_debug_event(
                build_debug_event(
                    producer_ts=event.producer_ts,
                    domain="character",
                    stage="character_input_received",
                    actor_id=event.source.actor_id,
                summary=summarize_character_input_from_fact(event),
                detail=event.model_dump(),
            )
        )
        compiled_candidates = compile_candidate_percepts(event)
        character_agent_messages: list[dict[str, object]] = []
        for candidate in compiled_candidates:
            _publish_debug_event(
                build_debug_event(
                    producer_ts=candidate.producer_ts,
                    domain="backend",
                    stage="candidate_percept_compiled",
                    actor_id=candidate.source_actor_id or None,
                    summary=summarize_character_input_from_candidate(candidate),
                    detail=candidate.model_dump(),
                )
            )
            candidate_actor_ids: list[str] = []
            if candidate.target_actor_id != "":
                candidate_actor_ids.append(candidate.target_actor_id)
            elif event.source.actor_id:
                candidate_actor_ids.append(event.source.actor_id)

            for actor_id in candidate_actor_ids:
                perceived = filter_candidate_for_actor(
                    candidate,
                    actor_id=actor_id,
                    context={"is_facing_target": True},
                )
                if perceived is not None:
                    if _should_suppress_character_agent_candidate_from_focus_mirror(
                        candidate=candidate,
                        actor_id=actor_id,
                    ):
                        continue
                    _ = character_perceived_input_service.apply_character_perceived_event(perceived)
                    _publish_debug_event(
                        build_debug_event(
                            producer_ts=perceived.producer_ts,
                            domain="character",
                            stage="character_perceived_applied",
                            actor_id=perceived.actor_id,
                            summary=summarize_character_input_from_character_perceived(perceived),
                            detail=perceived.model_dump(),
                        )
                    )
                    character_agent_messages.extend(
                        _as_character_agent_output_envelopes(
                            character_agent_runtime.ingest_character_perceived_event(perceived)
                        )
                    )
        messages = route_raw_fact_event(
            event,
            source_type=envelope.message_type,
            context=_build_visual_fact_handler_context(),
        )
        messages.extend(character_agent_messages)
        _publish_route_event(event, messages)
        return _finalize_outbound_messages(messages)

    if envelope.message_type == "environment_request":
        event = EnvironmentRequest(**envelope.payload)
        action_request = esm_service.build_environment_action_request(event)
        messages: list[dict[str, object]] = [
            {
                "message_type": "ack",
                "payload": {
                    "accepted": True,
                    "source_type": envelope.message_type,
                    "route": "esm_service",
                },
            }
        ]
        _publish_debug_event(
            build_debug_event(
                producer_ts=event.producer_ts,
                domain="world",
                stage="world_interaction_requested",
                actor_id=None,
                summary="收到 environment_request，目标是 %s。" % ",".join(event.target_entity_refs.get("environment_ids", [])),
                detail=event.model_dump(),
            )
        )
        event_trace.record("environment_request")
        event_trace.record("action_request")
        messages.append(_as_action_request_envelope(action_request.model_dump()))
        resolution, environment_result = esm_service.resolve_environment_request(event)
        event_trace.record(resolution.result_type)
        messages.extend(_publish_world_result_authority_event(resolution, source_event=event))
        if environment_result is not None:
            transition_trigger_type = "environment_request.light_level_drop"
            transition_from_state = "stable"
            if event.requested_change_type == "thermal_level_rise":
                transition_trigger_type = "environment_request.thermal_level_rise"
            elif event.requested_change_type == "smoke_density_rise":
                transition_trigger_type = "environment_request.smoke_density_rise"
            elif event.requested_change_type == "noise_level_rise":
                transition_trigger_type = "environment_request.noise_level_rise"
            elif event.requested_change_type == "light_level_restore":
                transition_trigger_type = "environment_request.light_level_restore"
                transition_from_state = "alerted"
            transition = esm_service.emit_state_machine_transition(
                room_id=event.room_id,
                scene_id=event.scene_id,
                zone_id=event.zone_id,
                entity_id="env_lamp",
                machine_id=environment_result.machine_id,
                from_state=transition_from_state,
                to_state=environment_result.current_state,
                trigger_type=transition_trigger_type,
                transition_reason="environment request accepted",
                producer_ts=environment_result.producer_ts,
                causation_id=event.causation_id,
                correlation_id=event.correlation_id,
            )
            event_trace.record(transition.event_type)
            event_trace.record(environment_result.result_type)
            messages.extend(_publish_state_machine_transition_authority_event(transition))
            messages.extend(_publish_world_result_authority_event(environment_result, source_event=event))
        return _finalize_outbound_messages(messages)

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
    _publish_debug_event(
        build_debug_event(
            producer_ts=event.producer_ts,
            domain="backend",
            stage="player_input_routed",
            actor_id=getattr(event, "actor_id", None),
            summary="后端接受了玩家输入，并路由到 %s。" % route["route"],
            detail={"intent_type": event.intent_type, "route": route["route"]},
        )
    )

    event_trace.record(event.intent_type)

    if route["route"] == "character_service" and isinstance(event, DialogueSubmit):
        _publish_debug_event(
            build_debug_event(
                producer_ts=event.producer_ts,
                domain="character",
                stage="character_input_received",
                actor_id=event.target_actor_id,
                summary=summarize_character_input(event.target_actor_id, "收到玩家对话输入"),
                detail=event.model_dump(),
            )
        )
        response = character_service.handle_dialogue(event)
        event_trace.record(response.output_type)
        messages.append(_as_envelope("dialogue_response", response.model_dump()))
        return _finalize_outbound_messages(messages)

    if route["route"] == "local_motion" and isinstance(event, MoveIntent):
        _publish_debug_event(
            build_debug_event(
                producer_ts=event.producer_ts,
                domain="character",
                stage="character_input_received",
                actor_id=event.actor_id,
                summary=summarize_character_input(event.actor_id, "收到移动输入"),
                detail=event.model_dump(),
            )
        )
        messages.extend(_ensure_runtime_snapshot_messages(event))
        return _finalize_outbound_messages(messages)

    if route["route"] == "character_service" and isinstance(event, FocusTargetChange):
        _publish_debug_event(
            build_debug_event(
                producer_ts=event.producer_ts,
                domain="character",
                stage="character_input_received",
                actor_id=event.actor_id,
                summary=summarize_character_input(event.actor_id, "收到焦点切换输入"),
                detail=event.model_dump(),
            )
        )
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
        _publish_debug_event(
            build_debug_event(
                producer_ts=event.producer_ts,
                domain="character",
                stage="character_interpretation_updated",
                actor_id=event.actor_id,
                summary=summarize_character_interpretation(event.actor_id, {"current_focus_target": event.target_actor_id or event.target_object_id or "", "current_attention_source": "focus_state"}),
                detail=state,
            )
        )
        return _finalize_outbound_messages(messages)

    if route["route"] == "esm_service" and isinstance(event, InteractIntent):
        action_request = esm_service.build_action_request(event)
        _publish_debug_event(
            build_debug_event(
                producer_ts=event.producer_ts,
                domain="world",
                stage="world_interaction_requested",
                actor_id=event.actor_id,
                summary="玩家请求与 %s 交互。" % event.target_object_id,
                detail=event.model_dump(),
            )
        )
        event_trace.record("action_request")
        messages.append(_as_action_request_envelope(action_request.model_dump()))
        actor_position = runtime.get_actor_position(event.actor_id)
        world_result = esm_service.resolve_interaction(event, actor_position=actor_position)
        event_trace.record(world_result.result_type)

        if world_result.result_type == "action_resolution_result":
            messages.extend(_publish_world_result_authority_event(world_result, source_event=event))
            _publish_debug_event(
                build_debug_event(
                    producer_ts=world_result.producer_ts,
                    domain="character",
                    stage="character_input_received",
                    actor_id=event.actor_id,
                    summary=summarize_character_input_from_world_result(event.actor_id, world_result.model_dump()),
                    detail=world_result.model_dump(),
                )
            )
            transition = esm_service.emit_state_machine_transition(
                room_id=event.room_id,
                scene_id=event.scene_id,
                zone_id=event.zone_id,
                entity_id=event.target_object_id,
                machine_id="visibility",
                from_state="partially_visible",
                to_state="visible",
                trigger_type="interact.inspect",
                transition_reason="player inspect interaction accepted",
                producer_ts=world_result.producer_ts + 1,
                causation_id=world_result.causation_id,
                correlation_id=world_result.correlation_id,
            )
            event_trace.record(transition.event_type)
            messages.extend(_publish_state_machine_transition_authority_event(transition))

            object_state_result = esm_service.emit_object_state_result(
                room_id=event.room_id,
                scene_id=event.scene_id,
                zone_id=event.zone_id,
                actor_id=event.actor_id,
                target_object_id=event.target_object_id,
                previous_state="partially_visible",
                current_state="visible",
                producer_ts=world_result.producer_ts + 2,
                request_ref=world_result.request_ref,
                causation_id=world_result.causation_id,
                correlation_id=world_result.correlation_id,
            )
            event_trace.record(object_state_result.result_type)
            messages.extend(_publish_world_result_authority_event(object_state_result, source_event=event))

            body_state_result = esm_service.emit_body_state_result(
                room_id=event.room_id,
                scene_id=event.scene_id,
                zone_id=event.zone_id,
                actor_id=event.actor_id,
                body_state_class="interaction_strain",
                previous_state="steady",
                current_state="engaged",
                producer_ts=world_result.producer_ts + 3,
                request_ref=world_result.request_ref,
                causation_id=world_result.causation_id,
                correlation_id=world_result.correlation_id,
            )
            event_trace.record(body_state_result.result_type)
            messages.extend(_publish_world_result_authority_event(body_state_result, source_event=event))
            self_body_perceived = SelfBodyPerceivedEvent(
                actor_id=event.actor_id,
                body_state_class=body_state_result.body_state_class,
                producer_ts=body_state_result.producer_ts,
                room_id=body_state_result.room_id,
                scene_id=body_state_result.scene_id,
                zone_id=body_state_result.zone_id,
                perceived_summary="%s is %s" % (body_state_result.body_state_class, body_state_result.current_state),
                source_body_result_id=body_state_result.result_id,
            )
            _ = character_perceived_input_service.apply_self_body_perceived_event(self_body_perceived)
            messages.append(_as_envelope("self_body_perceived_event", self_body_perceived.model_dump()))
            messages.extend(
                _as_character_agent_output_envelopes(
                    character_agent_runtime.ingest_self_body_perceived_event(self_body_perceived)
                )
            )

            environment_result = esm_service.emit_environment_shift(
                room_id=event.room_id,
                scene_id=event.scene_id,
                zone_id=event.zone_id,
                actor_id=event.actor_id,
                target_environment_id="env_lamp",
                previous_state="stable",
                current_state="alerted",
                producer_ts=world_result.producer_ts + 4,
                request_ref=world_result.request_ref,
                causation_id=world_result.causation_id,
                correlation_id=world_result.correlation_id,
            )
            event_trace.record(environment_result.result_type)
            messages.extend(_publish_world_result_authority_event(environment_result, source_event=event))

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
        else:
            messages.extend(_publish_world_result_authority_event(world_result, source_event=event))
            _publish_debug_event(
                build_debug_event(
                    producer_ts=world_result.producer_ts,
                    domain="character",
                    stage="character_input_received",
                    actor_id=event.actor_id,
                    summary=summarize_character_input_from_world_result(event.actor_id, world_result.model_dump()),
                    detail=world_result.model_dump(),
                )
            )
        return _finalize_outbound_messages(messages)

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


def _as_character_agent_output_envelopes(commands: list[object]) -> list[dict[str, object]]:
    return [
        {
            "message_type": "character_agent_output",
            "payload": command.model_dump(exclude_none=True),
        }
        for command in commands
    ]


def _should_suppress_character_agent_candidate_from_focus_mirror(
    *,
    candidate: object,
    actor_id: str,
) -> bool:
    if getattr(candidate, "source_fact_family", "") != "visual_fact":
        return False
    if getattr(candidate, "source_fact_type", "") != "fixed_gaze_on_target":
        return False

    focus = focus_state.get_focus(getattr(candidate, "source_actor_id", "") or "")
    if not isinstance(focus, dict):
        return False

    target_actor_id = str(getattr(candidate, "target_actor_id", "") or "")
    target_object_id = str(getattr(candidate, "target_object_id", "") or "")
    if target_actor_id != "" and target_actor_id != actor_id:
        return False
    if target_object_id != "":
        focus_target = str(focus.get("target_object_id", "") or "")
        if focus_target != target_object_id:
            return False
    elif target_actor_id != "":
        focus_target = str(focus.get("target_actor_id", "") or "")
        if focus_target != target_actor_id:
            return False
    else:
        return False

    focus_ts = int(str(focus.get("producer_ts", "0") or "0"))
    producer_ts = int(getattr(candidate, "producer_ts", 0) or 0)
    return abs(focus_ts - producer_ts) <= 160


def _as_error_ack(*, source_type: str, route: str, error: Exception) -> dict[str, object]:
    return {
        "message_type": "ack",
        "payload": {
            "accepted": False,
            "source_type": source_type,
            "route": route,
            "error_type": type(error).__name__,
            "error_message": str(error),
        },
    }


def _as_action_request_envelope(payload: dict[str, object]) -> dict[str, object]:
    source = payload.get("source", {})
    if not isinstance(source, dict):
        source = {}
    return {
        "message_type": "action_request",
        "event_id": str(payload.get("request_id", "") or ""),
        "event_type": "action_request",
        "producer_ts": int(payload.get("producer_ts", 0) or 0),
        "room_id": str(payload.get("room_id", "") or ""),
        "scene_id": str(payload.get("scene_id", "") or ""),
        "zone_id": str(payload.get("zone_id", "") or ""),
        "source": {
            "layer": str(source.get("layer", "") or ""),
            "system": str(source.get("system", "") or ""),
            "actor_id": str(source.get("actor_id", "") or ""),
            "object_id": str(source.get("object_id", "") or ""),
        },
        "routing": {
            "audience_mode": "authority_broadcast",
            "routing_mode": "authoritative_event_bus",
            "dialog_group_id": None,
            "target_ids": [],
        },
        "priority": "p1",
        "ttl": payload.get("constraints_hint", {}).get("ttl") if isinstance(payload.get("constraints_hint"), dict) else None,
        "durability": "replayable",
        "causation_id": str(payload.get("causation_id", "") or ""),
        "correlation_id": str(payload.get("correlation_id", "") or ""),
        "payload": payload,
    }


def _as_state_machine_transition_envelope(payload: dict[str, object]) -> dict[str, object]:
    return {
        "message_type": "state_machine_transition",
        "event_id": str(payload.get("event_id", "") or ""),
        "event_type": str(payload.get("event_type", "state_machine_transition") or "state_machine_transition"),
        "room_id": str(payload.get("room_id", "") or ""),
        "scene_id": str(payload.get("scene_id", "") or ""),
        "zone_id": str(payload.get("zone_id", "") or ""),
        "entity_id": str(payload.get("entity_id", "") or ""),
        "machine_id": str(payload.get("machine_id", "") or ""),
        "from_state": str(payload.get("from_state", "") or ""),
        "to_state": str(payload.get("to_state", "") or ""),
        "trigger_type": str(payload.get("trigger_type", "") or ""),
        "transition_reason": str(payload.get("transition_reason", "") or ""),
        "producer_ts": int(payload.get("producer_ts", 0) or 0),
        "causation_id": str(payload.get("causation_id", "") or ""),
        "correlation_id": str(payload.get("correlation_id", "") or ""),
        "payload": payload,
    }


def _as_world_result_envelope(payload: dict[str, object]) -> dict[str, object]:
    target_object_id = str(payload.get("target_object_id", "") or "")
    target_environment_id = str(payload.get("target_environment_id", "") or "")
    entity_id = str(payload.get("entity_id", "") or "")
    object_id = entity_id or target_object_id or target_environment_id or None
    return {
        "message_type": "world_result",
        "event_id": str(payload.get("result_id", "") or ""),
        "event_type": str(payload.get("result_type", "world_result") or "world_result"),
        "producer_ts": int(payload.get("producer_ts", 0) or 0),
        "room_id": str(payload.get("room_id", "") or ""),
        "scene_id": str(payload.get("scene_id", "") or ""),
        "zone_id": str(payload.get("zone_id", "") or ""),
        "entity_id": entity_id,
        "source": {
            "layer": "L1",
            "system": "esm",
            "actor_id": str(payload.get("actor_id", "") or ""),
            "object_id": object_id,
        },
        "routing": {
            "audience_mode": "authority_broadcast",
            "routing_mode": "authoritative_event_bus",
            "dialog_group_id": None,
            "target_ids": [],
        },
        "priority": "p1",
        "ttl": None,
        "durability": "replayable",
        "causation_id": str(payload.get("causation_id", "") or ""),
        "correlation_id": str(payload.get("correlation_id", "") or ""),
        "payload": payload,
    }


def _publish_visual_fact_authority_event(event: VisualFactEvent) -> list[dict[str, object]]:
    authority_event = authority_event_adapter.visual_fact_event(event)
    authority_event_bus.publish(authority_event)
    event_trace.record(authority_event.event_type)
    return _drain_frontend_authority_events()


def _publish_world_result_authority_event(
    result: WorldResultBase,
    *,
    source_event: object,
) -> list[dict[str, object]]:
    authority_event = authority_event_adapter.world_result_event(result, source_event=source_event)
    frontend_authority_event_projector.handle_event(authority_event)
    authority_event_bus.publish(authority_event)
    event_trace.record(authority_event.event_type)
    return _drain_frontend_authority_events()


def _publish_candidate_authority_event(event: ConversationCandidateEvent) -> list[dict[str, object]]:
    authority_event = authority_event_adapter.conversation_candidate_event(event)
    frontend_authority_event_projector.handle_event(authority_event)
    authority_event_bus.publish(authority_event)
    event_trace.record(authority_event.event_type)
    return _drain_frontend_authority_events()


def _publish_state_machine_transition_authority_event(event: object) -> list[dict[str, object]]:
    authority_event = authority_event_adapter.state_machine_transition_event(event)
    frontend_authority_event_projector.handle_event(authority_event)
    authority_event_bus.publish(authority_event)
    event_trace.record(authority_event.event_type)
    return _drain_frontend_authority_events()


def _drain_frontend_authority_events() -> list[dict[str, object]]:
    return frontend_authority_event_projector.drain()


def _finalize_outbound_messages(messages: list[dict[str, object]]) -> list[dict[str, object]]:
    messages.extend(_drain_frontend_authority_events())
    messages = _insert_character_agent_outputs_after_siming(messages)
    _emit_debug_from_messages(messages)
    return messages


def _insert_character_agent_outputs_after_siming(messages: list[dict[str, object]]) -> list[dict[str, object]]:
    ordered: list[dict[str, object]] = []
    for message in messages:
        ordered.append(message)
        if message.get("message_type") != "siming_output":
            continue
        payload = message.get("payload", {})
        if not isinstance(payload, dict):
            continue
        ordered.extend(_as_character_agent_output_envelopes(character_agent_runtime.ingest_siming_output(payload)))
    return ordered


def _publish_debug_event(event: dict[str, object]) -> None:
    debug_stream.publish(event)


def _publish_route_event(event: RawFactEvent | VisualFactEvent, messages: list[dict[str, object]]) -> None:
    if not messages:
        return
    first = messages[0]
    if first.get("message_type") != "ack":
        return
    payload = first.get("payload", {})
    if not isinstance(payload, dict):
        return
    route = str(payload.get("route", "unknown"))
    producer_ts = int(getattr(event, "producer_ts", 0))
    actor_id = None
    if isinstance(event, RawFactEvent):
        actor_id = event.source.actor_id or None
    else:
        actor_id = event.actor_id
    _publish_debug_event(
        build_debug_event(
            producer_ts=producer_ts,
            domain="backend",
            stage="fact_routed",
            actor_id=actor_id,
            summary=summarize_backend_route(event, route),
            detail={"route": route, "fact_family": getattr(event, "fact_family", "visual_fact"), "fact_type": event.fact_type},
        )
    )


def _ensure_runtime_snapshot_messages(event: MoveIntent | DialogueSubmit | InteractIntent | FocusTargetChange) -> list[dict[str, object]]:
    return _ensure_runtime_snapshot(
        actor_id=event.actor_id,
        room_id=event.room_id,
        scene_id=event.scene_id,
        zone_id=event.zone_id,
        producer_ts=event.producer_ts,
    )


def _ensure_runtime_snapshot_for_visual_fact(event: VisualFactEvent) -> list[dict[str, object]]:
    return _ensure_runtime_snapshot(
        actor_id=event.actor_id,
        room_id=event.room_id,
        scene_id=event.scene_id,
        zone_id=event.zone_id,
        producer_ts=event.producer_ts,
    )


def _build_visual_fact_handler_context() -> VisualFactHandlerContext:
    return VisualFactHandlerContext(
        conversation_relation_service=conversation_relation_service,
        event_trace=event_trace,
        ensure_runtime_snapshot_for_event=_ensure_runtime_snapshot_for_visual_fact,
        project_runtime_delta=_project_runtime_delta,
        candidate_messages=_candidate_messages,
        publish_visual_fact=_publish_visual_fact_authority_event,
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
    conversation_relation_service.apply_candidate_summary(candidate)
    runtime_delta = _project_runtime_delta(candidate.actor_id, candidate.producer_ts)
    messages = _publish_candidate_authority_event(candidate)
    if runtime_delta is not None:
        insert_index = 1 if messages and messages[0].get("message_type") == "conversation_candidate_event" else len(messages)
        messages.insert(insert_index, runtime_delta)
    return messages


def _emit_debug_from_messages(messages: list[dict[str, object]]) -> None:
    for message in messages:
        message_type = str(message.get("message_type", ""))
        payload = message.get("payload", {})
        if not isinstance(payload, dict):
            continue
        producer_ts = int(payload.get("producer_ts", 0) or 0)
        if message_type == "character_runtime_state_delta":
            actor_id = str(payload.get("actor_id", ""))
            _publish_debug_event(
                build_debug_event(
                    producer_ts=producer_ts,
                    domain="character",
                    stage="character_interpretation_updated",
                    actor_id=actor_id,
                    summary=summarize_character_interpretation(actor_id, payload),
                    detail=payload,
                )
            )
        elif message_type == "conversation_candidate_event":
            actor_id = str(payload.get("actor_id", ""))
            _publish_debug_event(
                build_debug_event(
                    producer_ts=producer_ts,
                    domain="character",
                    stage="character_candidate_updated",
                    actor_id=actor_id,
                    summary=summarize_character_candidate(actor_id, payload),
                    detail=payload,
                )
            )
        elif message_type == "dialogue_response":
            actor_id = str(payload.get("actor_id", ""))
            _publish_debug_event(
                build_debug_event(
                    producer_ts=producer_ts,
                    domain="character",
                    stage="character_output_emitted",
                    actor_id=actor_id,
                    summary=summarize_character_output(actor_id, message_type, payload),
                    detail=payload,
                )
            )
        elif message_type == "spatial_access_runtime_state_snapshot":
            actor_id = str(payload.get("actor_id", ""))
            _publish_debug_event(
                build_debug_event(
                    producer_ts=producer_ts,
                    domain="character",
                    stage="character_interpretation_updated",
                    actor_id=actor_id,
                    summary=summarize_character_interpretation(actor_id, payload),
                    detail=payload,
                )
            )
        elif message_type == "world_result":
            _publish_debug_event(
                build_debug_event(
                    producer_ts=producer_ts,
                    domain="world",
                    stage="world_result_emitted",
                    actor_id=str(payload.get("actor_id", "")) or None,
                    summary=summarize_world_result(payload),
                    detail=payload,
                )
            )
        elif message_type == "state_machine_transition":
            _publish_debug_event(
                build_debug_event(
                    producer_ts=producer_ts,
                    domain="world",
                    stage="world_result_emitted",
                    actor_id=None,
                    summary="状态机转移：%s %s -> %s。"
                    % (
                        str(payload.get("entity_id", "") or "entity"),
                        str(payload.get("from_state", "") or "unknown"),
                        str(payload.get("to_state", "") or "unknown"),
                    ),
                    detail=payload,
                )
            )
        elif message_type == "siming_output":
            target_actor_id = str(payload.get("target_actor_id", "")) or None
            if target_actor_id:
                _publish_debug_event(
                    build_debug_event(
                        producer_ts=producer_ts,
                        domain="character",
                        stage="character_input_received",
                        actor_id=target_actor_id,
                        summary=summarize_character_input_from_siming_output(payload),
                        detail=payload,
                    )
                )
            _publish_debug_event(
                build_debug_event(
                    producer_ts=producer_ts,
                    domain="siming",
                    stage="siming_output_emitted",
                    actor_id=target_actor_id,
                    summary=summarize_siming_output(payload),
                    detail=payload,
                )
            )
        elif message_type == "self_body_perceived_event":
            actor_id = str(payload.get("actor_id", "") or "")
            _publish_debug_event(
                build_debug_event(
                    producer_ts=producer_ts,
                    domain="character",
                    stage="self_body_perceived_applied",
                    actor_id=actor_id,
                    summary=summarize_character_input_from_self_body_perceived(payload),
                    detail=payload,
                )
            )
