from app.models.authority_event import AuthorityEvent
from app.services.siming_fact_core import SimingFactCore
from app.services.siming_observe import SimingObservePipeline


def make_event(**payload_overrides: object) -> AuthorityEvent:
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
    payload["payload"].update(payload_overrides)  # type: ignore[index, union-attr]
    return AuthorityEvent.model_validate(payload)


def test_fact_core_extracts_known_facts_from_observed_events() -> None:
    observed = SimingObservePipeline().observe([make_event()])

    result = SimingFactCore().evaluate(observed)

    assert result.accepted is True
    assert result.known_fact_ids == ["visual_fact:300:char_c:light_level_drop"]
    assert result.veto_reason is None


def test_fact_core_vetoes_locked_fact_conflicts_before_llm_or_projection() -> None:
    observed = SimingObservePipeline().observe([make_event(locked_fact_conflict=True)])

    result = SimingFactCore().evaluate(observed)

    assert result.accepted is False
    assert result.veto_reason == "locked_fact_conflict"
    assert result.known_fact_ids == []
