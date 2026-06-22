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
    assert 'get_node_or_null("/root/MainDemo")' not in source
    assert "get_viewport().get_camera_3d()" in source
