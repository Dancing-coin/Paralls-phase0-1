from types import SimpleNamespace

import pytest

from app import main
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.esm_service import ESMService
from app.services.phase0_authority_event_adapter import Phase0AuthorityEventAdapter
from app.services.siming_audit_writer import SimingAuditWriter
from app.services.siming_event_consumer import SimingEventConsumer
from app.services.siming_event_pipeline import SimingEventPipeline
from app.services.siming_event_producer import SimingEventProducer
from app.services.siming_runtime import SimingRuntime
from test_siming_event_producer import make_output


@pytest.fixture
def protocol(monkeypatch):
    bus, esm, runtime = InMemoryAuthorityEventBus(), ESMService(), SimingRuntime()
    esm.register_environment_target("room_demo", "scene_demo", "zone_focus", "env_lamp")
    producer = SimingEventProducer(bus)
    pipeline = SimingEventPipeline(bus=bus, consumer=SimingEventConsumer(), runtime=runtime,
        producer=producer, audit_writer=SimingAuditWriter())
    applied = []
    monkeypatch.setattr(main, "authority_event_bus", bus, raising=False)
    monkeypatch.setattr(main, "esm_service", esm, raising=False)
    monkeypatch.setattr(main, "siming_event_pipeline", pipeline, raising=False)
    monkeypatch.setattr(main, "l1_occupancy_service", SimpleNamespace(apply_environment_result=applied.append), raising=False)
    def publish(result, *, source_event, **kwargs):
        bus.publish(Phase0AuthorityEventAdapter().world_result_event(result, source_event=source_event))
    monkeypatch.setattr(main, "_publish_world_result_authority_event", publish)
    main._subscribe_siming_environment_protocol()
    return SimpleNamespace(bus=bus, esm=esm, runtime=runtime, producer=producer, applied=applied)


def test_complete_proposal_response_request_confirmation_result_flow(protocol):
    p = protocol
    event = p.producer.emit_environment_proposal(make_output())
    assert [e.event_type for e in p.bus.list_events()] == [
        "siming.environment_proposal", "esm.feasibility_response", "siming.environment_request",
        "esm.execution_confirmation", "esm_result_event", "esm_result_event",
    ]
    assert len(p.applied) == 1
    assert p.runtime.proposal_tracker.status(event.payload["proposal_id"]) == "executed"


@pytest.mark.parametrize("payload, expected_constraint", [
    ({"requested_change_type": "unsupported"}, None),
    ({"target_environment_id": "missing"}, "unknown_environment_target"),
])
def test_unsupported_change_and_unknown_target_abort_at_their_own_stage(protocol, payload, expected_constraint):
    p = protocol
    event = p.producer.emit_environment_proposal(make_output(payload={"target_environment_id": "env_lamp", **payload}))
    requests = p.bus.list_events(event_type="siming.environment_request")
    confirmations = p.bus.list_events(event_type="esm.execution_confirmation")
    if expected_constraint is None:
        assert not requests
        assert not confirmations
    else:
        assert len(requests) == len(confirmations) == 1
        assert confirmations[0].payload["execution_state"] == "aborted"
        constraints = p.bus.list_events(event_type="constraint_state_event")
        assert [event.payload["constraint_code"] for event in constraints] == [expected_constraint]
    assert not p.applied
    assert p.runtime.proposal_tracker.status(event.payload["proposal_id"]) == "aborted"


def test_replayed_response_and_request_do_not_repeat_execution(protocol):
    p = protocol
    p.producer.emit_environment_proposal(make_output())
    p.bus.publish(p.bus.list_events(event_type="esm.feasibility_response")[0])
    p.bus.publish(p.bus.list_events(event_type="siming.environment_request")[0])
    assert len(p.applied) == 1


def test_multiple_proposals_keep_distinct_identity(protocol):
    p = protocol
    for index in range(20):
        p.producer.emit_environment_proposal(make_output(causation_id=f"cause:{index}"))
    assert len(p.applied) == 20
    assert len({e.payload["proposal_id"] for e in p.bus.list_events(event_type="siming.environment_proposal")}) == 20


def test_one_hundred_concurrent_proposals_do_not_interfere(protocol):
    from concurrent.futures import ThreadPoolExecutor
    p = protocol
    with ThreadPoolExecutor(max_workers=8) as pool:
        events = list(pool.map(lambda index: p.producer.emit_environment_proposal(
            make_output(causation_id=f"parallel:{index}")), range(100)))
    assert len(p.applied) == 100
    assert all(p.runtime.proposal_tracker.status(event.payload["proposal_id"]) == "executed" for event in events)


def test_constraint_probe_returns_scoped_state_without_execution(protocol):
    p = protocol
    event = p.producer._to_authority_event(make_output()).model_copy(update={"event_type": "siming.constraint_probe",
        "payload": dict(probe_id="probe:1", target_environment_id="env_lamp", constraint_type="all",
            producer_ts=304, causation_id="visual_fact:300", correlation_id="visual_fact:300")})
    p.bus.publish(event)
    state = p.bus.list_events(event_type="esm.constraint_state")[0]
    assert state.payload["active_constraints"]["cooldown"]["remaining"] == 0
    assert not p.applied
    assert p.esm._latest_environment_request is None


@pytest.mark.parametrize("kind", ["bad_payload", "bad_source", "bad_scope"])
def test_malformed_proposal_is_rejected_and_logged(protocol, caplog, kind):
    p = protocol
    event = p.producer._proposal_event(make_output())
    if kind == "bad_payload":
        event.payload["requested_strength"] = "infinite"
    elif kind == "bad_source":
        event.source.system = "character"
    else:
        event.payload["room_id"] = "other"
    p.bus.publish(event)
    assert not p.bus.list_events(event_type="esm.feasibility_response")
    assert "protocol_09_rejected" in caplog.text
    assert not p.applied


def test_execution_rechecks_state_after_feasibility(protocol, monkeypatch):
    p = protocol
    original = p.esm.evaluate_proposal
    def evaluate(proposal):
        response = original(proposal)
        p.esm.register_environment_target(proposal.room_id, proposal.scene_id, proposal.zone_id,
            proposal.target_environment_id, spatial_allowed=False)
        return response
    monkeypatch.setattr(p.esm, "evaluate_proposal", evaluate)
    event = p.producer.emit_environment_proposal(make_output())
    assert not p.applied
    assert p.bus.list_events(event_type="esm.execution_confirmation")[0].payload["execution_state"] == "aborted"
    assert p.runtime.proposal_tracker.status(event.payload["proposal_id"]) == "aborted"
