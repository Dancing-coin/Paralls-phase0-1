from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_civilization_capability_read.py"
    cases = {
        "canonical_activation_outbox": "test_civilization_capability_activation_uses_one_canonical_stream_and_outbox",
        "wrong_authority_zero_write": "test_civilization_capability_rejects_wrong_authority_without_writes",
        "duplicate_and_changed_duplicate": "test_civilization_capability_duplicate_is_idempotent_but_changed_duplicate_is_zero_write",
        "revision_conflict_zero_write": "test_civilization_capability_rejects_revision_conflict_without_writes",
        "jurisdiction_effective_tick_authority_public_scope": "test_civilization_capability_view_enforces_jurisdiction_effective_tick_and_privacy_scope",
        "actor_scope": "test_civilization_capability_scope_filtering_is_independent_for_actor_creator_and_public",
        "creator_scope": "test_civilization_capability_creator_scope_is_not_an_actor_or_public_view",
        "source_revision_zero_write": "test_civilization_capability_read_rejects_stale_source_revision_without_writes",
        "revoke_correction_replay": "test_civilization_capability_revoke_and_correction_are_event_derived_and_replay_equivalent",
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-civilization-capability-read-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-civilization-capability-read",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": logs,
        "run_id": f"infra-civilization-capability-read-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": ["backend/app/gameplay/civilization_capability_runtime.py"],
        "stream": "gameplay:civilization_capability:{jurisdiction_ref}",
        "event_family": [
            "gameplay.civilization_capability.activated",
            "gameplay.civilization_capability.revoked",
            "gameplay.civilization_capability.corrected",
        ],
        "write_path": "CivilizationCapabilityAuthority -> OwnerAuthorizedFragment -> GameplayEventStore.append_batch -> outbox/replay -> scoped projection",
        "limitations": [
            "This is INF-4Y-A owner admission only; no semantic or population consumer binding is supported.",
            "No progression, six-axis propagation, institution system, scheduler, generic policy writer, P6, or P7 work is admitted.",
        ],
    }
    path = verification_dir(root) / "infra-civilization-capability-read-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-4Y-A Civilization Capability Read Report",
        {"results": [{"id": name, "status": "proved" if ok else "missing", "title": name} for name, ok in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_civilization_capability_read_report_json={path}")
    print(f"overall_infra_civilization_capability_read_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
