from __future__ import annotations

import pytest


def test_fixed_market_quote_and_period_models_exclude_dynamic_market_fields() -> None:
    from app.gameplay.econ1_economy_runtime import BusinessPeriod, MarketQuote

    quote = MarketQuote(quote_ref="quote:flour:1", item_ref="flour", unit_price=2, quantity_limit=10, valid_until_tick=5, public_digest="sha256:quote")
    period = BusinessPeriod(period_ref="period:1", sequence=1, policy_revision="policy:tax:v1")
    assert quote.unit_price == 2
    assert period.sequence == 1
    with pytest.raises(ValueError, match="extra|forbid"):
        MarketQuote(quote_ref="q", item_ref="i", unit_price=1, quantity_limit=1, valid_until_tick=1, public_digest="d", order_book={})
