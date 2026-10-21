import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts/verification/verify_character_laya_evaluation.py"
FIXTURE = REPO / "backend/tests/fixtures/character_evaluation/four_role_lock_event"


def evaluator():
    assert SCRIPT.is_file(), "missing fail-closed evaluation preflight"
    spec = importlib.util.spec_from_file_location("character_laya_evaluation", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_source_freeze_does_not_release_unprepared_four_role_quality():
    report = evaluator().audit_fixture(REPO, FIXTURE)
    assert report["source_status"] == "source_frozen"
    assert report["status"] == "evaluation_blocked"
    assert report["provider_calls"] == 0
    assert report["fine_tuning"] == "not_assessable"
    assert report["splits"]["calibration"] == "not_run"
    assert report["splits"]["final"] == "not_run"
    assert report["splits"]["independent_holdout"] == "not_run"
    assert "char_d_profile_schema_unresolved" in report["blockers"]
    assert "acceptable_actions_unreviewed" in report["blockers"]
    assert report["tracks"]["base_selection"]["denominator"] == 0
    assert report["tracks"]["base_selection"]["accuracy"] is None


def test_source_content_change_invalidates_frozen_source(tmp_path):
    module = evaluator()
    changed = tmp_path / "profile.yaml"
    changed.write_text("actor: changed", encoding="utf-8")
    assert module.check_source_pins(tmp_path, [{"path": "profile.yaml", "sha256": "0" * 64}]) == ["source_changed:profile.yaml"]


def test_preflight_never_opens_final_labels(tmp_path, monkeypatch):
    module = evaluator()
    manifest = yaml.safe_load((FIXTURE / "manifest.yaml").read_text(encoding="utf-8"))
    manifest["final_labels_path"] = "must-not-open.yaml"
    (tmp_path / "manifest.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    for name in ("splits.yaml", "development_inputs.yaml", "acceptable_actions.yaml"):
        (tmp_path / name).write_bytes((FIXTURE / name).read_bytes())
    final_path = tmp_path / "must-not-open.yaml"
    final_path.write_text("sealed_final_labels: do_not_read", encoding="utf-8")
    original = Path.open
    def guard(path, *args, **kwargs):
        if path.resolve() == final_path.resolve():
            raise AssertionError("preflight read final labels")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", guard)
    report = module.audit_fixture(REPO, tmp_path)
    assert report["final_labels_read"] is False
    assert report["status"] == "evaluation_blocked"


def test_role_variants_cannot_cross_split_boundary(tmp_path):
    module = evaluator()
    splits = {"development": ["trajectory:one"], "calibration": ["trajectory:one"], "final": [], "independent_holdout": []}
    assert module.check_split_isolation(splits) == ["trajectory_leakage:trajectory:one"]


def row(**changes):
    return {"track": "base_selection", "legal_target": True, "input_valid": True, "question_valid": True,
            "candidates_valid": True, "acceptable_presented": True,
            "raw_choice_acceptable": True, "fallback": False, "slow_model": False,
            "timeout": False, "latency_ms": 25.0, **changes}


def test_no_legal_target_is_excluded_and_slow_fallback_cannot_repair_accuracy():
    result = evaluator().score_records([
        row(legal_target=False), row(), row(fallback=True, slow_model=True), row(timeout=True)
    ], "base_selection")
    assert result["denominator"] == 3
    assert result["conditional_denominator"] == 3
    assert result["hits"] == 1
    assert result["accuracy"] == pytest.approx(1 / 3)
    assert result["fallback_count"] == 1
    assert result["slow_model_count"] == 1
    assert result["timeout_count"] == 1
    assert result["excluded_no_legal_target"] == 1


def test_slow_model_and_unknown_target_cannot_improve_laya_quality():
    result = evaluator().score_records([
        row(slow_model=True),
        row(legal_target="unknown"),
    ], "base_selection")
    assert result["denominator"] == 1
    assert result["hits"] == 0
    assert result["accuracy"] == 0.0
    assert result["slow_model_count"] == 1
    assert result["excluded_no_legal_target"] == 1


def test_candidate_defects_are_kept_in_end_to_end_but_not_conditional_denominator():
    result = evaluator().score_records([row(), row(candidates_valid=False)], "base_selection")
    assert result["denominator"] == 2
    assert result["conditional_denominator"] == 1
    assert result["hits"] == 1
    assert result["accuracy"] == 0.5


def test_input_or_question_errors_are_excluded_from_model_quality():
    result = evaluator().score_records([row(), row(input_valid=False), row(question_valid=False)], "base_selection")
    assert result["denominator"] == 1
    assert result["hits"] == 1
    assert result["excluded_input_or_question_error"] == 2


def test_missing_pin_cannot_report_source_frozen(tmp_path):
    manifest = yaml.safe_load((FIXTURE / "manifest.yaml").read_text(encoding="utf-8"))
    manifest["source_pins"] = []
    (tmp_path / "manifest.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    result = evaluator().audit_fixture(REPO, tmp_path)
    assert result["source_status"] != "source_frozen"


def test_empty_and_performance_tracks_are_never_counted_as_base_quality():
    result = evaluator().score_records([row(track="character_performance")], "base_selection")
    assert result["status"] == "not_run"
    assert result["accuracy"] is None
    assert result["denominator"] == 0


def test_claimed_freeze_flags_cannot_turn_missing_live_inputs_into_quality_pass(tmp_path):
    module = evaluator()
    manifest = yaml.safe_load((FIXTURE / "manifest.yaml").read_text(encoding="utf-8"))
    manifest["freeze"] = {gate: True for gate in ("policy", "questions", "candidates", "thresholds", "calibration_method")}
    manifest["policy_revision"] = "policy:claimed-frozen"
    manifest["quality_thresholds"] = {"selection": 1.0}
    manifest["calibration_method"] = "claimed"
    (tmp_path / "manifest.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    for name in ("splits.yaml", "development_inputs.yaml", "acceptable_actions.yaml"):
        (tmp_path / name).write_bytes((FIXTURE / name).read_bytes())
    result = module.audit_fixture(REPO, tmp_path)
    assert result["status"] == "evaluation_blocked"
    assert "development_missing:frozen_mind_frame" in result["blockers"]
    assert "official_baseline_not_run" in result["blockers"]


def test_cli_exports_raw_diagnosis_and_cleans_owned_scope(tmp_path):
    exported = tmp_path / "evidence"
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--export-evidence", str(exported)],
        cwd=REPO, text=True, encoding="utf-8", capture_output=True, timeout=30,
    )
    assert completed.returncode == 2
    assert "harness_cleanup=passed" in completed.stdout
    report = json.loads((exported / "character-laya-evaluation-preflight.json").read_text(encoding="utf-8"))
    assert report["status"] == "evaluation_blocked"
    assert (exported / "inputs/manifest.yaml").read_bytes() == (FIXTURE / "manifest.yaml").read_bytes()
    marker = json.loads((exported / ".harness-owner.json").read_text(encoding="utf-8"))
    import tempfile
    assert not (Path(tempfile.gettempdir()) / ("paralls-harness-" + marker["run_id"])).exists()
