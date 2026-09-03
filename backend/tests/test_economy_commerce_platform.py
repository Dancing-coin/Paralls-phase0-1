import pytest

from app.gameplay.economy_commerce_platform import EconomyCommerceAuthority, EconomyCommerceProjector, EconomyCommerceRuntimeError
from app.gameplay.event_store import GameplayEventStore


def test_delivery_settlement_and_labor_period_are_owner_bound_and_replayable():
    store = GameplayEventStore()
    authority = EconomyCommerceAuthority(store=store)
    assert authority.record_delivery_settlement(command_id="cmd:d", idempotency_key="idem:d", settlement_ref="settlement:d", commitment_ref="commit:1", policy_revision="policy:delivery@1", expected_revision=0, causation_id="cause", correlation_id="corr").committed
    assert authority.record_labor_period(command_id="cmd:l", idempotency_key="idem:l", period_ref="period:1", organization_ref="organization:bakery", payroll_amount_minor=10, policy_revision="policy:payroll@1", expected_revision=0, causation_id="cause", correlation_id="corr").committed
    projector = EconomyCommerceProjector()
    full = projector.rebuild(store.read_events())
    checkpoint = projector.rebuild(store.read_events()[:1])
    tail = projector.rebuild(store.read_events()[1:], checkpoint=checkpoint)
    assert full == tail
    assert "settlement:d" in full.delivery_settlements
    assert "period:1" in full.labor_periods


def test_tax_regulation_rejects_negative_amount_without_write():
    store = GameplayEventStore()
    authority = EconomyCommerceAuthority(store=store)
    with pytest.raises(EconomyCommerceRuntimeError, match="economy_tax_regulation_invalid"):
        authority.record_tax_regulation(command_id="cmd:t", idempotency_key="idem:t", assessment_ref="tax:1", organization_ref="organization:bakery", amount_minor=-1, policy_revision="policy:tax@1", expected_revision=0, causation_id="cause", correlation_id="corr")
    assert store.read_events() == []
