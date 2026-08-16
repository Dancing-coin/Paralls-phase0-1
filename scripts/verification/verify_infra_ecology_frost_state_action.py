from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    tests = root / "backend" / "tests" / "test_infra_ecology_frost_state_action.py"
    selectors = {
        "owner_two_event_append": "test_semantic_ecology_frost_dispel_cancels_exact_open_obligation_in_one_owner_batch",
        "exact_duplicate_replay": "test_semantic_ecology_frost_dispel_duplicate_replays_without_second_append",
        "changed_duplicate_zero_write": "test_semantic_ecology_frost_dispel_rejects_changed_duplicate_without_write",
        "inactive_source_zero_write": "test_semantic_ecology_frost_dispel_rejects_inactive_source_without_write",
        "revision_conflict_zero_write": "test_semantic_ecology_frost_dispel_rejects_stale_revision_without_write",
        "privacy_zero_write": "test_semantic_ecology_frost_dispel_rejects_private_input_without_write",
        "action_contract_zero_write": "test_semantic_ecology_frost_dispel_rejects_missing_action_contract_without_write",
        "full_checkpoint_tail_replay": "test_semantic_ecology_frost_dispel_replays_full_and_checkpoint_tail",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, selector in selectors.items():
        log_path = verification_dir(root) / f"infra-ecology-frost-state-action-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{tests}::{selector}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-ecology-frost-state-action",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(tests.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-ecology-frost-state-action-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "EcologyHazardAuthority",
        "stream": "gameplay:ecology:{region_ref}",
        "event_family": [
            "gameplay.ecology.crop_state_dispelled",
            "gameplay.ecology.crop_state_obligation_cancelled",
        ],
        "write_path": "Semantic proposal -> EcologyHazardAuthority -> GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch -> project outbox -> crop-state replay",
        "limitations": [
            "Only the fixed project-visible effect:frost/state:frosted@1 dispel action is admitted.",
            "It creates no generic action registration, repair/transform lifecycle, scheduler or cross-domain consumer edge.",
        ],
    }
    path = verification_dir(root) / "infra-ecology-frost-state-action-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-1Z Ecology Frost State-Action Report",
        {
            "results": [
                {"id": key, "status": "proved" if value else "missing", "title": key}
                for key, value in checks.items()
            ],
            "overall_passed": report["overall_passed"],
        },
        "overall_passed",
    )
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
