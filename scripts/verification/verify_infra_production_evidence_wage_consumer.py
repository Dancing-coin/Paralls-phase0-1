from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    focused = root / "backend" / "tests" / "test_infra_production_evidence_wage_consumer.py"
    cases = {
        "worker_scoped_source_freeze": "test_inf4z_wage_consumer_freezes_matching_worker_scoped_production_source",
        "economy_owner_source_pins_outbox": "test_inf4z_wage_consumer_commits_economy_owner_envelope_fragment_with_source_pins",
        "economy_envelope_settlement_plan": "test_inf4z_wage_consumer_uses_economy_envelope_and_settlement_plan",
        "forged_source_zero_write": "test_inf4z_wage_consumer_rejects_forged_source_without_write",
        "stale_source_zero_write": "test_inf4z_wage_consumer_rejects_stale_source_without_write",
        "forged_rows_zero_write": "test_inf4z_wage_consumer_rejects_forged_evidence_rows_without_write",
        "privacy_zero_write": "test_inf4z_wage_consumer_rejects_privacy_mismatch_without_write",
        "wage_revision_zero_write": "test_inf4z_wage_consumer_rejects_stale_wage_revision_without_write",
        "duplicate_owner_receipt_replay": "test_inf4z_wage_consumer_duplicate_and_replay_are_owner_scoped",
        "changed_duplicate_zero_write": "test_inf4z_wage_consumer_changed_duplicate_is_zero_write",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-production-evidence-wage-consumer-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(focused), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-production-evidence-wage-consumer",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(focused.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-production-evidence-wage-consumer-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "source_owner": "actor_gameplay.construction_production_domain",
        "source_stream": "gameplay:construction_production:{facility_ref}",
        "source_event_type": "gameplay.construction_production.work_completion_evidence_recorded",
        "consumer_owner": "actor_gameplay.econ1_economy_domain",
        "target_stream": "gameplay:economy:wage:{worker_ref}",
        "target_event_type": "gameplay.economy.wage_accrued",
        "write_path": "Production scoped view -> frozen input -> PopulationPlanner proposal -> EconomyAuthority -> GameplayCommandEnvelope/SettlementPlan -> GameplayEventStore.append_batch -> outbox/replay -> scoped projection",
        "limitations": [
            "Admits only canonical Production completed evidence for the matching worker actor.",
            "Does not admit generic work, non-production evidence, payroll payment, compensation, civilization consumers, P6, or P7."
        ],
    }
    path = verification_dir(root) / "infra-production-evidence-wage-consumer-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-4Z Production Evidence Wage Consumer Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_production_evidence_wage_consumer_report_json={path}")
    print(f"overall_infra_production_evidence_wage_consumer_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
