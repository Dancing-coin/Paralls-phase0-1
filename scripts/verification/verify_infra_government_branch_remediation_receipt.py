from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_government_failed_inspection_remediation_scenario.py"
    predecessor_script = root / "scripts" / "verification" / "verify_infra_government_failed_inspection_remediation_scenario.py"
    cases = {
        "durable_receipt_reconstruction": "test_failed_inspection_remediation_receipt_rebuilds_from_durable_event",
        "invalid_event_zero_write": "test_failed_inspection_remediation_receipt_rejects_non_remediation_event_without_write",
        "duplicate_receipt_stability": "test_failed_inspection_remediation_receipt_duplicate_append_rebuilds_stably",
        "receipt_privacy_zero_write": "test_failed_inspection_remediation_receipt_rejects_noncreator_scope_without_write",
        "scenario_checkpoint_tail_replay": "test_failed_inspection_remediation_projection_replays_checkpoint_tail",
        "production_and_promotion_zero_write": "test_failed_inspection_remediation_keeps_production_replay_and_promotion_zero_write",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    predecessor_log = verification_dir(root) / "infra-government-branch-remediation-receipt-predecessor-inf4j.log"
    predecessor = run_command([python, str(predecessor_script)], root, predecessor_log)
    checks["predecessor_inf4j"] = predecessor.returncode == 0
    evidence.append(str(predecessor_log.relative_to(root)).replace("\\", "/"))
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-government-branch-remediation-receipt-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-government-branch-remediation-receipt",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-government-branch-remediation-receipt-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "GovernmentAuthority",
        "stream": "gameplay:government_branch:{branch_ref}:{organization_ref}",
        "event": "gameplay.government.branch_inspection_remediation_recorded",
        "limitations": [
            "The receipt is derived from one existing remediation event and the existing scenario projection.",
            "It creates no receipt event, receipt store, generic receipt, remediation lifecycle or promotion path.",
        ],
    }
    path = verification_dir(root) / "infra-government-branch-remediation-receipt-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-4K Government Branch Remediation Receipt Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_government_branch_remediation_receipt_report_json={path}")
    print(f"overall_infra_government_branch_remediation_receipt_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
