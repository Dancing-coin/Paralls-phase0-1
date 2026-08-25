import asyncio
import os
from collections.abc import Callable
from secrets import compare_digest
from dataclasses import dataclass
from queue import Empty, Queue
from pathlib import Path
from threading import RLock
from time import time
from uuid import uuid4


from fastapi import FastAPI, Header, HTTPException, Request, WebSocket
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, ConfigDict, ValidationError
from starlette.websockets import WebSocketDisconnect

from app.config import Settings, settings
from app.debug_narration import (
    build_debug_event,
    summarize_backend_route,
    summarize_character_input_from_candidate,
    summarize_character_input_from_character_perceived,
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
from app.transport_projection import is_known_stream_mode, normalize_stream_mode, project_outbound_messages
from app.models.authority_event import AuthorityEvent, AuthorityEventRouting, AuthorityEventSource
from app.models.ai_output import DialogueResponse
from app.models.character_perceived import CharacterPerceivedEvent
from app.models.environment_request import EnvironmentRequest
from app.models.character_agent_runtime import CharacterGoalCommand
from app.models.character_agent_runtime import CharacterSuggestionPacket
from app.models.player_input import DialogueSubmit, FocusTargetChange, InteractIntent, MoveIntent, PickupIntent, RetrieveIntent, StowIntent
from app.models.raw_fact import RawFactEvent
from app.models.runtime_state import ConversationCandidateEvent
from app.models.self_body_perceived import SelfBodyPerceivedEvent
from app.models.siming_resource_capability import StagingAck
from app.models.transport import TransportBarrier
from app.models.visual_fact import VisualFactEvent
from app.models.world_result import WorldResultBase
from app.gameplay.dispatcher import GameplayOutboxDispatcher
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.godot_mirror_delivery import (
    GameplayGodotProjectionRepository,
    GameplayGodotProjectionPublisher,
    GameplayMirrorAfterCommitDelivery,
    GameplayMirrorConnectionRegistry,
    GameplayMirrorOutboundQueue,
    GameplayMirrorDeliveryError,
    GameplayMirrorOutboxRefreshConsumer,
    GameplayMirrorSubscriptionRegistry,
)
from app.gameplay.phase3_mirror_source import (
    Phase3MirrorActorConfiguration,
    install_phase3_mirror_sources,
)
from app.gameplay.adventure_basic_mirror_runtime import (
    AdventureBasicMirrorRuntime,
    AdventureBasicMirrorRuntimeError,
)
from app.gameplay.inventory_runtime import ContainerSpec, InventoryAuthorityService, InventoryDefinitionRegistry, ItemDefinition
from app.services.candidate_percept_service import compile_candidate_percepts
from app.services.character_service import CharacterService
from app.services.character_perceived_input_service import CharacterPerceivedInputService
from app.services.character_agent_runtime import CharacterAgentRuntime
from app.character_agent.storage.graph_memory_store import CharacterGraphMemoryStore
from app.character_agent.storage.memory_store import CharacterAgentMemoryStore
from app.character_agent.storage.memory_store_router import CharacterMemoryStoreRouter
from app.models.siming_heavenly_graph import HeavenlyGraphScope
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter
from app.services.behavior_turn_recorder import BehaviorTurnRecorder
from app.services.authority_graph_projector import HeavenlyAuthorityEventProjector
from app.character_agent.storage.graph_continuity_store import CharacterGraphContinuityStore
from app.services.character_runtime_state_service import CharacterRuntimeStateService
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.conversation_relation_service import ConversationRelationService
from app.services.esm_service import ESMService
from app.services.embodied_controller_auth_service import EmbodiedControllerAuthService, EmbodiedControllerEnrollment
from app.services.embodied_execution_ingress import EmbodiedExecutionIngress, EmbodiedRealizationRouteGate
from app.services.embodied_carry_place_authority_service import EmbodiedCarryPlaceAuthorityService
from app.services.embodied_custody_inventory_authority_service import EmbodiedCustodyInventoryAuthorityService
from app.services.default_scene_archive_door_embodied_service import DefaultSceneArchiveDoorEmbodiedService
from app.services.default_scene_pickup_policy import DefaultScenePickupPolicyService
from app.services.embodied_evidence_ledger import EmbodiedEvidenceLedger
from app.services.embodied_handoff_authority_service import EmbodiedHandoffAuthorityService
from app.services.embodied_interaction_session_service import EmbodiedInteractionSessionService
from app.services.embodied_harness_task import EmbodiedHarnessTaskCoordinator
from app.services.harness_execution_trace import HarnessExecutionTraceService
from app.services.harness_capability_store import HarnessCapabilityStore
from app.services.event_trace_service import EventTraceService
from app.services.fact_handlers.visual_fact_handler import (
    VisualFactHandlerContext,
    handle_visual_fact_event,
)
from app.services.fact_router import build_raw_fact_authority_ack, route_raw_fact_event
from app.services.focus_state_service import FocusStateService
from app.services.frontend_authority_event_projection import (
    FRONTEND_AUTHORITY_EVENT_TYPES,
    FrontendAuthorityEventProjector,
)
from app.services.interaction_orchestration_service import InteractionOrchestrationService, StructuredInteractionRequest
from app.services.per_character_percept_filter import filter_candidate_for_actor
from app.services.phase0_authority_event_adapter import Phase0AuthorityEventAdapter
from app.services.session_input_router import SessionInputRouter
from app.services.gameplay_mirror_session_access_service import (
    GameplayMirrorActorRequest,
    GameplayMirrorSessionAccessError,
    GameplayMirrorSessionAccessService,
    GameplayMirrorSubscriptionRequest,
)
from app.services.websocket_session_auth_service import (
    WebSocketConnectionContext,
    WebSocketSessionAuthService,
    WebSocketSessionEnrollment,
)
from app.services.trusted_local_gameplay_mirror_launcher import (
    TrustedLocalGameplayMirrorEnrollmentIssuer,
    TrustedLocalGameplayMirrorLaunchProfile,
)
from app.services.trusted_local_embodied_controller_launcher import (
    TrustedLocalEmbodiedControllerEnrollmentIssuer,
    TrustedLocalEmbodiedControllerLaunchProfile,
)
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
from app.services.siming_actor_memory_gateway import ActorMemoryReadGateway
from app.services.siming_adaptive_bridge import SimingAdaptiveBridge
from app.services.siming_context_compiler import SimingContextCompiler
from app.services.siming_heavenly_memory import SimingHeavenlyMemoryService
from app.services.siming_heavenly_runtime_support import SimingHeavenlyRuntimeSupport
from app.services.siming_resource_capability_registry import ResourceCapabilityRegistry
from app.services.siming_story_graph_runtime import SimingStoryGraphRuntime
from app.services.siming_story_node_staging import SimingStoryNodeStaging
from app.services.siming_story_obligation_runtime import SimingStoryObligationRuntime
from app.services.siming_debug_projection import SimingDebugProjection
from app.services.siming_runtime import SimingRuntime
from app.services.character_agent_debug_projection import CharacterAgentDebugProjection
from app.services.script_beat_projection import ScriptBeatProjection
from app.services.world_outcome_debug_projection import WorldOutcomeDebugProjection
from app.ws_protocol import Envelope, GameplayMirrorCapabilityOffer, GameplayMirrorCapabilityProfile, GameplayMirrorPredictionResolution, GameplayMirrorReceipt, WebSocketSessionRenewalRequest
from app.character_agent.execution.l4_adapter import CharacterAgentL4Adapter
from app.character_agent.execution.l4_executor import CharacterAgentL4Executor

app = FastAPI(title="Paralls Phase0 Backend")
BACKEND_BUILD = "paralls-phase0-backend-worktree-2026-06-02"
WORKTREE_ROOT = str(Path(__file__).resolve().parents[2])
STATIC_DIR = Path(__file__).resolve().parent / "static"
_pending_siming_character_dispatch_messages: dict[str, list[dict[str, object]]] = {}
_raw_fact_followup_lock = RLock()
_PLAYER_SHELL_ACTOR_IDS = {"char_c"}
_SPEECH_REQUEST_TYPES = {"speak_public", "speak_private", "share_info", "withhold"}
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
websocket_transport_closers: dict[str, Callable[[str], None]] = {}


class TrustedLocalGameplayMirrorEnrollmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    launch_profile_ref: str


class TrustedLocalEmbodiedControllerEnrollmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    launch_profile_ref: str


class TrustedLocalGameplayMirrorLiveProbeCommitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TrustedLocalGameplayMirrorLiveProbeControlledCloseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_ref: str


def actor_private_scope(actor_id: str) -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:demo",
        session_id="session:demo",
        story_branch_id="branch:main",
        graph_namespace="actor_private",
        owner_actor_id=actor_id,
    )


def siming_scope_for_event(event: AuthorityEvent) -> HeavenlyGraphScope:
    payload = event.payload if isinstance(event.payload, dict) else {}
    return HeavenlyGraphScope(
        world_id=str(payload.get("world_id", "world:demo") or "world:demo"),
        session_id=str(payload.get("session_id", "session:demo") or "session:demo"),
        story_branch_id=str(payload.get("story_branch_id", "branch:main") or "branch:main"),
    )


class FrontendSimingCharacterDispatchAdapter(SimingCharacterDispatchAdapter):
    def dispatch(self, event: AuthorityEvent) -> SimingCharacterDispatchResult:
        result = super().dispatch(event)
        _queue_siming_character_dispatch_messages(event.event_id, result)
        return result


@dataclass
class RuntimeState:
    heavenly_graph: SQLiteHeavenlyGraphAdapter
    character_graph_memory: CharacterGraphMemoryStore
    character_agent_runtime: CharacterAgentRuntime
    siming_runtime: SimingRuntime

    def close(self) -> None:
        self.heavenly_graph.close()


