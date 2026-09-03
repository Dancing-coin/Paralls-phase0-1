import pytest

from app.gameplay.economy_platform_content import (
    CurrencyDefinition,
    FxPolicy,
    PopulationMarketSignal,
    Quote,
)


def test_currency_content_is_strict_and_typed():
    value = CurrencyDefinition(
        currency_ref="currency:local",
        precision=2,
        issuer_ref="government:district",
        region_ref="region:district",
        monetary_policy_ref="policy:money:local@1",
    )
    assert value.precision == 2
    with pytest.raises(ValueError):
        CurrencyDefinition.model_validate({**value.model_dump(), "owner": "caller"})


def test_fx_policy_rejects_same_currency_and_invalid_window():
    with pytest.raises(ValueError, match="economy_fx_currency_pair_invalid"):
        FxPolicy(
            policy_ref="policy:fx:local@1",
            base_currency_ref="currency:local",
            quote_currency_ref="currency:local",
            numerator=1,
            denominator=1,
            valid_from_tick=0,
        )


def test_quote_rejects_reversed_validity_window():
    with pytest.raises(ValueError, match="economy_quote_window_invalid"):
        Quote(
            quote_ref="quote:bread@1",
            issuer_ref="organization:bakery",
            item_ref="item:bread",
            side="sell",
            unit_price_minor=10,
            currency_ref="currency:local",
            quantity_limit=1,
            valid_from_tick=10,
            valid_until_tick=1,
            policy_revision="policy:quote@1",
        )


def test_population_signal_requires_public_digest():
    signal = PopulationMarketSignal(
        signal_ref="signal:district:bread@1",
        region_ref="region:district",
        period_ref="period:1",
        item_ref="item:bread",
        side="demand",
        quantity=5,
        source_revision="population:district@1",
        public_digest="sha256:" + "a" * 64,
    )
    assert signal.side == "demand"
