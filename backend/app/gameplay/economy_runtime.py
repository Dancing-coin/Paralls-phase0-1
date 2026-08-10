"""Minimal event-sourced account ledger; balances are projections, never inputs."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Mapping, Sequence

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayEvent, OwnerAuthorizedFragment


class EconomyRuntimeError(ValueError): pass

@dataclass(frozen=True)
class Account:
    account_id: str; owner_ref: str; currency_ref: str; balance: int; source_event_id: str

@dataclass(frozen=True)
class TaxDue:
    organization_ref: str
    period_ref: str
    assessed_amount_minor: int
    policy_revision: str
    policy_digest: str
    due_calendar_ref: str
    evidence_refs: tuple[str, ...]
    source_digest: str
    source_event_id: str


@dataclass(frozen=True)
class BudgetReservation:
    reservation_ref: str
    account_id: str
    amount_minor: int
    source_event_id: str

@dataclass(frozen=True)
class EconomyProjection:
    accounts: Mapping[str, Account]
    balances: Mapping[str, int]
    source_revision_vector: Mapping[str, int]
    tax_due: Mapping[str, TaxDue] = MappingProxyType({})
    budget_reservations: Mapping[str, BudgetReservation] = MappingProxyType({})
    dynamic_quotes: Mapping[str, Mapping[str, object]] = MappingProxyType({})
    dynamic_orders: Mapping[str, Mapping[str, object]] = MappingProxyType({})

class EconomyProjector:
    def rebuild(self, events: Sequence[GameplayEvent]) -> EconomyProjection:
        accounts: dict[str, Account] = {}
        tax_due: dict[str, TaxDue] = {}
        budget_reservations: dict[str, BudgetReservation] = {}
        dynamic_quotes: dict[str, Mapping[str, object]] = {}
        dynamic_orders: dict[str, Mapping[str, object]] = {}
        revisions: dict[str, int] = {}
        for event in sorted(events, key=lambda item: (item.global_sequence, item.event_id)):
            if event.stream_id == "gameplay:economy":
                revisions[event.stream_id] = max(revisions.get(event.stream_id,0), event.stream_revision)
            if event.event_type == "gameplay.economy.tax_due_recorded":
                p = event.payload
                organization_ref = _text(p, "organization_ref")
                period_ref = _text(p, "period_ref")
                key = f"{organization_ref}:{period_ref}"
                if key in tax_due:
                    raise EconomyRuntimeError("economy_tax_due_duplicate")
                tax_due[key] = TaxDue(
                    organization_ref=organization_ref,
                    period_ref=period_ref,
                    assessed_amount_minor=_nonnegative(p, "assessed_amount_minor"),
                    policy_revision=_text(p, "policy_revision"),
                    policy_digest=_text(p, "policy_digest"),
                    due_calendar_ref=_text(p, "due_calendar_ref"),
                    evidence_refs=_text_tuple(p, "evidence_refs"),
                    source_digest=_text(p, "source_digest"),
                    source_event_id=event.event_id,
                )
                continue
            if event.event_type == "gameplay.economy.budget_reserved":
                p = event.payload
                reservation_ref = _text(p, "reservation_ref")
                if reservation_ref in budget_reservations:
                    raise EconomyRuntimeError("economy_budget_reservation_duplicate")
                budget_reservations[reservation_ref] = BudgetReservation(
                    reservation_ref,
                    _text(p, "account_id"),
                    _positive(p, "amount_minor"),
                    event.event_id,
                )
                continue
            if event.event_type == "gameplay.economy.dynamic_quote_published":
                quote = _mapping(p=event.payload, key="quote")
                quote_ref = _text(quote, "quote_ref")
                version = _positive(quote, "version")
                previous = dynamic_quotes.get(quote_ref)
                if previous is not None and version <= _positive(previous, "version"):
                    raise EconomyRuntimeError("economy_dynamic_quote_version_invalid")
                dynamic_quotes[quote_ref] = MappingProxyType(dict(quote))
                continue
            if event.event_type == "gameplay.economy.dynamic_order_submitted":
                order = _mapping(p=event.payload, key="order")
                order_ref = _text(order, "order_ref")
                if order_ref in dynamic_orders:
                    raise EconomyRuntimeError("economy_dynamic_order_duplicate")
                dynamic_orders[order_ref] = MappingProxyType(dict(order))
                continue
            if event.event_type not in {"gameplay.economy.account_opened", "gameplay.economy.account_debited", "gameplay.economy.account_credited"}: continue
            p = event.payload; account_id = _text(p, "account_id")
            if event.event_type == "gameplay.economy.account_opened":
                if account_id in accounts: raise EconomyRuntimeError("economy_account_duplicate")
                accounts[account_id] = Account(account_id, _text(p,"owner_ref"), _text(p,"currency_ref"), _nonnegative(p,"initial_balance"), event.event_id)
            else:
                prior = accounts.get(account_id)
                if prior is None: raise EconomyRuntimeError("economy_account_missing")
                amount = _positive(p,"amount")
                value = prior.balance - amount if event.event_type.endswith("debited") else prior.balance + amount
                if value < 0: raise EconomyRuntimeError("economy_insufficient_funds")
                accounts[account_id] = Account(prior.account_id, prior.owner_ref, prior.currency_ref, value, event.event_id)
            revisions[event.stream_id] = max(revisions.get(event.stream_id,0), event.stream_revision)
        frozen = MappingProxyType(dict(sorted(accounts.items())))
        return EconomyProjection(
            frozen,
            MappingProxyType({key: account.balance for key, account in frozen.items()}),
            MappingProxyType(dict(sorted(revisions.items()))),
            MappingProxyType(dict(sorted(tax_due.items()))),
            MappingProxyType(dict(sorted(budget_reservations.items()))),
            MappingProxyType(dict(sorted(dynamic_quotes.items()))),
            MappingProxyType(dict(sorted(dynamic_orders.items()))),
        )

class EconomyAuthorityService:
    _PRINCIPAL="actor_gameplay.economy_domain"
    def __init__(self, *, store: GameplayEventStore): self._store=store; self._projector=EconomyProjector()
    @staticmethod
    def assess_tax_due(*, taxable_amount_minor:int, tax_rate_basis_points:int, evidence_refs:tuple[str,...])->int:
        if taxable_amount_minor < 0 or tax_rate_basis_points < 0 or not evidence_refs or any(not ref for ref in evidence_refs): raise EconomyRuntimeError("economy_tax_assessment_invalid")
        return (taxable_amount_minor * tax_rate_basis_points) // 10_000
    def build_commerce_obligation_fragment(self, *, commitment_ref:str, buyer_organization_ref:str, account_obligation_refs:tuple[str,...], budget_reservation_refs:tuple[str,...], policy_revision:str, expected_revision:int)->OwnerAuthorizedFragment:
        """Validate Economy-owned consideration pins before contributing its fragment.

        Organization authorizes a purchase budget, but only Economy may attest
        that the referenced reservation is present on a buyer-owned account and
        remains covered by that account's current balance.  The commitment
        keeps only stable references; it does not copy account balances or a
        ledger into Commerce.
        """
        if (
            not commitment_ref
            or not buyer_organization_ref
            or not account_obligation_refs
            or not budget_reservation_refs
            or any(not ref.startswith("obligation:") for ref in account_obligation_refs)
            or any(not ref.startswith("reservation:") for ref in budget_reservation_refs)
        ):
            raise EconomyRuntimeError("commerce_obligation_invalid")
        stream="gameplay:economy"
        projection = self._projector.rebuild(self._store.read_events())
        if projection.source_revision_vector.get(stream, 0) != expected_revision:
            raise EconomyRuntimeError("revision_conflict")
        reservations: list[BudgetReservation] = []
        for reservation_ref in budget_reservation_refs:
            reservation = projection.budget_reservations.get(reservation_ref)
            if reservation is None:
                raise EconomyRuntimeError("commerce_budget_reservation_missing")
            account = projection.accounts.get(reservation.account_id)
            if account is None or account.owner_ref != buyer_organization_ref:
                raise EconomyRuntimeError("commerce_budget_reservation_owner_mismatch")
            reservations.append(reservation)
        reserved_by_account = {
            account_id: sum(item.amount_minor for item in projection.budget_reservations.values() if item.account_id == account_id)
            for account_id in {item.account_id for item in reservations}
        }
        if any(
            projection.accounts[account_id].balance < reserved_amount
            for account_id, reserved_amount in reserved_by_account.items()
        ):
            raise EconomyRuntimeError("commerce_budget_reservation_unavailable")
        return OwnerAuthorizedFragment(fragment_id=f"fragment:economy:commerce:{commitment_ref}",owner_principal_ref=self._PRINCIPAL,source_rule_ref="economy:commerce-obligation",expected_revisions={stream:expected_revision},pinned_revisions={"economy":expected_revision},event_specs={stream:(("gameplay.economy.commerce_obligation_recorded",{"commitment_ref":commitment_ref,"buyer_organization_ref":buyer_organization_ref,"account_obligation_refs":account_obligation_refs,"budget_reservation_refs":budget_reservation_refs,"policy_revision":policy_revision}),)})
    @classmethod
    def build_delivery_obligation_fragment(cls, *, delivery_ref:str, commitment_ref:str, status:str, reason:str|None, recovery_obligation_ref:str|None, policy_revision:str, expected_revision:int)->OwnerAuthorizedFragment:
        if status not in {"delivered","rejected","cancelled"}: raise EconomyRuntimeError("commerce_delivery_invalid")
        if status != "delivered" and not recovery_obligation_ref: raise EconomyRuntimeError("commerce_recovery_obligation_required")
        stream="gameplay:economy"
        payload={"delivery_ref":delivery_ref,"commitment_ref":commitment_ref,"status":status,"reason":reason,"recovery_obligation_ref":recovery_obligation_ref,"policy_revision":policy_revision}
        return OwnerAuthorizedFragment(fragment_id=f"fragment:economy:delivery:{delivery_ref}",owner_principal_ref=cls._PRINCIPAL,source_rule_ref="economy:commerce-delivery-obligation",expected_revisions={stream:expected_revision},pinned_revisions={"economy":expected_revision},event_specs={stream:(("gameplay.economy.delivery_obligation_updated",payload),)})
    def open_account(self, *, command_id:str, account_id:str, owner_ref:str, currency_ref:str, initial_balance:int, idempotency_key:str, causation_id:str, correlation_id:str)->AppendBatchResult:
        p=self._projector.rebuild(self._store.read_events())
        if account_id in p.accounts or not account_id or not owner_ref or not currency_ref or initial_balance<0: raise EconomyRuntimeError("economy_account_invalid")
        return self._append(command_id,idempotency_key,[self._event(command_id,"gameplay.economy.account_opened",1,{"account_id":account_id,"owner_ref":owner_ref,"currency_ref":currency_ref,"initial_balance":initial_balance},causation_id,correlation_id)],p)
    def transfer(self, *, command_id:str, debit_account_id:str, credit_account_id:str, amount:int, idempotency_key:str, causation_id:str, correlation_id:str)->AppendBatchResult:
        p=self._projector.rebuild(self._store.read_events()); debit=p.accounts.get(debit_account_id); credit=p.accounts.get(credit_account_id)
        if debit is None or credit is None or debit.currency_ref != credit.currency_ref or debit_account_id==credit_account_id or amount<=0: raise EconomyRuntimeError("economy_transfer_invalid")
        if debit.balance<amount: raise EconomyRuntimeError("economy_insufficient_funds")
        return self._append(command_id,idempotency_key,[self._event(command_id,"gameplay.economy.account_debited",1,{"account_id":debit_account_id,"amount":amount},causation_id,correlation_id),self._event(command_id,"gameplay.economy.account_credited",2,{"account_id":credit_account_id,"amount":amount},causation_id,correlation_id)],p)
    def reserve_budget(self, *, command_id:str, reservation_ref:str, account_id:str, amount_minor:int, idempotency_key:str, causation_id:str, correlation_id:str)->AppendBatchResult:
        p = self._projector.rebuild(self._store.read_events())
        account = p.accounts.get(account_id)
        already_reserved = sum(
            reservation.amount_minor
            for reservation in p.budget_reservations.values()
            if reservation.account_id == account_id
        )
        if (
            not reservation_ref.startswith("reservation:")
            or reservation_ref in p.budget_reservations
            or account is None
            or amount_minor <= 0
            or account.balance - already_reserved < amount_minor
        ):
            raise EconomyRuntimeError("economy_budget_reservation_invalid")
        return self._append(command_id,idempotency_key,[self._event(command_id,"gameplay.economy.budget_reserved",1,{"reservation_ref":reservation_ref,"account_id":account_id,"amount_minor":amount_minor},causation_id,correlation_id)],p)
    def publish_dynamic_quote(self, *, command_id:str, quote_payload:Mapping[str,object], idempotency_key:str, causation_id:str, correlation_id:str)->AppendBatchResult:
        p = self._projector.rebuild(self._store.read_events())
        quote_ref = _text(quote_payload, "quote_ref")
        version = _positive(quote_payload, "version")
        previous = p.dynamic_quotes.get(quote_ref)
        if previous is not None and version <= _positive(previous, "version"):
            raise EconomyRuntimeError("economy_dynamic_quote_version_invalid")
        if quote_payload.get("status") not in {"active", "cancelled"}:
            raise EconomyRuntimeError("economy_dynamic_quote_invalid")
        return self._append(command_id,idempotency_key,[self._event(command_id,"gameplay.economy.dynamic_quote_published",1,{"quote":dict(quote_payload)},causation_id,correlation_id)],p)
    def submit_dynamic_order(self, *, command_id:str, order_payload:Mapping[str,object], idempotency_key:str, causation_id:str, correlation_id:str)->AppendBatchResult:
        p = self._projector.rebuild(self._store.read_events())
        order_ref = _text(order_payload, "order_ref")
        if order_ref in p.dynamic_orders or order_payload.get("status") not in {"active", "cancelled"}:
            raise EconomyRuntimeError("economy_dynamic_order_invalid")
        return self._append(command_id,idempotency_key,[self._event(command_id,"gameplay.economy.dynamic_order_submitted",1,{"order":dict(order_payload)},causation_id,correlation_id)],p)
    def record_tax_due(self, *, command_id:str, organization_ref:str, period_ref:str, assessed_amount_minor:int, policy_revision:str, policy_digest:str, due_calendar_ref:str, evidence_refs:tuple[str,...], source_digest:str, idempotency_key:str, causation_id:str, correlation_id:str)->AppendBatchResult:
        p=self._projector.rebuild(self._store.read_events())
        if not all((organization_ref, period_ref, policy_revision, policy_digest, due_calendar_ref, source_digest, evidence_refs)) or assessed_amount_minor < 0: raise EconomyRuntimeError("economy_tax_assessment_invalid")
        payload={"organization_ref":organization_ref,"period_ref":period_ref,"assessed_amount_minor":assessed_amount_minor,"policy_revision":policy_revision,"policy_digest":policy_digest,"due_calendar_ref":due_calendar_ref,"evidence_refs":evidence_refs,"source_digest":source_digest}
        return self._append(command_id,idempotency_key,[self._event(command_id,"gameplay.economy.tax_due_recorded",1,payload,causation_id,correlation_id)],p)
    def _event(self,command_id:str,event_type:str,index:int,payload:dict[str,object],causation_id:str,correlation_id:str)->dict[str,object]:
        return {"event_id":f"evt:{command_id}:economy:{index}","event_type":event_type,"schema_version":1,"stream_id":"gameplay:economy","stream_revision":0,"global_sequence":0,"transaction_id":f"tx:{command_id}","command_id":command_id,"causation_id":causation_id,"correlation_id":correlation_id,"visibility_policy":"authority_only","payload":payload}
    def _append(self,command_id:str,idempotency_key:str,events:list[dict[str,object]],projection:EconomyProjection)->AppendBatchResult:
        digest=_digest(events); stream="gameplay:economy"
        return self._store.append_batch({"transaction_id":f"tx:{command_id}","command_id":command_id,"expected_stream_revisions":{stream:projection.source_revision_vector.get(stream,0)},"pinned_revisions":{"economy":projection.source_revision_vector.get(stream,0)},"events":events,"idempotency_record":{"principal_ref":self._PRINCIPAL,"idempotency_key":idempotency_key,"payload_digest":digest},"outbox_entries":[],"result_digest":digest,"projection_refresh_hints":[]})

def _text(p:Mapping[str,object],k:str)->str:
    v=p.get(k)
    if not isinstance(v,str) or not v: raise EconomyRuntimeError("economy_event_payload_invalid")
    return v
def _nonnegative(p:Mapping[str,object],k:str)->int:
    v=p.get(k)
    if isinstance(v,bool) or not isinstance(v,int) or v<0: raise EconomyRuntimeError("economy_event_payload_invalid")
    return v
def _positive(p:Mapping[str,object],k:str)->int:
    v=_nonnegative(p,k)
    if not v: raise EconomyRuntimeError("economy_event_payload_invalid")
    return v
def _text_tuple(p:Mapping[str,object],k:str)->tuple[str,...]:
    values=p.get(k)
    if not isinstance(values,(tuple,list)) or not values or any(not isinstance(value,str) or not value for value in values): raise EconomyRuntimeError("economy_event_payload_invalid")
    return tuple(values)
def _mapping(*, p:Mapping[str,object], key:str)->Mapping[str,object]:
    value=p.get(key)
    if not isinstance(value, Mapping): raise EconomyRuntimeError("economy_event_payload_invalid")
    return value
def _digest(v:object)->str: return sha256(json.dumps(v,sort_keys=True,separators=(",",":"),default=lambda x:dict(x) if isinstance(x,Mapping) else x.__dict__).encode()).hexdigest()

__all__=["Account","BudgetReservation","EconomyAuthorityService","EconomyProjection","EconomyProjector","EconomyRuntimeError","TaxDue"]
