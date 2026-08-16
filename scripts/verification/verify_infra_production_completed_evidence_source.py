from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    focused = root / "backend" / "tests" / "test_infra_production_completed_evidence_source.py"
    cases = {
        "production_start_contribution_linkage": "test_inf4z_production_start_commits_worker_contribution_linkage",
        "finished_source_required_zero_write": "test_inf4z_production_completed_evidence_requires_committed_finished_run",
        "owner_event_actor_scope": "test_inf4z_production_completed_evidence_has_owner_event_and_scoped_view",
        "envelope_plan_redacted_outbox": "test_inf4z_production_evidence_uses_envelope_plan_and_redacted_outbox",
        "empty_evidence_ref_zero_write": "test_inf4z_production_evidence_empty_ref_is_zero_write",
        "untrusted_evidence_ref_zero_write": "test_inf4z_production_evidence_untrusted_ref_is_zero_write",
        "stale_revision_zero_write": "test_inf4z_production_evidence_stale_revision_is_zero_write",
        "mismatched_contribution_zero_write": "test_inf4z_production_evidence_mismatched_contribution_is_zero_write",
        "idempotent_duplicate_receipt": "test_inf4z_production_evidence_duplicate_replays_same_owner_receipt",
        "changed_duplicate_zero_write": "test_inf4z_production_evidence_changed_duplicate_is_zero_write",
        "checkpoint_tail_view_replay": "test_inf4z_production_evidence_scoped_view_replays_from_checkpoint_tail",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-production-completed-evidence-source-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(focused), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-production-completed-evidence-source",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(focused.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-production-completed-evidence-source-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "actor_gameplay.construction_production_domain",
        "stream": "gameplay:construction_production:{facility_ref}",
        "event_type": "gameplay.construction_production.work_completion_evidence_recorded",
        "write_path": "ConstructionProductionAuthority -> GameplayCommandEnvelope/SettlementPlan -> GameplayEventStore.append_batch -> outbox/replay -> scoped projection",
        "limitations": [
            "Admits only production-completed evidence after a committed run_finished source with committed worker contribution linkage.",
            "Does not admit wage accrual, generic work mapping, actor-declared evidence, procurement/service evidence, P6, or P7."
        ]
    }
    path = verification_dir(root) / "infra-production-completed-evidence-source-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-4Z Production Completed-Evidence Source Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_production_completed_evidence_source_report_json={path}")
    print(f"overall_infra_production_completed_evidence_source_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
