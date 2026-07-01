from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_relationship_overlay_supports_required_relationship_line_families() -> None:
    source = (ROOT / "scripts" / "ui" / "RelationshipOverlay.gd").read_text(encoding="utf-8")

    assert "attention_lines" in source
    assert "dialogue_lines" in source
    assert "action_intent_lines" in source
    assert "blocked_lines" in source
    assert "siming_influence_lines" in source
    assert "target_markers" in source
    assert "draw_line(" in source
    assert "draw_circle(" in source
    assert "_resolve_world_target_node" in source
    assert "_project_world_to_canvas" in source
    assert "resolve_target_node(target_ref: String) -> Node3D" not in source
    assert 'state.call("get_visible_actor_states")' in source or "get_visible_actor_states" in source
    assert "for actor_id in actor_states.keys()" in source
    assert 'payload.get("focus_target"' in source
    assert 'payload.get("current_intent"' in source
    assert 'outcome.get("settlement_status"' in source
    assert 'state.call("get_latest_siming_state")' in source or "get_latest_siming_state" in source
    assert 'target_node.global_position + Vector3(0.0, 1.2, 0.0)' in source
    assert 'source_node.global_position + Vector3(0.0, 1.4, 0.0)' in source
    assert 'get_node_or_null("/root/MainDemo")' not in source
    assert "get_viewport().get_camera_3d()" in source


def test_actor_perception_sampler_declares_cone_range_and_los_hooks() -> None:
    text = (ROOT / "scripts" / "character" / "ActorPerceptionSampler.gd").read_text(encoding="utf-8")

    assert "sample_visible_targets" in text
    assert "_has_line_of_sight_to_target" in text
    assert "focus_max_distance" not in text
