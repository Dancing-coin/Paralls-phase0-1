import asyncio
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, Response
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from app.config import settings
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
from app.transport_projection import (
    is_known_stream_mode,
    normalize_stream_mode,
    project_outbound_messages,
)
from app.models.authority_event import AuthorityEvent, AuthorityEventRouting, AuthorityEventSource
from app.models.environment_request import EnvironmentRequest
from app.models.character_agent_runtime import CharacterGoalCommand
from app.models.character_agent_runtime import CharacterSuggestionPacket
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
from app.services.interaction_orchestration_service import InteractionOrchestrationService, StructuredInteractionRequest
from app.services.per_character_percept_filter import filter_candidate_for_actor
from app.services.phase0_authority_event_adapter import Phase0AuthorityEventAdapter
from app.services.session_input_router import SessionInputRouter
from app.services.siming_audit_writer import SimingAuditWriter
from app.world_runtime.projection import project_world_result_delta
from app.world_runtime.l1_fact_projection import FactProjectionLayer
from app.world_runtime.l1_occupancy import SpatialOccupancyService
from app.world_runtime.l1_runtime_perception_bridge import (
    L1ActorProjectionInput,
    L1RuntimePerceptionBridge,
    MixedPerceptionCaptureError,
)
from app.services.siming_character_dispatch_adapter import SimingCharacterDispatchAdapter, SimingCharacterDispatchResult
from app.services.siming_event_consumer import SimingEventConsumer
from app.services.siming_event_pipeline import SimingEventPipeline
from app.services.siming_event_producer import SimingEventProducer
from app.services.siming_llm_provider import build_siming_llm_provider
from app.services.siming_debug_projection import SimingDebugProjection
from app.services.siming_runtime import SimingRuntime
from app.services.character_agent_debug_projection import CharacterAgentDebugProjection
from app.services.script_beat_projection import ScriptBeatProjection
from app.services.world_outcome_debug_projection import WorldOutcomeDebugProjection
from app.ws_protocol import Envelope
from app.character_agent.execution.l4_adapter import CharacterAgentL4Adapter
from app.character_agent.execution.l4_executor import CharacterAgentL4Executor

app = FastAPI(title="Paralls Phase0 Backend")
BACKEND_BUILD = "paralls-phase0-backend-worktree-2026-06-02"
WORKTREE_ROOT = str(Path(__file__).resolve().parents[2])
STATIC_DIR = Path(__file__).resolve().parent / "static"
_pending_siming_character_dispatch_messages: dict[str, list[dict[str, object]]] = {}


class FrontendSimingCharacterDispatchAdapter(SimingCharacterDispatchAdapter):
    def dispatch(self, event: AuthorityEvent) -> SimingCharacterDispatchResult:
        result = super().dispatch(event)
        _queue_siming_character_dispatch_messages(event.event_id, result)
        return result


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
    global character_agent_l4_executor
    global character_agent_l4_adapter
    global character_agent_debug_projection
    global siming_debug_projection
    global world_outcome_debug_projection
    global script_beat_projection
    global l1_occupancy_service
    global l1_projection_layer
    global l1_perception_bridge
    global interaction_orchestration_service
    global _pending_siming_character_dispatch_messages

    runtime = SessionInputRouter()
    character_service = CharacterService()
    if "character_perceived_input_service" not in globals():
        character_perceived_input_service = CharacterPerceivedInputService()
    else:
        character_perceived_input_service.clear()
    character_agent_runtime = CharacterAgentRuntime()
    esm_service = ESMService()
    interaction_orchestration_service = InteractionOrchestrationService(esm_service=esm_service)
    l1_occupancy_service = SpatialOccupancyService()
    l1_projection_layer = FactProjectionLayer()
    l1_perception_bridge = L1RuntimePerceptionBridge()
    event_trace = EventTraceService()
    focus_state = FocusStateService()
    conversation_relation_service = ConversationRelationService()
    character_runtime_state_service = CharacterRuntimeStateService()
    authority_event_adapter = Phase0AuthorityEventAdapter()
    authority_event_bus = InMemoryAuthorityEventBus()
    if "siming_audit_writer" not in globals():
        siming_audit_writer = SimingAuditWriter()
    else:
        siming_audit_writer.reset()
    _pending_siming_character_dispatch_messages = {}
    siming_event_pipeline = SimingEventPipeline(
        bus=authority_event_bus,
        consumer=SimingEventConsumer(),
        runtime=SimingRuntime(llm_provider=build_siming_llm_provider(settings)),
        producer=SimingEventProducer(authority_event_bus),
        audit_writer=siming_audit_writer,
        character_dispatch_adapter=FrontendSimingCharacterDispatchAdapter(runtime=character_agent_runtime),
    )
    for event_type in SimingEventConsumer.ALLOWED_EVENT_TYPES:
        authority_event_bus.subscribe(event_type, siming_event_pipeline.handle_event, consumer_id="siming")
    frontend_authority_event_projector = FrontendAuthorityEventProjector()
    character_agent_l4_executor = CharacterAgentL4Executor()
    character_agent_l4_adapter = CharacterAgentL4Adapter(executor=character_agent_l4_executor)
    character_agent_debug_projection = CharacterAgentDebugProjection()
    siming_debug_projection = SimingDebugProjection()
    world_outcome_debug_projection = WorldOutcomeDebugProjection()
    script_beat_projection = ScriptBeatProjection()
    for event_type in FRONTEND_AUTHORITY_EVENT_TYPES:
        authority_event_bus.subscribe(
            event_type,
            frontend_authority_event_projector.handle_event,
            consumer_id="frontend_projector",
        )
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


@app.get("/debug/siming/read-model/{room_id}")
def debug_siming_read_model(room_id: str) -> dict[str, object]:
    read_model = siming_audit_writer.latest_read_model(room_id=room_id)
    if read_model is None:
        return {"room_id": room_id, "status": "missing"}
    return read_model.model_dump(exclude_none=True)


