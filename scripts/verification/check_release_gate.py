from __future__ import annotations

import json
from pathlib import Path

from common import read_text, repo_root, verification_dir, write_json, write_markdown


def _result(result_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {
        "id": result_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
        "notes": notes,
    }


def _metadata(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def evaluate_release_gate(project_root: Path) -> dict[str, object]:
    metadata_path = project_root / ".harness" / "ci" / "release-gate.json"
    local_ci_gate_path = project_root / ".harness" / "ci" / "local-ci-gate.ps1"
    workflow_path = project_root / ".github" / "workflows" / "harness.yml"
    metadata = _metadata(metadata_path)
    workflow_text = read_text(workflow_path)
    local_ci_gate_text = read_text(local_ci_gate_path)

    results = [
        _result(
            "release_gate_metadata_exists",
            "Release gate metadata points at the full harness profile",
            metadata.get("schema_version") == 1
            and metadata.get("required_profile") == "all"
            and metadata.get("ci_workflow") == ".github/workflows/harness.yml",
            [".harness/ci/release-gate.json"],
        ),
        _result(
            "ci_harness_workflow_exists",
            "CI harness workflow exists",
            workflow_path.exists(),
            [".github/workflows/harness.yml"],
        ),
        _result(
            "ci_runs_full_harness_profile",
            "CI workflow invokes the full harness profile",
            "python scripts/verification/harness.py --profile all" in workflow_text,
            [".github/workflows/harness.yml"],
        ),
        _result(
            "local_ci_gate_exists",
            "Local CI-equivalent gate exists",
            metadata.get("local_ci_gate") == ".harness/ci/local-ci-gate.ps1" and local_ci_gate_path.exists(),
            [".harness/ci/local-ci-gate.ps1"],
        ),
        _result(
            "local_ci_gate_matches_release_profile",
            "Local CI-equivalent gate invokes the same full harness profile",
            "python scripts\\verification\\harness.py --profile all" in local_ci_gate_text
            and "python -m pytest -q scripts\\verification\\tests" in local_ci_gate_text,
            [".harness/ci/local-ci-gate.ps1"],
        ),
    ]
    return {
        "results": results,
        "overall_release_gate_passed": all(str(entry["status"]) == "proved" for entry in results),
    }


def main() -> int:
    project_root = repo_root()
    report = evaluate_release_gate(project_root)
    log_dir = verification_dir(project_root)
    json_path = log_dir / "release-gate-report.json"
    md_path = log_dir / "release-gate-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Release Gate Verification Report", report, "overall_release_gate_passed")

    print(f"release_gate_report_json={json_path}")
    print(f"release_gate_report_md={md_path}")
    print(f"overall_release_gate_passed={report['overall_release_gate_passed']}")
    for entry in report["results"]:
        print(f"{entry['id']}={entry['status']}")
    return 0 if report["overall_release_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
