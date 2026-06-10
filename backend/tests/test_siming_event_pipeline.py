from app.models.authority_event import AuthorityEvent
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.siming_audit_writer import SimingAuditWriter
from app.services.siming_event_consumer import SimingEventConsumer
from app.services.siming_event_pipeline import SimingEventPipeline
from app.services.siming_event_producer import SimingEventProducer
from app.services.siming_runtime import SimingRuntime

from tests.test_authority_event import valid_event_dict


def build_pipeline() -> tuple[InMemoryAuthorityEventBus, SimingAuditWriter, SimingEventPipeline]:
    bus = InMemoryAuthorityEventBus()
    audit_writer = SimingAuditWriter()
    pipeline = SimingEventPipeline(
        bus=bus,
        consumer=SimingEventConsumer(),
        runtime=SimingRuntime(),
        producer=SimingEventProducer(bus),
        audit_writer=audit_writer,
    )
    return bus, audit_writer, pipeline


def make_event(event_type: str, payload_override: dict[str, object] | None = None) -> AuthorityEvent:
    payload = valid_event_dict()
    payload["event_type"] = event_type
    if payload_override is not None:
        payload["payload"] = payload_override
    return AuthorityEvent.model_validate(payload)


def test_pipeline_publishes_siming_outputs_and_records_audit() -> None:
    bus, audit_writer, pipeline = build_pipeline()

    pipeline.handle_event(make_event("visual_fact_event"))

    event_types = [event.event_type for event in bus.list_events()]
    assert "siming.fairness_snapshot" in event_types
    assert "siming.visual_observability_request" in event_types
    assert audit_writer.find_by_correlation(room_id="room_demo", correlation_id="visual_fact:100")[0].status == "recorded"


def test_pipeline_records_esm_rejection_closed_loop() -> None:
    _bus, audit_writer, pipeline = build_pipeline()
    event = make_event(
        "constraint_state_event",
        {
            "result_type": "constraint_state_result",
            "constraint_type": "distance",
            "constraint_summary": "target is too far away",
        },
    )

    pipeline.handle_event(event)

    audit = audit_writer.find_by_correlation(room_id="room_demo", correlation_id="visual_fact:100")[0]
    assert audit.status == "esm_rejected"
    assert audit.reason == "target is too far away"
