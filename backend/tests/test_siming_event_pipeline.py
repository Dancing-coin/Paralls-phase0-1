from app.models.authority_event import AuthorityEvent
from app.models.siming_event import InterventionCandidate, SimingOutput, SimingTickResult
from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.planning.l3_planner import CharacterAgentL3Service
from app.character_agent.reasoning.l2_reasoner import CharacterAgentL2Service
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.character_agent_runtime import CharacterAgentRuntime
from app.services.siming_audit_writer import SimingAuditWriter
from app.services.siming_character_dispatch_adapter import SimingCharacterDispatchAdapter
from app.services.siming_event_consumer import SimingEventConsumer
from app.services.siming_event_pipeline import SimingEventPipeline
from app.services.siming_event_producer import SimingEventProducer
from app.services.siming_llm_provider import FakeSimingLlmCandidateProvider
from app.services.siming_runtime import SimingRuntime


class _LocalGateway:
    def __init__(self) -> None:
        self._gateway = CharacterModelGateway()

    def run_task(
        self,
        *,
        task_kind: str,
        context: dict[str, object],
        route_override: str | None = None,
    ) -> dict[str, object]:
        return self._gateway.run_task(
            task_kind=task_kind,
            context=context,
            route_override=route_override or "local_only",
        )

    def prepare_run_request(
        self,
        *,
        task_kind: str,
        context: dict[str, object],
        route_override: str | None = None,
    ) -> dict[str, object]:
        return self._gateway.prepare_run_request(
            task_kind=task_kind,
            context=context,
            route_override=route_override or "local_only",
        )


def _local_runtime() -> CharacterAgentRuntime:
    runtime = CharacterAgentRuntime()
    local_gateway = _LocalGateway()
    runtime._l2 = CharacterAgentL2Service(gateway=local_gateway, profile_registry=runtime._profile_registry)
    runtime._l3 = CharacterAgentL3Service(gateway=local_gateway)
    return runtime


def make_visual_fact_event(**overrides: object) -> AuthorityEvent:
    payload = {
        "event_id": "visual_fact:300:char_c:light_level_drop",
        "event_type": "visual_fact_event",
        "producer_ts": 300,
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "source": {"layer": "L1", "system": "visual_fact", "actor_id": "char_c"},
        "routing": {"audience_mode": "room", "routing_mode": "event_type", "target_ids": ["siming"]},
        "priority": "p2",
        "ttl": 5000,
        "durability": "replayable",
        "causation_id": "visual_fact:300",
        "correlation_id": "visual_fact:300",
        "payload": {
            "fact_type": "light_level_drop",
            "established_fact_id": "visual_fact:300:char_c:light_level_drop",
            "target_environment_id": "env_lamp",
        },
    }
    payload.update(overrides)
    return AuthorityEvent.model_validate(payload)


def make_conversation_resolution_event(**overrides: object) -> AuthorityEvent:
    payload = {
        "event_id": "conversation_candidate:456:char_c",
        "event_type": "conversation_resolution_event",
        "producer_ts": 456,
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "source": {"layer": "L2", "system": "conversation_relation", "actor_id": "char_c"},
        "routing": {"audience_mode": "room", "routing_mode": "event_type", "target_ids": ["siming"]},
        "priority": "p2",
        "ttl": 5000,
        "durability": "replayable",
        "causation_id": "interact:456",
        "correlation_id": "interact:456",
        "payload": {
            "actor_id": "char_c",
            "room_id": "room_demo",
            "scene_id": "scene_demo",
            "zone_id": "zone_focus",
            "producer_ts": 456,
            "candidate_ref": "cand_obj_letter",
            "candidate_actor_ids": [],
            "candidate_object_ids": ["obj_letter"],
            "candidate_environment_ids": [],
            "engagement_pressure": "present",
            "privacy_risk_hint": "low",
            "causation_id": "interact:456",
            "correlation_id": "interact:456",
        },
    }
    payload.update(overrides)
    return AuthorityEvent.model_validate(payload)


def make_pipeline(bus: InMemoryAuthorityEventBus, audit_writer: SimingAuditWriter) -> SimingEventPipeline:
    return SimingEventPipeline(
        bus=bus,
        consumer=SimingEventConsumer(),
        runtime=SimingRuntime(),
        producer=SimingEventProducer(bus),
        audit_writer=audit_writer,
    )


class FakeCharacterInputRuntime:
    def tick(self, _inputs: list[object]) -> SimingTickResult:
        return SimingTickResult(
            outputs=[
                SimingOutput(
                    output_type="dispatch_intent",
                    room_id="room_demo",
                    scene_id="scene_demo",
                    zone_id="zone_focus",
                    causation_id="visual_fact:300:char_c:light_level_drop",
                    correlation_id="visual_fact:300",
                    producer_ts=304,
                    selected_path="character_input_path",
                    intervention_band="fact_reveal",
                    payload={
                        "presentation_hint": "surface established fact",
                        "target_actor_id": "char_b",
                        "target_environment_id": "env_lamp",
                    },
                )
            ]
        )


