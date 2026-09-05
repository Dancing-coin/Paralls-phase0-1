from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_low_poly_character_is_primitive_only_and_read_only() -> None:
    scene_path = ROOT / "scenes" / "phase0" / "ProceduralLowPolyCharacter.tscn"
    script_path = ROOT / "scripts" / "verification" / "ProceduralLowPolyCharacter.gd"
    assert scene_path.exists()
    assert script_path.exists()
    scene = scene_path.read_text(encoding="utf-8")
    script = script_path.read_text(encoding="utf-8")
    assert "CharacterBody3D" in scene
    assert "CapsuleMesh" in script
    assert "SphereMesh" in script
    assert "BoxMesh" in script
    assert "AnimationPlayer" in script
    assert "append_batch" not in script
    assert "BackendBridge" not in script
    assert "private_fact" not in script


def test_low_poly_character_exposes_profile_and_committed_state_contract() -> None:
    script = (ROOT / "scripts" / "verification" / "ProceduralLowPolyCharacter.gd").read_text(encoding="utf-8")
    for method in ("configure_profile", "apply_committed_state", "clear_speculative_state"):
        assert f"func {method}" in script
    for marker in ("actor_ref", "role_ref", "presentation_profile_ref"):
        assert marker in script
