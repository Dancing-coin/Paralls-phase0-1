from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_general_semantic_rule.py"
    cases = {
        "immutable_ruleset_and_registered_owner_row": "test_closed_ruleset_is_immutable_and_evaluates_the_registered_production_row",
        "unmapped_owner_and_durable_lifecycle_zero_write": "test_closed_ruleset_rejects_unmapped_owner_and_durable_lifecycle_without_mutation",
        "registered_fragment_append_and_outbox": "test_closed_ruleset_authority_uses_only_registered_production_fragment",
        "rule_mapping_mismatch_zero_write": "test_closed_ruleset_authority_rejects_rule_mapping_mismatch_without_write",
        "trace_privacy_filtering": "test_closed_ruleset_trace_is_filtered_independently_by_scope",
        "changed_idempotency_zero_write": "test_closed_ruleset_changed_idempotency_input_is_zero_write",
        "conflict_policy_determinism": "test_closed_ruleset_conflict_policies_are_deterministic",
        "reject_suppress_fail_closed": "test_closed_ruleset_reject_and_suppress_are_fail_closed",
        "fixed_precision_resistance": "test_closed_effect_resistance_is_fixed_precision_and_has_no_write_path",
        "full_checkpoint_tail_replay": "test_closed_ruleset_production_projection_full_and_checkpoint_tail_replay_match",
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-general-semantic-rule-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-general-semantic-rule",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": logs,
        "run_id": f"infra-general-semantic-rule-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": ["backend/app/gameplay/semantic_registry.py", "backend/app/gameplay/semantic_authority.py", "backend/app/gameplay/construction_production_runtime.py"],
        "write_path": "closed semantic evaluation -> registered construction owner fragment -> GameplayEventStore.append_batch -> outbox/replay -> scoped projection",
        "enabled_owner_rows": ["effect:production_due_finish -> ConstructionProductionAuthority.build_due_finish_fragment"],
        "limitations": ["Only the one-shot production-finish row is admitted.", "Durable state lifecycle, retry, cancellation, transformation, compensation, and economy/survival/ecology/social/civilization mappings remain unregistered and zero-write rejected."],
    }
    path = verification_dir(root) / "infra-general-semantic-rule-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-1X General Semantic Rule Report", {"results": [{"id": name, "status": "proved" if status else "missing", "title": name} for name, status in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_general_semantic_rule_report_json={path}")
    print(f"overall_infra_general_semantic_rule_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
