from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from registry import load_profile_registry

import verify_phase5b_relationship_reputation_knowledge as verifier


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_phase5b_profile_is_explicit_only() -> None:
    registry = load_profile_registry(PROJECT_ROOT)

    profile = registry.profiles["phase5b-relationship-reputation-knowledge"]
    assert profile["script"] == "scripts/verification/verify_phase5b_relationship_reputation_knowledge.py"
    assert profile["order"] == 123
    assert profile["include_in_profile_order"] is False
    assert profile["requires_godot"] is False
    assert profile["max_attempts"] == 1
    assert profile["result_artifact"] == ".harness/verification/phase5b-relationship-reputation-knowledge-report.json"


def test_phase5b_verifier_uses_required_focused_tests() -> None:
    assert verifier.TEST_FILES == (
        "backend/tests/test_p5_social_knowledge.py",
        "backend/tests/test_p5_quest_evidence.py",
        "backend/tests/test_p5_contracts.py",
        "backend/tests/test_gameplay_p5_batch_contract.py",
    )


def test_phase5b_build_report_fails_closed_when_focused_tests_fail() -> None:
    report = verifier.build_report(
        focused_ok=False,
        focused_log="focused failure",
        scenario=verifier.Phase5bScenarioEvidence(
            provenance={"provider_ref": "provider:evidence:social-observer"},
            permission_redaction={"public_knowledge_count": 0},
            decision_receipt={"result_kind": "committed_success"},
            replay_hash={"projection_hash": "sha256:abc"},
            failure_zero_write={"failure_code": "p5_revision_stale", "zero_write": True},
        ),
    )

    assert report["overall_passed"] is False
    assert report["focused_log"] == "focused failure"
    assert report["provenance"]["provider_ref"] == "provider:evidence:social-observer"
    assert report["permission_redaction"]["public_knowledge_count"] == 0
    assert report["replay_hash"]["projection_hash"] == "sha256:abc"
    assert report["failure_zero_write"]["zero_write"] is True
    assert report["focused_test_files"] == list(verifier.TEST_FILES)


def test_phase5b_build_report_includes_required_evidence_sections() -> None:
    report = verifier.build_report(
        focused_ok=True,
        focused_log="focused pass",
        scenario=verifier.Phase5bScenarioEvidence(
            provenance={"provider_ref": "provider:evidence:social-observer"},
            permission_redaction={"public_knowledge_count": 0},
            decision_receipt={"result_kind": "committed_success"},
            replay_hash={"projection_hash": "sha256:abc"},
            failure_zero_write={"failure_code": "p5_revision_stale", "zero_write": True},
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


def test_phase5b_main_returns_verifier_exit_code(monkeypatch) -> None:
    written: dict[str, object] = {}

    monkeypatch.setattr(verifier, "run_focused", lambda *tests: (False, "focused red"))
    monkeypatch.setattr(
        verifier,
        "collect_phase5b_scenario_evidence",
        lambda: verifier.Phase5bScenarioEvidence(
            provenance={"provider_ref": "provider:evidence:social-observer"},
            permission_redaction={"public_knowledge_count": 0},
            decision_receipt={"result_kind": "committed_success"},
            replay_hash={"projection_hash": "sha256:abc"},
            failure_zero_write={"failure_code": "p5_revision_stale", "zero_write": True},
        ),
    )

    def fake_write_report(name: str, report: dict[str, object]) -> int:
        written["name"] = name
        written["report"] = report
        return 1

    monkeypatch.setattr(verifier, "write_report", fake_write_report)

    exit_code = verifier.main([])

    assert exit_code == 1
    assert written["name"] == "phase5b-relationship-reputation-knowledge"
    report = written["report"]
    assert isinstance(report, dict)
    assert report["overall_passed"] is False
    assert report["focused_tests_passed"] is False
    assert report["focused_test_files"] == list(verifier.TEST_FILES)
