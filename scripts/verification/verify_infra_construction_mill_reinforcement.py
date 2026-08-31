from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    tests = root / "backend" / "tests" / "test_infra_construction_mill_reinforcement.py"
    cases = {
        "manifest_digest_and_exact_binding": "test_mill_manifest_digest_normalizes_and_binds_exact_descriptor",
        "digest_claim_zero_write": "test_mill_manifest_digest_claim_failures_are_nonmutating",
        "success_project_receipt": "test_mill_reinforcement_commits_fixed_project_event_and_append_receipt",
        "zero_write_package_and_revision": "test_mill_reinforcement_rejections_are_zero_write",
        "zero_write_unknown_active_package": "test_mill_reinforcement_unknown_active_package_is_zero_write",
        "zero_write_evidence_privacy": "test_mill_reinforcement_rejects_private_stale_or_conflicting_evidence_without_write",
        "zero_write_binding_and_digest": "test_mill_reinforcement_binding_and_digest_conflicts_are_zero_write",
        "idempotency_full_tail_terminal": "test_mill_reinforcement_duplicate_replay_and_checkpoint_tail_are_terminal",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-construction-mill-reinforcement-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{tests}::{test_name}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-construction-mill-reinforcement",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(tests.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-construction-mill-reinforcement-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "registered_row": {
            "package_id": "package:industrial-facilities",
            "package_revision": "package:industrial-facilities:v2",
            "content_digest": "sha256:8deea88c5e49c2aa06f30bbf1bd78ed103e26d8fb31769fe5564dbb7cc279896",
            "owner_ref": "actor_gameplay.construction_production_domain",
            "stream_pattern": "gameplay:construction_production:{facility_ref}",
            "event_types": ["gameplay.construction_production.facility_transformed"],
            "projection_scope": "project"
        },
        "write_path": "GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch -> ConstructionProductionAuthority.projector/outbox",
        "limitations": [
            "Only the frozen mill-to-mill_reinforced package declaration and exact immutable descriptor binding are admitted.",
            "The operation is terminal and has no compensation, reversal, fanout, payment, material, weather, maintenance, or generic transform semantics."
        ]
    }
    path = verification_dir(root) / "infra-construction-mill-reinforcement-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-1AG Construction Mill Reinforcement Report",
        {"results": [{"id": name, "status": "proved" if ok else "missing", "title": name} for name, ok in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_construction_mill_reinforcement_report_json={path}")
    print(f"overall_infra_construction_mill_reinforcement_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
