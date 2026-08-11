from __future__ import annotations

import argparse
import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from common import repo_root
from verify_phase4_common import run_focused, write_report


PROFILE_NAME = "phase5b-relationship-reputation-knowledge"
TEST_FILES = (
    "backend/tests/test_p5_social_knowledge.py",
    "backend/tests/test_p5_quest_evidence.py",
    "backend/tests/test_p5_contracts.py",
    "backend/tests/test_gameplay_p5_batch_contract.py",
)


@dataclass
class Phase5bScenarioEvidence:
    provenance: dict[str, object]
    permission_redaction: dict[str, object]
    decision_receipt: dict[str, object]
    replay_hash: dict[str, object]
    failure_zero_write: dict[str, object]
    errors: list[str] = field(default_factory=list)


def _load_test_module() -> Any:
    backend_root = repo_root() / "backend"
    sys.path.insert(0, str(backend_root))
    module_path = repo_root() / "backend" / "tests" / "test_p5_social_knowledge.py"
    spec = importlib.util.spec_from_file_location("phase5b_test_helpers", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"unable to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _unavailable(reason: str) -> Phase5bScenarioEvidence:
    payload = {"status": "unavailable", "reason": reason}
    return Phase5bScenarioEvidence(
        provenance=dict(payload),
        permission_redaction=dict(payload),
        decision_receipt=dict(payload),
        replay_hash=dict(payload),
        failure_zero_write=dict(payload),
        errors=[reason],
    )


def _view_payload(view: Any) -> dict[str, object]:
    return {
        "relationship_facts": [dict(fact) for fact in view.relationship_facts],
        "knowledge_facts": [dict(fact) for fact in view.knowledge_facts],
        "reputation": {target_ref: dict(relation_map) for target_ref, relation_map in view.reputation.items()},
        "source_revision_vector": dict(view.source_revision_vector),
        "projection_hash": view.projection_hash,
    }


def collect_phase5b_scenario_evidence() -> Phase5bScenarioEvidence:
    try:
        fixtures = _load_test_module()
        from app.gameplay.replay import GameplayProjectionReplay
    except Exception as exc:  # pragma: no cover - import failures are reported in the written profile report
        return _unavailable(f"scenario_import_failed:{exc}")

    try:
        registry = fixtures._registry()
        SocialFactAuthority = fixtures._load_authority()

        relationship_fact = fixtures._relationship_payload()
        knowledge_fact = fixtures._knowledge_payload()
        knowledge_stream = fixtures._knowledge_stream_ref(
            knower_ref=str(knowledge_fact["knower_ref"]),
            fact_ref=str(knowledge_fact["fact_ref"]),
        )
        proof_revisions = {
            str(relationship_fact["relationship_ref"]): 0,
            knowledge_stream: 0,
        }
        proof_store = fixtures.GameplayEventStore()
        proof_authority = SocialFactAuthority(registry=registry, store=proof_store)
        committed = proof_authority.resolve(
            command=fixtures._record_command(
                relationship_fact=relationship_fact,
                knowledge_fact=knowledge_fact,
                expected_revisions=proof_revisions,
                read_revisions=proof_revisions,
            ),
            request=fixtures._request(
                registry,
                relationship_fact=relationship_fact,
                knowledge_fact=knowledge_fact,
                expected_revisions=proof_revisions,
                read_revisions=proof_revisions,
            ),
            now="2026-08-11T00:00:00Z",
        )
        duplicate = proof_authority.resolve(
            command=fixtures._record_command(
                relationship_fact=relationship_fact,
                knowledge_fact=knowledge_fact,
                expected_revisions=proof_revisions,
                read_revisions=proof_revisions,
            ),
            request=fixtures._request(
                registry,
                relationship_fact=relationship_fact,
                knowledge_fact=knowledge_fact,
                expected_revisions=proof_revisions,
                read_revisions=proof_revisions,
            ),
            now="2026-08-11T00:00:00Z",
        )
        proof_public_view = proof_authority.view_for(recipient_ref="character:outsider", now="2026-08-11T00:00:00Z")
        proof_private_view = proof_authority.view_for(recipient_ref="character:baker:beta", now="2026-08-11T00:00:00Z")

        conflict_relationship = fixtures._relationship_payload(
            confidence=0.9,
            decay_rate_per_day=0.05,
            observed_at="2026-08-11T00:00:00Z",
        )
        conflict_knowledge_a = fixtures._knowledge_payload(
            fact_ref="fact:bakery:alibi",
            knower_ref="character:guard:alpha",
            subject_ref="character:baker:beta",
            visibility="public",
            confidence=0.9,
            decay_rate_per_day=0.1,
            observed_at="2026-08-11T00:00:00Z",
            observation_ref="observation:saw-baker-near-register",
        )
        conflict_store = fixtures.GameplayEventStore()
        conflict_authority = SocialFactAuthority(registry=registry, store=conflict_store)
        conflict_first_revisions = {
            str(conflict_relationship["relationship_ref"]): 0,
            fixtures._knowledge_stream_ref(
                knower_ref="character:guard:alpha",
                fact_ref="fact:bakery:alibi",
            ): 0,
        }
        conflict_first = conflict_authority.resolve(
            command=fixtures._record_command(
                request_id="request:p5:social:conflict:1",
                relationship_fact=conflict_relationship,
                knowledge_fact=conflict_knowledge_a,
                expected_revisions=conflict_first_revisions,
                read_revisions=conflict_first_revisions,
            ),
            request=fixtures._request(
                registry,
                request_id="request:p5:social:conflict:1",
                relationship_fact=conflict_relationship,
                knowledge_fact=conflict_knowledge_a,
                expected_revisions=conflict_first_revisions,
                read_revisions=conflict_first_revisions,
            ),
            now="2026-08-11T00:00:00Z",
        )
        conflict_knowledge_b = fixtures._knowledge_payload(
            fact_ref="fact:bakery:alibi",
            knower_ref="character:guard:alpha",
            subject_ref="character:baker:beta",
            visibility="public",
            confidence=0.8,
            decay_rate_per_day=0.05,
            observed_at="2026-08-12T00:00:00Z",
            observation_ref="observation:did-not-see-baker-near-register",
        )
        conflict_second = conflict_authority.resolve(
            command=fixtures._record_command(
                request_id="request:p5:social:conflict:2",
                relationship_fact=None,
                knowledge_fact=conflict_knowledge_b,
                expected_revisions={
                    fixtures._knowledge_stream_ref(
                        knower_ref="character:guard:alpha",
                        fact_ref="fact:bakery:alibi",
                    ): 1,
                },
                read_revisions={
                    fixtures._knowledge_stream_ref(
                        knower_ref="character:guard:alpha",
                        fact_ref="fact:bakery:alibi",
                    ): 1,
                },
            ),
            request=fixtures._request(
                registry,
                request_id="request:p5:social:conflict:2",
                relationship_ref=str(conflict_relationship["relationship_ref"]),
                knowledge_fact=conflict_knowledge_b,
                expected_revisions={
                    fixtures._knowledge_stream_ref(
                        knower_ref="character:guard:alpha",
                        fact_ref="fact:bakery:alibi",
                    ): 1,
                },
                read_revisions={
                    fixtures._knowledge_stream_ref(
                        knower_ref="character:guard:alpha",
                        fact_ref="fact:bakery:alibi",
                    ): 1,
                },
            ),
            now="2026-08-12T00:00:00Z",
        )
        conflict_public_view = conflict_authority.view_for(recipient_ref="character:outsider", now="2026-08-13T00:00:00Z")

        revocation_relationship = fixtures._relationship_payload()
        revocation_knowledge = fixtures._knowledge_payload()
        revocation_stream = fixtures._knowledge_stream_ref(
            knower_ref=str(revocation_knowledge["knower_ref"]),
            fact_ref=str(revocation_knowledge["fact_ref"]),
        )
        revocation_revisions = {
            str(revocation_relationship["relationship_ref"]): 0,
            revocation_stream: 0,
        }
        revocation_store = fixtures.GameplayEventStore()
        revocation_authority = SocialFactAuthority(registry=registry, store=revocation_store)
        revocation_first = revocation_authority.resolve(
            command=fixtures._record_command(
                request_id="request:p5:social:revocation:1",
                relationship_fact=revocation_relationship,
                knowledge_fact=revocation_knowledge,
                expected_revisions=revocation_revisions,
                read_revisions=revocation_revisions,
            ),
            request=fixtures._request(
                registry,
                request_id="request:p5:social:revocation:1",
                relationship_fact=revocation_relationship,
                knowledge_fact=revocation_knowledge,
                expected_revisions=revocation_revisions,
                read_revisions=revocation_revisions,
            ),
            now="2026-08-11T00:00:00Z",
        )
        revocation = {
            "fact_ref": str(revocation_knowledge["fact_ref"]),
            "knower_ref": str(revocation_knowledge["knower_ref"]),
            "recipient_ref": "character:baker:beta",
            "prior_visibility": str(revocation_knowledge["visibility"]),
        }
        revocation_result = revocation_authority.resolve(
            command=fixtures._revoke_command(
                request_id="request:p5:social:revocation:2",
                fact_ref=str(revocation_knowledge["fact_ref"]),
                knower_ref=str(revocation_knowledge["knower_ref"]),
                recipient_ref="character:baker:beta",
                prior_visibility=str(revocation_knowledge["visibility"]),
                expected_revisions={revocation_stream: 1},
                read_revisions={revocation_stream: 1},
            ),
            request=fixtures._request(
                registry,
                request_id="request:p5:social:revocation:2",
                relationship_ref=str(revocation_relationship["relationship_ref"]),
                revocation=revocation,
                expected_revisions={revocation_stream: 1},
                read_revisions={revocation_stream: 1},
            ),
            now="2026-08-11T01:00:00Z",
        )
        revocation_view = revocation_authority.view_for(recipient_ref="character:baker:beta", now="2026-08-11T01:00:00Z")

        replay_relationship = fixtures._relationship_payload()
        replay_knowledge_a = fixtures._knowledge_payload(
            visibility="public",
            knower_ref="character:guard:alpha",
            subject_ref="character:baker:beta",
            observation_ref="observation:public-ledger",
        )
        replay_store = fixtures.GameplayEventStore()
        replay_authority = SocialFactAuthority(registry=registry, store=replay_store)
        replay_first_revisions = {
            str(replay_relationship["relationship_ref"]): 0,
            fixtures._knowledge_stream_ref(
                knower_ref="character:guard:alpha",
                fact_ref=str(replay_knowledge_a["fact_ref"]),
            ): 0,
        }
        replay_first = replay_authority.resolve(
            command=fixtures._record_command(
                request_id="request:p5:social:reload:1",
                relationship_fact=replay_relationship,
                knowledge_fact=replay_knowledge_a,
                expected_revisions=replay_first_revisions,
                read_revisions=replay_first_revisions,
            ),
            request=fixtures._request(
                registry,
                request_id="request:p5:social:reload:1",
                relationship_fact=replay_relationship,
                knowledge_fact=replay_knowledge_a,
                expected_revisions=replay_first_revisions,
                read_revisions=replay_first_revisions,
            ),
            now="2026-08-11T00:00:00Z",
        )
        replay_checkpoint_path = Path(repo_root()) / ".harness" / "verification" / "phase5b-relationship-reputation-knowledge-checkpoint.json"
        replay_store.save_snapshot(replay_checkpoint_path)

        replay_knowledge_b = fixtures._knowledge_payload(
            fact_ref="fact:bakery:alibi",
            knower_ref="character:guard:alpha",
            subject_ref="character:baker:beta",
            visibility="public",
            confidence=0.8,
            decay_rate_per_day=0.05,
            observed_at="2026-08-12T00:00:00Z",
            observation_ref="observation:checkpoint-tail",
        )
        replay_second_revisions = {
            fixtures._knowledge_stream_ref(
                knower_ref="character:guard:alpha",
                fact_ref="fact:bakery:alibi",
            ): 0,
        }
        replay_command_two = fixtures._record_command(
            request_id="request:p5:social:reload:2",
            relationship_fact=None,
            knowledge_fact=replay_knowledge_b,
            expected_revisions=replay_second_revisions,
            read_revisions=replay_second_revisions,
        )
        replay_request_two = fixtures._request(
            registry,
            request_id="request:p5:social:reload:2",
            relationship_ref=str(replay_relationship["relationship_ref"]),
            knowledge_fact=replay_knowledge_b,
            expected_revisions=replay_second_revisions,
            read_revisions=replay_second_revisions,
        )
        replay_live_second = replay_authority.resolve(
            command=replay_command_two,
            request=replay_request_two,
            now="2026-08-12T00:00:00Z",
        )
        replay_checkpoint_store = fixtures.GameplayEventStore.load_snapshot(replay_checkpoint_path)
        replay_checkpoint_authority = SocialFactAuthority(registry=registry, store=replay_checkpoint_store)
        replay_checkpoint_second = replay_checkpoint_authority.resolve(
            command=replay_command_two,
            request=replay_request_two,
            now="2026-08-12T00:00:00Z",
        )
        replay_full_path = Path(repo_root()) / ".harness" / "verification" / "phase5b-relationship-reputation-knowledge-full.json"
        replay_store.save_snapshot(replay_full_path)
        replay_full_store = fixtures.GameplayEventStore.load_snapshot(replay_full_path)
        replay_full_authority = SocialFactAuthority(registry=registry, store=replay_full_store)

        replay_live_view = replay_authority.view_for(recipient_ref="character:outsider", now="2026-08-13T00:00:00Z")
        replay_checkpoint_view = replay_checkpoint_authority.view_for(recipient_ref="character:outsider", now="2026-08-13T00:00:00Z")
        replay_full_view = replay_full_authority.view_for(recipient_ref="character:outsider", now="2026-08-13T00:00:00Z")
        replay_events = replay_store.read_events()
        replay_runtime = GameplayProjectionReplay(projector_id="verification:phase5b", projector_version="v1")
        replay_full = replay_runtime.full_replay(replay_events)
        replay_split_at = max(1, len(replay_events) // 2)
        replay_checkpoint = replay_runtime.create_checkpoint(replay_events[:replay_split_at])
        replay_checkpoint_tail = replay_runtime.checkpoint_plus_tail_replay(
            replay_checkpoint,
            replay_events[replay_split_at:],
        )

        failure_store = fixtures.GameplayEventStore()
        failure_authority = SocialFactAuthority(registry=registry, store=failure_store)
        failure_relationship = fixtures._relationship_payload()
        failure_knowledge = fixtures._knowledge_payload()
        failure_revisions = {
            str(failure_relationship["relationship_ref"]): 0,
            fixtures._knowledge_stream_ref(
                knower_ref=str(failure_knowledge["knower_ref"]),
                fact_ref=str(failure_knowledge["fact_ref"]),
            ): 0,
        }
        failure_first = failure_authority.resolve(
            command=fixtures._record_command(
                relationship_fact=failure_relationship,
                knowledge_fact=failure_knowledge,
                expected_revisions=failure_revisions,
                read_revisions=failure_revisions,
            ),
            request=fixtures._request(
                registry,
                relationship_fact=failure_relationship,
                knowledge_fact=failure_knowledge,
                expected_revisions=failure_revisions,
                read_revisions=failure_revisions,
            ),
            now="2026-08-11T00:00:00Z",
        )
        before_failure_events = len(failure_store.read_events())
        stale_result = failure_authority.resolve(
            command=fixtures._record_command(
                request_id="request:p5:social:stale",
                relationship_fact=failure_relationship,
                knowledge_fact=failure_knowledge,
                expected_revisions=failure_revisions,
                read_revisions=failure_revisions,
            ),
            request=fixtures._request(
                registry,
                request_id="request:p5:social:stale",
                relationship_fact=failure_relationship,
                knowledge_fact=failure_knowledge,
                expected_revisions=failure_revisions,
                read_revisions=failure_revisions,
            ),
            now="2026-08-11T00:00:00Z",
        )
        after_failure_events = len(failure_store.read_events())

        return Phase5bScenarioEvidence(
            provenance={
                "provider_ref": "provider:evidence:social-observer",
                "registry_ref": registry.registry_ref,
                "registry_digest": registry.registry_digest,
                "relationship_ref": relationship_fact["relationship_ref"],
                "relationship_event_visibility": relationship_fact["visibility"],
                "knowledge_stream_ref": knowledge_stream,
                "knowledge_fact_ref": knowledge_fact["fact_ref"],
                "knowledge_event_visibility": knowledge_fact["visibility"],
                "committed_event_ids": list(committed.receipt.committed_event_ids) if committed.receipt else [],
                "duplicate_committed_event_ids": list(duplicate.receipt.committed_event_ids) if duplicate.receipt else [],
                "conflict_observation_refs": [
                    conflict_knowledge_a["observation_ref"],
                    conflict_knowledge_b["observation_ref"],
                ],
                "revocation_stream_ref": revocation_stream,
                "revocation_recipient_ref": revocation["recipient_ref"],
                "replay_checkpoint_path": str(replay_checkpoint_path),
                "replay_full_path": str(replay_full_path),
            },
            permission_redaction={
                "public_view": _view_payload(proof_public_view),
                "private_view": _view_payload(proof_private_view),
                "public_relationship_fact_has_evidence_ref": "evidence_ref" in proof_public_view.relationship_facts[0],
                "public_relationship_visibility": proof_public_view.relationship_facts[0]["visibility"],
                "public_knowledge_count": len(proof_public_view.knowledge_facts),
                "private_knowledge_count": len(proof_private_view.knowledge_facts),
                "private_knowledge_fact_ref": proof_private_view.knowledge_facts[0]["fact_ref"],
                "conflict_public_view": _view_payload(conflict_public_view),
                "conflict_public_knowledge_refs": [
                    fact["observation_ref"] for fact in conflict_public_view.knowledge_facts
                ],
                "conflict_public_reputation": conflict_public_view.reputation,
                "revocation_recipient_view": _view_payload(revocation_view),
                "revocation_recipient_knowledge_count_after": len(revocation_view.knowledge_facts),
                "revocation_projection_refresh_reason": (
                    revocation_result.receipt.projection_refresh_hints[0].reason
                    if revocation_result.receipt and revocation_result.receipt.projection_refresh_hints
                    else None
                ),
            },
            decision_receipt={
                "result_kind": committed.resolution.result_kind,
                "committed": bool(committed.receipt and committed.receipt.committed),
                "transaction_id": committed.receipt.transaction_id if committed.receipt else None,
                "committed_event_ids": list(committed.receipt.committed_event_ids) if committed.receipt else [],
                "idempotency_status": committed.receipt.idempotency_status if committed.receipt else None,
                "duplicate_result_kind": duplicate.resolution.result_kind,
                "duplicate_idempotency_status": duplicate.receipt.idempotency_status if duplicate.receipt else None,
                "duplicate_transaction_id": duplicate.receipt.transaction_id if duplicate.receipt else None,
                "duplicate_committed_event_ids": list(duplicate.receipt.committed_event_ids) if duplicate.receipt else [],
                "settlement_plan_event_mapping": dict(committed.settlement_plan.event_mapping) if committed.settlement_plan else {},
                "conflict_result_kind": conflict_first.resolution.result_kind,
                "conflict_second_result_kind": conflict_second.resolution.result_kind,
                "revocation_result_kind": revocation_result.resolution.result_kind,
                "revocation_idempotency_status": revocation_result.receipt.idempotency_status if revocation_result.receipt else None,
                "revocation_projection_refresh_hints": [
                    {
                        "projection_id": hint.projection_id,
                        "stream_id": hint.stream_id,
                        "reason": hint.reason,
                        "actor_refs": list(hint.actor_refs),
                    }
                    for hint in (revocation_result.receipt.projection_refresh_hints if revocation_result.receipt else [])
                ],
            },
            replay_hash={
                "event_count": len(replay_events),
                "snapshot_hash": fixtures._snapshot_hash(replay_store),
                "full_replay_succeeded": replay_full.succeeded,
                "checkpoint_tail_succeeded": replay_checkpoint_tail.succeeded,
                "full_replay_projection_hash": replay_full.projection_hash,
                "checkpoint_tail_projection_hash": replay_checkpoint_tail.projection_hash,
                "live_view_projection_hash": replay_live_view.projection_hash,
                "checkpoint_tail_view_projection_hash": replay_checkpoint_view.projection_hash,
                "full_view_projection_hash": replay_full_view.projection_hash,
                "replay_hash": replay_live_view.projection_hash,
                "checkpoint_tail_hash": replay_checkpoint_view.projection_hash,
                "full_result_kind": replay_live_second.resolution.result_kind,
                "checkpoint_tail_result_kind": replay_checkpoint_second.resolution.result_kind,
            },
            failure_zero_write={
                "result_kind": stale_result.resolution.result_kind,
                "failure_code": stale_result.resolution.failure_code,
                "zero_write": before_failure_events == after_failure_events,
                "event_count_before": before_failure_events,
                "event_count_after": after_failure_events,
                "first_commit_result_kind": failure_first.resolution.result_kind,
            },
        )
    except Exception as exc:  # pragma: no cover - profile output should capture this directly
        return _unavailable(f"scenario_collection_failed:{exc}")


def _scenario_passed(scenario: Phase5bScenarioEvidence) -> bool:
    if scenario.errors:
        return False

    provenance = scenario.provenance
    permission = scenario.permission_redaction
    decision = scenario.decision_receipt
    replay = scenario.replay_hash
    failure = scenario.failure_zero_write
    return bool(
        decision.get("result_kind") == "committed_success"
        and decision.get("committed") is True
        and decision.get("duplicate_result_kind") == "committed_success"
        and decision.get("duplicate_transaction_id") == decision.get("transaction_id")
        and decision.get("duplicate_committed_event_ids") == decision.get("committed_event_ids")
        and permission.get("public_relationship_fact_has_evidence_ref") is False
        and permission.get("public_knowledge_count") == 0
        and permission.get("private_knowledge_count") == 1
        and permission.get("private_knowledge_fact_ref")
        and permission.get("conflict_public_reputation", {}).get("character:baker:beta", {}).get("suspects") == 0.8
        and permission.get("revocation_recipient_knowledge_count_after") == 0
        and permission.get("revocation_projection_refresh_reason") == "visibility_revoked"
        and replay.get("full_replay_succeeded") is True
        and replay.get("checkpoint_tail_succeeded") is True
        and replay.get("full_replay_projection_hash")
        and replay.get("full_replay_projection_hash") == replay.get("checkpoint_tail_projection_hash")
        and replay.get("replay_hash")
        and replay.get("replay_hash") == replay.get("checkpoint_tail_hash") == replay.get("full_view_projection_hash")
        and failure.get("result_kind") == "rejected_zero_write"
        and failure.get("failure_code") == "p5_revision_stale"
        and failure.get("zero_write") is True
        and provenance.get("provider_ref") == "provider:evidence:social-observer"
    )


def build_report(
    *,
    focused_ok: bool,
    focused_log: str,
    scenario: Phase5bScenarioEvidence,
) -> dict[str, object]:
    report: dict[str, object] = {
        "overall_passed": focused_ok and _scenario_passed(scenario),
        "focused_tests_passed": focused_ok,
        "focused_test_files": list(TEST_FILES),
        "focused_log": focused_log,
        "provenance": scenario.provenance,
        "permission_redaction": scenario.permission_redaction,
        "decision_receipt": scenario.decision_receipt,
        "replay_hash": scenario.replay_hash,
        "failure_zero_write": scenario.failure_zero_write,
    }
    if scenario.errors:
        report["errors"] = list(scenario.errors)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    parser.parse_args(argv)

    focused_ok, focused_log = run_focused(*TEST_FILES)
    scenario = collect_phase5b_scenario_evidence()
    report = build_report(focused_ok=focused_ok, focused_log=focused_log, scenario=scenario)
    return write_report(PROFILE_NAME, report)


if __name__ == "__main__":
    raise SystemExit(main())
