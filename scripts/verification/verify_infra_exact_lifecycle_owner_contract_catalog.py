from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    catalog = root / "backend" / "tests" / "test_infra_exact_lifecycle_owner_contract_catalog.py"
    replay = root / "backend" / "tests" / "test_infra_ecology_drought_state_obligation.py"
    cases = {
        "exact_owner_rows": (catalog, "test_lifecycle_contract_catalog_materializes_only_the_five_exact_owner_rows"),
        "operation_scope_rejection": (catalog, "test_require_operation_rejects_the_survival_row_when_scope_is_wrong"),
        "survival_preappend_zero_write": (catalog, "test_survival_owner_gate_rejects_before_append_and_keeps_the_store_unchanged"),
        "construction_preappend_zero_write": (catalog, "test_construction_owner_gate_rejects_before_append_and_keeps_the_store_unchanged"),
        "checkpoint_tail_replay": (replay, "test_ecology_drought_state_checkpoint_tail_replay_matches_full_replay"),
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for name, (test_file, selector) in cases.items():
        log = verification_dir(root) / f"infra-exact-lifecycle-owner-contract-catalog-{name}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_file), "-k", selector], root, log)
        checks[name] = result.returncode == 0
        evidence.append(str(log.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-exact-lifecycle-owner-contract-catalog",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(catalog.relative_to(root)).replace("\\", "/"), str(replay.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-exact-lifecycle-owner-contract-catalog-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "write_path": "existing authority -> formal envelope/owner fragment -> GameplayEventStore.append_batch -> outbox/replay/scoped projection",
        "limitations": [
            "The catalog is immutable and owner-local; caller-open policy registration remains rejected.",
            "No generic effect/state matrix, scheduler, settlement writer, receipt store, or cross-domain payment path is admitted.",
        ],
    }
    path = verification_dir(root) / "infra-exact-lifecycle-owner-contract-catalog-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-2Y Exact Lifecycle Owner-Contract Catalog Report",
        {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()]},
        "overall_passed",
    )
    print(f"infra_exact_lifecycle_owner_contract_catalog_report_json={path}")
    print(f"overall_infra_exact_lifecycle_owner_contract_catalog_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
