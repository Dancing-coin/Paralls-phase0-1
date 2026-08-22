from app.models.authority_event import AuthorityEvent
import pytest

from app.models.siming_event import InterventionCandidate, SimingOutput, SimingTickResult
from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.planning.l3_planner import CharacterAgentL3Service
from app.character_agent.reasoning.l2_reasoner import CharacterAgentL2Service
from app.services.authority_event_bus import (
    AuthorityRecoveryLedger,
    InMemoryAuthorityEventBus,
)
from app.services.character_agent_runtime import CharacterAgentRuntime
from app.services.siming_audit_writer import SimingAuditWriter
from app.services.siming_character_dispatch_adapter import SimingCharacterDispatchAdapter
from app.services.siming_event_consumer import SimingEventConsumer
from app.services.siming_event_pipeline import SimingEventPipeline
from app.services.siming_event_producer import SimingEventProducer
from app.services.frontend_authority_event_projection import FrontendAuthorityEventProjector
from app.services.siming_llm_provider import FakeSimingLlmCandidateProvider
from app.services.siming_runtime import SimingRuntime
from app.world_runtime.intelligence_upgrade import SampleInputRef
from app.world_runtime.l1_perception_frame import L1PerceptionFrameService


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

    assert dispatched.routing.target_ids == ["char_b", "frontend_projector"]
    assert dispatched.correlation_id == "visual_fact:300"
    assert snapshot is not None
    assert snapshot.last_siming_catalyst == "surface established fact"
    assert any(entry["event_type"] == "siming_output_event" for entry in timeline)


class _GraphDispatchRuntime:
    def __init__(self) -> None:
        self.journal: list[str] = []

    def record_authority_outcome(self, event: AuthorityEvent) -> None:
        self.journal.append(f"authority:{event.event_id}")

    def tick(self, inputs: list[object]) -> SimingTickResult:
        self.journal.append("tick")
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
                    payload={"target_actor_id": "char_b"},
                )
            ]
        )

    def ensure_dispatches_unpublished(
        self, event: AuthorityEvent, outputs: list[SimingOutput]
    ) -> None:
        assert [output.output_type for output in outputs] == ["dispatch_intent"]
        self.journal.append(f"preflight:{event.correlation_id}")

    def record_published_dispatches(
        self, event: AuthorityEvent, dispatch_events: list[AuthorityEvent]
    ) -> None:
        assert event.correlation_id == "visual_fact:300"
        self.journal.extend(
            f"dispatch:{dispatch_event.event_id}" for dispatch_event in dispatch_events
        )


def test_pipeline_records_authority_before_tick_and_actual_dispatch_after_publish() -> None:
    bus = InMemoryAuthorityEventBus()
    audit_writer = SimingAuditWriter()
    runtime = _GraphDispatchRuntime()
    pipeline = SimingEventPipeline(
        bus=bus,
        consumer=SimingEventConsumer(),
        runtime=runtime,  # type: ignore[arg-type]
        producer=SimingEventProducer(bus),
        audit_writer=audit_writer,
    )
    bus.subscribe("visual_fact_event", pipeline.handle_event)

    bus.publish(make_visual_fact_event())

    assert runtime.journal == [
        "authority:visual_fact:300:char_c:light_level_drop",
        "tick",
        "preflight:visual_fact:300",
        "dispatch:siming:dispatch_intent:304:visual_fact:300:char_c:light_level_drop",
    ]


class _CrashOnceAfterPublishProducer(SimingEventProducer):
    def __init__(self, bus: InMemoryAuthorityEventBus) -> None:
        super().__init__(bus)
        self._crash_once = True

    def publish_outputs(self, outputs: list[SimingOutput]) -> list[AuthorityEvent]:
        published = super().publish_outputs(outputs)
        self._raise_after_first_publish()
        return published

    def publish_events(self, events: list[AuthorityEvent]) -> list[AuthorityEvent]:
        published = super().publish_events(events)
        self._raise_after_first_publish()
        return published

    def _raise_after_first_publish(self) -> None:
        if self._crash_once:
            self._crash_once = False
            raise RuntimeError("simulated crash after broker publication")


