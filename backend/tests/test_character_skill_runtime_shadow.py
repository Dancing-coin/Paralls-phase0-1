from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.character_agent.skills.registry import CharacterSkillRegistry
from app.character_agent.skills.service import CharacterSkillService
from app.models.character_perceived import CharacterPerceivedEvent


def _event(*, actor_id: str = "char_a") -> CharacterPerceivedEvent:
    return CharacterPerceivedEvent(
        actor_id=actor_id,
        percept_channel="visual",
        producer_ts=100,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_demo",
        perceived_summary="char_b pauses near the archive threshold",
        source_candidate_event_id="event:shadow:1",
        source_actor_id="char_b",
        target_actor_id="char_b",
        clarity_score=0.95,
        certainty_score=0.95,
    )


def _skill_affordance_payload(frame: dict[str, object]) -> dict[str, object]:
    affordances = frame["affordances"]
    assert isinstance(affordances, dict)
    cards = affordances["cards"]
    assert isinstance(cards, list)
    for card in cards:
        assert isinstance(card, dict)
        if card.get("factor_type") == "skill_affordance":
            payload = card.get("payload", {})
            assert isinstance(payload, dict)
            return payload
    raise AssertionError("skill_affordance card missing")


def test_runtime_shadow_frame_projects_compressed_skill_affordance_summary() -> None:
    runtime = CharacterAgentRuntime()
    runtime.ingest_character_perceived_event(_event())

    frame = runtime.build_shadow_mind_frame(
        actor_id="char_a",
        producer_ts=101,
        trigger_event={"event_id": "event:shadow:manual", "event_type": "shadow_probe"},
    )
    payload = _skill_affordance_payload(frame)

    assert payload["profile_skill_ids"] == ["observation", "mediation", "procedural recall"]
    assert payload["available_action_families"]["observation"]["examples"] == ["survey_scene"]
    assert payload["available_action_families"]["observation"]["level"] == "basic"
    assert payload["available_action_families"]["social"]["examples"] == [
        "defuse_social_tension"
    ]
    assert payload["available_action_families"]["procedure"]["examples"] == [
        "follow_room_protocol"
    ]
    assert "registry" not in payload
    assert "skills" not in payload
    assert "actions" not in payload
    assert "bindings" not in payload


def test_runtime_shadow_frame_tolerates_empty_skill_registry_without_exposing_registry() -> None:
    runtime = CharacterAgentRuntime(
        skill_service=CharacterSkillService(registry=CharacterSkillRegistry())
    )
    runtime.ingest_character_perceived_event(_event())

    frame = runtime.build_shadow_mind_frame(
        actor_id="char_a",
        producer_ts=101,
        trigger_event={"event_id": "event:shadow:manual", "event_type": "shadow_probe"},
    )
    payload = _skill_affordance_payload(frame)

    assert payload["profile_skill_ids"] == ["observation", "mediation", "procedural recall"]
    assert payload["profile_limits"] == []
    assert payload["available_action_families"] == {}
    assert payload["blocked_action_families"] == {}
    assert "registry" not in payload
    assert "skills" not in payload
    assert "actions" not in payload
    assert "bindings" not in payload
