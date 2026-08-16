from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    admission = root / "backend" / "tests" / "test_infra_closed_lifecycle_registration_admission.py"
    generic = root / "backend" / "tests" / "test_infra_time_obligation.py"
    construction = root / "backend" / "tests" / "test_infra_obligation_lifecycle.py"
    construction_due = root / "backend" / "tests" / "test_infra_multi_domain_obligation.py"
    survival = root / "backend" / "tests" / "test_infra_survival_state_obligation.py"
    cases = {
        "closed_policy_shape": (admission, "test_closed_lifecycle_registration_reader_contains_only_existing_owner_policies"),
        "policyless_generic_zero_write": (admission, "test_policyless_generic_fragment_is_zero_write_rejected"),
        "unknown_forged_registration_zero_write": (admission, "test_unknown_policy_and_forged_registration_are_zero_write_rejected"),
        "widened_registration_zero_write": (admission, "test_closed_registration_rejects_a_widened_terminal_event_contract"),
        "unregistered_fragment_event_zero_write": (admission, "test_registered_lifecycle_fragment_cannot_smuggle_an_unregistered_event"),
        "owner_privacy_scope_zero_write": (admission, "test_registered_lifecycle_fragment_cannot_override_the_owner_privacy_scope"),
        "construction_committed_open_zero_write": (admission, "test_construction_due_completion_requires_its_committed_run_open_event"),
        "historical_generic_due_zero_write": (generic, "test_unregistered_due_obligation_is_zero_write_rejected"),
        "historical_generic_duplicate_zero_write": (generic, "test_unregistered_due_obligation_duplicate_is_zero_write_rejected"),
        "construction_existing_owner_success": (construction_due, "test_production_due_policy_uses_clock_then_owner_fragment_then_event_spine"),
        "construction_checkpoint_tail_replay": (construction_due, "test_production_due_policy_public_receipt_is_filtered_and_replay_matches"),
        "survival_existing_owner_success": (survival, "test_due_survival_state_expiry_is_selected_by_clock_and_settled_by_existing_coordinator"),
        "survival_owner_replay": (survival, "test_survival_state_transform_cancels_prior_expiry_and_rebuilds_from_checkpoint_tail"),
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, (test_path, test_name) in cases.items():
        log_path = verification_dir(root) / f"infra-closed-lifecycle-registration-admission-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{test_path}::{test_name}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-closed-lifecycle-registration-admission",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(path.relative_to(root)).replace("\\", "/") for path in (admission, generic, construction, construction_due, survival)],
        "evidence": evidence,
        "run_id": f"infra-closed-lifecycle-registration-admission-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "closed_owner_count": 6,
        "write_path": "existing owner -> GameplayCommandEnvelope/SettlementPlan -> GameplayEventStore.append_batch -> outbox/replay -> scoped projection",
        "limitations": [
            "This closes caller registration admission; it does not add policy registration or generic business settlement.",
            "Only six existing owner policies, their closed owner-local event families, registered visibility scopes, and required committed-open admissions are accepted; unknown fragments, smuggled events, overridden privacy vectors, and uncommitted lifecycle terminals remain zero-write.",
        ],
    }
    path = verification_dir(root) / "infra-closed-lifecycle-registration-admission-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-2M Closed Lifecycle Registration Admission Report",
        {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_closed_lifecycle_registration_admission_report_json={path}")
    print(f"overall_infra_closed_lifecycle_registration_admission_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
