from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    tests = root / "backend" / "tests" / "test_infra_construction_facility_package_transform.py"
    cases = {
        "success_receipt_projection": "test_package_transform_commits_one_project_event_and_append_receipt",
        "zero_write_source_revision_and_package": "test_package_transform_rejections_are_zero_write",
        "zero_write_binding_and_digest": "test_package_transform_binding_and_digest_conflicts_are_zero_write",
        "zero_write_private_and_project_binding": "test_package_transform_rejects_private_or_project_binding_conflicting_evidence_without_write",
        "exact_duplicate_and_changed_duplicate": "test_package_transform_exact_duplicate_replays_and_changed_duplicate_is_zero_write",
        "full_checkpoint_tail_replay_terminal": "test_package_transform_full_and_checkpoint_tail_replay_match_and_is_terminal",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-construction-facility-package-transform-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{tests}::{test_name}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-construction-facility-package-transform",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(tests.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-construction-facility-package-transform-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "registered_row": {
            "package_id": "package:industrial-facilities",
            "package_revision": "package:industrial-facilities:v1",
            "content_digest": "sha256:41e1b40bcd1fd13e1692f2f51aed7dea6dceee0b1605bf215fe6c673fcd11f88",
            "owner_ref": "actor_gameplay.construction_production_domain",
            "stream_pattern": "gameplay:construction_production:{facility_ref}",
            "event_types": ["gameplay.construction_production.facility_transformed"],
            "projection_scope": "project",
        },
        "write_path": "GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch -> ConstructionProductionAuthority.projector/outbox",
        "limitations": [
            "Only the frozen package declaration and its one immutable descriptor binding may produce oven -> kiln.",
            "The operation is terminal and has no compensation, reversal, fanout, payment, material, or generic transform semantics.",
        ],
    }
    path = verification_dir(root) / "infra-construction-facility-package-transform-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-1AG Construction Facility Package Transform Report",
        {"results": [{"id": name, "status": "proved" if ok else "missing", "title": name} for name, ok in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_construction_facility_package_transform_report_json={path}")
    print(f"overall_infra_construction_facility_package_transform_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
