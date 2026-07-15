import pytest

from app.models.authority_event import AuthorityEvent
from app.models.siming_catalyst import InnerPrompt, SimingCatalystInput


def make_siming_event(
    *,
    event_type: str = "siming.impulse",
    target_ids: list[str] | None = None,
) -> AuthorityEvent:
    return AuthorityEvent.model_validate(
        {
            "event_id": "siming:impulse:101:cause:1",
            "event_type": event_type,
            "producer_ts": 101,
            "room_id": "room_demo",
            "scene_id": "scene_demo",
            "zone_id": "zone_focus",
            "source": {"layer": "L2", "system": "siming.dispatcher", "actor_id": None},
            "routing": {
                "audience_mode": "targeted",
                "routing_mode": "event_type",
                "target_ids": target_ids or ["char_a"],
            },
            "priority": "p1",
            "ttl": 5000,
            "durability": "replayable",
            "causation_id": "cause:1",
            "correlation_id": "corr:1",
            "payload": {
                "message_id": "msg:siming:1",
                "intervention_band": event_type.removeprefix("siming."),
                "presentation_hint": "notice the movement near the desk",
            },
        }
    )


def test_fact_reveal_creates_catalyst_input() -> None:
    event = make_siming_event(event_type="siming.fact_reveal", target_ids=["char_a"])
    event.payload.update(
        {
            "target_actor_id": "char_a",
            "target_object_id": "obj_letter",
            "presentation_hint": "the letter becomes narratively salient",
            "evidence_refs": ["authority_event:visual_fact:300"],
        }
    )

    catalyst = SimingCatalystInput.from_authority_event(event)

    assert catalyst.catalyst_type == "fact_reveal"
    assert catalyst.target_actor_id == "char_a"
    assert catalyst.target_object_id == "obj_letter"
    assert catalyst.evidence_refs == ["authority_event:visual_fact:300"]


def test_impulse_hint_requires_axis_target_evidence_and_intensity_limit() -> None:
    event = make_siming_event(event_type="siming.impulse", target_ids=["char_a"])
    event.payload.update(
        {
            "target_actor_id": "char_a",
            "target_object_id": "obj_letter",
            "presentation_hint": "a sudden urge to check the letter",
            "impulse_axis": "action",
            "impulse_label": "check_letter",
            "intensity": 0.35,
            "evidence_refs": ["public_fact:letter_seen"],
        }
    )

    catalyst = SimingCatalystInput.from_authority_event(event)

    assert catalyst.catalyst_type == "impulse_hint"
    assert catalyst.impulse_axis == "action"
    assert catalyst.intensity == 0.35


def test_impulse_hint_rejects_over_limit_intensity() -> None:
    event = make_siming_event(event_type="siming.impulse", target_ids=["char_a"])
    event.payload.update(
        {
            "target_actor_id": "char_a",
            "impulse_axis": "narrative",
            "intensity": 0.36,
            "evidence_refs": ["public_fact:letter_seen"],
        }
    )

    with pytest.raises(ValueError, match="intensity"):
        SimingCatalystInput.from_authority_event(event)


def test_player_targeted_impulse_hint_is_rejected_not_auto_converted() -> None:
    event = make_siming_event(event_type="siming.impulse", target_ids=["player"])
    event.payload.update(
        {
            "target_actor_id": "player",
            "target_actor_control": "player",
            "impulse_axis": "narrative",
            "intensity": 0.2,
            "evidence_refs": ["public_fact:letter_seen"],
        }
    )

    with pytest.raises(ValueError, match="player"):
        SimingCatalystInput.from_authority_event(event)


def test_inner_prompt_is_player_facing_and_non_authoritative() -> None:
    event = make_siming_event(event_type="siming.inner_prompt", target_ids=["frontend_projector"])
    event.payload.update(
        {
            "target_actor_id": "player",
            "prompt_text": "Something about the letter feels wrong.",
            "intensity": 0.2,
            "evidence_refs": ["public_fact:letter_seen"],
            "player_facing": True,
            "non_authoritative": True,
            "presentation_effects": ["narration_text"],
        }
    )

    prompt = InnerPrompt.from_authority_event(event)

    assert prompt.target_actor_id == "player"
    assert prompt.player_facing is True
    assert prompt.non_authoritative is True
    assert prompt.presentation_effects == ["narration_text"]


def test_inner_prompt_rejects_action_or_world_mutation_fields() -> None:
    event = make_siming_event(event_type="siming.inner_prompt", target_ids=["frontend_projector"])
    event.payload.update(
        {
            "target_actor_id": "player",
            "prompt_text": "Open the letter now.",
            "intensity": 0.2,
            "evidence_refs": ["public_fact:letter_seen"],
            "backend_action_request": {"action": "open"},
        }
    )

    with pytest.raises(ValueError, match="forbidden"):
        InnerPrompt.from_authority_event(event)
