from __future__ import annotations

from datetime import datetime, timezone
from shutil import which

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_semantic_economy_wage_obligation.py"
    terminal_lifecycle_path = root / "backend" / "tests" / "test_infra_economy_wage_terminal_lifecycle.py"
    cases = {
        "success_existing_economy_owner": "test_semantic_wage_effect_opens_existing_economy_obligation",
        "unknown_effect_zero_write": "test_semantic_wage_effect_rejects_unknown_effect_without_write",
        "unregistered_row_zero_write": "test_semantic_wage_effect_rejects_unregistered_row_without_write",
        "wrong_owner_zero_write": "test_semantic_wage_effect_rejects_wrong_owner_without_write",
        "wrong_stream_zero_write": "test_semantic_wage_effect_rejects_wrong_stream_without_write",
        "privacy_zero_write": "test_semantic_wage_effect_rejects_nonproject_privacy_without_write",
        "stale_vector_zero_write": "test_semantic_wage_effect_rejects_stale_vector_without_write",
        "duplicate_idempotency": "test_semantic_wage_effect_preserves_duplicate_idempotency",
        "changed_duplicate_zero_write": "test_semantic_wage_effect_rejects_changed_duplicate_without_write",
        "malformed_wage_fields_zero_write": "test_semantic_wage_effect_rejects_malformed_wage_fields_without_write",
        "revision_conflict_zero_write": "test_semantic_wage_effect_rejects_stale_revision_without_write",
        "project_outbox_scope": "test_semantic_wage_effect_outbox_is_project_scoped",
        "full_checkpoint_tail_replay": "test_semantic_wage_effect_lifecycle_replays_full_and_checkpoint_tail",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-semantic-economy-wage-obligation-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{test_path}::{test_name}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    entrypoint_log_path = verification_dir(root) / "infra-semantic-economy-wage-obligation-terminal-lifecycle-pytest-entrypoint.log"
    pytest_executable = which("pytest")
    if pytest_executable is None:
        checks["terminal_lifecycle_pytest_entrypoint"] = False
        entrypoint_log_path.write_text("pytest executable unavailable\n", encoding="utf-8")
    else:
        entrypoint = run_command([pytest_executable, "-q", str(terminal_lifecycle_path)], root, entrypoint_log_path)
        checks["terminal_lifecycle_pytest_entrypoint"] = entrypoint.returncode == 0
    evidence.append(str(entrypoint_log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-semantic-economy-wage-obligation",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [
            str(test_path.relative_to(root)).replace("\\", "/"),
            str(terminal_lifecycle_path.relative_to(root)).replace("\\", "/"),
        ],
        "evidence": evidence,
        "run_id": f"infra-semantic-economy-wage-obligation-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "registered_row": {
            "effect_ref": "effect:wage_accrual_due",
            "owner_ref": "actor_gameplay.econ1_economy_domain",
            "stream_pattern": "gameplay:economy:wage:{worker_ref}",
            "opened_event_type": "gameplay.economy.wage_obligation_opened",
            "projection_scope": "project",
        },
        "write_path": "closed semantic effect route -> EconomyAuthority envelope/SettlementPlan -> GameplayEventStore.append_batch -> outbox/replay/scoped projection",
        "limitations": [
            "This is one registered Economy effect/obligation row, not generic semantic owner dispatch.",
            "Payment, account balance, generic wage policy and additional semantic effect/state rows remain outside the admitted contract.",
        ],
    }
    path = verification_dir(root) / "infra-semantic-economy-wage-obligation-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-1J Semantic Economy Wage Obligation Owner Row Report",
        {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_semantic_economy_wage_obligation_report_json={path}")
    print(f"overall_infra_semantic_economy_wage_obligation_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
