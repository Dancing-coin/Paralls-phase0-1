"""Minimal event-sourced account ledger; balances are projections, never inputs."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Mapping, Sequence

from pydantic import ConfigDict, Field

from app.gameplay.ecology_consumer_admission import EcologyConsumerAdmissionCheck
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog, GovernedAuthorityContractError
from app.gameplay.models import AtomicEventBatch, AppendBatchResult, GameplayEvent, GameplayFailure, GameplayOutboxEntry, OwnerAuthorizedFragment, StrictGameplayModel
from app.gameplay.settlement_plan import SettlementPlan
from app.gameplay.shared_contracts import GameplayCommandEnvelope, ScheduledObligation, SettlementReceipt
from app.world_runtime.obligations import ObligationLifecycleRegistration


class EconomyRuntimeError(ValueError): pass

def _weather_quote_admission_channel():
    @dataclass(frozen=True)
    class _Admission:
        weather_event_id: str
        ecology_stream_id: str
        ecology_revision: int
        region_ref: str
        quote_ref: str
    def issue(
        *,
        weather_event_id: str,
        ecology_stream_id: str,
        ecology_revision: int,
        region_ref: str,
        quote_ref: str,
    ) -> object:
        return _Admission(
            weather_event_id,
            ecology_stream_id,
            ecology_revision,
            region_ref,
            quote_ref,
        )
    def contains(value: object) -> bool: return isinstance(value, _Admission)
    def matches(value: object, **source: object) -> bool:
        return isinstance(value, _Admission) and all(
            getattr(value, field) == source[field]
            for field in (
                "weather_event_id",
                "ecology_stream_id",
                "ecology_revision",
                "region_ref",
                "quote_ref",
            )
        )
    return issue, contains, matches


def _weather_quote_fanout_admission_channel():
    @dataclass(frozen=True)
    class _Admission:
        weather_event_id: str
        ecology_stream_id: str
        ecology_revision: int
        region_ref: str
        quote_refs: tuple[str, str]
    def issue(
        *, weather_event_id: str, ecology_stream_id: str, ecology_revision: int,
        region_ref: str, quote_refs: tuple[str, str],
    ) -> object:
        return _Admission(weather_event_id, ecology_stream_id, ecology_revision, region_ref, quote_refs)
    def contains(value: object) -> bool: return isinstance(value, _Admission)
    def matches(value: object, **source: object) -> bool:
        return isinstance(value, _Admission) and all(
            getattr(value, field) == source[field]
            for field in ("weather_event_id", "ecology_stream_id", "ecology_revision", "region_ref", "quote_refs")
        )
    return issue, contains, matches

_WEATHER_QUOTE_ISSUER, _CONTAINS_WEATHER_QUOTE_ADMISSION, _MATCHES_WEATHER_QUOTE_ADMISSION = _weather_quote_admission_channel()
_WEATHER_QUOTE_FANOUT_ISSUER, _CONTAINS_WEATHER_QUOTE_FANOUT_ADMISSION, _MATCHES_WEATHER_QUOTE_FANOUT_ADMISSION = _weather_quote_fanout_admission_channel()

def _take_weather_quote_admission_issuer() -> object:
    issuer = _WEATHER_QUOTE_ISSUER
    del globals()["_WEATHER_QUOTE_ISSUER"]
    del globals()["_take_weather_quote_admission_issuer"]
    return issuer


def _take_weather_quote_fanout_admission_issuer() -> object:
    issuer = _WEATHER_QUOTE_FANOUT_ISSUER
    del globals()["_WEATHER_QUOTE_FANOUT_ISSUER"]
    del globals()["_take_weather_quote_fanout_admission_issuer"]
    return issuer

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
class ScheduledTransferObligationResult:
    committed: bool
    obligation: ScheduledObligation | None
    append_result: AppendBatchResult


@dataclass(frozen=True)
class TaxObligationResult:
    committed: bool
    obligation: ScheduledObligation | None
    append_result: AppendBatchResult


class ScheduledAccountTransferPolicyInstance(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_ref: str = "policy:economy_scheduled_account_transfer@1"
    policy_instance_ref: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    debit_account_id: str = Field(min_length=1)
    credit_account_id: str = Field(min_length=1)
    amount_cap: int = Field(gt=0)
    active_from_tick: int = Field(ge=0)
    active_until_tick: int = Field(ge=0)

@dataclass(frozen=True)
class EconomyProjection:
    accounts: Mapping[str, Account]
    balances: Mapping[str, int]
    source_revision_vector: Mapping[str, int]
    tax_due: Mapping[str, TaxDue] = MappingProxyType({})
    budget_reservations: Mapping[str, BudgetReservation] = MappingProxyType({})
    dynamic_quotes: Mapping[str, Mapping[str, object]] = MappingProxyType({})
    dynamic_orders: Mapping[str, Mapping[str, object]] = MappingProxyType({})
    scheduled_transfer_policies: Mapping[str, ScheduledAccountTransferPolicyInstance] = MappingProxyType({})

class EconomyProjector:
    def rebuild(self, events: Sequence[GameplayEvent]) -> EconomyProjection:
        accounts: dict[str, Account] = {}
        tax_due: dict[str, TaxDue] = {}
        budget_reservations: dict[str, BudgetReservation] = {}
        dynamic_quotes: dict[str, Mapping[str, object]] = {}
        dynamic_orders: dict[str, Mapping[str, object]] = {}
        scheduled_transfer_policies: dict[str, ScheduledAccountTransferPolicyInstance] = {}
        revisions: dict[str, int] = {}
        for event in sorted(events, key=lambda item: (item.global_sequence, item.event_id)):
            if event.stream_id == "gameplay:economy":
                revisions[event.stream_id] = max(revisions.get(event.stream_id,0), event.stream_revision)
            if event.event_type == "gameplay.economy.scheduled_transfer_policy_registered":
                policy = ScheduledAccountTransferPolicyInstance.model_validate(event.payload)
                if policy.policy_instance_ref in scheduled_transfer_policies:
                    raise EconomyRuntimeError("economy_policy_duplicate")
                scheduled_transfer_policies[policy.policy_instance_ref] = policy
                continue
            if event.event_type == "gameplay.economy.scheduled_transfer_policy_revoked":
                policy_instance_ref = _text(event.payload, "policy_instance_ref")
                if policy_instance_ref not in scheduled_transfer_policies:
                    raise EconomyRuntimeError("economy_policy_missing")
                del scheduled_transfer_policies[policy_instance_ref]
                continue
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
            MappingProxyType(dict(sorted(scheduled_transfer_policies.items()))),
        )

class EconomyAuthorityService:
    _PRINCIPAL="actor_gameplay.economy_domain"
    def __init__(self, *, store: GameplayEventStore): self._store=store; self._projector=EconomyProjector()
    def commit_obligation_batch(self, batch: AtomicEventBatch) -> AppendBatchResult:
        """Commit only an Economy-ledger scheduled-transfer plan."""
        if not batch.owner_fragments or any(
            fragment.owner_principal_ref != self._PRINCIPAL
            or any(event.stream_id != "gameplay:economy" for event in batch.events)
            for fragment in batch.owner_fragments
        ):
            return self._rejected_append(batch.command_id, "economy_owner_commit_scope_denied")
        return self._store.append_batch(batch)

    @staticmethod
    def _rejected_append(command_id: str, error_code: str) -> AppendBatchResult:
        return AppendBatchResult(
            committed=False,
            transaction_id=f"transaction:{command_id}",
            command_id=command_id,
            idempotency_status="rejected",
            failure=GameplayFailure(error_code=error_code, message=error_code, failed_stage="economy_obligation_commit"),
        )
    @staticmethod
    def assess_tax_due(*, taxable_amount_minor:int, tax_rate_basis_points:int, evidence_refs:tuple[str,...])->int:
        if taxable_amount_minor < 0 or tax_rate_basis_points < 0 or not evidence_refs or any(not ref for ref in evidence_refs): raise EconomyRuntimeError("economy_tax_assessment_invalid")
        return (taxable_amount_minor * tax_rate_basis_points) // 10_000

    @classmethod
    def tax_obligation_registration(cls) -> ObligationLifecycleRegistration:
        return ObligationLifecycleRegistration(
            policy_ref="policy:economy_tax_due@1",
            policy_revision="1",
            owner_ref=cls._PRINCIPAL,
            stream_pattern="gameplay:economy",
            opened_event_type="gameplay.economy.tax_obligation_opened",
            settled_event_type="gameplay.economy.tax_obligation_settled",
            cancelled_event_type="gameplay.economy.tax_obligation_cancelled",
            expired_event_type="gameplay.economy.tax_obligation_expired",
            allowed_event_types=(
                "gameplay.economy.tax_due_recorded",
                "gameplay.economy.tax_obligation_opened",
                "gameplay.economy.tax_obligation_settled",
                "gameplay.economy.tax_obligation_cancelled",
                "gameplay.economy.tax_obligation_expired",
            ),
            visibility_scope="authority_only",
            requires_committed_open=True,
        )

    @staticmethod
    def tax_obligation_id_for(*, organization_ref: str, period_ref: str) -> str:
        return f"obligation:economy:tax:{organization_ref}:{period_ref}"

    def open_tax_obligation(
        self,
        *,
        command_id: str,
        tax_due_event_id: str,
        due_tick: int,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        expected_revision: int,
    ) -> TaxObligationResult:
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None and existing.committed:
            if len(existing.committed_event_ids) == 1:
                prior = self._store.get_event(existing.committed_event_ids[0])
                if (
                    prior.event_type == "gameplay.economy.tax_obligation_opened"
                    and prior.payload.get("source_tax_due_event_id") == tax_due_event_id
                    and prior.payload.get("due_tick") == due_tick
                ):
                    return TaxObligationResult(
                        True,
                        self.tax_obligation_for(obligation_id=_text(prior.payload, "obligation_id")),
                        existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True),
                    )
            return TaxObligationResult(False, None, self._rejected_append(command_id, "idempotency_key_reused"))
        if isinstance(due_tick, bool) or not isinstance(due_tick, int) or due_tick < 0:
            return TaxObligationResult(False, None, self._rejected_append(command_id, "economy_tax_due_tick_invalid"))
        try:
            source = self._store.get_event(tax_due_event_id)
        except KeyError:
            return TaxObligationResult(False, None, self._rejected_append(command_id, "economy_tax_source_missing"))
        if source.stream_id != "gameplay:economy" or source.event_type != "gameplay.economy.tax_due_recorded" or source.visibility_policy != "authority_only":
            return TaxObligationResult(False, None, self._rejected_append(command_id, "economy_tax_source_invalid"))
        projection = self._projector.rebuild(self._store.read_events())
        current_revision = projection.source_revision_vector.get("gameplay:economy", 0)
        if current_revision != expected_revision:
            return TaxObligationResult(False, None, self._rejected_append(command_id, "revision_conflict"))
        organization_ref = _text(source.payload, "organization_ref")
        period_ref = _text(source.payload, "period_ref")
        obligation_id = self.tax_obligation_id_for(organization_ref=organization_ref, period_ref=period_ref)
        if any(
            event.event_type == "gameplay.economy.tax_obligation_opened"
            and event.payload.get("obligation_id") == obligation_id
            for event in self._store.read_stream("gameplay:economy")
        ):
            return TaxObligationResult(False, None, self._rejected_append(command_id, "economy_tax_obligation_duplicate"))
        payload = {
            "obligation_id": obligation_id,
            "source_tax_due_event_id": source.event_id,
            "organization_ref": organization_ref,
            "period_ref": period_ref,
            "assessed_amount_minor": _nonnegative(source.payload, "assessed_amount_minor"),
            "policy_ref": "policy:economy_tax_due@1",
            "policy_revision": "1",
            "due_tick": due_tick,
            "open_idempotency_key": idempotency_key,
            "source_digest": _text(source.payload, "source_digest"),
            "evidence_refs": _text_tuple(source.payload, "evidence_refs"),
        }
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:economy-tax-obligation@1",
                contract_kind="lifecycle",
                owner_ref=self._PRINCIPAL,
                stream_ids=("gameplay:economy",),
                event_types=("gameplay.economy.tax_obligation_opened",),
                projection_scope="authority_only",
            )
        except GovernedAuthorityContractError as error:
            return TaxObligationResult(False, None, self._rejected_append(command_id, str(error)))
        fragment = OwnerAuthorizedFragment(
            fragment_id=f"fragment:economy:tax-obligation:open:{obligation_id}",
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref="economy:tax-obligation:open",
            expected_revisions={"gameplay:economy": expected_revision},
            pinned_revisions={"economy": expected_revision},
            event_specs={"gameplay:economy": (("gameplay.economy.tax_obligation_opened", payload),)},
            event_visibility_policies={"gameplay:economy": ("authority_only",)},
        )
        batch = self._tax_fragment_batch(
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            fragment=fragment,
        )
        append = self._store.append_batch(batch)
        obligation = self.tax_obligation_for(obligation_id=obligation_id) if append.committed else None
        return TaxObligationResult(append.committed, obligation, append)

    def tax_obligation_for(self, *, obligation_id: str) -> ScheduledObligation:
        opening = self._tax_opening(obligation_id=obligation_id)
        stream = "gameplay:economy"
        return ScheduledObligation(
            obligation_id=obligation_id,
            owner_ref=self._PRINCIPAL,
            due_tick=_nonnegative(opening.payload, "due_tick"),
            policy_revision=_text(opening.payload, "policy_revision"),
            status="open",
            idempotency_key=f"{_text(opening.payload, 'open_idempotency_key')}:settle",
            expected_revisions={stream: self._store.get_stream_head(stream)},
            visibility_scope="authority_only",
            source_refs=(
                "policy:economy_tax_due@1",
                f"opening_event:{opening.event_id}",
                f"source_tax_due_event:{_text(opening.payload, 'source_tax_due_event_id')}",
            ),
        )

    def build_tax_obligation_settlement_fragment(self, *, obligation: ScheduledObligation) -> OwnerAuthorizedFragment:
        return self._tax_terminal_fragment(obligation=obligation, event_type="gameplay.economy.tax_obligation_settled", current_state="settled", reason_ref=None)

    def build_tax_obligation_cancellation_fragment(self, *, obligation: ScheduledObligation, reason_ref: str) -> OwnerAuthorizedFragment:
        return self._tax_terminal_fragment(obligation=obligation, event_type="gameplay.economy.tax_obligation_cancelled", current_state="cancelled", reason_ref=reason_ref)

    def build_tax_obligation_expiry_fragment(self, *, obligation: ScheduledObligation, reason_ref: str) -> OwnerAuthorizedFragment:
        return self._tax_terminal_fragment(obligation=obligation, event_type="gameplay.economy.tax_obligation_expired", current_state="expired", reason_ref=reason_ref)

    def _tax_terminal_fragment(self, *, obligation: ScheduledObligation, event_type: str, current_state: str, reason_ref: str | None) -> OwnerAuthorizedFragment:
        opening = self._tax_opening(obligation_id=obligation.obligation_id)
        stream = "gameplay:economy"
        if (
            obligation.owner_ref != self._PRINCIPAL
            or obligation.visibility_scope != "authority_only"
            or set(obligation.expected_revisions) != {stream}
            or "policy:economy_tax_due@1" not in obligation.source_refs
            or f"opening_event:{opening.event_id}" not in obligation.source_refs
            or obligation.status not in {"open", "due"}
            or obligation.due_tick != _nonnegative(opening.payload, "due_tick")
        ):
            raise EconomyRuntimeError("economy_tax_obligation_invalid")
        GovernedAuthorityContractCatalog.require_operation(
            contract_ref="inf:economy-tax-obligation@1",
            contract_kind="lifecycle",
            owner_ref=self._PRINCIPAL,
            stream_ids=(stream,),
            event_types=(event_type,),
            projection_scope="authority_only",
        )
        payload = {
            "obligation_id": obligation.obligation_id,
            "prior_state": obligation.status,
            "current_state": current_state,
            "policy_ref": "policy:economy_tax_due@1",
            "policy_revision": obligation.policy_revision,
            "due_tick": obligation.due_tick,
            "source_tax_due_event_id": _text(opening.payload, "source_tax_due_event_id"),
        }
        if reason_ref is not None:
            payload["reason_ref"] = reason_ref
        return OwnerAuthorizedFragment(
            fragment_id=f"fragment:economy:tax-obligation:{current_state}:{obligation.obligation_id}",
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref=f"economy:tax-obligation:{current_state}",
            expected_revisions=dict(obligation.expected_revisions),
            pinned_revisions={"economy": obligation.expected_revisions[stream]},
            event_specs={stream: ((event_type, payload),)},
            event_visibility_policies={stream: ("authority_only",)},
        )

    def _tax_opening(self, *, obligation_id: str) -> GameplayEvent:
        for event in reversed(self._store.read_stream("gameplay:economy")):
            if event.event_type == "gameplay.economy.tax_obligation_opened" and event.payload.get("obligation_id") == obligation_id:
                return event
        raise EconomyRuntimeError("economy_tax_obligation_opening_missing")

    @staticmethod
    def _tax_fragment_batch(*, command_id: str, idempotency_key: str, causation_id: str, correlation_id: str, fragment: OwnerAuthorizedFragment) -> AtomicEventBatch:
        command = GameplayCommandEnvelope(
            command_id=command_id,
            command_type="gameplay.economy.tax_obligation",
            command_version=1,
            principal_ref=EconomyAuthorityService._PRINCIPAL,
            actor_ref=None,
            project_ref=None,
            transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key,
            expected_revisions=dict(fragment.expected_revisions),
            read_set_revisions=dict(fragment.expected_revisions),
            causation_id=causation_id,
            correlation_id=correlation_id,
            source_ref=fragment.fragment_id,
            submitted_at="economy-tax-obligation",
            pinned_revisions=dict(fragment.pinned_revisions),
            payload={
                "stream_ref": "gameplay:economy",
                "event_specs": [
                    {"event_type": event_type, "payload": {**payload, "visibility_policy": "authority_only"}}
                    for event_type, payload in fragment.event_specs["gameplay:economy"]
                ],
            },
        )
        batch = SettlementPlan.from_command_envelope(command).to_atomic_event_batch()
        return batch.model_copy(
            update={
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}",
                        transaction_id=batch.transaction_id,
                        event_id=event.event_id,
                        global_sequence=0,
                        topic="economy.tax_obligation.scoped_projection",
                        audience="authority:economy",
                        payload_projection={
                            "obligation_id": str(event.payload.get("obligation_id", "")),
                            "event_type": event.event_type,
                            "current_state": str(event.payload.get("current_state", "open")),
                        },
                    )
                    for event in batch.events
                ]
            },
            deep=True,
        )
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

    def settle_commerce_delivery_payment(
        self,
        *,
        command_id: str,
        delivery_event_id: str,
        delivery_stream_id: str,
        delivery_revision: int,
        commitment_ref: str,
        budget_reservation_ref: str,
        seller_account_id: str,
        expected_economy_revision: int,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        privacy_scope: str = "authority",
    ) -> AppendBatchResult:
        """Settle one delivered commerce payment from committed owner evidence."""
        request = {
            "operation": "commerce_delivery_payment",
            "command_id": command_id,
            "delivery_event_id": delivery_event_id,
            "delivery_stream_id": delivery_stream_id,
            "delivery_revision": delivery_revision,
            "commitment_ref": commitment_ref,
            "budget_reservation_ref": budget_reservation_ref,
            "seller_account_id": seller_account_id,
            "expected_economy_revision": expected_economy_revision,
            "causation_id": causation_id,
            "correlation_id": correlation_id,
            "privacy_scope": privacy_scope,
        }
        request_digest = _digest(request)
        duplicate = self._commerce_payment_duplicate_result(
            command_id=command_id,
            idempotency_key=idempotency_key,
            request_digest=request_digest,
        )
        if duplicate is not None:
            return duplicate
        if privacy_scope != "authority":
            return self._rejected_append(command_id, "commerce_payment_privacy_denied")
        if (
            not all(isinstance(value, str) and value for value in (
                command_id, delivery_event_id, delivery_stream_id, commitment_ref,
                budget_reservation_ref, seller_account_id, idempotency_key, causation_id, correlation_id,
            ))
            or isinstance(delivery_revision, bool)
            or not isinstance(delivery_revision, int)
            or delivery_revision <= 0
            or isinstance(expected_economy_revision, bool)
            or not isinstance(expected_economy_revision, int)
            or expected_economy_revision < 0
        ):
            return self._rejected_append(command_id, "commerce_payment_input_invalid")
        try:
            delivery_event = self._store.get_event(delivery_event_id)
        except KeyError:
            return self._rejected_append(command_id, "commerce_payment_source_missing")
        if (
            delivery_event.event_type != "gameplay.inventory.delivery_committed"
            or delivery_event.visibility_policy != "project"
            or delivery_event.stream_id != delivery_stream_id
            or delivery_event.stream_revision != delivery_revision
            or self._store.get_stream_head(delivery_stream_id) != delivery_revision
        ):
            return self._rejected_append(command_id, "commerce_payment_source_invalid")
        source = delivery_event.payload
        if source.get("commitment_ref") != commitment_ref:
            return self._rejected_append(command_id, "commerce_payment_commitment_mismatch")
        seller_ref = source.get("actor_ref")
        delivery_ref = source.get("delivery_ref")
        if not isinstance(seller_ref, str) or not seller_ref or not isinstance(delivery_ref, str) or not delivery_ref:
            return self._rejected_append(command_id, "commerce_payment_source_invalid")
        if delivery_stream_id != f"gameplay:inventory:{seller_ref}":
            return self._rejected_append(command_id, "commerce_payment_source_invalid")
        economy_stream = "gameplay:economy"
        if self._store.get_stream_head(economy_stream) != expected_economy_revision:
            return self._rejected_append(command_id, "revision_conflict")
        events = self._store.read_stream(economy_stream)
        delivery_obligation = next(
            (
                event for event in reversed(events)
                if event.event_type == "gameplay.economy.delivery_obligation_updated"
                and event.visibility_policy == "project"
                and event.payload.get("delivery_ref") == delivery_ref
                and event.payload.get("commitment_ref") == commitment_ref
                and event.payload.get("status") == "delivered"
            ),
            None,
        )
        commerce_obligation = next(
            (
                event for event in reversed(events)
                if event.event_type == "gameplay.economy.commerce_obligation_recorded"
                and event.visibility_policy == "project"
                and event.payload.get("commitment_ref") == commitment_ref
            ),
            None,
        )
        if delivery_obligation is None or commerce_obligation is None:
            return self._rejected_append(command_id, "commerce_payment_obligation_missing")
        if any(
            event.event_type == "gameplay.economy.commerce_delivery_payment_settled"
            and event.payload.get("delivery_event_id") == delivery_event_id
            for event in events
        ):
            return self._rejected_append(command_id, "commerce_payment_already_settled")
        buyer_ref = commerce_obligation.payload.get("buyer_organization_ref")
        committed_reservation_refs = commerce_obligation.payload.get("budget_reservation_refs")
        if (
            not isinstance(buyer_ref, str)
            or not buyer_ref
            or not isinstance(committed_reservation_refs, (tuple, list))
            or budget_reservation_ref not in committed_reservation_refs
        ):
            return self._rejected_append(command_id, "commerce_payment_obligation_invalid")
        projection = self._projector.rebuild(self._store.read_events())
        reservation = projection.budget_reservations.get(budget_reservation_ref)
        if reservation is None:
            return self._rejected_append(command_id, "commerce_payment_reservation_missing")
        buyer_account = projection.accounts.get(reservation.account_id)
        seller_account = projection.accounts.get(seller_account_id)
        if buyer_account is None or buyer_account.owner_ref != buyer_ref:
            return self._rejected_append(command_id, "commerce_payment_buyer_account_invalid")
        if (
            seller_account is None
            or seller_account.owner_ref != seller_ref
            or seller_account.currency_ref != buyer_account.currency_ref
        ):
            return self._rejected_append(command_id, "commerce_payment_seller_account_invalid")
        if buyer_account.balance < reservation.amount_minor:
            return self._rejected_append(command_id, "commerce_payment_insufficient_funds")
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:economy-commerce-delivery-payment@1",
                contract_kind="settlement",
                owner_ref=self._PRINCIPAL,
                stream_ids=(economy_stream,),
                event_types=(
                    "gameplay.economy.account_debited",
                    "gameplay.economy.account_credited",
                    "gameplay.economy.commerce_delivery_payment_settled",
                ),
                projection_scope="authority_only",
            )
        except GovernedAuthorityContractError as exc:
            return self._rejected_append(command_id, str(exc))
        amount = reservation.amount_minor
        fragment = OwnerAuthorizedFragment(
            fragment_id=f"fragment:economy:commerce-payment:{delivery_event_id}",
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref="economy:commerce-delivery-payment",
            expected_revisions={economy_stream: expected_economy_revision},
            read_set_revisions={delivery_stream_id: delivery_revision},
            pinned_revisions={"economy": expected_economy_revision, "delivery": delivery_revision},
            event_specs={
                economy_stream: (
                    ("gameplay.economy.account_debited", {"account_id": buyer_account.account_id, "amount": amount}),
                    ("gameplay.economy.account_credited", {"account_id": seller_account.account_id, "amount": amount}),
                    (
                        "gameplay.economy.commerce_delivery_payment_settled",
                        {
                            "delivery_event_id": delivery_event_id,
                            "delivery_ref": delivery_ref,
                            "commitment_ref": commitment_ref,
                            "buyer_account_id": buyer_account.account_id,
                            "seller_account_id": seller_account.account_id,
                            "amount_minor": amount,
                            "source_delivery_obligation_event_id": delivery_obligation.event_id,
                            "source_commerce_obligation_event_id": commerce_obligation.event_id,
                        },
                    ),
                )
            },
            event_visibility_policies={economy_stream: ("authority_only", "authority_only", "authority_only")},
        )
        return self._append_commerce_delivery_payment(
            command_id=command_id,
            command_type="gameplay.economy.settle_commerce_delivery_payment",
            submitted_at="economy-commerce-payment",
            terminal_event_type="gameplay.economy.commerce_delivery_payment_settled",
            source_ref=delivery_event_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            fragment=fragment,
            request_digest=request_digest,
        )

    def compensate_commerce_delivery_payment(
        self,
        *,
        command_id: str,
        settled_delivery_event_id: str,
        compensation_event_id: str,
        compensation_stream_id: str,
        compensation_revision: int,
        commitment_ref: str,
        expected_economy_revision: int,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        privacy_scope: str = "authority",
    ) -> AppendBatchResult:
        request = {
            "operation": "commerce_delivery_payment_compensation",
            "command_id": command_id,
            "settled_delivery_event_id": settled_delivery_event_id,
            "compensation_event_id": compensation_event_id,
            "compensation_stream_id": compensation_stream_id,
            "compensation_revision": compensation_revision,
            "commitment_ref": commitment_ref,
            "expected_economy_revision": expected_economy_revision,
            "causation_id": causation_id,
            "correlation_id": correlation_id,
            "privacy_scope": privacy_scope,
        }
        request_digest = _digest(request)
        duplicate = self._commerce_payment_duplicate_result(
            command_id=command_id,
            idempotency_key=idempotency_key,
            request_digest=request_digest,
        )
        if duplicate is not None:
            return duplicate
        if privacy_scope != "authority":
            return self._rejected_append(command_id, "commerce_payment_privacy_denied")
        if (
            not all(isinstance(value, str) and value for value in (
                command_id, settled_delivery_event_id, compensation_event_id, compensation_stream_id,
                commitment_ref, idempotency_key, causation_id, correlation_id,
            ))
            or isinstance(compensation_revision, bool)
            or not isinstance(compensation_revision, int)
            or compensation_revision <= 0
            or isinstance(expected_economy_revision, bool)
            or not isinstance(expected_economy_revision, int)
            or expected_economy_revision < 0
        ):
            return self._rejected_append(command_id, "commerce_payment_input_invalid")
        try:
            compensation_event = self._store.get_event(compensation_event_id)
        except KeyError:
            return self._rejected_append(command_id, "commerce_payment_compensation_source_missing")
        if (
            compensation_event.event_type not in {"gameplay.inventory.delivery_rejected", "gameplay.inventory.delivery_cancelled"}
            or compensation_event.visibility_policy != "project"
            or compensation_event.stream_id != compensation_stream_id
            or compensation_event.stream_revision != compensation_revision
            or self._store.get_stream_head(compensation_stream_id) != compensation_revision
        ):
            return self._rejected_append(command_id, "commerce_payment_compensation_source_invalid")
        compensation_source = compensation_event.payload
        if compensation_source.get("commitment_ref") != commitment_ref:
            return self._rejected_append(command_id, "commerce_payment_compensation_commitment_mismatch")
        seller_ref = compensation_source.get("actor_ref")
        compensation_delivery_ref = compensation_source.get("delivery_ref")
        if (
            not isinstance(seller_ref, str)
            or not seller_ref
            or compensation_stream_id != f"gameplay:inventory:{seller_ref}"
            or not isinstance(compensation_delivery_ref, str)
            or not compensation_delivery_ref
        ):
            return self._rejected_append(command_id, "commerce_payment_compensation_source_invalid")
        economy_stream = "gameplay:economy"
        if self._store.get_stream_head(economy_stream) != expected_economy_revision:
            return self._rejected_append(command_id, "revision_conflict")
        events = self._store.read_stream(economy_stream)
        settled_event = next(
            (
                event for event in reversed(events)
                if event.event_type == "gameplay.economy.commerce_delivery_payment_settled"
                and event.payload.get("delivery_event_id") == settled_delivery_event_id
                and event.payload.get("commitment_ref") == commitment_ref
            ),
            None,
        )
        if settled_event is None:
            return self._rejected_append(command_id, "commerce_payment_settlement_missing")
        if compensation_event.global_sequence <= settled_event.global_sequence:
            return self._rejected_append(command_id, "commerce_payment_compensation_source_invalid")
        if any(
            event.event_type == "gameplay.economy.commerce_delivery_payment_compensated"
            and event.payload.get("settled_delivery_event_id") == settled_delivery_event_id
            for event in events
        ):
            return self._rejected_append(command_id, "commerce_payment_already_compensated")
        settled_payload = settled_event.payload
        buyer_account_id = settled_payload.get("buyer_account_id")
        seller_account_id = settled_payload.get("seller_account_id")
        amount_minor = settled_payload.get("amount_minor")
        delivery_ref = settled_payload.get("delivery_ref")
        if (
            not isinstance(buyer_account_id, str)
            or not buyer_account_id
            or not isinstance(seller_account_id, str)
            or not seller_account_id
            or isinstance(amount_minor, bool)
            or not isinstance(amount_minor, int)
            or amount_minor <= 0
            or not isinstance(delivery_ref, str)
            or not delivery_ref
        ):
            return self._rejected_append(command_id, "commerce_payment_settlement_invalid")
        projection = self._projector.rebuild(self._store.read_events())
        buyer_account = projection.accounts.get(buyer_account_id)
        seller_account = projection.accounts.get(seller_account_id)
        if (
            buyer_account is None
            or seller_account is None
            or seller_account.owner_ref != seller_ref
            or seller_account.currency_ref != buyer_account.currency_ref
        ):
            return self._rejected_append(command_id, "commerce_payment_compensation_source_invalid")
        if seller_account.balance < amount_minor:
            return self._rejected_append(command_id, "commerce_payment_compensation_insufficient_funds")
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:economy-commerce-delivery-payment@1",
                contract_kind="settlement",
                owner_ref=self._PRINCIPAL,
                stream_ids=(economy_stream,),
                event_types=(
                    "gameplay.economy.account_debited",
                    "gameplay.economy.account_credited",
                    "gameplay.economy.commerce_delivery_payment_compensated",
                ),
                projection_scope="authority_only",
            )
        except GovernedAuthorityContractError as exc:
            return self._rejected_append(command_id, str(exc))
        fragment = OwnerAuthorizedFragment(
            fragment_id=f"fragment:economy:commerce-payment-compensation:{settled_delivery_event_id}",
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref="economy:commerce-delivery-payment-compensation",
            expected_revisions={economy_stream: expected_economy_revision},
            read_set_revisions={compensation_stream_id: compensation_revision},
            pinned_revisions={"economy": expected_economy_revision, "compensation": compensation_revision},
            event_specs={
                economy_stream: (
                    ("gameplay.economy.account_debited", {"account_id": seller_account_id, "amount": amount_minor}),
                    ("gameplay.economy.account_credited", {"account_id": buyer_account_id, "amount": amount_minor}),
                    (
                        "gameplay.economy.commerce_delivery_payment_compensated",
                        {
                            "settled_delivery_event_id": settled_delivery_event_id,
                            "compensation_event_id": compensation_event_id,
                            "delivery_ref": delivery_ref,
                            "compensation_delivery_ref": compensation_delivery_ref,
                            "commitment_ref": commitment_ref,
                            "buyer_account_id": buyer_account_id,
                            "seller_account_id": seller_account_id,
                            "amount_minor": amount_minor,
                            "source_settlement_event_id": settled_event.event_id,
                        },
                    ),
                )
            },
            event_visibility_policies={economy_stream: ("authority_only", "authority_only", "authority_only")},
        )
        return self._append_commerce_delivery_payment(
            command_id=command_id,
            command_type="gameplay.economy.compensate_commerce_delivery_payment",
            submitted_at="economy-commerce-payment-compensation",
            terminal_event_type="gameplay.economy.commerce_delivery_payment_compensated",
            source_ref=compensation_event_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            fragment=fragment,
            request_digest=request_digest,
        )

    def commerce_delivery_payment_projection(
        self, *, scope: str, checkpoint_at: int | None = None
    ) -> dict[str, object]:
        if scope not in {"authority", "public"}:
            raise EconomyRuntimeError("commerce_payment_projection_scope_invalid")
        events = [
            event for event in self._store.read_stream("gameplay:economy")
            if event.event_type in {
                "gameplay.economy.commerce_delivery_payment_settled",
                "gameplay.economy.commerce_delivery_payment_compensated",
            }
        ]
        if checkpoint_at is None:
            checkpoint_at = 0
        if checkpoint_at < 0:
            raise EconomyRuntimeError("commerce_payment_checkpoint_out_of_range")
        prefix_events = [event for event in events if event.global_sequence <= checkpoint_at]
        tail_events = [event for event in events if event.global_sequence > checkpoint_at]
        prefix_payments: dict[str, dict[str, object]] = {}
        for event in prefix_events:
            self._apply_commerce_delivery_payment_projection_event(
                payments=prefix_payments,
                event=event,
            )
        payments = dict(prefix_payments)
        for event in tail_events:
            self._apply_commerce_delivery_payment_projection_event(
                payments=payments,
                event=event,
            )
        visible = payments if scope == "authority" else {}
        projection: dict[str, object] = {"scope": scope, "payments": visible}
        projection["projection_hash"] = "sha256:" + sha256(
            json.dumps(projection, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()
        return projection

    def _apply_commerce_delivery_payment_projection_event(
        self,
        *,
        payments: dict[str, dict[str, object]],
        event: GameplayEvent,
    ) -> None:
        if event.event_type == "gameplay.economy.commerce_delivery_payment_settled":
            delivery_event_id = event.payload.get("delivery_event_id")
            if not isinstance(delivery_event_id, str) or not delivery_event_id:
                raise EconomyRuntimeError("commerce_payment_projection_invalid")
            payments[delivery_event_id] = {
                "status": "settled",
                "delivery_ref": event.payload.get("delivery_ref"),
                "commitment_ref": event.payload.get("commitment_ref"),
                "amount_minor": event.payload.get("amount_minor"),
                "payment_event_id": event.event_id,
            }
            return
        settled_delivery_event_id = event.payload.get("settled_delivery_event_id")
        if not isinstance(settled_delivery_event_id, str) or not settled_delivery_event_id:
            raise EconomyRuntimeError("commerce_payment_projection_invalid")
        prior = payments.get(settled_delivery_event_id, {})
        payments[settled_delivery_event_id] = {
            **prior,
            "status": "compensated",
            "delivery_ref": event.payload.get("delivery_ref", prior.get("delivery_ref")),
            "commitment_ref": event.payload.get("commitment_ref", prior.get("commitment_ref")),
            "amount_minor": event.payload.get("amount_minor", prior.get("amount_minor")),
            "payment_event_id": prior.get("payment_event_id"),
            "compensation_event_id": event.payload.get("compensation_event_id"),
        }

    def _commerce_payment_duplicate_result(
        self,
        *,
        command_id: str,
        idempotency_key: str,
        request_digest: str,
    ) -> AppendBatchResult | None:
        existing_record = self._store.get_idempotency_record(self._PRINCIPAL, idempotency_key)
        if existing_record is None:
            return None
        if existing_record.payload_digest != request_digest:
            return self._rejected_append(command_id, "idempotency_key_reused")
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is None:
            return self._rejected_append(command_id, "idempotency_record_missing_result")
        return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)

    def _append_commerce_delivery_payment(
        self,
        *,
        command_id: str,
        command_type: str,
        submitted_at: str,
        terminal_event_type: str,
        source_ref: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        fragment: OwnerAuthorizedFragment,
        request_digest: str,
    ) -> AppendBatchResult:
        stream = "gameplay:economy"
        event_specs = fragment.event_specs[stream]
        command = GameplayCommandEnvelope(
            command_id=command_id,
            command_type=command_type,
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=None,
            project_ref=None,
            transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key,
            expected_revisions={stream: fragment.expected_revisions[stream]},
            read_set_revisions=dict(fragment.read_set_revisions),
            causation_id=causation_id,
            correlation_id=correlation_id,
            source_ref=source_ref,
            submitted_at=submitted_at,
            pinned_revisions=dict(fragment.pinned_revisions),
            payload={
                "stream_ref": stream,
                "event_type": terminal_event_type,
                "event_specs": [
                    {"event_type": event_type, "payload": {**payload, "visibility_policy": "authority_only"}}
                    for event_type, payload in event_specs
                ],
            },
        )
        batch = SettlementPlan.from_command_envelope(command).to_atomic_event_batch()
        batch = batch.model_copy(
            update={
                "owner_fragments": [fragment],
                "idempotency_record": batch.idempotency_record.model_copy(
                    update={"payload_digest": request_digest},
                    deep=True,
                ),
            },
            deep=True,
        )
        batch = batch.model_copy(
            update={
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}",
                        transaction_id=batch.transaction_id,
                        event_id=event.event_id,
                        global_sequence=0,
                        topic="economy.commerce_payment.scoped_projection",
                        audience="authority:economy",
                        payload_projection={
                            "event_type": event.event_type,
                            "delivery_ref": str(
                                event.payload.get(
                                    "delivery_ref",
                                    event.payload.get("compensation_delivery_ref", ""),
                                )
                            ),
                        },
                    )
                    for event in batch.events
                ],
            },
            deep=True,
        )
        return self._store.append_batch(batch)
    def open_account(self, *, command_id:str, account_id:str, owner_ref:str, currency_ref:str, initial_balance:int, idempotency_key:str, causation_id:str, correlation_id:str, expected_revision:int|None=None)->AppendBatchResult:
        p=self._projector.rebuild(self._store.read_events())
        if account_id in p.accounts or not account_id or not owner_ref or not currency_ref or initial_balance<0: raise EconomyRuntimeError("economy_account_invalid")
        return self._append_account_settlement(
            command_id=command_id,
            command_type="gameplay.economy.open_account",
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            current_revision=p.source_revision_vector.get("gameplay:economy", 0),
            supplied_revision=expected_revision,
            source_ref=account_id,
            event_specs=(("gameplay.economy.account_opened", {"account_id":account_id,"owner_ref":owner_ref,"currency_ref":currency_ref,"initial_balance":initial_balance}),),
        )
    def transfer(self, *, command_id:str, debit_account_id:str, credit_account_id:str, amount:int, idempotency_key:str, causation_id:str, correlation_id:str, expected_revision:int|None=None)->AppendBatchResult:
        p=self._projector.rebuild(self._store.read_events()); debit=p.accounts.get(debit_account_id); credit=p.accounts.get(credit_account_id)
        if debit is None or credit is None or debit.currency_ref != credit.currency_ref or debit_account_id==credit_account_id or amount<=0: raise EconomyRuntimeError("economy_transfer_invalid")
        if debit.balance<amount: raise EconomyRuntimeError("economy_insufficient_funds")
        return self._append_account_settlement(
            command_id=command_id,
            command_type="gameplay.economy.transfer",
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            current_revision=p.source_revision_vector.get("gameplay:economy", 0),
            supplied_revision=expected_revision,
            source_ref=debit_account_id,
            event_specs=(
                ("gameplay.economy.account_debited", {"account_id":debit_account_id,"amount":amount}),
                ("gameplay.economy.account_credited", {"account_id":credit_account_id,"amount":amount}),
            ),
        )
    def reserve_budget(self, *, command_id:str, reservation_ref:str, account_id:str, amount_minor:int, idempotency_key:str, causation_id:str, correlation_id:str, expected_revision:int|None=None)->AppendBatchResult:
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
        return self._append_account_settlement(
            command_id=command_id,
            command_type="gameplay.economy.reserve_budget",
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            current_revision=p.source_revision_vector.get("gameplay:economy", 0),
            supplied_revision=expected_revision,
            source_ref=account_id,
            event_specs=(("gameplay.economy.budget_reserved", {"reservation_ref":reservation_ref,"account_id":account_id,"amount_minor":amount_minor}),),
        )

    def register_scheduled_transfer_policy_instance(
        self,
        *,
        policy: ScheduledAccountTransferPolicyInstance,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        expected_revision: int,
        privacy_scope: str,
    ) -> AppendBatchResult:
        if privacy_scope != "authority_only":
            return self._rejected_append(command_id, "economy_policy_privacy_denied")
        projection = self._projector.rebuild(self._store.read_events())
        payload = policy.model_dump(mode="json")
        duplicate = self._scheduled_transfer_policy_duplicate_result(
            command_id=command_id,
            idempotency_key=idempotency_key,
            event_type="gameplay.economy.scheduled_transfer_policy_registered",
            payload=payload,
        )
        if duplicate is not None:
            return duplicate
        if projection.source_revision_vector.get("gameplay:economy", 0) != expected_revision:
            return self._rejected_append(command_id, "revision_conflict")
        self._validate_scheduled_transfer_policy_instance(policy=policy, projection=projection)
        if policy.policy_instance_ref in projection.scheduled_transfer_policies:
            return self._rejected_append(command_id, "economy_policy_already_active")
        return self._append_scheduled_transfer_policy_event(
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            expected_revision=expected_revision,
            event_type="gameplay.economy.scheduled_transfer_policy_registered",
            payload=payload,
            fragment_id=f"fragment:economy:scheduled-transfer-policy:register:{policy.policy_instance_ref}",
            source_rule_ref="economy:scheduled-account-transfer-policy:register",
            outbox_audience="authority:economy",
        )

    def revoke_scheduled_transfer_policy_instance(
        self,
        *,
        policy_instance_ref: str,
        policy_revision: str,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        expected_revision: int,
        privacy_scope: str,
    ) -> AppendBatchResult:
        if privacy_scope != "authority_only":
            return self._rejected_append(command_id, "economy_policy_privacy_denied")
        projection = self._projector.rebuild(self._store.read_events())
        active = projection.scheduled_transfer_policies.get(policy_instance_ref)
        payload = {
            "policy_instance_ref": policy_instance_ref,
            "policy_ref": active.policy_ref if active is not None else "policy:economy_scheduled_account_transfer@1",
            "policy_revision": policy_revision,
        }
        duplicate = self._scheduled_transfer_policy_duplicate_result(
            command_id=command_id,
            idempotency_key=idempotency_key,
            event_type="gameplay.economy.scheduled_transfer_policy_revoked",
            payload=payload,
        )
        if duplicate is not None:
            return duplicate
        if projection.source_revision_vector.get("gameplay:economy", 0) != expected_revision:
            return self._rejected_append(command_id, "revision_conflict")
        if active is None:
            return self._rejected_append(command_id, "economy_policy_not_active")
        if active.policy_revision != policy_revision:
            raise EconomyRuntimeError("economy_policy_invalid")
        return self._append_scheduled_transfer_policy_event(
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            expected_revision=expected_revision,
            event_type="gameplay.economy.scheduled_transfer_policy_revoked",
            payload=payload,
            fragment_id=f"fragment:economy:scheduled-transfer-policy:revoke:{policy_instance_ref}",
            source_rule_ref="economy:scheduled-account-transfer-policy:revoke",
            outbox_audience="authority:economy",
        )

    @classmethod
    def scheduled_account_transfer_obligation_registration(cls) -> ObligationLifecycleRegistration:
        return ObligationLifecycleRegistration(
            policy_ref="policy:economy_scheduled_account_transfer@1",
            policy_revision="1",
            owner_ref=cls._PRINCIPAL,
            stream_pattern="gameplay:economy",
            opened_event_type="gameplay.economy.scheduled_transfer_obligation_opened",
            settled_event_type="gameplay.economy.scheduled_transfer_obligation_settled",
            cancelled_event_type="gameplay.economy.scheduled_transfer_obligation_cancelled",
            expired_event_type="gameplay.economy.scheduled_transfer_obligation_expired",
            visibility_scope="authority_only",
            requires_committed_open=True,
        )

    @staticmethod
    def scheduled_transfer_obligation_id_for(*, transfer_ref: str) -> str:
        return f"obligation:economy:scheduled-transfer:{transfer_ref}"

    def open_scheduled_account_transfer_obligation(
        self,
        *,
        command_id: str,
        transfer_ref: str,
        debit_account_id: str,
        credit_account_id: str,
        amount: int,
        due_tick: int,
        policy_instance_ref: str | None = None,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        expected_revision: int | None = None,
    ) -> ScheduledTransferObligationResult:
        projection = self._projector.rebuild(self._store.read_events())
        debit = projection.accounts.get(debit_account_id)
        credit = projection.accounts.get(credit_account_id)
        obligation_id = self.scheduled_transfer_obligation_id_for(transfer_ref=transfer_ref)
        if (
            not transfer_ref.startswith("scheduled-transfer:")
            or debit is None
            or credit is None
            or debit_account_id == credit_account_id
            or debit.currency_ref != credit.currency_ref
            or amount <= 0
            or due_tick < 0
            or debit.balance < amount
        ):
            raise EconomyRuntimeError("economy_scheduled_transfer_invalid")
        opening_payload = {
            "obligation_id": obligation_id,
            "transfer_ref": transfer_ref,
            "debit_account_id": debit_account_id,
            "credit_account_id": credit_account_id,
            "amount": amount,
            "due_tick": due_tick,
            "policy_ref": "policy:economy_scheduled_account_transfer@1",
            "policy_revision": "1",
            "open_idempotency_key": idempotency_key,
        }
        if policy_instance_ref is not None:
            policy_admission = self._admit_scheduled_transfer_policy_instance(
                command_id=command_id,
                projection=projection,
                policy_instance_ref=policy_instance_ref,
                debit_account_id=debit_account_id,
                credit_account_id=credit_account_id,
                amount=amount,
                due_tick=due_tick,
            )
            if isinstance(policy_admission, ScheduledTransferObligationResult):
                return policy_admission
            policy, registration = policy_admission
            opening_payload.update(
                {
                    "policy_instance_ref": policy.policy_instance_ref,
                    "policy_registration_event_id": registration.event_id,
                    "policy_registration_stream_revision": registration.stream_revision,
                    "policy_revision": policy.policy_revision,
                }
            )
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is None and any(
            event.event_type == "gameplay.economy.scheduled_transfer_obligation_opened"
            and event.payload.get("transfer_ref") == transfer_ref
            for event in self._store.read_stream("gameplay:economy")
        ):
            raise EconomyRuntimeError("economy_scheduled_transfer_duplicate")
        append = self._append_account_settlement(
            command_id=command_id,
            command_type="gameplay.economy.open_scheduled_transfer_obligation",
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            current_revision=projection.source_revision_vector.get("gameplay:economy", 0),
            supplied_revision=expected_revision,
            source_ref=debit_account_id,
            event_specs=(
                (
                    "gameplay.economy.scheduled_transfer_obligation_opened",
                    opening_payload,
                ),
            ),
        )
        obligation = self.scheduled_account_transfer_obligation_for(obligation_id=obligation_id) if append.committed else None
        return ScheduledTransferObligationResult(
            committed=append.committed,
            obligation=obligation,
            append_result=append,
        )

    def scheduled_account_transfer_obligation_for(self, *, obligation_id: str) -> ScheduledObligation:
        opening = self._scheduled_transfer_opening(obligation_id=obligation_id)
        stream = "gameplay:economy"
        due_tick = _nonnegative(opening.payload, "due_tick")
        source_refs = ["policy:economy_scheduled_account_transfer@1", f"opening_event:{opening.event_id}"]
        policy_instance_ref = opening.payload.get("policy_instance_ref")
        registration_event_id = opening.payload.get("policy_registration_event_id")
        if isinstance(policy_instance_ref, str) and policy_instance_ref:
            source_refs.append(f"policy_instance:{policy_instance_ref}")
        if isinstance(registration_event_id, str) and registration_event_id:
            source_refs.append(f"policy_registration_event:{registration_event_id}")
        return ScheduledObligation(
            obligation_id=obligation_id,
            owner_ref=self._PRINCIPAL,
            due_tick=due_tick,
            policy_revision=_text(opening.payload, "policy_revision"),
            status="open",
            idempotency_key=f"{_text(opening.payload, 'open_idempotency_key')}:settle",
            expected_revisions={stream: self._store.get_stream_head(stream)},
            visibility_scope="authority_only",
            source_refs=tuple(source_refs),
        )

    def build_scheduled_account_transfer_settlement_fragment(
        self, *, obligation: ScheduledObligation
    ) -> OwnerAuthorizedFragment:
        opening = self._scheduled_transfer_opening(obligation_id=obligation.obligation_id)
        stream = "gameplay:economy"
        if (
            obligation.owner_ref != self._PRINCIPAL
            or obligation.visibility_scope != "authority_only"
            or set(obligation.expected_revisions) != {stream}
            or obligation.due_tick != _nonnegative(opening.payload, "due_tick")
            or "policy:economy_scheduled_account_transfer@1" not in obligation.source_refs
            or f"opening_event:{opening.event_id}" not in obligation.source_refs
        ):
            raise EconomyRuntimeError("economy_scheduled_transfer_obligation_invalid")
        self._revalidate_scheduled_transfer_policy_snapshot(opening=opening, obligation=obligation)
        debit_account_id = _text(opening.payload, "debit_account_id")
        credit_account_id = _text(opening.payload, "credit_account_id")
        amount = _positive(opening.payload, "amount")
        projection = self._projector.rebuild(self._store.read_events())
        debit = projection.accounts.get(debit_account_id)
        credit = projection.accounts.get(credit_account_id)
        if (
            debit is None
            or credit is None
            or debit.currency_ref != credit.currency_ref
            or debit.balance < amount
        ):
            raise EconomyRuntimeError("economy_scheduled_transfer_unfunded")
        return OwnerAuthorizedFragment(
            fragment_id=f"fragment:economy:scheduled-transfer:settle:{obligation.obligation_id}",
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref="economy:scheduled-account-transfer:settle",
            expected_revisions=dict(obligation.expected_revisions),
            pinned_revisions={"economy": obligation.expected_revisions[stream]},
            event_specs={
                stream: (
                    ("gameplay.economy.account_debited", {"account_id": debit_account_id, "amount": amount}),
                    ("gameplay.economy.account_credited", {"account_id": credit_account_id, "amount": amount}),
                    (
                        "gameplay.economy.scheduled_transfer_obligation_settled",
                        {
                            "obligation_id": obligation.obligation_id,
                            "prior_state": obligation.status,
                            "current_state": "settled",
                            "policy_ref": "policy:economy_scheduled_account_transfer@1",
                            "policy_revision": obligation.policy_revision,
                            "due_tick": obligation.due_tick,
                        },
                    ),
                )
            },
            event_visibility_policies={stream: ("authority_only", "authority_only", "authority_only")},
        )

    def build_scheduled_account_transfer_cancellation_fragment(
        self, *, obligation: ScheduledObligation, reason_ref: str
    ) -> OwnerAuthorizedFragment:
        return self._scheduled_transfer_terminal_fragment(
            obligation=obligation,
            reason_ref=reason_ref,
            event_type="gameplay.economy.scheduled_transfer_obligation_cancelled",
            current_state="cancelled",
        )

    def build_scheduled_account_transfer_expiry_fragment(
        self, *, obligation: ScheduledObligation, reason_ref: str
    ) -> OwnerAuthorizedFragment:
        return self._scheduled_transfer_terminal_fragment(
            obligation=obligation,
            reason_ref=reason_ref,
            event_type="gameplay.economy.scheduled_transfer_obligation_expired",
            current_state="expired",
        )

    def _scheduled_transfer_terminal_fragment(
        self,
        *,
        obligation: ScheduledObligation,
        reason_ref: str,
        event_type: str,
        current_state: str,
    ) -> OwnerAuthorizedFragment:
        opening = self._scheduled_transfer_opening(obligation_id=obligation.obligation_id)
        stream = "gameplay:economy"
        if (
            not reason_ref
            or obligation.status not in {"open", "due"}
            or obligation.owner_ref != self._PRINCIPAL
            or obligation.visibility_scope != "authority_only"
            or set(obligation.expected_revisions) != {stream}
            or obligation.due_tick != _nonnegative(opening.payload, "due_tick")
            or "policy:economy_scheduled_account_transfer@1" not in obligation.source_refs
            or f"opening_event:{opening.event_id}" not in obligation.source_refs
        ):
            raise EconomyRuntimeError("economy_scheduled_transfer_obligation_invalid")
        self._revalidate_scheduled_transfer_policy_snapshot(opening=opening, obligation=obligation)
        return OwnerAuthorizedFragment(
            fragment_id=f"fragment:economy:scheduled-transfer:{current_state}:{obligation.obligation_id}",
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref=f"economy:scheduled-account-transfer:{current_state}",
            expected_revisions=dict(obligation.expected_revisions),
            pinned_revisions={"economy": obligation.expected_revisions[stream]},
            event_specs={
                stream: (
                    (
                        event_type,
                        {
                            "obligation_id": obligation.obligation_id,
                            "prior_state": obligation.status,
                            "current_state": current_state,
                            "policy_ref": "policy:economy_scheduled_account_transfer@1",
                            "policy_revision": obligation.policy_revision,
                            "due_tick": obligation.due_tick,
                            "reason_ref": reason_ref,
                        },
                    ),
                )
            },
            event_visibility_policies={stream: ("authority_only",)},
        )

    def _scheduled_transfer_opening(self, *, obligation_id: str) -> GameplayEvent:
        for event in reversed(self._store.read_stream("gameplay:economy")):
            if (
                event.event_type == "gameplay.economy.scheduled_transfer_obligation_opened"
                and event.payload.get("obligation_id") == obligation_id
                and event.visibility_policy == "authority_only"
                and event.payload.get("policy_ref") == "policy:economy_scheduled_account_transfer@1"
                and event.payload.get("policy_revision") == "1"
            ):
                return event
        raise EconomyRuntimeError("economy_scheduled_transfer_source_missing")
    def publish_dynamic_quote(self, *, command_id:str, quote_payload:Mapping[str,object], idempotency_key:str, causation_id:str, correlation_id:str, ecology_weather_source: Mapping[str, object] | None = None, expected_revision: int | None = None)->AppendBatchResult:
        p = self._projector.rebuild(self._store.read_events())
        quote_ref = _text(quote_payload, "quote_ref")
        version = _positive(quote_payload, "version")
        if {"account_id", "debit_account_id", "credit_account_id", "payment_ref"} & set(quote_payload):
            raise EconomyRuntimeError("economy_dynamic_quote_privacy_denied")
        event_payload = {"quote": dict(quote_payload)}
        if ecology_weather_source is not None:
            event_payload["ecology_weather_source"] = dict(ecology_weather_source)
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None and existing.committed:
            if len(existing.committed_event_ids) == 1:
                event = self._store.get_event(existing.committed_event_ids[0])
                if event.event_type == "gameplay.economy.dynamic_quote_published" and event.payload == event_payload:
                    return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            return AppendBatchResult(
                committed=False,
                transaction_id=f"transaction:{command_id}",
                command_id=command_id,
                idempotency_status="rejected",
            )
        previous = p.dynamic_quotes.get(quote_ref)
        if previous is not None and version <= _positive(previous, "version"):
            raise EconomyRuntimeError("economy_dynamic_quote_version_invalid")
        if quote_payload.get("status") not in {"active", "cancelled"}:
            raise EconomyRuntimeError("economy_dynamic_quote_invalid")
        stream = "gameplay:economy"
        expected_stream_revision = self._expected_revision(
            p.source_revision_vector.get(stream, 0),
            expected_revision,
        )
        command = GameplayCommandEnvelope(
            command_id=command_id, command_type="gameplay.economy.publish_dynamic_quote", command_version=1,
            principal_ref=self._PRINCIPAL, actor_ref=None, project_ref=None, transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key, expected_revisions={stream: expected_stream_revision}, read_set_revisions={stream: expected_stream_revision},
            causation_id=causation_id, correlation_id=correlation_id, source_ref="economy-dynamic-quote",
            submitted_at="economy-dynamic-quote", pinned_revisions={"economy": expected_stream_revision},
            payload={"stream_ref": stream, "event_type": "gameplay.economy.dynamic_quote_published", "visibility_policy": "project", **event_payload},
        )
        batch = SettlementPlan.from_command_envelope(command).to_atomic_event_batch()
        event = batch.events[0]
        fragment = OwnerAuthorizedFragment(
            fragment_id=f"fragment:economy:dynamic-quote:{quote_ref}:{version}", owner_principal_ref=self._PRINCIPAL,
            source_rule_ref="economy:dynamic-quote", expected_revisions={stream: expected_stream_revision},
            read_set_revisions={stream: expected_stream_revision}, pinned_revisions={"economy": expected_stream_revision},
            event_specs={stream: ((event.event_type, dict(event.payload)),)}, event_visibility_policies={stream: ("project",)},
        )
        batch = batch.model_copy(update={"owner_fragments": [fragment], "outbox_entries": [GameplayOutboxEntry(
            outbox_id=f"outbox:{event.event_id}", transaction_id=batch.transaction_id, event_id=event.event_id,
            global_sequence=0, topic="economy.dynamic_quote.scoped_projection", audience="project",
            payload_projection={"quote_ref": quote_ref, "version": version, "status": str(quote_payload["status"])},
        )]}, deep=True)
        return self._store.append_batch(batch)
    @staticmethod
    def _weather_quote_source(source: Mapping[str, object]) -> dict[str, object]:
        fields = (
            "weather_event_id",
            "ecology_stream_id",
            "ecology_revision",
            "region_ref",
            "quote_ref",
        )
        if not isinstance(source, Mapping) or set(source) != set(fields):
            raise EconomyRuntimeError("weather_quote_source_invalid")
        normalized = {field: source[field] for field in fields}
        if (
            not all(isinstance(normalized[field], str) and normalized[field] for field in fields if field != "ecology_revision")
            or isinstance(normalized["ecology_revision"], bool)
            or not isinstance(normalized["ecology_revision"], int)
            or normalized["ecology_revision"] < 1
        ):
            raise EconomyRuntimeError("weather_quote_source_invalid")
        return normalized

    @staticmethod
    def _weather_quote_rejected(*, idempotency_key: str, error_code: str) -> AppendBatchResult:
        command_id = f"command:weather-quote:{idempotency_key}"
        return AppendBatchResult(
            committed=False,
            transaction_id=f"transaction:{command_id}",
            command_id=command_id,
            idempotency_status="rejected",
            failure=GameplayFailure(
                error_code=error_code,
                message=error_code,
                failed_stage="economy_weather_quote_admission",
            ),
        )

    def settle_weather_front_quote(self, *, source: Mapping[str, object], admission: object, idempotency_key: str) -> AppendBatchResult:
        try:
            normalized_source = self._weather_quote_source(source)
        except EconomyRuntimeError as exc:
            return self._weather_quote_rejected(
                idempotency_key=idempotency_key,
                error_code=str(exc),
            )
        if not _CONTAINS_WEATHER_QUOTE_ADMISSION(admission) or not _MATCHES_WEATHER_QUOTE_ADMISSION(admission, **normalized_source):
            return self._weather_quote_rejected(
                idempotency_key=idempotency_key,
                error_code="weather_quote_admission_required",
            )
        try:
            event = self._store.get_event(str(normalized_source["weather_event_id"]))
        except KeyError:
            return self._weather_quote_rejected(
                idempotency_key=idempotency_key,
                error_code="weather_quote_source_invalid",
            )
        if event.event_type != "gameplay.ecology.weather_front.propagated" or event.visibility_policy != "project" or event.stream_id != normalized_source["ecology_stream_id"] or event.stream_revision != normalized_source["ecology_revision"] or event.payload.get("target_region_ref") != normalized_source["region_ref"] or self._store.get_stream_head(event.stream_id) != normalized_source["ecology_revision"]:
            return self._weather_quote_rejected(
                idempotency_key=idempotency_key,
                error_code="weather_quote_source_invalid",
            )
        stream = "gameplay:economy"
        admission_check = EcologyConsumerAdmissionCheck.verify(
            store=self._store,
            contract_ref="inf:weather-front-economy-quote@1",
            target_owner_ref=self._PRINCIPAL,
            target_stream_ids=(stream,),
            target_event_types=("gameplay.economy.dynamic_quote_published",),
            projection_scope="project",
            source_event_id=event.event_id,
            source_stream_id=event.stream_id,
            source_revision=event.stream_revision,
            target_expected_revisions={stream: self._store.get_stream_head(stream)},
            idempotency_key=idempotency_key,
        )
        if not admission_check.accepted:
            return self._weather_quote_rejected(
                idempotency_key=idempotency_key,
                error_code=admission_check.error_code or "weather_quote_admission_invalid",
            )
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None and existing.committed:
            if len(existing.committed_event_ids) == 1:
                existing_event = self._store.get_event(existing.committed_event_ids[0])
                if (
                    existing_event.event_type == "gameplay.economy.dynamic_quote_published"
                    and existing_event.payload.get("ecology_weather_source") == normalized_source
                    and existing_event.payload.get("quote", {}).get("quote_ref") == normalized_source["quote_ref"]
                ):
                    return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            return self._weather_quote_rejected(
                idempotency_key=idempotency_key,
                error_code="weather_quote_idempotency_conflict",
            )
        quote_ref = str(normalized_source["quote_ref"]); quote = self._projector.rebuild(self._store.read_events()).dynamic_quotes.get(quote_ref)
        if quote is None:
            return self._weather_quote_rejected(
                idempotency_key=idempotency_key,
                error_code="weather_quote_target_missing",
            )
        updated = dict(quote); updated["version"] = _positive(quote, "version") + 1
        if "unit_price_minor" in updated: updated["unit_price_minor"] = max(1, int(updated["unit_price_minor"]) * 110 // 100)
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:weather-front-economy-quote@1",
                contract_kind="ecology_consumer",
                owner_ref=self._PRINCIPAL,
                stream_ids=("gameplay:economy",),
                event_types=("gameplay.economy.dynamic_quote_published",),
                projection_scope="project",
            )
        except GovernedAuthorityContractError as error:
            return self._weather_quote_rejected(
                idempotency_key=idempotency_key,
                error_code=str(error),
            )
        return self.publish_dynamic_quote(command_id=f"command:weather-quote:{event.event_id}:{quote_ref}", quote_payload=updated, idempotency_key=idempotency_key, causation_id=event.event_id, correlation_id=f"weather-quote:{quote_ref}", ecology_weather_source=normalized_source)

    @staticmethod
    def _weather_quote_fanout_source(source: Mapping[str, object]) -> dict[str, object]:
        fields = ("weather_event_id", "ecology_stream_id", "ecology_revision", "region_ref", "quote_refs")
        if not isinstance(source, Mapping) or set(source) != set(fields):
            raise EconomyRuntimeError("weather_quote_fanout_source_invalid")
        normalized = {field: source[field] for field in fields}
        quote_refs = normalized["quote_refs"]
        if (
            not all(isinstance(normalized[field], str) and normalized[field] for field in fields if field not in {"ecology_revision", "quote_refs"})
            or isinstance(normalized["ecology_revision"], bool)
            or not isinstance(normalized["ecology_revision"], int)
            or normalized["ecology_revision"] < 1
            or not isinstance(quote_refs, (tuple, list))
            or len(quote_refs) != 2
            or any(not isinstance(ref, str) or not ref for ref in quote_refs)
            or quote_refs[0] == quote_refs[1]
        ):
            raise EconomyRuntimeError("weather_quote_fanout_source_invalid")
        canonical_refs = tuple(sorted(quote_refs))
        if tuple(quote_refs) != canonical_refs:
            raise EconomyRuntimeError("weather_quote_fanout_source_invalid")
        normalized["quote_refs"] = canonical_refs
        return normalized

    @staticmethod
    def _weather_quote_fanout_rejected(*, idempotency_key: str, error_code: str) -> AppendBatchResult:
        command_id = f"command:weather-quote-fanout:{idempotency_key}"
        return AppendBatchResult(
            committed=False,
            transaction_id=f"transaction:{command_id}",
            command_id=command_id,
            idempotency_status="rejected",
            failure=GameplayFailure(
                error_code=error_code,
                message=error_code,
                failed_stage="economy_weather_quote_fanout_admission",
            ),
        )

    def settle_weather_front_quote_fanout(self, *, source: Mapping[str, object], admission: object, idempotency_key: str) -> AppendBatchResult:
        try:
            normalized_source = self._weather_quote_fanout_source(source)
        except EconomyRuntimeError as exc:
            return self._weather_quote_fanout_rejected(idempotency_key=idempotency_key, error_code=str(exc))
        if not _CONTAINS_WEATHER_QUOTE_FANOUT_ADMISSION(admission) or not _MATCHES_WEATHER_QUOTE_FANOUT_ADMISSION(admission, **normalized_source):
            return self._weather_quote_fanout_rejected(idempotency_key=idempotency_key, error_code="weather_quote_fanout_admission_required")
        try:
            event = self._store.get_event(str(normalized_source["weather_event_id"]))
        except KeyError:
            return self._weather_quote_fanout_rejected(idempotency_key=idempotency_key, error_code="weather_quote_fanout_source_invalid")
        if (
            event.event_type != "gameplay.ecology.weather_front.propagated"
            or event.visibility_policy != "project"
            or event.stream_id != normalized_source["ecology_stream_id"]
            or event.stream_revision != normalized_source["ecology_revision"]
            or event.payload.get("target_region_ref") != normalized_source["region_ref"]
            or self._store.get_stream_head(event.stream_id) != normalized_source["ecology_revision"]
        ):
            return self._weather_quote_fanout_rejected(idempotency_key=idempotency_key, error_code="weather_quote_fanout_source_invalid")
        stream = "gameplay:economy"
        admission_check = EcologyConsumerAdmissionCheck.verify(
            store=self._store,
            contract_ref="inf:weather-front-economy-quote-fanout@1",
            target_owner_ref=self._PRINCIPAL,
            target_stream_ids=(stream,),
            target_event_types=("gameplay.economy.dynamic_quote_published",),
            projection_scope="project",
            source_event_id=event.event_id,
            source_stream_id=event.stream_id,
            source_revision=event.stream_revision,
            target_expected_revisions={stream: self._store.get_stream_head(stream)},
            idempotency_key=idempotency_key,
        )
        if not admission_check.accepted:
            return self._weather_quote_fanout_rejected(
                idempotency_key=idempotency_key,
                error_code=admission_check.error_code or "weather_quote_fanout_admission_invalid",
            )
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None and existing.committed:
            if len(existing.committed_event_ids) == 2:
                prior_events = [self._store.get_event(event_id) for event_id in existing.committed_event_ids]
                if (
                    all(prior.event_type == "gameplay.economy.dynamic_quote_published" for prior in prior_events)
                    and all(prior.payload.get("ecology_weather_source") == normalized_source for prior in prior_events)
                    and tuple(sorted(str(prior.payload.get("quote", {}).get("quote_ref", "")) for prior in prior_events)) == normalized_source["quote_refs"]
                ):
                    return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            return self._weather_quote_fanout_rejected(idempotency_key=idempotency_key, error_code="weather_quote_fanout_idempotency_conflict")
        projection = self._projector.rebuild(self._store.read_events())
        expected_revision = projection.source_revision_vector.get(stream, 0)
        quotes: list[dict[str, object]] = []
        for quote_ref in normalized_source["quote_refs"]:
            quote = projection.dynamic_quotes.get(quote_ref)
            if quote is None:
                return self._weather_quote_fanout_rejected(idempotency_key=idempotency_key, error_code="weather_quote_fanout_target_missing")
            updated = dict(quote)
            updated["version"] = _positive(quote, "version") + 1
            if "unit_price_minor" in updated:
                updated["unit_price_minor"] = max(1, int(updated["unit_price_minor"]) * 110 // 100)
            quotes.append(updated)
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:weather-front-economy-quote-fanout@1",
                contract_kind="ecology_consumer",
                owner_ref=self._PRINCIPAL,
                stream_ids=(stream,),
                event_types=("gameplay.economy.dynamic_quote_published",),
                projection_scope="project",
            )
        except GovernedAuthorityContractError as error:
            return self._weather_quote_fanout_rejected(idempotency_key=idempotency_key, error_code=str(error))
        event_specs = tuple(("gameplay.economy.dynamic_quote_published", {"quote": quote, "ecology_weather_source": normalized_source}) for quote in quotes)
        fragment = OwnerAuthorizedFragment(
            fragment_id=f"fragment:economy:weather-quote-fanout:{event.event_id}:{':'.join(normalized_source['quote_refs'])}",
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref="economy:weather-front-quote-fanout",
            expected_revisions={stream: expected_revision},
            read_set_revisions={stream: expected_revision, event.stream_id: event.stream_revision},
            pinned_revisions={"economy": expected_revision, "ecology_source": event.stream_revision},
            event_specs={stream: event_specs},
            event_visibility_policies={stream: ("project", "project")},
        )
        command_id = f"command:weather-quote-fanout:{event.event_id}:{':'.join(normalized_source['quote_refs'])}"
        command = GameplayCommandEnvelope(
            command_id=command_id,
            command_type="gameplay.economy.weather_front_quote_fanout",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=None,
            project_ref=None,
            transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key,
            expected_revisions={stream: expected_revision},
            read_set_revisions=dict(fragment.read_set_revisions),
            causation_id=event.event_id,
            correlation_id=f"weather-quote-fanout:{':'.join(normalized_source['quote_refs'])}",
            source_ref=event.event_id,
            submitted_at="economy-weather-quote-fanout",
            pinned_revisions=dict(fragment.pinned_revisions),
            payload={
                "stream_ref": stream,
                "event_specs": [
                    {"event_type": event_type, "payload": {**payload, "visibility_policy": "project"}}
                    for event_type, payload in event_specs
                ],
            },
        )
        batch = SettlementPlan.from_command_envelope(command).to_atomic_event_batch()
        batch = batch.model_copy(
            update={
                "owner_fragments": [fragment],
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{published.event_id}",
                        transaction_id=batch.transaction_id,
                        event_id=published.event_id,
                        global_sequence=0,
                        topic="economy.dynamic_quote.scoped_projection",
                        audience="project",
                        payload_projection={
                            "quote_ref": str(published.payload["quote"]["quote_ref"]),
                            "version": int(published.payload["quote"]["version"]),
                            "status": str(published.payload["quote"]["status"]),
                        },
                    )
                    for published in batch.events
                ],
            },
            deep=True,
        )
        return self._store.append_batch(batch)
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
    def _validate_scheduled_transfer_policy_instance(self, *, policy: ScheduledAccountTransferPolicyInstance, projection: EconomyProjection) -> None:
        debit = projection.accounts.get(policy.debit_account_id)
        credit = projection.accounts.get(policy.credit_account_id)
        if (
            policy.policy_ref != "policy:economy_scheduled_account_transfer@1"
            or policy.debit_account_id == policy.credit_account_id
            or policy.active_until_tick < policy.active_from_tick
            or debit is None
            or credit is None
            or debit.currency_ref != credit.currency_ref
        ):
            raise EconomyRuntimeError("economy_policy_invalid")
    def _admit_scheduled_transfer_policy_instance(self, *, command_id: str, projection: EconomyProjection, policy_instance_ref: str, debit_account_id: str, credit_account_id: str, amount: int, due_tick: int) -> tuple[ScheduledAccountTransferPolicyInstance, GameplayEvent] | ScheduledTransferObligationResult:
        policy = projection.scheduled_transfer_policies.get(policy_instance_ref)
        if policy is None:
            return self._rejected_scheduled_transfer_open(command_id=command_id, error_code="economy_policy_instance_missing")
        if policy.debit_account_id != debit_account_id or policy.credit_account_id != credit_account_id:
            return self._rejected_scheduled_transfer_open(command_id=command_id, error_code="economy_policy_instance_mismatch")
        if amount > policy.amount_cap:
            return self._rejected_scheduled_transfer_open(command_id=command_id, error_code="economy_policy_instance_cap_exceeded")
        if not policy.active_from_tick <= due_tick <= policy.active_until_tick:
            return self._rejected_scheduled_transfer_open(command_id=command_id, error_code="economy_policy_instance_interval_mismatch")
        registration = self._active_scheduled_transfer_policy_registration(policy_instance_ref=policy_instance_ref)
        if registration is None:
            return self._rejected_scheduled_transfer_open(command_id=command_id, error_code="economy_policy_instance_missing")
        return policy, registration
    def _active_scheduled_transfer_policy_registration(self, *, policy_instance_ref: str) -> GameplayEvent | None:
        for event in reversed(self._store.read_stream("gameplay:economy")):
            if event.payload.get("policy_instance_ref") != policy_instance_ref:
                continue
            if event.event_type == "gameplay.economy.scheduled_transfer_policy_revoked":
                return None
            if event.event_type == "gameplay.economy.scheduled_transfer_policy_registered":
                return event
        return None
    def _revalidate_scheduled_transfer_policy_snapshot(self, *, opening: GameplayEvent, obligation: ScheduledObligation) -> None:
        policy_instance_ref = opening.payload.get("policy_instance_ref")
        if policy_instance_ref is None:
            if obligation.policy_revision != "1":
                raise EconomyRuntimeError("economy_scheduled_transfer_obligation_invalid")
            return
        registration_event_id = _text(opening.payload, "policy_registration_event_id")
        registration_stream_revision = _nonnegative(opening.payload, "policy_registration_stream_revision")
        if (
            not isinstance(policy_instance_ref, str)
            or not policy_instance_ref
            or obligation.policy_revision != _text(opening.payload, "policy_revision")
            or f"policy_instance:{policy_instance_ref}" not in obligation.source_refs
            or f"policy_registration_event:{registration_event_id}" not in obligation.source_refs
        ):
            raise EconomyRuntimeError("economy_scheduled_transfer_obligation_invalid")
        try:
            registration = self._store.get_event(registration_event_id)
        except KeyError as exc:
            raise EconomyRuntimeError("economy_scheduled_transfer_obligation_invalid") from exc
        if (
            registration.event_type != "gameplay.economy.scheduled_transfer_policy_registered"
            or registration.visibility_policy != "authority_only"
            or registration.stream_revision != registration_stream_revision
            or registration.payload.get("policy_instance_ref") != policy_instance_ref
            or registration.payload.get("policy_revision") != obligation.policy_revision
            or registration.payload.get("debit_account_id") != opening.payload.get("debit_account_id")
            or registration.payload.get("credit_account_id") != opening.payload.get("credit_account_id")
            or _positive(registration.payload, "amount_cap") < _positive(opening.payload, "amount")
            or not _nonnegative(registration.payload, "active_from_tick") <= _nonnegative(opening.payload, "due_tick") <= _nonnegative(registration.payload, "active_until_tick")
        ):
            raise EconomyRuntimeError("economy_scheduled_transfer_obligation_invalid")
    def _rejected_scheduled_transfer_open(self, *, command_id: str, error_code: str) -> ScheduledTransferObligationResult:
        return ScheduledTransferObligationResult(
            committed=False,
            obligation=None,
            append_result=AppendBatchResult(
                committed=False,
                transaction_id=f"transaction:{command_id}",
                command_id=command_id,
                idempotency_status="rejected",
                failure=GameplayFailure(error_code=error_code, message=error_code, failed_stage="economy_policy_instance_admission"),
            ),
        )
    def _scheduled_transfer_policy_duplicate_result(self, *, command_id: str, idempotency_key: str, event_type: str, payload: dict[str, object]) -> AppendBatchResult | None:
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is None:
            return None
        if not existing.committed or len(existing.committed_event_ids) != 1:
            return self._rejected_append(command_id, "idempotency_key_reused")
        event = self._store.get_event(existing.committed_event_ids[0])
        if event.event_type != event_type or event.visibility_policy != "authority_only" or event.payload != payload:
            return self._rejected_append(command_id, "idempotency_key_reused")
        return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
    def _append_scheduled_transfer_policy_event(self, *, command_id: str, idempotency_key: str, causation_id: str, correlation_id: str, expected_revision: int, event_type: str, payload: dict[str, object], fragment_id: str, source_rule_ref: str, outbox_audience: str) -> AppendBatchResult:
        stream = "gameplay:economy"
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:economy-scheduled-transfer-policy@1",
                contract_kind="policy",
                owner_ref=self._PRINCIPAL,
                stream_ids=(stream,),
                event_types=(event_type,),
                projection_scope="authority_only",
            )
        except GovernedAuthorityContractError as exc:
            return self._rejected_append(command_id, str(exc))
        command = GameplayCommandEnvelope(
            command_id=command_id,
            command_type="gameplay.economy.scheduled_transfer_policy",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=None,
            project_ref=None,
            transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key,
            expected_revisions={stream: expected_revision},
            read_set_revisions={stream: expected_revision},
            causation_id=causation_id,
            correlation_id=correlation_id,
            source_ref=str(payload["policy_instance_ref"]),
            submitted_at="economy-policy-registration",
            pinned_revisions={"economy": expected_revision},
            payload={"stream_ref": stream, "event_type": event_type, "visibility_policy": "authority_only", **payload},
        )
        batch = SettlementPlan.from_command_envelope(command).to_atomic_event_batch()
        event = batch.events[0]
        fragment = OwnerAuthorizedFragment(
            fragment_id=fragment_id,
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref=source_rule_ref,
            expected_revisions={stream: expected_revision},
            read_set_revisions={stream: expected_revision},
            pinned_revisions={"economy": expected_revision},
            event_specs={stream: ((event.event_type, dict(event.payload)),)},
            event_visibility_policies={stream: ("authority_only",)},
        )
        batch = batch.model_copy(
            update={
                "owner_fragments": [fragment],
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}",
                        transaction_id=batch.transaction_id,
                        event_id=event.event_id,
                        global_sequence=0,
                        topic="economy.policy.scoped_projection",
                        audience=outbox_audience,
                        payload_projection={"policy_instance_ref": str(payload["policy_instance_ref"]), "event_type": event.event_type},
                    )
                ],
            },
            deep=True,
        )
        return self._store.append_batch(batch)
    @staticmethod
    def _expected_revision(current: int, supplied: int | None) -> int:
        if supplied is None:
            return current
        if isinstance(supplied, bool) or supplied < 0:
            raise EconomyRuntimeError("economy_account_revision_invalid")
        return supplied
    def _append_account_settlement(self, *, command_id:str, command_type:str, idempotency_key:str, causation_id:str, correlation_id:str, current_revision:int, supplied_revision:int|None, source_ref:str, event_specs:tuple[tuple[str,dict[str,object]],...])->AppendBatchResult:
        stream="gameplay:economy"
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if supplied_revision is None and existing is not None and existing.committed:
            expected_revision = existing.resulting_stream_revisions.get(stream, 0) - len(event_specs)
        else:
            expected_revision = self._expected_revision(current_revision, supplied_revision)
        command = GameplayCommandEnvelope(
            command_id=command_id,
            command_type=command_type,
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=None,
            project_ref=None,
            transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key,
            expected_revisions={stream: expected_revision},
            read_set_revisions={stream: expected_revision},
            causation_id=causation_id,
            correlation_id=correlation_id,
            source_ref=source_ref,
            submitted_at="economy-account-settlement",
            pinned_revisions={"economy": expected_revision},
            payload={
                "stream_ref": stream,
                "event_type": event_specs[0][0],
                "event_specs": [
                    {"event_type": event_type, "payload": {**payload, "visibility_policy": "authority_only"}}
                    for event_type, payload in event_specs
                ],
            },
        )
        batch = SettlementPlan.from_command_envelope(command).to_atomic_event_batch()
        batch = batch.model_copy(
            update={
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}",
                        transaction_id=batch.transaction_id,
                        event_id=event.event_id,
                        global_sequence=0,
                        topic="economy.account.scoped_projection",
                        audience="authority:economy",
                        payload_projection={"account_id": str(event.payload.get("account_id", "")), "event_type": event.event_type},
                    )
                    for event in batch.events
                ]
            },
            deep=True,
        )
        return self._store.append_batch(batch)
    @staticmethod
    def account_settlement_receipt_for(*, result: AppendBatchResult | None, privacy_scope: str) -> SettlementReceipt:
        if privacy_scope != "authority":
            raise EconomyRuntimeError("economy_account_receipt_scope_denied")
        if result is None:
            raise EconomyRuntimeError("economy_account_receipt_missing")
        return SettlementReceipt.from_append_result(
            result=result,
            audit_refs=(f"economy_transaction:{result.transaction_id}",),
        )
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

__all__=["Account","BudgetReservation","EconomyAuthorityService","EconomyProjection","EconomyProjector","EconomyRuntimeError","ScheduledAccountTransferPolicyInstance","TaxDue","TaxObligationResult"]
