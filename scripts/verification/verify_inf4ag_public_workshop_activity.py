from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    cases = {
        "exact_source_and_append": (
            "backend/tests/test_inf4ag_public_workshop_activity.py",
            "test_inf4ag_records_exact_fulfilled_public_workshop_activity",
        ),
        "zero_write_privacy_duplicate": (
            "backend/tests/test_inf4ag_public_workshop_activity.py",
            "test_inf4ag_activity_duplicate_changed_duplicate_and_private_source_are_zero_write",
        ),
        "full_tail_replay": (
            "backend/tests/test_inf4ag_public_workshop_activity.py",
            "test_inf4ag_activity_full_and_checkpoint_tail_replay_match",
        ),
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, (relative, selector) in cases.items():
        log_path = verification_dir(root) / f"inf4ag-public-workshop-activity-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{root / relative}::{selector}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "inf4ag-public-workshop-activity",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": ["backend/tests/test_inf4ag_public_workshop_activity.py"],
        "evidence": evidence,
        "run_id": f"inf4ag-public-workshop-activity-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "row": "fulfilled INF-2AG public-workshop Contract -> existing Organization activity record",
        "owner": "actor_gameplay.organization_domain",
        "stream": "gameplay:organization:{provider_ref}",
        "event_type": "gameplay.organization.public_workshop_activity_recorded",
        "privacy": "project",
        "boundaries": [
            "exact public-workshop Contract terms and provider binding",
            "facility/project proof and Contract revision fence",
            "append-derived Organization receipt",
            "full/checkpoint-tail replay",
            "no payment, social relationship, population, attendance roster, or generic activity writer",
        ],
    }
    path = verification_dir(root) / "inf4ag-public-workshop-activity-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-4AG Public Workshop Activity Report",
        {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"inf4ag_public_workshop_activity_report_json={path}")
    print(f"overall_inf4ag_public_workshop_activity_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