def build_runtime_state(runtime_settings: Settings) -> RuntimeState:
    graph_path = Path(runtime_settings.heavenly_graph_path)
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    heavenly_graph = SQLiteHeavenlyGraphAdapter(graph_path)
    character_agent_storage_root = (
        None
        if graph_path.name == ":memory:"
        else graph_path.parent / f"{graph_path.name}.character-agent"
    )
    continuity_store = CharacterGraphContinuityStore(
        heavenly_graph,
        scope_resolver=actor_private_scope,
        require_complete_snapshot=True,
    )
    graph_memory = CharacterGraphMemoryStore(
        heavenly_graph,
        scope_resolver=actor_private_scope,
        continuity_reader=continuity_store.read_snapshot,
    )
    memory_router = CharacterMemoryStoreRouter(
        light_store=CharacterAgentMemoryStore(),
        graph_store=graph_memory,
        heavy_actor_ids=frozenset(runtime_settings.character_graph_memory_heavy_actor_ids),
    )
    character_agent_runtime = CharacterAgentRuntime(
        storage_root=character_agent_storage_root,
        memory_store=memory_router,
        continuity_store=continuity_store,
        behavior_turn_recorder=BehaviorTurnRecorder(heavenly_graph),
        behavior_turn_scope_resolver=actor_private_scope,
    )
    llm_provider = build_siming_llm_provider(runtime_settings)

    def actor_autonomy(proposal) -> bool:
        actor_id = proposal.target_actor_id
        if not character_agent_runtime.supports_actor(actor_id):
            return False
        supervision = character_agent_runtime.get_supervision_state_record(actor_id)
        if (
            supervision.current_level in {"medium", "strong"}
            and not supervision.active_constraints.allow_proactive_initiation
        ):
            return False
        return character_agent_runtime.is_command_allowed_for_mode(
            character_agent_runtime.get_control_mode(actor_id), "speak"
        )

    support = None
    if runtime_settings.siming_heavenly_mode != "off":
        memory = SimingHeavenlyMemoryService(heavenly_graph)
        story = SimingStoryGraphRuntime(heavenly_graph, memory)
        obligations = SimingStoryObligationRuntime(heavenly_graph, memory)
        resources = ResourceCapabilityRegistry()
        actor_memory = ActorMemoryReadGateway(character_agent_runtime)
        support = SimingHeavenlyRuntimeSupport(
            mode=runtime_settings.siming_heavenly_mode,
            memory=memory,
            compiler=SimingContextCompiler(heavenly_graph),
            actor_memory=actor_memory,
            story=story,
            obligations=obligations,
            resources=resources,
            staging=SimingStoryNodeStaging(story, memory, obligations),
            bridges=lambda context: SimingAdaptiveBridge(
                graph=heavenly_graph,
                compiled_context=context,
                story_runtime=story,
                obligations=obligations,
                resources=resources,
                actor_memory_gateway=actor_memory,
                actor_autonomy=actor_autonomy,
            ),
            llm_provider=llm_provider,
        )
    return RuntimeState(
        heavenly_graph=heavenly_graph,
        character_graph_memory=graph_memory,
        character_agent_runtime=character_agent_runtime,
        siming_runtime=SimingRuntime(
            llm_provider=llm_provider,
            heavenly_support=support,
            behavior_turn_recorder=BehaviorTurnRecorder(heavenly_graph),
            behavior_turn_scope_resolver=siming_scope_for_event,
        ),
    )


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
    global embodied_controller_auth_service
    global embodied_controller_trusted_local_enrollment_issuer
    global embodied_controller_launcher_bootstrap_secret
    global websocket_session_auth_service
    global gameplay_mirror_trusted_local_enrollment_issuer
    global gameplay_mirror_launcher_bootstrap_secret
    global gameplay_godot_projection_repository
    global gameplay_mirror_subscription_registry
    global gameplay_mirror_session_access_service
    global gameplay_mirror_connection_registry
    global gameplay_mirror_outbox_refresh_consumer
    global gameplay_godot_projection_publisher
    global embodied_execution_ingress
    global embodied_realization_route_gate
    global gameplay_event_store
    global gameplay_outbox_dispatcher
    global adventure_basic_mirror_runtime
    global embodied_evidence_ledger
    global embodied_interaction_session_service
    global embodied_harness_task_coordinator
    global harness_execution_trace
    global harness_capability_store
    global embodied_handoff_authority_service
    global embodied_carry_place_authority_service
    global default_scene_pickup_policy_service
    global inventory_definition_registry
    global inventory_authority_service
    global embodied_custody_inventory_authority_service
    global default_scene_archive_door_embodied_service
    global heavenly_graph
    global _pending_siming_character_dispatch_messages
    global websocket_transport_closers

    previous_graph = globals().get("heavenly_graph")
    if isinstance(previous_graph, SQLiteHeavenlyGraphAdapter):
        previous_graph.close()
    previous_trace = globals().get("harness_execution_trace")
    if isinstance(previous_trace, HarnessExecutionTraceService):
        previous_trace.close()
    previous_capabilities = globals().get("harness_capability_store")
    if isinstance(previous_capabilities, HarnessCapabilityStore):
        previous_capabilities.close()
    runtime_state = build_runtime_state(settings)
    heavenly_graph = runtime_state.heavenly_graph
    runtime = SessionInputRouter()
    websocket_transport_closers = {}
    character_agent_runtime = CharacterAgentRuntime()
    character_agent_runtime = runtime_state.character_agent_runtime

    def dialogue_context_provider(actor_id: str) -> dict[str, object]:
        if not character_agent_runtime.supports_actor(actor_id):
            return {}
        snapshot = character_agent_runtime.get_private_snapshot(actor_id)
        return {
            "profile": character_agent_runtime._profile_payload(actor_id),
            "effective_profile": character_agent_runtime._effective_profile_payload(actor_id),
            "snapshot": snapshot.model_dump() if snapshot is not None else {},
            "memory": character_agent_runtime.get_memory_record_bundle(actor_id).model_dump(),
            "need_tension_state": character_agent_runtime.get_need_tension_state(actor_id),
        }

    character_service = CharacterService(dialogue_context_provider=dialogue_context_provider)
    if "character_perceived_input_service" not in globals():
        character_perceived_input_service = CharacterPerceivedInputService()
    else:
        character_perceived_input_service.clear()
    esm_service = ESMService()
    harness_ledger_parent = (
        None
        if Path(settings.heavenly_graph_path).name == ":memory:"
        else Path(settings.heavenly_graph_path).resolve().parent
    )
    harness_ledger_stem = Path(settings.heavenly_graph_path).resolve().stem
    harness_execution_trace = HarnessExecutionTraceService(
        ledger_path=(harness_ledger_parent / f"{harness_ledger_stem}.harness-task-ledger.sqlite3") if harness_ledger_parent else None
    )
    interaction_orchestration_service = InteractionOrchestrationService(
        esm_service=esm_service,
        harness_trace=harness_execution_trace,
    )
    embodied_controller_auth_service = EmbodiedControllerAuthService()
    embodied_evidence_ledger = EmbodiedEvidenceLedger()
    default_scene_archive_door_embodied_service = DefaultSceneArchiveDoorEmbodiedService(
        esm_service=esm_service,
        auth_service=embodied_controller_auth_service,
        evidence_ledger=embodied_evidence_ledger,
    )
    embodied_controller_launcher_bootstrap_secret = settings.embodied_controller_launcher_bootstrap_secret
    embodied_controller_trusted_local_enrollment_issuer = None
    if embodied_controller_launcher_bootstrap_secret and settings.embodied_controller_trusted_local_launch_profiles:
        embodied_controller_trusted_local_enrollment_issuer = TrustedLocalEmbodiedControllerEnrollmentIssuer(
            auth_service=embodied_controller_auth_service,
            launch_profiles=tuple(
                TrustedLocalEmbodiedControllerLaunchProfile(
                    profile_ref=profile.profile_ref,
                    actor_id=profile.actor_id,
                    controller_instance_id=profile.controller_instance_id,
                    credential_ttl_seconds=profile.credential_ttl_seconds,
                )
                for profile in settings.embodied_controller_trusted_local_launch_profiles
            ),
        )
    websocket_session_auth_service = WebSocketSessionAuthService()
    gameplay_mirror_launcher_bootstrap_secret = settings.gameplay_mirror_launcher_bootstrap_secret
    gameplay_mirror_trusted_local_enrollment_issuer = None
    if gameplay_mirror_launcher_bootstrap_secret and settings.gameplay_mirror_trusted_local_launch_profiles:
        gameplay_mirror_trusted_local_enrollment_issuer = TrustedLocalGameplayMirrorEnrollmentIssuer(
            auth_service=websocket_session_auth_service,
            launch_profiles=tuple(
                TrustedLocalGameplayMirrorLaunchProfile(
                    profile_ref=profile.profile_ref,
                    principal_ref=profile.principal_ref,
                    allowed_actor_refs=profile.allowed_actor_refs,
                    credential_ttl_seconds=profile.credential_ttl_seconds,
                )
                for profile in settings.gameplay_mirror_trusted_local_launch_profiles
            ),
        )
    gameplay_godot_projection_repository = GameplayGodotProjectionRepository()
    gameplay_mirror_subscription_registry = GameplayMirrorSubscriptionRegistry(
        projection_source=gameplay_godot_projection_repository.view_for,
    )
    gameplay_godot_projection_publisher = GameplayGodotProjectionPublisher(
        repository=gameplay_godot_projection_repository,
    )
    gameplay_mirror_session_access_service = GameplayMirrorSessionAccessService(
        registry=gameplay_mirror_subscription_registry,
        projection_publisher=gameplay_godot_projection_publisher,
    )
    gameplay_mirror_connection_registry = GameplayMirrorConnectionRegistry()
    gameplay_mirror_outbox_refresh_consumer = GameplayMirrorOutboxRefreshConsumer(
        delivery=GameplayMirrorAfterCommitDelivery(
            registry=gameplay_mirror_subscription_registry,
            deliver=gameplay_mirror_connection_registry.deliver,
            on_delivery_failure=lambda session_ref: _revoke_mirror_delivery_session(session_ref),
        )
    )
    embodied_execution_ingress = EmbodiedExecutionIngress(auth_service=embodied_controller_auth_service)
    embodied_realization_route_gate = EmbodiedRealizationRouteGate()
    l1_occupancy_service = SpatialOccupancyService()
    l1_projection_layer = FactProjectionLayer()
    l1_perception_bridge = L1RuntimePerceptionBridge()
    event_trace = EventTraceService()
    focus_state = FocusStateService()
    conversation_relation_service = ConversationRelationService()
    character_runtime_state_service = CharacterRuntimeStateService()
    authority_event_adapter = Phase0AuthorityEventAdapter()
    authority_event_bus = InMemoryAuthorityEventBus()
    gameplay_event_store = GameplayEventStore()
    install_phase3_mirror_sources(
        configurations=tuple(
            Phase3MirrorActorConfiguration.model_validate(item)
            for item in settings.gameplay_mirror_phase3_actor_configs
        ),
        store=gameplay_event_store,
        publisher=gameplay_godot_projection_publisher,
    )
    def refresh_then_fanout(transaction) -> None:
        gameplay_godot_projection_publisher.after_transaction_dispatched(transaction)
        gameplay_mirror_outbox_refresh_consumer.after_transaction_dispatched(transaction)

    adventure_basic_mirror_runtime = None
    if settings.adventure_basic_mirror_live_scenario:
        adventure_basic_mirror_runtime = AdventureBasicMirrorRuntime.create(
            scenario_id=settings.adventure_basic_mirror_live_scenario,
            publisher=gameplay_godot_projection_publisher,
            authority_bus=authority_event_bus,
            after_transaction_dispatched=refresh_then_fanout,
        )

    gameplay_outbox_dispatcher = GameplayOutboxDispatcher(
        store=gameplay_event_store,
        bus=authority_event_bus,
        after_transaction_dispatched=refresh_then_fanout,
    )
    embodied_interaction_session_service = EmbodiedInteractionSessionService(
        store=gameplay_event_store,
        dispatcher=gameplay_outbox_dispatcher,
        evidence_ledger=embodied_evidence_ledger,
    )
    harness_capability_store = (
        None
        if harness_ledger_parent is None
        else HarnessCapabilityStore(harness_ledger_parent / f"{harness_ledger_stem}.harness-capabilities.sqlite3")
    )
    embodied_harness_task_coordinator = EmbodiedHarnessTaskCoordinator(
        session_service=embodied_interaction_session_service,
        evidence_ledger=embodied_evidence_ledger,
        trace=harness_execution_trace,
        capability_store=harness_capability_store,
    )
    embodied_handoff_authority_service = EmbodiedHandoffAuthorityService(
        store=gameplay_event_store,
        dispatcher=gameplay_outbox_dispatcher,
        evidence_ledger=embodied_evidence_ledger,
    )
    embodied_handoff_authority_service.seed_asset_possession(
        asset_ref="item:letter_01",
        custody_holder_ref="character:siming",
        owner_ref="character:siming",
    )
    embodied_carry_place_authority_service = EmbodiedCarryPlaceAuthorityService(
        store=gameplay_event_store,
        dispatcher=gameplay_outbox_dispatcher,
        evidence_ledger=embodied_evidence_ledger,
    )
    embodied_carry_place_authority_service.seed_asset_possession(
        asset_ref="item:crate_01",
        custody_holder_ref="world:anchor:table_01",
        owner_ref="character:siming",
    )
    embodied_carry_place_authority_service.seed_drop_target(
        target_ref="world:anchor:floor_slot_01",
        occupied_by_ref="",
        scene_revision=11,
    )
    default_scene_pickup_policy_service = DefaultScenePickupPolicyService.demo_defaults()
    inventory_definition_registry = InventoryDefinitionRegistry()
    inventory_definition_registry.register_item(ItemDefinition("archive_token", "v1", 1, 1))
    inventory_authority_service = InventoryAuthorityService(
        store=gameplay_event_store,
        registry=inventory_definition_registry,
    )
    created_inventory_containers: set[tuple[str, str]] = set()
    for pickup_policy in default_scene_pickup_policy_service.policies():
        embodied_carry_place_authority_service.seed_asset_possession(
            asset_ref=pickup_policy.asset_ref,
            custody_holder_ref=pickup_policy.source_holder_ref,
            owner_ref="world:archive",
        )
        for actor_id in pickup_policy.allowed_actor_ids:
            actor_ref = f"character:{actor_id}"
            container_id = DefaultScenePickupPolicyService.inventory_destination_for(
                pickup_policy,
                actor_id,
            )
            if not container_id:
                raise ValueError("default_scene_inventory_destination_missing")
            if (actor_ref, container_id) not in created_inventory_containers:
                inventory_authority_service.create_container(
                    command_id=f"bootstrap:inventory:{actor_id}:{container_id}",
                    actor_ref=actor_ref,
                    spec=ContainerSpec(
                        container_id=container_id,
                        capacity_weight=12,
                        capacity_volume=12,
                        capacity_slots=8,
                    ),
                    idempotency_key=f"bootstrap:inventory:{actor_id}:{container_id}",
                    causation_id="runtime_reset",
                    correlation_id="runtime_reset",
                )
                created_inventory_containers.add((actor_ref, container_id))
            embodied_carry_place_authority_service.seed_drop_target(
                target_ref=f"character:{actor_id}:hand",
                occupied_by_ref="",
                scene_revision=11,
            )
    embodied_custody_inventory_authority_service = EmbodiedCustodyInventoryAuthorityService(
        store=gameplay_event_store,
        inventory_registry=inventory_definition_registry,
        custody_service=embodied_carry_place_authority_service,
    )
    embodied_carry_place_authority_service.seed_drop_target(
        target_ref="world:anchor:occupied_slot_01",
        occupied_by_ref="item:barrel_01",
        scene_revision=11,
    )
    if "siming_audit_writer" not in globals():
        siming_audit_writer = SimingAuditWriter()
    else:
        siming_audit_writer.reset()
    _pending_siming_character_dispatch_messages = {}
    siming_event_pipeline = SimingEventPipeline(
        bus=authority_event_bus,
        consumer=SimingEventConsumer(),
        runtime=runtime_state.siming_runtime,
        producer=SimingEventProducer(authority_event_bus),
        audit_writer=siming_audit_writer,
        character_dispatch_adapter=FrontendSimingCharacterDispatchAdapter(runtime=character_agent_runtime),
    )
    for event_type in SimingEventConsumer.ALLOWED_EVENT_TYPES:
        authority_event_bus.subscribe(event_type, siming_event_pipeline.handle_event)
    authority_event_bus.subscribe("siming.staging_request", _ack_siming_staging_request)
    frontend_authority_event_projector = FrontendAuthorityEventProjector()
    authority_graph_projector = HeavenlyAuthorityEventProjector(
        heavenly_graph,
        scope_resolver=lambda event: HeavenlyGraphScope(
            world_id=event.payload.get("world_id", "world:demo") if isinstance(event.payload.get("world_id", "world:demo"), str) else "world:demo",
            session_id=event.payload.get("session_id", "session:demo") if isinstance(event.payload.get("session_id", "session:demo"), str) else "session:demo",
            story_branch_id=event.payload.get("story_branch_id", "branch:main") if isinstance(event.payload.get("story_branch_id", "branch:main"), str) else "branch:main",
        ),
    )
    authority_event_bus.subscribe("*", authority_graph_projector.project)
    character_agent_l4_executor = CharacterAgentL4Executor()
    character_agent_l4_adapter = CharacterAgentL4Adapter(executor=character_agent_l4_executor)
    character_agent_debug_projection = CharacterAgentDebugProjection()
    siming_debug_projection = SimingDebugProjection()
    world_outcome_debug_projection = WorldOutcomeDebugProjection()
    script_beat_projection = ScriptBeatProjection()
    for event_type in FRONTEND_AUTHORITY_EVENT_TYPES:
        authority_event_bus.subscribe(event_type, frontend_authority_event_projector.handle_event)
    debug_stream.clear()


def _ack_siming_staging_request(event: AuthorityEvent) -> None:
    payload = event.payload
    target_actor_id = str(payload.get("target_actor_id", "") or "")
    character_accepted = character_agent_runtime.supports_actor(target_actor_id)
    character_reason = "" if character_accepted else "unsupported_actor"
    if character_accepted:
        supervision = character_agent_runtime.get_supervision_state_record(
            target_actor_id
        )
        character_accepted = (
            (
                supervision.current_level == "weak"
                or supervision.active_constraints.allow_proactive_initiation
            )
            and character_agent_runtime.is_command_allowed_for_mode(
                character_agent_runtime.get_control_mode(target_actor_id), "speak"
            )
        )
        if not character_accepted:
            character_reason = "actor_control_mode_disallows_staging"
    _publish_runtime_staging_ack(
        event,
        source="character",
        accepted=character_accepted,
        reason=character_reason,
        producer_ts=event.producer_ts + 1,
    )

    esm_accepted = all(
        isinstance(payload.get(key), str) and bool(payload[key])
        for key in ("node_id", "obligation_id", "realization_signature")
    )
    _publish_runtime_staging_ack(
        event,
        source="esm",
        accepted=esm_accepted,
        reason="" if esm_accepted else "invalid_staging_contract",
        producer_ts=event.producer_ts + 2,
    )


