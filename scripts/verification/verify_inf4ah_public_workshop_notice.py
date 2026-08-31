from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    cases = {
        "exact_source_and_append": ("backend/tests/test_inf4ah_public_workshop_notice.py", "test_inf4ah_records_project_public_workshop_notice_from_exact_activity"),
        "zero_write_privacy_duplicate": ("backend/tests/test_inf4ah_public_workshop_notice.py", "test_inf4ah_notice_duplicate_changed_duplicate_private_and_wrong_source_are_zero_write"),
        "full_tail_replay": ("backend/tests/test_inf4ah_public_workshop_notice.py", "test_inf4ah_notice_full_and_checkpoint_tail_replay_match"),
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, (relative, selector) in cases.items():
        log_path = verification_dir(root) / f"inf4ah-public-workshop-notice-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{root / relative}::{selector}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "inf4ah-public-workshop-notice",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": ["backend/tests/test_inf4ah_public_workshop_notice.py"],
        "evidence": evidence,
        "run_id": f"inf4ah-public-workshop-notice-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "row": "fulfilled INF-4AG public workshop activity -> Government project public notice",
        "owner": "actor_gameplay.government_domain",
        "stream": "gameplay:government:public-notice:{jurisdiction_ref}",
        "event_type": "gameplay.government.public_workshop_notice_recorded",
        "privacy": "project",
        "boundaries": [
            "exact INF-4AG activity and Contract provenance",
            "facility/project/jurisdiction binding",
            "append-derived Government receipt",
            "full/checkpoint-tail replay",
            "no contract, account, payment, participant, social or population payload",
        ],
    }
    path = verification_dir(root) / "inf4ah-public-workshop-notice-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-4AH Public Workshop Notice Report",
        {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"inf4ah_public_workshop_notice_report_json={path}")
    print(f"overall_inf4ah_public_workshop_notice_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
