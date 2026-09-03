"""Strict, owner-neutral Economy v3/platform 2.0 content contracts.

These models describe immutable package content only. They do not write facts;
runtime settlement remains owned by the existing domain authorities.
"""
from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from app.gameplay.models import StrictGameplayModel


class EconomyContentModel(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CurrencyDefinition(EconomyContentModel):
    currency_ref: str = Field(pattern=r"^currency:")
    precision: int = Field(ge=0, le=9)
    issuer_ref: str = Field(min_length=1)
    region_ref: str = Field(min_length=1)
    monetary_policy_ref: str = Field(pattern=r"^policy:")


class MonetaryPolicy(EconomyContentModel):
    policy_ref: str = Field(pattern=r"^policy:")
    issuance_mode: Literal["fixed_window", "authority_quota"]
    max_supply_minor: int = Field(ge=0)
    effective_from_tick: int = Field(ge=0)
    effective_until_tick: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_window(self) -> "MonetaryPolicy":
        if self.effective_until_tick is not None and self.effective_until_tick < self.effective_from_tick:
            raise ValueError("economy_policy_window_invalid")
        return self


class FxPolicy(EconomyContentModel):
    policy_ref: str = Field(pattern=r"^policy:")
    base_currency_ref: str = Field(pattern=r"^currency:")
    quote_currency_ref: str = Field(pattern=r"^currency:")
    numerator: int = Field(gt=0)
    denominator: int = Field(gt=0)
    valid_from_tick: int = Field(ge=0)
    valid_until_tick: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_pair(self) -> "FxPolicy":
        if self.base_currency_ref == self.quote_currency_ref:
            raise ValueError("economy_fx_currency_pair_invalid")
        if self.valid_until_tick is not None and self.valid_until_tick < self.valid_from_tick:
            raise ValueError("economy_fx_window_invalid")
        return self


class AccountPolicy(EconomyContentModel):
    policy_ref: str = Field(pattern=r"^policy:")
    currency_ref: str = Field(pattern=r"^currency:")
    credit_limit_minor: int = Field(ge=0)
    overdraft_allowed: bool = False


class LedgerPosting(EconomyContentModel):
    posting_ref: str = Field(min_length=1)
    account_ref: str = Field(pattern=r"^account:")
    direction: Literal["debit", "credit"]
    amount_minor: int = Field(gt=0)
    transaction_ref: str = Field(min_length=1)


class Hold(EconomyContentModel):
    hold_ref: str = Field(min_length=1)
    account_ref: str = Field(pattern=r"^account:")
    amount_minor: int = Field(gt=0)
    purpose_ref: str = Field(min_length=1)
    expires_at_tick: int = Field(ge=0)


class Obligation(EconomyContentModel):
    obligation_ref: str = Field(min_length=1)
    debtor_ref: str = Field(min_length=1)
    creditor_ref: str = Field(min_length=1)
    amount_minor: int = Field(gt=0)
    due_tick: int = Field(ge=0)
    policy_revision: str = Field(min_length=1)


class MarketRegion(EconomyContentModel):
    region_ref: str = Field(min_length=1)
    jurisdiction_ref: str = Field(min_length=1)
    currency_refs: tuple[str, ...] = Field(min_length=1)
    clearing_period_ref: str = Field(min_length=1)


class Quote(EconomyContentModel):
    quote_ref: str = Field(min_length=1)
    issuer_ref: str = Field(min_length=1)
    item_ref: str = Field(min_length=1)
    side: Literal["buy", "sell"]
    unit_price_minor: int = Field(gt=0)
    currency_ref: str = Field(pattern=r"^currency:")
    quantity_limit: int = Field(gt=0)
    valid_from_tick: int = Field(ge=0)
    valid_until_tick: int = Field(ge=0)
    policy_revision: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_window(self) -> "Quote":
        if self.valid_until_tick < self.valid_from_tick:
            raise ValueError("economy_quote_window_invalid")
        return self


class Order(EconomyContentModel):
    order_ref: str = Field(min_length=1)
    principal_ref: str = Field(min_length=1)
    quote_ref: str = Field(min_length=1)
    side: Literal["buy", "sell"]
    quantity: int = Field(gt=0)
    limit_price_minor: int = Field(gt=0)
    currency_ref: str = Field(pattern=r"^currency:")
    region_ref: str = Field(min_length=1)


class ClearingPolicy(EconomyContentModel):
    policy_ref: str = Field(pattern=r"^policy:")
    ordering_key: Literal["created_tick_order_ref"]
    partial_fill: bool
    max_matches: int = Field(gt=0)


class DeliveryTerms(EconomyContentModel):
    delivery_policy_ref: str = Field(pattern=r"^policy:")
    source_custody_ref: str = Field(min_length=1)
    destination_custody_ref: str = Field(min_length=1)
    acceptance_policy_ref: str = Field(pattern=r"^policy:")


class LaborPolicy(EconomyContentModel):
    policy_ref: str = Field(pattern=r"^policy:")
    pay_period_ref: str = Field(min_length=1)
    wage_currency_ref: str = Field(pattern=r"^currency:")
    evidence_kind: str = Field(min_length=1)


class TaxPolicy(EconomyContentModel):
    policy_ref: str = Field(pattern=r"^policy:")
    jurisdiction_ref: str = Field(min_length=1)
    tax_kind: str = Field(min_length=1)
    rate_basis_points: int = Field(ge=0, le=10000)
    due_calendar_ref: str = Field(min_length=1)


class CreditFacility(EconomyContentModel):
    facility_ref: str = Field(min_length=1)
    lender_ref: str = Field(min_length=1)
    borrower_ref: str = Field(min_length=1)
    currency_ref: str = Field(pattern=r"^currency:")
    principal_limit_minor: int = Field(gt=0)
    interest_policy_ref: str = Field(pattern=r"^policy:")
    default_policy_ref: str = Field(pattern=r"^policy:")


class Collateral(EconomyContentModel):
    collateral_ref: str = Field(min_length=1)
    ownership_right_ref: str = Field(min_length=1)
    valuation_policy_ref: str = Field(pattern=r"^policy:")
    liquidation_policy_ref: str = Field(pattern=r"^policy:")


class InsurancePolicy(EconomyContentModel):
    policy_ref: str = Field(pattern=r"^policy:")
    insurer_ref: str = Field(min_length=1)
    covered_risk_ref: str = Field(min_length=1)
    premium_currency_ref: str = Field(pattern=r"^currency:")
    claim_policy_ref: str = Field(pattern=r"^policy:")


class SecurityDefinition(EconomyContentModel):
    security_ref: str = Field(min_length=1)
    issuer_ref: str = Field(min_length=1)
    denomination_currency_ref: str = Field(pattern=r"^currency:")
    rights_ref: str = Field(min_length=1)
    transfer_policy_ref: str = Field(pattern=r"^policy:")


class InsolvencyPolicy(EconomyContentModel):
    policy_ref: str = Field(pattern=r"^policy:")
    jurisdiction_ref: str = Field(min_length=1)
    trigger_ref: str = Field(min_length=1)
    waterfall_ref: str = Field(min_length=1)
    discharge_policy_ref: str = Field(pattern=r"^policy:")


class RegionalMacroPolicy(EconomyContentModel):
    policy_ref: str = Field(pattern=r"^policy:")
    region_ref: str = Field(min_length=1)
    period_ref: str = Field(min_length=1)
    price_index_basket_refs: tuple[str, ...] = Field(min_length=1)
    interest_rule_ref: str = Field(pattern=r"^policy:")
    fx_rule_ref: str = Field(pattern=r"^policy:")
    signal_source_refs: tuple[str, ...] = Field(min_length=1)


class PopulationMarketSignal(EconomyContentModel):
    signal_ref: str = Field(min_length=1)
    region_ref: str = Field(min_length=1)
    period_ref: str = Field(min_length=1)
    item_ref: str = Field(min_length=1)
    side: Literal["demand", "supply"]
    quantity: int = Field(ge=0)
    source_revision: str = Field(min_length=1)
    public_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


__all__ = [name for name, value in globals().items() if isinstance(value, type) and issubclass(value, EconomyContentModel)]
