from types import SimpleNamespace

from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.economy_temporal_consumer import EconomyTemporalConsumer
from app.gameplay.event_store import GameplayEventStore


def _driver(tick: int):
    return SimpleNamespace(
        current_tick=tick,
        catch_up_limit=2,
        world_runtime=SimpleNamespace(is_paused=lambda: False),
    )


def _accounts():
    store = GameplayEventStore()
    service = EconomyAuthorityService(store=store)
    assert service.open_account(
        command_id="temporal:account:alice",
        account_id="account:alice",
        owner_ref="actor:alice",
        currency_ref="currency:coin",
        initial_balance=10,
        idempotency_key="temporal:account:alice",
        causation_id="cause:temporal:account:alice",
        correlation_id="corr:temporal:account:alice",
        expected_revision=0,
    ).committed
    assert service.open_account(
        command_id="temporal:account:bob",
        account_id="account:bob",
        owner_ref="actor:bob",
        currency_ref="currency:coin",
        initial_balance=0,
        idempotency_key="temporal:account:bob",
        causation_id="cause:temporal:account:bob",
        correlation_id="corr:temporal:account:bob",
        expected_revision=1,
    ).committed
    return store, service


def test_economy_temporal_consumer_settles_scheduled_transfer_once_at_confirmed_tick():
    store, service = _accounts()
    opened = service.open_scheduled_account_transfer_obligation(
        command_id="temporal:transfer:open",
        transfer_ref="scheduled-transfer:temporal:1",
        debit_account_id="account:alice",
        credit_account_id="account:bob",
        amount=4,
        due_tick=8,
        idempotency_key="temporal:transfer:open",
        causation_id="cause:temporal:transfer:open",
        correlation_id="corr:temporal:transfer:open",
        expected_revision=2,
    )
    assert opened.committed
    consumer = EconomyTemporalConsumer(store=store, authority=service)
    consumer.advance(_driver(7))
    assert consumer.last_results == ()
    before = len(store.read_events())
    consumer.advance(_driver(8))
    assert len(store.read_events()) == before + 3
    assert consumer.last_errors == ()
    consumer.advance(_driver(8))
    assert len(store.read_events()) == before + 3


def test_economy_temporal_consumer_tax_and_close_boundary():
    store = GameplayEventStore()
    service = EconomyAuthorityService(store=store)
    source = service.record_tax_due(
        command_id="temporal:tax:source",
        organization_ref="organization:temporal",
        period_ref="period:2026-10",
        assessed_amount_minor=27,
        policy_revision="policy:commercial@7",
        policy_digest="sha256:commercial-policy",
        due_calendar_ref="calendar:monthly",
        evidence_refs=("evidence:taxable:temporal",),
        source_digest="sha256:tax-source",
        idempotency_key="temporal:tax:source",
        causation_id="cause:temporal:tax:source",
        correlation_id="corr:temporal:tax:source",
    )
    assert source.committed
    opened = service.open_tax_obligation(
        command_id="temporal:tax:open",
        tax_due_event_id=store.read_events()[-1].event_id,
        due_tick=5,
        idempotency_key="temporal:tax:open",
        causation_id="cause:temporal:tax:open",
        correlation_id="corr:temporal:tax:open",
        expected_revision=1,
    )
    assert opened.committed
    consumer = EconomyTemporalConsumer(store=store, authority=service)
    consumer.advance(_driver(5))
    assert consumer.last_errors == ()
    assert store.read_events()[-1].event_type == "gameplay.economy.tax_obligation_settled"
    consumer.close()
    try:
        consumer.advance(_driver(6))
    except RuntimeError as exc:
        assert str(exc) == "economy_consumer_closed"
    else:
        raise AssertionError("closed Economy consumer accepted advancement")


def test_scheduled_transfer_temporal_consumer_recovers_from_new_durable_store(tmp_path):
    from app.gameplay.event_store import DurableGameplayEventStore

    path = tmp_path / "economy-consumer-recovery.db"
    store = DurableGameplayEventStore(path)
    service = EconomyAuthorityService(store=store)
    assert service.open_account(
        command_id="durable:alice", account_id="account:alice", owner_ref="actor:alice",
        currency_ref="currency:coin", initial_balance=10, idempotency_key="durable:alice",
        causation_id="cause:durable:alice", correlation_id="corr:durable:alice", expected_revision=0,
    ).committed
    assert service.open_account(
        command_id="durable:bob", account_id="account:bob", owner_ref="actor:bob",
        currency_ref="currency:coin", initial_balance=0, idempotency_key="durable:bob",
        causation_id="cause:durable:bob", correlation_id="corr:durable:bob", expected_revision=1,
    ).committed
    assert service.open_scheduled_account_transfer_obligation(
        command_id="durable:transfer:open", transfer_ref="scheduled-transfer:durable:1",
        debit_account_id="account:alice", credit_account_id="account:bob", amount=4, due_tick=8,
        idempotency_key="durable:transfer:open", causation_id="cause:durable:transfer:open",
        correlation_id="corr:durable:transfer:open", expected_revision=2,
    ).committed
    first_consumer = EconomyTemporalConsumer(store=store, authority=service)
    first_consumer.advance(_driver(8))
    assert first_consumer.last_errors == ()
    settled_event_ids = tuple(
        event.event_id for event in store.read_stream("gameplay:economy")
        if event.event_type == "gameplay.economy.scheduled_transfer_obligation_settled"
    )
    assert len(settled_event_ids) == 1
    store.close()

    reopened = DurableGameplayEventStore(path)
    try:
        restored_service = EconomyAuthorityService(store=reopened)
        restored_consumer = EconomyTemporalConsumer(store=reopened, authority=restored_service)
        restored_consumer.advance(_driver(8))
        assert restored_consumer.last_errors == ()
        assert restored_consumer.last_results == ()
        assert tuple(
            event.event_id for event in reopened.read_stream("gameplay:economy")
            if event.event_type == "gameplay.economy.scheduled_transfer_obligation_settled"
        ) == settled_event_ids
        projection = restored_service._projector.rebuild(reopened.read_events())
        assert projection.accounts["account:alice"].balance == 6
        assert projection.accounts["account:bob"].balance == 4
    finally:
        reopened.close()
