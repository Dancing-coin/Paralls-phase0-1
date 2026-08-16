"""Bounded P4 commercial proposals and deterministic Economy-owned clearing.

This module deliberately stores no order book or inventory projection.  Quotes
and orders are caller supplied, versioned public proposals; clearing is pure;
and the only write here is an Economy-owned committed clearing receipt.
"""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.debt_runtime import DebtAuthorityService, DebtProjector, DebtRuntimeError
from app.gameplay.contract_runtime import ContractAuthorityService, ContractProjector, ContractTermsDefinition, ContractTermsRegistry
from app.gameplay.economy_runtime import EconomyAuthorityService, EconomyProjector
from app.gameplay.econ1_economy_runtime import EconomyAuthority as Econ1EconomyAuthority
from app.gameplay.inventory_runtime import (
    ContainerSpec,
    InventoryAuthorityService,
    InventoryDefinitionRegistry,
    ItemDefinition,
    InventoryProjector,
    InventoryRuntimeError,
)
from app.gameplay.models import AppendBatchResult, GameplayOutboxEntry, StrictGameplayModel
from app.gameplay.organization_government_runtime import GovernmentAuthority, OrganizationAuthority
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.settlement_plan import (
    OwnerAuthorizedFragment,
    build_multi_stream_atomic_event_batch,
    build_multi_stream_atomic_event_batch_from_fragments,
)
from app.gameplay.shared_contracts import (
    EffectProposal,
    GameplayCommandEnvelope,
    SettlementReceipt,
    SettlementPlan as SharedSettlementPlan,
)


def _digest(value: object) -> str:
    return "sha256:" + sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


class DynamicQuote(StrictGameplayModel):
    """A versioned public Economy offer, priced only in integer minor units."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    quote_ref: str = Field(min_length=1)
    issuer_ref: str = Field(min_length=1)
    item_ref: str = Field(min_length=1)
    quality_ref: str = Field(min_length=1)
    side: Literal["sell", "buy"]
    quantity_limit: int = Field(gt=0, strict=True)
    unit_price_minor: int = Field(gt=0, strict=True)
    currency_ref: str = Field(min_length=1)
    version: int = Field(ge=1, strict=True)
    valid_from_tick: int = Field(ge=0, strict=True)
    valid_until_tick: int = Field(ge=0, strict=True)
    policy_revision: str = Field(min_length=1)
    reservation_ref: str = Field(min_length=1)
    inventory_custody_ref: str = Field(default="custody:declared", min_length=1)
    capacity_reservation_ref: str = Field(default="capacity:declared", min_length=1)
    delivery_policy_ref: str = Field(default="policy:delivery:standard", min_length=1)
    cancellation_policy_ref: str = Field(default="policy:cancellation:standard", min_length=1)
    public_digest: str = Field(min_length=1)
    status: Literal["active", "cancelled"] = "active"

    @model_validator(mode="after")
    def validate_window(self) -> "DynamicQuote":
        if self.valid_until_tick < self.valid_from_tick:
            raise ValueError("quote_window_invalid")
        return self


class QuoteOrder(StrictGameplayModel):
    """A bounded buy intent.  It carries every external revision it relies on."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    order_ref: str = Field(min_length=1)
    issuer_ref: str = Field(min_length=1)
    item_ref: str = Field(min_length=1)
    quality_ref: str = Field(min_length=1)
    side: Literal["buy", "sell"]
    quantity: int = Field(gt=0, strict=True)
    limit_price_minor: int = Field(gt=0, strict=True)
    currency_ref: str = Field(min_length=1)
    created_tick: int = Field(ge=0, strict=True)
    valid_from_tick: int = Field(ge=0, strict=True)
    valid_until_tick: int = Field(ge=0, strict=True)
    policy_revision: str = Field(min_length=1)
    reservation_ref: str = Field(min_length=1)
    inventory_custody_ref: str = Field(default="custody:declared", min_length=1)
    capacity_reservation_ref: str = Field(default="capacity:declared", min_length=1)
    delivery_policy_ref: str = Field(default="policy:delivery:standard", min_length=1)
    cancellation_policy_ref: str = Field(default="policy:cancellation:standard", min_length=1)
    public_digest: str = Field(min_length=1)
    revision_vector: dict[str, int] = Field(min_length=1)
    status: Literal["active", "cancelled"] = "active"

    @model_validator(mode="after")
    def validate_order(self) -> "QuoteOrder":
        if self.valid_until_tick < self.valid_from_tick:
            raise ValueError("order_window_invalid")
        if any(not stream_id or isinstance(revision, bool) or revision < 0 for stream_id, revision in self.revision_vector.items()):
            raise ValueError("revision_vector_invalid")
        return self


class ClearingCandidate(StrictGameplayModel):
    """A fully pinned candidate, suitable only for authority revalidation."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    candidate_ref: str = Field(min_length=1)
    quote_ref: str = Field(min_length=1)
    quote_version: int = Field(ge=1, strict=True)
    quote_issuer_ref: str = Field(min_length=1)
    order_ref: str = Field(min_length=1)
    order_issuer_ref: str = Field(min_length=1)
    item_ref: str = Field(min_length=1)
    quality_ref: str = Field(min_length=1)
    side: Literal["sell_to_buy"]
    quantity: int = Field(gt=0, strict=True)
    unit_price_minor: int = Field(gt=0, strict=True)
    currency_ref: str = Field(min_length=1)
    valid_from_tick: int = Field(ge=0, strict=True)
    valid_until_tick: int = Field(ge=0, strict=True)
    policy_revision: str = Field(min_length=1)
    quote_reservation_ref: str = Field(min_length=1)
    order_reservation_ref: str = Field(min_length=1)
    quote_inventory_custody_ref: str = Field(min_length=1)
    order_inventory_custody_ref: str = Field(min_length=1)
    quote_capacity_reservation_ref: str = Field(min_length=1)
    order_capacity_reservation_ref: str = Field(min_length=1)
    quote_delivery_policy_ref: str = Field(min_length=1)
    quote_cancellation_policy_ref: str = Field(min_length=1)
    order_delivery_policy_ref: str = Field(min_length=1)
    order_cancellation_policy_ref: str = Field(min_length=1)
    quote_public_digest: str = Field(min_length=1)
    order_public_digest: str = Field(min_length=1)
    revision_vector: dict[str, int] = Field(min_length=1)

    @classmethod
    def from_match(cls, quote: DynamicQuote, order: QuoteOrder, *, quantity: int) -> "ClearingCandidate":
        return cls(
            candidate_ref=f"candidate:{quote.quote_ref}:{quote.version}:{order.order_ref}",
            quote_ref=quote.quote_ref,
            quote_version=quote.version,
            quote_issuer_ref=quote.issuer_ref,
            order_ref=order.order_ref,
            order_issuer_ref=order.issuer_ref,
            item_ref=quote.item_ref,
            quality_ref=quote.quality_ref,
            side="sell_to_buy",
            quantity=quantity,
            unit_price_minor=quote.unit_price_minor,
            currency_ref=quote.currency_ref,
            valid_from_tick=max(quote.valid_from_tick, order.valid_from_tick),
            valid_until_tick=min(quote.valid_until_tick, order.valid_until_tick),
            policy_revision=quote.policy_revision,
            quote_reservation_ref=quote.reservation_ref,
            order_reservation_ref=order.reservation_ref,
            quote_inventory_custody_ref=quote.inventory_custody_ref,
            order_inventory_custody_ref=order.inventory_custody_ref,
            quote_capacity_reservation_ref=quote.capacity_reservation_ref,
            order_capacity_reservation_ref=order.capacity_reservation_ref,
            quote_delivery_policy_ref=quote.delivery_policy_ref,
            quote_cancellation_policy_ref=quote.cancellation_policy_ref,
            order_delivery_policy_ref=order.delivery_policy_ref,
            order_cancellation_policy_ref=order.cancellation_policy_ref,
            quote_public_digest=quote.public_digest,
            order_public_digest=order.public_digest,
            revision_vector=dict(sorted(order.revision_vector.items())),
        )


class ClearingResult(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    candidates: tuple[ClearingCandidate, ...] = ()
    rejections: tuple[tuple[str, str], ...] = ()
    explanation_digest: str = Field(min_length=1)


class CommercialCommitOutcome(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    committed: bool
    receipt: AppendBatchResult | None = None
    error_code: str | None = None
    zero_write: bool
    revision_vector: dict[str, int] = Field(default_factory=dict)
    public_digest: str = Field(min_length=1)
    settlement_plan: SharedSettlementPlan | None = None


class LaborContractRef(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    contract_ref: str = Field(min_length=1)
    employing_organization_ref: str = Field(min_length=1)
    worker_ref: str = Field(pattern=r"^character:")
    wage_obligation_ref: str = Field(min_length=1)
    work_evidence_refs: tuple[str, ...] = Field(min_length=1)
    wage_amount_minor: int = Field(gt=0, strict=True)
    wage_policy_revision: str = Field(min_length=1)


class CommerceCommitment(StrictGameplayModel):
    """Cross-domain reference projection; it owns none of the referenced facts."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    commitment_ref: str = Field(min_length=1)
    quote_ref: str = Field(min_length=1)
    order_ref: str = Field(min_length=1)
    buyer_organization_ref: str = Field(min_length=1)
    seller_organization_ref: str = Field(min_length=1)
    account_obligation_refs: tuple[str, ...] = Field(min_length=1)
    inventory_custody_refs: tuple[str, ...] = Field(min_length=1)
    organization_grant_refs: tuple[str, ...] = Field(min_length=1)
    budget_reservation_refs: tuple[str, ...] = Field(min_length=1)
    capacity_reservation_refs: tuple[str, ...] = Field(min_length=1)
    delivery_window_ref: str = Field(min_length=1)
    quality_evidence_refs: tuple[str, ...] = Field(min_length=1)
    labor_contract: LaborContractRef | None = None
    policy_revision: str = Field(min_length=1)
    revision_vector: dict[str, int] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_commitment(self) -> "CommerceCommitment":
        if self.buyer_organization_ref == self.seller_organization_ref:
            raise ValueError("commerce_parties_must_differ")
        if any(not ref.startswith("grant:") for ref in self.organization_grant_refs):
            raise ValueError("organization_grant_ref_invalid")
        if any(not ref.startswith("reservation:") for ref in self.budget_reservation_refs):
            raise ValueError("budget_reservation_ref_invalid")
        if any(not ref.startswith("capacity:") for ref in self.capacity_reservation_refs):
            raise ValueError("capacity_reservation_ref_invalid")
        if any(isinstance(value, bool) or value < 0 for value in self.revision_vector.values()):
            raise ValueError("revision_vector_invalid")
        if self.labor_contract is not None and self.labor_contract.employing_organization_ref != self.buyer_organization_ref:
            raise ValueError("labor_contract_organization_mismatch")
        return self


