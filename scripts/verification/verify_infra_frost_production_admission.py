from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_frost_production_admission.py"
    cases = {
        "committed_source_provenance_and_redaction": "test_committed_frost_source_has_owner_provenance_and_public_redaction",
        "source_without_plot_zero_write": "test_frost_without_plot_is_not_a_production_source_and_adds_no_write",
        "source_privacy_revision_zero_write": "test_private_or_stale_frost_source_is_zero_write",
        "source_duplicate_idempotency": "test_duplicate_frost_source_settlement_is_idempotent",
        "one_due_target_from_committed_projection": "test_construction_selects_one_due_target_from_committed_projection",
        "target_missing_or_not_due_zero_write": "test_construction_target_missing_ambiguous_or_not_due_is_zero_write",
        "target_ambiguous_zero_write": "test_construction_target_ambiguity_is_zero_write",
        "full_checkpoint_tail_source_replay": "test_admission_source_replay_matches_full_and_checkpoint_tail",
        "full_checkpoint_tail_target_replay": "test_admission_target_selection_matches_full_and_checkpoint_tail_rebuild",
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-frost-production-admission-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-frost-production-admission",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": logs,
        "run_id": f"infra-frost-production-admission-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": ["backend/app/gameplay/ecology_runtime.py", "backend/app/gameplay/construction_production_runtime.py"],
        "source_event": "semantic.effect.settled(effect:frost) on crop stream",
        "target_projection": "ConstructionProductionProjector facility_acquired + run_started",
        "write_path": "EcologyHazardAuthority -> SemanticSettlementAuthority -> GameplayEventStore.append_batch -> outbox/replay; construction selection is read-only",
        "limitations": ["No frost-to-production consequence is written.", "INF-3R remains a separate package after this admission evidence."],
    }
    path = verification_dir(root) / "infra-frost-production-admission-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-3R-A Frost Production Admission Report", {"results": [{"id": name, "status": "proved" if status else "missing", "title": name} for name, status in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_frost_production_admission_report_json={path}")
    print(f"overall_infra_frost_production_admission_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
