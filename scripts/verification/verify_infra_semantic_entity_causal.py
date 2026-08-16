from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_semantic_entity_causal.py"
    test_cases = {
        "tag_inheritance_and_snapshot_digest": "test_snapshot_inheritance_selector_and_digest_are_deterministic",
        "selector_and_parameter_conflict_rejection": "test_semantic_registry_rejects_cycle_unknown_and_same_specificity_conflict_without_mutation",
        "event_derived_entity_and_causal_projection": "test_causal_projection_derives_parent_and_children_without_writes",
        "incremental_replay_equivalence": "test_causal_projection_incremental_replay_matches_full_rebuild",
        "rejected_input_does_not_mutate_projection": "test_rejected_projection_input_does_not_mutate_existing_projection",
        "authority_append_and_outbox": "test_semantic_authority_success_writes_one_event_and_outbox_entry",
        "authority_duplicate_idempotency": "test_semantic_authority_duplicate_replays_without_second_write",
        "authority_privacy_scope": "test_semantic_authority_scoped_projection_redacts_evidence_from_public",
        "authority_checkpoint_tail_replay": "test_semantic_authority_checkpoint_tail_replay_matches_full",
        "authority_revision_conflict_zero_write": "test_semantic_authority_revision_conflict_is_zero_write",
        "authority_private_proposal_zero_write": "test_semantic_authority_private_proposal_is_zero_write",
        "meta_rule_phase_chain_and_filtered_trace": "test_meta_rule_enforces_phase_conflict_chain_budget_and_filtered_trace",
    }
    logs: list[str] = []
    checks: dict[str, bool] = {}
    for check, test_name in test_cases.items():
        log_path = verification_dir(root) / f"infra-semantic-entity-causal-{check}.log"
        result = run_command(
            [python, "-m", "pytest", "-q", str(test_path), "-k", test_name],
            root,
            log_path,
        )
        checks[check] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    lifecycle_test_path = root / "backend" / "tests" / "test_semantic_effect_lifecycle.py"
    lifecycle_cases = {
        "effect_resistance_and_serialized_expiry_proposal": "test_effect_lifecycle_applies_resistance_and_emits_expiry_obligation",
        "effect_state_overflow_zero_mutation": "test_effect_lifecycle_rejects_overflow_without_state_mutation",
    }
    for check, test_name in lifecycle_cases.items():
        log_path = verification_dir(root) / f"infra-semantic-entity-causal-{check}.log"
        result = run_command(
            [python, "-m", "pytest", "-q", str(lifecycle_test_path), "-k", test_name],
            root,
            log_path,
        )
        checks[check] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-semantic-entity-causal",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [
            str(test_path.relative_to(root)).replace("\\", "/"),
            str(lifecycle_test_path.relative_to(root)).replace("\\", "/"),
        ],
        "evidence": logs,
        "run_id": f"infra-semantic-entity-causal-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": [
            "backend/app/gameplay/semantic_registry.py",
            "backend/app/gameplay/entity_causal_projection.py",
            "backend/app/gameplay/semantic_authority.py",
        ],
        "write_path": "domain authority -> GameplayEventStore.append_batch -> event/replay -> EntityCausalProjection",
        "freshness": "invalidated by semantic registry, entity projection, event schema, or focused-test changes",
        "limitations": [
            "The documented semantic vertical is implemented; broader cross-domain owner coverage and a richer untrusted-rule language remain out of scope.",
            "The expiry obligation is a serialized evaluator proposal only; no event-derived ScheduledObligation lifecycle is proved by this profile.",
            "Entity/causal projection remains read-only; only existing authorities write through the event spine.",
        ],
    }
    path = verification_dir(root) / "infra-semantic-entity-causal-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-1 Semantic Entity Causal Report",
        {
            "results": [
                {"id": name, "status": "proved" if status else "missing", "title": name}
                for name, status in checks.items()
            ],
            "overall_passed": report["overall_passed"],
        },
        "overall_passed",
    )
    print(f"infra_semantic_entity_causal_report_json={path}")
    print(f"overall_infra_semantic_entity_causal_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
