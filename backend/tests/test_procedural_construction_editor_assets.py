from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_procedural_construction_editor_is_internal_asset_free_and_backend_mirror_only() -> None:
    script = ROOT / "scripts" / "phase0" / "ProceduralConstructionEditor.gd"
    scene = ROOT / "scenes" / "phase0" / "ProceduralConstructionEditor.tscn"

    assert script.exists()
    assert scene.exists()
    source = script.read_text(encoding="utf-8")
    assert "class_name ProceduralConstructionEditor" in source
    assert "apply_backend_projection" in source
    assert "reject_backend_intent" in source
    assert "apply_backend_replay_timeline" in source
    assert "backend_projection_summary" in source
    assert "build_typed_draft" in source
    assert "declaration_digest" not in source
    assert "content_digest" not in source
    assert "binding_ref" not in source
    assert "load(" not in source
    assert "send_envelope" not in source


def test_procedural_construction_editor_runtime_probe_exercises_backend_mirror_contract() -> None:
    probe = ROOT / "scripts" / "verification" / "ProceduralConstructionEditorRuntimeProbe.gd"

    assert probe.exists()
    source = probe.read_text(encoding="utf-8")
    assert "ProceduralConstructionEditor.tscn" in source
    assert "preview_placement" in source
    assert "apply_backend_projection" in source
    assert "reject_backend_intent" in source
    assert "build_typed_draft" in source
