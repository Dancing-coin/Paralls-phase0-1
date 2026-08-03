from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_phase_playback_is_a_local_adapter_with_no_settlement_authority() -> None:
    adapter = _read("scripts/interaction/EmbodiedActionPlaybackAdapter.gd")
    controller = _read("scripts/interaction/EmbodiedActionController.gd")

    assert "class_name EmbodiedActionPlaybackAdapter" in adapter
    assert "begin_phase" in adapter
    assert "restore_local_ownership" in adapter
    assert "local_execution_only" in adapter
    assert "settlement" not in adapter.lower()
    assert "world_truth" not in adapter.lower()
    assert "playback_adapter" in controller
    assert "local_playback_unavailable" in controller


def test_reviewed_skin_playback_checks_descriptor_clip_and_recovers_to_idle() -> None:
    skin = _read("scripts/character/KnightRoleSkin.gd")

    assert "play_reviewed_action_atom" in skin
    assert "restore_reviewed_action_playback" in skin
    assert "REVIEWED_ACTION_ATOM_STATES" in skin
    assert "animation_clip_ref" in skin


def test_controller_playback_probe_uses_catalog_and_real_skin_host() -> None:
    probe = _read("scripts/verification/EmbodiedActionPlaybackProbe.gd")
    scene = _read("scenes/phase0/EmbodiedActionPlaybackProbe.tscn")

    assert "DefaultSceneActionAtomCatalog" in probe
    assert "KnightRoleSkin.tscn" in probe
    assert "phase_playback" in probe
    assert "EmbodiedActionPlaybackProbe.gd" in scene
