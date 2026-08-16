from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_frost_production_recipe_admission.py"
    cases = {
        "committed_recipe_snapshot_and_revision": "test_committed_run_started_event_derives_authority_recipe_with_source_revision",
        "scope_missing_stale_zero_write": "test_recipe_public_missing_and_stale_queries_are_zero_write",
        "duplicate_recipe_source_idempotency": "test_duplicate_run_start_reuses_one_committed_recipe_snapshot",
        "legacy_snapshot_zero_write": "test_legacy_run_event_without_recipe_snapshot_is_zero_write_rejected",
        "full_checkpoint_tail_recipe_rebuild": "test_recipe_admission_is_idempotent_and_checkpoint_tail_rebuild_is_equal",
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-frost-production-recipe-admission-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-frost-production-recipe-admission",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": logs,
        "run_id": f"infra-frost-production-recipe-admission-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": ["backend/app/gameplay/construction_production_runtime.py"],
        "source_event": "gameplay.construction_production.run_started(recipe_snapshot)",
        "read_path": "ConstructionProductionProjector -> authority-only recipe_for_run; no write path",
        "limitations": ["No frost-to-production consequence is written.", "Recipe inputs are intentionally not exposed in the fragment snapshot."],
    }
    path = verification_dir(root) / "infra-frost-production-recipe-admission-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-3R-B Production Recipe Admission Report", {"results": [{"id": name, "status": "proved" if status else "missing", "title": name} for name, status in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_frost_production_recipe_admission_report_json={path}")
    print(f"overall_infra_frost_production_recipe_admission_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
