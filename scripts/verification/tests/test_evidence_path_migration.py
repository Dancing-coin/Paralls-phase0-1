from __future__ import annotations

import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


VERIFICATION_SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VERIFICATION_SCRIPTS))


@pytest.mark.parametrize(
    "module_name",
    ["verify_post_p5_f2_gates", "verify_post_p5_f2_complete", "verify_post_p5_dg_opening"],
)
def test_report_consumers_read_current_evidence_instead_of_repo_residue(tmp_path, monkeypatch, module_name):
    module = importlib.import_module(module_name)
    project = tmp_path / "project"
    stale_report = project / ".harness" / "verification" / "report.json"
    stale_report.parent.mkdir(parents=True)
    stale_report.write_text('{"source": "stale"}', encoding="utf-8")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "report.json").write_text('{"source": "current"}', encoding="utf-8")
    monkeypatch.setattr(
        module,
        "artifact_path",
        lambda root, relative: evidence / Path(relative).name,
        raising=False,
    )

    assert module._read(project, ".harness/verification/report.json") == {"source": "current"}


def test_baseline_producer_resolves_output_when_invoked(tmp_path, monkeypatch):
    module = importlib.import_module("verify_unified_character_action_foundation")
    project = tmp_path / "project"
    project.mkdir()
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    monkeypatch.setattr(module, "ROOT", project)
    monkeypatch.setattr(module, "EVIDENCE_PATH", project / ".harness/verification/baseline.json", raising=False)
    monkeypatch.setattr(module, "verification_dir", lambda root: evidence, raising=False)
    monkeypatch.setattr(module, "verify_baseline", lambda: {"valid": True})
    monkeypatch.setattr(sys, "argv", ["verify_unified_character_action_foundation.py", "--stage", "baseline"])

    assert module.main() == 0
    report = evidence / "unified-character-action-foundation-baseline.json"
    assert json.loads(report.read_text(encoding="utf-8")) == {"valid": True}
    assert not (project / ".harness").exists()


def test_direct_entry_cleans_output_without_creating_repo_harness(tmp_path):
    project = tmp_path / "project"
    scripts = project / "scripts" / "verification"
    scripts.mkdir(parents=True)
    for name in ("common.py", "run_context.py", "process_control.py", "verify_unified_character_action_foundation.py"):
        shutil.copy2(VERIFICATION_SCRIPTS / name, scripts / name)
    ledger = project / "docs" / "character" / "character-action-foundation-current-state.md"
    ledger.parent.mkdir(parents=True)
    ledger.write_text("## Migration Ledger\n", encoding="utf-8")
    scene_dir = project / "scenes" / "phase0"
    scene_dir.mkdir(parents=True)
    for name in ("PlayerShell.tscn", "CharacterReplica.tscn"):
        (scene_dir / name).write_text('type="CharacterBody3D"\nname="CharacterMotor" type="Node" parent="."\n', encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-B", str(scripts / "verify_unified_character_action_foundation.py"), "--stage", "baseline"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert '"valid": true' in result.stdout
    assert not (project / ".harness").exists()


def test_vla_capture_accepts_current_run_evidence_outside_project(tmp_path):
    from common import artifact_path
    from run_context import run_scope
    from vla_live_proof_artifact import GODOT_RUNTIME_CAPTURE, GODOT_RUNTIME_REPORT, resolve_live_proof_image

    project = tmp_path / "project"
    project.mkdir()
    with run_scope(project) as run:
        capture = artifact_path(project, GODOT_RUNTIME_CAPTURE)
        capture.write_bytes(b"\x89PNG\r\n\x1a\n")
        artifact_path(project, GODOT_RUNTIME_REPORT).write_text(
            json.dumps({"status": "godot-runtime-sampling-verified", "artifact_ref": "runtime://artifact/" + capture.as_posix()}),
            encoding="utf-8",
        )
        image = resolve_live_proof_image(
            project,
            configured_url="",
            configured_path="",
            use_godot_runtime_capture=True,
            max_godot_capture_age_seconds=60,
        )
        assert image.source.startswith("data:image/png;base64,")
        assert not (project / ".harness").exists()
    assert not run.evidence_root.exists()
