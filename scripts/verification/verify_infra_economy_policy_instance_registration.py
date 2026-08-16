from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_economy_policy_instance_registration.py"
    full_suite = [str(test_path)]
    privacy_outbox_receipt = [
        f"{test_path}::test_economy_policy_instance_registration_outbox_is_authority_scoped_and_redacted",
        f"{test_path}::test_economy_policy_instance_registration_receipt_is_derived_from_append_result",
        f"{test_path}::test_economy_policy_instance_registration_receipt_rejects_nonauthority_scope_without_write",
        f"{test_path}::test_economy_policy_instance_revocation_outbox_is_authority_scoped_and_redacted",
        f"{test_path}::test_economy_policy_instance_revocation_receipt_is_derived_from_append_result",
        f"{test_path}::test_economy_policy_instance_revocation_receipt_rejects_nonauthority_scope_without_write",
    ]
    instance_bound_settlement_revocation = [
        f"{test_path}::test_economy_policy_instance_allows_explicit_binding_and_pins_registration_snapshot",
        f"{test_path}::test_economy_revokes_scheduled_transfer_policy_instance_and_restores_manual_open",
        f"{test_path}::test_economy_policy_instance_bound_due_settlement_succeeds",
        f"{test_path}::test_economy_policy_instance_bound_cancellation_succeeds",
        f"{test_path}::test_economy_policy_instance_bound_expiry_succeeds",
        f"{test_path}::test_economy_policy_instance_bound_due_settlement_survives_policy_revocation",
        f"{test_path}::test_economy_policy_instance_bound_cancellation_survives_policy_revocation",
        f"{test_path}::test_economy_policy_instance_bound_expiry_survives_policy_revocation",
    ]
    replay = [
        f"{test_path}::test_economy_policy_instance_projection_full_and_checkpoint_tail_replay_match",
    ]
    cases = {
        "focused_suite": full_suite,
        "full_checkpoint_tail_replay": replay,
        "privacy_outbox_receipt": privacy_outbox_receipt,
        "instance_bound_settlement_revocation": instance_bound_settlement_revocation,
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    for check, args in cases.items():
        log_path = verification_dir(root) / f"infra-economy-policy-instance-registration-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", *args], root, log_path)
        checks[check] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-economy-policy-instance-registration",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": logs,
        "run_id": f"infra-economy-policy-instance-registration-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "actor_gameplay.economy_domain",
        "stream": "gameplay:economy",
        "event_family": [
            "scheduled_transfer_policy_registered",
            "scheduled_transfer_policy_revoked",
            "scheduled_transfer_obligation_opened",
            "scheduled_transfer_obligation_settled",
            "scheduled_transfer_obligation_cancelled",
            "scheduled_transfer_obligation_expired",
        ],
        "write_path": "EconomyAuthorityService -> GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch -> authority-only outbox/receipt -> EconomyProjector and ObligationLifecycleProjection",
        "limitations": [
            "The contract remains an existing-Economy owner surface for one scheduled-transfer policy kind only.",
            "It does not create a generic policy registry, a scheduler, or a cross-domain settlement writer.",
            "Bound settlement/revocation is validated only against the already admitted Economy policy-instance snapshot."
        ],
    }
    path = verification_dir(root) / "infra-economy-policy-instance-registration-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-2U Economy Policy-Instance Registration Report",
        {"results": [{"id": name, "status": "proved" if ok else "missing", "title": name} for name, ok in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_economy_policy_instance_registration_report_json={path}")
    print(f"overall_infra_economy_policy_instance_registration_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
