from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_population_branch_preview.py"
    cases = {
        "isolated_branch_events_checkpoint_tail": "test_isolated_branch_events_rebuild_projection_and_checkpoint_tail_without_production_append",
        "deterministic_buffer_replay": "test_branch_buffer_replays_deterministically_without_production_append",
        "base_digest_zero_write": "test_inf4z_branch_preview_rejects_fixed_base_digest_without_production_writes",
        "unknown_profile_zero_write": "test_inf4z_branch_preview_rejects_unknown_candidate_profile_without_production_writes",
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-isolated-branch-evolution-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-isolated-branch-evolution",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": logs,
        "run_id": f"infra-isolated-branch-evolution-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "BranchPreviewAuthority analysis buffer only",
        "write_path": "frozen base/calibration/identity inputs -> isolated branch descriptor and branch candidate records -> local replay projection; no GameplayEventStore.append_batch path",
        "limitations": [
            "Branch records are non-production analysis artifacts, not a second event store or world-truth writer.",
            "Promotion is explicitly unsupported and production events/outbox remain unchanged.",
        ],
    }
    path = verification_dir(root) / "infra-isolated-branch-evolution-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-4B Isolated Branch Evolution Report", {"results": [{"id": name, "status": "proved" if ok else "missing", "title": name} for name, ok in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_isolated_branch_evolution_report_json={path}")
    print(f"overall_infra_isolated_branch_evolution_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
