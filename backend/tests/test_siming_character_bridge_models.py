from pydantic import ValidationError

from app.models.siming_character_bridge import (
    CharacterDeliveryAuditSummary,
    SimingCharacterCompatibilityInput,
)


def test_compatibility_input_requires_delivery_id_and_target_actor() -> None:
    payload = SimingCharacterCompatibilityInput(
        message_id="msg:siming:1",
        delivery_id="delivery:msg:siming:1:char_a:1",
        actor_id="char_a",
        input_type="siming_high_level_message",
        band="impulse",
        producer_ts=101,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="cause:1",
        correlation_id="corr:1",
        presentation_hint="look toward the sound",
    )

    assert payload.delivery_id == "delivery:msg:siming:1:char_a:1"
    assert payload.actor_id == "char_a"
    assert payload.input_type == "siming_high_level_message"


def test_compatibility_input_rejects_low_level_command_fields() -> None:
    try:
        SimingCharacterCompatibilityInput(
            message_id="msg:siming:2",
            delivery_id="delivery:msg:siming:2:char_a:1",
            actor_id="char_a",
            input_type="siming_high_level_message",
            band="impulse",
            producer_ts=102,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            causation_id="cause:2",
            correlation_id="corr:2",
            go_to_position=[1.0, 2.0, 3.0],
        )
    except ValidationError as exc:
        assert "forbidden" in str(exc)
    else:
        raise AssertionError("expected ValidationError")


def test_delivery_audit_summary_accepts_restricted_outcome_labels_only() -> None:
    summary = CharacterDeliveryAuditSummary(
        message_id="msg:siming:3",
        delivery_id="delivery:msg:siming:3:char_b:1",
        actor_id="char_b",
        status="suggested_only",
        producer_ts=103,
        causation_id="cause:3",
        correlation_id="corr:3",
    )

    assert summary.status == "suggested_only"
