from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root(); python = resolve_python_exe(None)
    tests = root / "backend" / "tests" / "test_infra_activation_survival_expiry.py"
    selectors = {"owner_fragment_success": "test_released_fatigue_expiry_pending_settles_through_existing_survival_fragment", "duplicate_revision_zero_write": "test_released_fatigue_expiry_pending_replays_duplicate_and_rejects_stale_revision", "privacy_checkpoint_tail_replay": "test_released_fatigue_expiry_pending_rejects_nonproject_privacy_and_replays_tail"}
    checks: dict[str, bool] = {}; evidence: list[str] = []
    for check, selector in selectors.items():
        log = verification_dir(root) / f"infra-activation-fatigue-expiry-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{tests}::{selector}"], root, log)
        checks[check] = result.returncode == 0; evidence.append(str(log.relative_to(root)).replace("\\", "/"))
    report = {"profile": "infra-activation-fatigue-expiry", "overall_passed": all(checks.values()), "checks": checks, "focused_test_files": [str(tests.relative_to(root)).replace("\\", "/")], "evidence": evidence, "run_id": f"inf2n-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}", "commit": evidence_revision(root), "owner": "SurvivalAuthority", "write_path": "released activation pending -> existing Survival fragment -> one append_batch -> scoped projection/replay", "limitations": ["Only state:fatigued is additionally bound.", "No generic activation-obligation binding is added."]}
    path = verification_dir(root) / "infra-activation-fatigue-expiry-report.json"; write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-2N Fatigue Activation Expiry Report", {"results": [{"id": k, "status": "proved" if v else "missing", "title": k} for k,v in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    return 0 if report["overall_passed"] else 1

if __name__ == "__main__": raise SystemExit(main())
