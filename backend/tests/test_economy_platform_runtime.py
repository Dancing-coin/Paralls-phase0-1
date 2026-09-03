import pytest

from app.gameplay.economy_platform_runtime import EconomyPlatformAuthority, EconomyPlatformProjector, EconomyPlatformRuntimeError
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.event_schema_registry import EventSchemaRegistry, register_general_economy_platform_event_schemas


def test_currency_issuance_uses_owner_fragment_and_append_receipt():
    store = GameplayEventStore()
    authority = EconomyPlatformAuthority(store=store)
    result = authority.record_currency_issuance(
        command_id="cmd:issue",
        idempotency_key="idem:issue",
        currency_ref="currency:local",
        amount_minor=100,
        issuer_ref="government:district",
        policy_revision="policy:money:local@1",
        expected_revision=0,
        causation_id="cause:issue",
        correlation_id="corr:issue",
    )
    assert result.committed
    assert result.committed_event_ids
    assert store.read_events()[0].event_type == "gameplay.economy.currency_issuance_recorded@1"
    projection = EconomyPlatformProjector().rebuild(store.read_events())
    assert projection.currency_issuance_minor == {"currency:local": 100}


def test_population_signal_rejects_invalid_side_before_write():
    store = GameplayEventStore()
    authority = EconomyPlatformAuthority(store=store)
    with pytest.raises(EconomyPlatformRuntimeError, match="economy_population_signal_invalid"):
        authority.record_population_market_signal(
            command_id="cmd:signal",
            idempotency_key="idem:signal",
            signal_ref="signal:one",
            region_ref="region:district",
            period_ref="period:1",
            item_ref="item:bread",
            side="payment",
            quantity=1,
            source_revision="population:district@1",
            expected_revision=0,
            causation_id="cause:signal",
            correlation_id="corr:signal",
        )
    assert store.read_events() == []


def test_core_ledger_hold_and_obligation_records_replay_from_checkpoint_tail():
    store = GameplayEventStore()
    authority = EconomyPlatformAuthority(store=store)
    authority.record_ledger_posting(command_id="cmd:p", idempotency_key="idem:p", posting_ref="posting:1", account_ref="account:a", direction="credit", amount_minor=7, transaction_ref="tx:1", expected_revision=0, causation_id="cause", correlation_id="corr")
    authority.record_hold(command_id="cmd:h", idempotency_key="idem:h", hold_ref="hold:1", account_ref="account:a", amount_minor=2, purpose_ref="purpose:order", expires_at_tick=10, expected_revision=1, causation_id="cause", correlation_id="corr")
    authority.record_obligation(command_id="cmd:o", idempotency_key="idem:o", obligation_ref="obligation:1", debtor_ref="actor:a", creditor_ref="actor:b", amount_minor=5, due_tick=12, policy_revision="policy:pay@1", expected_revision=0, causation_id="cause", correlation_id="corr")
    projector = EconomyPlatformProjector()
    full = projector.rebuild(store.read_events())
    checkpoint = projector.rebuild(store.read_events()[:1])
    tail = projector.rebuild(store.read_events()[1:], checkpoint=checkpoint)
    assert full == tail
    assert set(full.ledger_postings) == {"posting:1"}
    assert set(full.holds) == {"hold:1"}
    assert set(full.obligations) == {"obligation:1"}


def test_fx_fixing_replays_from_checkpoint_tail():
    store = GameplayEventStore()
    authority = EconomyPlatformAuthority(store=store)
    authority.record_fx_fixing(command_id="cmd:fx", idempotency_key="idem:fx", fixing_ref="fixing:local-usd", base_currency_ref="currency:local", quote_currency_ref="currency:usd", numerator=3, denominator=2, policy_revision="policy:fx@1", expected_revision=0, causation_id="cause", correlation_id="corr")
    projector = EconomyPlatformProjector()
    full = projector.rebuild(store.read_events())
    tail = projector.rebuild(store.read_events(), checkpoint=projector.rebuild(()))
    assert full == tail
    assert full.fx_fixings["fixing:local-usd"]["numerator"] == 3


def test_currency_issuance_is_admitted_by_registry_backed_store():
    registry = EventSchemaRegistry()
    register_general_economy_platform_event_schemas(registry)
    store = GameplayEventStore(event_schema_registry=registry)
    result = EconomyPlatformAuthority(store=store).record_currency_issuance(command_id="cmd:issue", idempotency_key="idem:issue", currency_ref="currency:local", amount_minor=1, issuer_ref="government:district", policy_revision="policy:money@1", expected_revision=0, causation_id="cause", correlation_id="corr")
    assert result.committed
