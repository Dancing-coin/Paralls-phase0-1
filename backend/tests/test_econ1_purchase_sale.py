from __future__ import annotations

import pytest

from app.gameplay.econ1_economy_runtime import EconomyAuthority, MarketQuote, PurchasePosting, SalePosting
from app.gameplay.event_store import GameplayEventStore


def test_fixed_quote_expiry_and_quantity_are_fail_closed() -> None:
    quote = MarketQuote(quote_ref="q", item_ref="flour", unit_price=2, quantity_limit=3, valid_until_tick=5, public_digest="d")
    EconomyAuthority.validate_quote(quote, tick=5, quantity=3)
    with pytest.raises(ValueError, match="quote_expired"):
        EconomyAuthority.validate_quote(quote, tick=6, quantity=1)
    with pytest.raises(ValueError, match="quote_quantity_exhausted"):
        EconomyAuthority.validate_quote(quote, tick=1, quantity=4)


def test_settle_purchase_and_sale_append_economy_events_and_fail_without_write() -> None:
    store = GameplayEventStore()
    authority = EconomyAuthority(store=store)
    quote = MarketQuote(quote_ref="q", item_ref="flour", unit_price=2, quantity_limit=3, valid_until_tick=5, public_digest="d")
    purchase = PurchasePosting(posting_ref="purchase:1", quote_ref="q", buyer_ref="character:buyer", quantity=2, total_amount=4)
    result = authority.settle_purchase(
        quote, purchase, tick=1, command_id="command:economy:purchase:1", idempotency_key="idem:economy:purchase:1",
        causation_id="cause:economy:purchase:1", correlation_id="corr:economy:1",
    )
    assert result.committed is True
    sale = SalePosting(posting_ref="sale:1", seller_ref="character:seller", item_ref="bread", quantity=1, total_amount=5, demand_digest="demand:1")
    sale_result = authority.settle_sale(
        sale, command_id="command:economy:sale:1", idempotency_key="idem:economy:sale:1",
        causation_id="cause:economy:sale:1", correlation_id="corr:economy:1",
    )
    assert sale_result.committed is True
    assert [event.event_type for event in store.read_events()] == ["gameplay.economy.purchase_posted", "gameplay.economy.sale_posted"]
    before = len(store.read_events())
    with pytest.raises(ValueError, match="quote_expired"):
        authority.settle_purchase(
            quote, purchase.model_copy(update={"posting_ref": "purchase:expired"}), tick=6,
            command_id="command:economy:purchase:2", idempotency_key="idem:economy:purchase:2",
            causation_id="cause:economy:purchase:2", correlation_id="corr:economy:1",
        )
    assert len(store.read_events()) == before
