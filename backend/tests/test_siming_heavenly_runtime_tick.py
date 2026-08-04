from app.models.authority_event import (
    AuthorityEvent,
    AuthorityEventRouting,
    AuthorityEventSource,
)
from app.models.siming_event import SimingOutput
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.siming_event_consumer import SimingEventConsumer
from app.services.siming_event_producer import SimingEventProducer


def _event(event_type: str, *, payload: dict[str, object]) -> AuthorityEvent:
    return AuthorityEvent(
        event_id=f"event:{event_type}",
        event_type=event_type,
        producer_ts=100,
        room_id="room:main",
        scene_id="scene:throne",
        zone_id="zone:archive",
        source=AuthorityEventSource(layer="L2", system="test"),
        routing=AuthorityEventRouting(
            audience_mode="targeted", routing_mode="event_type"
        ),
        priority="p2",
        durability="replayable",
        causation_id="cause:1",
        correlation_id="corr:destroy:1",
        payload=payload,
    )


def test_consumer_admits_structured_staging_ack() -> None:
    inputs = SimingEventConsumer().handle_event(
        _event(
            "siming_staging_ack",
            payload={
                "source": "character",
                "correlation_id": "corr:destroy:1",
                "accepted": True,
            },
        )
    )

    assert len(inputs) == 1
    assert inputs[0].input_type == "siming_staging_ack"


def test_producer_publishes_staging_request_as_non_catalyst_event() -> None:
    bus = InMemoryAuthorityEventBus()
    event = SimingEventProducer(bus).publish_outputs(
        [
            SimingOutput(
                output_type="staging_request",
                room_id="room:main",
                scene_id="scene:throne",
                zone_id="zone:archive",
                causation_id="event:destroy",
                correlation_id="corr:destroy:1",
                producer_ts=101,
                payload={"node_id": "runtime:bridge:proposal:destroy:1"},
            )
        ]
    )

    assert [item.event_type for item in event] == ["siming.staging_request"]
