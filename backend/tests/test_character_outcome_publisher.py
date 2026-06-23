import pytest

from app.models.character_agent_runtime import CharacterGoalCommand
from app.models.siming_character_bridge import CharacterDeliveryAuditSummary
from app.services.character_outcome_publisher import CharacterOutcomePublisher


def test_publisher_emits_role_owned_externalization_events_only() -> None:
    publisher = CharacterOutcomePublisher()
    command = CharacterGoalCommand(
        actor_id="char_a",
        command_type="speak",
        ttl_ms=1500,
        causation_id="cause:talk:1",
        correlation_id="corr:talk:1",
        producer_ts=300,
        dialogue_text="keep your voice down",
    )

    result = publisher.publish_commands(actor_id="char_a", commands=[command])

    assert [event["event_type"] for event in result.role_events] == ["SpeechActPublished"]
    assert result.linked_authority_results == []


def test_publisher_links_but_does_not_mint_world_result() -> None:
    publisher = CharacterOutcomePublisher()

    result = publisher.link_authority_result(
        actor_id="char_a",
        delivery_id="delivery:msg:1:char_a:1",
        authority_event_type="constraint_state_event",
        authority_event_id="constraint:obj_letter:1",
        correlation_id="corr:1",
        causation_id="cause:1",
    )

    assert result["link_type"] == "authority_result_link"
    assert result["link_mode"] == "reference_only"
    assert result["authority_event_type"] == "constraint_state_event"
    assert result["authority_event_id"] == "constraint:obj_letter:1"
    assert "message_type" not in result
    assert "event_type" not in result
    assert "payload" not in result


def test_publisher_does_not_emit_settlement_event_types_from_role_commands() -> None:
    publisher = CharacterOutcomePublisher()
    command = CharacterGoalCommand(
        actor_id="char_a",
        command_type="interact",
        ttl_ms=1500,
        causation_id="cause:act:1",
        correlation_id="corr:act:1",
        producer_ts=301,
        target_object_id="obj_letter",
    )

    result = publisher.publish_commands(actor_id="char_a", commands=[command])

    assert [event["event_type"] for event in result.role_events] == ["ActionRequestIssued"]
    assert {
        "world_result",
        "constraint_result",
        "conversation_resolution",
        "world_result_event",
        "constraint_state_result",
        "conversation_resolution_event",
    }.isdisjoint({str(event["event_type"]) for event in result.role_events})


def test_publisher_rejects_actor_mismatch_in_command_batch() -> None:
    publisher = CharacterOutcomePublisher()
    command = CharacterGoalCommand(
        actor_id="char_b",
        command_type="speak",
        ttl_ms=1500,
        causation_id="cause:talk:2",
        correlation_id="corr:talk:2",
        producer_ts=302,
        dialogue_text="I heard something.",
    )

    with pytest.raises(ValueError, match="command.actor_id must match publish actor_id"):
        publisher.publish_commands(actor_id="char_a", commands=[command])


def test_publisher_preserves_action_request_command_payload() -> None:
    publisher = CharacterOutcomePublisher()
    command = CharacterGoalCommand(
        actor_id="char_a",
        command_type="go_to",
        ttl_ms=1750,
        causation_id="cause:move:1",
        correlation_id="corr:move:1",
        producer_ts=303,
        target_position=[1.0, 2.0, 3.0],
        role_state_hint="cautious",
        physiology_hint="slow steps",
        execution_payload={"path_mode": "safe"},
    )

    result = publisher.publish_commands(actor_id="char_a", commands=[command])

    event = result.role_events[0]
    assert event["event_type"] == "ActionRequestIssued"
    assert event["actor_id"] == "char_a"
    assert event["producer_ts"] == 303
    assert event["ttl_ms"] == 1750
    assert event["payload"] == {
        "command_type": "go_to",
        "target_actor_id": None,
        "target_object_id": None,
        "target_environment_id": None,
        "target_position": [1.0, 2.0, 3.0],
        "role_state_hint": "cautious",
        "physiology_hint": "slow steps",
        "execution_payload": {"path_mode": "safe"},
    }


def test_publisher_keeps_restricted_audit_summaries_off_role_events() -> None:
    publisher = CharacterOutcomePublisher()
    summary = CharacterDeliveryAuditSummary(
        message_id="msg:siming:1",
        delivery_id="delivery:msg:siming:1:char_a:1",
        actor_id="char_a",
        status="suggested_only",
        producer_ts=304,
        causation_id="cause:audit:1",
        correlation_id="corr:audit:1",
    )

    result = publisher.publish_restricted_audit_summaries(summaries=[summary])

    assert result.role_events == []
    assert result.linked_authority_results == []
    assert result.restricted_audit_records == [
        {
            "record_type": "CharacterDeliveryAuditSummary",
            "visibility": "restricted_audit",
            "message_id": "msg:siming:1",
            "delivery_id": "delivery:msg:siming:1:char_a:1",
            "actor_id": "char_a",
            "status": "suggested_only",
            "producer_ts": 304,
            "causation_id": "cause:audit:1",
            "correlation_id": "corr:audit:1",
        }
    ]
