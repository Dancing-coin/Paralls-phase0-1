from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_action_lock_priority_is_frozen_in_spec() -> None:
    control_spec_text = (
        ROOT
        / "docs"
        / "superpowers"
        / "specs"
        / "2026-06-12-character-actor-control-and-locomotion-design.md"
    ).read_text(encoding="utf-8")

    assert "interact > speak > observe/look_at > approach/go_to > idle" in control_spec_text


def test_shared_actor_path_mentions_action_lock_and_interrupt_rules() -> None:
    replica_source = (ROOT / "scripts" / "character" / "CharacterReplica.gd").read_text(
        encoding="utf-8"
    )

    assert "func _command_priority(" in replica_source
    assert "func _can_interrupt_current_action(" in replica_source
    assert "interact" in replica_source
    assert "speak" in replica_source
