from __future__ import annotations

import pytest

from app.gameplay.economy_runtime import EconomyAuthorityService, EconomyRuntimeError
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.government_treasury_runtime import (
    GovernmentTreasuryCollectorAuthority,
    TaxPaymentCompensationIntentV1,
    TaxPaymentIntentV1,
)


def _seed_current_tax_obligation(*, admit_collector: bool = True) -> tuple[
    GameplayEventStore,
    EconomyAuthorityService,
    object,
    object,
    object,
    object,
]:
    store = GameplayEventStore()
    service = EconomyAuthorityService(store=store)
    assert service.open_account(
        command_id="command:tax-payment:payer-account",
        account_id="account:citizen-a",
        owner_ref="organization:citizen-a",
        currency_ref="currency:local",
        initial_balance=90,
        idempotency_key="idem:tax-payment:payer-account",
        causation_id="cause:tax-payment:payer-account",
        correlation_id="corr:tax-payment:payer-account",
        expected_revision=0,
    ).committed
    payer_account_opened = store.read_events()[-1]
    assert service.open_account(
        command_id="command:tax-payment:collector-account",
        account_id="account:treasury:harbor-city",
        owner_ref="government:harbor-city",
        currency_ref="currency:local",
        initial_balance=0,
        idempotency_key="idem:tax-payment:collector-account",
        causation_id="cause:tax-payment:collector-account",
        correlation_id="corr:tax-payment:collector-account",
        expected_revision=1,
    ).committed
    assert service.record_tax_due(
        command_id="command:tax-payment:due",
        organization_ref="organization:citizen-a",
        period_ref="period:2026-q3",
        assessed_amount_minor=30,
        policy_revision="policy:government-tax@1",
        policy_digest="sha256:government-tax",
        due_calendar_ref="calendar:quarterly",
        evidence_refs=("evidence:tax-payment:assessed",),
        source_digest="sha256:tax-payment:source",
        idempotency_key="idem:tax-payment:due",
        causation_id="cause:tax-payment:due",
        correlation_id="corr:tax-payment:due",
        jurisdiction_ref="jurisdiction:harbor-city",
        currency_ref="currency:local",
    ).committed
    tax_due_event = store.read_events()[-1]
    opened = service.open_tax_obligation(
        command_id="command:tax-payment:open",
        tax_due_event_id=tax_due_event.event_id,
        due_tick=25,
        idempotency_key="idem:tax-payment:open",
        causation_id=tax_due_event.event_id,
        correlation_id="corr:tax-payment:open",
        expected_revision=3,
    )
    assert opened.committed and opened.obligation is not None
    obligation_opened = next(
        store.get_event(event_id)
        for event_id in opened.append_result.committed_event_ids
        if store.get_event(event_id).event_type == "gameplay.economy.tax_obligation_opened"
    )
    treasury = GovernmentTreasuryCollectorAuthority(store=store)
    if admit_collector:
        collector_admission = treasury.admit_collector_account(
            command_id="command:tax-payment:collector-admit",
            jurisdiction_ref="jurisdiction:harbor-city",
            currency_ref="currency:local",
            collector_account_ref="account:treasury:harbor-city",
            collector_owner_ref="government:harbor-city",
            idempotency_key="idem:tax-payment:collector-admit",
            causation_id="cause:tax-payment:collector-admit",
            correlation_id="corr:tax-payment:collector-admit",
            expected_revision=0,
        )
        assert collector_admission.committed
    return store, service, treasury, payer_account_opened, tax_due_event, obligation_opened


def test_tax_due_and_opened_obligation_should_expose_jurisdiction_currency_and_source_revision_pins() -> None:
    _store, _service, _treasury, _payer_account_opened, tax_due_event, obligation_opened = _seed_current_tax_obligation()

    assert tax_due_event.payload["jurisdiction_ref"] == "jurisdiction:harbor-city"
    assert tax_due_event.payload["currency_ref"] == "currency:local"
    assert obligation_opened.payload["source_tax_due_stream_revision"] == tax_due_event.stream_revision
    assert obligation_opened.payload["jurisdiction_ref"] == tax_due_event.payload["jurisdiction_ref"]
    assert obligation_opened.payload["currency_ref"] == tax_due_event.payload["currency_ref"]


