"""Event-sourced simple-debt issuance and repayment authority."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Mapping, Sequence

from pydantic import ConfigDict, Field

from app.gameplay.economy_runtime import EconomyProjector
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog, GovernedAuthorityContractError
from app.gameplay.models import (
    AppendBatchResult,
    AtomicEventBatch,
    GameplayEvent,
    GameplayOutboxEntry,
    IdempotencyRecord,
    OwnerAuthorizedFragment,
    StrictGameplayModel,
)
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.shared_contracts import GameplayCommandEnvelope


class DebtRuntimeError(ValueError):
    pass


class DebtSettlementEventSpec(StrictGameplayModel):
    """Closed event proposal accepted only by the existing debt authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_type: str = Field(min_length=1)
    stream_id: str = Field(min_length=1)
    payload: dict[str, object] = Field(default_factory=dict)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)

    @classmethod
    def from_legacy(cls, event: Mapping[str, object], *, command_id: str) -> "DebtSettlementEventSpec":
        if (
            event.get("command_id") != command_id
            or event.get("visibility_policy") != "authority_only"
            or not isinstance(event.get("event_type"), str)
            or not isinstance(event.get("stream_id"), str)
            or not isinstance(event.get("payload"), dict)
            or not isinstance(event.get("causation_id"), str)
            or not isinstance(event.get("correlation_id"), str)
        ):
            raise DebtRuntimeError("debt_settlement_event_invalid")
        return cls(
            event_type=str(event["event_type"]),
            stream_id=str(event["stream_id"]),
            payload=dict(event["payload"]),
            causation_id=str(event["causation_id"]),
            correlation_id=str(event["correlation_id"]),
        )


@dataclass(frozen=True)
class DebtSettlementPlan:
    """The non-generic formal plan for existing simple-debt settlement rows."""

    command: GameplayCommandEnvelope
    event_specs: tuple[DebtSettlementEventSpec, ...]
    expected_revisions: Mapping[str, int]
    idempotency_digest: str

    _STREAMS = frozenset({"gameplay:economy", "gameplay:contracts", "gameplay:debt", "gameplay:commerce"})
    _EVENT_STREAMS = MappingProxyType(
        {
            "gameplay.economy.account_debited": "gameplay:economy",
            "gameplay.economy.account_credited": "gameplay:economy",
            "gameplay.contract.simple_debt_created": "gameplay:contracts",
            "gameplay.contract.simple_debt_fulfilled": "gameplay:contracts",
            "gameplay.contract.simple_debt_cancelled": "gameplay:contracts",
            "gameplay.contract.simple_debt_reopened": "gameplay:contracts",
            "gameplay.contract.simple_debt_cancellation_reversed": "gameplay:contracts",
            "gameplay.debt.claim_issued": "gameplay:debt",
            "gameplay.debt.claim_overdue": "gameplay:debt",
            "gameplay.debt.claim_defaulted": "gameplay:debt",
            "gameplay.debt.payment_applied": "gameplay:debt",
            "gameplay.debt.payment_corrected": "gameplay:debt",
            "gameplay.debt.claim_satisfied": "gameplay:debt",
            "gameplay.debt.claim_cancelled": "gameplay:debt",
            "gameplay.debt.claim_reopened": "gameplay:debt",
            "gameplay.debt.claim_cancellation_reversed": "gameplay:debt",
            "gameplay.commerce.debt_issued_settled": "gameplay:commerce",
            "gameplay.commerce.debt_payment_settled": "gameplay:commerce",
            "gameplay.commerce.debt_cancelled_settled": "gameplay:commerce",
            "gameplay.commerce.debt_payment_corrected_settled": "gameplay:commerce",
            "gameplay.commerce.debt_cancellation_reversed": "gameplay:commerce",
        }
    )

    def to_atomic_event_batch(self) -> AtomicEventBatch:
        if (
            self.command.command_type != "gameplay.debt.simple_settlement"
            or self.command.principal_ref != DebtAuthorityService._PRINCIPAL
            or not self.event_specs
            or set(self.expected_revisions) != self._STREAMS
            or self.command.expected_revisions != dict(self.expected_revisions)
            or self.command.read_set_revisions != dict(self.expected_revisions)
        ):
            raise DebtRuntimeError("debt_settlement_plan_invalid")
        if any(spec.stream_id not in self._STREAMS for spec in self.event_specs):
            raise DebtRuntimeError("debt_settlement_stream_invalid")
        if any(spec.event_type not in self._EVENT_STREAMS for spec in self.event_specs):
            raise DebtRuntimeError("debt_settlement_event_invalid")
        if any(self._EVENT_STREAMS[spec.event_type] != spec.stream_id for spec in self.event_specs):
            raise DebtRuntimeError("debt_settlement_stream_invalid")
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:simple-debt-settlement@1",
                contract_kind="settlement",
                owner_ref=DebtAuthorityService._PRINCIPAL,
                stream_ids=tuple(sorted(self.expected_revisions)),
                event_types=tuple(spec.event_type for spec in self.event_specs),
                projection_scope="authority_only",
            )
        except GovernedAuthorityContractError as exc:
            raise DebtRuntimeError(str(exc)) from exc
        if any(
            spec.causation_id != self.command.causation_id
            or spec.correlation_id != self.command.correlation_id
            for spec in self.event_specs
        ):
            raise DebtRuntimeError("debt_settlement_event_invalid")
        transaction_id = self.command.transaction_id or f"transaction:{self.command.command_id}"
        events = [
            GameplayEvent(
                event_id=f"event:{self.command.command_id}:debt:{index}",
                event_type=spec.event_type,
                schema_version=self.command.command_version,
                stream_id=spec.stream_id,
                stream_revision=0,
                global_sequence=0,
                transaction_id=transaction_id,
                command_id=self.command.command_id,
                causation_id=spec.causation_id,
                correlation_id=spec.correlation_id,
                visibility_policy="authority_only",
                payload=spec.payload,
            )
            for index, spec in enumerate(self.event_specs, start=1)
        ]
        fragments = [
            OwnerAuthorizedFragment(
                fragment_id=f"fragment:debt:settlement:{self.command.command_id}:{stream_id}",
                owner_principal_ref=DebtAuthorityService._PRINCIPAL,
                source_rule_ref="debt:simple-settlement",
                expected_revisions={stream_id: self.expected_revisions[stream_id]},
                read_set_revisions=dict(self.expected_revisions),
                pinned_revisions=dict(self.command.pinned_revisions),
                event_specs={
                    stream_id: tuple(
                        (spec.event_type, spec.payload)
                        for spec in self.event_specs
                        if spec.stream_id == stream_id
                    )
                },
                event_visibility_policies={
                    stream_id: tuple(
                        "authority_only"
                        for spec in self.event_specs
                        if spec.stream_id == stream_id
                    )
                },
            )
            for stream_id in self._STREAMS
            if any(spec.stream_id == stream_id for spec in self.event_specs)
        ]
        digest = _digest(
            {
                "command": self.command.model_dump(mode="json"),
                "event_specs": [spec.model_dump(mode="json") for spec in self.event_specs],
            }
        )
        return AtomicEventBatch(
            transaction_id=transaction_id,
            command_id=self.command.command_id,
            expected_stream_revisions=dict(self.expected_revisions),
            read_stream_revisions=dict(self.expected_revisions),
            pinned_revisions=dict(self.command.pinned_revisions),
            events=events,
            idempotency_record=IdempotencyRecord(
                principal_ref=DebtAuthorityService._PRINCIPAL,
                idempotency_key=self.command.idempotency_key,
                payload_digest=self.idempotency_digest,
            ),
            owner_fragments=fragments,
            outbox_entries=[
                GameplayOutboxEntry(
                    outbox_id=f"outbox:{event.event_id}",
                    transaction_id=transaction_id,
                    event_id=event.event_id,
                    global_sequence=0,
                    topic="world.debt.scoped_projection",
                    audience="authority",
                    payload_projection={"event_type": event.event_type, "stream_id": event.stream_id},
                )
                for event in events
            ],
            result_digest=digest,
        )


