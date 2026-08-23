from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts" / "verification"))

import verify_heavenly_graph_semantic_foundation as verifier


def test_profile_manifest_is_graph_only_and_stable() -> None:
    profile = json.loads(
        (ROOT / ".harness" / "profiles" / "heavenly-graph-semantic-foundation.json").read_text(
            encoding="utf-8"
        )
    )
    assert profile["name"] == "heavenly-graph-semantic-foundation"
    assert profile["order"] == 79
    assert profile["requires_godot"] is False
    assert profile["script"] == "scripts/verification/verify_heavenly_graph_semantic_foundation.py"
    assert profile["result_artifact"] == ".harness/verification/heavenly-graph-semantic-foundation-report.json"
    assert "graph-only" in profile["description"]


def test_verifier_report_ids_and_graph_only_evidence(tmp_path: Path) -> None:
    report = verifier.run_verification(tmp_path)
    assert report["overall_heavenly_graph_semantic_foundation_passed"] is True
    ids = [item["id"] for item in report["results"]]
    assert ids == list(verifier.RESULT_IDS)
    assert set(report["artifacts"]) >= {"sqlite_database", "pytest_log"}
    assert all("role" not in json.dumps(item).lower() for item in report["results"])
    assert all("simingruntime" not in json.dumps(item).lower() for item in report["results"])


def test_verifier_runs_the_complete_graph_contract_suite() -> None:
    assert verifier.GRAPH_TEST_FILES == (
        "backend/tests/heavenly_graph_contract.py",
        "backend/tests/test_sqlite_heavenly_graph_contract.py",
        "backend/tests/test_heavenly_graph_semantics.py",
        "backend/tests/test_heavenly_graph_semantic_queries.py",
        "backend/tests/test_heavenly_graph_branch_lifecycle.py",
        "backend/tests/test_heavenly_graph_consistency.py",
    )


def test_verifier_uses_temporary_sqlite_owned_by_verifier(tmp_path: Path) -> None:
    evidence = verifier.collect_graph_evidence(tmp_path)
    database = Path(evidence["sqlite_database"])
    assert database.exists()
    assert database.parent == Path(evidence["temporary_directory"])
    assert str(database).startswith(str(tmp_path))


def test_every_required_proof_requires_in_memory_sqlite_parity(tmp_path: Path) -> None:
    evidence = verifier.collect_graph_evidence(tmp_path)
    assert set(evidence["adapter_checks"]) == {"in_memory", "sqlite"}
    for check_id in verifier.RESULT_IDS[1:]:
        assert evidence["adapter_checks"]["in_memory"][check_id] is True
        assert evidence["adapter_checks"]["sqlite"][check_id] is True
        assert evidence["checks"][check_id] is True


def test_report_uses_stable_evidence_markers_after_temp_cleanup(tmp_path: Path) -> None:
    report = verifier.run_verification(tmp_path)
    encoded = json.dumps(report)
    assert str(tmp_path) not in encoded
    assert "heavenly-graph-verify-" not in encoded
    for result in report["results"][1:]:
        assert result["evidence"] == ["verifier-owned-temporary-database"]


@pytest.mark.parametrize(
    "check_id",
    [
        "adapter_parity",
        "semantic_metadata",
        "scope_denial",
        "bounded_results",
        "stale_write_rejection",
        "correction_chain",
        "branch_isolation",
        "replay_digest",
    ],
)
def test_graph_contract_checks_are_proved(check_id: str, tmp_path: Path) -> None:
    report = verifier.run_verification(tmp_path)
    result = next(item for item in report["results"] if item["id"] == check_id)
    assert result["status"] == "proved", result
    assert result["evidence"]


def test_verifier_fails_closed_for_missing_metadata(tmp_path: Path) -> None:
    evidence = verifier.collect_graph_evidence(tmp_path)
    evidence["semantic_metadata"] = False
    report = verifier.evaluate_evidence(evidence)
    assert report["overall"] is False
    assert report["checks"]["semantic_metadata"] is False


@pytest.mark.parametrize("check_id", verifier.RESULT_IDS[1:])
def test_verifier_fails_closed_for_each_missing_graph_proof(check_id: str, tmp_path: Path) -> None:
    evidence = verifier.collect_graph_evidence(tmp_path)
    evidence["checks"][check_id] = False
    report = verifier.evaluate_evidence(evidence)
    assert report["overall"] is False
    assert report["checks"][check_id] is False


def test_run_verification_fails_closed_when_focused_pytest_fails(tmp_path: Path) -> None:
    report = verifier.run_verification(tmp_path, focused_exit_code=1)
    focused = report["results"][0]
    assert report["overall_heavenly_graph_semantic_foundation_passed"] is False
    assert focused["id"] == "focused_contract_tests"
    assert focused["status"] == "missing"
