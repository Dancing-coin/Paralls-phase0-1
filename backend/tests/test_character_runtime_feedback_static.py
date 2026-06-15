from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_visible_runtime_feedback_is_not_owned_by_character_replica() -> None:
    replica_source = (ROOT / "scripts" / "character" / "CharacterReplica.gd").read_text(
        encoding="utf-8"
    )
    feedback_source = (ROOT / "scripts" / "character" / "CharacterRuntimeFeedback.gd").read_text(
        encoding="utf-8"
    )
    scene_source = (ROOT / "scenes" / "phase0" / "CharacterReplica.tscn").read_text(
        encoding="utf-8"
    )

    assert "class_name CharacterRuntimeFeedback" in feedback_source
    assert "func show_combat_feedback(text: String) -> void:" in feedback_source
    assert "func update_nameplate(" in feedback_source
    assert "@onready var nameplate" not in replica_source
    assert "combat_feedback_timer" not in replica_source
    assert "combat_feedback_text" not in replica_source
    assert "func _update_nameplate() -> void:" not in replica_source
    assert "func _show_combat_feedback(text: String) -> void:" not in replica_source
    assert "func _update_combat_feedback(delta: float) -> void:" not in replica_source
    assert '[node name="CharacterRuntimeFeedback"' in scene_source