class DeliveryResult(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    delivery_ref: str = Field(min_length=1)
    commitment_ref: str = Field(min_length=1)
    status: Literal["delivered", "rejected", "cancelled"]
    delivered_quantity: int = Field(ge=0, strict=True)
    quality_evidence_ref: str = Field(min_length=1)
    delivery_window_ref: str = Field(min_length=1)
    revision_vector: dict[str, int] = Field(min_length=1)
    reason: str | None = None


class CommercePrivacyView(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    scope: Literal["public", "organization"]
    commitment_ref: str
    buyer_organization_ref: str
    seller_organization_ref: str
    quote_ref: str
    order_ref: str
    policy_revision: str
    delivery_window_ref: str
    quality_evidence_refs: tuple[str, ...]
    account_obligation_refs: tuple[str, ...] = ()
    inventory_custody_refs: tuple[str, ...] = ()
    organization_grant_refs: tuple[str, ...] = ()
    budget_reservation_refs: tuple[str, ...] = ()
    capacity_reservation_refs: tuple[str, ...] = ()
    labor_contract_ref: str | None = None


class CommerceAuthority:
    """Builds one multi-owner settlement batch from already-owned references."""

    _PRINCIPAL = "actor_gameplay.commerce_authority"

    def __init__(
        self,
        *,
        store: GameplayEventStore,
        inventory_registry: InventoryDefinitionRegistry | None = None,
    ) -> None:
        self._store = store
        self._inventory_registry = inventory_registry or InventoryDefinitionRegistry()

    def accept_commitment(self, commitment: CommerceCommitment, *, idempotency_key: str) -> CommercialCommitOutcome:
        idempotency_digest = self._commitment_idempotency_digest(commitment)
        existing_record = self._store.get_idempotency_record(self._PRINCIPAL, idempotency_key)
        if existing_record is not None:
            if existing_record.payload_digest != idempotency_digest:
                return self._rejected_payload(commitment.commitment_ref, "idempotency_key_reused")
            duplicate = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
            if duplicate is None:
                return self._rejected_payload(commitment.commitment_ref, "idempotency_record_missing_result")
            return CommercialCommitOutcome(
                committed=duplicate.committed,
                receipt=duplicate.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True),
                zero_write=True,
                revision_vector=dict(duplicate.resulting_stream_revisions),
                public_digest=_digest(duplicate.model_dump(mode="json")),
            )
        required_streams = {
            self._organization_stream(commitment.buyer_organization_ref),
            self._organization_stream(commitment.seller_organization_ref),
            "gameplay:economy",
            self._inventory_stream(commitment.seller_organization_ref),
        }
        if commitment.labor_contract is not None:
            required_streams.add(f"gameplay:economy:wage:{commitment.labor_contract.worker_ref}")
            required_streams.add("gameplay:contracts")
        missing = required_streams - set(commitment.revision_vector)
        if missing:
            return self._rejected_payload(commitment.commitment_ref, "revision_vector_incomplete")
        if any(
            self._store.get_stream_head(stream_id) != expected_revision
            for stream_id, expected_revision in commitment.revision_vector.items()
        ):
            return self._rejected_payload(commitment.commitment_ref, "revision_conflict")
        if commitment.labor_contract is not None:
            labor = commitment.labor_contract
            contract = ContractProjector().rebuild(self._store.read_events()).contracts.get(labor.contract_ref)
            if (
                contract is None
                or contract.status != "active"
                or contract.contract_type != "simple_service"
                or labor.employing_organization_ref not in contract.party_refs
                or labor.worker_ref not in contract.party_refs
            ):
                return self._rejected_payload(commitment.commitment_ref, "labor_contract_missing_or_stale")
        try:
            organization = OrganizationAuthority(store=self._store)
            fragments: tuple[OwnerAuthorizedFragment, ...] = (
                organization.build_commerce_commitment_fragment(
                    organization_ref=commitment.buyer_organization_ref,
                    commitment_ref=commitment.commitment_ref,
                    counterparty_organization_ref=commitment.seller_organization_ref,
                    organization_grant_refs=commitment.organization_grant_refs,
                    budget_reservation_refs=commitment.budget_reservation_refs,
                    policy_revision=commitment.policy_revision,
                    expected_revision=commitment.revision_vector[self._organization_stream(commitment.buyer_organization_ref)],
                ),
                organization.build_commerce_commitment_fragment(
                    organization_ref=commitment.seller_organization_ref,
                    commitment_ref=commitment.commitment_ref,
                    counterparty_organization_ref=commitment.buyer_organization_ref,
                    organization_grant_refs=(),
                    budget_reservation_refs=(),
                    policy_revision=commitment.policy_revision,
                    expected_revision=commitment.revision_vector[self._organization_stream(commitment.seller_organization_ref)],
                ),
                EconomyAuthorityService(store=self._store).build_commerce_obligation_fragment(
                    commitment_ref=commitment.commitment_ref,
                    buyer_organization_ref=commitment.buyer_organization_ref,
                    account_obligation_refs=commitment.account_obligation_refs,
                    budget_reservation_refs=commitment.budget_reservation_refs,
                    policy_revision=commitment.policy_revision,
                    expected_revision=commitment.revision_vector["gameplay:economy"],
                ),
                InventoryAuthorityService(store=self._store, registry=self._inventory_registry).build_commerce_custody_fragment(
                    seller_actor_ref=commitment.seller_organization_ref,
                    commitment_ref=commitment.commitment_ref,
                    custody_refs=commitment.inventory_custody_refs,
                    capacity_reservation_refs=commitment.capacity_reservation_refs,
                    delivery_window_ref=commitment.delivery_window_ref,
                    expected_revision=commitment.revision_vector[self._inventory_stream(commitment.seller_organization_ref)],
                    policy_revision=commitment.policy_revision,
                ),
            )
            if commitment.labor_contract is not None:
                labor = commitment.labor_contract
                fragments += (
                    Econ1EconomyAuthority.build_commerce_wage_accrual_fragment(
                        commitment_ref=commitment.commitment_ref,
                        organization_ref=commitment.buyer_organization_ref,
                        worker_ref=labor.worker_ref,
                        wage_obligation_ref=labor.wage_obligation_ref,
                        work_evidence_refs=labor.work_evidence_refs,
                        wage_amount_minor=labor.wage_amount_minor,
                        wage_policy_revision=labor.wage_policy_revision,
                        expected_revision=commitment.revision_vector[f"gameplay:economy:wage:{labor.worker_ref}"],
                    ),
                )
        except Exception as exc:
            return self._rejected_payload(commitment.commitment_ref, str(exc))
        return self._commit_fragments(
            command_id=f"p4b:commit:{commitment.commitment_ref}",
            idempotency_key=idempotency_key,
            fragments=fragments,
            source_ref=commitment.commitment_ref,
            pinned=commitment.revision_vector,
            atomic_validation_revisions=commitment.revision_vector,
            idempotency_payload_digest=idempotency_digest,
        )

    def record_delivery(self, commitment: CommerceCommitment, delivery: DeliveryResult, *, idempotency_key: str) -> CommercialCommitOutcome:
        if delivery.commitment_ref != commitment.commitment_ref or delivery.delivery_window_ref != commitment.delivery_window_ref:
            return self._rejected_payload(commitment.commitment_ref, "delivery_reference_invalid")
        required_streams = {self._inventory_stream(commitment.seller_organization_ref), "gameplay:economy"}
        missing = required_streams - set(delivery.revision_vector)
        if missing:
            return self._rejected_payload(delivery.delivery_ref, "revision_vector_incomplete")
        recovery_obligation_ref = (
            None if delivery.status == "delivered"
            else f"obligation:commerce-recovery:{commitment.commitment_ref}:{delivery.delivery_ref}"
        )
        try:
            fragments = (
                InventoryAuthorityService(store=self._store, registry=self._inventory_registry).build_commerce_delivery_fragment(
                    seller_actor_ref=commitment.seller_organization_ref,
                    delivery_ref=delivery.delivery_ref,
                    commitment_ref=commitment.commitment_ref,
                    status=delivery.status,
                    delivered_quantity=delivery.delivered_quantity,
                    quality_evidence_ref=delivery.quality_evidence_ref,
                    delivery_window_ref=delivery.delivery_window_ref,
                    reason=delivery.reason,
                    expected_revision=delivery.revision_vector[self._inventory_stream(commitment.seller_organization_ref)],
                    policy_revision=commitment.policy_revision,
                ),
                EconomyAuthorityService.build_delivery_obligation_fragment(
                    delivery_ref=delivery.delivery_ref,
                    commitment_ref=commitment.commitment_ref,
                    status=delivery.status,
                    reason=delivery.reason,
                    recovery_obligation_ref=recovery_obligation_ref,
                    policy_revision=commitment.policy_revision,
                    expected_revision=delivery.revision_vector["gameplay:economy"],
                ),
            )
        except Exception as exc:
            return self._rejected_payload(delivery.delivery_ref, str(exc))
        return self._commit_fragments(
            command_id=f"p4b:delivery:{delivery.delivery_ref}",
            idempotency_key=idempotency_key,
            fragments=fragments,
            source_ref=delivery.delivery_ref,
            pinned={**commitment.revision_vector, **delivery.revision_vector},
        )

    def project_commitment(self, commitment: CommerceCommitment, *, scope: Literal["public", "organization"]) -> CommercePrivacyView:
        private = scope == "organization"
        return CommercePrivacyView(
            scope=scope,
            commitment_ref=commitment.commitment_ref,
            buyer_organization_ref=commitment.buyer_organization_ref,
            seller_organization_ref=commitment.seller_organization_ref,
            quote_ref=commitment.quote_ref,
            order_ref=commitment.order_ref,
            policy_revision=commitment.policy_revision,
            delivery_window_ref=commitment.delivery_window_ref,
            quality_evidence_refs=commitment.quality_evidence_refs,
            account_obligation_refs=commitment.account_obligation_refs if private else (),
            inventory_custody_refs=commitment.inventory_custody_refs if private else (),
            organization_grant_refs=commitment.organization_grant_refs if private else (),
            budget_reservation_refs=commitment.budget_reservation_refs if private else (),
            capacity_reservation_refs=commitment.capacity_reservation_refs if private else (),
            labor_contract_ref=commitment.labor_contract.contract_ref if private and commitment.labor_contract else None,
        )

    @staticmethod
    def commerce_settlement_receipt_for(*, result: AppendBatchResult | None, privacy_scope: str) -> SettlementReceipt:
        if privacy_scope != "authority":
            raise ValueError("commerce_settlement_receipt_scope_denied")
        if result is None:
            raise ValueError("commerce_settlement_receipt_missing")
        return SettlementReceipt.from_append_result(
            result=result,
            audit_refs=(f"commerce_transaction:{result.transaction_id}",),
        )

    @staticmethod
    def _commitment_idempotency_digest(commitment: CommerceCommitment) -> str:
        return _digest({"operation": "commerce_commitment", "commitment": commitment.model_dump(mode="json")})

    @staticmethod
    def _organization_stream(ref: str) -> str:
        return f"gameplay:organization:{ref}"

    @staticmethod
    def _inventory_stream(ref: str) -> str:
        return f"gameplay:inventory:{ref}"

    def _commit_fragments(
        self,
        *,
        command_id: str,
        idempotency_key: str,
        fragments: tuple[OwnerAuthorizedFragment, ...],
        source_ref: str,
        pinned: dict[str, int],
        atomic_validation_revisions: dict[str, int] | None = None,
        idempotency_payload_digest: str | None = None,
    ) -> CommercialCommitOutcome:
        expected = {stream: revision for fragment in fragments for stream, revision in fragment.expected_revisions.items()}
        for stream, revision in expected.items():
            actual = self._store.get_stream_head(stream)
            if actual != revision:
                return self._rejected_payload(source_ref, "revision_conflict")
        command = GameplayCommandEnvelope(
            command_id=command_id,
            command_type="gameplay.commerce.commit",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key,
            expected_revisions=expected,
            causation_id=f"causation:{source_ref}",
            correlation_id=f"correlation:{source_ref}",
            source_ref=source_ref,
            submitted_at="p4",
            pinned_revisions=pinned,
            payload={"event_streams": tuple(sorted(expected)), "owner_fragment_ids": tuple(fragment.fragment_id for fragment in fragments)},
        )
        plan = SharedSettlementPlan(
            plan_id=f"settlement:{command_id}",
            command_id=command_id,
            expected_revision_vector=dict(sorted({**pinned, **expected}.items())),
            proposals=tuple(EffectProposal(proposal_id=fragment.fragment_id, effect_ref=fragment.source_rule_ref, target_refs=tuple(sorted(fragment.expected_revisions)), source_rule_ref=fragment.source_rule_ref, pinned_revisions={**pinned, **fragment.pinned_revisions}) for fragment in fragments),
            event_mapping={
                stream: (specs[0][0] if len(specs) == 1 else tuple(event_type for event_type, _ in specs))
                for fragment in fragments
                for stream, specs in fragment.event_specs.items()
            },
            idempotency_key=idempotency_key,
            causation_id=command.causation_id,
            correlation_id=command.correlation_id,
        )
        batch = build_multi_stream_atomic_event_batch_from_fragments(
            command_id=command_id,
            idempotency_principal_ref=self._PRINCIPAL,
            idempotency_key=idempotency_key,
            causation_id=command.causation_id,
            correlation_id=command.correlation_id,
            fragments=fragments,
        )
        if atomic_validation_revisions is not None:
            batch = batch.model_copy(
                update={
                    "expected_stream_revisions": dict(
                        sorted({**batch.expected_stream_revisions, **atomic_validation_revisions}.items())
                    ),
                    "pinned_revisions": dict(
                        sorted({**batch.pinned_revisions, **atomic_validation_revisions}.items())
                    ),
                },
                deep=True,
            )
        if idempotency_payload_digest is not None:
            batch = batch.model_copy(
                update={
                    "idempotency_record": batch.idempotency_record.model_copy(
                        update={"payload_digest": idempotency_payload_digest},
                        deep=True,
                    ),
                    "outbox_entries": [
                        GameplayOutboxEntry(
                            outbox_id=f"outbox:{command_id}:{event.event_id}",
                            transaction_id=batch.transaction_id,
                            event_id=event.event_id,
                            global_sequence=0,
                            topic="commerce.commitment.settled",
                            audience="authority:commerce",
                            payload_projection={"commitment_ref": source_ref, "event_type": event.event_type},
                        )
                        for event in batch.events
                    ],
                },
                deep=True,
            )
        receipt = self._store.append_batch(batch)
        return CommercialCommitOutcome(committed=receipt.committed, receipt=receipt, error_code=receipt.failure.error_code if receipt.failure else None, zero_write=not receipt.committed, revision_vector=dict(receipt.resulting_stream_revisions), public_digest=_digest({"source_ref": source_ref, "receipt": receipt.model_dump(mode="json")}), settlement_plan=plan)

    @staticmethod
    def _rejected_payload(source_ref: str, error_code: str) -> CommercialCommitOutcome:
        return CommercialCommitOutcome(committed=False, error_code=error_code, zero_write=True, public_digest=_digest({"source_ref": source_ref, "error_code": error_code}))


class CommercialPolicy(StrictGameplayModel):
    """Government-owned policy facts; assessments and claims remain external owners."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    policy_ref: str = Field(min_length=1)
    jurisdiction_ref: str = Field(min_length=1)
    revision: int = Field(ge=1, strict=True)
    public_digest: str = Field(min_length=1)
    permit_class: str = Field(min_length=1)
    tax_rate_basis_points: int = Field(ge=0, le=10_000, strict=True)
    credit_limit_minor: int = Field(ge=0, strict=True)
    due_calendar_ref: str = Field(min_length=1)
    credit_grant_ref: str = Field(default="grant:commercial:bounded-credit", min_length=1)
    credit_grant_digest: str = Field(default="sha256:credit-grant:bounded", min_length=1)


class PermitApplication(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    application_ref: str = Field(min_length=1)
    organization_ref: str = Field(min_length=1)
    jurisdiction_ref: str = Field(min_length=1)
    permit_class: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = ()


class InspectionEvidence(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    inspection_ref: str = Field(min_length=1)
    organization_ref: str = Field(min_length=1)
    jurisdiction_ref: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    evidence_ref: str = Field(min_length=1)
    passed: bool


class BoundedCreditProposal(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    proposal_ref: str = Field(min_length=1)
    borrower_organization_ref: str = Field(min_length=1)
    creditor_ref: str = Field(min_length=1)
    jurisdiction_ref: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    amount_minor: int = Field(gt=0, strict=True)
    due_tick: int = Field(ge=0, strict=True)
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    credit_grant_ref: str = Field(default="grant:commercial:bounded-credit", min_length=1)
    credit_grant_digest: str = Field(default="sha256:credit-grant:bounded", min_length=1)


class GovernmentCreditAuthority:
    """Policy/permit/inspection gate with bounded debt and economy owner events."""

    _PRINCIPAL = "actor_gameplay.government_institution_adapter"

    def __init__(self, *, store: GameplayEventStore) -> None:
        self._store = store

    def decide_permit(self, policy: CommercialPolicy, application: PermitApplication, *, approved: bool, idempotency_key: str) -> CommercialCommitOutcome:
        error = self._policy_error(policy, application.jurisdiction_ref, application.policy_revision)
        if error is not None:
            return CommerceAuthority._rejected_payload(application.application_ref, error)
        if application.permit_class != policy.permit_class:
            return CommerceAuthority._rejected_payload(application.application_ref, "permit_class_mismatch")
        if approved and not application.evidence_refs:
            return CommerceAuthority._rejected_payload(application.application_ref, "permit_evidence_required")
        try:
            fragment = GovernmentAuthority(store=self._store).build_commercial_permit_fragment(
                application_ref=application.application_ref,
                organization_ref=application.organization_ref,
                permit_class=application.permit_class,
                policy_revision=policy.policy_ref,
                policy_digest=policy.public_digest,
                evidence_refs=application.evidence_refs,
                approved=approved,
            )
        except Exception as exc:
            return CommerceAuthority._rejected_payload(application.application_ref, str(exc))
        return self._commit_fragments(
            command_id=f"p4c:permit:{application.application_ref}",
            idempotency_key=idempotency_key,
            fragments=(fragment,),
            source_ref=application.application_ref,
            policy=policy,
        )

    def record_inspection(self, policy: CommercialPolicy, evidence: InspectionEvidence, *, idempotency_key: str) -> CommercialCommitOutcome:
        error = self._policy_error(policy, evidence.jurisdiction_ref, evidence.policy_revision)
        if error is not None:
            return CommerceAuthority._rejected_payload(evidence.inspection_ref, error)
        try:
            fragment = GovernmentAuthority(store=self._store).build_commercial_inspection_fragment(
                inspection_ref=evidence.inspection_ref,
                organization_ref=evidence.organization_ref,
                jurisdiction_ref=evidence.jurisdiction_ref,
                policy_revision=policy.policy_ref,
                policy_digest=policy.public_digest,
                evidence_ref=evidence.evidence_ref,
                passed=evidence.passed,
            )
        except Exception as exc:
            return CommerceAuthority._rejected_payload(evidence.inspection_ref, str(exc))
        return self._commit_fragments(
            command_id=f"p4c:inspection:{evidence.inspection_ref}",
            idempotency_key=idempotency_key,
            fragments=(fragment,),
            source_ref=evidence.inspection_ref,
            policy=policy,
        )

    def assess_tax(
        self,
        policy: CommercialPolicy,
        *,
        organization_ref: str,
        period_ref: str,
        taxable_amount_minor: int,
        evidence_refs: tuple[str, ...],
        idempotency_key: str,
    ) -> CommercialCommitOutcome:
        if taxable_amount_minor < 0:
            return CommerceAuthority._rejected_payload(period_ref, "taxable_amount_invalid")
        try:
            assessment = EconomyAuthorityService.assess_tax_due(
                taxable_amount_minor=taxable_amount_minor,
                tax_rate_basis_points=policy.tax_rate_basis_points,
                evidence_refs=evidence_refs,
            )
        except Exception as exc:
            return CommerceAuthority._rejected_payload(period_ref, str(exc))
        command_id = f"p4c:tax:{period_ref}:{organization_ref}"
        expected = {"gameplay:economy": self._store.get_stream_head("gameplay:economy")}
        source_digest = _digest({"taxable_amount_minor": taxable_amount_minor, "evidence_refs": evidence_refs, "policy_digest": policy.public_digest})
        plan = self._owner_plan(command_id=command_id, idempotency_key=idempotency_key, expected=expected, source_ref=period_ref, policy=policy, event_mapping={"gameplay:economy": "gameplay.economy.tax_due_recorded"})
        try:
            receipt = EconomyAuthorityService(store=self._store).record_tax_due(
                command_id=command_id, organization_ref=organization_ref, period_ref=period_ref,
                assessed_amount_minor=assessment, policy_revision=policy.policy_ref,
                policy_digest=policy.public_digest, due_calendar_ref=policy.due_calendar_ref,
                evidence_refs=evidence_refs, source_digest=source_digest,
                idempotency_key=idempotency_key, causation_id=f"causation:{period_ref}",
                correlation_id=f"correlation:{period_ref}",
            )
        except Exception as exc:
            return CommerceAuthority._rejected_payload(period_ref, str(exc))
        return self._owner_outcome(command_id=command_id, idempotency_key=idempotency_key, expected=expected, source_ref=period_ref, policy=policy, plan=plan, receipt=receipt)

    def validate_bounded_credit_proposal(self, policy: CommercialPolicy, proposal: BoundedCreditProposal) -> CommercialCommitOutcome:
        error = self._policy_error(policy, proposal.jurisdiction_ref, proposal.policy_revision)
        if error is not None:
            return CommerceAuthority._rejected_payload(proposal.proposal_ref, error)
        if proposal.amount_minor > policy.credit_limit_minor:
            return CommerceAuthority._rejected_payload(proposal.proposal_ref, "credit_limit_exceeded")
        if proposal.credit_grant_ref != policy.credit_grant_ref or proposal.credit_grant_digest != policy.credit_grant_digest:
            return CommerceAuthority._rejected_payload(proposal.proposal_ref, "credit_grant_stale")
        if any(not evidence_ref.startswith("evidence:") for evidence_ref in proposal.evidence_refs):
            return CommerceAuthority._rejected_payload(proposal.proposal_ref, "credit_evidence_invalid")
        return CommercialCommitOutcome(committed=False, error_code="credit_owner_parameters_required", zero_write=True, public_digest=_digest({"proposal_ref": proposal.proposal_ref, "validation": "valid"}))

    def issue_bounded_credit(
        self,
        policy: CommercialPolicy,
        proposal: BoundedCreditProposal,
        *,
        contract_id: str,
        debt_id: str,
        creditor_account_id: str,
        debtor_account_id: str,
        currency_ref: str,
        idempotency_key: str,
    ) -> CommercialCommitOutcome:
        """Delegate the monetary path to the existing Debt/Contract/Economy owner."""
        error = self._policy_error(policy, proposal.jurisdiction_ref, proposal.policy_revision)
        if error is not None:
            return CommerceAuthority._rejected_payload(proposal.proposal_ref, error)
        if proposal.amount_minor > policy.credit_limit_minor:
            return CommerceAuthority._rejected_payload(proposal.proposal_ref, "credit_limit_exceeded")
        validation = self.validate_bounded_credit_proposal(policy, proposal)
        if validation.error_code != "credit_owner_parameters_required":
            return validation
        expected = self._debt_expected_revisions()
        command_id = f"p4c:debt-issue:{proposal.proposal_ref}"
        plan = self._owner_plan(command_id=command_id, idempotency_key=idempotency_key, expected=expected, source_ref=proposal.proposal_ref, policy=policy, event_mapping={"gameplay:economy": ("gameplay.economy.account_debited", "gameplay.economy.account_credited"), "gameplay:contracts": "gameplay.contract.simple_debt_created", "gameplay:debt": "gameplay.debt.claim_issued", "gameplay:commerce": "gameplay.commerce.debt_issued_settled"})
        try:
            receipt = DebtAuthorityService(store=self._store).issue_simple_debt(
                command_id=command_id,
                contract_id=contract_id,
                debt_id=debt_id,
                creditor_ref=proposal.creditor_ref,
                debtor_ref=proposal.borrower_organization_ref,
                creditor_account_id=creditor_account_id,
                debtor_account_id=debtor_account_id,
                currency_ref=currency_ref,
                principal_amount=proposal.amount_minor,
                due_tick=proposal.due_tick,
                idempotency_key=idempotency_key,
                causation_id=f"causation:{proposal.proposal_ref}",
                correlation_id=f"correlation:{proposal.proposal_ref}",
            )
        except DebtRuntimeError as exc:
            return CommerceAuthority._rejected_payload(proposal.proposal_ref, str(exc))
        return self._owner_outcome(command_id=command_id, idempotency_key=idempotency_key, expected=expected, source_ref=proposal.proposal_ref, policy=policy, plan=plan, receipt=receipt)

    def repay_bounded_credit(
        self,
        *,
        debt_id: str,
        debtor_account_id: str,
        creditor_account_id: str,
        amount_minor: int,
        idempotency_key: str,
    ) -> CommercialCommitOutcome:
        expected = self._debt_expected_revisions()
        command_id = f"p4c:debt-repay:{debt_id}:{amount_minor}"
        claim = DebtProjector().rebuild(self._store.read_events()).claims.get(debt_id)
        debt_events: tuple[str, ...] = ("gameplay.debt.payment_applied", "gameplay.debt.claim_satisfied") if claim is not None and amount_minor == claim.outstanding_amount else ("gameplay.debt.payment_applied",)
        contract_events: tuple[str, ...] = ("gameplay.contract.simple_debt_fulfilled",) if claim is not None and amount_minor == claim.outstanding_amount else ()
        event_mapping: dict[str, str | tuple[str, ...]] = {"gameplay:economy": ("gameplay.economy.account_debited", "gameplay.economy.account_credited"), "gameplay:debt": debt_events, "gameplay:commerce": "gameplay.commerce.debt_payment_settled"}
        if contract_events:
            event_mapping["gameplay:contracts"] = contract_events
        plan = self._owner_plan(command_id=command_id, idempotency_key=idempotency_key, expected=expected, source_ref=debt_id, policy=None, event_mapping=event_mapping)
        try:
            receipt = DebtAuthorityService(store=self._store).pay_debt(
                command_id=command_id,
                debt_id=debt_id,
                debtor_account_id=debtor_account_id,
                creditor_account_id=creditor_account_id,
                amount=amount_minor,
                idempotency_key=idempotency_key,
                causation_id=f"causation:{debt_id}",
                correlation_id=f"correlation:{debt_id}",
            )
        except DebtRuntimeError as exc:
            return CommerceAuthority._rejected_payload(debt_id, str(exc))
        return self._owner_outcome(command_id=command_id, idempotency_key=idempotency_key, expected=expected, source_ref=debt_id, policy=None, plan=plan, receipt=receipt)

    def validate_credit_repayment_request(self, *, claim_ref: str, amount_minor: int) -> CommercialCommitOutcome:
        if not claim_ref or amount_minor <= 0:
            return CommerceAuthority._rejected_payload(claim_ref or "credit", "credit_repayment_invalid")
        return CommercialCommitOutcome(committed=False, error_code="credit_owner_parameters_required", zero_write=True, public_digest=_digest({"claim_ref": claim_ref, "validation": "valid"}))

    def mark_overdue_or_default(self, *, debt_id: str, due_tick: int, tick: int, idempotency_key: str, defaulted: bool = False) -> CommercialCommitOutcome:
        if not debt_id or tick <= due_tick:
            return CommerceAuthority._rejected_payload(debt_id or "credit", "credit_not_overdue")
        expected = self._debt_expected_revisions()
        command_id = f"p4c:default:{debt_id}:{tick}" if defaulted else f"p4c:overdue:{debt_id}:{tick}"
        event_mapping: dict[str, str | tuple[str, ...]] = {
            "gameplay:debt": "gameplay.debt.claim_defaulted" if defaulted else "gameplay.debt.claim_overdue"
        }
        plan = self._owner_plan(command_id=command_id, idempotency_key=idempotency_key, expected=expected, source_ref=debt_id, policy=None, event_mapping=event_mapping)
        try:
            debt = DebtAuthorityService(store=self._store)
            if defaulted:
                receipt = debt.mark_debt_default(
                    command_id=command_id, debt_id=debt_id, due_tick=due_tick,
                    default_tick=tick, idempotency_key=idempotency_key,
                    causation_id=f"causation:{debt_id}", correlation_id=f"correlation:{debt_id}",
                )
            else:
                receipt = debt.mark_debt_overdue(
                    command_id=command_id, debt_id=debt_id, due_tick=due_tick,
                    overdue_tick=tick, idempotency_key=idempotency_key,
                    causation_id=f"causation:{debt_id}", correlation_id=f"correlation:{debt_id}",
                )
        except DebtRuntimeError as exc:
            return CommerceAuthority._rejected_payload(debt_id, str(exc))
        return self._owner_outcome(command_id=command_id, idempotency_key=idempotency_key, expected=expected, source_ref=debt_id, policy=None, plan=plan, receipt=receipt)

    def project_policy(self, policy: CommercialPolicy, *, scope: Literal["public", "authority"] = "public") -> dict[str, object]:
        result: dict[str, object] = {
            "policy_ref": policy.policy_ref,
            "jurisdiction_ref": policy.jurisdiction_ref,
            "revision": policy.revision,
            "public_digest": policy.public_digest,
            "permit_class": policy.permit_class,
            "due_calendar_ref": policy.due_calendar_ref,
        }
        if scope == "authority":
            result.update({"tax_rate_basis_points": policy.tax_rate_basis_points, "credit_limit_minor": policy.credit_limit_minor})
        return result

    @staticmethod
    def _policy_error(policy: CommercialPolicy, jurisdiction_ref: str, policy_revision: str) -> str | None:
        if policy.jurisdiction_ref != jurisdiction_ref:
            return "jurisdiction_mismatch"
        if policy.policy_ref != policy_revision:
            return "policy_revision_stale"
        return None

    def _debt_expected_revisions(self) -> dict[str, int]:
        return {
            stream: self._store.get_stream_head(stream)
            for stream in ("gameplay:economy", "gameplay:contracts", "gameplay:debt", "gameplay:commerce")
        }

    def _owner_plan(
        self,
        *,
        command_id: str,
        idempotency_key: str,
        expected: dict[str, int],
        source_ref: str,
        policy: CommercialPolicy | None,
        event_mapping: dict[str, str | tuple[str, ...]],
    ) -> SharedSettlementPlan:
        pins = {"policy": policy.revision} if policy is not None else {}
        command = GameplayCommandEnvelope(
            command_id=command_id, command_type="gameplay.institution.owner_settlement",
            command_version=1, principal_ref=self._PRINCIPAL,
            transaction_id=f"transaction:{command_id}", idempotency_key=idempotency_key,
            expected_revisions=expected, causation_id=f"causation:{source_ref}",
            correlation_id=f"correlation:{source_ref}", source_ref=source_ref,
            submitted_at="p4", pinned_revisions=pins,
            payload={"event_streams": tuple(sorted(event_mapping))},
        )
        return SharedSettlementPlan(
            plan_id=f"settlement:{command_id}", command_id=command_id,
            expected_revision_vector=expected,
            proposals=tuple(
                EffectProposal(
                    proposal_id=f"proposal:{stream}",
                    effect_ref=(event_types[0] if isinstance(event_types, tuple) else event_types),
                    target_refs=(stream,), source_rule_ref="p4:institution-owner",
                    pinned_revisions=pins,
                )
                for stream, event_types in sorted(event_mapping.items())
            ),
            event_mapping=event_mapping, idempotency_key=idempotency_key,
            causation_id=command.causation_id, correlation_id=command.correlation_id,
        )

    def _owner_outcome(
        self,
        *,
        command_id: str,
        idempotency_key: str,
        expected: dict[str, int],
        source_ref: str,
        policy: CommercialPolicy | None,
        plan: SharedSettlementPlan,
        receipt: AppendBatchResult,
    ) -> CommercialCommitOutcome:
        return CommercialCommitOutcome(
            committed=receipt.committed, receipt=receipt,
            error_code=receipt.failure.error_code if receipt.failure else None,
            zero_write=not receipt.committed,
            revision_vector=dict(receipt.resulting_stream_revisions),
            public_digest=_digest({"source_ref": source_ref, "receipt": receipt.model_dump(mode="json")}),
            settlement_plan=plan,
        )

    def _commit_fragments(
        self,
        *,
        command_id: str,
        idempotency_key: str,
        fragments: tuple[OwnerAuthorizedFragment, ...],
        source_ref: str,
        policy: CommercialPolicy | None,
    ) -> CommercialCommitOutcome:
        duplicate = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if duplicate is not None:
            return CommercialCommitOutcome(committed=True, receipt=duplicate.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True), zero_write=True, revision_vector=dict(duplicate.resulting_stream_revisions), public_digest=_digest(duplicate.model_dump(mode="json")))
        expected = {stream: revision for fragment in fragments for stream, revision in fragment.expected_revisions.items()}
        command = GameplayCommandEnvelope(
            command_id=command_id, command_type="gameplay.institution.commit", command_version=1,
            principal_ref=self._PRINCIPAL, transaction_id=f"transaction:{command_id}", idempotency_key=idempotency_key,
            expected_revisions=expected, causation_id=f"causation:{source_ref}", correlation_id=f"correlation:{source_ref}", source_ref=source_ref,
            submitted_at="p4", pinned_revisions={"policy": policy.revision} if policy else {}, payload={"event_streams": tuple(sorted(expected)), "owner_fragment_ids": tuple(fragment.fragment_id for fragment in fragments)},
        )
        plan = SharedSettlementPlan(
            plan_id=f"settlement:{command_id}", command_id=command_id, expected_revision_vector=expected,
            proposals=tuple(EffectProposal(proposal_id=fragment.fragment_id, effect_ref=fragment.source_rule_ref, target_refs=tuple(sorted(fragment.expected_revisions)), source_rule_ref=fragment.source_rule_ref, pinned_revisions={**command.pinned_revisions, **fragment.pinned_revisions}) for fragment in fragments),
            event_mapping={stream: (specs[0][0] if len(specs) == 1 else tuple(event_type for event_type, _ in specs)) for fragment in fragments for stream, specs in fragment.event_specs.items()}, idempotency_key=idempotency_key,
            causation_id=command.causation_id, correlation_id=command.correlation_id,
        )
        batch = build_multi_stream_atomic_event_batch_from_fragments(command_id=command_id, idempotency_principal_ref=self._PRINCIPAL, idempotency_key=idempotency_key, causation_id=command.causation_id, correlation_id=command.correlation_id, fragments=fragments)
        receipt = self._store.append_batch(batch)
        return CommercialCommitOutcome(committed=receipt.committed, receipt=receipt, error_code=receipt.failure.error_code if receipt.failure else None, zero_write=not receipt.committed, revision_vector=dict(receipt.resulting_stream_revisions), public_digest=_digest({"source_ref": source_ref, "receipt": receipt.model_dump(mode="json")}), settlement_plan=plan)


class CommercialEcosystemResult(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    competition: CommercialCommitOutcome
    customer_demand: CommercialCommitOutcome
    procurement: CommercialCommitOutcome
    delivery: CommercialCommitOutcome
    permit: CommercialCommitOutcome
    inspection: CommercialCommitOutcome
    tax: CommercialCommitOutcome
    credit: CommercialCommitOutcome
    default: CommercialCommitOutcome
    structured_reject: CommercialCommitOutcome
    replay_hash: str = Field(min_length=1)
    checkpoint_tail_hash: str = Field(min_length=1)
    event_log_digest: str = Field(min_length=1)
    public_view: dict[str, object]
    no_new_owner_audit: dict[str, bool]


class CommercialEcosystemScenario:
    """P4D reference composition; it creates no owner beyond the existing store."""

    def run(self) -> CommercialEcosystemResult:
        store = GameplayEventStore()
        accounts = EconomyAuthorityService(store=store)
        accounts.open_account(command_id="p4d:landlord-account", account_id="account:landlord-service", owner_ref="organization:landlord-service", currency_ref="currency:local", initial_balance=100, idempotency_key="p4d:landlord-account", causation_id="cause:p4d", correlation_id="corr:p4d")
        accounts.open_account(command_id="p4d:bakery-a-account", account_id="account:bakery-a", owner_ref="organization:bakery-a", currency_ref="currency:local", initial_balance=100, idempotency_key="p4d:bakery-a-account", causation_id="cause:p4d", correlation_id="corr:p4d")
        accounts.open_account(command_id="p4d:bakery-b-account", account_id="account:bakery-b", owner_ref="organization:bakery-b", currency_ref="currency:local", initial_balance=100, idempotency_key="p4d:bakery-b-account", causation_id="cause:p4d", correlation_id="corr:p4d")
        accounts.open_account(command_id="p4d:customer-account", account_id="account:customer", owner_ref="organization:customer", currency_ref="currency:local", initial_balance=30, idempotency_key="p4d:customer-account", causation_id="cause:p4d", correlation_id="corr:p4d")
        registry = InventoryDefinitionRegistry()
        registry.register_item(ItemDefinition("item:flour", "v1", 1, 1))
        registry.register_item(ItemDefinition("item:bread", "v1", 1, 1))
        inventory = InventoryAuthorityService(store=store, registry=registry)
        inventory.create_container(command_id="p4d:supplier-container", actor_ref="organization:supplier", spec=ContainerSpec("container:supplier", 100, 100, 10), idempotency_key="p4d:supplier-container", causation_id="cause:p4d", correlation_id="corr:p4d")
        inventory.instantiate(command_id="p4d:supplier-flour", actor_ref="organization:supplier", item_id="item:flour:supplier-lot", definition_id="item:flour", quantity=6, container_id="container:supplier", idempotency_key="p4d:supplier-flour", causation_id="cause:p4d", correlation_id="corr:p4d")
        inventory.reserve_item(command_id="p4d:supplier-flour-reservation", actor_ref="organization:supplier", item_id="item:flour:supplier-lot", reservation_ref="reservation:supplier:flour", quantity=6, idempotency_key="p4d:supplier-flour-reservation", causation_id="cause:p4d", correlation_id="corr:p4d")
        inventory.reserve_commerce_capacity(command_id="p4d:supplier-capacity", actor_ref="organization:supplier", capacity_reservation_ref="capacity:supplier:delivery", available_quantity=6, idempotency_key="p4d:supplier-capacity", causation_id="cause:p4d", correlation_id="corr:p4d")
        inventory.reserve_commerce_capacity(command_id="p4d:bakery-a-receiving", actor_ref="organization:bakery-a", capacity_reservation_ref="capacity:bakery-a:receive", available_quantity=4, idempotency_key="p4d:bakery-a-receiving", causation_id="cause:p4d", correlation_id="corr:p4d")
        inventory.reserve_commerce_capacity(command_id="p4d:bakery-b-receiving", actor_ref="organization:bakery-b", capacity_reservation_ref="capacity:bakery-b:receive", available_quantity=4, idempotency_key="p4d:bakery-b-receiving", causation_id="cause:p4d", correlation_id="corr:p4d")
        accounts.reserve_budget(command_id="p4d:bakery-a-budget", reservation_ref="reservation:bakery-a:budget", account_id="account:bakery-a", amount_minor=32, idempotency_key="p4d:bakery-a-budget", causation_id="cause:p4d", correlation_id="corr:p4d")
        accounts.reserve_budget(command_id="p4d:bakery-b-budget", reservation_ref="reservation:bakery-b:budget", account_id="account:bakery-b", amount_minor=32, idempotency_key="p4d:bakery-b-budget", causation_id="cause:p4d", correlation_id="corr:p4d")
        OrganizationAuthority(store=store).grant_commerce_budget(command_id="p4d:bakery-a-authorization", organization_ref="organization:bakery-a", grant_ref="grant:bakery-a:procurement", budget_reservation_ref="reservation:bakery-a:budget", amount_minor=32, policy_revision="policy:commerce:v1", idempotency_key="p4d:bakery-a-authorization", causation_id="cause:p4d", correlation_id="corr:p4d")
        contract_terms = ContractTermsRegistry()
        contract_terms.register(ContractTermsDefinition("terms:bakery-a:counter", "simple_service", 2, "service-completed"))
        ContractAuthorityService(store=store, terms_registry=contract_terms, policy_authorities={"actor_gameplay.organization_domain"}).create_contract(command_id="p4d:counter-contract", contract_id="contract:bakery-a:counter", contract_type="simple_service", terms_ref="terms:bakery-a:counter", party_refs=("organization:bakery-a", "character:char-c"), idempotency_key="p4d:counter-contract", causation_id="cause:p4d", correlation_id="corr:p4d")
        quote = DynamicQuote(
            quote_ref="quote:supplier:flour:v1", issuer_ref="organization:supplier", item_ref="item:flour",
            quality_ref="quality:standard", side="sell", quantity_limit=6, unit_price_minor=7,
            currency_ref="currency:local", version=1, valid_from_tick=1, valid_until_tick=10,
            policy_revision="policy:commerce:v1", reservation_ref="reservation:supplier:flour",
            inventory_custody_ref="custody:supplier:flour", capacity_reservation_ref="capacity:supplier:delivery",
            delivery_policy_ref="policy:delivery:standard", cancellation_policy_ref="policy:cancel:standard",
            public_digest="sha256:quote:supplier:flour:v1",
        )
        orders = (
            QuoteOrder(order_ref="order:bakery-a:flour", issuer_ref="organization:bakery-a", item_ref="item:flour", quality_ref="quality:standard", side="buy", quantity=4, limit_price_minor=8, currency_ref="currency:local", created_tick=1, valid_from_tick=1, valid_until_tick=10, policy_revision="policy:commerce:v1", reservation_ref="reservation:bakery-a:budget", inventory_custody_ref="custody:bakery-a:incoming", capacity_reservation_ref="capacity:bakery-a:receive", delivery_policy_ref="policy:delivery:standard", cancellation_policy_ref="policy:cancel:standard", public_digest="sha256:order:bakery-a:flour", revision_vector={"gameplay:economy": 9, "gameplay:inventory:organization:supplier": 5, "gameplay:inventory:organization:bakery-a": 1}),
            QuoteOrder(order_ref="order:bakery-b:flour", issuer_ref="organization:bakery-b", item_ref="item:flour", quality_ref="quality:standard", side="buy", quantity=4, limit_price_minor=8, currency_ref="currency:local", created_tick=2, valid_from_tick=1, valid_until_tick=10, policy_revision="policy:commerce:v1", reservation_ref="reservation:bakery-b:budget", inventory_custody_ref="custody:bakery-b:incoming", capacity_reservation_ref="capacity:bakery-b:receive", delivery_policy_ref="policy:delivery:standard", cancellation_policy_ref="policy:cancel:standard", public_digest="sha256:order:bakery-b:flour", revision_vector={"gameplay:economy": 9, "gameplay:inventory:organization:supplier": 5, "gameplay:inventory:organization:bakery-b": 1}),
        )
        accounts.publish_dynamic_quote(command_id="p4d:supplier-quote", quote_payload=quote.model_dump(mode="json"), idempotency_key="p4d:supplier-quote", causation_id="cause:p4d", correlation_id="corr:p4d")
        accounts.submit_dynamic_order(command_id="p4d:bakery-a-order", order_payload=orders[0].model_dump(mode="json"), idempotency_key="p4d:bakery-a-order", causation_id="cause:p4d", correlation_id="corr:p4d")
        accounts.submit_dynamic_order(command_id="p4d:bakery-b-order", order_payload=orders[1].model_dump(mode="json"), idempotency_key="p4d:bakery-b-order", causation_id="cause:p4d", correlation_id="corr:p4d")
        proposal = DeterministicClearing().clear(quotes=(quote,), orders=orders, tick=2)
        candidate = proposal.candidates[0]
        economy = DynamicCommerceAuthority(store=store, inventory_registry=registry)
        bakery_b_candidate = next((item for item in proposal.candidates if item.order_ref == orders[1].order_ref), None)
        if bakery_b_candidate is None or (orders[1].order_ref, "quantity_exhausted") not in proposal.rejections:
            raise RuntimeError("p4d_competition_not_quantity_exhausted")
        try:
            bakery_b_quote, bakery_b_order, bakery_b_quantities = economy._resolve_current_owner_facts(bakery_b_candidate)
        except (ValueError, InventoryRuntimeError) as exc:
            raise RuntimeError("p4d_bakery_b_owner_fact_missing") from exc
        if economy._owner_fact_error(bakery_b_candidate, bakery_b_quote, bakery_b_order, bakery_b_quantities, 2) is not None:
            raise RuntimeError("p4d_bakery_b_owner_fact_invalid")
        competition = economy.commit_candidate(
            candidate,
            tick=2,
            idempotency_key="p4d:competition",
        )
        inventory.create_container(command_id="p4d:bakery-a-container", actor_ref="organization:bakery-a", spec=ContainerSpec("container:bakery-a", 100, 100, 10), idempotency_key="p4d:bakery-a-container", causation_id="cause:p4d", correlation_id="corr:p4d")
        inventory.instantiate(command_id="p4d:bakery-a-bread", actor_ref="organization:bakery-a", item_id="item:bread:bakery-a-lot", definition_id="item:bread", quantity=2, container_id="container:bakery-a", idempotency_key="p4d:bakery-a-bread", causation_id="cause:p4d", correlation_id="corr:p4d")
        inventory.reserve_item(command_id="p4d:bakery-a-bread-reservation", actor_ref="organization:bakery-a", item_id="item:bread:bakery-a-lot", reservation_ref="reservation:bakery-a:bread", quantity=2, idempotency_key="p4d:bakery-a-bread-reservation", causation_id="cause:p4d", correlation_id="corr:p4d")
        inventory.reserve_commerce_capacity(command_id="p4d:bakery-a-counter", actor_ref="organization:bakery-a", capacity_reservation_ref="capacity:bakery-a:counter", available_quantity=2, idempotency_key="p4d:bakery-a-counter", causation_id="cause:p4d", correlation_id="corr:p4d")
        inventory.reserve_commerce_capacity(command_id="p4d:customer-receiving", actor_ref="organization:customer", capacity_reservation_ref="capacity:customer:receipt", available_quantity=1, idempotency_key="p4d:customer-receiving", causation_id="cause:p4d", correlation_id="corr:p4d")
        accounts.reserve_budget(command_id="p4d:customer-budget", reservation_ref="reservation:customer:budget", account_id="account:customer", amount_minor=10, idempotency_key="p4d:customer-budget", causation_id="cause:p4d", correlation_id="corr:p4d")
        customer_quote = DynamicQuote(quote_ref="quote:bakery-a:bread:v1", issuer_ref="organization:bakery-a", item_ref="item:bread", quality_ref="quality:standard", side="sell", quantity_limit=2, unit_price_minor=9, currency_ref="currency:local", version=1, valid_from_tick=2, valid_until_tick=10, policy_revision="policy:commerce:v1", reservation_ref="reservation:bakery-a:bread", inventory_custody_ref="custody:bakery-a:bread", capacity_reservation_ref="capacity:bakery-a:counter", delivery_policy_ref="policy:delivery:standard", cancellation_policy_ref="policy:cancel:standard", public_digest="sha256:quote:bakery-a:bread:v1")
        customer_order = QuoteOrder(order_ref="order:customer:bread", issuer_ref="organization:customer", item_ref="item:bread", quality_ref="quality:standard", side="buy", quantity=1, limit_price_minor=10, currency_ref="currency:local", created_tick=2, valid_from_tick=2, valid_until_tick=10, policy_revision="policy:commerce:v1", reservation_ref="reservation:customer:budget", inventory_custody_ref="custody:customer:counter", capacity_reservation_ref="capacity:customer:receipt", delivery_policy_ref="policy:delivery:standard", cancellation_policy_ref="policy:cancel:standard", public_digest="sha256:order:customer:bread", revision_vector={"gameplay:economy": 13, "gameplay:inventory:organization:bakery-a": 6, "gameplay:inventory:organization:customer": 1})
        accounts.publish_dynamic_quote(command_id="p4d:bread-quote", quote_payload=customer_quote.model_dump(mode="json"), idempotency_key="p4d:bread-quote", causation_id="cause:p4d", correlation_id="corr:p4d")
        accounts.submit_dynamic_order(command_id="p4d:customer-order", order_payload=customer_order.model_dump(mode="json"), idempotency_key="p4d:customer-order", causation_id="cause:p4d", correlation_id="corr:p4d")
        customer_candidate = DeterministicClearing().clear(quotes=(customer_quote,), orders=(customer_order,), tick=2).candidates[0]
        customer_demand = economy.commit_candidate(customer_candidate, tick=2, idempotency_key="p4d:customer-demand")
        commitment = CommerceCommitment(
            commitment_ref="commitment:bakery-a:flour", quote_ref=quote.quote_ref, order_ref=orders[0].order_ref,
            buyer_organization_ref="organization:bakery-a", seller_organization_ref="organization:supplier",
            account_obligation_refs=("obligation:bakery-a:flour",), inventory_custody_refs=(quote.reservation_ref,),
            organization_grant_refs=("grant:bakery-a:procurement",), budget_reservation_refs=("reservation:bakery-a:budget",), capacity_reservation_refs=("capacity:supplier:delivery",),
            delivery_window_ref="delivery:window:1", quality_evidence_refs=("evidence:quality:flour:standard",),
            labor_contract=LaborContractRef(contract_ref="contract:bakery-a:counter", employing_organization_ref="organization:bakery-a", worker_ref="character:char-c", wage_obligation_ref="obligation:wage:char-c", work_evidence_refs=("evidence:work:counter:1",), wage_amount_minor=5, wage_policy_revision="policy:wage:v1"),
            policy_revision=quote.policy_revision,
            revision_vector={"gameplay:organization:organization:bakery-a": 1, "gameplay:organization:organization:supplier": 0, "gameplay:economy": 14, "gameplay:inventory:organization:supplier": 5, "gameplay:economy:wage:character:char-c": 0, "gameplay:contracts": 1},
        )
        commerce = CommerceAuthority(store=store, inventory_registry=registry)
        procurement = commerce.accept_commitment(commitment, idempotency_key="p4d:procurement")
        delivery_revisions = {
            stream: store.get_stream_head(stream)
            for stream in ("gameplay:inventory:organization:supplier", "gameplay:economy")
        }
        delivery = commerce.record_delivery(commitment, DeliveryResult(delivery_ref="delivery:flour:1", commitment_ref=commitment.commitment_ref, status="delivered", delivered_quantity=4, quality_evidence_ref="evidence:quality:flour:standard", delivery_window_ref=commitment.delivery_window_ref, revision_vector=delivery_revisions), idempotency_key="p4d:delivery")
        policy = CommercialPolicy(policy_ref="policy:commerce:v1", jurisdiction_ref="jurisdiction:bakery-district", revision=1, public_digest="sha256:policy:commerce:v1", permit_class="permit:food-service", tax_rate_basis_points=500, credit_limit_minor=100, due_calendar_ref="calendar:monthly")
        institutions = GovernmentCreditAuthority(store=store)
        permit = institutions.decide_permit(policy, PermitApplication(application_ref="permit:bakery-a", organization_ref="organization:bakery-a", jurisdiction_ref=policy.jurisdiction_ref, permit_class=policy.permit_class, policy_revision=policy.policy_ref, evidence_refs=("evidence:permit:bakery-a",)), approved=True, idempotency_key="p4d:permit")
        inspection = institutions.record_inspection(policy, InspectionEvidence(inspection_ref="inspection:bakery-a", organization_ref="organization:bakery-a", jurisdiction_ref=policy.jurisdiction_ref, policy_revision=policy.policy_ref, evidence_ref="evidence:inspection:bakery-a", passed=True), idempotency_key="p4d:inspection")
        tax = institutions.assess_tax(policy, organization_ref="organization:bakery-a", period_ref="period:bakery-a:1", taxable_amount_minor=80, evidence_refs=("evidence:taxable:bakery-a:1",), idempotency_key="p4d:tax")
        credit_proposal = BoundedCreditProposal(proposal_ref="credit:bakery-a:landlord", borrower_organization_ref="organization:bakery-a", creditor_ref="organization:landlord-service", jurisdiction_ref=policy.jurisdiction_ref, policy_revision=policy.policy_ref, amount_minor=60, due_tick=8, evidence_refs=("evidence:period:bakery-a:1",))
        credit = institutions.issue_bounded_credit(policy, credit_proposal, contract_id="contract:credit:bakery-a:landlord", debt_id="debt:credit:bakery-a:landlord", creditor_account_id="account:landlord-service", debtor_account_id="account:bakery-a", currency_ref="currency:local", idempotency_key="p4d:credit")
        institutions.mark_overdue_or_default(debt_id="debt:credit:bakery-a:landlord", due_tick=8, tick=9, idempotency_key="p4d:overdue")
        default = institutions.mark_overdue_or_default(debt_id="debt:credit:bakery-a:landlord", due_tick=8, tick=10, defaulted=True, idempotency_key="p4d:default")
        structured_reject = economy.commit_candidate(
            candidate,
            tick=2,
            idempotency_key="p4d:stale-candidate",
        )
        events = store.read_events()
        event_payload = [event.model_dump(mode="json") for event in events]
        event_log_digest = _digest(event_payload)
        replay = GameplayProjectionReplay(projector_id="projection:p4d-commerce", projector_version="v1")
        full_replay = replay.full_replay(events)
        split_at = max(1, len(events) // 2)
        checkpoint = replay.create_checkpoint(events[:split_at])
        checkpoint_replay = replay.checkpoint_plus_tail_replay(checkpoint, events[split_at:])
        if not full_replay.succeeded or not checkpoint_replay.succeeded:
            raise RuntimeError("p4d_replay_failed")
        replay_hash = "sha256:" + full_replay.projection_hash
        checkpoint_tail_hash = "sha256:" + checkpoint_replay.projection_hash
        public_view = {"policy_digest": policy.public_digest, "quote_digest": quote.public_digest, "redaction": "account-and-custody-refs-excluded", "organizations": ("organization:bakery-a", "organization:bakery-b", "organization:supplier", "organization:customer", "organization:landlord-service", "organization:regulator"), "competition": {"winner_order_ref": candidate.order_ref, "bakery_b_owner_valid": True, "bakery_b_rejection": "quantity_exhausted"}}
        transactions = store.read_transactions()
        all_event_types = {event.event_type for event in events}
        canonical_streams = frozenset({
            "gameplay:economy",
            "gameplay:economy:wage:character:char-c",
            "gameplay:inventory:organization:supplier",
            "gameplay:inventory:organization:bakery-a",
            "gameplay:inventory:organization:bakery-b",
            "gameplay:inventory:organization:customer",
            "gameplay:organization:organization:bakery-a",
            "gameplay:organization:organization:supplier",
            "gameplay:government:organization:bakery-a",
            "gameplay:contracts",
            "gameplay:debt",
            "gameplay:commerce",
        })
        direct_owner_streams = {
            "actor_gameplay.organization_domain": frozenset({"gameplay:organization:organization:bakery-a", "gameplay:organization:organization:supplier"}),
            "actor_gameplay.contract_domain": frozenset({"gameplay:contracts"}),
            "actor_gameplay.economy_domain": frozenset({"gameplay:economy"}),
            "actor_gameplay.inventory_domain": frozenset({
                "gameplay:inventory:organization:supplier",
                "gameplay:inventory:organization:bakery-a",
                "gameplay:inventory:organization:bakery-b",
                "gameplay:inventory:organization:customer",
            }),
            "actor_gameplay.econ1_economy_domain": frozenset({"gameplay:economy:wage:character:char-c"}),
            "actor_gameplay.debt_domain": frozenset({"gameplay:economy", "gameplay:contracts", "gameplay:debt", "gameplay:commerce"}),
        }
        fragment_owner_streams = {
            "actor_gameplay.organization_domain": frozenset({"gameplay:organization:organization:bakery-a", "gameplay:organization:organization:supplier"}),
            "actor_gameplay.inventory_domain": direct_owner_streams["actor_gameplay.inventory_domain"],
            "actor_gameplay.economy_domain": frozenset({"gameplay:economy"}),
            "actor_gameplay.econ1_economy_domain": direct_owner_streams["actor_gameplay.econ1_economy_domain"],
            "actor_gameplay.government_domain": frozenset({"gameplay:government:organization:bakery-a"}),
        }
        adapter_principals = frozenset({"actor_gameplay.commerce_authority", "actor_gameplay.government_institution_adapter"})
        unknown_stream = any(event.stream_id not in canonical_streams for batch in transactions for event in batch.events)
        unknown_principal = False
        fragment_provenance_missing = False
        for batch in transactions:
            principal = batch.idempotency_record.principal_ref
            batch_streams = {event.stream_id for event in batch.events}
            if principal in adapter_principals:
                if not batch.owner_fragments:
                    fragment_provenance_missing = True
                    continue
                fragment_streams: set[str] = set()
                for fragment in batch.owner_fragments:
                    allowed = fragment_owner_streams.get(fragment.owner_principal_ref)
                    if allowed is None or not set(fragment.event_specs).issubset(allowed):
                        unknown_principal = True
                    fragment_streams.update(fragment.event_specs)
                if fragment_streams != batch_streams:
                    fragment_provenance_missing = True
            elif principal not in direct_owner_streams:
                unknown_principal = True
            elif not batch_streams.issubset(direct_owner_streams[principal]):
                unknown_principal = True
        no_new_owner_audit = {
            "market_runtime": any("market_runtime" in event_type or "order_book" in event_type for event_type in all_event_types),
            "global_scheduler": any("scheduler" in event_type or "global_clock" in event_type for event_type in all_event_types),
            "autonomous_organization_writer": any(
                batch.idempotency_record.principal_ref == "actor_gameplay.commerce_authority" and not batch.owner_fragments
                for batch in transactions
            ),
            "second_settlement_path": any(
                batch.idempotency_record.principal_ref in adapter_principals and not batch.owner_fragments
                for batch in transactions
            ),
            "unknown_canonical_stream": unknown_stream,
            "unknown_writer_principal": unknown_principal,
            "owner_fragment_provenance_missing": fragment_provenance_missing,
        }
        return CommercialEcosystemResult(
            competition=competition, customer_demand=customer_demand, procurement=procurement, delivery=delivery, permit=permit, inspection=inspection,
            tax=tax, credit=credit, default=default, structured_reject=structured_reject,
            replay_hash=replay_hash, checkpoint_tail_hash=checkpoint_tail_hash, event_log_digest=event_log_digest, public_view=public_view,
            no_new_owner_audit=no_new_owner_audit,
        )


class DeterministicClearing:
    """Pure price-time ordering with no random input or retained market state."""

    def clear(self, *, quotes: tuple[DynamicQuote, ...], orders: tuple[QuoteOrder, ...], tick: int) -> ClearingResult:
        current_quotes = self._current_quotes(quotes)
        active_quotes = [quote for quote in current_quotes if quote.side == "sell" and self._is_active(quote, tick)]
        active_orders = [order for order in orders if order.side == "buy" and self._is_active(order, tick)]
        rejected: list[tuple[str, str]] = []
        for order in sorted(orders, key=lambda item: item.order_ref):
            if order.status == "cancelled":
                rejected.append((order.order_ref, "order_cancelled"))
            elif not self._is_active(order, tick):
                rejected.append((order.order_ref, "order_expired"))
        for order in active_orders:
            eligible = [quote for quote in active_quotes if self._compatible(quote, order)]
            same_terms_different_policy = any(
                quote.item_ref == order.item_ref
                and quote.quality_ref == order.quality_ref
                and quote.currency_ref == order.currency_ref
                and quote.issuer_ref != order.issuer_ref
                and quote.policy_revision != order.policy_revision
                for quote in current_quotes
            )
            if not eligible and same_terms_different_policy:
                rejected.append((order.order_ref, "policy_revision_stale"))
            elif not eligible and any(quote.status == "cancelled" and self._compatible_identity(quote, order) for quote in current_quotes):
                rejected.append((order.order_ref, "quote_cancelled"))
            elif not eligible and any(not self._is_active(quote, tick) and self._compatible_identity(quote, order) for quote in current_quotes):
                rejected.append((order.order_ref, "quote_expired"))
        remaining_quote = {quote.quote_ref: quote.quantity_limit for quote in active_quotes}
        candidates: list[ClearingCandidate] = []
        for order in sorted(active_orders, key=lambda item: (-item.limit_price_minor, item.created_tick, item.order_ref)):
            remaining_order = order.quantity
            eligible = [quote for quote in active_quotes if self._compatible(quote, order) and quote.unit_price_minor <= order.limit_price_minor]
            if not eligible:
                continue
            for quote in sorted(active_quotes, key=lambda item: (item.unit_price_minor, item.issuer_ref, item.quote_ref)):
                if remaining_order == 0 or not self._compatible(quote, order) or quote.unit_price_minor > order.limit_price_minor:
                    continue
                quantity = min(remaining_order, remaining_quote[quote.quote_ref])
                if quantity == 0:
                    continue
                candidates.append(ClearingCandidate.from_match(quote, order, quantity=quantity))
                remaining_order -= quantity
                remaining_quote[quote.quote_ref] -= quantity
            if remaining_order:
                rejected.append((order.order_ref, "quantity_exhausted"))
        normalized_rejections = tuple(sorted(set(rejected), key=lambda item: item[0]))
        candidate_tuple = tuple(candidates)
        return ClearingResult(
            candidates=candidate_tuple,
            rejections=normalized_rejections,
            explanation_digest=_digest({"tick": tick, "candidates": [item.model_dump(mode="json") for item in candidate_tuple], "rejections": normalized_rejections}),
        )

    @staticmethod
    def _is_active(value: DynamicQuote | QuoteOrder, tick: int) -> bool:
        return value.status == "active" and value.valid_from_tick <= tick <= value.valid_until_tick

    @staticmethod
    def _current_quotes(quotes: tuple[DynamicQuote, ...]) -> tuple[DynamicQuote, ...]:
        """Keep only the immutable current version for each public quote ref."""
        current: dict[str, DynamicQuote] = {}
        for quote in sorted(quotes, key=lambda value: (value.quote_ref, value.version, value.public_digest)):
            prior = current.get(quote.quote_ref)
            if prior is None or quote.version > prior.version:
                current[quote.quote_ref] = quote
        return tuple(current[quote_ref] for quote_ref in sorted(current))

    @staticmethod
    def _compatible_identity(quote: DynamicQuote, order: QuoteOrder) -> bool:
        return (
            quote.item_ref == order.item_ref
            and quote.quality_ref == order.quality_ref
            and quote.currency_ref == order.currency_ref
            and quote.policy_revision == order.policy_revision
            and quote.delivery_policy_ref == order.delivery_policy_ref
            and quote.cancellation_policy_ref == order.cancellation_policy_ref
        )

    @classmethod
    def _compatible(cls, quote: DynamicQuote, order: QuoteOrder) -> bool:
        return cls._compatible_identity(quote, order) and quote.issuer_ref != order.issuer_ref


class DynamicCommerceAuthority:
    """Economy authority that revalidates a candidate before one append-batch write."""

    _PRINCIPAL = "actor_gameplay.economy_domain"

    def __init__(self, *, store: GameplayEventStore, inventory_registry: InventoryDefinitionRegistry) -> None:
        self._store = store
        self._inventory_registry = inventory_registry

    def commit_candidate(
        self,
        candidate: ClearingCandidate,
        *,
        tick: int,
        idempotency_key: str,
    ) -> CommercialCommitOutcome:
        duplicate = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if duplicate is not None:
            replayed = duplicate.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            return CommercialCommitOutcome(
                committed=replayed.committed,
                receipt=replayed,
                zero_write=True,
                revision_vector=dict(replayed.resulting_stream_revisions),
                public_digest=_digest({"candidate_ref": candidate.candidate_ref, "receipt": replayed.model_dump(mode="json")}),
            )
        error = self._candidate_error(candidate, tick)
        if error is not None:
            return self._rejected(candidate, error)
        try:
            quote, order, owner_quantities = self._resolve_current_owner_facts(candidate)
        except (ValueError, InventoryRuntimeError) as exc:
            return self._rejected(candidate, str(exc))
        error = self._owner_fact_error(candidate, quote, order, owner_quantities, tick)
        if error is not None:
            return self._rejected(candidate, error)
        for stream_id, expected_revision in candidate.revision_vector.items():
            if self._store.get_stream_head(stream_id) != expected_revision:
                return self._rejected(candidate, "revision_conflict")
        economy_stream = "gameplay:economy"
        expected_revisions = dict(candidate.revision_vector)
        expected_revisions[economy_stream] = self._store.get_stream_head(economy_stream)
        command = GameplayCommandEnvelope(
            command_id=f"p4a:clear:{candidate.candidate_ref}",
            command_type="gameplay.economy.clearing_revalidate",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            transaction_id=f"transaction:p4a:clear:{candidate.candidate_ref}",
            idempotency_key=idempotency_key,
            expected_revisions=dict(sorted(expected_revisions.items())),
            causation_id=f"causation:{candidate.candidate_ref}",
            correlation_id=f"correlation:{candidate.order_ref}",
            source_ref=candidate.candidate_ref,
            submitted_at="p4",
            pinned_revisions=dict(sorted(candidate.revision_vector.items())),
            payload={
                "candidate_ref": candidate.candidate_ref,
                "public_digest": candidate.quote_public_digest,
                "revalidation_digest": _digest(owner_quantities),
            },
        )
        plan = SharedSettlementPlan(
            plan_id=f"settlement:{command.command_id}",
            command_id=command.command_id,
            expected_revision_vector=command.expected_revisions,
            proposals=(EffectProposal(proposal_id=f"proposal:{candidate.candidate_ref}", effect_ref="gameplay.economy.clearing_revalidated", target_refs=(economy_stream,), source_rule_ref="p4:clearing", pinned_revisions=command.pinned_revisions),),
            event_mapping={economy_stream: "gameplay.economy.clearing_revalidated"},
            idempotency_key=idempotency_key,
            causation_id=command.causation_id,
            correlation_id=command.correlation_id,
        )
        # P4A owns only its Economy posting.  The complete external vector and
        # owner witness are retained as pins; fabricating Inventory or
        # Organization events here would create a second owner path.
        batch = build_multi_stream_atomic_event_batch(
            command_id=command.command_id,
            principal_ref=command.principal_ref,
            expected_revisions={economy_stream: expected_revisions[economy_stream]},
            event_specs={
                economy_stream: [
                    (
                        "gameplay.economy.clearing_revalidated",
                        self._event_payload(candidate, tick, owner_quantities),
                    )
                ]
            },
            idempotency_key=idempotency_key,
            causation_id=command.causation_id,
            correlation_id=command.correlation_id,
            pinned_revisions=command.pinned_revisions,
        )
        # The clear emits only the Economy-owned revalidation event, but its
        # authority decision depends on the complete candidate vector.  Carry
        # every owner head into the atomic compare-and-append so an Inventory
        # or other owner change between reconstruction and append fails closed.
        batch = batch.model_copy(
            update={
                "expected_stream_revisions": dict(sorted(command.expected_revisions.items())),
                "pinned_revisions": dict(sorted(command.pinned_revisions.items())),
            },
            deep=True,
        )
        receipt = self._store.append_batch(batch)
        return CommercialCommitOutcome(
            committed=receipt.committed,
            receipt=receipt,
            error_code=receipt.failure.error_code if receipt.failure is not None else None,
            zero_write=not receipt.committed,
            revision_vector=dict(receipt.resulting_stream_revisions),
            public_digest=_digest({"candidate": candidate.model_dump(mode="json"), "receipt": receipt.model_dump(mode="json")}),
            settlement_plan=plan,
        )

    @staticmethod
    def _candidate_error(candidate: ClearingCandidate, tick: int) -> str | None:
        if tick < candidate.valid_from_tick or tick > candidate.valid_until_tick:
            return "quote_expired"
        if candidate.quantity <= 0 or candidate.unit_price_minor <= 0:
            return "clearing_candidate_invalid"
        return None

    @staticmethod
    def _owner_fact_error(
        candidate: ClearingCandidate,
        quote: DynamicQuote,
        order: QuoteOrder,
        owner_quantities: dict[str, int],
        tick: int,
    ) -> str | None:
        if quote.quote_ref != candidate.quote_ref or quote.version != candidate.quote_version:
            return "quote_version_stale"
        if order.order_ref != candidate.order_ref:
            return "order_stale"
        if quote.status != "active" or order.status != "active":
            return "quote_cancelled" if quote.status != "active" else "order_cancelled"
        if not (quote.valid_from_tick <= tick <= quote.valid_until_tick and order.valid_from_tick <= tick <= order.valid_until_tick):
            return "quote_expired"
        if quote.public_digest != candidate.quote_public_digest or order.public_digest != candidate.order_public_digest:
            return "public_digest_stale"
        if (
            quote.issuer_ref != candidate.quote_issuer_ref
            or order.issuer_ref != candidate.order_issuer_ref
            or quote.item_ref != candidate.item_ref
            or order.item_ref != candidate.item_ref
            or quote.quality_ref != candidate.quality_ref
            or order.quality_ref != candidate.quality_ref
            or quote.currency_ref != candidate.currency_ref
            or order.currency_ref != candidate.currency_ref
            or quote.policy_revision != candidate.policy_revision
            or order.policy_revision != candidate.policy_revision
            or quote.unit_price_minor != candidate.unit_price_minor
            or order.limit_price_minor < candidate.unit_price_minor
            or quote.reservation_ref != candidate.quote_reservation_ref
            or order.reservation_ref != candidate.order_reservation_ref
            or quote.inventory_custody_ref != candidate.quote_inventory_custody_ref
            or order.inventory_custody_ref != candidate.order_inventory_custody_ref
            or quote.capacity_reservation_ref != candidate.quote_capacity_reservation_ref
            or order.capacity_reservation_ref != candidate.order_capacity_reservation_ref
            or quote.delivery_policy_ref != candidate.quote_delivery_policy_ref
            or quote.cancellation_policy_ref != candidate.quote_cancellation_policy_ref
            or order.delivery_policy_ref != candidate.order_delivery_policy_ref
            or order.cancellation_policy_ref != candidate.order_cancellation_policy_ref
        ):
            return "candidate_terms_stale"
        if order.revision_vector != candidate.revision_vector:
            return "revision_vector_stale"
        if min(
            owner_quantities["quote_reservation_available_quantity"],
            owner_quantities["order_reservation_available_quantity"],
            owner_quantities["quote_capacity_available_quantity"],
            owner_quantities["order_capacity_available_quantity"],
            quote.quantity_limit,
            order.quantity,
        ) < candidate.quantity:
            return "reservation_or_capacity_exhausted"
        if owner_quantities["budget_available_minor"] < candidate.quantity * candidate.unit_price_minor:
            return "budget_insufficient"
        return None

    def _resolve_current_owner_facts(
        self,
        candidate: ClearingCandidate,
    ) -> tuple[DynamicQuote, QuoteOrder, dict[str, int]]:
        """Resolve only named current facts; this is not an order-book lookup.

        Quotes/orders are Economy-owned public publications.  Stock and both
        capacity reservations are reconstructed by the Inventory owner, and
        buyer funding is reconstructed by Economy.  No caller can substitute a
        snapshot for these event-sourced facts.
        """
        events = self._store.read_events()
        economy = EconomyProjector().rebuild(events)
        quote_payload = economy.dynamic_quotes.get(candidate.quote_ref)
        order_payload = economy.dynamic_orders.get(candidate.order_ref)
        if quote_payload is None:
            raise ValueError("quote_owner_fact_missing")
        if order_payload is None:
            raise ValueError("order_owner_fact_missing")
        try:
            quote = DynamicQuote.model_validate(dict(quote_payload))
            order = QuoteOrder.model_validate(dict(order_payload))
        except Exception as exc:
            raise ValueError("quote_or_order_owner_fact_invalid") from exc
        quote_inventory = InventoryProjector(self._inventory_registry).rebuild(quote.issuer_ref, events)
        order_inventory = InventoryProjector(self._inventory_registry).rebuild(order.issuer_ref, events)
        quote_reservation = quote_inventory.reservations.get(candidate.quote_reservation_ref)
        if quote_reservation is None:
            raise ValueError("quote_reservation_missing")
        quote_capacity = quote_inventory.capacity_reservations.get(candidate.quote_capacity_reservation_ref)
        if quote_capacity is None:
            raise ValueError("quote_capacity_reservation_missing")
        order_capacity = order_inventory.capacity_reservations.get(candidate.order_capacity_reservation_ref)
        if order_capacity is None:
            raise ValueError("order_capacity_reservation_missing")
        budget = economy.budget_reservations.get(candidate.order_reservation_ref)
        if budget is None:
            raise ValueError("order_budget_reservation_missing")
        account = economy.accounts.get(budget.account_id)
        if account is None or account.owner_ref != order.issuer_ref or account.currency_ref != order.currency_ref:
            raise ValueError("order_budget_owner_mismatch")
        already_reserved = sum(
            reservation.amount_minor
            for reservation in economy.budget_reservations.values()
            if reservation.account_id == account.account_id
        )
        return quote, order, {
            "quote_reservation_available_quantity": quote_reservation.quantity,
            "order_reservation_available_quantity": budget.amount_minor // candidate.unit_price_minor,
            "quote_capacity_available_quantity": quote_capacity.available_quantity,
            "order_capacity_available_quantity": order_capacity.available_quantity,
            "budget_available_minor": min(
                budget.amount_minor,
                account.balance - (already_reserved - budget.amount_minor),
            ),
        }

    @staticmethod
    def _event_payload(
        candidate: ClearingCandidate,
        tick: int,
        owner_quantities: dict[str, int],
    ) -> dict[str, object]:
        return {
            **candidate.model_dump(mode="json"),
            "tick": tick,
            "total_amount_minor": candidate.quantity * candidate.unit_price_minor,
            "revalidation_digest": _digest(owner_quantities),
        }

    @staticmethod
    def _rejected(candidate: ClearingCandidate, error_code: str) -> CommercialCommitOutcome:
        return CommercialCommitOutcome(
            committed=False,
            error_code=error_code,
            zero_write=True,
            revision_vector={},
            public_digest=_digest({"candidate_ref": candidate.candidate_ref, "error_code": error_code}),
        )


__all__ = [
    "ClearingCandidate",
    "ClearingResult",
    "BoundedCreditProposal",
    "CommercialPolicy",
    "CommerceAuthority",
    "CommerceCommitment",
    "CommercialCommitOutcome",
    "CommercialEcosystemResult",
    "CommercialEcosystemScenario",
    "CommercePrivacyView",
    "DeliveryResult",
    "DeterministicClearing",
    "DynamicCommerceAuthority",
    "DynamicQuote",
    "GovernmentCreditAuthority",
    "InspectionEvidence",
    "LaborContractRef",
    "PermitApplication",
    "QuoteOrder",
]