class _PrepublicationLedgerRuntime:
    def __init__(self) -> None:
        self.sent_dispatch_ids: dict[str, str] = {}

    def tick(self, inputs: list[object]) -> SimingTickResult:
        event = inputs[0].source_event
        if event.correlation_id in self.sent_dispatch_ids:
            return SimingTickResult()
        return SimingTickResult(
            outputs=[
                SimingOutput(
                    output_type="dispatch_intent",
                    room_id=event.room_id,
                    scene_id=event.scene_id,
                    zone_id=event.zone_id,
                    causation_id=event.causation_id,
                    correlation_id=event.correlation_id,
                    producer_ts=event.producer_ts + 1,
                    selected_path="character_input_path",
                    intervention_band="fact_reveal",
                    payload={
                        "target_actor_id": "char_b",
                        "siming_graph_owned": True,
                    },
                )
            ]
        )

    def record_dispatches_unconfirmed(
        self, event: AuthorityEvent, dispatch_events: list[AuthorityEvent]
    ) -> None:
        assert len(dispatch_events) == 1
        dispatch_event = dispatch_events[0]
        assert dispatch_event.correlation_id == event.correlation_id
        self.sent_dispatch_ids.setdefault(event.correlation_id, dispatch_event.event_id)


class _AuthorityUnknownDispatchRuntime:
    def __init__(self) -> None:
        self.tick_calls = 0

    def reconcile_pending_dispatch(
        self,
        event: AuthorityEvent,
        *,
        authority_ledger: AuthorityRecoveryLedger | None,
    ) -> str:
        assert event.correlation_id == "visual_fact:300"
        assert authority_ledger is None
        return "authority_unknown"

    def tick(self, inputs: list[object]) -> SimingTickResult:
        self.tick_calls += 1
        return SimingTickResult()


class _UnavailableAuthorityLedgerBus(InMemoryAuthorityEventBus):
    def authority_recovery_ledger(self) -> AuthorityRecoveryLedger:
        raise RuntimeError("authority ledger unavailable")


class _LedgerArgumentsRuntime:
    def __init__(self) -> None:
        self.authority_ledger: AuthorityRecoveryLedger | None = None

    def reconcile_pending_dispatch(
        self,
        event: AuthorityEvent,
        *,
        authority_ledger: AuthorityRecoveryLedger | None,
    ) -> str:
        del event
        self.authority_ledger = authority_ledger
        return "not_pending"

    def tick(self, inputs: list[object]) -> SimingTickResult:
        del inputs
        return SimingTickResult()


def test_pipeline_persists_graph_dispatch_before_publish_crash_and_replay() -> None:
    bus = InMemoryAuthorityEventBus()
    runtime = _PrepublicationLedgerRuntime()
    pipeline = SimingEventPipeline(
        bus=bus,
        consumer=SimingEventConsumer(),
        runtime=runtime,  # type: ignore[arg-type]
        producer=_CrashOnceAfterPublishProducer(bus),
        audit_writer=SimingAuditWriter(),
    )
    event = make_visual_fact_event()

    with pytest.raises(RuntimeError, match="simulated crash"):
        pipeline.handle_event(event)

    pipeline.handle_event(event)

    dispatches = bus.list_events(event_type="siming.fact_reveal")
    assert len(dispatches) == 1
    assert runtime.sent_dispatch_ids == {event.correlation_id: dispatches[0].event_id}


def test_pipeline_audits_and_does_not_retry_when_authority_ledger_is_unavailable() -> None:
    bus = _UnavailableAuthorityLedgerBus()
    audit_writer = SimingAuditWriter()
    runtime = _AuthorityUnknownDispatchRuntime()
    pipeline = SimingEventPipeline(
        bus=bus,
        consumer=SimingEventConsumer(),
        runtime=runtime,  # type: ignore[arg-type]
        producer=SimingEventProducer(bus),
        audit_writer=audit_writer,
    )

    pipeline.handle_event(make_visual_fact_event())

    assert runtime.tick_calls == 0
    records = audit_writer.find_by_correlation(
        room_id="room_demo", correlation_id="visual_fact:300"
    )
    assert [(record.status, record.reason) for record in records] == [
        ("no_action", "dispatch_recovery_authority_unknown")
    ]


def test_pipeline_reconciles_against_expired_authority_ledger_events() -> None:
    bus = InMemoryAuthorityEventBus(now_ts_provider=lambda: 10_000)
    expired = make_visual_fact_event(
        event_id="siming:dispatch_intent:304:expired",
        event_type="siming.fact_reveal",
        producer_ts=1,
        ttl=1,
    )
    bus.publish(expired)
    runtime = _LedgerArgumentsRuntime()
    pipeline = SimingEventPipeline(
        bus=bus,
        consumer=SimingEventConsumer(),
        runtime=runtime,  # type: ignore[arg-type]
        producer=SimingEventProducer(bus),
        audit_writer=SimingAuditWriter(),
    )

    pipeline.handle_event(make_visual_fact_event())

    assert runtime.authority_ledger == AuthorityRecoveryLedger(
        event_ids=frozenset({expired.event_id}),
        is_complete_across_restart=False,
    )


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


