from app.debug_narration import (
    summarize_character_candidate,
    summarize_character_input_from_fact,
    summarize_character_input_from_candidate,
    summarize_character_input_from_character_perceived,
    summarize_character_input_from_self_body_perceived,
    summarize_character_input_from_siming_output,
    summarize_character_input_from_world_result,
    summarize_character_interpretation,
    summarize_character_output,
)
from app.models.candidate_percept import CandidatePerceptEvent
from app.models.character_perceived import CharacterPerceivedEvent
from app.models.raw_fact import RawFactEvent
from app.models.self_body_perceived import SelfBodyPerceivedEvent
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


def test_summarize_character_input_from_spatial_access_clear_fact_is_natural_language() -> None:
    event = RawFactEvent(
        fact_family="spatial_access_fact",
        fact_type="actor_left_actor_range",
        relation_type="actor_left_actor_range",
        producer_ts=951,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_c"},
        targets={},
        effect_kind="clear",
        subject_key="nearby_actor_refs",
    )

    summary = summarize_character_input_from_fact(event)

    assert "离开" in summary or "退出" in summary or "不再接近" in summary


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


def test_summarize_character_input_from_world_result_mentions_action_resolution_success() -> None:
    summary = summarize_character_input_from_world_result(
        "char_c",
        {
            "result_type": "action_resolution_result",
            "target_object_id": "obj_letter",
        },
    )

    assert "CharacterC" in summary
    assert "obj_letter" in summary
    assert "交互结算已确认" in summary


def test_summarize_character_input_from_world_result_mentions_body_state_change() -> None:
    summary = summarize_character_input_from_world_result(
        "char_c",
        {
            "result_type": "body_state_result",
            "body_state_class": "interaction_strain",
            "current_state": "engaged",
        },
    )

    assert "CharacterC" in summary
    assert "interaction_strain" in summary
    assert "engaged" in summary


def test_summarize_character_input_from_siming_output_mentions_target() -> None:
    summary = summarize_character_input_from_siming_output(
        {
            "output_type": "attention_prompt",
            "target_actor_id": "char_b",
            "target_object_id": "obj_letter",
        },
    )

    assert "CharacterB" in summary
    assert "obj_letter" in summary
    assert "司命提示" in summary


def test_summarize_character_input_from_candidate_mentions_l2_candidate_layer() -> None:
    event = CandidatePerceptEvent(
        percept_channel="visual",
        source_fact_family="visual_fact",
        source_fact_type="fixed_gaze_on_target",
        producer_ts=910,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source_actor_id="char_c",
        target_actor_id="char_a",
        audience_scope="candidate",
        observability={"visual": True},
        causation_id="visual_fact:910",
        correlation_id="visual_fact:910",
    )

    summary = summarize_character_input_from_candidate(event)

    assert "候选感知" in summary
    assert "CharacterC" in summary
    assert "CharacterA" in summary


def test_summarize_character_input_from_character_perceived_mentions_private_perception_layer() -> None:
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="visual",
        producer_ts=911,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="char_c is looking at char_a",
        source_candidate_event_id="visual_fact:911:char_a",
    )

    summary = summarize_character_input_from_character_perceived(event)

    assert "角色私有感知" in summary
    assert "CharacterA" in summary
    assert "visual" in summary


def test_summarize_character_input_from_self_body_perceived_mentions_self_body_layer() -> None:
    event = SelfBodyPerceivedEvent(
        actor_id="char_c",
        body_state_class="interaction_strain",
        producer_ts=912,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="interaction_strain is engaged",
        source_body_result_id="body_result:char_c:912",
    )

    summary = summarize_character_input_from_self_body_perceived(event)

    assert "自身身体感知" in summary
    assert "CharacterC" in summary
    assert "interaction_strain" in summary