def close_runtime_resources() -> None:
    """Close process-owned persistent runtime resources without rebuilding state."""
    previous_graph = globals().get("heavenly_graph")
    if isinstance(previous_graph, SQLiteHeavenlyGraphAdapter):
        previous_graph.close()
    previous_trace = globals().get("harness_execution_trace")
    if isinstance(previous_trace, HarnessExecutionTraceService):
        previous_trace.close()
    previous_capabilities = globals().get("harness_capability_store")
    if isinstance(previous_capabilities, HarnessCapabilityStore):
        previous_capabilities.close()


def _publish_runtime_staging_ack(
    event: AuthorityEvent,
    *,
    source: str,
    accepted: bool,
    reason: str,
    producer_ts: int,
) -> None:
    if any(
        ack.correlation_id == event.correlation_id
        and ack.payload.get("source") == source
        for ack in authority_event_bus.list_events(event_type="siming_staging_ack")
    ):
        return
    ack = StagingAck(
        source=source,
        correlation_id=event.correlation_id,
        accepted=accepted,
        reason=reason,
    )
    authority_event_bus.publish(
        authority_event_adapter.staging_ack_event(
            ack,
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            producer_ts=producer_ts,
        )
    )


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


@app.post("/internal/trusted-local-gameplay-mirror-enrollment")
def issue_trusted_local_gameplay_mirror_enrollment(
    payload: TrustedLocalGameplayMirrorEnrollmentRequest,
    request: Request,
    launcher_secret: str | None = Header(default=None, alias="X-Gameplay-Mirror-Launcher-Secret"),
) -> dict[str, object]:
    peer_host = request.client.host if request.client is not None else ""
    if peer_host not in _LOOPBACK_HOSTS:
        raise HTTPException(
            status_code=403,
            detail={"error_code": "trusted_local_gameplay_mirror_launcher_requires_loopback"},
        )
    if (
        gameplay_mirror_trusted_local_enrollment_issuer is None
        or not gameplay_mirror_launcher_bootstrap_secret
        or launcher_secret is None
        or not compare_digest(launcher_secret, gameplay_mirror_launcher_bootstrap_secret)
    ):
        raise HTTPException(
            status_code=403,
            detail={"error_code": "trusted_local_gameplay_mirror_launcher_unauthorized"},
        )
    try:
        enrollment = gameplay_mirror_trusted_local_enrollment_issuer.issue_for_launch_profile(
            payload.launch_profile_ref,
            now=int(time()),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error_code": str(exc)}) from exc
    return enrollment.model_dump(exclude_none=True)


@app.post("/internal/trusted-local-embodied-controller-enrollment")
def issue_trusted_local_embodied_controller_enrollment(
    payload: TrustedLocalEmbodiedControllerEnrollmentRequest,
    request: Request,
    launcher_secret: str | None = Header(default=None, alias="X-Embodied-Controller-Launcher-Secret"),
) -> dict[str, object]:
    peer_host = request.client.host if request.client is not None else ""
    if peer_host not in _LOOPBACK_HOSTS:
        raise HTTPException(
            status_code=403,
            detail={"error_code": "trusted_local_embodied_controller_launcher_requires_loopback"},
        )
    if (
        embodied_controller_trusted_local_enrollment_issuer is None
        or not embodied_controller_launcher_bootstrap_secret
        or launcher_secret is None
        or not compare_digest(launcher_secret, embodied_controller_launcher_bootstrap_secret)
    ):
        raise HTTPException(
            status_code=403,
            detail={"error_code": "trusted_local_embodied_controller_launcher_unauthorized"},
        )
    try:
        enrollment = embodied_controller_trusted_local_enrollment_issuer.issue_for_launch_profile(
            payload.launch_profile_ref,
            now=int(time()),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error_code": str(exc)}) from exc
    return enrollment.model_dump(exclude_none=True)


def _require_trusted_local_gameplay_mirror_live_probe(
    *,
    request: Request,
    launcher_secret: str | None,
) -> None:
    peer_host = request.client.host if request.client is not None else ""
    if peer_host not in _LOOPBACK_HOSTS:
        raise HTTPException(status_code=403, detail={"error_code": "trusted_local_gameplay_mirror_launcher_requires_loopback"})
    if (
        not gameplay_mirror_launcher_bootstrap_secret
        or launcher_secret is None
        or not compare_digest(launcher_secret, gameplay_mirror_launcher_bootstrap_secret)
    ):
        raise HTTPException(status_code=403, detail={"error_code": "trusted_local_gameplay_mirror_launcher_unauthorized"})


@app.post("/internal/trusted-local-gameplay-mirror-live-probe-commit")
def commit_trusted_local_gameplay_mirror_live_probe(
    request: Request,
    launcher_secret: str | None = Header(default=None, alias="X-Gameplay-Mirror-Launcher-Secret"),
    payload: TrustedLocalGameplayMirrorLiveProbeCommitRequest | None = None,
) -> dict[str, object]:
    """Verifier-only initial committed update selected entirely from server configuration."""

    del payload
    _require_trusted_local_gameplay_mirror_live_probe(request=request, launcher_secret=launcher_secret)
    return _commit_configured_trusted_local_gameplay_mirror_live_probe(configuration_index=0)


@app.post("/internal/trusted-local-gameplay-mirror-live-probe-reconnect-commit")
def commit_trusted_local_gameplay_mirror_live_probe_reconnect(
    request: Request,
    launcher_secret: str | None = Header(default=None, alias="X-Gameplay-Mirror-Launcher-Secret"),
    payload: TrustedLocalGameplayMirrorLiveProbeCommitRequest | None = None,
) -> dict[str, object]:
    """Verifier-only replacement-scope update; actor selection remains server-owned."""

    del payload
    _require_trusted_local_gameplay_mirror_live_probe(request=request, launcher_secret=launcher_secret)
    return _commit_configured_trusted_local_gameplay_mirror_live_probe(configuration_index=1)


@app.post("/internal/trusted-local-gameplay-mirror-live-probe-prediction-confirm")
def confirm_trusted_local_gameplay_mirror_live_prediction(
    request: Request,
    launcher_secret: str | None = Header(default=None, alias="X-Gameplay-Mirror-Launcher-Secret"),
    payload: TrustedLocalGameplayMirrorLiveProbeCommitRequest | None = None,
) -> dict[str, object]:
    """Verifier-only authority commit followed by its server-issued prediction confirmation."""

    del payload
    _require_trusted_local_gameplay_mirror_live_probe(request=request, launcher_secret=launcher_secret)
    committed = _commit_configured_trusted_local_gameplay_mirror_live_probe(
        configuration_index=0,
        resource_delta=-1,
    )
    delivered = _deliver_trusted_local_gameplay_mirror_prediction_resolutions(
        actor_ref=str(committed["actor_ref"]),
        resolutions=(
            GameplayMirrorPredictionResolution(
                prediction_id="prediction:live:stamina-confirm",
                command_id="command:live:stamina-confirm",
                resolution="confirmed",
                transaction_id=str(committed["transaction_id"]),
            ),
        ),
    )
    view = gameplay_godot_projection_repository.view_for(str(committed["actor_ref"]))
    return {
        **committed,
        "prediction_resolution_deliveries": delivered,
        "facade_revision": view.source_facade_revision,
        "source_revision_vector": dict(view.source_revision_vector),
    }


@app.post("/internal/trusted-local-gameplay-mirror-live-probe-prediction-reject")
def reject_trusted_local_gameplay_mirror_live_prediction(
    request: Request,
    launcher_secret: str | None = Header(default=None, alias="X-Gameplay-Mirror-Launcher-Secret"),
    payload: TrustedLocalGameplayMirrorLiveProbeCommitRequest | None = None,
) -> dict[str, object]:
    """Verifier-only stale-revision rejection with no event-batch write."""

    del payload
    _require_trusted_local_gameplay_mirror_live_probe(request=request, launcher_secret=launcher_secret)
    if not settings.gameplay_mirror_phase3_actor_configs:
        raise HTTPException(status_code=409, detail={"error_code": "trusted_local_gameplay_mirror_live_probe_source_unavailable"})
    configuration = Phase3MirrorActorConfiguration.model_validate(settings.gameplay_mirror_phase3_actor_configs[0])
    actor_ref = configuration.actor_ref
    resource_stream = f"gameplay:resources:{actor_ref}"
    head = gameplay_event_store.get_stream_head(resource_stream)
    if head < 1:
        raise HTTPException(status_code=409, detail={"error_code": "trusted_local_gameplay_mirror_prediction_base_required"})
    transaction_id = f"tx:trusted-local-mirror-live:prediction-reject:{uuid4()}"
    command_id = f"cmd:trusted-local-mirror-live:prediction-reject:{uuid4()}"
    event_count_before = len(gameplay_event_store.read_events())
    rejected = gameplay_event_store.append_batch(
        {
            "transaction_id": transaction_id,
            "command_id": command_id,
            "expected_stream_revisions": {resource_stream: head - 1},
            "pinned_revisions": {},
            "events": [
                {
                    "event_id": f"evt:trusted-local-mirror-live:prediction-reject:{uuid4()}",
                    "event_type": "gameplay.resource.adjusted",
                    "schema_version": 1,
                    "stream_id": resource_stream,
                    "stream_revision": 0,
                    "global_sequence": 0,
                    "transaction_id": transaction_id,
                    "command_id": command_id,
                    "causation_id": command_id,
                    "correlation_id": transaction_id,
                    "visibility_policy": "authority_only",
                    "payload": {
                        "actor_ref": actor_ref,
                        "resource_id": "core.stamina",
                        "delta": -1,
                        "reason_ref": "trusted_local_live_prediction_reject",
                    },
                }
            ],
            "idempotency_record": {
                "principal_ref": "trusted_local_gameplay_mirror_live_probe",
                "idempotency_key": command_id,
                "payload_digest": f"sha256:{command_id}",
            },
            "outbox_entries": [],
            "result_digest": f"sha256:{transaction_id}",
            "projection_refresh_hints": [],
        }
    )
    if rejected.committed:
        raise HTTPException(status_code=500, detail={"error_code": "trusted_local_gameplay_mirror_prediction_rejection_committed"})
    if len(gameplay_event_store.read_events()) != event_count_before:
        raise HTTPException(status_code=500, detail={"error_code": "trusted_local_gameplay_mirror_prediction_rejection_mutated"})
    error_code = rejected.failure.error_code if rejected.failure is not None else "stream_revision_conflict"
    delivered = _deliver_trusted_local_gameplay_mirror_prediction_resolutions(
        actor_ref=actor_ref,
        resolutions=(
            GameplayMirrorPredictionResolution(
                prediction_id="prediction:live:stamina-reject",
                command_id="command:live:stamina-reject",
                resolution="rejected",
                error_code=error_code,
            ),
        ),
    )
    view = gameplay_godot_projection_repository.view_for(actor_ref)
    return {
        "actor_ref": actor_ref,
        "transaction_id": transaction_id,
        "error_code": error_code,
        "mutation_count": 0,
        "prediction_resolution_deliveries": delivered,
        "facade_revision": view.source_facade_revision,
        "source_revision_vector": dict(view.source_revision_vector),
    }


@app.post("/internal/trusted-local-gameplay-mirror-live-probe-controlled-close")
def close_trusted_local_gameplay_mirror_live_probe_transport(
    payload: TrustedLocalGameplayMirrorLiveProbeControlledCloseRequest,
    request: Request,
    launcher_secret: str | None = Header(default=None, alias="X-Gameplay-Mirror-Launcher-Secret"),
) -> dict[str, object]:
    """Verifier-only transport revocation that cannot mutate Gameplay authority state."""

    _require_trusted_local_gameplay_mirror_live_probe(request=request, launcher_secret=launcher_secret)
    connection_ref = gameplay_mirror_connection_registry.connection_ref_for(session_ref=payload.session_ref)
    if connection_ref is None:
        raise HTTPException(status_code=404, detail={"error_code": "mirror_live_probe_transport_unknown"})
    if not revoke_websocket_session_for_transport(
        session_ref=payload.session_ref,
        connection_ref=connection_ref,
        reason_code="mirror_delivery_unrecoverable",
        now=int(time()),
    ):
        raise HTTPException(status_code=409, detail={"error_code": "mirror_live_probe_transport_revocation_failed"})
    return {"session_ref": payload.session_ref, "reason_code": "mirror_delivery_unrecoverable"}


def _deliver_trusted_local_gameplay_mirror_prediction_resolutions(
    *,
    actor_ref: str,
    resolutions: tuple[GameplayMirrorPredictionResolution, ...],
) -> int:
    view = gameplay_godot_projection_repository.view_for(actor_ref)
    delivered = 0
    for session_ref in gameplay_mirror_subscription_registry.subscribed_session_refs(actor_ref=actor_ref):
        gameplay_mirror_connection_registry.deliver_prediction_resolutions(
            session_ref=session_ref,
            actor_ref=actor_ref,
            facade_revision=view.source_facade_revision,
            resolutions=resolutions,
        )
        delivered += 1
    if delivered == 0:
        raise HTTPException(status_code=409, detail={"error_code": "trusted_local_gameplay_mirror_prediction_subscriber_required"})
    return delivered


def _commit_configured_trusted_local_gameplay_mirror_live_probe(
    *,
    configuration_index: int,
    resource_delta: int = 0,
) -> dict[str, object]:
    if not settings.gameplay_mirror_phase3_actor_configs:
        raise HTTPException(status_code=409, detail={"error_code": "trusted_local_gameplay_mirror_live_probe_source_unavailable"})
    if configuration_index >= len(settings.gameplay_mirror_phase3_actor_configs):
        raise HTTPException(status_code=409, detail={"error_code": "trusted_local_gameplay_mirror_live_probe_source_unavailable"})
    configuration = Phase3MirrorActorConfiguration.model_validate(settings.gameplay_mirror_phase3_actor_configs[configuration_index])
    actor_ref = configuration.actor_ref
    transaction_id = f"tx:trusted-local-mirror-live:{uuid4()}"
    command_id = f"cmd:trusted-local-mirror-live:{uuid4()}"
    lifecycle_stream = f"gameplay:state_groups:{actor_ref}"
    resource_stream = f"gameplay:resources:{actor_ref}"
    event_prefix = f"evt:trusted-local-mirror-live:{uuid4()}"
    events = [
        {
            "event_id": f"{event_prefix}:materialize",
            "event_type": "gameplay.state_group.materialized",
            "schema_version": 1,
            "stream_id": lifecycle_stream,
            "stream_revision": 0,
            "global_sequence": 0,
            "transaction_id": transaction_id,
            "command_id": command_id,
            "causation_id": command_id,
            "correlation_id": transaction_id,
            "visibility_policy": "authority_only",
            "payload": {"actor_ref": actor_ref, "group_id": "core.resources", "definition_version": "1", "source_patch_revision": configuration.active_patch_set_revision},
        },
        {
            "event_id": f"{event_prefix}:enable",
            "event_type": "gameplay.state_group.enabled",
            "schema_version": 1,
            "stream_id": lifecycle_stream,
            "stream_revision": 0,
            "global_sequence": 0,
            "transaction_id": transaction_id,
            "command_id": command_id,
            "causation_id": command_id,
            "correlation_id": transaction_id,
            "visibility_policy": "authority_only",
            "payload": {"actor_ref": actor_ref, "group_id": "core.resources", "definition_version": "1", "source_patch_revision": configuration.active_patch_set_revision},
        },
        {
            "event_id": f"{event_prefix}:resource",
            "event_type": "gameplay.resource.materialized",
            "schema_version": 1,
            "stream_id": resource_stream,
            "stream_revision": 0,
            "global_sequence": 0,
            "transaction_id": transaction_id,
            "command_id": command_id,
            "causation_id": command_id,
            "correlation_id": transaction_id,
            "visibility_policy": "authority_only",
            "payload": {"actor_ref": actor_ref, "resource_id": "core.stamina", "minimum": 0, "maximum": 10, "current": 6},
        },
    ]
    if gameplay_event_store.get_stream_head(lifecycle_stream) > 0:
        # Later probe updates reuse the already committed lifecycle state.
        events = events[2:]
    if gameplay_event_store.get_stream_head(resource_stream) > 0:
        events[-1]["event_type"] = "gameplay.resource.adjusted"
        events[-1]["payload"] = {
            "actor_ref": actor_ref,
            "resource_id": "core.stamina",
            "delta": resource_delta,
            "reason_ref": "trusted_local_live_probe_refresh",
        }
    result = gameplay_event_store.append_batch(
        {
            "transaction_id": transaction_id,
            "command_id": command_id,
            "expected_stream_revisions": {lifecycle_stream: gameplay_event_store.get_stream_head(lifecycle_stream), resource_stream: gameplay_event_store.get_stream_head(resource_stream)},
            "pinned_revisions": {},
            "events": events,
            "idempotency_record": {"principal_ref": "trusted_local_gameplay_mirror_live_probe", "idempotency_key": command_id, "payload_digest": f"sha256:{command_id}"},
            "outbox_entries": [
                {
                    "outbox_id": f"outbox:{event_prefix}:resource",
                    "transaction_id": transaction_id,
                    "event_id": f"{event_prefix}:resource",
                    "global_sequence": 0,
                    "topic": "gameplay.committed",
                    "audience": "godot_room",
                    "payload_projection": {"room_id": "room_demo", "scene_id": "scene_demo", "zone_id": "zone_focus", "source": {"layer": "gameplay", "system": "trusted_local_live_probe"}, "routing": {"audience_mode": "room", "routing_mode": "event_type", "target_ids": ["godot_mirror"]}, "priority": "p1", "durability": "replayable", "payload": {"actor_ref": actor_ref}},
                    "delivery_state": "pending",
                    "attempt_count": 0,
                    "last_error": None,
                }
            ],
            "result_digest": f"sha256:{transaction_id}",
            "projection_refresh_hints": [{"projection_id": "godot_mirror", "stream_id": resource_stream, "reason": "trusted_local_live_probe", "actor_refs": [actor_ref]}],
        }
    )
    if not result.committed:
        raise HTTPException(status_code=409, detail={"error_code": result.failure.error_code if result.failure else "trusted_local_gameplay_mirror_live_probe_commit_failed"})
    gameplay_outbox_dispatcher.dispatch_pending()
    return {"actor_ref": actor_ref, "transaction_id": transaction_id, "mutation_count": len(events)}


@app.post("/internal/trusted-local-adventure-basic-live-probe-commit")
def commit_trusted_local_adventure_basic_live_probe(
    request: Request,
    launcher_secret: str | None = Header(default=None, alias="X-Gameplay-Mirror-Launcher-Secret"),
    payload: TrustedLocalGameplayMirrorLiveProbeCommitRequest | None = None,
) -> dict[str, object]:
    """Run one server-configured Adventure Basic authority path for live mirror proof."""

    del payload
    _require_trusted_local_gameplay_mirror_live_probe(request=request, launcher_secret=launcher_secret)
    if adventure_basic_mirror_runtime is None:
        raise HTTPException(status_code=409, detail={"error_code": "adventure_basic_live_probe_source_unavailable"})
    try:
        result = adventure_basic_mirror_runtime.execute_canonical_success()
    except AdventureBasicMirrorRuntimeError as exc:
        raise HTTPException(status_code=409, detail={"error_code": str(exc)}) from exc
    return {
        "scenario_id": result.scenario_id,
        "actor_ref": adventure_basic_mirror_runtime.actor_ref,
        "transaction_ids": list(result.transaction_ids),
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    raw_stream_mode = websocket.query_params.get("stream_mode")
    stream_mode = normalize_stream_mode(raw_stream_mode)
    if not is_known_stream_mode(raw_stream_mode):
        _publish_debug_event(
            build_debug_event(
                producer_ts=0,
                domain="backend",
                stage="unknown_stream_mode",
                summary="Unknown websocket stream mode; using full projection.",
                detail={"raw_stream_mode": raw_stream_mode},
            )
        )
    connection_context = WebSocketConnectionContext(
        remote_host=websocket.client.host if websocket.client is not None else "",
        observed_at=int(time()),
        connection_ref=f"ws_connection:{uuid4()}",
    )
    transport_close_requested = asyncio.Event()
    transport_close_revocation_received = asyncio.Event()
    transport_close_reason = ""
    connection_loop = asyncio.get_running_loop()

    def request_transport_close(reason_code: str) -> None:
        def request_on_connection_loop() -> None:
            nonlocal transport_close_reason
            if transport_close_requested.is_set():
                return
            transport_close_reason = reason_code
            transport_close_requested.set()

        connection_loop.call_soon_threadsafe(request_on_connection_loop)

    websocket_transport_closers[connection_context.connection_ref] = request_transport_close
    active_dialogue_streams: dict[str, tuple[asyncio.Event, asyncio.Task[None]]] = {}
    raw_fact_followup_tasks: set[asyncio.Task[None]] = set()
    send_lock = asyncio.Lock()
    mirror_delivery_queue = GameplayMirrorOutboundQueue(
        projection_capacity=settings.gameplay_mirror_projection_queue_capacity,
        control_capacity=settings.gameplay_mirror_control_queue_capacity,
        dirty_actor_limit=settings.gameplay_mirror_dirty_actor_limit,
    )
    drop_first_live_probe_delivery = settings.gameplay_mirror_live_probe_drop_first_delivery
    live_probe_delivery_delay_seconds = settings.gameplay_mirror_live_probe_delivery_delay_seconds

    async def send(message: dict[str, object]) -> None:
        async with send_lock:
            await websocket.send_json(message)

    async def send_batch(messages: list[dict[str, object]]) -> None:
        for message in project_outbound_messages(messages, stream_mode=stream_mode):
            await send(message)

    async def send_controlled_transport_close() -> None:
        await transport_close_requested.wait()
        try:
            await send(
                _as_envelope(
                    "websocket_session_revoked",
                    {
                        "reason_code": transport_close_reason,
                        "route": "gameplay_mirror_transport",
                    },
                )
            )
            try:
                await asyncio.wait_for(transport_close_revocation_received.wait(), timeout=1.0)
            except TimeoutError:
                pass
            await websocket.close(code=4403, reason=transport_close_reason)
        except RuntimeError:
            # The peer may have disconnected after server revocation. Either
            # way, the transport state was already removed synchronously.
            return

    async def send_mirror_deliveries() -> None:
        nonlocal drop_first_live_probe_delivery
        while True:
            try:
                payload = mirror_delivery_queue.pop_next()
            except Exception:
                await asyncio.sleep(0.01)
                continue
            if payload is None:
                await asyncio.sleep(0.01)
                continue
            if drop_first_live_probe_delivery and payload.get("message_type") == "gameplay_mirror_delivery":
                drop_first_live_probe_delivery = False
                continue
            await send(payload)
            if live_probe_delivery_delay_seconds:
                await asyncio.sleep(live_probe_delivery_delay_seconds)

    async def run_dialogue_stream(event: DialogueSubmit, request_id: str, cancelled: asyncio.Event) -> None:
        partial_chars = 0
        sequence = 0
        fallback_used = False
        try:
            await send(
                _as_envelope(
                    "dialogue_stream_start",
                    {
                        "request_id": request_id,
                        "actor_id": event.target_actor_id if event.player_id != "character_agent" else event.actor_id,
                        "target_actor_id": event.actor_id if event.player_id != "character_agent" else event.target_actor_id,
                    },
                )
            )
            direct_content = await asyncio.to_thread(_dialogue_direct_content, event)
            if direct_content:
                response = await asyncio.to_thread(_direct_dialogue_response, event, direct_content)
                if cancelled.is_set():
                    await send(_dialogue_stream_end(request_id, "cancelled", partial_chars, fallback_used))
                    return
                _record_completed_dialogue_response(response)
                event_trace.record(response.output_type)
                await send(_as_envelope("dialogue_response", response.model_dump()))
                await send(_dialogue_stream_end(request_id, "completed", len(response.content), fallback_used))
                await send_batch(_observatory_messages_from_outbound([]))
                return

            stream = character_service.stream_dialogue(event, cancelled=cancelled.is_set)
            while True:
                has_event, stream_event = await asyncio.to_thread(_next_dialogue_stream_event, stream)
                if not has_event:
                    raise ValueError("character dialogue stream ended without a completion event")
                if cancelled.is_set() or stream_event["event"] == "cancelled":
                    await send(_dialogue_stream_end(request_id, "cancelled", partial_chars, fallback_used))
                    return
                if stream_event["event"] == "delta":
                    delta = str(stream_event["delta"])
                    partial_chars += len(delta)
                    sequence += 1
                    await send(
                        _as_envelope(
                            "dialogue_stream_delta",
                            {
                                "request_id": request_id,
                                "sequence": sequence,
                                "delta": delta,
                                "accumulated_chars": partial_chars,
                            },
                        )
                    )
                    continue
                if stream_event["event"] != "completed":
                    raise ValueError("character dialogue stream emitted an unsupported event")
                response = stream_event["response"]
                if not isinstance(response, DialogueResponse):
                    raise ValueError("character dialogue stream completed without DialogueResponse")
                fallback_used = bool(stream_event.get("fallback_used", False))
                if cancelled.is_set():
                    await send(_dialogue_stream_end(request_id, "cancelled", partial_chars, fallback_used))
                    return
                audio = character_service.tts.synthesize(response.actor_id, response.content)
                response = response.model_copy(update={"audio": audio})
                _record_completed_dialogue_response(response)
                event_trace.record(response.output_type)
                await send(_as_envelope("dialogue_response", response.model_dump()))
                await send(_dialogue_stream_end(request_id, "completed", partial_chars, fallback_used))
                await send_batch(_observatory_messages_from_outbound([]))
                return
        except Exception as exc:
            if cancelled.is_set():
                await send(_dialogue_stream_end(request_id, "cancelled", partial_chars, fallback_used))
                return
            status = "timed_out" if isinstance(exc, TimeoutError) else "failed"
            await send(_dialogue_stream_end(request_id, status, partial_chars, fallback_used))
        finally:
            active_dialogue_streams.pop(request_id, None)

    async def send_raw_fact_followups(envelope: Envelope, authority_ack: dict[str, object]) -> None:
        try:
            outbound = await asyncio.to_thread(
                _handle_raw_fact_followup,
                envelope,
                connection_context=connection_context,
            )
            await send_batch(_drop_matching_authority_ack(outbound, authority_ack))
        except (ValidationError, ValueError, TypeError) as exc:
            await send(_as_error_ack(source_type=envelope.message_type, route="raw_fact_followup_failed", error=exc))
        except Exception as exc:
            _publish_debug_event(
                build_debug_event(
                    producer_ts=0,
                    domain="backend",
                    stage="raw_fact_followup_failed",
                    summary="raw fact follow-up failed after authority acknowledgement",
                    detail={"error_type": type(exc).__name__, "error": str(exc)},
                )
            )
            await send(_as_error_ack(source_type=envelope.message_type, route="raw_fact_followup_failed", error=exc))

    mirror_delivery_task = asyncio.create_task(send_mirror_deliveries())
    controlled_close_task = asyncio.create_task(send_controlled_transport_close())
    try:
        while True:
            try:
                raw = await websocket.receive_json()
                envelope = Envelope(**raw)
                if envelope.message_type == "dialogue_stream_cancel":
                    request_id = str(envelope.payload.get("request_id", "") or "")
                    active = active_dialogue_streams.get(request_id)
                    if active is None:
                        await send(
                            _as_envelope(
                                "ack",
                                {"accepted": False, "source_type": envelope.message_type, "route": "dialogue_stream_unknown"},
                            )
                        )
                    else:
                        active[0].set()
                        await send(
                            _as_envelope(
                                "ack",
                                {"accepted": True, "source_type": envelope.message_type, "route": "dialogue_stream_cancel"},
                            )
                        )
                    continue
                stream_event = _streamable_dialogue_submit(envelope)
                if stream_event is not None:
                    route = runtime.accept_player_input(stream_event)
                    if route["route"] == "character_service":
                        request_id = stream_event.request_id or f"dialogue:{uuid4()}"
                        stream_event.request_id = request_id
                        if request_id in active_dialogue_streams:
                            await send(
                                _as_envelope(
                                    "ack",
                                    {"accepted": False, "source_type": envelope.message_type, "route": "dialogue_stream_duplicate"},
                                )
                            )
                            continue
                        _publish_debug_event(
                            build_debug_event(
                                producer_ts=stream_event.producer_ts,
                                domain="character",
                                stage="character_input_received",
                                actor_id=stream_event.target_actor_id,
                                summary=summarize_character_input(stream_event.target_actor_id, "收到玩家对话输入"),
                                detail=stream_event.model_dump(),
                            )
                        )
                        event_trace.record(stream_event.intent_type)
                        await send(
                            _as_envelope(
                                "ack",
                                {"accepted": route["accepted"], "source_type": envelope.message_type, "route": route["route"]},
                            )
                        )
                        cancelled = asyncio.Event()
                        task = asyncio.create_task(run_dialogue_stream(stream_event, request_id, cancelled))
                        active_dialogue_streams[request_id] = (cancelled, task)
                        continue
                if envelope.message_type == "raw_fact_event":
                    authority_ack = _raw_fact_fast_authority_ack(envelope)
                    await send(authority_ack)
                    task = asyncio.create_task(send_raw_fact_followups(envelope, authority_ack))
                    raw_fact_followup_tasks.add(task)
                    task.add_done_callback(raw_fact_followup_tasks.discard)
                    continue
                if envelope.message_type == "websocket_session_revocation_received":
                    payload = envelope.payload if isinstance(envelope.payload, dict) else {}
                    if (
                        transport_close_requested.is_set()
                        and str(payload.get("reason_code", "")) == transport_close_reason
                        and str(payload.get("route", "")) == "gameplay_mirror_transport"
                    ):
                        transport_close_revocation_received.set()
                    continue
                outbound = _handle_websocket_envelope(envelope, connection_context)
                if _session_bound_by(outbound, envelope.message_type, connection_context):
                    gameplay_mirror_connection_registry.register(
                        session_ref=connection_context.binding.session_ref,
                        connection_ref=connection_context.connection_ref,
                        connection_epoch=connection_context.binding.connection_epoch,
                        deliver=mirror_delivery_queue.enqueue_projection,
                    )
            except (ValidationError, ValueError, TypeError) as exc:
                source_type = "unknown"
                if isinstance(raw, dict):
                    source_type = str(raw.get("message_type", "unknown"))
                outbound = [_as_error_ack(source_type=source_type, route="invalid_payload", error=exc)]
            await send_batch(outbound)
    except WebSocketDisconnect:
        return
    finally:
        if websocket_transport_closers.get(connection_context.connection_ref) == request_transport_close:
            websocket_transport_closers.pop(connection_context.connection_ref, None)
        if connection_context.binding is not None:
            _drop_mirror_transport_session(connection_context, connection_context.binding.session_ref)
            websocket_session_auth_service.disconnect_session(
                connection_context.binding.session_ref,
                now=int(time()),
            )
        mirror_delivery_task.cancel()
        controlled_close_task.cancel()
        mirror_delivery_queue.clear()
        tasks = [task for cancelled, task in active_dialogue_streams.values()]
        for cancelled, _task in active_dialogue_streams.values():
            cancelled.set()
        for task in tasks:
            task.cancel()
        for task in raw_fact_followup_tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if raw_fact_followup_tasks:
            await asyncio.gather(*raw_fact_followup_tasks, return_exceptions=True)
        await asyncio.gather(mirror_delivery_task, return_exceptions=True)
        await asyncio.gather(controlled_close_task, return_exceptions=True)


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


def _handle_raw_fact_followup(
    envelope: Envelope,
    *,
    connection_context: WebSocketConnectionContext,
) -> list[dict[str, object]]:
    with _raw_fact_followup_lock:
        result = _handle_envelope(envelope, connection_context=connection_context)
        return result


def _handle_websocket_envelope(
    envelope: Envelope,
    connection_context: WebSocketConnectionContext,
) -> list[dict[str, object]]:
    try:
        return _handle_envelope(envelope, connection_context=connection_context)
    except TypeError as exc:
        if "unexpected keyword argument 'connection_context'" not in str(exc):
            raise
        return _handle_envelope(envelope)


def _handle_envelope(
    envelope: Envelope,
    *,
    connection_context: WebSocketConnectionContext | None = None,
) -> list[dict[str, object]]:
    connection_context = connection_context or WebSocketConnectionContext.direct_handler_compatibility()
    if envelope.message_type == "transport_barrier":
        barrier = TransportBarrier(**envelope.payload)
        return [
            {
                "message_type": "ack",
                "payload": {
                    "accepted": True,
                    "source_type": "transport_barrier",
                    "route": "transport_barrier",
                    "request_id": barrier.request_id,
                    "producer_ts": barrier.producer_ts,
                },
            }
        ]
    if envelope.message_type == "siming_staging_ack":
        payload = envelope.payload
        required_text = ("room_id", "scene_id", "zone_id", "correlation_id")
        if any(not isinstance(payload.get(key), str) or not payload[key] for key in required_text):
            return _as_error_ack(
                source_type=envelope.message_type,
                route="siming_staging_ack",
                error=ValueError("missing_staging_ack_context"),
            )
        if not isinstance(payload.get("producer_ts"), int) or isinstance(payload.get("producer_ts"), bool):
            return _as_error_ack(
                source_type=envelope.message_type,
                route="siming_staging_ack",
                error=ValueError("invalid_staging_ack_timestamp"),
            )
        try:
            ack = StagingAck(
                source="godot",
                correlation_id=payload["correlation_id"],
                accepted=payload["accepted"],
                reason=payload.get("reason", ""),
            )
        except (KeyError, ValidationError, TypeError) as exc:
            return _as_error_ack(
                source_type=envelope.message_type,
                route="siming_staging_ack",
                error=exc,
            )
        if any(
            existing.correlation_id == ack.correlation_id
            and existing.payload.get("source") == ack.source
            for existing in authority_event_bus.list_events(event_type="siming_staging_ack")
        ):
            event_trace.record("siming_staging_ack_duplicate_suppressed")
            return _finalize_outbound_messages(
                [{
                    "message_type": "ack",
                    "payload": {
                        "accepted": True,
                        "source_type": envelope.message_type,
                        "route": "siming_staging_ack_duplicate",
                    },
                }]
            )
        authority_event_bus.publish(
            authority_event_adapter.staging_ack_event(
                ack,
                room_id=payload["room_id"],
                scene_id=payload["scene_id"],
                zone_id=payload["zone_id"],
                producer_ts=payload["producer_ts"],
            )
        )
        event_trace.record("siming_staging_ack")
        return _finalize_outbound_messages(
            [
                {
                    "message_type": "ack",
                    "payload": {
                        "accepted": True,
                        "source_type": envelope.message_type,
                        "route": "siming_staging_ack",
                    },
                }
            ]
        )
    if envelope.message_type == "embodied_interaction_session_probe":
        return _handle_embodied_interaction_session_probe(envelope)

    if envelope.message_type == "embodied_handoff_probe":
        return _handle_embodied_handoff_probe(envelope)

    if envelope.message_type == "embodied_grab_carry_place_probe":
        return _handle_embodied_grab_carry_place_probe(envelope)

    if envelope.message_type == "embodied_controller_bind":
        try:
            enrollment = EmbodiedControllerEnrollment.model_validate(envelope.payload)
        except ValidationError as exc:
            return EmbodiedExecutionIngress.protocol_error(envelope.message_type, f"invalid_payload:{exc.errors()[0]['type']}")
        result = embodied_controller_auth_service.bind_controller(
            enrollment,
            remote_host=connection_context.remote_host,
            now=int(envelope.payload.get("producer_ts", 100) or 100),
            connection_ref=connection_context.connection_ref,
        )
        if not result.accepted or result.binding is None:
            return EmbodiedExecutionIngress.protocol_error(envelope.message_type, result.error_code)
        return [
            {
                "message_type": "ack",
                "payload": {
                    "accepted": True,
                    "source_type": envelope.message_type,
                    "route": "embodied_controller_auth",
                },
            },
            {
                "message_type": "embodied_controller_bound",
                "payload": result.binding.model_dump(mode="json"),
            },
        ]

    if envelope.message_type == "websocket_session_bind":
        if connection_context.binding is not None:
            return _websocket_session_bind_error(envelope.message_type, "websocket_session_already_bound")
        try:
            enrollment = WebSocketSessionEnrollment.model_validate(envelope.payload)
        except ValidationError as exc:
            return _websocket_session_bind_error(envelope.message_type, f"invalid_payload:{exc.errors()[0]['type']}")
        profile = _select_gameplay_mirror_capability_profile(enrollment.capability_offer)
        if profile is None:
            return _websocket_session_bind_error(envelope.message_type, "mirror_capability_incompatible")
        result = websocket_session_auth_service.bind_session(
            enrollment,
            remote_host=connection_context.remote_host,
            now=connection_context.observed_at,
        )
        if not result.accepted or result.binding is None:
            return _websocket_session_bind_error(envelope.message_type, result.error_code)
        connection_context.binding = result.binding
        connection_context.capability_profile = profile
        return [
            {
                "message_type": "ack",
                "payload": {
                    "accepted": True,
                    "source_type": envelope.message_type,
                    "route": "websocket_session_auth",
                },
            },
            {
                "message_type": "websocket_session_bound",
                "payload": {**result.binding.model_dump(mode="json"), "capability_profile": profile.model_dump(mode="json")},
            },
        ]

    if envelope.message_type == "websocket_session_renewal":
        try:
            WebSocketSessionRenewalRequest.model_validate(envelope.payload)
        except ValidationError as exc:
            return _websocket_session_renewal_error(envelope.message_type, f"invalid_payload:{exc.errors()[0]['type']}")
        binding = connection_context.binding
        if binding is None:
            return _websocket_session_renewal_error(envelope.message_type, "renewal_enrollment_required")
        try:
            replacement = websocket_session_auth_service.issue_replacement_enrollment(
                binding.session_ref,
                connection_context.observed_at,
            )
        except ValueError:
            return _websocket_session_renewal_error(envelope.message_type, "renewal_denied")
        _drop_mirror_transport_session(connection_context, binding.session_ref)
        connection_context.binding = None
        _publish_debug_event(
            build_debug_event(
                producer_ts=connection_context.observed_at,
                domain="backend",
                stage="websocket_session_renewal_issued",
                summary="WebSocket session renewal enrollment issued.",
                detail={"connection_ref": connection_context.connection_ref, "previous_session_ref": binding.session_ref},
            )
        )
        return [
            _as_envelope(
                "ack",
                {"accepted": True, "source_type": envelope.message_type, "route": "websocket_session_renewal"},
            ),
            _as_envelope("websocket_session_renewal_enrollment", replacement.model_dump(mode="json", exclude_none=True)),
        ]

    if envelope.message_type == "gameplay_mirror_subscribe":
        try:
            request = GameplayMirrorSubscriptionRequest.model_validate(envelope.payload)
            projection = gameplay_mirror_session_access_service.subscribe(
                context=connection_context,
                request=request,
            )
        except (GameplayMirrorSessionAccessError, GameplayMirrorDeliveryError, ValidationError) as exc:
            return _gameplay_mirror_error(envelope.message_type, _error_code(exc))
        return [
            _as_envelope(
                "ack",
                {
                    "accepted": True,
                    "source_type": envelope.message_type,
                    "route": "gameplay_mirror_subscribe",
                },
            ),
            projection,
        ]

    if envelope.message_type == "gameplay_mirror_snapshot_request":
        try:
            request = GameplayMirrorActorRequest.model_validate(envelope.payload)
            projection = gameplay_mirror_session_access_service.snapshot(
                context=connection_context,
                actor_ref=request.actor_ref,
            )
        except (GameplayMirrorSessionAccessError, GameplayMirrorDeliveryError, ValidationError) as exc:
            return _gameplay_mirror_error(envelope.message_type, _error_code(exc))
        return [
            _as_envelope(
                "ack",
                {
                    "accepted": True,
                    "source_type": envelope.message_type,
                    "route": "gameplay_mirror_snapshot",
                },
            ),
            projection,
        ]

    if envelope.message_type == "gameplay_mirror_resync_request":
        try:
            request = GameplayMirrorActorRequest.model_validate(envelope.payload)
            projection = gameplay_mirror_session_access_service.snapshot(
                context=connection_context,
                actor_ref=request.actor_ref,
            )
        except (GameplayMirrorSessionAccessError, GameplayMirrorDeliveryError, ValidationError) as exc:
            return _gameplay_mirror_error(envelope.message_type, _error_code(exc))
        return [
            _as_envelope(
                "ack",
                {
                    "accepted": True,
                    "source_type": envelope.message_type,
                    "route": "gameplay_mirror_resync",
                },
            ),
            projection,
        ]

    if envelope.message_type == "gameplay_mirror_receipt":
        if connection_context.binding is None:
            return _gameplay_mirror_error(envelope.message_type, "websocket_session_required")
        if connection_context.capability_profile is None or not connection_context.capability_profile.supports_receipt:
            return _gameplay_mirror_error(envelope.message_type, "mirror_capability_incompatible")
        try:
            receipt = GameplayMirrorReceipt.model_validate(envelope.payload)
            gameplay_mirror_connection_registry.acknowledge(
                session_ref=connection_context.binding.session_ref,
                receipt=receipt,
            )
        except (GameplayMirrorDeliveryError, ValidationError) as exc:
            return _gameplay_mirror_error(envelope.message_type, _error_code(exc))
        return [
            _as_envelope(
                "ack",
                {"accepted": True, "source_type": envelope.message_type, "route": "gameplay_mirror_receipt"},
            )
        ]

    if envelope.message_type == "gameplay_mirror_unsubscribe":
        try:
            request = GameplayMirrorActorRequest.model_validate(envelope.payload)
            removed = gameplay_mirror_session_access_service.unsubscribe(
                context=connection_context,
                actor_ref=request.actor_ref,
            )
        except (GameplayMirrorSessionAccessError, GameplayMirrorDeliveryError, ValidationError) as exc:
            return _gameplay_mirror_error(envelope.message_type, _error_code(exc))
        return [
            _as_envelope(
                "ack",
                {
                    "accepted": True,
                    "source_type": envelope.message_type,
                    "route": "gameplay_mirror_unsubscribe",
                    "subscription_removed": removed,
                },
            )
        ]

    if envelope.message_type == "embodied_phase_event":
        result = embodied_execution_ingress.handle_phase_event(
            envelope.payload,
            connection_ref=connection_context.connection_ref,
        )
        if not result.accepted:
            return EmbodiedExecutionIngress.protocol_error(envelope.message_type, result.error_code)
        grant_id = str(envelope.payload.get("grant_id", "") or "")
        if default_scene_archive_door_embodied_service.handles_grant(grant_id):
            if not default_scene_archive_door_embodied_service.record_phase_event(
                envelope.payload,
                now=int(envelope.payload.get("observed_at", 0) or 0),
            ):
                return EmbodiedExecutionIngress.protocol_error(envelope.message_type, "evidence_ledger_rejected")
        return result.outbound

    if envelope.message_type == "embodied_local_outcome":
        grant_id = str(envelope.payload.get("controller_grant_id", "") or "")
        if default_scene_archive_door_embodied_service.handles_grant(grant_id):
            result = default_scene_archive_door_embodied_service.handle_local_outcome(
                envelope.payload,
                connection_ref=connection_context.connection_ref,
                now=int(envelope.payload.get("observed_at", 0) or 0),
            )
            if not result.accepted:
                return EmbodiedExecutionIngress.protocol_error(envelope.message_type, result.error_code)
            outbound = [
                _as_envelope(
                    "ack",
                    {
                        "accepted": True,
                        "source_type": envelope.message_type,
                        "route": "default_scene_archive_door_embodied_authority",
                    },
                ),
            ]
            if result.settlement_payload is not None:
                outbound.append(_as_envelope("embodied_settlement_result", result.settlement_payload))
            if result.object_result is not None:
                outbound.extend(_publish_world_result_authority_event(result.object_result, source_event=envelope))
                outbound.append(_as_world_result_envelope(result.object_result.model_dump(mode="json")))
            return outbound
        result = embodied_execution_ingress.handle_local_outcome(
            envelope.payload,
            now=int(envelope.payload.get("observed_at", 0) or 0),
            connection_ref=connection_context.connection_ref,
        )
        if not result.accepted:
            return EmbodiedExecutionIngress.protocol_error(envelope.message_type, result.error_code)
        session_id = str(envelope.payload.get("session_id", "") or "")
        if session_id:
            task_result = embodied_harness_task_coordinator.record_terminal_observation(
                task_id=session_id,
                participant_ref=str(envelope.payload.get("actor_id", "") or ""),
                attempt_ref=str(envelope.payload.get("interaction_attempt_id", "") or ""),
                terminal_status=str(envelope.payload.get("terminal_status", "failed") or "failed"),
                payload_digest=str(envelope.payload.get("payload_digest", "") or ""),
                producer_ts=int(envelope.payload.get("observed_at", 0) or 0),
            )
            if not task_result.accepted:
                return EmbodiedExecutionIngress.protocol_error(envelope.message_type, task_result.error_code)
        return result.outbound

    if envelope.message_type == "embodied_presentation_observed":
        result = default_scene_archive_door_embodied_service.record_presentation_observation(
            envelope.payload,
            connection_ref=connection_context.connection_ref,
            now=int(time() * 1000),
        )
        if not result.accepted:
            return EmbodiedExecutionIngress.protocol_error(envelope.message_type, result.error_code)
        return [
            _as_envelope(
                "ack",
                {
                    "accepted": True,
                    "source_type": envelope.message_type,
                    "route": "default_scene_archive_door_presentation_evidence",
                    "idempotent": result.idempotent,
                },
            )
        ]

    if envelope.message_type == "embodied_resync_request":
        return [
            {
                "message_type": "ack",
                "payload": {
                    "accepted": True,
                    "source_type": envelope.message_type,
                    "route": "embodied_resync",
                },
            },
            {
                "message_type": "embodied_resync_projection",
                "payload": {
                    "resume_allowed": False,
                    "reason": "authority_grant_required_after_resync",
                },
            },
        ]

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
                response = _handle_character_agent_speech_action(
                    actor_id=actor_id,
                    action=action,
                    producer_ts=0,
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
        response = _handle_player_dialogue_submit(event)
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

    if route["route"] == "default_scene_pickup_authority" and isinstance(event, PickupIntent):
        return _finalize_outbound_messages(_handle_default_scene_pickup(event))
    if route["route"] == "default_scene_inventory_authority" and isinstance(event, StowIntent):
        return _finalize_outbound_messages(_handle_default_scene_stow(event))
    if route["route"] == "default_scene_inventory_authority" and isinstance(event, RetrieveIntent):
        return _finalize_outbound_messages(_handle_default_scene_retrieve(event))

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
        if event.target_object_id == "obj_archive_door" and event.interaction_type in {"open", "close"}:
            preflight = default_scene_archive_door_embodied_service.preflight(
                event=event,
                action_request=action_request,
                actor_position=actor_position,
                connection_ref=connection_context.connection_ref,
                now=event.producer_ts,
            )
            if preflight.constraint is not None:
                messages.extend(_publish_world_result_authority_event(preflight.constraint, source_event=event))
                messages.append(_as_world_result_envelope(preflight.constraint.model_dump(mode="json")))
            elif preflight.embodied_action_request is not None:
                messages.append(_as_envelope("embodied_action_request", preflight.embodied_action_request))
            return _finalize_outbound_messages(messages)
        interaction_policy = esm_service.interaction_policy_for(
            event.target_object_id,
            event.interaction_type,
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            actor_id=event.actor_id,
        )
        if interaction_policy is None:
            world_result = esm_service.reject_unsupported_interaction(event)
        elif not bool(interaction_policy.get("state_match", True)):
            world_result = esm_service.reject_interaction_state(
                event,
                expected_state=str(interaction_policy["previous_state"]),
                actual_state=esm_service.interaction_state_for(
                    room_id=event.room_id,
                    scene_id=event.scene_id,
                    zone_id=event.zone_id,
                    target_object_id=event.target_object_id,
                ),
            )
        elif not bool(interaction_policy.get("owner_match", True)):
            world_result = esm_service.reject_interaction_owner(
                event,
                expected_owner=event.actor_id,
                actual_owner=esm_service.interaction_owner_for(
                    room_id=event.room_id,
                    scene_id=event.scene_id,
                    zone_id=event.zone_id,
                    target_object_id=event.target_object_id,
                ),
            )
        else:
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
            if interaction_policy is None:
                raise RuntimeError("accepted interaction must have a registered ESM policy")
            previous_object_state = str(interaction_policy["previous_state"])
            current_object_state = str(interaction_policy["current_state"])
            object_affordances = [str(value) for value in interaction_policy["affordances"]]
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
                machine_id=str(interaction_policy["machine_id"]),
                from_state=previous_object_state,
                to_state=current_object_state,
                trigger_type="interact.%s" % event.interaction_type,
                transition_reason="player interaction accepted by registered ESM policy",
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
                previous_state=previous_object_state,
                current_state=current_object_state,
                machine_id=str(interaction_policy["machine_id"]),
                producer_ts=world_result.producer_ts + 2,
                request_ref=world_result.request_ref,
                causation_id=world_result.causation_id,
                correlation_id=world_result.correlation_id,
            )
            l1_occupancy_service.apply_object_state_update(
                object_id=object_state_result.target_object_id,
                zone_id=object_state_result.zone_id,
                state=object_state_result.current_state,
                affordances=object_affordances,
                occludes=bool(interaction_policy["occludes"]),
                producer_ts=object_state_result.producer_ts,
                source_ref=object_state_result.result_id,
            )
            event_trace.record(object_state_result.result_type)
            messages.extend(_publish_world_result_authority_event(object_state_result, source_event=event))
            esm_service.commit_interaction_state(
                room_id=event.room_id,
                scene_id=event.scene_id,
                zone_id=event.zone_id,
                target_object_id=event.target_object_id,
                current_state=object_state_result.current_state,
                actor_id=event.actor_id,
                interaction_type=event.interaction_type,
            )

            body_state_result = esm_service.emit_body_state_result(
                room_id=event.room_id,
                scene_id=event.scene_id,
                zone_id=event.zone_id,
                actor_id=event.actor_id,
                body_state_class=str(interaction_policy.get("body_state_class", "interaction_strain")),
                previous_state=str(interaction_policy.get("body_previous_state", "steady")),
                current_state=str(interaction_policy.get("body_current_state", "engaged")),
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
            if os.environ.get("SIMING_HEAVENLY_AUTOTEST_SETUP") != "1":
                character_agent_runtime.run_scheduled_background_cognition_ticks(self_body_perceived.producer_ts)
            if event.actor_id != "char_c":
                messages.extend(
                    _as_character_agent_suggestion_envelopes(
                        character_agent_runtime.drain_suggestion_packets(event.actor_id)
                    )
                )

            if str(interaction_policy["environment_transition"]) == "alert_lamp":
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


def _websocket_session_bind_error(source_type: str, error_code: str) -> list[dict[str, object]]:
    return [
        {
            "message_type": "ack",
            "payload": {
                "accepted": False,
                "source_type": source_type,
                "route": "websocket_session_auth",
                "error_code": error_code,
            },
        }
    ]


def _select_gameplay_mirror_capability_profile(
    offer: GameplayMirrorCapabilityOffer | None,
) -> GameplayMirrorCapabilityProfile | None:
    """Intersect untrusted feature preferences with the fixed server policy."""

    if offer is None:
        return GameplayMirrorCapabilityProfile(
            protocol_version=1,
            supports_snapshot=True,
            supports_delta=False,
            supports_receipt=False,
            projection_schema="gameplay_runtime_state.godot.v1",
        )
    if not offer.supports_snapshot or "gameplay_runtime_state.godot.v1" not in offer.projection_schemas:
        return None
    return GameplayMirrorCapabilityProfile(
        protocol_version=min(offer.protocol_version, 2),
        supports_snapshot=True,
        supports_delta=False,
        supports_receipt=offer.supports_receipt,
        projection_schema="gameplay_runtime_state.godot.v1",
    )


def _websocket_session_renewal_error(source_type: str, error_code: str) -> list[dict[str, object]]:
    return [
        _as_envelope(
            "ack",
            {
                "accepted": False,
                "source_type": source_type,
                "route": "websocket_session_renewal",
                "error_code": error_code,
            },
        )
    ]


def _drop_mirror_transport_session(connection_context: WebSocketConnectionContext, session_ref: str) -> None:
    """Remove only disposable delivery state; committed gameplay data is intentionally untouched."""

    gameplay_mirror_subscription_registry.drop_session(session_ref=session_ref)
    gameplay_mirror_connection_registry.unregister(
        session_ref=session_ref,
        connection_ref=connection_context.connection_ref,
    )


def _revoke_mirror_delivery_session(session_ref: str) -> None:
    """Close an unusable mirror transport without touching committed gameplay state."""

    connection_ref = gameplay_mirror_connection_registry.connection_ref_for(session_ref=session_ref)
    if connection_ref is None:
        gameplay_mirror_subscription_registry.drop_session(session_ref=session_ref)
        return
    revoke_websocket_session_for_transport(
        session_ref=session_ref,
        connection_ref=connection_ref,
        reason_code="mirror_delivery_unrecoverable",
        now=int(time()),
    )


def revoke_websocket_session_for_transport(
    *,
    session_ref: str,
    connection_ref: str,
    reason_code: str,
    now: int,
) -> bool:
    """Server-only lifecycle hook that cannot alter committed gameplay authority data."""

    revoked = websocket_session_auth_service.revoke_session(
        session_ref,
        reason_code=reason_code,
        now=now,
    )
    if not revoked:
        return False
    _drop_mirror_transport_session(
        WebSocketConnectionContext(remote_host="", observed_at=now, connection_ref=connection_ref),
        session_ref,
    )
    _publish_debug_event(
        build_debug_event(
            producer_ts=now,
            domain="backend",
            stage="websocket_session_revoked",
            summary="WebSocket session transport revoked.",
            detail={"connection_ref": connection_ref, "session_ref": session_ref, "reason_code": reason_code},
        )
    )
    closer = websocket_transport_closers.get(connection_ref)
    if closer is not None:
        closer(reason_code)
    return True


def _gameplay_mirror_error(source_type: str, error_code: str) -> list[dict[str, object]]:
    return [
        _as_envelope(
            "ack",
            {
                "accepted": False,
                "source_type": source_type,
                "route": "gameplay_mirror",
                "error_code": error_code,
            },
        )
    ]


def _session_bound_by(
    messages: list[dict[str, object]],
    source_type: str,
    connection_context: WebSocketConnectionContext,
) -> bool:
    if source_type != "websocket_session_bind" or connection_context.binding is None:
        return False
    return any(
        message.get("message_type") == "ack"
        and isinstance(message.get("payload"), dict)
        and message["payload"].get("accepted") is True
        and message["payload"].get("route") == "websocket_session_auth"
        for message in messages
    )


def _error_code(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return f"invalid_payload:{exc.errors()[0]['type']}"
    return str(exc)


def _handle_embodied_interaction_session_probe(envelope: Envelope) -> list[dict[str, object]]:
    payload = envelope.payload if isinstance(envelope.payload, dict) else {}
    session_id = str(payload.get("session_id", "") or "session:handshake:websocket")
    semantic_action = str(payload.get("semantic_action", "") or "handshake")
    initiator_ref = str(payload.get("initiator_ref", "") or "character:siming")
    participant_refs = [str(item) for item in payload.get("participant_refs", [])] if isinstance(payload.get("participant_refs", []), list) else []
    if not participant_refs:
        participant_refs = [initiator_ref, "character:maya"]
    target_refs = [str(item) for item in payload.get("target_refs", [])] if isinstance(payload.get("target_refs", []), list) else []
    participant_private_terms = payload.get("participant_private_terms")
    if participant_private_terms is not None and not isinstance(participant_private_terms, dict):
        return EmbodiedExecutionIngress.protocol_error(envelope.message_type, "invalid_participant_private_terms")

    bus_start = len(authority_event_bus.list_events())
    task_result = embodied_harness_task_coordinator.run_handshake(
        session_id=session_id,
        semantic_action=semantic_action,
        initiator_ref=initiator_ref,
        participant_refs=participant_refs,
        target_refs=target_refs,
        authority_preflight_ref=str(payload.get("authority_preflight_ref", "") or f"preflight:{session_id}"),
        policy_revision=int(payload.get("policy_revision", 3) or 3),
        scene_revision=int(payload.get("scene_revision", 11) or 11),
        causation_id=str(payload.get("causation_id", "") or f"cmd:{session_id}:propose"),
        correlation_id=str(payload.get("correlation_id", "") or f"corr:{session_id}"),
        participant_private_terms=participant_private_terms,
        complete=False,
    )
    if not task_result.accepted:
        return EmbodiedExecutionIngress.protocol_error(envelope.message_type, task_result.error_code)

    session_messages = [
        outbound
        for event in authority_event_bus.list_events()[bus_start:]
        if (outbound := _embodied_session_event_envelope_from_authority_event(event)) is not None
    ]
    embodied_harness_task_coordinator.record_godot_projection(
        session_id,
        session_messages,
        producer_ts=int(payload.get("producer_ts", 0) or 0),
    )
    return [
        _as_envelope(
            "ack",
            {
                "accepted": True,
                "source_type": "embodied_interaction_session_probe",
                "route": "embodied_interaction_session",
            },
        ),
        *session_messages,
    ]


def _embodied_session_event_envelope_from_authority_event(event: AuthorityEvent) -> dict[str, object] | None:
    if not event.event_type.startswith("embodied.interaction_session."):
        return None
    payload = dict(event.payload)
    committed_payload = payload.get("committed_payload", {})
    if not isinstance(committed_payload, dict):
        committed_payload = {}
    state = str(payload.get("state", "") or committed_payload.get("state", "") or "")
    safe_payload: dict[str, object] = {
        "event_type": event.event_type,
        "session_id": str(payload.get("session_id", "") or committed_payload.get("session_id", "") or ""),
        "semantic_action": str(payload.get("semantic_action", "") or committed_payload.get("semantic_action", "") or ""),
        "state": state,
        "safe_phase": str(payload.get("safe_phase", "") or state),
        "sync_status": str(payload.get("sync_status", "") or state),
        "transaction_id": str(payload.get("transaction_id", "") or ""),
        "event_id": str(payload.get("event_id", "") or event.event_id),
        "stream_id": str(payload.get("stream_id", "") or ""),
        "stream_revision": int(payload.get("stream_revision", 0) or 0),
        "global_sequence": int(payload.get("global_sequence", 0) or 0),
    }
    allowed_projection_fields = {
        "initiator_ref",
        "participant_ref",
        "participant_refs",
        "target_refs",
        "slot_assignments",
        "reservation_refs",
        "actor_ref",
        "target_ref",
        "reason_code",
        "attempt_ref",
        "attempt_refs",
        "terminal_status",
        "settlement_ref",
        "policy_revision",
        "scene_revision",
        "visibility_policy",
    }
    for field_name in allowed_projection_fields:
        if field_name in payload:
            safe_payload[field_name] = payload[field_name]
        elif field_name in committed_payload:
            safe_payload[field_name] = committed_payload[field_name]
    return _as_envelope("embodied_interaction_session_event", safe_payload)


def _handle_embodied_handoff_probe(envelope: Envelope) -> list[dict[str, object]]:
    payload = envelope.payload if isinstance(envelope.payload, dict) else {}
    session_id = str(payload.get("session_id", "") or "session:handoff:websocket:1")
    asset_ref = str(payload.get("asset_ref", "") or "item:letter_01")
    from_actor_ref = str(payload.get("from_actor_ref", "") or "character:siming")
    to_actor_ref = str(payload.get("to_actor_ref", "") or "character:maya")
    bus_start = len(authority_event_bus.list_events())
    started = embodied_handoff_authority_service.start_handoff(
        session_id=session_id,
        asset_ref=asset_ref,
        from_actor_ref=from_actor_ref,
        to_actor_ref=to_actor_ref,
        causation_id=f"cmd:{session_id}:start",
        correlation_id=f"corr:{session_id}",
    )
    if not started.accepted:
        return EmbodiedExecutionIngress.protocol_error(envelope.message_type, started.error_code)
    settled = embodied_handoff_authority_service.settle_handoff(
        session_id=session_id,
        asset_ref=asset_ref,
        from_actor_ref=from_actor_ref,
        to_actor_ref=to_actor_ref,
        participant_observations={
            from_actor_ref: f"digest:terminal:{session_id}:{from_actor_ref}",
            to_actor_ref: f"digest:terminal:{session_id}:{to_actor_ref}",
        },
        idempotency_key=f"handoff:{session_id}:settle",
        payload_digest=f"digest:handoff:{session_id}",
    )
    if not settled.accepted:
        return EmbodiedExecutionIngress.protocol_error(envelope.message_type, settled.error_code)
    handoff_messages = [
        outbound
        for event in authority_event_bus.list_events()[bus_start:]
        if (outbound := _embodied_handoff_event_envelope_from_authority_event(event)) is not None
    ]
    return [
        _as_envelope(
            "ack",
            {
                "accepted": True,
                "source_type": "embodied_handoff_probe",
                "route": "embodied_handoff_authority",
            },
        ),
        *handoff_messages,
    ]


def _embodied_handoff_event_envelope_from_authority_event(event: AuthorityEvent) -> dict[str, object] | None:
    if event.event_type != "embodied.handoff.settled":
        return None
    payload = dict(event.payload)
    committed_payload = payload.get("committed_payload", {})
    if not isinstance(committed_payload, dict):
        committed_payload = {}
    safe_payload: dict[str, object] = {
        "event_type": event.event_type,
        "transaction_id": str(payload.get("transaction_id", "") or ""),
        "event_id": str(payload.get("event_id", "") or event.event_id),
        "stream_id": str(payload.get("stream_id", "") or ""),
        "stream_revision": int(payload.get("stream_revision", 0) or 0),
        "global_sequence": int(payload.get("global_sequence", 0) or 0),
    }
    allowed_fields = {
        "session_id",
        "asset_ref",
        "from_actor_ref",
        "to_actor_ref",
        "custody_holder_ref",
        "owner_ref",
        "settlement_ref",
        "attachment_directive",
    }
    for field_name in allowed_fields:
        if field_name in payload:
            safe_payload[field_name] = payload[field_name]
        elif field_name in committed_payload:
            safe_payload[field_name] = committed_payload[field_name]
    return _as_envelope("embodied_handoff_event", safe_payload)


def _handle_embodied_grab_carry_place_probe(envelope: Envelope) -> list[dict[str, object]]:
    payload = envelope.payload if isinstance(envelope.payload, dict) else {}
    session_id = str(payload.get("session_id", "") or "session:carry-place:websocket:1")
    asset_ref = str(payload.get("asset_ref", "") or "item:crate_01")
    actor_ref = str(payload.get("actor_ref", "") or "character:siming")
    source_holder_ref = str(payload.get("source_holder_ref", "") or "world:anchor:table_01")
    drop_target_ref = str(payload.get("drop_target_ref", "") or "world:anchor:floor_slot_01")
    bus_start = len(authority_event_bus.list_events())
    started = embodied_carry_place_authority_service.start_carry_place(
        session_id=session_id,
        asset_ref=asset_ref,
        actor_ref=actor_ref,
        source_holder_ref=source_holder_ref,
        drop_target_ref=drop_target_ref,
        causation_id=f"cmd:{session_id}:start",
        correlation_id=f"corr:{session_id}",
    )
    if not started.accepted:
        return EmbodiedExecutionIngress.protocol_error(envelope.message_type, started.error_code)
    settled = embodied_carry_place_authority_service.settle_carry_place(
        session_id=session_id,
        asset_ref=asset_ref,
        actor_ref=actor_ref,
        source_holder_ref=source_holder_ref,
        drop_target_ref=drop_target_ref,
        participant_observations={
            actor_ref: f"digest:terminal:{session_id}:{actor_ref}",
            drop_target_ref: f"digest:terminal:{session_id}:{drop_target_ref}",
        },
        idempotency_key=f"carry-place:{session_id}:settle",
        payload_digest=f"digest:carry-place:{session_id}",
    )
    if not settled.accepted:
        return EmbodiedExecutionIngress.protocol_error(envelope.message_type, settled.error_code)
    carry_place_messages = [
        outbound
        for event in authority_event_bus.list_events()[bus_start:]
        if (outbound := _embodied_carry_place_event_envelope_from_authority_event(event)) is not None
    ]
    return [
        _as_envelope(
            "ack",
            {
                "accepted": True,
                "source_type": "embodied_grab_carry_place_probe",
                "route": "embodied_carry_place_authority",
            },
        ),
        *carry_place_messages,
    ]


def _handle_default_scene_pickup(event: PickupIntent) -> list[dict[str, object]]:
    """Settles a reviewed pickup without accepting client-controlled world refs."""

    resolution = default_scene_pickup_policy_service.resolve(
        target_object_id=event.target_object_id,
        interaction_type=event.interaction_type,
        actor_id=event.actor_id,
        room_id=event.room_id,
        scene_id=event.scene_id,
        zone_id=event.zone_id,
        actor_position=runtime.get_actor_position(event.actor_id),
    )
    if not resolution.accepted or resolution.policy is None:
        return _default_scene_pickup_rejection(event, resolution.error_code)

    policy = resolution.policy
    session_id = f"session:default-scene-pickup:{event.actor_id}:{event.target_object_id}:{event.producer_ts}"
    bus_start = len(authority_event_bus.list_events())
    started = embodied_carry_place_authority_service.start_carry_place(
        session_id=session_id,
        asset_ref=policy.asset_ref,
        actor_ref=resolution.actor_ref,
        source_holder_ref=policy.source_holder_ref,
        drop_target_ref=resolution.drop_target_ref,
        causation_id=f"cmd:{session_id}:start",
        correlation_id=f"corr:{session_id}",
    )
    if not started.accepted:
        return _default_scene_pickup_rejection(event, started.error_code)

    settled = embodied_carry_place_authority_service.settle_carry_place(
        session_id=session_id,
        asset_ref=policy.asset_ref,
        actor_ref=resolution.actor_ref,
        source_holder_ref=policy.source_holder_ref,
        drop_target_ref=resolution.drop_target_ref,
        participant_observations={
            resolution.actor_ref: f"digest:terminal:{session_id}:{resolution.actor_ref}",
            resolution.drop_target_ref: f"digest:terminal:{session_id}:{resolution.drop_target_ref}",
        },
        idempotency_key=f"default-scene-pickup:{session_id}:settle",
        payload_digest=f"digest:default-scene-pickup:{session_id}",
    )
    if not settled.accepted:
        return _default_scene_pickup_rejection(event, settled.error_code)

    carry_place_messages = [
        outbound
        for authority_event in authority_event_bus.list_events()[bus_start:]
        if (outbound := _embodied_carry_place_event_envelope_from_authority_event(authority_event)) is not None
    ]
    return [
        _as_envelope(
            "ack",
            {
                "accepted": True,
                "source_type": "player_input",
                "route": "default_scene_pickup_authority",
            },
        ),
        _as_envelope(
            "embodied_pickup_result",
            {
                "accepted": True,
                "target_object_id": event.target_object_id,
                "interaction_type": event.interaction_type,
                "policy_revision": policy.policy_revision,
                "possession_semantics": "custody_only",
            },
        ),
        *carry_place_messages,
    ]


def _default_scene_pickup_rejection(event: PickupIntent, error_code: str) -> list[dict[str, object]]:
    return [
        _as_envelope(
            "ack",
            {
                "accepted": False,
                "source_type": "player_input",
                "route": "default_scene_pickup_authority",
            },
        ),
        _as_envelope(
            "embodied_pickup_result",
            {
                "accepted": False,
                "target_object_id": event.target_object_id,
                "interaction_type": event.interaction_type,
                "constraint_type": "pickup_authority_constraint",
                "constraint_code": error_code or "pickup_rejected",
            },
        ),
    ]


def _handle_default_scene_stow(event: StowIntent) -> list[dict[str, object]]:
    resolution = default_scene_pickup_policy_service.resolve_stow(
        target_object_id=event.target_object_id,
        actor_id=event.actor_id,
        room_id=event.room_id,
        scene_id=event.scene_id,
        zone_id=event.zone_id,
    )
    if not resolution.accepted or resolution.policy is None:
        return _as_default_scene_stow_result(event, False, resolution.error_code)

    policy = resolution.policy
    destination_container_id = DefaultScenePickupPolicyService.inventory_destination_for(
        policy,
        event.actor_id,
    )
    if not destination_container_id:
        return _as_default_scene_stow_result(event, False, "inventory_destination_unavailable")
    command_id = f"stow:{event.actor_id}:{event.target_object_id}:{event.producer_ts}"
    result = embodied_custody_inventory_authority_service.stow_from_custody(
        command_id=command_id,
        actor_ref=resolution.actor_ref,
        asset_ref=policy.asset_ref,
        item_id=policy.asset_ref,
        definition_id=policy.inventory_definition_id,
        quantity=policy.inventory_quantity,
        source_holder_ref=resolution.drop_target_ref,
        destination_container_id=destination_container_id,
        idempotency_key=command_id,
        causation_id=f"stow:{event.producer_ts}",
        correlation_id=f"stow:{event.producer_ts}",
    )
    return _as_default_scene_stow_result(
        event,
        result.accepted,
        result.error_code,
        result.transaction_id,
    )


def _as_default_scene_stow_result(event: StowIntent, accepted: bool, error_code: str = "", transaction_id: str = "") -> list[dict[str, object]]:
    payload: dict[str, object] = {
        "accepted": accepted,
        "target_object_id": event.target_object_id,
        "constraint_code": error_code,
        "transaction_id": transaction_id,
        "possession_semantics": "inventory_location" if accepted else "",
    }
    if accepted:
        payload["presentation_directive"] = {
            "mode": "inventory_stowed_for_presentation",
            "authority_only": True,
        }
    return [
        _as_envelope(
            "ack",
            {
                "accepted": accepted,
                "source_type": "player_input",
                "route": "default_scene_inventory_authority",
                "request_id": event.request_id,
                "intent_type": event.intent_type,
                "producer_ts": event.producer_ts,
            },
        ),
        _as_envelope(
            "embodied_inventory_stow_result",
            payload,
        ),
    ]


def _handle_default_scene_retrieve(event: RetrieveIntent) -> list[dict[str, object]]:
    resolution = default_scene_pickup_policy_service.resolve_retrieve(
        target_object_id=event.target_object_id,
        actor_id=event.actor_id,
        room_id=event.room_id,
        scene_id=event.scene_id,
        zone_id=event.zone_id,
        actor_position=runtime.get_actor_position(event.actor_id),
    )
    if not resolution.accepted or resolution.policy is None:
        return _as_default_scene_retrieve_result(event, False, resolution.error_code)

    policy = resolution.policy
    command_id = f"retrieve:{event.actor_id}:{event.target_object_id}:{event.producer_ts}"
    result = embodied_custody_inventory_authority_service.retrieve_to_custody(
        command_id=command_id,
        actor_ref=resolution.actor_ref,
        asset_ref=policy.asset_ref,
        item_id=policy.item_id,
        source_container_id=resolution.source_container_id,
        destination_receiver_ref=resolution.destination_receiver_ref,
        expected_definition_id=policy.expected_definition_id,
        idempotency_key=command_id,
        causation_id=f"retrieve:{event.producer_ts}",
        correlation_id=f"retrieve:{event.producer_ts}",
    )
    return _as_default_scene_retrieve_result(
        event,
        result.accepted,
        result.error_code,
        result.transaction_id,
        policy.asset_ref,
    )


def _as_default_scene_retrieve_result(
    event: RetrieveIntent,
    accepted: bool,
    error_code: str = "",
    transaction_id: str = "",
    asset_ref: str = "",
) -> list[dict[str, object]]:
    payload: dict[str, object] = {
        "accepted": accepted,
        "target_object_id": event.target_object_id,
        "constraint_code": error_code,
        "transaction_id": transaction_id,
        "possession_semantics": "custody_only" if accepted else "",
        "asset_ref": asset_ref if accepted else "",
    }
    if accepted:
        payload["presentation_directive"] = {
            "mode": "inventory_retrieved_for_presentation",
            "authority_only": True,
        }
    return [
        _as_envelope(
            "ack",
            {
                "accepted": accepted,
                "source_type": "player_input",
                "route": "default_scene_inventory_authority",
                "request_id": event.request_id,
                "intent_type": event.intent_type,
                "producer_ts": event.producer_ts,
            },
        ),
        _as_envelope("embodied_inventory_retrieve_result", payload),
    ]


def _embodied_carry_place_event_envelope_from_authority_event(event: AuthorityEvent) -> dict[str, object] | None:
    if event.event_type != "embodied.place.settled":
        return None
    payload = dict(event.payload)
    committed_payload = payload.get("committed_payload", {})
    if not isinstance(committed_payload, dict):
        committed_payload = {}
    safe_payload: dict[str, object] = {
        "event_type": event.event_type,
        "transaction_id": str(payload.get("transaction_id", "") or ""),
        "event_id": str(payload.get("event_id", "") or event.event_id),
        "stream_id": str(payload.get("stream_id", "") or ""),
        "stream_revision": int(payload.get("stream_revision", 0) or 0),
        "global_sequence": int(payload.get("global_sequence", 0) or 0),
    }
    allowed_fields = {
        "session_id",
        "asset_ref",
        "actor_ref",
        "source_holder_ref",
        "drop_target_ref",
        "custody_holder_ref",
        "owner_ref",
        "settlement_ref",
        "placement_directive",
    }
    for field_name in allowed_fields:
        if field_name in payload:
            safe_payload[field_name] = payload[field_name]
        elif field_name in committed_payload:
            safe_payload[field_name] = committed_payload[field_name]
    return _as_envelope("embodied_carry_place_event", safe_payload)


def _parse_player_input(payload: dict) -> MoveIntent | DialogueSubmit | InteractIntent | PickupIntent | StowIntent | RetrieveIntent | FocusTargetChange:
    intent_type = payload.get("intent_type", "")
    if intent_type == "dialogue_submit":
        return DialogueSubmit(**payload)
    if intent_type == "interact_intent":
        return InteractIntent(**payload)
    if intent_type == "pickup_intent":
        return PickupIntent(**payload)
    if intent_type == "stow_intent":
        return StowIntent(**payload)
    if intent_type == "retrieve_intent":
        return RetrieveIntent(**payload)
    if intent_type == "move_intent":
        return MoveIntent(**payload)
    if intent_type == "focus_target_change":
        return FocusTargetChange(**payload)
    raise ValueError(f"unsupported intent_type: {intent_type}")


def _handle_player_dialogue_submit(event: DialogueSubmit) -> DialogueResponse:
    direct_content = _dialogue_direct_content(event)
    if direct_content:
        response = _direct_dialogue_response(event, direct_content)
    else:
        response = character_service.handle_dialogue(event)
    _record_completed_dialogue_response(response)
    return response


def _dialogue_direct_content(event: DialogueSubmit) -> str:
    commands: list[CharacterGoalCommand] = []
    if _is_agent_dialogue_target(event.target_actor_id):
        perceived = _dialogue_submit_to_character_perceived_event(event)
        commands = _ingest_dialogue_perception(perceived)
    return _first_speech_command_content(commands)


def _direct_dialogue_response(event: DialogueSubmit, content: str) -> DialogueResponse:
    audio = character_service.tts.synthesize(event.target_actor_id, content)
    return DialogueResponse(
        actor_id=event.target_actor_id,
        room_id=event.room_id,
        output_type="dialogue_response",
        causation_id=f"dialogue:{event.producer_ts}",
        producer_ts=event.producer_ts + 1,
        target_actor_id=event.actor_id,
        content=content,
        tone="neutral",
        tts_required=True,
        audio=audio,
        request_id=event.request_id,
    )


def _record_completed_dialogue_response(response: DialogueResponse) -> None:
    if _is_agent_dialogue_target(response.actor_id):
        character_agent_runtime.record_dialogue_response(
            actor_id=response.actor_id,
            producer_ts=int(response.producer_ts or 0),
            payload=response.model_dump(),
        )


def _streamable_dialogue_submit(envelope: Envelope) -> DialogueSubmit | None:
    if envelope.message_type != "player_input":
        return None
    event = _parse_player_input(envelope.payload)
    return event if isinstance(event, DialogueSubmit) else None


def _next_dialogue_stream_event(stream) -> tuple[bool, dict[str, object] | None]:
    try:
        return True, next(stream)
    except StopIteration:
        return False, None


def _dialogue_stream_end(
    request_id: str,
    status: str,
    partial_chars: int,
    fallback_used: bool,
) -> dict[str, object]:
    return _as_envelope(
        "dialogue_stream_end",
        {
            "request_id": request_id,
            "status": status,
            "partial_chars": partial_chars,
            "fallback_used": fallback_used,
        },
    )


def _handle_character_agent_speech_action(
    *,
    actor_id: str,
    action: dict[str, object],
    producer_ts: int,
) -> DialogueResponse:
    request_type = str(action.get("request_type", "") or "")
    speaking_actor_id = str(action.get("actor_id", "") or actor_id)
    content = str(action.get("content", "") or "")
    target_actor_id = str(action.get("target_actor_id", "") or "")
    tone = str(action.get("tone", "") or "neutral")
    room_id = str(action.get("room_id", "") or "room_demo")
    audio = character_service.tts.synthesize(speaking_actor_id, content)
    response = DialogueResponse(
        actor_id=speaking_actor_id,
        room_id=room_id,
        output_type="dialogue_response",
        causation_id=f"dialogue:{producer_ts}",
        producer_ts=producer_ts + 1,
        target_actor_id=target_actor_id,
        content=content,
        tone=tone,
        tts_required=True,
        audio=audio,
    )
    character_agent_runtime.record_dialogue_response(
        actor_id=response.actor_id,
        producer_ts=int(response.producer_ts or 0),
        payload=response.model_dump(),
    )
    _backfill_character_agent_speech_perception(
        action=action,
        request_type=request_type,
        response=response,
    )
    return response


def _is_agent_dialogue_target(actor_id: str) -> bool:
    return (
        actor_id not in _PLAYER_SHELL_ACTOR_IDS
        and actor_id != ""
        and character_agent_runtime.supports_actor(actor_id)
    )


def _dialogue_submit_to_character_perceived_event(event: DialogueSubmit) -> CharacterPerceivedEvent:
    source_event_id = f"dialogue_submit:{event.producer_ts}:{event.actor_id}:{event.target_actor_id}"
    return CharacterPerceivedEvent(
        actor_id=event.target_actor_id,
        percept_channel="auditory",
        producer_ts=event.producer_ts,
        room_id=event.room_id,
        scene_id=event.scene_id,
        zone_id=event.zone_id,
        perceived_summary=f'{event.actor_id}对你说："{event.content}"',
        source_candidate_event_id=source_event_id,
        source_actor_id=event.actor_id,
        target_actor_id=event.target_actor_id,
        subject_ref=event.actor_id,
        target_ref=event.target_actor_id,
        source_ref_lineage=[source_event_id],
        clarity_score=1.0,
        certainty_score=1.0,
    )


def _backfill_character_agent_speech_perception(
    *,
    action: dict[str, object],
    request_type: str,
    response: DialogueResponse,
) -> None:
    for perceived in _character_agent_speech_perceived_events(
        action=action,
        request_type=request_type,
        response=response,
    ):
        _ingest_dialogue_perception(perceived)


def _character_agent_speech_perceived_events(
    *,
    action: dict[str, object],
    request_type: str,
    response: DialogueResponse,
) -> list[CharacterPerceivedEvent]:
    room_id = str(action.get("room_id", "") or response.room_id or "room_demo")
    scene_id = str(action.get("scene_id", "") or "scene_demo")
    zone_id = str(action.get("zone_id", "") or "zone_focus")
    lineage = _speech_source_ref_lineage(action)
    events: list[CharacterPerceivedEvent] = []
    for listener_id in _speech_perception_recipients(
        action=action,
        request_type=request_type,
        speaker_actor_id=response.actor_id,
        target_actor_id=str(response.target_actor_id or ""),
        zone_id=zone_id,
    ):
        source_event_id = (
            f"character_agent_speech:{response.producer_ts}:"
            f"{request_type}:{response.actor_id}:{listener_id}"
        )
        perceived_summary = f'{response.actor_id}对你说："{response.content}"'
        events.append(
            CharacterPerceivedEvent(
                actor_id=listener_id,
                percept_channel="auditory",
                producer_ts=int(response.producer_ts or 0),
                room_id=room_id,
                scene_id=scene_id,
                zone_id=zone_id,
                perceived_summary=perceived_summary,
                source_candidate_event_id=source_event_id,
                source_actor_id=response.actor_id,
                target_actor_id=listener_id,
                subject_ref=response.actor_id,
                target_ref=listener_id,
                source_ref_lineage=[*lineage, source_event_id],
                clarity_score=1.0,
                certainty_score=1.0,
            )
        )
    return events


def _speech_perception_recipients(
    *,
    action: dict[str, object],
    request_type: str,
    speaker_actor_id: str,
    target_actor_id: str,
    zone_id: str,
) -> list[str]:
    if request_type in {"speak_private", "share_info", "withhold"}:
        candidates = [target_actor_id] if target_actor_id else []
    elif request_type == "speak_public":
        candidates = _same_room_agent_actor_ids(zone_id=zone_id)
        if target_actor_id:
            candidates.append(target_actor_id)
    else:
        candidates = []

    recipients: list[str] = []
    for candidate in candidates:
        actor_id = str(candidate or "")
        if actor_id == speaker_actor_id or not _is_agent_dialogue_target(actor_id):
            continue
        if actor_id not in recipients:
            recipients.append(actor_id)
    return recipients


def _same_room_agent_actor_ids(*, zone_id: str) -> list[str]:
    snapshot = l1_occupancy_service.snapshot()
    if zone_id:
        zone = snapshot.zone_states.get(zone_id)
        if zone is not None and zone.actor_ids:
            return list(zone.actor_ids)

    actor_ids: list[str] = []
    for zone in snapshot.zone_states.values():
        actor_ids.extend(zone.actor_ids)
    if actor_ids:
        return sorted(set(actor_ids))

    return sorted(str(actor_id) for actor_id in getattr(character_agent_runtime, "_supported_actor_ids", set()))


def _speech_source_ref_lineage(action: dict[str, object]) -> list[str]:
    raw_lineage = action.get("source_ref_lineage", [])
    if not isinstance(raw_lineage, list):
        return []
    lineage: list[str] = []
    for ref in raw_lineage:
        text = str(ref or "")
        if text:
            lineage.append(text)
    return lineage


def _ingest_dialogue_perception(perceived: CharacterPerceivedEvent) -> list[CharacterGoalCommand]:
    if not _is_agent_dialogue_target(perceived.actor_id):
        return []
    character_perceived_input_service.apply_character_perceived_event(perceived)
    if _dialogue_cascade_depth(perceived) >= settings.character_dialogue_cascade_limit:
        character_agent_runtime.record_character_perceived_event_without_cognition(perceived)
        return []
    return character_agent_runtime.ingest_character_perceived_event(perceived)


def _dialogue_cascade_depth(perceived: CharacterPerceivedEvent) -> int:
    return len(perceived.source_ref_lineage)


def _first_speech_command_content(commands: list[CharacterGoalCommand]) -> str:
    for command in commands:
        if command.command_type != "speak":
            continue
        if command.dialogue_text:
            return command.dialogue_text
        payload = command.execution_payload or {}
        bundle = payload.get("action_request_bundle", {})
        if not isinstance(bundle, dict):
            continue
        requested_actions = bundle.get("requested_actions", [])
        if not isinstance(requested_actions, list):
            continue
        for action in requested_actions:
            if not isinstance(action, dict):
                continue
            if str(action.get("request_type", "") or "") not in _SPEECH_REQUEST_TYPES:
                continue
            content = str(action.get("content", "") or "")
            if content:
                return content
    return ""


def _as_envelope(message_type: str, payload: dict[str, object]) -> dict[str, object]:
    return {
        "message_type": message_type,
        "payload": payload,
    }


def _as_character_agent_execution_envelopes(commands: list[CharacterGoalCommand]) -> list[dict[str, object]]:
    envelopes: list[dict[str, object]] = []
    for command in commands:
        payload = dict(character_agent_l4_adapter.command_to_execution_payload(command))
        payload["actor_id"] = command.actor_id
        payload["producer_ts"] = command.producer_ts
        payload["causation_id"] = command.causation_id
        payload["correlation_id"] = command.correlation_id
        envelopes.append(
            {
                "message_type": "character_agent_execution",
                "payload": payload,
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
    candidates = compile_candidate_percepts(event)
    for candidate in candidates:
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
            if os.environ.get("SIMING_HEAVENLY_AUTOTEST_SETUP") == "1" and actor_id == "char_c":
                continue
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
            if os.environ.get("SIMING_HEAVENLY_AUTOTEST_SETUP") != "1":
                character_agent_runtime.run_scheduled_background_cognition_ticks(perceived.producer_ts)
            character_agent_messages.extend(
                _as_character_agent_suggestion_envelopes(
                    character_agent_runtime.drain_suggestion_packets(actor_id)
                )
            )
    return character_agent_messages


def _raw_fact_fast_authority_ack(envelope: Envelope) -> dict[str, object]:
    raw_payload = envelope.payload if isinstance(envelope.payload, dict) else {}
    event = RawFactEvent(**raw_payload)
    return build_raw_fact_authority_ack(event, source_type=envelope.message_type)


def _drop_matching_authority_ack(
    messages: list[dict[str, object]],
    authority_ack: dict[str, object],
) -> list[dict[str, object]]:
    if not messages:
        return messages
    first = messages[0]
    if first.get("message_type") == "ack" and _ack_payloads_match(first.get("payload", {}), authority_ack.get("payload", {})):
        return messages[1:]
    return messages


def _ack_payloads_match(first_payload: object, second_payload: object) -> bool:
    if not isinstance(first_payload, dict) or not isinstance(second_payload, dict):
        return False
    keys = ("accepted", "source_type", "route", "fact_family", "fact_type", "relation_type", "fact_key")
    return all(first_payload.get(key) == second_payload.get(key) for key in keys)


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
    messages = _move_authority_events_to_tail(messages)
    _emit_debug_from_messages(messages)
    return messages


def _move_authority_events_to_tail(messages: list[dict[str, object]]) -> list[dict[str, object]]:
    authority_events = [message for message in messages if message.get("message_type") == "authority_event"]
    if not authority_events:
        return messages
    non_authority_events = [message for message in messages if message.get("message_type") != "authority_event"]
    return non_authority_events + authority_events


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
    if os.environ.get("SIMING_HEAVENLY_AUTOTEST_SETUP") == "1":
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
