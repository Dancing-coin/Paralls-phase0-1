from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_ecology_disaster.py"
    cases = {
        "versioned_ecology_records": "test_ecology_records_are_versioned_and_owner_scoped",
        "frost_authority_settlement": "test_hazard_settles_frost_through_semantic_authority_and_existing_store",
        "revision_and_privacy_zero_write": "test_hazard_duplicate_revision_and_scope_failures_do_not_write",
        "idempotency_and_chain_budget": "test_hazard_duplicate_replays_and_chain_budget_rejection_is_zero_write",
        "scoped_projection_and_checkpoint_tail_replay": "test_hazard_projection_is_redacted_and_replay_equivalent",
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    for name, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-ecology-disaster-{name}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[name] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-ecology-disaster",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": logs,
        "run_id": f"infra-ecology-disaster-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": ["backend/app/gameplay/ecology_runtime.py", "backend/app/gameplay/semantic_authority.py"],
        "write_path": "hazard authority -> semantic lifecycle authority -> SettlementPlan -> GameplayEventStore.append_batch -> outbox/replay -> scoped projection",
        "godot_runtime": "not changed; no Godot visible completion claim",
        "limitations": ["Only frost/crop vertical is implemented; climate, markets, construction, body, and broader ecology propagation remain owner-specific follow-up."],
    }
    path = verification_dir(root) / "infra-ecology-disaster-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-3 Ecology Disaster Report", {"results": [{"id": name, "status": "proved" if ok else "missing", "title": name} for name, ok in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_ecology_disaster_report_json={path}")
    print(f"overall_infra_ecology_disaster_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
