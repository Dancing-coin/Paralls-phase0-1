"""Bounded Treasury collector-identity owner for INF-2AB.

The authority owns only the canonical collector account reference for a
jurisdiction/currency pair. Economy remains the sole ledger and payment writer.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Mapping, Sequence

from pydantic import ConfigDict, Field

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.governed_contract_catalog import (
    GovernedAuthorityContractCatalog,
    GovernedAuthorityContractError,
)
from app.gameplay.models import (
    AppendBatchResult,
    GameplayEvent,
    GameplayFailure,
    GameplayOutboxEntry,
    OwnerAuthorizedFragment,
    StrictGameplayModel,
)
from app.gameplay.settlement_plan import SettlementPlan
from app.gameplay.shared_contracts import GameplayCommandEnvelope, SettlementReceipt


class GovernmentTreasuryCollectorError(ValueError):
    pass


class TaxPaymentIntentV1(StrictGameplayModel):
    """The only agent-facing tax-payment input surface."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_ref: str = "capability:government-tax-payment@1"
    obligation_id: str = Field(min_length=1)
    command_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)


class TaxPaymentCompensationIntentV1(StrictGameplayModel):
    """Fixed compensation request; source and payment identities are pinned."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_ref: str = "capability:government-tax-payment@1"
    settled_payment_event_id: str = Field(min_length=1)
    reversal_source_event_id: str = Field(min_length=1)
    command_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)


@dataclass(frozen=True)
class CollectorAccountIdentity:
    jurisdiction_ref: str
    currency_ref: str
    collector_account_ref: str
    collector_owner_ref: str
    source_event_id: str
    stream_revision: int


@dataclass(frozen=True)
class TreasuryCollectorProjection:
    identities: Mapping[tuple[str, str], CollectorAccountIdentity]
    source_revision_vector: Mapping[str, int]


class TreasuryCollectorProjector:
    _EVENT = "gameplay.government_treasury.collector_account_admitted"

    def rebuild(
        self,
        events: Sequence[GameplayEvent],
        *,
        checkpoint: TreasuryCollectorProjection | None = None,
    ) -> TreasuryCollectorProjection:
        identities = dict(checkpoint.identities) if checkpoint is not None else {}
        revisions = dict(checkpoint.source_revision_vector) if checkpoint is not None else {}
        for event in sorted(events, key=lambda item: (item.global_sequence, item.event_id)):
            if not event.stream_id.startswith("gameplay:government_treasury:"):
                continue
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
            if event.event_type != self._EVENT:
                continue
            payload = event.payload
            jurisdiction_ref = _text(payload, "jurisdiction_ref")
            currency_ref = _text(payload, "currency_ref")
            key = (jurisdiction_ref, currency_ref)
            if key in identities:
                raise GovernmentTreasuryCollectorError("treasury_collector_identity_duplicate")
            identities[key] = CollectorAccountIdentity(
                jurisdiction_ref=jurisdiction_ref,
                currency_ref=currency_ref,
                collector_account_ref=_text(payload, "collector_account_ref"),
                collector_owner_ref=_text(payload, "collector_owner_ref"),
                source_event_id=event.event_id,
                stream_revision=event.stream_revision,
            )
        return TreasuryCollectorProjection(
            identities=MappingProxyType(dict(sorted(identities.items()))),
            source_revision_vector=MappingProxyType(dict(sorted(revisions.items()))),
        )


class GovernmentTreasuryCollectorAuthority:
    """The admitted owner of collector identity, and nothing else."""

    _PRINCIPAL = "actor_gameplay.government_treasury_collector"
    _EVENT = "gameplay.government_treasury.collector_account_admitted"
    _CONTRACT = "inf:government-treasury-collector@1"

    def __init__(self, *, store: GameplayEventStore) -> None:
        self._store = store
        self._projector = TreasuryCollectorProjector()

    @staticmethod
    def stream_for(*, jurisdiction_ref: str) -> str:
        if not isinstance(jurisdiction_ref, str) or not jurisdiction_ref:
            raise GovernmentTreasuryCollectorError("treasury_jurisdiction_invalid")
        return f"gameplay:government_treasury:{jurisdiction_ref}"

    @staticmethod
    def _rejected(command_id: str, error_code: str) -> AppendBatchResult:
        return AppendBatchResult(
            committed=False,
            transaction_id=f"transaction:{command_id}",
            command_id=command_id,
            idempotency_status="rejected",
            failure=GameplayFailure(
                error_code=error_code,
                message=error_code,
                failed_stage="government_treasury_collector_admission",
            ),
        )

    def admit_collector_account(
        self,
        *,
        command_id: str,
        jurisdiction_ref: str,
        currency_ref: str,
        collector_account_ref: str,
        collector_owner_ref: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        expected_revision: int | None = None,
    ) -> AppendBatchResult:
        """Admit one immutable canonical collector identity.

        This validates an existing Economy account but never debits, credits,
        or writes the Economy stream.
        """
        if not all(
            isinstance(value, str) and value
            for value in (
                command_id,
                jurisdiction_ref,
                currency_ref,
                collector_account_ref,
                collector_owner_ref,
                idempotency_key,
                causation_id,
                correlation_id,
            )
        ):
            return self._rejected(command_id, "treasury_collector_input_invalid")
        stream = self.stream_for(jurisdiction_ref=jurisdiction_ref)
        current_revision = self._store.get_stream_head(stream)
        if expected_revision is None:
            expected_revision = current_revision
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 0:
            return self._rejected(command_id, "treasury_collector_revision_invalid")
        request = {
            "command_id": command_id,
            "jurisdiction_ref": jurisdiction_ref,
            "currency_ref": currency_ref,
            "collector_account_ref": collector_account_ref,
            "collector_owner_ref": collector_owner_ref,
            "causation_id": causation_id,
            "correlation_id": correlation_id,
            "expected_revision": expected_revision,
        }
        request_digest = _digest(request)
        prior = self._store.get_idempotency_record(self._PRINCIPAL, idempotency_key)
        if prior is not None:
            if prior.payload_digest != request_digest:
                return self._rejected(command_id, "idempotency_key_reused")
            replay = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
            if replay is None:
                return self._rejected(command_id, "idempotency_record_missing_result")
            return replay.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
        if current_revision != expected_revision:
            return self._rejected(command_id, "revision_conflict")
        try:
            account_opened = next(
                event
                for event in reversed(self._store.read_stream("gameplay:economy"))
                if event.event_type == "gameplay.economy.account_opened"
                and event.payload.get("account_id") == collector_account_ref
            )
        except StopIteration:
            return self._rejected(command_id, "treasury_collector_account_missing")
        if (
            account_opened.visibility_policy != "authority_only"
            or account_opened.payload.get("owner_ref") != collector_owner_ref
            or account_opened.payload.get("currency_ref") != currency_ref
        ):
            return self._rejected(command_id, "treasury_collector_account_invalid")
        projection = self._projector.rebuild(self._store.read_events())
        if (jurisdiction_ref, currency_ref) in projection.identities:
            return self._rejected(command_id, "treasury_collector_identity_already_admitted")
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref=self._CONTRACT,
                contract_kind="settlement",
                owner_ref=self._PRINCIPAL,
                stream_ids=(stream,),
                event_types=(self._EVENT,),
                projection_scope="authority_only",
            )
        except GovernedAuthorityContractError as exc:
            return self._rejected(command_id, str(exc))
        payload = {
            "jurisdiction_ref": jurisdiction_ref,
            "currency_ref": currency_ref,
            "collector_account_ref": collector_account_ref,
            "collector_owner_ref": collector_owner_ref,
            "collector_account_opened_event_id": account_opened.event_id,
            "collector_account_opened_stream_revision": account_opened.stream_revision,
        }
        fragment = OwnerAuthorizedFragment(
            fragment_id=f"fragment:government-treasury:collector:{jurisdiction_ref}:{currency_ref}",
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref="government-treasury:collector-account-admission",
            expected_revisions={stream: expected_revision},
            read_set_revisions={"gameplay:economy": self._store.get_stream_head("gameplay:economy")},
            pinned_revisions={
                "treasury": expected_revision,
                "collector_account_opened": account_opened.stream_revision,
            },
            event_specs={stream: ((self._EVENT, payload),)},
            event_visibility_policies={stream: ("authority_only",)},
        )
        command = GameplayCommandEnvelope(
            command_id=command_id,
            command_type="gameplay.government_treasury.collector_account_admission",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=None,
            project_ref=None,
            transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key,
            expected_revisions={stream: expected_revision},
            read_set_revisions=dict(fragment.read_set_revisions),
            causation_id=causation_id,
            correlation_id=correlation_id,
            source_ref=account_opened.event_id,
            submitted_at="government-treasury-collector-admission",
            pinned_revisions=dict(fragment.pinned_revisions),
            payload={
                "stream_ref": stream,
                "event_type": self._EVENT,
                "event_specs": [{"event_type": self._EVENT, "payload": {**payload, "visibility_policy": "authority_only"}}],
            },
        )
        batch = SettlementPlan.from_command_envelope(command).to_atomic_event_batch().model_copy(
            update={
                "owner_fragments": [fragment],
                "idempotency_record": SettlementPlan.from_command_envelope(command).to_atomic_event_batch().idempotency_record.model_copy(
                    update={"payload_digest": request_digest}, deep=True
                ),
            },
            deep=True,
        )
        event = batch.events[0]
        batch = batch.model_copy(
            update={
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}",
                        transaction_id=batch.transaction_id,
                        event_id=event.event_id,
                        global_sequence=0,
                        topic="government_treasury.collector.scoped_projection",
                        audience="authority:government_treasury",
                        payload_projection={"jurisdiction_ref": jurisdiction_ref, "currency_ref": currency_ref, "event_type": event.event_type},
                    )
                ]
            },
            deep=True,
        )
        return self._store.append_batch(batch)

    def collector_identity_projection(
        self, *, scope: str, checkpoint_at: int | None = None
    ) -> TreasuryCollectorProjection:
        if scope != "authority":
            raise GovernmentTreasuryCollectorError("treasury_collector_projection_scope_denied")
        events = self._store.read_events()
        if checkpoint_at is None:
            return self._projector.rebuild(events)
        if checkpoint_at < 0:
            raise GovernmentTreasuryCollectorError("treasury_collector_checkpoint_invalid")
        checkpoint = self._projector.rebuild(
            [event for event in events if event.global_sequence <= checkpoint_at]
        )
        return self._projector.rebuild(
            [event for event in events if event.global_sequence > checkpoint_at], checkpoint=checkpoint
        )

    @staticmethod
    def collector_receipt_for(*, result: AppendBatchResult | None, scope: str) -> SettlementReceipt:
        if scope != "authority":
            raise GovernmentTreasuryCollectorError("treasury_collector_receipt_scope_denied")
        if result is None:
            raise GovernmentTreasuryCollectorError("treasury_collector_receipt_missing")
        return SettlementReceipt.from_append_result(
            result=result, audit_refs=(f"government_treasury_transaction:{result.transaction_id}",)
        )


def _text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise GovernmentTreasuryCollectorError("treasury_collector_event_invalid")
    return value


def _digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


__all__ = [
    "CollectorAccountIdentity",
    "GovernmentTreasuryCollectorAuthority",
    "GovernmentTreasuryCollectorError",
    "TaxPaymentCompensationIntentV1",
    "TaxPaymentIntentV1",
    "TreasuryCollectorProjection",
    "TreasuryCollectorProjector",
]