def test_pipeline_publishes_visual_observability_event_from_visual_fact_input() -> None:
    bus = InMemoryAuthorityEventBus()
    audit_writer = SimingAuditWriter()
    pipeline = make_pipeline(bus, audit_writer)
    bus.subscribe("visual_fact_event", pipeline.handle_event)

    bus.publish(make_visual_fact_event())

    event_types = [event.event_type for event in bus.list_events(room_id="room_demo")]
    assert "visual_fact_event" in event_types
    assert "siming.visual_observability_request" in event_types
    projected = bus.list_events(event_type="siming.visual_observability_request")[0]
    observatory_messages = pipeline.drain_observatory_messages()
    message_types = [message["message_type"] for message in observatory_messages]
    stages = [
        message["payload"]["stage"]
        for message in observatory_messages
        if message["message_type"] == "siming_debug_event"
    ]

    assert projected.source.system == "siming.dispatcher"
    assert projected.causation_id == "visual_fact:300:char_c:light_level_drop"
    assert projected.payload["established_fact_id"] == "visual_fact:300:char_c:light_level_drop"
    assert audit_writer.find_by_correlation(room_id="room_demo", correlation_id="visual_fact:300")
    assert "siming_debug_snapshot" in message_types
    assert "fairness_snapshot" in stages
    assert "intervention_candidate" in stages
    assert "intervention_decision" in stages
    assert "dispatch_finalized" in stages


def test_pipeline_ignores_events_outside_siming_allowlist() -> None:
    bus = InMemoryAuthorityEventBus()
    audit_writer = SimingAuditWriter()
    pipeline = make_pipeline(bus, audit_writer)
    bus.subscribe("presentation_event", pipeline.handle_event)

    bus.publish(make_visual_fact_event(event_id="presentation:1", event_type="presentation_event"))

    assert [event.event_type for event in bus.list_events()] == ["presentation_event"]
    assert audit_writer.find_by_correlation(room_id="room_demo", correlation_id="visual_fact:300") == []
    assert pipeline.drain_observatory_messages() == []


def test_pipeline_publishes_llm_assisted_output_only_through_siming_event_producer() -> None:
    bus = InMemoryAuthorityEventBus()
    audit_writer = SimingAuditWriter()
    candidate = InterventionCandidate(
        candidate_id="cand:llm:1",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="visual_fact:300:char_c:light_level_drop",
        correlation_id="visual_fact:300",
        proposed_band="fact_reveal",
        target_actor_id="char_b",
        target_environment_id="env_lamp",
        established_fact_ids=["visual_fact:300:char_c:light_level_drop"],
        source="llm",
    )
    pipeline = SimingEventPipeline(
        bus=bus,
        consumer=SimingEventConsumer(),
        runtime=SimingRuntime(llm_provider=FakeSimingLlmCandidateProvider([candidate])),
        producer=SimingEventProducer(bus),
        audit_writer=audit_writer,
    )
    bus.subscribe("visual_fact_event", pipeline.handle_event)

    bus.publish(make_visual_fact_event())

    event_types = [event.event_type for event in bus.list_events(room_id="room_demo")]
    assert "siming.intervention_candidate" in event_types
    assert "siming.intervention_decision" in event_types
    assert "siming.visual_observability_request" in event_types
    assert "siming.dispatch_requested" not in event_types
    projected = bus.list_events(event_type="siming.visual_observability_request")[0]
    assert projected.source.system == "siming.dispatcher"
    assert projected.causation_id == "visual_fact:300:char_c:light_level_drop"
    assert projected.correlation_id == "visual_fact:300"
    assert projected.payload["established_fact_id"] == "visual_fact:300:char_c:light_level_drop"
    assert projected.payload["target_environment_id"] == "env_lamp"
    assert projected.payload["target_actor_id"] == "char_b"


def test_pipeline_dispatches_new_character_input_outputs_through_adapter() -> None:
    bus = InMemoryAuthorityEventBus()
    audit_writer = SimingAuditWriter()
    character_runtime = _local_runtime()
    pipeline = SimingEventPipeline(
        bus=bus,
        consumer=SimingEventConsumer(),
        runtime=FakeCharacterInputRuntime(),
        producer=SimingEventProducer(bus),
        audit_writer=audit_writer,
        character_dispatch_adapter=SimingCharacterDispatchAdapter(runtime=character_runtime),
    )
    bus.subscribe("visual_fact_event", pipeline.handle_event)

    bus.publish(make_visual_fact_event())

    dispatched = bus.list_events(event_type="siming.fact_reveal")[0]
    snapshot = character_runtime.get_private_snapshot("char_b")
    timeline = character_runtime.get_session_timeline("char_b")

    assert dispatched.routing.target_ids == ["char_b"]
    assert dispatched.correlation_id == "visual_fact:300"
    assert snapshot is not None
    assert snapshot.last_siming_catalyst == "surface established fact"
    assert any(entry["event_type"] == "siming_output_event" for entry in timeline)


