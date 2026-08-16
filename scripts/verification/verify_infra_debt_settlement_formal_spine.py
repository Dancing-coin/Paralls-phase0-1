from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    tests = root / "backend" / "tests" / "test_infra_debt_settlement_formal_spine.py"
    selectors = {
        "formal_owner_fragments_and_redacted_outbox": "test_simple_debt_issue_uses_formal_owner_fragments_and_redacted_outbox",
        "payment_formal_owner_fragments_and_redacted_outbox": "test_simple_debt_payment_uses_formal_owner_fragments_and_redacted_outbox",
        "legacy_event_compatibility": "test_simple_debt_issue_preserves_legacy_event_family_order_and_payload_contract",
        "exact_duplicate_zero_write": "test_simple_debt_formal_spine_replays_exact_duplicate_without_second_append",
        "changed_duplicate_zero_write": "test_simple_debt_formal_spine_rejects_changed_idempotency_without_append",
        "stale_revision_zero_write": "test_simple_debt_plan_rejects_stale_revision_without_append",
        "closed_event_admission_zero_write": "test_simple_debt_plan_rejects_unregistered_event_before_append",
        "closed_event_stream_pairing_zero_write": "test_simple_debt_plan_rejects_registered_event_on_wrong_stream_before_append",
        "full_checkpoint_tail_replay": "test_simple_debt_formal_spine_replays_full_and_checkpoint_tail",
        "owner_local_replay_reader": "test_debt_authority_replay_projection_matches_full_and_checkpoint_tail",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, selector in selectors.items():
        log_path = verification_dir(root) / f"infra-debt-settlement-formal-spine-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{tests}::{selector}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-debt-settlement-formal-spine",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(tests.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-debt-settlement-formal-spine-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "DebtAuthorityService",
        "streams": ["gameplay:economy", "gameplay:contracts", "gameplay:debt", "gameplay:commerce"],
        "write_path": "DebtAuthorityService -> GameplayCommandEnvelope -> DebtSettlementPlan -> owner fragments -> GameplayEventStore.append_batch -> authority-scoped outbox -> replay",
        "limitations": [
            "Only the existing simple-debt issue, payment, cancellation, correction, reopening, overdue and default event family is admitted.",
            "The plan rejects caller-selected event types and stream sets before append.",
            "This does not admit arbitrary payment policies, caller-open registration or generic cross-domain settlement.",
        ],
    }
    path = verification_dir(root) / "infra-debt-settlement-formal-spine-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-2L Debt Settlement Formal Spine Report",
        {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
