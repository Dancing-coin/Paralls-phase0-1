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


def test_verifier_uses_temporary_sqlite_owned_by_verifier(tmp_path: Path) -> None:
    evidence = verifier.collect_graph_evidence(tmp_path)
    database = Path(evidence["sqlite_database"])
    assert database.exists()
    assert database.parent == Path(evidence["temporary_directory"])
    assert str(database).startswith(str(tmp_path))


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
