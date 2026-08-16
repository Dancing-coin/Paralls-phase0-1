from __future__ import annotations

from datetime import datetime, timezone

from common import (
    evidence_revision,
    repo_root,
    resolve_python_exe,
    run_command,
    verification_dir,
    write_json,
    write_markdown,
)


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_activation_profile_region_assignment.py"
    cases = {
        "activation_owner_project_evidence_append": "test_profile_region_assignment_commits_only_activation_fragment_from_project_ecology_evidence",
        "forged_evidence_zero_write": "test_profile_region_assignment_rejects_forged_ecology_evidence_without_write",
        "private_evidence_zero_write": "test_profile_region_assignment_rejects_private_ecology_evidence_without_write",
        "inactive_profile_zero_write": "test_profile_region_assignment_rejects_inactive_profile_without_write",
        "duplicate_idempotency": "test_profile_region_assignment_exact_duplicate_replays_without_second_write",
        "activation_revision_zero_write": "test_profile_region_assignment_rejects_stale_activation_revision_without_write",
        "ecology_source_revision_zero_write": "test_profile_region_assignment_rejects_stale_ecology_source_revision_without_write",
        "changed_idempotency_zero_write": "test_profile_region_assignment_rejects_changed_idempotency_reuse_without_write",
        "reader_privacy_scope": "test_profile_region_assignment_rejects_nonproject_reader",
        "checkpoint_tail_scoped_projection_replay": "test_profile_region_assignment_checkpoint_tail_replay_matches_full",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-activation-profile-region-assignment-{check}.log"
        result = run_command(
            [python, "-m", "pytest", "-q", str(test_path), "-k", test_name],
            root,
            log_path,
        )
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-activation-profile-region-assignment",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-activation-profile-region-assignment-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owners": ["ProfileActivationAuthority", "EcologyHazardAuthority"],
        "activation_stream": "population:{world_ref}",
        "ecology_source_stream": "gameplay:ecology:{region_ref}",
        "target_event": "population.activation.region_assigned",
        "write_path": "ProfileActivationAuthority -> GameplayCommandEnvelope -> OwnerAuthorizedFragment / AppendDerivedSettlementRecipe -> GameplayEventStore.append_batch() -> outbox/replay -> project-scoped profile-region projection",
        "receipt_boundary": "The returned ActivationReceipt is derived solely from the activation append result; Ecology remains evidence owner and never writes the population stream.",
        "limitations": [
            "This is one fixed project-visible ecology-region evidence row. It does not infer location from profile homeland, Godot/client position, or household residence.",
            "It does not write Survival state or admit weather-front-to-Survival. That future edge still requires its own Survival owner fragment and receipt contract.",
            "No population/NPC/social truth owner, scheduler, generic location system, branch promotion, SOC, GAME, P6, or P7 work is admitted."
        ]
    }
    path = verification_dir(root) / "infra-activation-profile-region-assignment-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-4AC Activation-Owned Profile Region Assignment Report",
        {
            "results": [
                {"id": key, "status": "proved" if value else "missing", "title": key}
                for key, value in checks.items()
            ],
            "overall_passed": report["overall_passed"],
        },
        "overall_passed",
    )
    print(f"infra_activation_profile_region_assignment_report_json={path}")
    print(f"overall_infra_activation_profile_region_assignment_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
