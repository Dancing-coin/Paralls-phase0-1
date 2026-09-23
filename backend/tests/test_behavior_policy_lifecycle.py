from pathlib import Path

import pytest

from app.character_agent.models.behavior_policy import BehaviorPolicyRecord
from app.character_agent.storage.behavior_policy_store import BehaviorPolicyStore


def recovery_policy(
    *,
    actor_id: str,
    max_consumptions: int,
    expires_at: int,
) -> BehaviorPolicyRecord:
    return BehaviorPolicyRecord(
        policy_id=f"policy:{actor_id}:recovery",
        actor_id=actor_id,
        source_turn_id="turn:source:1",
        branch_id="branch:main",
        valid_at=100,
        causation_id="cause:source:1",
        correlation_id="correlation:source:1",
        source_revision=1,
        policy_type="recovery",
        failed_intent="share_info",
        hypothesis="try a different locally viable action",
        status="accepted",
        created_at=100,
        expires_at=expires_at,
        max_consumptions=max_consumptions,
        failure_window=60,
        evidence_refs=["settlement:1"],
        idempotency_key=f"idempotency:{actor_id}:recovery",
    )


def test_policy_consumption_is_idempotent_across_restart(tmp_path: Path) -> None:
    store = BehaviorPolicyStore(tmp_path)
    policy = store.propose(
        recovery_policy(actor_id="char_b", max_consumptions=2, expires_at=300)
    )

    assert store.consume("char_b", policy.policy_id, "turn:char_b:2", now=200).applied

    restored = BehaviorPolicyStore(tmp_path)
    replay = restored.consume("char_b", policy.policy_id, "turn:char_b:2", now=200)

    assert replay.replayed is True
    assert replay.record.consumed_count == 1


def test_policy_store_rejects_cross_actor_and_altered_idempotency_payload(tmp_path: Path) -> None:
    store = BehaviorPolicyStore(tmp_path)
    policy = store.propose(
        recovery_policy(actor_id="char_b", max_consumptions=2, expires_at=300)
    )

    with pytest.raises(ValueError, match="behavior_policy_actor_forbidden"):
        store.consume("char_a", policy.policy_id, "turn:char_a:2", now=200)
    with pytest.raises(ValueError, match="behavior_policy_idempotency_conflict"):
        store.propose(
            recovery_policy(actor_id="char_b", max_consumptions=1, expires_at=300)
        )


def test_policy_store_expires_and_enforces_declared_consumption_limit(tmp_path: Path) -> None:
    store = BehaviorPolicyStore(tmp_path)
    expired = store.propose(
        recovery_policy(actor_id="char_b", max_consumptions=1, expires_at=200)
    )
    expiry = store.consume("char_b", expired.policy_id, "turn:char_b:2", now=200)

    assert expiry.applied is False
    assert expiry.reason == "expired"
    assert expiry.record.status == "expired"

    active = store.propose(
        BehaviorPolicyRecord(
            **{
                **recovery_policy(actor_id="char_b", max_consumptions=1, expires_at=300).model_dump(),
                "policy_id": "policy:char_b:limited",
                "idempotency_key": "idempotency:char_b:limited",
            }
        )
    )
    assert store.consume("char_b", active.policy_id, "turn:char_b:3", now=201).applied
    limited = store.consume("char_b", active.policy_id, "turn:char_b:4", now=202)

    assert limited.applied is False
    assert limited.reason == "max_consumptions_reached"
    assert limited.record.consumed_count == 1


def test_policy_reconciliation_supersedes_prior_policy_and_rolls_back_on_success(tmp_path: Path) -> None:
    store = BehaviorPolicyStore(tmp_path)
    original = store.propose(
        recovery_policy(actor_id="char_b", max_consumptions=2, expires_at=300)
    )
    successor = store.propose(
        BehaviorPolicyRecord(
            **{
                **recovery_policy(actor_id="char_b", max_consumptions=2, expires_at=300).model_dump(),
                "policy_id": "policy:char_b:successor",
                "idempotency_key": "idempotency:char_b:successor",
                "supersedes_policy_id": original.policy_id,
                "policy_revision": 2,
            }
        )
    )

    assert store.get("char_b", original.policy_id).status == "superseded"
    assert store.reconcile_outcome(
        "char_b", successor.policy_id, successor.source_turn_id, "success", now=210
    ).status == "rolled_back"


def test_policy_proposal_and_reconciliation_replay_the_same_lifecycle_result(tmp_path: Path) -> None:
    store = BehaviorPolicyStore(tmp_path)
    proposed = recovery_policy(actor_id="char_b", max_consumptions=2, expires_at=300).model_copy(
        update={"status": "candidate"}
    )
    store.propose(proposed)
    accepted = store.reconcile_outcome(
        "char_b", proposed.policy_id, proposed.source_turn_id, "evidence_qualified", now=200
    )

    assert store.propose(proposed).status == "accepted"
    assert store.reconcile_outcome(
        "char_b", proposed.policy_id, proposed.source_turn_id, "evidence_qualified", now=200
    ) == accepted


def test_policy_requires_turn_scope_lineage_and_cannot_reopen_terminal_state(tmp_path: Path) -> None:
    invalid = recovery_policy(actor_id="char_b", max_consumptions=2, expires_at=300).model_copy(update={"branch_id": ""})
    with pytest.raises(ValueError, match="branch_id"):
        BehaviorPolicyRecord.model_validate(invalid.model_dump())

    store = BehaviorPolicyStore(tmp_path)
    policy = store.propose(recovery_policy(actor_id="char_b", max_consumptions=2, expires_at=300))
    rolled_back = store.reconcile_outcome(
        "char_b", policy.policy_id, policy.source_turn_id, "success", now=200
    )

    assert rolled_back.transition_revision == 1
    assert store.reconcile_outcome(
        "char_b", policy.policy_id, policy.source_turn_id, "accepted", now=201
    ).status == "rolled_back"


def test_policy_store_merges_compatible_failures_within_window_and_rejects_stale_snapshot(tmp_path: Path) -> None:
    store = BehaviorPolicyStore(tmp_path)
    first = store.propose(recovery_policy(actor_id="char_b", max_consumptions=2, expires_at=300))
    second = store.propose(
        recovery_policy(actor_id="char_b", max_consumptions=2, expires_at=300).model_copy(
            update={"policy_id": "policy:char_b:recovery:next", "idempotency_key": "key:next", "created_at": 110}
        )
    )

    assert second.policy_id == first.policy_id
    assert second.failure_count == 2
    newer = store.reconcile_outcome("char_b", first.policy_id, first.source_turn_id, "accepted", now=120)
    store.restore_continuity_snapshot("char_b", {"records": [first.model_dump()]})

    assert store.get("char_b", first.policy_id) == newer


def test_successful_settlement_rolls_back_only_exactly_linked_consumption(tmp_path: Path) -> None:
    store = BehaviorPolicyStore(tmp_path)
    policy = store.propose(recovery_policy(actor_id="char_b", max_consumptions=2, expires_at=300))
    store.consume("char_b", policy.policy_id, "turn:char_b:2", 200, causation_id="cause:turn:2", correlation_id="corr:turn:2")

    assert store.reconcile_consumed_turn("char_b", "turn:char_b:2", "success", 210, causation_id="cause:other", correlation_id="corr:turn:2") is None
    rolled_back = store.reconcile_consumed_turn("char_b", "turn:char_b:2", "success", 210, causation_id="cause:turn:2", correlation_id="corr:turn:2")

    assert rolled_back is not None and rolled_back.status == "rolled_back"
