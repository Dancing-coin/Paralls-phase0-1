import pytest
from pydantic import ValidationError

from app.models.authority_event import AuthorityEvent


def valid_event_dict() -> dict[str, object]:
    return {
        "event_id": "evt_visual_1",
        "event_type": "visual_fact_event",
        "producer_ts": 100,
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "source": {
            "layer": "L1",
            "system": "visual_fact",
            "actor_id": "char_c",
        },
        "routing": {
            "audience_mode": "room",
            "routing_mode": "broadcast",
            "target_ids": ["siming"],
        },
        "priority": "p2",
        "ttl": 5000,
        "durability": "replayable",
        "causation_id": "visual_fact:100",
        "correlation_id": "visual_fact:100",
        "payload": {
            "fact_type": "light_level_drop",
            "target_environment_id": "env_lamp",
        },
    }


def test_authority_event_accepts_required_public_envelope() -> None:
    event = AuthorityEvent.model_validate(valid_event_dict())

    assert event.event_id == "evt_visual_1"
    assert event.source.system == "visual_fact"
    assert event.routing.target_ids == ["siming"]
    assert event.payload["fact_type"] == "light_level_drop"


@pytest.mark.parametrize(
    "missing_key",
    [
        "event_id",
        "event_type",
        "producer_ts",
        "room_id",
        "source",
        "routing",
        "causation_id",
        "correlation_id",
        "payload",
    ],
)
def test_authority_event_rejects_missing_required_envelope_keys(missing_key: str) -> None:
    payload = valid_event_dict()
    payload.pop(missing_key)

    with pytest.raises(ValidationError):
        AuthorityEvent.model_validate(payload)


@pytest.mark.parametrize("forbidden_key", ["world_ts", "sim_tick_ts"])
def test_authority_event_rejects_domain_time_at_public_envelope_root(forbidden_key: str) -> None:
    payload = valid_event_dict()
    payload[forbidden_key] = 123

    with pytest.raises(ValidationError, match=forbidden_key):
        AuthorityEvent.model_validate(payload)


@pytest.mark.parametrize("legacy_key", ["producer", "source_actor_id", "target_actor_ids"])
def test_authority_event_rejects_legacy_flat_envelope_fields(legacy_key: str) -> None:
    payload = valid_event_dict()
    payload[legacy_key] = "legacy"

    with pytest.raises(ValidationError, match=legacy_key):
        AuthorityEvent.model_validate(payload)


@pytest.mark.parametrize("priority", ["low", "urgent", "p4"])
def test_authority_event_rejects_unknown_priority(priority: str) -> None:
    payload = valid_event_dict()
    payload["priority"] = priority

    with pytest.raises(ValidationError):
        AuthorityEvent.model_validate(payload)


@pytest.mark.parametrize("durability", ["durable", "ephemeral", "memory"])
def test_authority_event_rejects_unknown_durability(durability: str) -> None:
    payload = valid_event_dict()
    payload["durability"] = durability

    with pytest.raises(ValidationError):
        AuthorityEvent.model_validate(payload)