def test_tax_obligation_open_should_expose_explicit_economy_payer_binding_pins() -> None:
    _store, _service, _treasury, payer_account_opened, _tax_due_event, obligation_opened = _seed_current_tax_obligation()

    assert obligation_opened.payload["payer_binding_event_id"]
    assert obligation_opened.payload["payer_binding_stream_revision"]
    assert obligation_opened.payload["payer_account_opened_event_id"] == payer_account_opened.event_id
    assert (
        obligation_opened.payload["payer_account_opened_stream_revision"]
        == payer_account_opened.stream_revision
    )
    assert obligation_opened.payload["payer_account_owner_ref"] == payer_account_opened.payload["owner_ref"]


def test_tax_payment_minimal_intent_and_atomic_settlement_vector() -> None:
    store, service, _treasury, _payer_account_opened, _tax_due_event, obligation_opened = _seed_current_tax_obligation()
    intent = TaxPaymentIntentV1(
        obligation_id=obligation_opened.payload["obligation_id"],
        command_id="command:tax-payment:settle",
        idempotency_key="tax-payment:obligation:economy:tax:organization:citizen-a:period:2026-q3:account:citizen-a:v1",
        causation_id="cause:tax-payment:settle",
        correlation_id="corr:tax-payment:settle",
    )

    assert set(intent.model_dump()) == {"capability_ref", "obligation_id", "command_id", "idempotency_key", "causation_id", "correlation_id"}

    payment = service.settle_tax_payment(intent)

    assert payment.committed, payment.failure
    assert [store.get_event(event_id).event_type for event_id in payment.committed_event_ids] == [
        "gameplay.economy.account_debited",
        "gameplay.economy.account_credited",
        "gameplay.economy.tax_payment_settled",
        "gameplay.economy.tax_obligation_settled",
    ]
    assert all(event.stream_id == "gameplay:economy" for event in (store.get_event(event_id) for event_id in payment.committed_event_ids))
    assert {entry.audience for entry in store.list_outbox() if entry.transaction_id == payment.transaction_id} == {"authority:economy"}


def test_tax_payment_compensation_atomically_reopens_obligation_and_replays() -> None:
    store, service, _treasury, _payer_account_opened, _tax_due_event, obligation_opened = _seed_current_tax_obligation()
    settle_intent = TaxPaymentIntentV1(
        obligation_id=obligation_opened.payload["obligation_id"],
        command_id="command:tax-payment:settle",
        idempotency_key="tax-payment:obligation:economy:tax:organization:citizen-a:period:2026-q3:account:citizen-a:v1",
        causation_id="cause:tax-payment:settle",
        correlation_id="corr:tax-payment:settle",
    )
    payment = service.settle_tax_payment(settle_intent)

    assert payment.committed, payment.failure
    settled_payment = next(
        store.get_event(event_id)
        for event_id in payment.committed_event_ids
        if store.get_event(event_id).event_type == "gameplay.economy.tax_payment_settled"
    )
    reversal = service.request_tax_payment_reversal(
        settled_payment_event_id=settled_payment.event_id,
        command_id="command:tax-payment:reverse",
        idempotency_key="tax-payment:reversal:economy:tax:organization:citizen-a:period:2026-q3:v1",
        causation_id="cause:tax-payment:reverse",
        correlation_id="corr:tax-payment:reverse",
    )
    assert reversal.committed
    compensation_intent = TaxPaymentCompensationIntentV1(
        settled_payment_event_id=settled_payment.event_id,
        reversal_source_event_id=reversal.committed_event_ids[0],
        command_id="command:tax-payment:compensate",
        idempotency_key="tax-payment:compensation:economy:tax:organization:citizen-a:period:2026-q3:v1",
        causation_id="cause:tax-payment:compensate",
        correlation_id="corr:tax-payment:compensate",
    )
    before_invalid_events, before_invalid_outbox = store.read_events(), store.list_outbox()
    invalid_source = service.compensate_tax_payment(
        compensation_intent.model_copy(update={"reversal_source_event_id": settled_payment.event_id})
    )
    assert not invalid_source.committed
    assert invalid_source.failure is not None and invalid_source.failure.error_code == "government_tax_payment_compensation_source_invalid"
    assert store.read_events() == before_invalid_events
    assert store.list_outbox() == before_invalid_outbox

    compensation = service.compensate_tax_payment(compensation_intent)
    assert compensation.committed
    assert [store.get_event(event_id).event_type for event_id in compensation.committed_event_ids] == [
        "gameplay.economy.account_debited",
        "gameplay.economy.account_credited",
        "gameplay.economy.tax_payment_compensated",
        "gameplay.economy.tax_obligation_reopened",
    ]
    reopened = store.get_event(compensation.committed_event_ids[-1])
    assert reopened.payload["prior_state"] == "settled"
    assert reopened.payload["current_state"] == "open"
    full = service.tax_payment_projection(scope="authority")
    tail = service.tax_payment_projection(
        scope="authority",
        checkpoint_at=payment.global_sequence_range[-1],
    )
    assert tail == full
    before_duplicate_events, before_duplicate_outbox = store.read_events(), store.list_outbox()
    duplicate = service.compensate_tax_payment(compensation_intent)
    changed = service.compensate_tax_payment(
        compensation_intent.model_copy(update={"command_id": "command:tax-payment:compensate-changed"})
    )
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert not changed.committed
    assert changed.failure is not None and changed.failure.error_code == "idempotency_key_reused"
    assert store.read_events() == before_duplicate_events
    assert store.list_outbox() == before_duplicate_outbox


