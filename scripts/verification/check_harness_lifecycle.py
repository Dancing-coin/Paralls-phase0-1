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


def _read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _contains(path: Path, patterns: list[str]) -> bool:
    text = read_text(path)
    return all(pattern in text for pattern in patterns)


def evaluate_harness_lifecycle(project_root: Path) -> dict[str, object]:
    features_path = project_root / ".harness" / "features.json"
    local_ci_gate = project_root / ".harness" / "ci" / "local-ci-gate.ps1"
    profile_template = project_root / ".harness" / "templates" / "profile-template.json"
    rule_template = project_root / ".harness" / "templates" / "rule-template.json"
    retention_policy_path = project_root / ".harness" / "retention-policy.json"
    changes_dir = project_root / ".harness" / "changes"
    change_manifest_template = project_root / ".harness" / "templates" / "change-manifest-template.json"
    harness_guide = project_root / "docs" / "harness.md"
    quality_docs = [
        project_root / ".harness" / "clean-state-checklist.md",
        project_root / ".harness" / "session-handoff.md",
        project_root / ".harness" / "evaluator-rubric.md",
        project_root / ".harness" / "quality-document.md",
        project_root / "docs" / "harness-architecture.md",
        project_root / "docs" / "harness-reliability.md",
    ]

    features = _read_json(features_path)
    feature_entries = features.get("features", [])
    retention_policy = _read_json(retention_policy_path)

    results = [
        _result(
            "lifecycle_feature_ledger_exists",
            "Harness feature ledger exists with pass/evidence entries",
            features.get("schema_version") == 1
            and isinstance(feature_entries, list)
            and len(feature_entries) >= 8
            and all(isinstance(entry, dict) and entry.get("status") == "pass" and entry.get("evidence") for entry in feature_entries),
            [".harness/features.json"],
        ),
        _result(
            "lifecycle_local_ci_gate_exists",
            "Local CI gate exists and runs focused tests, compile, and full harness",
            _contains(
                local_ci_gate,
                [
                    "python -m pytest -q scripts\\verification\\tests",
                    "python -m compileall -q scripts\\verification",
                    "python scripts\\verification\\harness.py --profile all",
                ],
            ),
            [".harness/ci/local-ci-gate.ps1"],
        ),
        _result(
            "lifecycle_templates_exist",
            "Future profile and rule templates exist",
            _contains(profile_template, ['"script"', '"requires_godot"', '"template_variables"'])
            and _contains(rule_template, ['"profile"', '"rules"', '"evidence"']),
            [".harness/templates/profile-template.json", ".harness/templates/rule-template.json"],
        ),
        _result(
            "lifecycle_decision_manifest_surface_exists",
            "Harness decision manifest directory and template exist",
            changes_dir.exists()
            and change_manifest_template.exists()
            and _contains(
                change_manifest_template,
                [
                    '"schema_version"',
                    '"id"',
                    '"title"',
                    '"status"',
                    '"active"',
                    '"predicted_fixes"',
                    '"predicted_regressions"',
                    '"verification_profiles"',
                ],
            ),
            [".harness/changes/", ".harness/templates/change-manifest-template.json"],
        ),
        _result(
            "lifecycle_decision_observability_docs_exist",
            "Harness guide documents decision observability and failure digest artifacts",
            _contains(
                harness_guide,
                [
                    "Decision Observability",
                    ".harness/changes/",
                    "failure-digest",
                    "harness_changes",
                    "harness_change_errors",
                ],
            ),
            ["docs/harness.md"],
        ),
        _result(
            "lifecycle_retention_policy_exists",
            "Retention policy defines baseline, diff, and run archive handling",
            retention_policy.get("schema_version") == 1
            and int(retention_policy.get("max_archived_runs", 0)) > 0
            and retention_policy.get("preserve_latest_baseline") is True
            and retention_policy.get("diff_against") == "previous_baseline"
            and retention_policy.get("archive_root") == ".harness/verification/runs/",
            [".harness/retention-policy.json"],
        ),
        _result(
            "lifecycle_quality_docs_exist",
            "Quality, handoff, architecture, and reliability docs exist",
            all(path.exists() for path in quality_docs)
            and _contains(project_root / "docs" / "harness-reliability.md", [".harness/retention-policy.json", "local-ci-gate.ps1"])
            and _contains(project_root / "docs" / "harness-architecture.md", [".harness/profiles", ".harness/rules"]),
            [str(path.relative_to(project_root)).replace("\\", "/") for path in quality_docs],
        ),
    ]
    return {
        "results": results,
        "overall_harness_lifecycle_passed": all(str(entry["status"]) == "proved" for entry in results),
    }


def main() -> int:
    project_root = repo_root()
    report = evaluate_harness_lifecycle(project_root)
    log_dir = verification_dir(project_root)
    json_path = log_dir / "harness-lifecycle-report.json"
    md_path = log_dir / "harness-lifecycle-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Harness Lifecycle Verification Report", report, "overall_harness_lifecycle_passed")

    print(f"harness_lifecycle_report_json={json_path}")
    print(f"harness_lifecycle_report_md={md_path}")
    print(f"overall_harness_lifecycle_passed={report['overall_harness_lifecycle_passed']}")
    for entry in report["results"]:
        print(f"{entry['id']}={entry['status']}")
    return 0 if report["overall_harness_lifecycle_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
