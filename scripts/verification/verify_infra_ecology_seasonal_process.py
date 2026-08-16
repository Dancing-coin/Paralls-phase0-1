from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_ecology_process_lifecycle.py"
    cases = {
        "owner_batch_environment_resource_crop": "test_closed_seasonal_process_advances_environment_resource_and_crop_through_one_owner_batch",
        "idempotency_revision_privacy_principal_replay": "test_seasonal_process_is_idempotent_revisioned_private_rejected_and_replayable",
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-ecology-seasonal-process-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-ecology-seasonal-process",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": logs,
        "run_id": f"infra-ecology-seasonal-process-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "EcologyHazardAuthority",
        "stream": "gameplay:ecology:{region_ref}",
        "write_path": "EcologyHazardAuthority -> GameplayCommandEnvelope -> OwnerAuthorizedFragment -> GameplayEventStore.append_batch -> outbox/replay -> scoped projection",
        "limitations": [
            "One fixed seasonal process only; no scheduler, generic weather model, retry, compensation, or multi-region fanout.",
            "No cross-domain consumer edge is admitted by this profile.",
        ],
    }
    path = verification_dir(root) / "infra-ecology-seasonal-process-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-3A Ecology Seasonal Process Report", {"results": [{"id": name, "status": "proved" if ok else "missing", "title": name} for name, ok in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_ecology_seasonal_process_report_json={path}")
    print(f"overall_infra_ecology_seasonal_process_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