def test_pipeline_records_multi_stage_checkpoints_for_runtime_tick() -> None:
    bus = InMemoryAuthorityEventBus()
    audit_writer = SimingAuditWriter()
    pipeline = make_pipeline(bus, audit_writer)
    bus.subscribe("visual_fact_event", pipeline.handle_event)

    bus.publish(make_visual_fact_event())

    checkpoint_types = {
        checkpoint.checkpoint_type for checkpoint in audit_writer.list_checkpoints(room_id="room_demo")
    }
    assert checkpoint_types == {"pre_decision", "post_decision", "post_dispatch"}
    assert "fairness_after" not in checkpoint_types


def test_pipeline_does_not_publish_internal_narrative_or_read_facade_events() -> None:
    bus = InMemoryAuthorityEventBus()
    audit_writer = SimingAuditWriter()
    pipeline = make_pipeline(bus, audit_writer)
    bus.subscribe("visual_fact_event", pipeline.handle_event)

    bus.publish(make_visual_fact_event())

    event_types = {event.event_type for event in bus.list_events(room_id="room_demo")}
    assert "siming.read_model" not in event_types
    assert "siming.checkpoint" not in event_types
    assert "siming.narrative_state" not in event_types
    assert "siming.intervention_seed" not in event_types


def test_pipeline_canonical_bundle_ingestion_records_read_model_without_decision_outputs() -> None:
    bus = InMemoryAuthorityEventBus()
    audit_writer = SimingAuditWriter()
    pipeline = make_pipeline(bus, audit_writer)
    frame_service = L1PerceptionFrameService()
    frame = frame_service.build_siming_frame(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        started_at=100,
        ended_at=150,
        environment_inputs=[
            SampleInputRef(provider_kind="spatial_patch", ref_id="runtime://space/zone_focus/global/150")
        ],
        structured_fact_refs=["raw_fact_event:spatial_access_fact:line_of_sight_blocked:150"],
    )
    bundle = frame_service.build_canonical_bundle(
        frame,
        local_spatial_state={"zone_id": "zone_focus"},
        target_state={"affected_actors": ["char_b"]},
        environment_state={"visibility_level": "reduced"},
    )

    result = pipeline.ingest_canonical_percept_bundle(bundle)

    assert result.read_model is not None
    assert audit_writer.list_read_models(room_id="room_demo")
    assert all(
        output.output_type not in {"intervention_candidate", "intervention_decision", "dispatch_intent"}
        for output in result.outputs
    )
    assert not any(event.event_type.startswith("siming.") for event in bus.list_events(room_id="room_demo"))


def test_frontend_projector_projects_inner_prompt_as_presentation_only() -> None:
    projector = FrontendAuthorityEventProjector()
    event = AuthorityEvent.model_validate(
        {
            "event_id": "siming:inner_prompt:1",
            "event_type": "siming.inner_prompt",
            "producer_ts": 101,
            "room_id": "room_demo",
            "scene_id": "scene_demo",
            "zone_id": "zone_focus",
            "source": {"layer": "L2", "system": "siming.dispatcher", "actor_id": None},
            "routing": {
                "audience_mode": "targeted",
                "routing_mode": "event_type",
                "target_ids": ["frontend_projector"],
            },
            "priority": "p1",
            "ttl": 5000,
            "durability": "realtime",
            "causation_id": "cause:1",
            "correlation_id": "corr:1",
            "payload": {
                "target_actor_id": "player",
                "prompt_text": "Something about the letter feels wrong.",
                "intensity": 0.2,
                "evidence_refs": ["public_fact:letter_seen"],
                "player_facing": True,
                "non_authoritative": True,
                "presentation_effects": ["narration_text"],
            },
        }
    )

    projected = projector.handle_event(event)

    assert projected is not None
    assert projected["type"] == "siming_inner_prompt"
    assert projected["target_actor_id"] == "player"
    assert projected["non_authoritative"] is True
    assert "backend_action_request" not in projected
    assert "world_mutation" not in projected
