import pytest

from app.models.authority_event import AuthorityEvent
from app.models.siming_event import FairnessStateSnapshot, InterventionCandidate, SimingAuditRecord
from app.services.siming_llm_provider import (
    DisabledSimingLlmCandidateProvider,
    FakeSimingLlmCandidateProvider,
    SimingLlmProviderTimeout,
)


def make_snapshot() -> FairnessStateSnapshot:
    return FairnessStateSnapshot(
        snapshot_id="fairness:visual_fact:300",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
        known_fact_ids=["visual_fact:300:char_c:light_level_drop"],
        eligible_actor_ids=["char_b"],
    )


def make_event() -> AuthorityEvent:
    return AuthorityEvent.model_validate(
        {
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
            },
        }
    )


def test_disabled_provider_returns_no_candidates() -> None:
    provider = DisabledSimingLlmCandidateProvider()

    assert provider.generate_candidates(snapshot=make_snapshot(), recent_events=[make_event()], recent_audit=[]) == []


def test_fake_provider_returns_deep_copied_fixture_candidates() -> None:
    fixture = InterventionCandidate(
        candidate_id="cand:fixture",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
        proposed_band="fact_reveal",
        target_actor_id="char_b",
        established_fact_ids=["visual_fact:300:char_c:light_level_drop"],
        source="llm",
    )
    provider = FakeSimingLlmCandidateProvider([fixture])

    candidates = provider.generate_candidates(snapshot=make_snapshot(), recent_events=[make_event()], recent_audit=[])
    candidates[0].reason_tags.append("mutated")

    second = provider.generate_candidates(snapshot=make_snapshot(), recent_events=[make_event()], recent_audit=[])
    assert second[0].reason_tags == []


def test_fake_provider_can_raise_timeout() -> None:
    provider = FakeSimingLlmCandidateProvider([], timeout=True)

    with pytest.raises(SimingLlmProviderTimeout):
        provider.generate_candidates(snapshot=make_snapshot(), recent_events=[make_event()], recent_audit=[])
