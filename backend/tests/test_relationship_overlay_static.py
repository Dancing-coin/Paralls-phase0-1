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
