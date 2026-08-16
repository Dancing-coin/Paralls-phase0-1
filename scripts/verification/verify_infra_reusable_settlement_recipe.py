from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    cases = {
        "single_owner_recipe": "test_recipe_builds_one_append_batch_for_a_single_owner_without_write_capability",
        "multi_owner_append_receipt": "test_recipe_combines_existing_multi_owner_fragments_and_derives_receipt_from_one_result",
        "rejected_zero_write_receipt": "test_recipe_rejected_append_result_produces_zero_write_receipt",
        "overlap_zero_write_fence": "test_recipe_rejects_overlapping_owner_streams_before_any_append",
    }
    test_path = root / "backend" / "tests" / "test_infra_reusable_settlement_recipe.py"
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-reusable-settlement-recipe-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))

    existing = {
        "owner_only_obligation_commit": "backend/tests/test_infra_owner_only_obligation_commit_spine.py::test_plan_settle_is_zero_write_and_survival_authority_commits_planned_batch",
        "append_derived_receipt_factory": "backend/tests/test_infra_append_derived_settlement_receipt.py::test_settlement_receipt_is_derived_from_one_committed_append_result",
    }
    for check, node in existing.items():
        log_path = verification_dir(root) / f"infra-reusable-settlement-recipe-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", "-p", "no:cacheprovider", node], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))

    report = {
        "profile": "infra-reusable-settlement-recipe",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-reusable-settlement-recipe-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owners": ["actor_gameplay.survival_domain", "actor_gameplay.organization_domain", "actor_gameplay.economy_domain"],
        "write_path": "existing authority -> GameplayCommandEnvelope/SettlementPlan -> GameplayEventStore.append_batch -> outbox/replay -> scoped projection",
        "limitations": [
            "Recipe composition does not authorize arbitrary cross-domain business outcomes.",
            "Receipt is derived only from the owner-supplied append result; the recipe never appends or stores receipts.",
        ],
    }
    path = verification_dir(root) / "infra-reusable-settlement-recipe-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-2C3 Append-Derived Settlement Recipe Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_reusable_settlement_recipe_report_json={path}")
    print(f"overall_infra_reusable_settlement_recipe_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