def test_treasury_collector_identity_is_private_replayable_and_identity_only() -> None:
    store, _service, treasury, _payer_account_opened, _tax_due_event, _obligation_opened = _seed_current_tax_obligation()
    stream = "gameplay:government_treasury:jurisdiction:harbor-city"
    treasury_events = store.read_stream(stream)

    assert [event.event_type for event in treasury_events] == [
        "gameplay.government_treasury.collector_account_admitted"
    ]
    assert all(event.visibility_policy == "authority_only" for event in treasury_events)
    assert treasury.collector_identity_projection(scope="authority") == treasury.collector_identity_projection(
        scope="authority", checkpoint_at=treasury_events[0].global_sequence
    )
    with pytest.raises(ValueError, match="projection_scope_denied"):
        treasury.collector_identity_projection(scope="public")

    before_events, before_outbox = store.read_events(), store.list_outbox()
    stale = treasury.admit_collector_account(
        command_id="command:tax-payment:collector-stale",
        jurisdiction_ref="jurisdiction:harbor-city",
        currency_ref="currency:local",
        collector_account_ref="account:treasury:harbor-city",
        collector_owner_ref="government:harbor-city",
        idempotency_key="idem:tax-payment:collector-stale",
        causation_id="cause:tax-payment:collector-stale",
        correlation_id="corr:tax-payment:collector-stale",
        expected_revision=0,
    )
    assert not stale.committed
    assert stale.failure is not None and stale.failure.error_code == "revision_conflict"
    assert store.read_events() == before_events
    assert store.list_outbox() == before_outbox


def test_tax_payment_rejects_capability_or_missing_collector_without_writes() -> None:
    store, service, _treasury, _payer_account_opened, _tax_due_event, obligation_opened = _seed_current_tax_obligation()
    before_events, before_outbox = store.read_events(), store.list_outbox()
    rejected = service.settle_tax_payment(
        TaxPaymentIntentV1(
            capability_ref="capability:government-tax-payment@2",
            obligation_id=obligation_opened.payload["obligation_id"],
            command_id="command:tax-payment:wrong-capability",
            idempotency_key="tax-payment:wrong-capability",
            causation_id="cause:tax-payment:wrong-capability",
            correlation_id="corr:tax-payment:wrong-capability",
        )
    )
    assert not rejected.committed
    assert rejected.failure is not None and rejected.failure.error_code == "government_tax_payment_capability_denied"
    assert store.read_events() == before_events
    assert store.list_outbox() == before_outbox

    store, service, _treasury, _payer_account_opened, _tax_due_event, obligation_opened = _seed_current_tax_obligation(admit_collector=False)
    before_events, before_outbox = store.read_events(), store.list_outbox()
    missing_collector = service.settle_tax_payment(
        TaxPaymentIntentV1(
            obligation_id=obligation_opened.payload["obligation_id"],
            command_id="command:tax-payment:missing-collector",
            idempotency_key="tax-payment:obligation:economy:tax:organization:citizen-a:period:2026-q3:account:citizen-a:v1",
            causation_id="cause:tax-payment:missing-collector",
            correlation_id="corr:tax-payment:missing-collector",
        )
    )
    assert not missing_collector.committed
    assert missing_collector.failure is not None and missing_collector.failure.error_code == "government_tax_payment_collector_missing"
    assert store.read_events() == before_events
    assert store.list_outbox() == before_outbox


