from app.models.authority_event import AuthorityEvent
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.siming_audit_writer import SimingAuditWriter
from app.services.siming_event_consumer import SimingEventConsumer
from app.services.siming_event_pipeline import SimingEventPipeline
from app.services.siming_event_producer import SimingEventProducer
from app.services.siming_runtime import SimingRuntime


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


def make_pipeline(bus: InMemoryAuthorityEventBus, audit_writer: SimingAuditWriter) -> SimingEventPipeline:
    return SimingEventPipeline(
        bus=bus,
        consumer=SimingEventConsumer(),
        runtime=SimingRuntime(),
        producer=SimingEventProducer(bus),
        audit_writer=audit_writer,
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
