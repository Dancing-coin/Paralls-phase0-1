from app.debug_narration import (
    summarize_character_candidate,
    summarize_character_input_from_fact,
    summarize_character_interpretation,
    summarize_character_output,
)
from app.models.raw_fact import RawFactEvent
from app.models.visual_fact import VisualFactEvent


def test_summarize_character_input_from_visual_fact_is_natural_language() -> None:
    event = VisualFactEvent(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=1,
        fact_type="fixed_gaze_on_target",
        relation_type="actor_looks_at_object",
        target_object_id="obj_letter",
    )

    summary = summarize_character_input_from_fact(event)

    assert "CharacterC" in summary
    assert "视觉事实" in summary
    assert "obj_letter" in summary


def test_summarize_character_input_from_spatial_access_fact_mentions_distance() -> None:
    event = RawFactEvent(
        fact_family="spatial_access_fact",
        fact_type="actor_approached_actor",
        relation_type="actor_approached_actor",
        producer_ts=2,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_c"},
        targets={"actor_id": "char_b"},
        world={"distance_m": 3.2},
    )

    summary = summarize_character_input_from_fact(event)

    assert "CharacterC" in summary
    assert "CharacterB" in summary
    assert "3.2" in summary


def test_summarize_character_interpretation_humanizes_source_and_target() -> None:
    summary = summarize_character_interpretation(
        "char_b",
        {
            "current_focus_target": "obj_letter",
            "current_attention_source": "visual_fact",
        },
    )

    assert "CharacterB" in summary
    assert "obj_letter" in summary
    assert "视觉事实" in summary


def test_summarize_character_candidate_mentions_priority_when_elevated() -> None:
    summary = summarize_character_candidate(
        "char_a",
        {
            "candidate_actor_ids": ["char_b"],
            "engagement_pressure": "elevated",
        },
    )

    assert "CharacterA" in summary
    assert "CharacterB" in summary
    assert "优先" in summary


def test_summarize_character_output_includes_dialogue_content() -> None:
    summary = summarize_character_output(
        "char_a",
        "dialogue_response",
        {
            "target_actor_id": "char_c",
            "content": "我注意到那封信了。",
            "tone": "警觉的",
        },
    )

    assert "CharacterA" in summary
    assert "CharacterC" in summary
    assert "我注意到那封信了" in summary