@dataclass(frozen=True)
class SimpleDebtContract:
    contract_id: str
    creditor_ref: str
    debtor_ref: str
    currency_ref: str
    status: str
    source_event_id: str


@dataclass(frozen=True)
class DebtClaim:
    debt_id: str
    contract_id: str
    creditor_ref: str
    debtor_ref: str
    currency_ref: str
    principal_amount: int
    outstanding_amount: int
    status: str
    source_event_id: str
    due_tick: int | None = None


@dataclass(frozen=True)
class DebtTransaction:
    record_id: str
    settlement_transaction_id: str
    kind: str
    debt_id: str
    amount: int
    source_event_id: str


@dataclass(frozen=True)
class DebtCancellation:
    record_id: str
    debt_id: str
    cancelled_outstanding_amount: int
    source_event_id: str


@dataclass(frozen=True)
class DebtProjection:
    contracts: Mapping[str, SimpleDebtContract]
    claims: Mapping[str, DebtClaim]
    transactions: Mapping[str, DebtTransaction]
    corrections: Mapping[str, str]
    cancellations: Mapping[str, DebtCancellation]
    cancellation_reversals: Mapping[str, str]
    source_revision_vector: Mapping[str, int]


class DebtProjector:
    _EVENT_TYPES = {
        "gameplay.contract.simple_debt_created",
        "gameplay.contract.simple_debt_fulfilled",
        "gameplay.contract.simple_debt_cancelled",
        "gameplay.contract.simple_debt_reopened",
        "gameplay.contract.simple_debt_cancellation_reversed",
        "gameplay.debt.claim_issued",
        "gameplay.debt.claim_overdue",
        "gameplay.debt.claim_defaulted",
        "gameplay.debt.payment_applied",
        "gameplay.debt.payment_corrected",
        "gameplay.debt.claim_satisfied",
        "gameplay.debt.claim_cancelled",
        "gameplay.debt.claim_reopened",
        "gameplay.debt.claim_cancellation_reversed",
        "gameplay.commerce.debt_issued_settled",
        "gameplay.commerce.debt_payment_settled",
        "gameplay.commerce.debt_cancelled_settled",
        "gameplay.commerce.debt_payment_corrected_settled",
        "gameplay.commerce.debt_cancellation_reversed",
    }

    def rebuild(self, events: Sequence[GameplayEvent]) -> DebtProjection:
        contracts: dict[str, SimpleDebtContract] = {}
        claims: dict[str, DebtClaim] = {}
        transactions: dict[str, DebtTransaction] = {}
        corrections: dict[str, str] = {}
        cancellations: dict[str, DebtCancellation] = {}
        cancellation_reversals: dict[str, str] = {}
        revisions: dict[str, int] = {}
        for event in sorted(events, key=lambda value: (value.global_sequence, value.event_id)):
            if event.event_type not in self._EVENT_TYPES:
                continue
            payload = event.payload
            if event.event_type == "gameplay.contract.simple_debt_created":
                contract_id = _text(payload, "contract_id")
                if contract_id in contracts:
                    raise DebtRuntimeError("economy_contract_duplicate")
                contracts[contract_id] = SimpleDebtContract(
                    contract_id=contract_id,
                    creditor_ref=_text(payload, "creditor_ref"),
                    debtor_ref=_text(payload, "debtor_ref"),
                    currency_ref=_text(payload, "currency_ref"),
                    status="active",
                    source_event_id=event.event_id,
                )
            elif event.event_type in {"gameplay.contract.simple_debt_fulfilled", "gameplay.contract.simple_debt_cancelled"}:
                contract_id = _text(payload, "contract_id")
                contract = contracts.get(contract_id)
                if contract is None or contract.status != "active":
                    raise DebtRuntimeError("economy_contract_invalid")
                status = "fulfilled" if event.event_type.endswith("fulfilled") else "cancelled"
                contracts[contract_id] = SimpleDebtContract(**{**contract.__dict__, "status": status, "source_event_id": event.event_id})
            elif event.event_type == "gameplay.contract.simple_debt_reopened":
                contract_id = _text(payload, "contract_id")
                contract = contracts.get(contract_id)
                if contract is None or contract.status != "fulfilled":
                    raise DebtRuntimeError("economy_contract_invalid")
                _text(payload, "authority_ref")
                _text(payload, "reason")
                contracts[contract_id] = SimpleDebtContract(**{**contract.__dict__, "status": "active", "source_event_id": event.event_id})
            elif event.event_type == "gameplay.contract.simple_debt_cancellation_reversed":
                contract_id = _text(payload, "contract_id")
                contract = contracts.get(contract_id)
                if contract is None or contract.status != "cancelled":
                    raise DebtRuntimeError("economy_contract_invalid")
                _text(payload, "authority_ref")
                _text(payload, "reason")
                contracts[contract_id] = SimpleDebtContract(**{**contract.__dict__, "status": "active", "source_event_id": event.event_id})
            elif event.event_type == "gameplay.debt.claim_issued":
                debt_id = _text(payload, "debt_id")
                contract_id = _text(payload, "contract_id")
                contract = contracts.get(contract_id)
                principal_amount = _positive(payload, "principal_amount")
                if debt_id in claims or contract is None:
                    raise DebtRuntimeError("economy_debt_invalid")
                if contract.creditor_ref != _text(payload, "creditor_ref") or contract.debtor_ref != _text(payload, "debtor_ref") or contract.currency_ref != _text(payload, "currency_ref"):
                    raise DebtRuntimeError("economy_debt_contract_mismatch")
                due_tick = payload.get("due_tick")
                if due_tick is not None:
                    due_tick = _nonnegative(payload, "due_tick")
                claims[debt_id] = DebtClaim(
                    debt_id=debt_id,
                    contract_id=contract_id,
                    creditor_ref=contract.creditor_ref,
                    debtor_ref=contract.debtor_ref,
                    currency_ref=contract.currency_ref,
                    principal_amount=principal_amount,
                    outstanding_amount=principal_amount,
                    status="active",
                    source_event_id=event.event_id,
                    due_tick=due_tick,
                )
            elif event.event_type == "gameplay.debt.payment_applied":
                debt_id = _text(payload, "debt_id")
                claim = claims.get(debt_id)
                amount = _positive(payload, "amount")
                if claim is None or claim.status not in {"active", "overdue"} or amount > claim.outstanding_amount:
                    raise DebtRuntimeError("economy_payment_exceeds_outstanding")
                claims[debt_id] = DebtClaim(**{**claim.__dict__, "outstanding_amount": claim.outstanding_amount - amount, "source_event_id": event.event_id})
            elif event.event_type == "gameplay.debt.claim_overdue":
                debt_id = _text(payload, "debt_id")
                claim = claims.get(debt_id)
                due_tick = _nonnegative(payload, "due_tick")
                overdue_tick = _nonnegative(payload, "overdue_tick")
                if claim is None or claim.status != "active" or overdue_tick <= due_tick:
                    raise DebtRuntimeError("economy_debt_not_overdue")
                claims[debt_id] = DebtClaim(**{**claim.__dict__, "status": "overdue", "source_event_id": event.event_id})
            elif event.event_type == "gameplay.debt.claim_defaulted":
                debt_id = _text(payload, "debt_id")
                claim = claims.get(debt_id)
                due_tick = _nonnegative(payload, "due_tick")
                default_tick = _nonnegative(payload, "default_tick")
                if claim is None or claim.status != "overdue" or claim.due_tick != due_tick or default_tick <= due_tick:
                    raise DebtRuntimeError("economy_debt_default_invalid")
                claims[debt_id] = DebtClaim(**{**claim.__dict__, "status": "defaulted", "source_event_id": event.event_id})
            elif event.event_type == "gameplay.debt.payment_corrected":
                debt_id = _text(payload, "debt_id")
                original_payment_record_id = _text(payload, "original_payment_record_id")
                correction_record_id = _text(payload, "correction_record_id")
                claim = claims.get(debt_id)
                original = transactions.get(original_payment_record_id)
                amount = _positive(payload, "amount")
                if claim is None or claim.status != "active" or original is None or original.kind != "debt_payment" or original.debt_id != debt_id or original.amount != amount or original_payment_record_id in corrections:
                    raise DebtRuntimeError("economy_payment_already_corrected")
                _text(payload, "authority_ref")
                _text(payload, "reason")
                claims[debt_id] = DebtClaim(**{**claim.__dict__, "outstanding_amount": claim.outstanding_amount + amount, "source_event_id": event.event_id})
                corrections[original_payment_record_id] = correction_record_id
            elif event.event_type == "gameplay.debt.claim_satisfied":
                debt_id = _text(payload, "debt_id")
                claim = claims.get(debt_id)
                if claim is None or claim.status not in {"active", "overdue"} or claim.outstanding_amount != 0:
                    raise DebtRuntimeError("economy_debt_not_active")
                claims[debt_id] = DebtClaim(**{**claim.__dict__, "status": "satisfied", "source_event_id": event.event_id})
            elif event.event_type == "gameplay.debt.claim_reopened":
                debt_id = _text(payload, "debt_id")
                claim = claims.get(debt_id)
                if claim is None or claim.status != "satisfied" or claim.outstanding_amount != 0:
                    raise DebtRuntimeError("economy_debt_not_active")
                _text(payload, "authority_ref")
                _text(payload, "reason")
                claims[debt_id] = DebtClaim(**{**claim.__dict__, "status": "active", "source_event_id": event.event_id})
            elif event.event_type == "gameplay.debt.claim_cancellation_reversed":
                debt_id = _text(payload, "debt_id")
                original_cancellation_record_id = _text(payload, "original_cancellation_record_id")
                reversal_record_id = _text(payload, "reversal_record_id")
                claim = claims.get(debt_id)
                cancellation = cancellations.get(original_cancellation_record_id)
                amount = _positive(payload, "amount")
                if claim is None or claim.status != "cancelled" or cancellation is None or cancellation.debt_id != debt_id or cancellation.cancelled_outstanding_amount != amount or original_cancellation_record_id in cancellation_reversals:
                    raise DebtRuntimeError("economy_cancellation_already_reversed")
                _text(payload, "authority_ref")
                _text(payload, "reason")
                claims[debt_id] = DebtClaim(**{**claim.__dict__, "outstanding_amount": amount, "status": "active", "source_event_id": event.event_id})
                cancellation_reversals[original_cancellation_record_id] = reversal_record_id
            elif event.event_type == "gameplay.debt.claim_cancelled":
                debt_id = _text(payload, "debt_id")
                claim = claims.get(debt_id)
                if claim is None or claim.status not in {"active", "overdue"}:
                    raise DebtRuntimeError("economy_debt_not_active")
                _text(payload, "authority_ref")
                _text(payload, "reason")
                claims[debt_id] = DebtClaim(**{**claim.__dict__, "outstanding_amount": 0, "status": "cancelled", "source_event_id": event.event_id})
            else:
                record_id = _text(payload, "record_id")
                debt_id = _text(payload, "debt_id")
                if record_id in transactions or debt_id not in claims:
                    raise DebtRuntimeError("economy_transaction_invalid")
                if event.event_type == "gameplay.commerce.debt_issued_settled":
                    amount = _positive(payload, "principal_amount")
                    kind = "debt_issue"
                elif event.event_type == "gameplay.commerce.debt_payment_settled":
                    amount = _positive(payload, "amount")
                    kind = "debt_payment"
                elif event.event_type == "gameplay.commerce.debt_cancelled_settled":
                    amount = _nonnegative(payload, "amount")
                    if amount != 0:
                        raise DebtRuntimeError("economy_transaction_invalid")
                    kind = "debt_cancellation"
                    cancelled_outstanding_amount = _positive(payload, "cancelled_outstanding_amount")
                elif event.event_type == "gameplay.commerce.debt_cancellation_reversed":
                    amount = _positive(payload, "amount")
                    kind = "debt_cancellation_reversal"
                else:
                    amount = _positive(payload, "amount")
                    kind = "debt_payment_correction"
                transactions[record_id] = DebtTransaction(
                    record_id=record_id,
                    settlement_transaction_id=event.transaction_id,
                    kind=kind,
                    debt_id=debt_id,
                    amount=amount,
                    source_event_id=event.event_id,
                )
                if event.event_type == "gameplay.commerce.debt_cancelled_settled":
                    cancellations[record_id] = DebtCancellation(
                        record_id=record_id,
                        debt_id=debt_id,
                        cancelled_outstanding_amount=cancelled_outstanding_amount,
                        source_event_id=event.event_id,
                    )
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
        return DebtProjection(
            contracts=MappingProxyType(dict(sorted(contracts.items()))),
            claims=MappingProxyType(dict(sorted(claims.items()))),
            transactions=MappingProxyType(dict(sorted(transactions.items()))),
            corrections=MappingProxyType(dict(sorted(corrections.items()))),
            cancellations=MappingProxyType(dict(sorted(cancellations.items()))),
            cancellation_reversals=MappingProxyType(dict(sorted(cancellation_reversals.items()))),
            source_revision_vector=MappingProxyType(dict(sorted(revisions.items()))),
        )


