import pytest

from app.gameplay.debt_runtime import (
    DebtAuthorityService,
    DebtRuntimeError,
    DebtSettlementEventSpec,
    DebtSettlementPlan,
)
from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.shared_contracts import GameplayCommandEnvelope


def _service() -> tuple[GameplayEventStore, DebtAuthorityService]:
    store = GameplayEventStore()
    economy = EconomyAuthorityService(store=store)
    assert economy.open_account(
        command_id="inf2l:creditor-account",
        account_id="account:creditor",
        owner_ref="actor:creditor",
        currency_ref="currency:local",
        initial_balance=20,
        idempotency_key="inf2l:creditor-account",
        causation_id="cause:inf2l",
        correlation_id="corr:inf2l",
    ).committed
    assert economy.open_account(
        command_id="inf2l:debtor-account",
        account_id="account:debtor",
        owner_ref="actor:debtor",
        currency_ref="currency:local",
        initial_balance=1,
        idempotency_key="inf2l:debtor-account",
        causation_id="cause:inf2l",
        correlation_id="corr:inf2l",
    ).committed
    return store, DebtAuthorityService(store=store)


def _issue(store: GameplayEventStore, debt: DebtAuthorityService, *, key: str = "inf2l:issue"):
    return debt.issue_simple_debt(
        command_id="inf2l:issue",
        contract_id="contract:inf2l",
        debt_id="debt:inf2l",
        creditor_ref="actor:creditor",
        debtor_ref="actor:debtor",
        creditor_account_id="account:creditor",
        debtor_account_id="account:debtor",
        currency_ref="currency:local",
        principal_amount=8,
        due_tick=3,
        idempotency_key=key,
        causation_id="cause:inf2l:issue",
        correlation_id="corr:inf2l:issue",
    )


def _pay(debt: DebtAuthorityService, *, key: str = "inf2l:payment"):
    return debt.pay_debt(
        command_id="inf2l:payment",
        debt_id="debt:inf2l",
        debtor_account_id="account:debtor",
        creditor_account_id="account:creditor",
        amount=8,
        idempotency_key=key,
        causation_id="cause:inf2l:payment",
        correlation_id="corr:inf2l:payment",
    )

def test_simple_debt_issue_uses_formal_owner_fragments_and_redacted_outbox() -> None:
    store, debt = _service()

    result = _issue(store, debt)

    assert result.committed
    transaction = store.read_transactions()[-1]
    assert transaction.transaction_id == "transaction:inf2l:issue"
    assert transaction.expected_stream_revisions == {
        "gameplay:economy": 2,
        "gameplay:contracts": 0,
        "gameplay:debt": 0,
        "gameplay:commerce": 0,
    }
    assert transaction.read_stream_revisions == transaction.expected_stream_revisions
    assert {fragment.owner_principal_ref for fragment in transaction.owner_fragments} == {
        "actor_gameplay.debt_domain"
    }
    assert {stream for fragment in transaction.owner_fragments for stream in fragment.event_specs} == set(
        transaction.expected_stream_revisions
    )
    outbox = [entry for entry in store.list_outbox() if entry.transaction_id == transaction.transaction_id]
    assert len(outbox) == len(transaction.events)
    assert all(entry.audience == "authority" for entry in outbox)
    assert all(
        not ({"account_id", "amount", "creditor_ref", "debtor_ref", "reason"} & entry.payload_projection.keys())
        for entry in outbox
    )


def test_simple_debt_payment_uses_formal_owner_fragments_and_redacted_outbox() -> None:
    store, debt = _service()
    assert _issue(store, debt).committed

    result = _pay(debt)

    assert result.committed
    transaction = store.read_transactions()[-1]
    assert transaction.transaction_id == "transaction:inf2l:payment"
    assert transaction.expected_stream_revisions == {
        "gameplay:economy": 4,
        "gameplay:contracts": 1,
        "gameplay:debt": 1,
        "gameplay:commerce": 1,
    }
    assert transaction.read_stream_revisions == transaction.expected_stream_revisions
    assert {fragment.owner_principal_ref for fragment in transaction.owner_fragments} == {
        "actor_gameplay.debt_domain"
    }
    assert {stream for fragment in transaction.owner_fragments for stream in fragment.event_specs} == set(
        transaction.expected_stream_revisions
    )
    outbox = [entry for entry in store.list_outbox() if entry.transaction_id == transaction.transaction_id]
    assert len(outbox) == len(transaction.events)
    assert all(entry.audience == "authority" for entry in outbox)
    assert all(
        not ({"account_id", "amount", "creditor_ref", "debtor_ref", "reason"} & entry.payload_projection.keys())
        for entry in outbox
    )