def test_tax_payment_duplicate_receipt_privacy_and_changed_duplicate_are_zero_write() -> None:
    store, service, _treasury, _payer_account_opened, _tax_due_event, obligation_opened = _seed_current_tax_obligation()
    intent = TaxPaymentIntentV1(
        obligation_id=obligation_opened.payload["obligation_id"],
        command_id="command:tax-payment:deduplicate",
        idempotency_key="tax-payment:obligation:economy:tax:organization:citizen-a:period:2026-q3:account:citizen-a:v1",
        causation_id="cause:tax-payment:deduplicate",
        correlation_id="corr:tax-payment:deduplicate",
    )
    payment = service.settle_tax_payment(intent)
    assert payment.committed
    receipt = service.tax_payment_receipt_for(result=payment, scope="authority")
    assert receipt.transaction_id == payment.transaction_id
    assert receipt.committed_event_ids == tuple(payment.committed_event_ids)
    with pytest.raises(EconomyRuntimeError, match="receipt_scope_denied"):
        service.tax_payment_receipt_for(result=payment, scope="public")

    before_events, before_outbox = store.read_events(), store.list_outbox()
    duplicate = service.settle_tax_payment(intent)
    changed = service.settle_tax_payment(
        intent.model_copy(update={"command_id": "command:tax-payment:changed"})
    )
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert not changed.committed
    assert changed.failure is not None and changed.failure.error_code == "idempotency_key_reused"
    assert store.read_events() == before_events
    assert store.list_outbox() == before_outbox


def test_tax_payment_rejects_a_stale_collector_stream_revision_without_writes() -> None:
    store, service, treasury, _payer_account_opened, _tax_due_event, obligation_opened = _seed_current_tax_obligation()
    assert service.open_account(
        command_id="command:tax-payment:reserve-collector-account",
        account_id="account:treasury:reserve",
        owner_ref="government:harbor-city",
        currency_ref="currency:reserve",
        initial_balance=0,
        idempotency_key="idem:tax-payment:reserve-collector-account",
        causation_id="cause:tax-payment:reserve-collector-account",
        correlation_id="corr:tax-payment:reserve-collector-account",
        expected_revision=store.get_stream_head("gameplay:economy"),
    ).committed
    assert treasury.admit_collector_account(
        command_id="command:tax-payment:reserve-collector-admit",
        jurisdiction_ref="jurisdiction:harbor-city",
        currency_ref="currency:reserve",
        collector_account_ref="account:treasury:reserve",
        collector_owner_ref="government:harbor-city",
        idempotency_key="idem:tax-payment:reserve-collector-admit",
        causation_id="cause:tax-payment:reserve-collector-admit",
        correlation_id="corr:tax-payment:reserve-collector-admit",
        expected_revision=1,
    ).committed
    before_events, before_outbox = store.read_events(), store.list_outbox()
    stale = service.settle_tax_payment(
        TaxPaymentIntentV1(
            obligation_id=obligation_opened.payload["obligation_id"],
            command_id="command:tax-payment:stale-collector",
            idempotency_key="tax-payment:obligation:economy:tax:organization:citizen-a:period:2026-q3:account:citizen-a:v1",
            causation_id="cause:tax-payment:stale-collector",
            correlation_id="corr:tax-payment:stale-collector",
        )
    )
    assert not stale.committed
    assert stale.failure is not None and stale.failure.error_code == "government_tax_payment_collector_missing"
    assert store.read_events() == before_events
    assert store.list_outbox() == before_outbox
