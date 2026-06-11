from __future__ import annotations

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


def evaluate_drift(project_root: Path) -> dict[str, object]:
    temporary_artifacts = [
        ".playwright-mcp",
        "harness-snapshot.md",
    ]
    present_artifacts = [path for path in temporary_artifacts if (project_root / path).exists()]

    gitignore_text = read_text(project_root / ".gitignore")
    gitignore_entries = {line.strip() for line in gitignore_text.splitlines() if line.strip() and not line.lstrip().startswith("#")}
    required_ignored_paths = [".harness/verification/", "__pycache__/", ".pytest_cache/"]
    missing_ignored_paths = [path for path in required_ignored_paths if path not in gitignore_entries]
    broad_harness_ignore_entries = sorted(
        entry
        for entry in gitignore_entries
        if entry.strip("/") == ".harness" or entry in {".harness/**", "/.harness/**"}
    )

    registry_files = sorted((project_root / ".harness" / "profiles").glob("*.json"))
    rule_files = sorted((project_root / ".harness" / "rules").glob("*.json"))
    missing_registry_inputs = []
    if not registry_files:
        missing_registry_inputs.append(".harness/profiles/*.json")
    if not rule_files:
        missing_registry_inputs.append(".harness/rules/*.json")
    missing_registry_inputs.extend(broad_harness_ignore_entries)

    required_test_files = [
        "scripts/verification/tests/test_boundary_checks.py",
        "scripts/verification/tests/test_docs_checks.py",
        "scripts/verification/tests/test_drift_checks.py",
        "scripts/verification/tests/test_formal_profile_checks.py",
        "scripts/verification/tests/test_harness_registry.py",
        "scripts/verification/tests/test_harness_runner.py",
        "scripts/verification/tests/test_runtime_trace.py",
    ]
    missing_tests = [path for path in required_test_files if not (project_root / path).exists()]

    results = [
        _result(
            "temporary_browser_artifacts_absent",
            "Temporary browser/snapshot artifacts are absent from the workspace root",
            not present_artifacts,
            temporary_artifacts,
            "\n".join(present_artifacts),
        ),
        _result(
            "harness_artifacts_are_gitignored",
            "Generated harness evidence and Python cache artifacts are gitignored",
            not missing_ignored_paths,
            required_ignored_paths,
            "\n".join(missing_ignored_paths),
        ),
        _result(
            "harness_registry_is_versionable",
            "Harness profile and rule registry inputs exist and are not hidden by a broad .harness ignore",
            not missing_registry_inputs,
            [
                *[str(path.relative_to(project_root)).replace("\\", "/") for path in registry_files],
                *[str(path.relative_to(project_root)).replace("\\", "/") for path in rule_files],
            ],
            "\n".join(missing_registry_inputs),
        ),
        _result(
            "verification_scripts_have_tests",
            "Harness verification helpers have focused tests",
            not missing_tests,
            required_test_files,
            "\n".join(missing_tests),
        ),
    ]
    return {
        "results": results,
        "overall_drift_passed": all(str(entry["status"]) == "proved" for entry in results),
    }


def main() -> int:
    project_root = repo_root()
    report = evaluate_drift(project_root)
    log_dir = verification_dir(project_root)
    json_path = log_dir / "drift-report.json"
    md_path = log_dir / "drift-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Cleanup Drift Verification Report", report, "overall_drift_passed")

    print(f"drift_report_json={json_path}")
    print(f"drift_report_md={md_path}")
    print(f"overall_drift_passed={report['overall_drift_passed']}")
    for entry in report["results"]:
        print(f"{entry['id']}={entry['status']}")
    return 0 if report["overall_drift_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
