from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_branch_work_wage_owner_admission.py"
    cases = {
        "success_and_existing_owner_receipt": "test_inf4t_commits_only_existing_economy_wage_for_committed_production_and_valid_branch_request",
        "branch_only_zero_write": "test_inf4t_rejects_branch_only_or_forged_pins_without_write",
        "privacy_revision_target_zero_write": "test_inf4t_rejects_worker_privacy_revision_and_caller_target_fields_without_write",
        "idempotency_and_replay": "test_inf4t_exact_duplicate_replays_changed_duplicate_is_zero_write_and_replay_is_separate",
        "branch_privacy_and_no_compensation": "test_inf4t_branch_scope_is_creator_debug_and_no_combined_or_compensation_surface_exists",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-branch-work-wage-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-branch-work-wage-owner-admission",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-branch-work-wage-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owners": ["ConstructionProductionAuthority", "EconomyAuthority"],
        "branch_read_surface": "BranchPreviewAuthority.durable_branch_projection",
        "source_event": "gameplay.construction_production.work_completion_evidence_recorded",
        "target_event": "gameplay.economy.wage_accrued",
        "target_stream": "gameplay:economy:wage:{worker_ref}",
        "write_path": "typed branch request -> canonical Production reread -> existing Economy owner -> GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()",
        "receipt_boundary": "one Economy owner receipt only; branch snapshot and Production evidence remain separate histories",
        "limitations": [
            "Branch candidates are request metadata only and never replace committed Production evidence.",
            "No branch owner, promotion writer, router, registry, payroll, payment, compensation, or combined receipt is admitted.",
        ],
    }
    path = verification_dir(root) / "infra-branch-work-wage-owner-admission-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-4T Branch Work To Economy Wage Owner-Admission Report",
        {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_branch_work_wage_owner_admission_report_json={path}")
    print(f"overall_infra_branch_work_wage_owner_admission_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
