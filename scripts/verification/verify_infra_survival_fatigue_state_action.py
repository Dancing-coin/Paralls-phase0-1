from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    tests = root / "backend" / "tests" / "test_infra_semantic_survival_state_action.py"
    selectors = {
        "fatigue_dispel_success": "test_semantic_survival_fatigue_dispel_commits_existing_owner_events",
        "fatigue_transform_success": "test_semantic_survival_fatigue_transform_commits_fixed_recovery_owner_events",
        "fatigue_privacy_zero_write": "test_semantic_survival_fatigue_action_rejects_nonproject_privacy_without_write",
        "fatigue_duplicate_revision_replay": "test_semantic_survival_fatigue_action_duplicate_revision_and_replay_are_closed",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, selector in selectors.items():
        log = verification_dir(root) / f"infra-survival-fatigue-state-action-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{tests}::{selector}"], root, log)
        checks[check] = result.returncode == 0
        evidence.append(str(log.relative_to(root)).replace("\\", "/"))
    report = {"profile": "infra-survival-fatigue-state-action", "overall_passed": all(checks.values()), "checks": checks, "focused_test_files": [str(tests.relative_to(root)).replace("\\", "/")], "evidence": evidence, "run_id": f"inf1t-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}", "commit": evidence_revision(root), "owner": "SurvivalAuthority", "write_path": "closed semantic action -> existing Survival fragment -> one append_batch -> project outbox/replay", "limitations": ["Only the already-admitted fatigue row is added to existing dispel/recovery-transform actions.", "No generic action registration or replacement target is admitted."]}
    path = verification_dir(root) / "infra-survival-fatigue-state-action-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-1T Survival Fatigue State Action Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
