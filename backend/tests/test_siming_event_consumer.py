from app.models.authority_event import AuthorityEvent
from app.services.siming_event_consumer import SimingEventConsumer

from tests.test_authority_event import valid_event_dict


def make_event(event_type: str) -> AuthorityEvent:
    payload = valid_event_dict()
    payload["event_type"] = event_type
    return AuthorityEvent.model_validate(payload)


def test_consumer_accepts_visual_fact_event() -> None:
    consumer = SimingEventConsumer()

    result = consumer.handle_event(make_event("visual_fact_event"))

    assert len(result) == 1
    assert result[0].input_type == "visual_fact_event"
    assert result[0].source_event.event_type == "visual_fact_event"


def test_consumer_accepts_esm_result_event() -> None:
    consumer = SimingEventConsumer()

    result = consumer.handle_event(make_event("esm_result_event"))

    assert len(result) == 1
    assert result[0].input_type == "esm_result_event"


def test_consumer_ignores_unqualified_event_family() -> None:
    consumer = SimingEventConsumer()

    assert consumer.handle_event(make_event("player_input")) == []
    assert consumer.handle_event(make_event("siming.fairness_snapshot")) == []
