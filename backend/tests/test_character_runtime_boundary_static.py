from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_character_replica_remains_the_actor_runtime_shell() -> None:
    replica_source = (ROOT / "scripts" / "character" / "CharacterReplica.gd").read_text(
        encoding="utf-8"
    )

    assert "func begin_player_control_frame(" in replica_source
    assert "func apply_player_shell_pose(" in replica_source
    assert "func clear_player_shell_frame() -> void:" in replica_source
    assert "func _build_player_presentation_input() -> Dictionary:" in replica_source
    assert "func _push_player_presentation_input() -> void:" in replica_source


def test_main_demo_controller_does_not_keep_direct_character_runtime_dependency() -> None:
    controller_source = (ROOT / "scripts" / "phase0" / "MainDemoController.gd").read_text(
        encoding="utf-8"
    )

    assert '@onready var character_c: Node3D = $PlayerCharacter/CharacterReplica' not in controller_source
    assert "character_c.has_method(" not in controller_source
    assert "character_c.get_visual_forward()" not in controller_source
