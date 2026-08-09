"""Fixed-offer Econ-1 economy owner; no market discovery or NPC state."""

from __future__ import annotations

from hashlib import sha256
import json

from pydantic import ConfigDict, Field

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import StrictGameplayModel
from app.gameplay.settlement_plan import build_atomic_event_batch, build_multi_stream_atomic_event_batch
from app.gameplay.economy_runtime import EconomyProjector, EconomyRuntimeError


class MarketQuote(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    quote_ref: str = Field(min_length=1)
    item_ref: str = Field(min_length=1)
    unit_price: float = Field(gt=0)
    quantity_limit: int = Field(gt=0)
    valid_until_tick: int = Field(ge=0)
    public_digest: str = Field(min_length=1)


class PurchasePosting(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    posting_ref: str = Field(min_length=1)
    quote_ref: str = Field(min_length=1)
    buyer_ref: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    total_amount: float = Field(gt=0)
    tax_ref: str | None = None


class SalePosting(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    posting_ref: str = Field(min_length=1)
    seller_ref: str = Field(min_length=1)
    item_ref: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    total_amount: float = Field(gt=0)
    demand_digest: str = Field(min_length=1)


class EconomicObligation(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    obligation_ref: str = Field(min_length=1)
    owner_ref: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    amount: float = Field(ge=0)
    due_tick: int = Field(ge=0)
    status: str = "due"


class OperatingWindow(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    window_ref: str = Field(min_length=1)
    organization_ref: str = Field(min_length=1)
    opens_at_tick: int = Field(ge=0)
    closes_at_tick: int = Field(ge=0)
    policy_revision: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    status: str = "planned"


class WageAccrual(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    accrual_ref: str = Field(min_length=1)
    organization_ref: str = Field(min_length=1)
    payee_actor_ref: str = Field(pattern=r"^character:")
    work_evidence_refs: tuple[str, ...] = Field(min_length=1)
    wage_policy_revision: str = Field(min_length=1)
    amount: float = Field(gt=0)
    status: str = "accrued"


class BusinessPeriod(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    period_ref: str = Field(min_length=1)
    sequence: int = Field(ge=1)
    policy_revision: str = Field(min_length=1)
    revenue: float = 0
    cost: float = 0
    tax: float = 0
    obligations: tuple[EconomicObligation, ...] = ()
    closed: bool = False

    @property
    def result_digest(self) -> str:
        payload = self.model_dump(mode="json")
        return "sha256:" + sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class EconomyAuthority:
    _PRINCIPAL = "actor_gameplay.econ1_economy_domain"

    def __init__(self, *, store: GameplayEventStore) -> None:
        self._store = store

    @staticmethod
    def validate_quote(quote: MarketQuote, *, tick: int, quantity: int) -> None:
        if tick > quote.valid_until_tick:
            raise ValueError("quote_expired")
        if quantity > quote.quantity_limit:
            raise ValueError("quote_quantity_exhausted")

    def open_window(self, window: OperatingWindow, *, command_id: str, idempotency_key: str, causation_id: str, correlation_id: str):
        current_status = self._window_status(window.window_ref)
        if current_status is not None:
            raise ValueError("operating_window_already_opened")
        if window.status not in {"planned", "open"}:
            raise ValueError("operating_window_invalid")
        opened = window.model_copy(update={"status": "open"})
        return self._settle(stream_id=f"gameplay:organization:window:{window.window_ref}", command_id=command_id, idempotency_key=idempotency_key, causation_id=causation_id, correlation_id=correlation_id, event_type="gameplay.organization.operating_window_opened", payload=opened.model_dump(mode="json"), pinned_revisions={"window": 0})

    def close_window(self, window: OperatingWindow, *, command_id: str, idempotency_key: str, causation_id: str, correlation_id: str):
        if self._window_status(window.window_ref) != "open":
            raise ValueError("operating_window_closed")
        closed = window.model_copy(update={"status": "closed"})
        return self._settle(stream_id=f"gameplay:organization:window:{window.window_ref}", command_id=command_id, idempotency_key=idempotency_key, causation_id=causation_id, correlation_id=correlation_id, event_type="gameplay.organization.operating_window_closed", payload=closed.model_dump(mode="json"), pinned_revisions={"window": 0})

    def evaluate_due(self, window: OperatingWindow, *, command_id: str, idempotency_key: str, causation_id: str, correlation_id: str):
        if self._window_status(window.window_ref) != "closed":
            raise ValueError("operating_window_open")
        return self._settle(stream_id=f"gameplay:organization:window:{window.window_ref}", command_id=command_id, idempotency_key=idempotency_key, causation_id=causation_id, correlation_id=correlation_id, event_type="gameplay.organization.due_evaluation_recorded", payload={"window_ref": window.window_ref}, pinned_revisions={"window": 0})

    def accrue_wage(self, accrual: WageAccrual, *, completed_evidence_refs: set[str], command_id: str, idempotency_key: str, causation_id: str, correlation_id: str):
        if not set(accrual.work_evidence_refs).issubset(completed_evidence_refs):
            raise ValueError("work_evidence_invalid")
        return self._settle(stream_id=f"gameplay:economy:wage:{accrual.payee_actor_ref}", command_id=command_id, idempotency_key=idempotency_key, causation_id=causation_id, correlation_id=correlation_id, event_type="gameplay.economy.wage_accrued", payload=accrual.model_dump(mode="json"), pinned_revisions={"wage": 1})

    def mark_overdue(self, accrual: WageAccrual, *, command_id: str, idempotency_key: str, causation_id: str, correlation_id: str):
        overdue = accrual.model_copy(update={"status": "overdue"})
        return self._settle(stream_id=f"gameplay:economy:wage:{accrual.payee_actor_ref}", command_id=command_id, idempotency_key=idempotency_key, causation_id=causation_id, correlation_id=correlation_id, event_type="gameplay.economy.wage_overdue", payload=overdue.model_dump(mode="json"), pinned_revisions={"wage": 1})

    def pay_wage(
        self,
        accrual: WageAccrual,
        *,
        payer_account_id: str,
        payee_account_id: str,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ):
        """Commit wage payment and account transfer as one multi-stream batch."""
        if accrual.status not in {"accrued", "due"}:
            raise ValueError("wage_payment_invalid_status")
        amount = int(accrual.amount)
        if amount != accrual.amount or amount <= 0:
            raise ValueError("wage_amount_not_integral")
        projection = EconomyProjector().rebuild(self._store.read_events())
        payer = projection.accounts.get(payer_account_id)
        payee = projection.accounts.get(payee_account_id)
        if payer is None or payee is None or payer.currency_ref != payee.currency_ref:
            raise EconomyRuntimeError("economy_account_invalid")
        if payer.balance < amount:
            raise EconomyRuntimeError("economy_insufficient_funds")
        wage_stream = f"gameplay:economy:wage:{accrual.payee_actor_ref}"
        account_stream = "gameplay:economy"
        batch = build_multi_stream_atomic_event_batch(
            command_id=command_id,
            principal_ref=self._PRINCIPAL,
            expected_revisions={
                wage_stream: self._store.get_stream_head(wage_stream),
                account_stream: projection.source_revision_vector.get(account_stream, 0),
            },
            event_specs={
                account_stream: [
                    ("gameplay.economy.account_debited", {"account_id": payer_account_id, "amount": amount}),
                    ("gameplay.economy.account_credited", {"account_id": payee_account_id, "amount": amount}),
                ],
                wage_stream: [("gameplay.economy.wage_paid", {
                    **accrual.model_dump(mode="json"),
                    "status": "paid",
                    "payer_account_id": payer_account_id,
                    "payee_account_id": payee_account_id,
                })],
            },
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            pinned_revisions={"wage": 1, "economy": projection.source_revision_vector.get(account_stream, 0)},
        )
        return self._store.append_batch(batch)

    def _window_status(self, window_ref: str) -> str | None:
        stream_id = f"gameplay:organization:window:{window_ref}"
        status: str | None = None
        for event in self._store.read_stream(stream_id):
            if event.event_type.endswith("operating_window_opened"):
                status = "open"
            elif event.event_type.endswith("operating_window_closed"):
                status = "closed"
        return status

    @staticmethod
    def close_period(period: BusinessPeriod) -> BusinessPeriod:
        if period.closed:
            raise ValueError("period_already_closed")
        if any(obligation.status == "overdue" for obligation in period.obligations):
            raise ValueError("overdue_obligation")
        return period.model_copy(update={"closed": True}, deep=True)

    def settle_purchase(
        self,
        quote: MarketQuote,
        posting: PurchasePosting,
        *,
        tick: int,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ):
        self.validate_quote(quote, tick=tick, quantity=posting.quantity)
        if posting.quote_ref != quote.quote_ref or posting.total_amount != quote.unit_price * posting.quantity:
            raise ValueError("purchase_posting_invalid")
        return self._settle(
            stream_id=f"gameplay:economy:{posting.buyer_ref}",
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            event_type="gameplay.economy.purchase_posted",
            payload={**posting.model_dump(mode="json"), "item_ref": quote.item_ref, "tick": tick},
            pinned_revisions={"quote": quote.valid_until_tick},
        )

    def settle_sale(
        self,
        posting: SalePosting,
        *,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ):
        return self._settle(
            stream_id=f"gameplay:economy:{posting.seller_ref}",
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            event_type="gameplay.economy.sale_posted",
            payload=posting.model_dump(mode="json"),
            pinned_revisions={},
        )

    def settle_period_close(
        self,
        period: BusinessPeriod,
        *,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ):
        closed = self.close_period(period)
        return self._settle(
            stream_id=f"gameplay:economy:period:{period.period_ref}",
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            event_type="gameplay.economy.business_period_closed",
            payload=closed.model_dump(mode="json"),
            pinned_revisions={"period": period.sequence},
        )

    def _settle(
        self,
        *,
        stream_id: str,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        event_type: str,
        payload: dict[str, object],
        pinned_revisions: dict[str, int],
    ):
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None:
            return existing
        batch = build_atomic_event_batch(
            command_id=command_id,
            principal_ref=self._PRINCIPAL,
            stream_id=stream_id,
            expected_revision=self._store.get_stream_head(stream_id),
            event_specs=[(event_type, payload)],
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            pinned_revisions=pinned_revisions,
        )
        return self._store.append_batch(batch)

    @staticmethod
    def post_purchase(
        *,
        store: GameplayEventStore,
        buyer_ref: str,
        seller_ref: str,
        item_ref: str,
        quantity: int,
        total_amount: float,
        quote_ref: str,
        tick: int,
    ):
        if quantity <= 0 or total_amount <= 0:
            raise ValueError("purchase_invalid")
        command_id = f"purchase:{buyer_ref}:{quote_ref}:{tick}"
        authority = EconomyAuthority(store=store)
        quote = MarketQuote(
            quote_ref=quote_ref,
            item_ref=item_ref,
            unit_price=total_amount / quantity,
            quantity_limit=quantity,
            valid_until_tick=tick,
            public_digest=f"legacy:{quote_ref}",
        )
        posting = PurchasePosting(
            posting_ref=command_id,
            quote_ref=quote_ref,
            buyer_ref=buyer_ref,
            quantity=quantity,
            total_amount=total_amount,
        )
        return authority.settle_purchase(
            quote,
            posting,
            tick=tick,
            command_id=command_id,
            idempotency_key=command_id,
            causation_id=f"causation:{command_id}",
            correlation_id=f"correlation:{buyer_ref}:{tick}",
        )

    @staticmethod
    def post_sale(
        *,
        store: GameplayEventStore,
        seller_ref: str,
        buyer_ref: str,
        item_ref: str,
        quantity: int,
        total_amount: float,
        tick: int,
    ):
        if quantity <= 0 or total_amount <= 0:
            raise ValueError("sale_invalid")
        command_id = f"sale:{seller_ref}:{item_ref}:{tick}"
        posting = SalePosting(
            posting_ref=command_id,
            seller_ref=seller_ref,
            item_ref=item_ref,
            quantity=quantity,
            total_amount=total_amount,
            demand_digest=f"legacy:{buyer_ref}",
        )
        return EconomyAuthority(store=store).settle_sale(
            posting,
            command_id=command_id,
            idempotency_key=command_id,
            causation_id=f"causation:{command_id}",
            correlation_id=f"correlation:{seller_ref}:{tick}",
        )

    @staticmethod
    def close_period_and_settle(*, store: GameplayEventStore, period: BusinessPeriod, organization_ref: str):
        command_id = f"period-close:{period.period_ref}"
        return EconomyAuthority(store=store).settle_period_close(
            period,
            command_id=command_id,
            idempotency_key=command_id,
            causation_id=f"causation:{command_id}",
            correlation_id=f"correlation:{organization_ref}:{period.sequence}",
        )
        return store.append_batch(batch)


__all__ = ["BusinessPeriod", "EconomicObligation", "EconomyAuthority", "MarketQuote", "OperatingWindow", "PurchasePosting", "SalePosting", "WageAccrual"]
