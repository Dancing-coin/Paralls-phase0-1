from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    matrix = root / "backend" / "tests" / "test_infra_semantic_state_owner_matrix.py"
    owner = root / "backend" / "tests" / "test_infra_survival_state_obligation.py"
    semantic = root / "backend" / "tests" / "test_infra_semantic_registered_state_owner_dispatch.py"
    selectors = {
        "closed_owner_contract": (matrix, "test_survival_fatigue_row_is_an_explicit_closed_owner_contract"),
        "owner_spine_success": (owner, "test_survival_fatigue_owner_row_commits_through_the_existing_state_obligation_spine"),
        "duplicate_and_changed_duplicate": (owner, "test_survival_fatigue_owner_row_replays_duplicate_and_rejects_changed_input"),
        "revision_and_forged_contract_zero_write": (owner, "test_survival_fatigue_owner_row_rejects_stale_revision_and_forged_contract_without_write"),
        "semantic_owner_dispatch": (semantic, "test_registered_state_dispatch_routes_fatigue_to_existing_owner"),
        "privacy_zero_write": (semantic, "test_registered_state_dispatch_rejects_fatigue_nonproject_privacy_without_append"),
        "full_checkpoint_tail_replay": (owner, "test_survival_fatigue_owner_row_replays_full_and_checkpoint_tail"),
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, (test_path, selector) in selectors.items():
        log_path = verification_dir(root) / f"infra-survival-fatigue-owner-row-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{test_path}::{selector}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-survival-fatigue-owner-row",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(path.relative_to(root)).replace("\\", "/") for path in (matrix, owner, semantic)],
        "evidence": evidence,
        "run_id": f"infra-survival-fatigue-owner-row-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "SurvivalAuthority",
        "stream": "gameplay:survival:{actor_ref}",
        "write_path": "Semantic proposal -> Survival GameplayCommandEnvelope -> GameplayEventStore.append_batch -> project outbox -> replay",
        "limitations": ["Only effect:fatigue_exposure -> state:fatigued is admitted.", "No generic state registration or writer is added."],
    }
    path = verification_dir(root) / "infra-survival-fatigue-owner-row-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-1S Survival Fatigue Owner Row Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_survival_fatigue_owner_row_report_json={path}")
    print(f"overall_infra_survival_fatigue_owner_row_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
