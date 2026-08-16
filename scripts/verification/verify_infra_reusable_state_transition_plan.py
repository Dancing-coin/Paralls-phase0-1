from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_file = root / "backend" / "tests" / "test_infra_reusable_state_transition_plan.py"
    cases = {
        "apply_policy_and_expiry": "test_reusable_state_plan_exposes_apply_policy_and_expiry_without_write_capability",
        "add_replace_reject": "test_reusable_state_plan_has_distinct_replace_add_and_reject_decisions",
        "dispel_transform": "test_reusable_state_plan_covers_dispel_and_transform_as_owner_proposals",
        "multi_owner_reuse": "test_same_pure_plan_shape_is_usable_for_registered_survival_construction_and_ecology_rows",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for name, selector in cases.items():
        log = verification_dir(root) / f"infra-reusable-state-transition-plan-{name}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_file), "-k", selector], root, log)
        checks[name] = result.returncode == 0
        evidence.append(str(log.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-reusable-state-transition-plan",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_file.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-reusable-state-transition-plan-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "write_path": "pure EffectLifecycleEvaluator StateTransitionPlan -> existing owner adapter -> existing GameplayEventStore.append_batch",
        "limitations": [
            "The plan is proposal-only and cannot append, register owners, select a stream, or execute expressions.",
            "Existing owner rows remain closed; no generic state registration or generic lifecycle settlement is admitted.",
        ],
    }
    path = verification_dir(root) / "infra-reusable-state-transition-plan-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-C1 Reusable State Transition Plan Report",
        {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()]},
        "overall_passed",
    )
    print(f"infra_reusable_state_transition_plan_report_json={path}")
    print(f"overall_infra_reusable_state_transition_plan_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
