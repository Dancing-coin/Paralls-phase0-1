from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from registry import load_profile_registry


PROJECT_ROOT = Path(__file__).resolve().parents[3]
VERIFIER_PATH = PROJECT_ROOT / "scripts" / "verification" / "verify_phase5c_investigation_stealth_conflict.py"


def _load_verifier_module():
    assert VERIFIER_PATH.exists(), f"missing verifier script: {VERIFIER_PATH}"
    spec = importlib.util.spec_from_file_location("phase5c_verifier", VERIFIER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_phase5c_profile_is_explicit_only() -> None:
    registry = load_profile_registry(PROJECT_ROOT)

    assert "phase5c-investigation-stealth-conflict" in registry.profiles
    profile = registry.profiles["phase5c-investigation-stealth-conflict"]
    assert profile["script"] == "scripts/verification/verify_phase5c_investigation_stealth_conflict.py"
    assert profile["order"] == 124
    assert profile["include_in_profile_order"] is False
    assert profile["requires_godot"] is False
    assert profile["max_attempts"] == 1
    assert profile["result_artifact"] == ".harness/verification/phase5c-investigation-stealth-conflict-report.json"


def test_phase5c_verifier_uses_required_focused_tests() -> None:
    verifier = _load_verifier_module()

    assert verifier.TEST_FILES == (
        "backend/tests/test_p5_investigation_conflict.py",
        "backend/tests/test_p5_social_knowledge.py",
        "backend/tests/test_p5_quest_evidence.py",
        "backend/tests/test_p5_contracts.py",
        "backend/tests/test_gameplay_p5_batch_contract.py",
    )


def test_phase5c_build_report_fails_closed_when_focused_tests_fail() -> None:
    verifier = _load_verifier_module()

    report = verifier.build_report(
        focused_ok=False,
        focused_log="focused failure",
        scenario=verifier.Phase5cScenarioEvidence(
            provenance={"perception_visibility": "public"},
            permission_redaction={"public_hidden_clue_redacted": True},
            decision_receipt={"result_kind": "committed_adverse_outcome"},
            replay_hash={"full_replay_hash": "sha256:abc"},
            failure_zero_write={"failure_code": "p5_perception_hidden", "zero_write": True},
        ),
    )

    assert report["overall_passed"] is False
    assert report["focused_tests_passed"] is False
    assert report["focused_log"] == "focused failure"
    assert report["focused_test_files"] == list(verifier.TEST_FILES)
    assert report["provenance"]["perception_visibility"] == "public"
    assert report["permission_redaction"]["public_hidden_clue_redacted"] is True
    assert report["decision_receipt"]["result_kind"] == "committed_adverse_outcome"
    assert report["replay_hash"]["full_replay_hash"] == "sha256:abc"
    assert report["failure_zero_write"]["zero_write"] is True


def test_phase5c_build_report_includes_required_evidence_sections() -> None:
    verifier = _load_verifier_module()

    report = verifier.build_report(
        focused_ok=True,
        focused_log="focused pass",
        scenario=verifier.Phase5cScenarioEvidence(
            provenance={"perception_visibility": "public"},
            permission_redaction={"public_hidden_clue_redacted": True},
            decision_receipt={"result_kind": "committed_adverse_outcome"},
            replay_hash={"full_replay_hash": "sha256:abc"},
            failure_zero_write={"failure_code": "p5_perception_hidden", "zero_write": True},
        ),
    )

    assert set(report) >= {
        "overall_passed",
        "focused_tests_passed",
        "focused_test_files",
        "focused_log",
        "provenance",
        "permission_redaction",
        "decision_receipt",
        "replay_hash",
        "failure_zero_write",
    }


def test_phase5c_main_returns_verifier_exit_code(monkeypatch) -> None:
    verifier = _load_verifier_module()
    written: dict[str, object] = {}

    monkeypatch.setattr(verifier, "run_focused", lambda *tests: (False, "focused red"))
    monkeypatch.setattr(
        verifier,
        "collect_phase5c_scenario_evidence",
        lambda: verifier.Phase5cScenarioEvidence(
            provenance={"perception_visibility": "public"},
            permission_redaction={"public_hidden_clue_redacted": True},
            decision_receipt={"result_kind": "committed_adverse_outcome"},
            replay_hash={"full_replay_hash": "sha256:abc"},
            failure_zero_write={"failure_code": "p5_perception_hidden", "zero_write": True},
        ),
    )

    def fake_write_report(name: str, report: dict[str, object]) -> int:
        written["name"] = name
        written["report"] = report
        return 1

    monkeypatch.setattr(verifier, "write_report", fake_write_report)

    exit_code = verifier.main([])

    assert exit_code == 1
    assert written["name"] == "phase5c-investigation-stealth-conflict"
    report = written["report"]
    assert isinstance(report, dict)
    assert report["overall_passed"] is False
    assert report["focused_tests_passed"] is False
    assert report["focused_test_files"] == list(verifier.TEST_FILES)
