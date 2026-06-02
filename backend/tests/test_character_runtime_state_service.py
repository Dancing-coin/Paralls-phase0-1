from app.models.runtime_state import ConversationCandidateEvent
from app.services.character_runtime_state_service import CharacterRuntimeStateService


def test_state_service_builds_initial_snapshot_for_actor() -> None:
    service = CharacterRuntimeStateService()
    snapshot = service.get_or_create_snapshot(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=100,
    )
    assert snapshot.actor_id == "char_c"
    assert snapshot.revision_seq == 1


def test_state_service_applies_candidate_event_and_emits_delta() -> None:
    service = CharacterRuntimeStateService()
    service.get_or_create_snapshot(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=100,
    )
    candidate = ConversationCandidateEvent(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=101,
        candidate_actor_ids=["char_a"],
        candidate_object_ids=["obj_letter"],
        candidate_environment_ids=[],
        engagement_pressure="elevated",
        privacy_risk_hint="low",
        causation_id="focus:101",
        correlation_id="focus:101",
    )
    delta = service.apply_conversation_candidate(candidate)
    assert delta.actor_id == "char_c"
    assert "conversation_candidate_refs" in delta.changed_fields
    assert delta.conversation_candidate_refs == ["cand_char_a_obj_letter"]


def test_state_service_skips_duplicate_focus_delta() -> None:
    service = CharacterRuntimeStateService()
    first = service.apply_focus_state(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=110,
        target_actor_id="char_a",
        target_object_id=None,
    )
    second = service.apply_focus_state(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=111,
        target_actor_id="char_a",
        target_object_id=None,
    )

    assert first is not None
    assert second is None


def test_state_service_skips_duplicate_candidate_delta() -> None:
    service = CharacterRuntimeStateService()
    candidate = ConversationCandidateEvent(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=120,
        candidate_actor_ids=[],
        candidate_object_ids=["obj_letter"],
        candidate_environment_ids=[],
        engagement_pressure="present",
        privacy_risk_hint="low",
        causation_id="visual_fact:120",
        correlation_id="visual_fact:120",
    )
    first = service.apply_conversation_candidate(candidate)
    second = service.apply_conversation_candidate(candidate)

    assert first is not None
    assert second is None


def test_state_service_applies_runtime_projection_delta() -> None:
    service = CharacterRuntimeStateService()
    delta = service.apply_runtime_projection(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=130,
        current_focus_target="obj_letter",
        current_attention_source="visual_fact",
        nearby_actor_refs=[],
        nearby_object_refs=["obj_letter"],
        nearby_environment_refs=[],
    )

    assert delta is not None
    assert delta.current_focus_target == "obj_letter"
    assert delta.current_attention_source == "visual_fact"


def test_state_service_applies_runtime_projection_environment_refs() -> None:
    service = CharacterRuntimeStateService()
    delta = service.apply_runtime_projection(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=131,
        current_focus_target="env_lamp",
        current_attention_source="visual_fact",
        nearby_actor_refs=[],
        nearby_object_refs=["obj_letter"],
        nearby_environment_refs=["env_lamp"],
    )

    assert delta is not None
    assert delta.nearby_environment_refs == ["env_lamp"]
