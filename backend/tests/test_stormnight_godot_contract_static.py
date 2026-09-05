from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_stormnight_scene_has_procedural_case_geometry_and_read_only_view() -> None:
    scene = (ROOT / "scenes" / "phase0" / "StormnightCopperSanatorium.tscn").read_text(encoding="utf-8")
    probe = (ROOT / "scripts" / "verification" / "StormnightCopperSanatoriumProbe.gd").read_text(encoding="utf-8")
    view = (ROOT / "scripts" / "verification" / "StormnightCopperSanatoriumView.gd").read_text(encoding="utf-8")
    assert "StormnightCopperSanatoriumProbe.gd" in scene
    for marker in ("ROOMS", "Occluder", "HideSpot", "Door", "EvidenceTable", "sound_zone_ref"):
        assert marker in probe
    assert "ProceduralLowPolyCharacter.tscn" in probe
    assert "ACTOR_PROFILES" in probe
    assert probe.count("actor_ref") >= 4
    assert "ThroneHall" not in probe
    assert "KnightRoleSkin" not in probe
    for method in ("apply_committed_projection", "reject_speculative_state", "read_only_panel_state"):
        assert f"func {method}" in view
    assert "append_batch" not in probe
    assert "BackendBridge" not in probe
    assert "STORMNIGHT_CASE_PROJECTION_PATH" in probe
