from __future__ import annotations

from datetime import datetime, timezone

from common import (
    evidence_revision,
    repo_root,
    resolve_python_exe,
    run_command,
    verification_dir,
    write_json,
    write_markdown,
)


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    cases = {
        "exact_source_and_append": (
            "backend/tests/test_inf4aj_public_project_execution.py",
            "test_inf4aj_records_one_funded_and_executed_project_fact",
        ),
        "zero_write_duplicate_privacy_revision": (
            "backend/tests/test_inf4aj_public_project_execution.py",
            "test_inf4aj_duplicate_changed_duplicate_private_stale_and_mismatched_sources_are_zero_write",
        ),
        "catalog_contract": (
            "backend/tests/test_inf4aj_public_project_execution.py",
            "test_inf4aj_catalog_pins_exact_existing_organization_owner_contract",
        ),
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, (relative, selector) in cases.items():
        log_path = verification_dir(root) / f"inf4aj-public-project-execution-{check}.log"
        result = run_command(
            [python, "-m", "pytest", "-q", f"{root / relative}::{selector}"],
            root,
            log_path,
        )
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "inf4aj-public-project-execution",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": ["backend/tests/test_inf4aj_public_project_execution.py"],
        "evidence": evidence,
        "run_id": f"inf4aj-public-project-execution-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "row": "INF-4AG project activity + INF-2AI authority-only budget consumption -> Organization project execution",
        "owner": "actor_gameplay.organization_domain",
        "stream": "gameplay:organization:{organization_ref}",
        "event_type": "gameplay.organization.public_project_execution_recorded",
        "privacy": "project",
        "semantic": "funded_and_executed",
        "boundaries": [
            "fixed municipal-assessment-office facility/project binding",
            "exact INF-4AG provider/service/policy/descriptor source pins",
            "exact INF-2AI catalog/policy/descriptor/terminal source pins",
            "owner-derived idempotency and append-derived receipt",
            "full/checkpoint-tail Organization replay",
            "no payment, debit, release, refund, material, inventory, output, attendance, social or population writer",
        ],
    }
    path = verification_dir(root) / "inf4aj-public-project-execution-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-4AJ Public Project Execution Report",
        {
            "results": [
                {"id": key, "status": "proved" if value else "missing", "title": key}
                for key, value in checks.items()
            ],
            "overall_passed": report["overall_passed"],
        },
        "overall_passed",
    )
    print(f"inf4aj_public_project_execution_report_json={path}")
    print(f"overall_inf4aj_public_project_execution_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