def test_simple_debt_issue_preserves_legacy_event_family_order_and_payload_contract() -> None:
    store, debt = _service()

    result = _issue(store, debt)

    assert result.committed
    events = store.read_transactions()[-1].events
    assert [event.event_type for event in events] == [
        "gameplay.economy.account_debited",
        "gameplay.economy.account_credited",
        "gameplay.contract.simple_debt_created",
        "gameplay.debt.claim_issued",
        "gameplay.commerce.debt_issued_settled",
    ]
    assert events[0].payload == {"account_id": "account:creditor", "amount": 8}
    assert events[1].payload == {"account_id": "account:debtor", "amount": 8}
    assert events[3].payload == {
        "debt_id": "debt:inf2l",
        "contract_id": "contract:inf2l",
        "creditor_ref": "actor:creditor",
        "debtor_ref": "actor:debtor",
        "currency_ref": "currency:local",
        "principal_amount": 8,
        "due_tick": 3,
    }


def test_simple_debt_formal_spine_replays_exact_duplicate_without_second_append() -> None:
    store, debt = _service()
    first = _issue(store, debt, key="inf2l:duplicate")
    before_events, before_outbox = store.read_events(), store.list_outbox()

    duplicate = _issue(store, debt, key="inf2l:duplicate")

    assert first.committed and duplicate.committed
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert store.read_events() == before_events and store.list_outbox() == before_outbox


def test_simple_debt_formal_spine_rejects_changed_idempotency_without_append() -> None:
    store, debt = _service()
    assert _issue(store, debt, key="inf2l:changed").committed
    before_events, before_outbox = store.read_events(), store.list_outbox()

    with pytest.raises(DebtRuntimeError, match="idempotency_key_reused"):
        debt.issue_simple_debt(
            command_id="inf2l:issue",
            contract_id="contract:inf2l",
            debt_id="debt:inf2l",
            creditor_ref="actor:creditor",
            debtor_ref="actor:debtor",
            creditor_account_id="account:creditor",
            debtor_account_id="account:debtor",
            currency_ref="currency:local",
            principal_amount=9,
            due_tick=3,
            idempotency_key="inf2l:changed",
            causation_id="cause:inf2l:issue",
            correlation_id="corr:inf2l:issue",
        )

    assert store.read_events() == before_events and store.list_outbox() == before_outbox


def test_simple_debt_plan_rejects_stale_revision_without_append() -> None:
    store, debt = _service()
    stale_revisions = {
        "gameplay:economy": 2,
        "gameplay:contracts": 0,
        "gameplay:debt": 0,
        "gameplay:commerce": 0,
    }
    assert _issue(store, debt).committed
    before_events = store.read_events()
    command = GameplayCommandEnvelope(
        command_id="inf2l:stale",
        command_type="gameplay.debt.simple_settlement",
        command_version=1,
        principal_ref="actor_gameplay.debt_domain",
        transaction_id="transaction:inf2l:stale",
        idempotency_key="inf2l:stale",
        expected_revisions=stale_revisions,
        read_set_revisions=stale_revisions,
        causation_id="cause:inf2l:stale",
        correlation_id="corr:inf2l:stale",
        source_ref="debt-simple-settlement",
        submitted_at="test",
        pinned_revisions={f"debt_settlement:{stream}": revision for stream, revision in stale_revisions.items()},
        payload={"settlement_kind": "simple_debt"},
    )
    plan = DebtSettlementPlan(
        command=command,
        expected_revisions=stale_revisions,
        idempotency_digest="digest:stale",
        event_specs=(
            DebtSettlementEventSpec(
                event_type="gameplay.debt.claim_overdue",
                stream_id="gameplay:debt",
                payload={"debt_id": "debt:inf2l", "due_tick": 3, "overdue_tick": 4},
                causation_id="cause:inf2l:stale",
                correlation_id="corr:inf2l:stale",
            ),
        ),
    )

    result = store.append_batch(plan.to_atomic_event_batch())

    assert not result.committed and result.failure and result.failure.error_code == "revision_conflict"
    assert store.read_events() == before_events


