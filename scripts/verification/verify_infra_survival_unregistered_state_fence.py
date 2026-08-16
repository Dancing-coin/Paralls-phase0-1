from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    tests = root / "backend" / "tests" / "test_infra_survival_reject_state_obligation.py"
    selector = "test_unregistered_survival_reject_state_is_zero_write_before_any_owner_append"
    log = verification_dir(root) / "infra-survival-unregistered-state-fence-zero-write.log"
    result = run_command([python, "-m", "pytest", "-q", f"{tests}::{selector}"], root, log)
    report = {"profile": "infra-survival-unregistered-state-fence", "overall_passed": result.returncode == 0, "checks": {"unregistered_reject_state_zero_write": result.returncode == 0}, "evidence": [str(log.relative_to(root)).replace("\\", "/")], "run_id": f"infra-survival-unregistered-state-fence-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}", "commit": evidence_revision(root), "limitations": ["No reject owner row is admitted."]}
    path = verification_dir(root) / "infra-survival-unregistered-state-fence-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-1V Unregistered Survival State Fence Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in report["checks"].items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
