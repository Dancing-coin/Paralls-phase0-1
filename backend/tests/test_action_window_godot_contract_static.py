from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_existing_embodied_controller_owns_graph_window_and_rejection_cleanup() -> None:
    source = (ROOT / "scripts" / "interaction" / "EmbodiedActionController.gd").read_text(encoding="utf-8")
    assert "begin_action_graph_node" in source
    assert "advance_action_window" in source
    assert "reject_action_window" in source
    assert "speculative_state_cleared" in source
    assert "restore_local_ownership" in source
    assert "GameplayEventStore" not in source


def test_character_replica_camera_switch_is_presentation_only() -> None:
    source = (ROOT / "scripts" / "character" / "CharacterReplica.gd").read_text(encoding="utf-8")
    assert 'presentation_camera_mode := "third_person"' in source
    assert "set_presentation_camera_mode" in source
    assert '"presentation_only": true' in source