def test_pipeline_does_not_dispatch_visual_observability_outputs_through_adapter() -> None:
    bus = InMemoryAuthorityEventBus()
    audit_writer = SimingAuditWriter()
    character_runtime = _local_runtime()
    pipeline = SimingEventPipeline(
        bus=bus,
        consumer=SimingEventConsumer(),
        runtime=SimingRuntime(),
        producer=SimingEventProducer(bus),
        audit_writer=audit_writer,
        character_dispatch_adapter=SimingCharacterDispatchAdapter(runtime=character_runtime),
    )
    bus.subscribe("visual_fact_event", pipeline.handle_event)

    bus.publish(make_visual_fact_event())

    assert bus.list_events(event_type="siming.visual_observability_request")
    assert character_runtime.get_private_snapshot("char_b") is None


def test_pipeline_routes_object_only_conversation_fact_reveal_to_visual_observability() -> None:
    bus = InMemoryAuthorityEventBus()
    audit_writer = SimingAuditWriter()
    character_runtime = _local_runtime()
    pipeline = SimingEventPipeline(
        bus=bus,
        consumer=SimingEventConsumer(),
        runtime=SimingRuntime(),
        producer=SimingEventProducer(bus),
        audit_writer=audit_writer,
        character_dispatch_adapter=SimingCharacterDispatchAdapter(runtime=character_runtime),
    )
    bus.subscribe("conversation_resolution_event", pipeline.handle_event)

    bus.publish(make_conversation_resolution_event())

    event_types = [event.event_type for event in bus.list_events(room_id="room_demo")]
    projected = bus.list_events(event_type="siming.visual_observability_request")[0]

    assert "siming.fact_reveal" not in event_types
    assert "siming.visual_observability_request" in event_types
    assert projected.payload["target_object_id"] == "obj_letter"
    assert character_runtime.get_private_snapshot("char_b") is None


def test_pipeline_records_llm_timeout_audit() -> None:
    bus = InMemoryAuthorityEventBus()
    audit_writer = SimingAuditWriter()
    pipeline = SimingEventPipeline(
        bus=bus,
        consumer=SimingEventConsumer(),
        runtime=SimingRuntime(llm_provider=FakeSimingLlmCandidateProvider([], timeout=True)),
        producer=SimingEventProducer(bus),
        audit_writer=audit_writer,
    )
    bus.subscribe("visual_fact_event", pipeline.handle_event)

    bus.publish(make_visual_fact_event())

    records = audit_writer.find_by_correlation(room_id="room_demo", correlation_id="visual_fact:300")
    assert any(record.status == "llm_timeout" for record in records)


def test_pipeline_records_policy_rejection_audit() -> None:
    bus = InMemoryAuthorityEventBus()
    audit_writer = SimingAuditWriter()
    candidate = InterventionCandidate(
        candidate_id="cand:unsafe",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="visual_fact:300:char_c:light_level_drop",
        correlation_id="visual_fact:300",
        proposed_band="fact_reveal",
        target_actor_id="char_b",
        established_fact_ids=["visual_fact:unknown"],
        source="llm",
    )
    pipeline = SimingEventPipeline(
        bus=bus,
        consumer=SimingEventConsumer(),
        runtime=SimingRuntime(llm_provider=FakeSimingLlmCandidateProvider([candidate])),
        producer=SimingEventProducer(bus),
        audit_writer=audit_writer,
    )
    bus.subscribe("visual_fact_event", pipeline.handle_event)

    bus.publish(make_visual_fact_event())

    records = audit_writer.find_by_correlation(room_id="room_demo", correlation_id="visual_fact:300")
    assert any(record.status == "policy_rejected" for record in records)


def test_pipeline_preserves_no_action_audit_when_no_candidate_or_rule_applies() -> None:
    bus = InMemoryAuthorityEventBus()
    audit_writer = SimingAuditWriter()
    pipeline = make_pipeline(bus, audit_writer)
    bus.subscribe("world_fact_event", pipeline.handle_event)

    bus.publish(
        make_visual_fact_event(
            event_id="world:1",
            event_type="world_fact_event",
            payload={"fact_type": "unrelated"},
        )
    )

    records = audit_writer.find_by_correlation(room_id="room_demo", correlation_id="visual_fact:300")
    assert any(record.status == "no_action" for record in records)


def test_pipeline_records_checkpoint_and_read_model_for_runtime_tick() -> None:
    bus = InMemoryAuthorityEventBus()
    audit_writer = SimingAuditWriter()
    pipeline = make_pipeline(bus, audit_writer)
    bus.subscribe("visual_fact_event", pipeline.handle_event)

    bus.publish(make_visual_fact_event())

    checkpoints = audit_writer.list_checkpoints(room_id="room_demo")
    read_models = audit_writer.list_read_models(room_id="room_demo")
    assert checkpoints
    assert checkpoints[0].fairness_snapshot_ref is not None
    assert checkpoints[0].fairness_snapshot_ref.startswith("fairness:")
    assert read_models
    assert read_models[0].derived_from_snapshot_ref is not None
    assert read_models[0].derived_from_snapshot_ref.startswith("fairness:")
    event_types = [event.event_type for event in bus.list_events(room_id="room_demo")]
    assert "siming.read_model" not in event_types
    assert "siming.checkpoint" not in event_types