class DebtAuthorityService:
    """Owns simple-debt settlement; accounts remain an event-derived projection."""

    _PRINCIPAL = "actor_gameplay.debt_domain"
    _ECONOMY_STREAM = "gameplay:economy"
    _CONTRACT_STREAM = "gameplay:contracts"
    _DEBT_STREAM = "gameplay:debt"
    _COMMERCE_STREAM = "gameplay:commerce"

    def __init__(self, *, store: GameplayEventStore) -> None:
        self._store = store
        self._economy_projector = EconomyProjector()
        self._debt_projector = DebtProjector()

    def replay_projection(self, *, checkpoint_at: int | None = None):
        """Replay the fixed simple-debt owner surface from the canonical event store."""
        replay = GameplayProjectionReplay(
            projector_id="infra-simple-debt-settlement", projector_version="1"
        )
        events = self._store.read_events()
        if checkpoint_at is None:
            return replay.full_replay(events)
        checkpoint = replay.create_checkpoint(events[:checkpoint_at])
        return replay.checkpoint_plus_tail_replay(checkpoint, events[checkpoint_at:])

    def issue_simple_debt(
        self,
        *,
        command_id: str,
        contract_id: str,
        debt_id: str,
        creditor_ref: str,
        debtor_ref: str,
        creditor_account_id: str,
        debtor_account_id: str,
        currency_ref: str,
        principal_amount: int,
        due_tick: int | None = None,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        command = {
            "kind": "issue_simple_debt",
            "command_id": command_id,
            "contract_id": contract_id,
            "debt_id": debt_id,
            "creditor_ref": creditor_ref,
            "debtor_ref": debtor_ref,
            "creditor_account_id": creditor_account_id,
            "debtor_account_id": debtor_account_id,
            "currency_ref": currency_ref,
            "principal_amount": principal_amount,
            "due_tick": due_tick,
        }
        digest = _digest(command)
        duplicate = self._duplicate(idempotency_key, digest)
        if duplicate is not None:
            return duplicate
        if not all((contract_id, debt_id, creditor_ref, debtor_ref, creditor_account_id, debtor_account_id, currency_ref)) or creditor_ref == debtor_ref or creditor_account_id == debtor_account_id or principal_amount <= 0 or (due_tick is not None and (isinstance(due_tick, bool) or due_tick < 0)):
            raise DebtRuntimeError("economy_debt_invalid")
        events = self._store.read_events()
        projection = self._debt_projector.rebuild(events)
        if contract_id in projection.contracts or debt_id in projection.claims:
            raise DebtRuntimeError("economy_debt_invalid")
        economy = self._economy_projector.rebuild(events)
        creditor = economy.accounts.get(creditor_account_id)
        debtor = economy.accounts.get(debtor_account_id)
        if creditor is None or debtor is None or creditor.owner_ref != creditor_ref or debtor.owner_ref != debtor_ref:
            raise DebtRuntimeError("economy_account_invalid")
        if creditor.currency_ref != currency_ref or debtor.currency_ref != currency_ref:
            raise DebtRuntimeError("economy_currency_mismatch")
        if creditor.balance < principal_amount:
            raise DebtRuntimeError("economy_insufficient_funds")
        transaction_id = f"tx:{command_id}"
        revisions = self._revisions()
        batch_events = [
            self._event(command_id, 1, "gameplay.economy.account_debited", self._ECONOMY_STREAM, transaction_id, causation_id, correlation_id, {"account_id": creditor_account_id, "amount": principal_amount}),
            self._event(command_id, 2, "gameplay.economy.account_credited", self._ECONOMY_STREAM, transaction_id, causation_id, correlation_id, {"account_id": debtor_account_id, "amount": principal_amount}),
            self._event(command_id, 3, "gameplay.contract.simple_debt_created", self._CONTRACT_STREAM, transaction_id, causation_id, correlation_id, {"contract_id": contract_id, "creditor_ref": creditor_ref, "debtor_ref": debtor_ref, "currency_ref": currency_ref}),
            self._event(command_id, 4, "gameplay.debt.claim_issued", self._DEBT_STREAM, transaction_id, causation_id, correlation_id, {"debt_id": debt_id, "contract_id": contract_id, "creditor_ref": creditor_ref, "debtor_ref": debtor_ref, "currency_ref": currency_ref, "principal_amount": principal_amount, **({"due_tick": due_tick} if due_tick is not None else {})}),
            self._event(command_id, 5, "gameplay.commerce.debt_issued_settled", self._COMMERCE_STREAM, transaction_id, causation_id, correlation_id, {"record_id": f"debt-issue:{command_id}", "debt_id": debt_id, "principal_amount": principal_amount}),
        ]
        return self._append(command_id, idempotency_key, digest, batch_events, revisions)

    def pay_debt(
        self,
        *,
        command_id: str,
        debt_id: str,
        debtor_account_id: str,
        creditor_account_id: str,
        amount: int,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        command = {
            "kind": "pay_debt",
            "command_id": command_id,
            "debt_id": debt_id,
            "debtor_account_id": debtor_account_id,
            "creditor_account_id": creditor_account_id,
            "amount": amount,
        }
        digest = _digest(command)
        duplicate = self._duplicate(idempotency_key, digest)
        if duplicate is not None:
            return duplicate
        events = self._store.read_events()
        projection = self._debt_projector.rebuild(events)
        claim = projection.claims.get(debt_id)
        if claim is None or claim.status not in {"active", "overdue"}:
            raise DebtRuntimeError("economy_debt_not_active")
        if amount <= 0 or amount > claim.outstanding_amount:
            raise DebtRuntimeError("economy_payment_exceeds_outstanding")
        contract = projection.contracts.get(claim.contract_id)
        if contract is None or contract.status != "active":
            raise DebtRuntimeError("economy_contract_invalid")
        economy = self._economy_projector.rebuild(events)
        debtor = economy.accounts.get(debtor_account_id)
        creditor = economy.accounts.get(creditor_account_id)
        if debtor is None or creditor is None or debtor.owner_ref != claim.debtor_ref or creditor.owner_ref != claim.creditor_ref:
            raise DebtRuntimeError("economy_account_invalid")
        if debtor.currency_ref != claim.currency_ref or creditor.currency_ref != claim.currency_ref:
            raise DebtRuntimeError("economy_currency_mismatch")
        if debtor.balance < amount:
            raise DebtRuntimeError("economy_insufficient_funds")
        transaction_id = f"tx:{command_id}"
        events_to_append = [
            self._event(command_id, 1, "gameplay.economy.account_debited", self._ECONOMY_STREAM, transaction_id, causation_id, correlation_id, {"account_id": debtor_account_id, "amount": amount}),
            self._event(command_id, 2, "gameplay.economy.account_credited", self._ECONOMY_STREAM, transaction_id, causation_id, correlation_id, {"account_id": creditor_account_id, "amount": amount}),
            self._event(command_id, 3, "gameplay.debt.payment_applied", self._DEBT_STREAM, transaction_id, causation_id, correlation_id, {"debt_id": debt_id, "amount": amount}),
        ]
        if amount == claim.outstanding_amount:
            events_to_append.extend(
                [
                    self._event(command_id, 4, "gameplay.debt.claim_satisfied", self._DEBT_STREAM, transaction_id, causation_id, correlation_id, {"debt_id": debt_id}),
                    self._event(command_id, 5, "gameplay.contract.simple_debt_fulfilled", self._CONTRACT_STREAM, transaction_id, causation_id, correlation_id, {"contract_id": claim.contract_id}),
                    self._event(command_id, 6, "gameplay.commerce.debt_payment_settled", self._COMMERCE_STREAM, transaction_id, causation_id, correlation_id, {"record_id": f"debt-payment:{command_id}", "debt_id": debt_id, "amount": amount}),
                ]
            )
        else:
            events_to_append.append(self._event(command_id, 4, "gameplay.commerce.debt_payment_settled", self._COMMERCE_STREAM, transaction_id, causation_id, correlation_id, {"record_id": f"debt-payment:{command_id}", "debt_id": debt_id, "amount": amount}))
        return self._append(command_id, idempotency_key, digest, events_to_append, self._revisions())

    def cancel_debt_by_policy(
        self,
        *,
        command_id: str,
        debt_id: str,
        authority_ref: str,
        reason: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        command = {
            "kind": "cancel_debt_by_policy",
            "command_id": command_id,
            "debt_id": debt_id,
            "authority_ref": authority_ref,
            "reason": reason,
        }
        digest = _digest(command)
        duplicate = self._duplicate(idempotency_key, digest)
        if duplicate is not None:
            return duplicate
        projection = self._debt_projector.rebuild(self._store.read_events())
        claim = projection.claims.get(debt_id)
        contract = projection.contracts.get(claim.contract_id) if claim is not None else None
        if claim is None or claim.status != "active" or contract is None or contract.status != "active":
            raise DebtRuntimeError("economy_debt_not_active")
        if not authority_ref or not reason:
            raise DebtRuntimeError("economy_debt_cancellation_invalid")
        transaction_id = f"tx:{command_id}"
        events = [
            self._event(command_id, 1, "gameplay.debt.claim_cancelled", self._DEBT_STREAM, transaction_id, causation_id, correlation_id, {"debt_id": debt_id, "authority_ref": authority_ref, "reason": reason}),
            self._event(command_id, 2, "gameplay.contract.simple_debt_cancelled", self._CONTRACT_STREAM, transaction_id, causation_id, correlation_id, {"contract_id": claim.contract_id, "authority_ref": authority_ref, "reason": reason}),
            self._event(command_id, 3, "gameplay.commerce.debt_cancelled_settled", self._COMMERCE_STREAM, transaction_id, causation_id, correlation_id, {"record_id": f"debt-cancel:{command_id}", "debt_id": debt_id, "amount": 0, "cancelled_outstanding_amount": claim.outstanding_amount, "authority_ref": authority_ref, "reason": reason}),
        ]
        return self._append(command_id, idempotency_key, digest, events, self._revisions())

    def mark_debt_overdue(
        self,
        *,
        command_id: str,
        debt_id: str,
        due_tick: int,
        overdue_tick: int,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        command = {
            "kind": "mark_debt_overdue",
            "command_id": command_id,
            "debt_id": debt_id,
            "due_tick": due_tick,
            "overdue_tick": overdue_tick,
        }
        digest = _digest(command)
        duplicate = self._duplicate(idempotency_key, digest)
        if duplicate is not None:
            return duplicate
        claim = self._debt_projector.rebuild(self._store.read_events()).claims.get(debt_id)
        if not debt_id or due_tick < 0 or overdue_tick <= due_tick or claim is None or claim.status != "active":
            raise DebtRuntimeError("economy_debt_not_overdue")
        if claim.due_tick is None or claim.due_tick != due_tick:
            raise DebtRuntimeError("economy_debt_due_tick_mismatch")
        event = self._event(
            command_id,
            1,
            "gameplay.debt.claim_overdue",
            self._DEBT_STREAM,
            f"tx:{command_id}",
            causation_id,
            correlation_id,
            {"debt_id": debt_id, "due_tick": due_tick, "overdue_tick": overdue_tick},
        )
        return self._append(command_id, idempotency_key, digest, [event], self._revisions())

    def mark_debt_default(
        self,
        *,
        command_id: str,
        debt_id: str,
        due_tick: int,
        default_tick: int,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        command = {
            "kind": "mark_debt_default",
            "command_id": command_id,
            "debt_id": debt_id,
            "due_tick": due_tick,
            "default_tick": default_tick,
        }
        digest = _digest(command)
        duplicate = self._duplicate(idempotency_key, digest)
        if duplicate is not None:
            return duplicate
        claim = self._debt_projector.rebuild(self._store.read_events()).claims.get(debt_id)
        if not debt_id or due_tick < 0 or default_tick <= due_tick or claim is None or claim.status != "overdue":
            raise DebtRuntimeError("economy_debt_default_invalid")
        if claim.due_tick is None or claim.due_tick != due_tick:
            raise DebtRuntimeError("economy_debt_due_tick_mismatch")
        event = self._event(
            command_id,
            1,
            "gameplay.debt.claim_defaulted",
            self._DEBT_STREAM,
            f"tx:{command_id}",
            causation_id,
            correlation_id,
            {"debt_id": debt_id, "due_tick": due_tick, "default_tick": default_tick},
        )
        return self._append(command_id, idempotency_key, digest, [event], self._revisions())

    def reverse_debt_cancellation_by_policy(
        self,
        *,
        command_id: str,
        debt_id: str,
        original_cancellation_record_id: str,
        authority_ref: str,
        reason: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        command = {
            "kind": "reverse_debt_cancellation_by_policy",
            "command_id": command_id,
            "debt_id": debt_id,
            "original_cancellation_record_id": original_cancellation_record_id,
            "authority_ref": authority_ref,
            "reason": reason,
        }
        digest = _digest(command)
        duplicate = self._duplicate(idempotency_key, digest)
        if duplicate is not None:
            return duplicate
        projection = self._debt_projector.rebuild(self._store.read_events())
        claim = projection.claims.get(debt_id)
        contract = projection.contracts.get(claim.contract_id) if claim is not None else None
        cancellation = projection.cancellations.get(original_cancellation_record_id)
        if claim is None or claim.status != "cancelled" or contract is None or contract.status != "cancelled" or cancellation is None or cancellation.debt_id != debt_id or original_cancellation_record_id in projection.cancellation_reversals:
            raise DebtRuntimeError("economy_cancellation_already_reversed")
        if not authority_ref or not reason:
            raise DebtRuntimeError("economy_debt_cancellation_reversal_invalid")
        reversal_record_id = f"debt-cancellation-reversal:{command_id}"
        transaction_id = f"tx:{command_id}"
        events = [
            self._event(command_id, 1, "gameplay.contract.simple_debt_cancellation_reversed", self._CONTRACT_STREAM, transaction_id, causation_id, correlation_id, {"contract_id": claim.contract_id, "original_cancellation_record_id": original_cancellation_record_id, "authority_ref": authority_ref, "reason": reason}),
            self._event(command_id, 2, "gameplay.debt.claim_cancellation_reversed", self._DEBT_STREAM, transaction_id, causation_id, correlation_id, {"debt_id": debt_id, "original_cancellation_record_id": original_cancellation_record_id, "reversal_record_id": reversal_record_id, "amount": cancellation.cancelled_outstanding_amount, "authority_ref": authority_ref, "reason": reason}),
            self._event(command_id, 3, "gameplay.commerce.debt_cancellation_reversed", self._COMMERCE_STREAM, transaction_id, causation_id, correlation_id, {"record_id": reversal_record_id, "debt_id": debt_id, "original_cancellation_record_id": original_cancellation_record_id, "amount": cancellation.cancelled_outstanding_amount, "authority_ref": authority_ref, "reason": reason}),
        ]
        return self._append(command_id, idempotency_key, digest, events, self._revisions())

    def correct_debt_payment_by_policy(
        self,
        *,
        command_id: str,
        debt_id: str,
        original_payment_record_id: str,
        debtor_account_id: str,
        creditor_account_id: str,
        authority_ref: str,
        reason: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        command = {
            "kind": "correct_debt_payment_by_policy",
            "command_id": command_id,
            "debt_id": debt_id,
            "original_payment_record_id": original_payment_record_id,
            "debtor_account_id": debtor_account_id,
            "creditor_account_id": creditor_account_id,
            "authority_ref": authority_ref,
            "reason": reason,
        }
        digest = _digest(command)
        duplicate = self._duplicate(idempotency_key, digest)
        if duplicate is not None:
            return duplicate
        projection = self._debt_projector.rebuild(self._store.read_events())
        claim = projection.claims.get(debt_id)
        original = projection.transactions.get(original_payment_record_id)
        contract = projection.contracts.get(claim.contract_id) if claim is not None else None
        if claim is None or original is None or original.kind != "debt_payment" or original.debt_id != debt_id or original_payment_record_id in projection.corrections:
            raise DebtRuntimeError("economy_payment_already_corrected")
        if claim.status == "active":
            if contract is None or contract.status != "active":
                raise DebtRuntimeError("economy_contract_invalid")
        elif claim.status == "satisfied":
            if contract is None or contract.status != "fulfilled":
                raise DebtRuntimeError("economy_contract_invalid")
        else:
            raise DebtRuntimeError("economy_debt_not_active")
        if not authority_ref or not reason:
            raise DebtRuntimeError("economy_debt_correction_invalid")
        economy = self._economy_projector.rebuild(self._store.read_events())
        debtor = economy.accounts.get(debtor_account_id)
        creditor = economy.accounts.get(creditor_account_id)
        if debtor is None or creditor is None or debtor.owner_ref != claim.debtor_ref or creditor.owner_ref != claim.creditor_ref:
            raise DebtRuntimeError("economy_account_invalid")
        if debtor.currency_ref != claim.currency_ref or creditor.currency_ref != claim.currency_ref:
            raise DebtRuntimeError("economy_currency_mismatch")
        if creditor.balance < original.amount:
            raise DebtRuntimeError("economy_insufficient_funds")
        transaction_id = f"tx:{command_id}"
        correction_record_id = f"debt-correction:{command_id}"
        events = [
            self._event(command_id, 1, "gameplay.economy.account_debited", self._ECONOMY_STREAM, transaction_id, causation_id, correlation_id, {"account_id": creditor_account_id, "amount": original.amount}),
            self._event(command_id, 2, "gameplay.economy.account_credited", self._ECONOMY_STREAM, transaction_id, causation_id, correlation_id, {"account_id": debtor_account_id, "amount": original.amount}),
        ]
        next_sequence = 3
        if claim.status == "satisfied":
            events.extend(
                [
                    self._event(command_id, next_sequence, "gameplay.contract.simple_debt_reopened", self._CONTRACT_STREAM, transaction_id, causation_id, correlation_id, {"contract_id": claim.contract_id, "authority_ref": authority_ref, "reason": reason}),
                    self._event(command_id, next_sequence + 1, "gameplay.debt.claim_reopened", self._DEBT_STREAM, transaction_id, causation_id, correlation_id, {"debt_id": debt_id, "authority_ref": authority_ref, "reason": reason}),
                ]
            )
            next_sequence += 2
        events.extend(
            [
                self._event(command_id, next_sequence, "gameplay.debt.payment_corrected", self._DEBT_STREAM, transaction_id, causation_id, correlation_id, {"debt_id": debt_id, "original_payment_record_id": original_payment_record_id, "correction_record_id": correction_record_id, "amount": original.amount, "authority_ref": authority_ref, "reason": reason}),
                self._event(command_id, next_sequence + 1, "gameplay.commerce.debt_payment_corrected_settled", self._COMMERCE_STREAM, transaction_id, causation_id, correlation_id, {"record_id": correction_record_id, "debt_id": debt_id, "original_payment_record_id": original_payment_record_id, "amount": original.amount, "authority_ref": authority_ref, "reason": reason}),
            ]
        )
        return self._append(command_id, idempotency_key, digest, events, self._revisions())

    def _revisions(self) -> dict[str, int]:
        return {
            self._ECONOMY_STREAM: self._store.get_stream_head(self._ECONOMY_STREAM),
            self._CONTRACT_STREAM: self._store.get_stream_head(self._CONTRACT_STREAM),
            self._DEBT_STREAM: self._store.get_stream_head(self._DEBT_STREAM),
            self._COMMERCE_STREAM: self._store.get_stream_head(self._COMMERCE_STREAM),
        }

    def _append(self, command_id: str, idempotency_key: str, digest: str, events: list[dict[str, object]], revisions: Mapping[str, int]) -> AppendBatchResult:
        specs = tuple(
            DebtSettlementEventSpec.from_legacy(event, command_id=command_id)
            for event in events
        )
        if not specs:
            raise DebtRuntimeError("debt_settlement_events_required")
        command = GameplayCommandEnvelope(
            command_id=command_id,
            command_type="gameplay.debt.simple_settlement",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=None,
            project_ref=None,
            transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key,
            expected_revisions=dict(revisions),
            read_set_revisions=dict(revisions),
            causation_id=specs[0].causation_id,
            correlation_id=specs[0].correlation_id,
            source_ref="debt-simple-settlement",
            submitted_at="debt-settlement",
            pinned_revisions={f"debt_settlement:{stream}": revision for stream, revision in revisions.items()},
            payload={"settlement_kind": "simple_debt"},
        )
        batch = DebtSettlementPlan(
            command=command,
            event_specs=specs,
            expected_revisions=dict(revisions),
            idempotency_digest=digest,
        ).to_atomic_event_batch()
        return self._store.append_batch(batch)

    def _duplicate(self, idempotency_key: str, digest: str) -> AppendBatchResult | None:
        record = self._store.get_idempotency_record(self._PRINCIPAL, idempotency_key)
        if record is None:
            return None
        if record.payload_digest != digest:
            raise DebtRuntimeError("idempotency_key_reused")
        result = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if result is None:
            raise DebtRuntimeError("economy_idempotency_missing_result")
        return result.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)

    @staticmethod
    def _event(command_id: str, index: int, event_type: str, stream_id: str, transaction_id: str, causation_id: str, correlation_id: str, payload: Mapping[str, object]) -> dict[str, object]:
        return {
            "event_id": f"evt:{command_id}:debt:{index}",
            "event_type": event_type,
            "schema_version": 1,
            "stream_id": stream_id,
            "stream_revision": 0,
            "global_sequence": 0,
            "transaction_id": transaction_id,
            "command_id": command_id,
            "causation_id": causation_id,
            "correlation_id": correlation_id,
            "visibility_policy": "authority_only",
            "payload": dict(payload),
        }


def _text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise DebtRuntimeError("economy_event_payload_invalid")
    return value


def _nonnegative(payload: Mapping[str, object], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DebtRuntimeError("economy_event_payload_invalid")
    return value


def _positive(payload: Mapping[str, object], key: str) -> int:
    value = _nonnegative(payload, key)
    if value == 0:
        raise DebtRuntimeError("economy_event_payload_invalid")
    return value


def _digest(value: object) -> str:
    return sha256(json.dumps(value, default=lambda item: dict(item) if isinstance(item, Mapping) else item.__dict__, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


__all__ = ["DebtAuthorityService", "DebtClaim", "DebtProjection", "DebtProjector", "DebtRuntimeError", "DebtTransaction", "SimpleDebtContract"]
