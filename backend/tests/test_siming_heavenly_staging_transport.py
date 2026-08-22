import pytest

from app import main
from app.models.authority_event import AuthorityEvent, AuthorityEventRouting, AuthorityEventSource
from app.models.character_agent_runtime import CharacterGoalCommand
from app.services.siming_character_dispatch_adapter import SimingCharacterDispatchResult
from app.ws_protocol import Envelope


def test_godot_staging_ack_is_published_as_authority_event() -> None:
    main.reset_runtime_state()

    messages = main._handle_envelope(
        Envelope(
            message_type="siming_staging_ack",
            payload={
                "room_id": "room_demo",
                "scene_id": "scene_demo",
                "zone_id": "zone_focus",
                "producer_ts": 500,
                "correlation_id": "corr:destroy:1",
                "accepted": True,
                "reason": "scene_ready",
            },
        )
    )

    assert messages[0]["payload"]["route"] == "siming_staging_ack"
    event = main.authority_event_bus.list_events(event_type="siming_staging_ack")[0]
    assert event.source.system == "godot"
    assert event.payload == {
        "source": "godot",
        "correlation_id": "corr:destroy:1",
        "accepted": True,
        "reason": "scene_ready",
    }


def test_repeated_godot_staging_ack_is_published_once_per_correlation_and_source() -> None:
    main.reset_runtime_state()
    payload = {
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "producer_ts": 500,
        "correlation_id": "corr:destroy:1",
        "accepted": True,
        "reason": "scene_ready",
    }

    main._handle_envelope(Envelope(message_type="siming_staging_ack", payload=payload))
    main._handle_envelope(Envelope(message_type="siming_staging_ack", payload=payload))

    acks = main.authority_event_bus.list_events(event_type="siming_staging_ack")
    assert [(ack.correlation_id, ack.payload["source"]) for ack in acks] == [
        ("corr:destroy:1", "godot")
    ]


def test_character_execution_envelope_retains_siming_staging_correlation() -> None:
    main.reset_runtime_state()
    command = CharacterGoalCommand(
        actor_id="char_b",
        command_type="observe",
        ttl_ms=1000,
        causation_id="siming:staging_request:503:destroy",
        correlation_id="corr:destroy:1",
        execution_payload={"actor_id": "char_b", "action_request_bundle": {"requested_actions": []}},
    )

    envelope = main._as_character_agent_execution_envelopes([command])[0]

    assert envelope["payload"]["actor_id"] == "char_b"
    assert envelope["payload"]["correlation_id"] == "corr:destroy:1"
    assert envelope["payload"]["causation_id"] == "siming:staging_request:503:destroy"


def test_char_b_observation_retains_the_destruction_authority_reference() -> None:
    main.reset_runtime_state()
    destruction_result_ref = "esm_result_event:501:destroy:letter"

    main._handle_envelope(
        Envelope(
            message_type="raw_fact_event",
            payload={
                "fact_family": "visual_fact",
                "fact_type": "object_state_change",
                "relation_type": "actor_observes_object_removal",
                "producer_ts": 502,
                "room_id": "room_demo",
                "scene_id": "scene_demo",
                "zone_id": "zone_focus",
                "source": {
                    "layer": "L1",
                    "system": "godot.raw_fact_emitter",
                    "actor_id": "char_b",
                },
                "targets": {"object_id": "obj_letter"},
                "observability": {"visual": True},
                "source_ref_lineage": [destruction_result_ref],
                "causation_id": destruction_result_ref,
                "correlation_id": "corr:destroy:1",
            },
        )
    )

    perceived_events = [
        event
        for event in main.character_agent_runtime.get_session_timeline("char_b")
        if event["event_type"] == "character_perceived_event"
    ]
    observed_event = perceived_events[-1]
    observed = observed_event["payload"]
    assert observed_event["actor_id"] == "char_b"
    assert observed["target_object_id"] == "obj_letter"
    assert destruction_result_ref in observed["source_ref_lineage"]


def test_staging_request_collects_character_and_esm_acks_before_godot() -> None:
    main.reset_runtime_state()
    request = AuthorityEvent(
        event_id="siming:staging_request:503:destroy",
        event_type="siming.staging_request",
        producer_ts=503,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source=AuthorityEventSource(layer="L2", system="siming.dispatcher"),
        routing=AuthorityEventRouting(
            audience_mode="targeted",
            routing_mode="event_type",
            target_ids=["char_b", "frontend_projector"],
        ),
        priority="p2",
        ttl=5000,
        durability="replayable",
        causation_id="esm_result_event:501:destroy:letter",
        correlation_id="corr:destroy:1",
        payload={
            "node_id": "runtime:bridge:proposal:destroy:1",
            "obligation_id": "obligation:evidence:1",
            "realization_signature": "sig:private-confrontation",
            "target_actor_id": "char_b",
        },
    )

    main.authority_event_bus.publish(request)

    acks = main.authority_event_bus.list_events(event_type="siming_staging_ack")
    assert [ack.payload["source"] for ack in acks] == ["character", "esm"]
    assert {ack.correlation_id for ack in acks} == {"corr:destroy:1"}
    assert acks[0].payload["accepted"] is True


@pytest.mark.parametrize("event_type", ["siming.opportunity", "siming.impulse"])
def test_character_dispatch_reaches_godot_character_execution(event_type: str) -> None:
    main.reset_runtime_state()
    event = AuthorityEvent(
        event_id="siming:dispatch_intent:503:staging_ack:godot",
        event_type=event_type,
        producer_ts=503,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source=AuthorityEventSource(layer="L2", system="siming.dispatcher"),
        routing=AuthorityEventRouting(
            audience_mode="targeted",
            routing_mode="event_type",
            target_ids=["char_b", "frontend_projector"],
        ),
        priority="p2",
        ttl=5000,
        durability="replayable",
        causation_id="siming_staging_ack:503:godot:corr:destroy:1",
        correlation_id="corr:destroy:1",
        payload={
            "target_actor_id": "char_b",
            "presentation_hint": "The original evidence is gone.",
        },
    )
    command = CharacterGoalCommand(
        actor_id="char_b",
        command_type="observe",
        ttl_ms=1000,
        causation_id=event.causation_id,
        correlation_id=event.correlation_id,
        execution_payload={"actor_id": "char_b", "action_request_bundle": {"requested_actions": []}},
    )

    main._queue_siming_character_dispatch_messages(
        event.event_id,
        SimingCharacterDispatchResult(commands_by_actor={"char_b": [command]}),
    )
    main.authority_event_bus.publish(event)
    messages = main._finalize_outbound_messages(
        [{"message_type": "ack", "payload": {"accepted": True}}]
    )

    assert [message["message_type"] for message in messages] == [
        "ack",
        "siming_output",
        "character_agent_execution",
        "authority_event",
    ]
    assert messages[1]["payload"]["authority_event_id"] == event.event_id
    assert messages[2]["payload"]["correlation_id"] == "corr:destroy:1"
