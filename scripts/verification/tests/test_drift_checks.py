from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from check_drift import evaluate_drift
from common import repo_root


def test_evaluate_drift_proves_cleanup_invariants() -> None:
    report = evaluate_drift(repo_root())
    statuses = {entry["id"]: entry["status"] for entry in report["results"]}

    assert statuses["temporary_browser_artifacts_absent"] == "proved"
    assert statuses["harness_artifacts_are_gitignored"] == "proved"
    assert statuses["harness_registry_is_versionable"] == "proved"
    assert statuses["verification_scripts_have_tests"] == "proved"


def test_evaluate_drift_rejects_broad_harness_gitignore(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text(
        ".harness/\n__pycache__/\n.pytest_cache/\n",
        encoding="utf-8",
    )
    (tmp_path / ".harness" / "profiles").mkdir(parents=True)
    (tmp_path / ".harness" / "rules").mkdir(parents=True)
    (tmp_path / ".harness" / "profiles" / "docs.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".harness" / "rules" / "docs-rules.json").write_text("{}", encoding="utf-8")

    for path in [
        "scripts/verification/tests/test_boundary_checks.py",
        "scripts/verification/tests/test_docs_checks.py",
        "scripts/verification/tests/test_drift_checks.py",
        "scripts/verification/tests/test_harness_registry.py",
        "scripts/verification/tests/test_harness_runner.py",
        "scripts/verification/tests/test_runtime_trace.py",
    ]:
        file_path = tmp_path / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("", encoding="utf-8")

    report = evaluate_drift(tmp_path)
    statuses = {entry["id"]: entry["status"] for entry in report["results"]}

    assert statuses["harness_registry_is_versionable"] == "missing"
