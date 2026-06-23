from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_player_controlled_character_replica_is_visible_by_default() -> None:
    bridge_source = (ROOT / "scripts" / "player" / "Phase0PlayerBridge.gd").read_text(
        encoding="utf-8"
    )

    assert "@export var hide_player_visual_shell := false" in bridge_source