def test_simple_debt_plan_rejects_unregistered_event_before_append() -> None:
    store, _ = _service()
    before_events, before_outbox = store.read_events(), store.list_outbox()
    revisions = {
        "gameplay:economy": 2,
        "gameplay:contracts": 0,
        "gameplay:debt": 0,
        "gameplay:commerce": 0,
    }
    command = GameplayCommandEnvelope(
        command_id="inf2l:unregistered",
        command_type="gameplay.debt.simple_settlement",
        command_version=1,
        principal_ref="actor_gameplay.debt_domain",
        transaction_id="transaction:inf2l:unregistered",
        idempotency_key="inf2l:unregistered",
        expected_revisions=revisions,
        read_set_revisions=revisions,
        causation_id="cause:inf2l:unregistered",
        correlation_id="corr:inf2l:unregistered",
        source_ref="debt-simple-settlement",
        submitted_at="test",
        pinned_revisions={f"debt_settlement:{stream}": revision for stream, revision in revisions.items()},
        payload={"settlement_kind": "simple_debt"},
    )
    plan = DebtSettlementPlan(
        command=command,
        expected_revisions=revisions,
        idempotency_digest="digest:unregistered",
        event_specs=(
            DebtSettlementEventSpec(
                event_type="gameplay.economy.account_opened",
                stream_id="gameplay:economy",
                payload={},
                causation_id="cause:inf2l:unregistered",
                correlation_id="corr:inf2l:unregistered",
            ),
        ),
    )

    with pytest.raises(DebtRuntimeError, match="debt_settlement_event_invalid"):
        plan.to_atomic_event_batch()

    assert store.read_events() == before_events and store.list_outbox() == before_outbox
    assert store.get_stream_head("gameplay:debt") == 0


def test_simple_debt_plan_rejects_registered_event_on_wrong_stream_before_append() -> None:
    store, _ = _service()
    before_events, before_outbox = store.read_events(), store.list_outbox()
    revisions = {
        "gameplay:economy": 2,
        "gameplay:contracts": 0,
        "gameplay:debt": 0,
        "gameplay:commerce": 0,
    }
    command = GameplayCommandEnvelope(
        command_id="inf2l:wrong-stream",
        command_type="gameplay.debt.simple_settlement",
        command_version=1,
        principal_ref="actor_gameplay.debt_domain",
        transaction_id="transaction:inf2l:wrong-stream",
        idempotency_key="inf2l:wrong-stream",
        expected_revisions=revisions,
        read_set_revisions=revisions,
        causation_id="cause:inf2l:wrong-stream",
        correlation_id="corr:inf2l:wrong-stream",
        source_ref="debt-simple-settlement",
        submitted_at="test",
        pinned_revisions={f"debt_settlement:{stream}": revision for stream, revision in revisions.items()},
        payload={"settlement_kind": "simple_debt"},
    )
    plan = DebtSettlementPlan(
        command=command,
        expected_revisions=revisions,
        idempotency_digest="digest:wrong-stream",
        event_specs=(
            DebtSettlementEventSpec(
                event_type="gameplay.debt.claim_issued",
                stream_id="gameplay:economy",
                payload={"debt_id": "debt:inf2l"},
                causation_id="cause:inf2l:wrong-stream",
                correlation_id="corr:inf2l:wrong-stream",
            ),
        ),
    )

    with pytest.raises(DebtRuntimeError, match="debt_settlement_stream_invalid"):
        plan.to_atomic_event_batch()

    assert store.read_events() == before_events and store.list_outbox() == before_outbox
    assert store.get_stream_head("gameplay:economy") == 2


def test_simple_debt_formal_spine_replays_full_and_checkpoint_tail() -> None:
    store, debt = _service()
    checkpoint_events = store.read_events()
    assert _issue(store, debt).committed
    replay = GameplayProjectionReplay(projector_id="inf2l-debt", projector_version="1")

    full = replay.full_replay(store.read_events())
    checkpoint = replay.create_checkpoint(checkpoint_events)
    tail = replay.checkpoint_plus_tail_replay(checkpoint, store.read_events()[len(checkpoint_events):])

    assert full.succeeded and tail.succeeded
    assert full.projection_hash == tail.projection_hash


def test_debt_authority_replay_projection_matches_full_and_checkpoint_tail() -> None:
    store, debt = _service()
    checkpoint_events = store.read_events()
    assert _issue(store, debt).committed

    full = debt.replay_projection()
    checkpoint = debt.replay_projection(checkpoint_at=len(checkpoint_events))

    assert full.succeeded and checkpoint.succeeded
    assert full.projection_hash == checkpoint.projection_hash


def test_debt_authority_replay_projection_matches_full_and_checkpoint_tail() -> None:
    store, debt = _service()
    assert _issue(store, debt).committed
    checkpoint_at = len(store.read_events())
    assert _pay(debt).committed

    full = debt.replay_projection()
    tail = debt.replay_projection(checkpoint_at=checkpoint_at)

    assert full.succeeded and tail.succeeded
    assert full.projection_hash == tail.projection_hash
