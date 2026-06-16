from pathlib import Path

import app.main as main
from app.models.authority_event import AuthorityEvent
from app.models.siming_event import InterventionCandidate
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.siming_audit_writer import SimingAuditWriter
from app.services.siming_event_consumer import SimingEventConsumer
from app.services.siming_event_pipeline import SimingEventPipeline
from app.services.siming_event_producer import SimingEventProducer
from app.services.siming_llm_provider import FakeSimingLlmCandidateProvider
from app.services.siming_runtime import SimingRuntime
from app.ws_protocol import Envelope


def _messages_of_type(messages: list[dict[str, object]], message_type: str) -> list[dict[str, object]]:
    return [message for message in messages if message.get("message_type") == message_type]


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


def test_visual_fact_siming_output_is_projected_from_authority_event() -> None:
    main.reset_runtime_state()

    outbound = main._handle_envelope(
        Envelope(
            message_type="visual_fact_event",
            payload={
                "actor_id": "char_c",
                "room_id": "room_demo",
                "scene_id": "scene_demo",
                "zone_id": "zone_focus",
                "producer_ts": 151,
                "fact_type": "light_level_drop",
                "relation_type": "environment_light_drop",
                "target_environment_id": "env_lamp",
            },
        )
    )

    siming_outputs = _messages_of_type(outbound, "siming_output")
    visual_output = next(
        output
        for output in siming_outputs
        if output["payload"]["authority_event_type"] == "siming.visual_observability_request"  # type: ignore[index]
    )
    authority_event_id = visual_output["payload"]["authority_event_id"]  # type: ignore[index]
    bus_events = main.authority_event_bus.list_events(room_id="room_demo")
    bus_event_by_id = {event.event_id: event for event in bus_events}

    assert "visual_fact:151:char_c:light_level_drop" in bus_event_by_id
    assert authority_event_id in bus_event_by_id
    projected_event = bus_event_by_id[authority_event_id]
    assert projected_event.event_type == "siming.visual_observability_request"
    assert projected_event.source.system == "siming.dispatcher"
    assert visual_output["payload"]["target_environment_id"] == projected_event.payload["target_environment_id"]  # type: ignore[index]
    assert visual_output["payload"]["causation_id"] == projected_event.causation_id  # type: ignore[index]
    assert visual_output["payload"]["correlation_id"] == projected_event.correlation_id  # type: ignore[index]


def test_interact_success_siming_outputs_are_projected_from_authority_bus() -> None:
    main.reset_runtime_state()

    outbound = main._handle_envelope(
        Envelope(
            message_type="player_input",
            payload={
                "player_id": "p1",
                "room_id": "room_demo",
                "actor_id": "char_c",
                "intent_type": "interact_intent",
                "producer_ts": 456,
                "target_object_id": "obj_letter",
                "interaction_type": "inspect",
            },
        )
    )

    siming_outputs = _messages_of_type(outbound, "siming_output")
    bus_events = main.authority_event_bus.list_events(room_id="room_demo")
    bus_event_by_id = {event.event_id: event for event in bus_events}

    assert {event.event_type for event in bus_events} >= {"esm_result_event", "conversation_resolution_event", "siming.fact_reveal"}
    assert siming_outputs
    for output in siming_outputs:
        payload = output["payload"]
        authority_event_id = payload["authority_event_id"]  # type: ignore[index]
        assert authority_event_id in bus_event_by_id
        authority_event = bus_event_by_id[authority_event_id]
        assert payload["authority_event_type"] == authority_event.event_type  # type: ignore[index]
        assert payload["causation_id"] == authority_event.causation_id  # type: ignore[index]
        assert payload["correlation_id"] == authority_event.correlation_id  # type: ignore[index]


def test_llm_assisted_siming_output_preserves_authority_causation_chain() -> None:
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
        explanation="LLM provenance marker",
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

    source_event = make_visual_fact_event()
    bus.publish(source_event)

    llm_candidate = bus.list_events(event_type="siming.intervention_candidate")[0]
    llm_decision = bus.list_events(event_type="siming.intervention_decision")[0]
    projected = bus.list_events(event_type="siming.visual_observability_request")[0]

    assert llm_candidate.payload["candidate_id"] == "cand:llm:1"
    assert llm_candidate.payload["source"] == "llm"
    assert llm_decision.payload["candidate_id"] == "cand:llm:1"
    assert projected.event_id.startswith("siming:")
    assert projected.causation_id == source_event.event_id
    assert projected.correlation_id == source_event.correlation_id
    assert projected.payload["presentation_hint"] == "LLM provenance marker"
    records = audit_writer.find_by_correlation(room_id="room_demo", correlation_id="visual_fact:300")
    assert any(record.status == "recorded" for record in records)


def test_runtime_mainline_does_not_call_legacy_siming_service() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    runtime_sources = [
        backend_root / "app" / "main.py",
        backend_root / "app" / "services" / "fact_handlers" / "visual_fact_handler.py",
    ]

    forbidden_tokens = [
        "SimingService",
        "siming_service",
        "evaluate_world_event",
        "evaluate_candidate_relationship",
        "evaluate_visual_fact",
        "context.siming_service",
    ]
    combined_source = "\n".join(path.read_text(encoding="utf-8") for path in runtime_sources)

    for token in forbidden_tokens:
        assert token not in combined_source
