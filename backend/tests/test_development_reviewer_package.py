import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1].parent
FIXTURE = ROOT / "backend/tests/fixtures/character_evaluation/four_role_preparation"


def _module():
    path = ROOT / "scripts/verification/build_development_reviewer_package.py"
    spec = importlib.util.spec_from_file_location("reviewer_package", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reviewer_package_excludes_policy_answers_and_keeps_two_tracks():
    package = _module().build(
        role_sensitive_path=FIXTURE / "role-sensitive-development.yaml",
        development_package={"split": "development", "final_labels_read": False},
    )
    assert package["independent_review_approved"] is False
    assert {row["question_kind"] for row in package["scenarios"]} == {
        "autonomous_decision", "explicit_instruction_diagnostic"
    }
    text = json.dumps(package, ensure_ascii=False).lower()
    for forbidden in ("acceptable_paths", "acceptable_pairs", "gold", "raw_response", "rationale"):
        assert forbidden not in text
    assert all(item["runtime_legality"] == "unverified" for row in package["scenarios"] for item in row["candidates"])


def test_reviewer_package_mapping_and_descriptions_are_reproducible():
    builder = _module()
    first = builder.build(role_sensitive_path=FIXTURE / "role-sensitive-development.yaml", development_package={"x": 1})
    second = builder.build(role_sensitive_path=FIXTURE / "role-sensitive-development.yaml", development_package={"x": 1})
    assert first == second
    assert all(row["mapping_digest"].startswith("sha256:") for row in first["scenarios"])


def test_original_development_facts_are_included_without_authored_truth():
    record = {
        "scenario_id": "old-scenario", "actor_id": "char_a", "split": "development",
        "trajectory_group": "old-trajectory",
        "visible_evidence": {"event": "An exterior mark is visible", "question": "Inspect evidence", "targets": ["obj:door", "actor:clerk"]},
        "complete_u": ["observe:obj:door", "ask_probe:actor:clerk", "defer:obj:door"],
        "grading": {"acceptable_pairs": [["observe", "obj:door"]]},
    }
    package = _module().build(role_sensitive_path=FIXTURE / "role-sensitive-development.yaml", development_package={"records": [record]})
    row = next(row for row in package["scenarios"] if row["scenario_id"] == "old-scenario")
    assert row["question_kind"] == "explicit_instruction_diagnostic"
    assert row["cohort"] == "description_frozen_regression"
    assert row["facts"]["event"] == record["visible_evidence"]["event"]
    assert "acceptable_pairs" not in json.dumps(package)
    assert {item["action_family"] for item in row["candidate_records"]} == {"observe", "ask_probe", "defer"}


def test_reviewer_rejects_leakage_in_values():
    import pytest
    with pytest.raises(ValueError, match="forbidden"):
        _module()._assert_clean({"facts": "acceptable_paths: use a leaked answer"})
