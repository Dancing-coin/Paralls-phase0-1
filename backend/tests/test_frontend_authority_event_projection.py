from types import SimpleNamespace

from app.models.authority_event import AuthorityEvent
from app.models.runtime_state import ConversationCandidateEvent
from app.models.state_machine_transition import StateMachineTransitionEvent
from app.models.world_result import ActionResolutionResult
from app.services.frontend_authority_event_projection import (
    FrontendAuthorityEventProjector,
    project_authority_event_as_siming_output,
)
from app.services.phase0_authority_event_adapter import Phase0AuthorityEventAdapter


def test_projector_emits_legacy_conversation_candidate_event_for_authority_candidate() -> None:
    candidate = ConversationCandidateEvent(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=123,
        candidate_ref="cand_char_a",
        candidate_actor_ids=["char_a"],
        candidate_object_ids=[],
        candidate_environment_ids=[],
        engagement_pressure="elevated",
        privacy_risk_hint="low",
        causation_id="focus:123",
        correlation_id="focus:123",
    )
    authority_event = Phase0AuthorityEventAdapter().conversation_candidate_event(candidate)
    projector = FrontendAuthorityEventProjector()

    projector.handle_event(authority_event)
    messages = projector.drain()

    assert messages == [
        {
            "message_type": "conversation_candidate_event",
            "payload": candidate.model_dump(),
        }
    ]


def test_projector_emits_legacy_world_result_for_authority_esm_result() -> None:
    result = ActionResolutionResult(
        request_ref="interact:456:obj_letter",
        result_id="action_resolution:interact:456:obj_letter",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
        source_type="player",
        entity_id="obj_letter",
        target_object_id="obj_letter",
        result_type="action_resolution_result",
        causation_id="interact:456",
        correlation_id="interact:456",
        producer_ts=457,
        settlement_status="accepted",
        resolution_status="accepted",
        resolved_entities=["obj_letter"],
        applied_state_changes=["object_state_result"],
        stable_state_summary="interaction accepted",
    )
    authority_event = Phase0AuthorityEventAdapter().world_result_event(
        result,
        source_event=SimpleNamespace(scene_id="scene_demo", zone_id="zone_focus", actor_id="char_c"),
    )
    projector = FrontendAuthorityEventProjector()

    projector.handle_event(authority_event)
    messages = projector.drain()

    assert messages == [
        {
            "message_type": "world_result",
            "event_id": "action_resolution:interact:456:obj_letter",
            "event_type": "action_resolution_result",
            "producer_ts": 457,
            "room_id": "room_demo",
            "scene_id": "scene_demo",
            "zone_id": "zone_focus",
            "entity_id": "obj_letter",
            "source": {
                "layer": "L1",
                "system": "esm",
                "actor_id": "char_c",
                "object_id": "obj_letter",
            },
            "routing": {
                "audience_mode": "authority_broadcast",
                "routing_mode": "authoritative_event_bus",
                "dialog_group_id": None,
                "target_ids": [],
            },
            "priority": "p1",
            "ttl": None,
            "durability": "replayable",
            "causation_id": "interact:456",
            "correlation_id": "interact:456",
            "payload": result.model_dump(exclude_none=True),
        }
    ]


def test_projector_emits_legacy_state_machine_transition_for_authority_transition() -> None:
    transition = StateMachineTransitionEvent(
        event_id="transition:visibility:obj_letter:300",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        entity_id="obj_letter",
        machine_id="visibility",
        from_state="partially_visible",
        to_state="visible",
        trigger_type="interact.inspect",
        transition_reason="player inspect interaction accepted",
        producer_ts=300,
        causation_id="interact:300",
        correlation_id="interact:300",
    )
    authority_event = Phase0AuthorityEventAdapter().state_machine_transition_event(transition)
    projector = FrontendAuthorityEventProjector()

    projector.handle_event(authority_event)
    messages = projector.drain()

    assert messages == [
        {
            "message_type": "state_machine_transition",
            "event_id": "transition:visibility:obj_letter:300",
            "event_type": "state_machine_transition",
            "room_id": "room_demo",
            "scene_id": "scene_demo",
            "zone_id": "zone_focus",
            "entity_id": "obj_letter",
            "machine_id": "visibility",
            "from_state": "partially_visible",
            "to_state": "visible",
            "trigger_type": "interact.inspect",
            "transition_reason": "player inspect interaction accepted",
            "producer_ts": 300,
            "causation_id": "interact:300",
            "correlation_id": "interact:300",
            "payload": transition.model_dump(),
        }
    ]


def test_frontend_siming_output_projection_remains_frontend_compatibility_only() -> None:
    event = AuthorityEvent.model_validate(
        {
            "event_id": "siming:fact_reveal:500:cause:1",
            "event_type": "siming.fact_reveal",
            "producer_ts": 500,
            "room_id": "room_demo",
            "scene_id": "scene_demo",
            "zone_id": "zone_focus",
            "source": {"layer": "L2", "system": "siming.dispatcher", "actor_id": None},
            "routing": {
                "audience_mode": "targeted",
                "routing_mode": "event_type",
                "target_ids": ["char_a"],
            },
            "priority": "p1",
            "ttl": 5000,
            "durability": "replayable",
            "causation_id": "cause:1",
            "correlation_id": "corr:1",
            "payload": {
                "message_id": "msg:1",
                "target_actor_id": "char_a",
                "presentation_hint": "look at the lamp",
            },
        }
    )

    envelope = project_authority_event_as_siming_output(event)

    assert envelope is not None
    assert envelope["message_type"] == "siming_output"
    assert envelope["payload"]["authority_event_id"] == "siming:fact_reveal:500:cause:1"
    assert envelope["payload"]["authority_event_type"] == "siming.fact_reveal"
