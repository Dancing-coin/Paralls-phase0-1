from app.models.feasibility_response import FeasibilityResponse
from app.services.siming_proposal_tracker import SimingProposalTracker
import pytest

from app.models.siming_event import SimingInput
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.siming_event_producer import SimingEventProducer
from app.services.siming_runtime import SimingRuntime
from test_siming_event_producer import make_output


def response(proposal_ref="p", feasible=True):
    return FeasibilityResponse(response_id="f", proposal_ref=proposal_ref, feasible=feasible,
        constraints=[] if feasible else ["unsupported_change_type"], producer_ts=1,
        causation_id="p", correlation_id="corr")


def test_tracker_accepts_once_and_isolates_proposals():
    tracker = SimingProposalTracker()
    tracker.register_proposal("p", "first", 100)
    tracker.register_proposal("q", "second", 100)
    assert tracker.accept_response(response(), 101) == "first"
    assert tracker.accept_response(response(), 102) is None
    assert tracker.accept_response(response("q", False), 101) is None
    assert tracker.status("q") == "aborted"


def test_tracker_rejects_expired_and_cleans_old_records():
    tracker = SimingProposalTracker()
    tracker.register_proposal("p", "first", 100)
    assert tracker.accept_response(response(), 5101) is None
    assert tracker.status("p") == "aborted"
    tracker.cleanup_old_proposals(60101)
    assert tracker.status("p") is None


def prepare():
    clock = [100]
    runtime = SimingRuntime()
    runtime.proposal_tracker = SimingProposalTracker(now_ts_provider=lambda: clock[0])
    bus = InMemoryAuthorityEventBus()
    producer = SimingEventProducer(bus, proposal_tracker=runtime.proposal_tracker)
    event = producer.emit_environment_proposal(make_output())
    return clock, runtime, producer, event


def answer(event, **updates):
    payload = dict(response_id="f", proposal_ref=event.payload["proposal_id"], feasible=True,
        constraints=[], estimated_effect={"light_level": "low"}, alternative_suggestions=[],
        producer_ts=event.producer_ts + 1, causation_id=event.payload["proposal_id"], correlation_id=event.correlation_id)
    payload.update(updates)
    return event.model_copy(update={"event_id": "response:1", "event_type": "esm.feasibility_response",
        "causation_id": event.payload["proposal_id"], "producer_ts": payload["producer_ts"],
        "source": event.source.model_copy(update={"layer": "L1", "system": "esm"}),
        "routing": event.routing.model_copy(update={"target_ids": ["siming"]}), "payload": payload})


def test_feasible_response_reenters_tick_and_emits_formal_request_once():
    _, runtime, producer, event = prepare()
    incoming = SimingInput(input_type="esm.feasibility_response", source_event=answer(event))
    result = runtime.tick([incoming])
    request = producer.materialize_outputs(result.outputs)[0]
    assert request.event_type == "siming.environment_request"
    assert request.payload["proposal_ref"] == event.payload["proposal_id"]
    assert request.payload["feasibility_ref"] == "f"
    assert not runtime.tick([incoming]).outputs


@pytest.mark.parametrize("field,value", [("feasible", False), ("correlation_id", "other"),
    ("proposal_ref", "other"), ("causation_id", "other"), ("estimated_effect", {}), ("constraints", ["blocked"])])
def test_unusable_or_unrelated_response_cannot_dispatch(field, value):
    _, runtime, _, event = prepare()
    result = runtime.tick([SimingInput(input_type="esm.feasibility_response", source_event=answer(event, **{field: value}))])
    assert not result.outputs


@pytest.mark.parametrize("elapsed", [5000, 5001, 10000])
def test_late_response_aborts_without_request(elapsed):
    clock, runtime, _, event = prepare()
    clock[0] += elapsed
    result = runtime.tick([SimingInput(input_type="esm.feasibility_response", source_event=answer(event))])
    assert not result.outputs
    assert runtime.proposal_tracker.status(event.payload["proposal_id"]) == "aborted"


def test_invalid_esm_source_cannot_dispatch():
    _, runtime, _, event = prepare()
    incoming = answer(event)
    incoming.source.system = "character"
    assert not runtime.tick([SimingInput(input_type="esm.feasibility_response", source_event=incoming)]).outputs


def test_pending_proposal_expires_without_response():
    clock, runtime, _, event = prepare()
    clock[0] += 5001
    runtime.proposal_tracker.cleanup_old_proposals()
    assert runtime.proposal_tracker.status(event.payload["proposal_id"]) == "aborted"