@app.post("/interaction/orchestrate")
def orchestrate_structured_interaction(payload: StructuredInteractionRequest) -> dict[str, object]:
    return interaction_orchestration_service.execute(payload).model_dump()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    raw_stream_mode = websocket.query_params.get("stream_mode")
    stream_mode = normalize_stream_mode(raw_stream_mode)
    if not is_known_stream_mode(raw_stream_mode):
        _publish_debug_event(
            build_debug_event(
                producer_ts=0,
                domain="transport",
                stage="unknown_stream_mode",
                actor_id=None,
                summary=f"unknown stream mode {raw_stream_mode!r}; using full",
                detail={"raw_stream_mode": raw_stream_mode, "resolved_stream_mode": stream_mode},
            )
        )
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
            projected = project_outbound_messages(outbound, stream_mode=stream_mode)
            for message in projected:
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
        messages.extend(_character_agent_messages_from_fact_candidates(event))
        _publish_route_event(event, messages)
        return _finalize_outbound_messages(messages)

    if envelope.message_type == "raw_fact_event":
        raw_payload = envelope.payload if isinstance(envelope.payload, dict) else {}
        provider_refs = _l1_provider_refs_from_payload(raw_payload)
        event = RawFactEvent(**raw_payload)
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
        projected_facts = _ingest_l1_world_fact_foundation(event)
        character_agent_messages = _character_agent_messages_from_fact_candidates(event)
        messages = route_raw_fact_event(
            event,
            source_type=envelope.message_type,
            context=_build_visual_fact_handler_context(),
        )
        messages.extend(character_agent_messages)
        messages.extend(_messages_from_projected_l1_facts(projected_facts, provider_refs=provider_refs))
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
            l1_occupancy_service.apply_environment_result(environment_result)
            messages.extend(_messages_from_projected_l1_facts(_project_l1_facts_for_dirty_zones(environment_result.producer_ts)))
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

    if envelope.message_type == "character_actor_status":
        return [
            {
                "message_type": "ack",
                "payload": {
                    "accepted": True,
                    "source_type": envelope.message_type,
                    "route": "character_actor_runtime_status",
                },
            }
        ]

    if envelope.message_type == "character_agent_execution":
        payload = envelope.payload if isinstance(envelope.payload, dict) else {}
        actor_id = str(payload.get("actor_id", "") or "")
        route_name = "esm_service"
        bundle = payload.get("action_request_bundle", {})
        requested_actions = bundle.get("requested_actions", []) if isinstance(bundle, dict) else []
        if isinstance(requested_actions, list):
            for action in requested_actions:
                if isinstance(action, dict) and str(action.get("request_type", "") or "") in {"speak_public", "speak_private", "share_info", "withhold"}:
                    route_name = "character_service"
                    break
        messages: list[dict[str, object]] = [
            {
                "message_type": "ack",
                "payload": {
                    "accepted": True,
                    "source_type": envelope.message_type,
                    "route": route_name,
                },
            }
        ]
        action_requests = _as_character_agent_action_request_envelopes(payload, producer_ts=0)
        messages.extend(action_requests)
        for action in requested_actions:
            if not isinstance(action, dict):
                continue
            if str(action.get("request_type", "") or "") in {"speak_public", "speak_private", "share_info", "withhold"}:
                character_agent_runtime.record_execution_request(
                    actor_id=actor_id,
                    producer_ts=0,
                    payload=action,
                )
                dialogue_event = DialogueSubmit(
                    player_id="character_agent",
                    room_id="room_demo",
                    scene_id="scene_demo",
                    zone_id="zone_focus",
                    actor_id=str(action.get("actor_id", "") or actor_id),
                    intent_type="dialogue_submit",
                    producer_ts=0,
                    target_actor_id=str(action.get("target_actor_id", "") or ""),
                    content=str(action.get("content", "") or ""),
                )
                response = character_service.handle_dialogue(dialogue_event)
                character_agent_runtime.record_dialogue_response(
                    actor_id=dialogue_event.actor_id,
                    producer_ts=int(response.producer_ts or 0),
                    payload=response.model_dump(),
                )
                messages.append(
                    {
                        "message_type": "dialogue_response",
                        "payload": response.model_dump(),
                    }
                )
                continue
            character_agent_runtime.record_execution_request(
                actor_id=actor_id,
                producer_ts=0,
                payload=action,
            )
            request_type = str(action.get("request_type", "") or "")
            if request_type == "approach":
                world_result = _actor_target_action_settlement(
                    actor_id=actor_id,
                    request_type=request_type,
                    target_actor_id=str(action.get("target_actor_id", "") or ""),
                )
                character_agent_runtime.record_settlement_result(
                    actor_id=actor_id,
                    producer_ts=1,
                    payload=world_result,
                )
                messages.append(_as_world_result_envelope(world_result))
                var_social_spatial_result = _as_social_spatial_runtime_result(world_result)
                if var_social_spatial_result is not None:
                    messages.append(var_social_spatial_result)
                continue
            if request_type == "follow_target":
                world_result = _actor_target_action_settlement(
                    actor_id=actor_id,
                    request_type=request_type,
                    target_actor_id=str(action.get("target_actor_id", "") or ""),
                )
                character_agent_runtime.record_settlement_result(
                    actor_id=actor_id,
                    producer_ts=1,
                    payload=world_result,
                )
                messages.append(_as_world_result_envelope(world_result))
                var_social_spatial_result = _as_social_spatial_runtime_result(world_result)
                if var_social_spatial_result is not None:
                    messages.append(var_social_spatial_result)
                continue
            if request_type == "seek_private_distance":
                world_result = _actor_target_action_settlement(
                    actor_id=actor_id,
                    request_type=request_type,
                    target_actor_id=str(action.get("target_actor_id", "") or ""),
                )
                character_agent_runtime.record_settlement_result(
                    actor_id=actor_id,
                    producer_ts=1,
                    payload=world_result,
                )
                messages.append(_as_world_result_envelope(world_result))
                var_social_spatial_result = _as_social_spatial_runtime_result(world_result)
                if var_social_spatial_result is not None:
                    messages.append(var_social_spatial_result)
                continue
            if request_type == "withdraw":
                world_result = _actor_target_action_settlement(
                    actor_id=actor_id,
                    request_type=request_type,
                    target_actor_id=str(action.get("target_actor_id", "") or ""),
                )
                character_agent_runtime.record_settlement_result(
                    actor_id=actor_id,
                    producer_ts=1,
                    payload=world_result,
                )
                messages.append(_as_world_result_envelope(world_result))
                var_social_spatial_result = _as_social_spatial_runtime_result(world_result)
                if var_social_spatial_result is not None:
                    messages.append(var_social_spatial_result)
                continue
            if request_type == "break_contact":
                world_result = _actor_target_action_settlement(
                    actor_id=actor_id,
                    request_type=request_type,
                    target_actor_id=str(action.get("target_actor_id", "") or ""),
                )
                character_agent_runtime.record_settlement_result(
                    actor_id=actor_id,
                    producer_ts=1,
                    payload=world_result,
                )
                messages.append(_as_world_result_envelope(world_result))
                var_social_spatial_result = _as_social_spatial_runtime_result(world_result)
                if var_social_spatial_result is not None:
                    messages.append(var_social_spatial_result)
                continue
            if request_type != "interact":
                continue
            interact_event = InteractIntent(
                player_id="character_agent",
                room_id="room_demo",
                scene_id="scene_demo",
                zone_id="zone_focus",
                actor_id=str(action.get("actor_id", "") or actor_id),
                intent_type="interact_intent",
                producer_ts=0,
                target_object_id=str(action.get("target_object_id", "") or ""),
                interaction_type=str(action.get("interaction_type", "inspect") or "inspect"),
            )
            world_result = esm_service.resolve_interaction(interact_event)
            character_agent_runtime.record_settlement_result(
                actor_id=interact_event.actor_id,
                producer_ts=int(world_result.producer_ts or 0),
                payload=world_result.model_dump(exclude_none=True),
            )
            messages.extend(_publish_world_result_authority_event(world_result, source_event=interact_event))
        return _finalize_outbound_messages(messages)

    if envelope.message_type == "character_supervision_authorization":
        payload = envelope.payload if isinstance(envelope.payload, dict) else {}
        state = character_agent_runtime.apply_supervision_authorization(payload)
        return _finalize_outbound_messages(
            [
                {
                    "message_type": "ack",
                    "payload": {
                        "accepted": True,
                        "source_type": envelope.message_type,
                        "route": "character_supervision_runtime",
                    },
                },
                {
                    "message_type": "character_supervision_state",
                    "payload": state.model_dump(),
                },
            ]
        )

    if envelope.message_type == "character_supervision_clear":
        payload = envelope.payload if isinstance(envelope.payload, dict) else {}
        actor_id = str(payload.get("actor_id", "") or "")
        producer_ts = int(payload.get("producer_ts", 0) or 0)
        reason = str(payload.get("reason", "") or "external_supervision_clear")
        state = character_agent_runtime.clear_supervision_authorization(
            actor_id=actor_id,
            producer_ts=producer_ts,
            reason=reason,
        )
        return _finalize_outbound_messages(
            [
                {
                    "message_type": "ack",
                    "payload": {
                        "accepted": True,
                        "source_type": envelope.message_type,
                        "route": "character_supervision_runtime",
                    },
                },
                {
                    "message_type": "character_supervision_state",
                    "payload": state.model_dump(),
                },
            ]
        )

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
                "request_id": event.request_id,
                "intent_type": event.intent_type,
                "producer_ts": event.producer_ts,
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
        print(
            "phase0_failed_interaction_diag actor_id=%s target_object_id=%s actor_position=%s result_type=%s"
            % (
                event.actor_id,
                event.target_object_id,
                actor_position,
                world_result.result_type,
            )
        )
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
            l1_occupancy_service.apply_object_state_update(
                object_id=object_state_result.target_object_id,
                zone_id=object_state_result.zone_id,
                state=object_state_result.current_state,
                affordances=["inspect", "read"],
                occludes=False,
                producer_ts=object_state_result.producer_ts,
                source_ref=object_state_result.result_id,
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
            self_body_commands = character_agent_runtime.ingest_self_body_perceived_event(self_body_perceived)
            messages.extend(_as_character_agent_execution_envelopes(self_body_commands))
            character_agent_runtime.run_scheduled_background_cognition_ticks(self_body_perceived.producer_ts)
            if event.actor_id != "char_c":
                messages.extend(
                    _as_character_agent_suggestion_envelopes(
                        character_agent_runtime.drain_suggestion_packets(event.actor_id)
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
            l1_occupancy_service.apply_environment_result(environment_result)
            messages.extend(_messages_from_projected_l1_facts(_project_l1_facts_for_dirty_zones(environment_result.producer_ts)))
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


def _as_character_agent_execution_envelopes(commands: list[CharacterGoalCommand]) -> list[dict[str, object]]:
    envelopes: list[dict[str, object]] = []
    for command in commands:
        envelopes.append(
            {
                "message_type": "character_agent_execution",
                "payload": character_agent_l4_adapter.command_to_execution_payload(command),
            }
        )
    return envelopes


def _as_character_agent_action_request_envelopes(
    execution_payload: dict[str, object],
    *,
    producer_ts: int,
) -> list[dict[str, object]]:
    bundle = execution_payload.get("action_request_bundle", {})
    if not isinstance(bundle, dict):
        return []
    requested_actions = bundle.get("requested_actions", [])
    if not isinstance(requested_actions, list):
        return []

    messages: list[dict[str, object]] = []
    actor_id = str(execution_payload.get("actor_id", "") or "")
    for idx, action in enumerate(requested_actions):
        if not isinstance(action, dict):
            continue
        request_type = str(action.get("request_type", "") or "")
        if request_type == "interact":
            target_object_id = str(action.get("target_object_id", "") or "")
            payload = {
                "request_id": f"character_agent:{producer_ts}:{actor_id}:{idx}",
                "request_type": "interact",
                "room_id": "room_demo",
                "scene_id": "scene_demo",
                "zone_id": "zone_focus",
                "actor_id": actor_id,
                "action_type": "character_agent_execution",
                "source": {
                    "layer": "L4",
                    "system": "character_agent_l4",
                    "actor_id": actor_id,
                },
                "target_entity_refs": {
                    "actor_ids": [],
                    "object_ids": [target_object_id] if target_object_id else [],
                    "environment_ids": [],
                },
                "action_profile": str(action.get("interaction_type", "inspect") or "inspect"),
                "intent_strength": "normal",
                "constraints_hint": {},
                "producer_ts": producer_ts,
                "causation_id": f"character_agent:{producer_ts}:{actor_id}",
                "correlation_id": f"character_agent:{producer_ts}:{actor_id}",
                "target_object_id": target_object_id,
                "payload": {
                    "interaction_type": str(action.get("interaction_type", "inspect") or "inspect"),
                },
            }
            messages.append(_as_action_request_envelope(payload))
        elif request_type == "approach":
            target_actor_id = str(action.get("target_actor_id", "") or "")
            payload = {
                "request_id": f"character_agent:{producer_ts}:{actor_id}:{idx}",
                "request_type": "approach",
                "room_id": "room_demo",
                "scene_id": "scene_demo",
                "zone_id": "zone_focus",
                "actor_id": actor_id,
                "action_type": "character_agent_execution",
                "source": {
                    "layer": "L4",
                    "system": "character_agent_l4",
                    "actor_id": actor_id,
                },
                "target_entity_refs": {
                    "actor_ids": [target_actor_id] if target_actor_id else [],
                    "object_ids": [],
                    "environment_ids": [],
                },
                "action_profile": "approach",
                "intent_strength": "normal",
                "constraints_hint": {},
                "producer_ts": producer_ts,
                "causation_id": f"character_agent:{producer_ts}:{actor_id}",
                "correlation_id": f"character_agent:{producer_ts}:{actor_id}",
                "target_actor_id": target_actor_id,
                "payload": {},
            }
            messages.append(_as_action_request_envelope(payload))
        elif request_type == "seek_private_distance":
            target_actor_id = str(action.get("target_actor_id", "") or "")
            payload = {
                "request_id": f"character_agent:{producer_ts}:{actor_id}:{idx}",
                "request_type": "seek_private_distance",
                "room_id": "room_demo",
                "scene_id": "scene_demo",
                "zone_id": "zone_focus",
                "actor_id": actor_id,
                "action_type": "character_agent_execution",
                "source": {
                    "layer": "L4",
                    "system": "character_agent_l4",
                    "actor_id": actor_id,
                },
                "target_entity_refs": {
                    "actor_ids": [target_actor_id] if target_actor_id else [],
                    "object_ids": [],
                    "environment_ids": [],
                },
                "action_profile": "seek_private_distance",
                "intent_strength": "normal",
                "constraints_hint": {},
                "producer_ts": producer_ts,
                "causation_id": f"character_agent:{producer_ts}:{actor_id}",
                "correlation_id": f"character_agent:{producer_ts}:{actor_id}",
                "target_actor_id": target_actor_id,
                "payload": {},
            }
            messages.append(_as_action_request_envelope(payload))
        elif request_type == "withdraw":
            target_actor_id = str(action.get("target_actor_id", "") or "")
            payload = {
                "request_id": f"character_agent:{producer_ts}:{actor_id}:{idx}",
                "request_type": "withdraw",
                "room_id": "room_demo",
                "scene_id": "scene_demo",
                "zone_id": "zone_focus",
                "actor_id": actor_id,
                "action_type": "character_agent_execution",
                "source": {
                    "layer": "L4",
                    "system": "character_agent_l4",
                    "actor_id": actor_id,
                },
                "target_entity_refs": {
                    "actor_ids": [target_actor_id] if target_actor_id else [],
                    "object_ids": [],
                    "environment_ids": [],
                },
                "action_profile": "withdraw",
                "intent_strength": "normal",
                "constraints_hint": {},
                "producer_ts": producer_ts,
                "causation_id": f"character_agent:{producer_ts}:{actor_id}",
                "correlation_id": f"character_agent:{producer_ts}:{actor_id}",
                "target_actor_id": target_actor_id,
                "payload": {},
            }
            messages.append(_as_action_request_envelope(payload))
        elif request_type == "follow_target":
            target_actor_id = str(action.get("target_actor_id", "") or "")
            payload = {
                "request_id": f"character_agent:{producer_ts}:{actor_id}:{idx}",
                "request_type": "follow_target",
                "room_id": "room_demo",
                "scene_id": "scene_demo",
                "zone_id": "zone_focus",
                "actor_id": actor_id,
                "action_type": "character_agent_execution",
                "source": {
                    "layer": "L4",
                    "system": "character_agent_l4",
                    "actor_id": actor_id,
                },
                "target_entity_refs": {
                    "actor_ids": [target_actor_id] if target_actor_id else [],
                    "object_ids": [],
                    "environment_ids": [],
                },
                "action_profile": "follow_target",
                "intent_strength": "normal",
                "constraints_hint": {},
                "producer_ts": producer_ts,
                "causation_id": f"character_agent:{producer_ts}:{actor_id}",
                "correlation_id": f"character_agent:{producer_ts}:{actor_id}",
                "target_actor_id": target_actor_id,
                "payload": {},
            }
            messages.append(_as_action_request_envelope(payload))
        elif request_type == "break_contact":
            target_actor_id = str(action.get("target_actor_id", "") or "")
            payload = {
                "request_id": f"character_agent:{producer_ts}:{actor_id}:{idx}",
                "request_type": "break_contact",
                "room_id": "room_demo",
                "scene_id": "scene_demo",
                "zone_id": "zone_focus",
                "actor_id": actor_id,
                "action_type": "character_agent_execution",
                "source": {
                    "layer": "L4",
                    "system": "character_agent_l4",
                    "actor_id": actor_id,
                },
                "target_entity_refs": {
                    "actor_ids": [target_actor_id] if target_actor_id else [],
                    "object_ids": [],
                    "environment_ids": [],
                },
                "action_profile": "break_contact",
                "intent_strength": "normal",
                "constraints_hint": {},
                "producer_ts": producer_ts,
                "causation_id": f"character_agent:{producer_ts}:{actor_id}",
                "correlation_id": f"character_agent:{producer_ts}:{actor_id}",
                "target_actor_id": target_actor_id,
                "payload": {},
            }
            messages.append(_as_action_request_envelope(payload))
        elif request_type == "speak_public":
            target_actor_id = str(action.get("target_actor_id", "") or "")
            messages.append(
                {
                    "message_type": "character_agent_dialogue_request",
                    "payload": {
                        "actor_id": actor_id,
                        "target_actor_id": target_actor_id,
                        "content": str(action.get("content", "") or ""),
                        "producer_ts": producer_ts,
                        "source_system": "character_agent_l4",
                    },
                }
            )
        elif request_type == "speak_private":
            target_actor_id = str(action.get("target_actor_id", "") or "")
            messages.append(
                {
                    "message_type": "character_agent_dialogue_request",
                    "payload": {
                        "actor_id": actor_id,
                        "target_actor_id": target_actor_id,
                        "content": str(action.get("content", "") or ""),
                        "producer_ts": producer_ts,
                        "source_system": "character_agent_l4",
                    },
                }
            )
        elif request_type == "share_info":
            target_actor_id = str(action.get("target_actor_id", "") or "")
            messages.append(
                {
                    "message_type": "character_agent_dialogue_request",
                    "payload": {
                        "actor_id": actor_id,
                        "target_actor_id": target_actor_id,
                        "content": str(action.get("content", "") or ""),
                        "producer_ts": producer_ts,
                        "source_system": "character_agent_l4",
                    },
                }
            )
        elif request_type == "withhold":
            target_actor_id = str(action.get("target_actor_id", "") or "")
            messages.append(
                {
                    "message_type": "character_agent_dialogue_request",
                    "payload": {
                        "actor_id": actor_id,
                        "target_actor_id": target_actor_id,
                        "content": str(action.get("content", "") or ""),
                        "producer_ts": producer_ts,
                        "source_system": "character_agent_l4",
                    },
                }
            )
    return messages


def _as_character_agent_suggestion_envelopes(
    packets: list[CharacterSuggestionPacket],
) -> list[dict[str, object]]:
    return [
        {
            "message_type": "character_agent_suggestion",
            "payload": packet.model_dump(exclude_none=True),
        }
        for packet in packets
    ]


def _queue_siming_character_dispatch_messages(authority_event_id: str, result: SimingCharacterDispatchResult) -> None:
    messages: list[dict[str, object]] = []
    commands_by_actor = getattr(result, "commands_by_actor", {})
    if isinstance(commands_by_actor, dict):
        for commands in commands_by_actor.values():
            if isinstance(commands, list):
                messages.extend(_as_character_agent_execution_envelopes(commands))
    delivery_inputs = getattr(result, "delivery_inputs", [])
    for delivery_input in delivery_inputs if isinstance(delivery_inputs, list) else []:
        actor_id = str(getattr(delivery_input, "actor_id", "") or "")
        producer_ts = int(getattr(delivery_input, "producer_ts", 0) or 0)
        if producer_ts > 0:
            character_agent_runtime.run_scheduled_background_cognition_ticks(producer_ts)
        messages.extend(
            _as_character_agent_suggestion_envelopes(character_agent_runtime.drain_suggestion_packets(actor_id))
        )
    if messages:
        _pending_siming_character_dispatch_messages.setdefault(authority_event_id, []).extend(messages)


def _drain_siming_character_dispatch_messages(authority_event_id: str) -> list[dict[str, object]]:
    return _pending_siming_character_dispatch_messages.pop(authority_event_id, [])


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


def _ingest_l1_world_fact_foundation(event: RawFactEvent) -> list[RawFactEvent]:
    if event.source.system == "world_runtime.l1_fact_projection":
        return []
    if event.fact_family != "spatial_access_fact":
        return []
    if event.fact_type == "actor_entered_zone":
        l1_occupancy_service.apply_actor_zone_update(
            actor_id=event.source.actor_id,
            previous_zone_id="",
            next_zone_id=event.zone_id,
            producer_ts=event.producer_ts,
            source_ref=f"raw_fact_event:{event.fact_type}:{event.producer_ts}",
        )
    elif event.fact_type == "actor_left_zone":
        l1_occupancy_service.apply_actor_zone_update(
            actor_id=event.source.actor_id,
            previous_zone_id=event.zone_id,
            next_zone_id="",
            producer_ts=event.producer_ts,
            source_ref=f"raw_fact_event:{event.fact_type}:{event.producer_ts}",
        )
    elif event.fact_type == "actor_left_actor_range":
        l1_occupancy_service.apply_actor_proximity_update(
            actor_id=event.source.actor_id,
            target_actor_id=event.targets.actor_id,
            producer_ts=event.producer_ts,
            source_ref=f"raw_fact_event:{event.fact_type}:{event.producer_ts}",
            is_near=False,
        )
    elif event.fact_type == "actor_left_object_range":
        l1_occupancy_service.apply_actor_proximity_update(
            actor_id=event.source.actor_id,
            target_object_id=event.targets.object_id,
            producer_ts=event.producer_ts,
            source_ref=f"raw_fact_event:{event.fact_type}:{event.producer_ts}",
            is_near=False,
        )
    elif event.fact_type in {"actor_approached_actor", "actor_approached_object"}:
        l1_occupancy_service.apply_actor_proximity_update(
            actor_id=event.source.actor_id,
            target_actor_id=event.targets.actor_id,
            target_object_id=event.targets.object_id,
            distance_m=event.world.distance_m,
            producer_ts=event.producer_ts,
            source_ref=f"raw_fact_event:{event.fact_type}:{event.producer_ts}",
        )
    else:
        return []
    if event.targets.actor_id == "" and event.targets.object_id == "":
        return []
    return l1_projection_layer.project_actor_target_facts(
        l1_occupancy_service.snapshot(),
        actor_id=event.source.actor_id,
        target_actor_id=event.targets.actor_id,
        target_object_id=event.targets.object_id,
        producer_ts=event.producer_ts + 1,
    )


def _project_l1_facts_for_dirty_zones(producer_ts: int) -> list[RawFactEvent]:
    snapshot = l1_occupancy_service.snapshot()
    facts: list[RawFactEvent] = []
    for zone_id in snapshot.dirty_zone_ids:
        zone = snapshot.zone_states.get(zone_id)
        if zone is None:
            continue
        target_object_id = zone.object_ids[0] if zone.object_ids else ""
        for actor_id in zone.actor_ids:
            facts.extend(
                l1_projection_layer.project_actor_target_facts(
                    snapshot,
                    actor_id=actor_id,
                    target_object_id=target_object_id,
                    producer_ts=producer_ts + 1,
                )
            )
    return facts


def _l1_provider_refs_from_payload(payload: dict[str, object]) -> dict[str, list[dict[str, object]]] | None:
    raw_refs = payload.get("l1_provider_refs") or payload.get("provider_refs")
    if not isinstance(raw_refs, dict):
        return None

    normalized: dict[str, list[dict[str, object]]] = {}
    direct_keys = {
        "visual_inputs",
        "spatial_inputs",
        "auditory_inputs",
        "embodied_inputs",
        "skeletal_inputs",
        "environment_inputs",
    }
    artifact_key_map = {
        "visual_ref": "visual_inputs",
        "spatial_ref": "spatial_inputs",
        "auditory_ref": "auditory_inputs",
        "embodied_ref": "embodied_inputs",
    }

    for key in direct_keys:
        entries = raw_refs.get(key)
        if isinstance(entries, list):
            normalized[key] = _normalize_l1_provider_ref_entries(entries)

    for artifact_key, bridge_key in artifact_key_map.items():
        entry = raw_refs.get(artifact_key)
        if isinstance(entry, dict):
            normalized.setdefault(bridge_key, []).extend(_normalize_l1_provider_ref_entries([entry]))

    normalized = {key: entries for key, entries in normalized.items() if entries}
    return normalized or None


def _normalize_l1_provider_ref_entries(entries: list[object]) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        provider_kind = str(entry.get("provider_kind", "") or "")
        if provider_kind == "":
            provider_kind = _provider_kind_from_ref_entry(entry)
        ref_id = _ref_id_from_ref_entry(entry) or str(entry.get("ref_id", "") or "")
        if provider_kind == "" or ref_id == "":
            continue
        normalized_entry: dict[str, object] = {
                "provider_kind": provider_kind,
                "ref_id": ref_id,
                "summary": str(entry.get("summary", "") or entry.get("semantic_summary", "") or "runtime provider ref"),
                "retention": str(entry.get("retention", "") or "debug_artifact"),
        }
        for passthrough_key in (
            "runtime_source_refs",
            "stable_source_ref",
            "camera_pose",
            "actor_node_path",
            "target_ref",
            "actor_frame_ref",
            "camera_frame_ref",
            "listener_frame_ref",
        ):
            if passthrough_key in entry:
                normalized_entry[passthrough_key] = entry[passthrough_key]
        for capture_key in (
            "capture_root_id",
            "capture_id",
            "clock_domain",
            "monotonic_tick",
            "source_frame_index",
            "wall_clock_ts",
            "sample_ref_id",
        ):
            if capture_key in entry:
                normalized_entry[capture_key] = entry[capture_key]
        normalized.append(normalized_entry)
    return normalized


def _provider_kind_from_ref_entry(entry: dict[str, object]) -> str:
    ref_type = str(entry.get("ref_type", "") or entry.get("kind", "") or "")
    if ref_type in {"visual_patch", "spatial_patch", "auditory_context", "embodied_state"}:
        return ref_type
    source = str(entry.get("source", "") or "")
    if "visual" in source or "camera" in source or "viewport" in source:
        return "visual_patch"
    if "spatial" in source or "occupancy" in source:
        return "spatial_patch"
    if "auditory" in source:
        return "auditory_context"
    if "embodied" in source or "actor" in source:
        return "embodied_state"
    return ""


def _ref_id_from_ref_entry(entry: dict[str, object]) -> str:
    for key in ("artifact_ref", "runtime_source_ref", "viewport_capture_ref"):
        value = entry.get(key)
        if isinstance(value, str) and value:
            return value
    runtime_refs = entry.get("runtime_source_refs")
    if isinstance(runtime_refs, list):
        for value in runtime_refs:
            if isinstance(value, str) and value:
                return value
    camera_pose = entry.get("camera_pose")
    if isinstance(camera_pose, dict):
        capture_ref = camera_pose.get("viewport_capture_ref") or camera_pose.get("artifact_ref")
        if isinstance(capture_ref, str) and capture_ref:
            return capture_ref
    return ""


def _messages_from_projected_l1_facts(
    projected_facts: list[RawFactEvent],
    *,
    provider_refs: dict[str, list[dict[str, object]]] | None = None,
) -> list[dict[str, object]]:
    messages: list[dict[str, object]] = []
    projected_by_actor: dict[str, list[RawFactEvent]] = {}
    for fact in projected_facts:
        _publish_debug_event(
            build_debug_event(
                producer_ts=fact.producer_ts,
                domain="world",
                stage="l1_fact_projected",
                actor_id=fact.source.actor_id or None,
                summary=summarize_raw_fact_event(fact),
                detail=fact.model_dump(),
            )
        )
        messages.extend(
            route_raw_fact_event(
                fact,
                source_type="raw_fact_event",
                context=_build_visual_fact_handler_context(),
            )
        )
        messages.extend(_character_agent_messages_from_fact_candidates(fact))
        actor_id = fact.source.actor_id or fact.targets.actor_id
        if actor_id:
            projected_by_actor.setdefault(actor_id, []).append(fact)
    if not projected_by_actor:
        return messages
    actor_projections = [
        _projection_input_for_actor(actor_id, actor_facts, provider_refs)
        for actor_id, actor_facts in projected_by_actor.items()
    ]
    latest_ts = max(fact.producer_ts for fact in projected_facts)
    try:
        bridge_result = l1_perception_bridge.consume_multi_actor_projected_facts(
            occupancy=l1_occupancy_service.snapshot(),
            actor_projections=actor_projections,
            character_runtime=character_agent_runtime,
            siming_runtime=siming_event_pipeline,
        )
    except MixedPerceptionCaptureError as exc:
        _publish_debug_event(
            build_debug_event(
                producer_ts=latest_ts,
                domain="world",
                stage="l1_canonical_bundle_bridge_failed",
                summary="L1 canonical bundle bridge rejected mixed capture batch",
                detail={
                    "error": str(exc),
                    "actor_ids": list(projected_by_actor.keys()),
                    "capture_roots": sorted({fact.capture_root_id for fact in projected_facts if fact.capture_root_id}),
                    "clock_domains": sorted({fact.clock_domain for fact in projected_facts if fact.clock_domain}),
                    "monotonic_ticks": sorted({int(fact.monotonic_tick) for fact in projected_facts if fact.monotonic_tick is not None}),
                },
            )
        )
        return messages
    except Exception as exc:
        _publish_debug_event(
            build_debug_event(
                producer_ts=latest_ts,
                domain="world",
                stage="l1_canonical_bundle_bridge_failed",
                summary=f"L1 canonical bundle bridge failed: {type(exc).__name__}",
                detail={"error": str(exc), "actor_ids": list(projected_by_actor.keys())},
            )
        )
        return messages
    if bridge_result is None:
        return messages
    for actor_id, actor_result in bridge_result.actor_results.items():
        _publish_debug_event(
            build_debug_event(
                producer_ts=latest_ts,
                domain="world",
                stage="l1_perception_query_frame_assembled",
                actor_id=actor_id,
                summary="L1 projected facts assembled into character and Siming PQFs",
                detail={
                    "character_frame": actor_result.get("character_frame", {}),
                    "siming_frame": bridge_result.siming_frame,
                    "context_isolation": bridge_result.context_isolation,
                },
            )
        )
        _publish_debug_event(
            build_debug_event(
                producer_ts=latest_ts,
                domain="world",
                stage="l1_canonical_percept_bundle_consumed",
                actor_id=actor_id,
                summary="L1 canonical percept bundles consumed by character and Siming runtimes",
                detail={
                    **actor_result,
                    "siming_frame": bridge_result.siming_frame,
                    "siming_bundle": bridge_result.siming_bundle,
                    "siming_result": bridge_result.siming_result,
                    "multi_actor_patch": bridge_result.multi_actor_patch,
                    "context_isolation": bridge_result.context_isolation,
                },
            )
        )
    return messages


def _projection_input_for_actor(
    actor_id: str,
    actor_facts: list[RawFactEvent],
    provider_refs: dict[str, list[dict[str, object]]] | None,
) -> L1ActorProjectionInput:
    scoped_refs = _provider_refs_for_actor(actor_id, provider_refs)
    view_refs = _projection_view_refs(actor_id, scoped_refs)
    return L1ActorProjectionInput(
        actor_id=actor_id,
        projected_facts=actor_facts,
        provider_refs=scoped_refs,
        actor_frame_ref=view_refs["actor_frame_ref"],
        camera_frame_ref=view_refs["camera_frame_ref"],
        listener_frame_ref=view_refs["listener_frame_ref"],
    )


def _provider_refs_for_actor(
    actor_id: str,
    provider_refs: dict[str, list[dict[str, object]]] | None,
) -> dict[str, list[dict[str, object]]]:
    if provider_refs is None:
        return {}
    scoped: dict[str, list[dict[str, object]]] = {}
    actor_marker = actor_id
    for key, entries in provider_refs.items():
        filtered: list[dict[str, object]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            runtime_refs = entry.get("runtime_source_refs")
            ref_id = str(entry.get("ref_id", "") or "")
            actor_node_path = str(entry.get("actor_node_path", "") or "")
            target_ref = str(entry.get("target_ref", "") or "")
            matches_actor = (
                actor_marker in ref_id
                or actor_marker in actor_node_path
                or target_ref == actor_marker
                or (
                    isinstance(runtime_refs, list)
                    and any(actor_marker in str(value) for value in runtime_refs)
                )
            )
            if matches_actor or key in {"spatial_inputs", "environment_inputs", "visual_inputs"}:
                filtered.append(dict(entry))
        if filtered:
            scoped[key] = filtered
    return scoped


def _projection_view_refs(
    actor_id: str,
    provider_refs: dict[str, list[dict[str, object]]],
) -> dict[str, str]:
    actor_frame_ref = ""
    camera_frame_ref = ""
    listener_frame_ref = ""

    embodied_entries = provider_refs.get("embodied_inputs", [])
    if embodied_entries:
        first = embodied_entries[0]
        actor_frame_ref = str(first.get("actor_frame_ref", "") or first.get("actor_node_path", "") or "")
        if actor_frame_ref == "":
            runtime_refs = first.get("runtime_source_refs")
            if isinstance(runtime_refs, list):
                actor_frame_ref = next((str(value) for value in runtime_refs if actor_id in str(value)), "")

    visual_entries = provider_refs.get("visual_inputs", [])
    if visual_entries:
        first = visual_entries[0]
        camera_pose = first.get("camera_pose")
        if isinstance(camera_pose, dict):
            camera_frame_ref = str(
                camera_pose.get("runtime_source_ref", "")
                or camera_pose.get("node_path", "")
                or camera_pose.get("viewport_artifact_ref", "")
                or ""
            )
        if camera_frame_ref == "":
            camera_frame_ref = str(first.get("camera_frame_ref", "") or first.get("ref_id", "") or "")

    auditory_entries = provider_refs.get("auditory_inputs", [])
    if auditory_entries:
        first = auditory_entries[0]
        listener_frame_ref = str(first.get("listener_frame_ref", "") or first.get("ref_id", "") or "")
        if listener_frame_ref == "":
            runtime_refs = first.get("runtime_source_refs")
            if isinstance(runtime_refs, list):
                listener_frame_ref = next((str(value) for value in runtime_refs if actor_id in str(value)), "")

    return {
        "actor_frame_ref": actor_frame_ref,
        "camera_frame_ref": camera_frame_ref,
        "listener_frame_ref": listener_frame_ref,
    }


def _character_agent_messages_from_fact_candidates(event: RawFactEvent) -> list[dict[str, object]]:
    character_agent_messages: list[dict[str, object]] = []
    for candidate in compile_candidate_percepts(event):
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
            if perceived is None:
                continue
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
            character_agent_commands = character_agent_runtime.ingest_character_perceived_event(perceived)
            character_agent_messages.extend(_as_character_agent_execution_envelopes(character_agent_commands))
            character_agent_runtime.run_scheduled_background_cognition_ticks(perceived.producer_ts)
            character_agent_messages.extend(
                _as_character_agent_suggestion_envelopes(
                    character_agent_runtime.drain_suggestion_packets(actor_id)
                )
            )
    return character_agent_messages


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
    envelope_payload = dict(payload)
    delta = project_world_result_delta(envelope_payload)
    if delta is not None:
        envelope_payload["world_runtime_delta"] = delta.model_dump()
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
        "payload": envelope_payload,
    }


def _as_social_spatial_runtime_result(payload: dict[str, object]) -> dict[str, object] | None:
    if str(payload.get("result_type", "") or "") != "action_resolution_result":
        return None
    action_profile = str(payload.get("action_profile", "") or "")
    if action_profile not in {
        "approach",
        "follow_target",
        "seek_private_distance",
        "withdraw",
        "break_contact",
    }:
        return None
    return {
        "message_type": "social_spatial_runtime_result",
        "payload": {
            "actor_id": str(payload.get("actor_id", "") or ""),
            "target_actor_id": str(payload.get("target_actor_id", "") or ""),
            "action_profile": action_profile,
            "settlement_status": str(payload.get("settlement_status", "") or ""),
            "producer_ts": int(payload.get("producer_ts", 0) or 0),
        },
    }


def _publish_visual_fact_authority_event(event: VisualFactEvent) -> list[dict[str, object]]:
    authority_event = authority_event_adapter.visual_fact_event(event)
    authority_event_bus.publish(authority_event)
    event_trace.record(authority_event.event_type)
    return _drain_frontend_authority_events()


def _actor_target_action_settlement(
    *,
    actor_id: str,
    request_type: str,
    target_actor_id: str,
) -> dict[str, object]:
    return {
        "request_ref": f"character_agent:0:{actor_id}:{request_type}",
        "result_id": f"action_resolution:character_agent:0:{actor_id}:{request_type}",
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "actor_id": actor_id,
        "source_type": "system",
        "entity_id": target_actor_id,
        "result_type": "action_resolution_result",
        "causation_id": f"character_agent:0:{actor_id}",
        "correlation_id": f"character_agent:0:{actor_id}",
        "producer_ts": 1,
        "resolution_status": "accepted",
        "resolved_entities": [target_actor_id] if target_actor_id else [],
        "applied_state_changes": ["social_spatial_state_result"],
        "stable_state_summary": f"{request_type} accepted",
        "settlement_status": "accepted",
        "target_actor_id": target_actor_id,
        "action_profile": request_type,
        "source_action_request_type": request_type,
    }


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
    messages = _insert_character_agent_execution_after_siming(messages)
    messages.extend(_observatory_messages_from_outbound(messages))
    _emit_debug_from_messages(messages)
    return messages


def _insert_character_agent_execution_after_siming(messages: list[dict[str, object]]) -> list[dict[str, object]]:
    ordered: list[dict[str, object]] = []
    for message in messages:
        ordered.append(message)
        if message.get("message_type") == "siming_output":
            payload = message.get("payload", {})
            authority_event_id = str(payload.get("authority_event_id", "") or "") if isinstance(payload, dict) else ""
            ordered.extend(_drain_siming_character_dispatch_messages(authority_event_id))
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
        elif message_type == "character_agent_debug_event":
            _publish_debug_event(
                build_debug_event(
                    producer_ts=producer_ts,
                    domain="character",
                    stage=str(payload.get("stage", "") or ""),
                    actor_id=str(payload.get("actor_id", "")) or None,
                    summary=str(payload.get("summary", "") or ""),
                    detail=payload,
                )
            )
        elif message_type == "character_agent_debug_snapshot":
            _publish_debug_event(
                build_debug_event(
                    producer_ts=producer_ts,
                    domain="character",
                    stage="character_observatory_snapshot",
                    actor_id=str(payload.get("actor_id", "")) or None,
                    summary=str(payload.get("why_now_summary", "") or payload.get("decision_summary", "") or ""),
                    detail=payload,
                )
            )
        elif message_type == "siming_debug_snapshot":
            _publish_debug_event(
                build_debug_event(
                    producer_ts=producer_ts,
                    domain="siming",
                    stage="siming_observatory_snapshot",
                    actor_id=None,
                    summary=str(payload.get("reason_summary", "") or payload.get("fairness_summary", "") or ""),
                    detail=payload,
                )
            )
        elif message_type == "world_outcome_trace":
            _publish_debug_event(
                build_debug_event(
                    producer_ts=producer_ts,
                    domain="world",
                    stage="world_outcome_trace",
                    actor_id=str(payload.get("actor_id", "")) or None,
                    summary=str(payload.get("dramatic_consequence_summary", "") or ""),
                    detail=payload,
                )
            )
        elif message_type == "script_beat_event":
            _publish_debug_event(
                build_debug_event(
                    producer_ts=producer_ts,
                    domain="world",
                    stage="script_beat_event",
                    actor_id=None,
                    summary=str(payload.get("dramatic_summary", "") or ""),
                    detail=payload,
                )
            )
        elif message_type == "scheduling_round_trace":
            _publish_debug_event(
                build_debug_event(
                    producer_ts=producer_ts,
                    domain="world",
                    stage="scheduling_round_trace",
                    actor_id=str(payload.get("lead_actor_id", "")) or None,
                    summary=str(payload.get("round_summary", "") or ""),
                    detail=payload,
                )
            )


def _observatory_messages_from_outbound(messages: list[dict[str, object]]) -> list[dict[str, object]]:
    extras: list[dict[str, object]] = []
    extras.extend(character_agent_runtime.drain_observatory_messages())
    extras.extend(siming_event_pipeline.drain_observatory_messages())
    actor_events: list[dict[str, object]] = []
    siming_events: list[dict[str, object]] = []
    world_events: list[dict[str, object]] = []
    for message in messages:
        message_type = str(message.get("message_type", "") or "")
        payload = message.get("payload", {})
        if not isinstance(payload, dict):
            continue
        if message_type == "world_result":
            for world_message in _world_outcome_observatory_messages_from_payload(payload):
                extras.append(world_message)
                world_payload = world_message.get("payload", {})
                if world_message.get("message_type") == "world_outcome_trace" and isinstance(world_payload, dict):
                    world_events.append(world_payload)
    for message in extras:
        payload = message.get("payload", {})
        if not isinstance(payload, dict):
            continue
        if message.get("message_type") == "character_agent_debug_event":
            actor_events.append(payload)
        elif message.get("message_type") == "siming_debug_event":
            siming_events.append(payload)
    extras.extend(_scheduling_round_trace_messages_from_actor_events(actor_events))
    extras.extend(_script_beat_messages_from_observatory_events(actor_events, siming_events, world_events))
    return extras


def _world_outcome_observatory_messages_from_payload(payload: dict[str, object]) -> list[dict[str, object]]:
    world_event = world_outcome_debug_projection.project(message_type="world_result", payload=payload)
    return [
        {
            "message_type": "world_outcome_trace",
            "payload": world_event.model_dump(exclude_none=True),
        },
    ]


def _scheduling_round_trace_messages_from_actor_events(
    actor_events: list[dict[str, object]],
) -> list[dict[str, object]]:
    traces: list[dict[str, object]] = []
    seen_round_ids: set[int] = set()
    for event in actor_events:
        if str(event.get("stage", "") or "") != "scheduling_round_state":
            continue
        detail = event.get("detail", {})
        if not isinstance(detail, dict):
            continue
        round_id = int(detail.get("round_id", 0) or 0)
        if round_id in seen_round_ids:
            continue
        seen_round_ids.add(round_id)
        traces.append(
            {
                "message_type": "scheduling_round_trace",
                "payload": dict(detail),
            }
        )
    return traces


def _script_beat_messages_from_observatory_events(
    actor_events: list[dict[str, object]],
    siming_events: list[dict[str, object]],
    world_events: list[dict[str, object]],
) -> list[dict[str, object]]:
    if not actor_events and not siming_events and not world_events:
        return []
    actor_models = [
        character_agent_debug_projection.project_stage_event(
            actor_id=str(event.get("actor_id", "") or ""),
            producer_ts=int(event.get("producer_ts", 0) or 0),
            stage=str(event.get("stage", "") or ""),
            summary=str(event.get("summary", "") or ""),
            focus_target=str(event.get("focus_target", "") or ""),
            intent_label=str(event.get("intent_label", "") or ""),
            participants=[str(value) for value in event.get("participants", [])],
            detail=dict(event.get("detail", {})) if isinstance(event.get("detail", {}), dict) else {},
        )
        for event in actor_events
        if str(event.get("actor_id", "") or "") != ""
    ]
    siming_models = [
        siming_debug_projection.project_event(
            source_event=_observatory_authority_event_from_payload(
                event,
                event_type="siming_debug_event",
                event_id=str(event.get("causation_id", "") or "siming_debug_event"),
            ),
            stage=str(event.get("stage", "") or ""),
            summary=str(event.get("summary", "") or ""),
            selected_path=str(event.get("selected_path", "") or ""),
            intervention_band=str(event.get("intervention_band", "") or ""),
            target_ref=str(event.get("target_ref", "") or ""),
            reason_summary=str(event.get("reason_summary", "") or ""),
            downstream_status=str(event.get("downstream_status", "") or ""),
            no_action_reason=str(event.get("no_action_reason", "") or ""),
        )
        for event in siming_events
    ]
    world_models = [
        world_outcome_debug_projection.project(message_type="world_result", payload=event)
        for event in world_events
    ]
    if not actor_models and not siming_models and not world_models:
        return []
    beat = script_beat_projection.project(actor_models, siming_models, world_models)
    return [
        {
            "message_type": "script_beat_event",
            "payload": beat.model_dump(exclude_none=True),
        }
    ]


def _observatory_authority_event_from_payload(
    payload: dict[str, object],
    *,
    event_type: str,
    event_id: str,
) -> AuthorityEvent:
    return AuthorityEvent(
        event_id=event_id,
        event_type=event_type,
        producer_ts=int(payload.get("producer_ts", 0) or 0),
        room_id=str(payload.get("room_id", "room_demo") or "room_demo"),
        scene_id=str(payload.get("scene_id", "scene_demo") or "scene_demo"),
        zone_id=str(payload.get("zone_id", "zone_focus") or "zone_focus"),
        source=AuthorityEventSource(
            layer="L2",
            system="siming.observatory",
            actor_id=str(payload.get("target_actor_id", "") or "") or None,
        ),
        routing=AuthorityEventRouting(
            audience_mode="targeted",
            routing_mode="event_type",
            target_ids=[],
        ),
        priority="p2",
        ttl=5000,
        durability="replayable",
        causation_id=str(payload.get("causation_id", "") or event_id),
        correlation_id=str(payload.get("correlation_id", "") or event_id),
        payload=dict(payload),
    )
