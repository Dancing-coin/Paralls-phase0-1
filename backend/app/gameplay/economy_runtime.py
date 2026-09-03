"""Minimal event-sourced account ledger; balances are projections, never inputs."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Mapping, Sequence

from pydantic import ConfigDict, Field, model_validator

from app.gameplay.ecology_consumer_admission import EcologyConsumerAdmissionCheck
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.government_treasury_runtime import (
    TaxPaymentCompensationIntentV1,
    TaxPaymentIntentV1,
)
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog, GovernedAuthorityContractError
from app.gameplay.contract_runtime import ContractProjector
from app.gameplay.inventory_runtime import InventoryAuthorityService, InventoryDefinitionRegistry, InventoryRuntimeError
from app.gameplay.models import AtomicEventBatch, AppendBatchResult, GameplayEvent, GameplayFailure, GameplayOutboxEntry, OwnerAuthorizedFragment, StrictGameplayModel
from app.gameplay.ownership_runtime import OwnershipAuthorityService, OwnershipRuntimeError
from app.gameplay.patch_runtime import GameplayPatchRuntimeError, PackageDeclaredNegotiatedExchangeDefinition
from app.gameplay.settlement_plan import AppendDerivedSettlementRecipe, SettlementPlan
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
    jurisdiction_ref: str | None = None
    currency_ref: str | None = None


@dataclass(frozen=True)
class BudgetReservation:
    reservation_ref: str
    account_id: str
    amount_minor: int
    source_event_id: str


@dataclass(frozen=True)
class PublicProjectBudgetConsumption:
    consumption_ref: str
    source_event_id: str
    project_ref: str
    facility_ref: str


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


class PartyConsentAttestationV1(StrictGameplayModel):
    """A proposal attestation; it is not a payment or source-fact selector."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    party_ref: str = Field(min_length=1)
    proposal_digest: str = Field(min_length=1)


class PackageDeclaredNegotiatedExchangeIntentV1(StrictGameplayModel):
    """The closed caller surface for the one admitted package exchange."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_ref: str = Field(min_length=1)
    outcome_ref: str = Field(min_length=1)
    proposal_digest: str = Field(min_length=1)
    provider_consent: PartyConsentAttestationV1
    receiver_consent: PartyConsentAttestationV1
    proposed_amount: int | None = Field(default=None, gt=0)
    command_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_attestations(self) -> "PackageDeclaredNegotiatedExchangeIntentV1":
        if (
            self.provider_consent.proposal_digest != self.proposal_digest
            or self.receiver_consent.proposal_digest != self.proposal_digest
            or self.provider_consent.party_ref == self.receiver_consent.party_ref
        ):
            raise ValueError("package_exchange_consent_invalid")
        return self


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
    public_project_budget_consumptions: Mapping[str, PublicProjectBudgetConsumption] = MappingProxyType({})

class EconomyProjector:
    def rebuild(self, events: Sequence[GameplayEvent]) -> EconomyProjection:
        accounts: dict[str, Account] = {}
        tax_due: dict[str, TaxDue] = {}
        budget_reservations: dict[str, BudgetReservation] = {}
        dynamic_quotes: dict[str, Mapping[str, object]] = {}
        dynamic_orders: dict[str, Mapping[str, object]] = {}
        scheduled_transfer_policies: dict[str, ScheduledAccountTransferPolicyInstance] = {}
        public_project_budget_consumptions: dict[str, PublicProjectBudgetConsumption] = {}
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
                    jurisdiction_ref=_optional_text(p, "jurisdiction_ref"),
                    currency_ref=_optional_text(p, "currency_ref"),
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
            if event.event_type == "gameplay.economy.public_project_budget_consumed":
                consumption_ref = _text(event.payload, "consumption_ref")
                if consumption_ref in public_project_budget_consumptions:
                    raise EconomyRuntimeError("economy_public_project_budget_consumption_duplicate")
                public_project_budget_consumptions[consumption_ref] = PublicProjectBudgetConsumption(
                    consumption_ref=consumption_ref,
                    source_event_id=event.event_id,
                    project_ref=_text(event.payload, "project_ref"),
                    facility_ref=_text(event.payload, "facility_ref"),
                )
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
        _validate_public_project_budget_provenance(events)
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
            MappingProxyType(dict(sorted(public_project_budget_consumptions.items()))),
        )

class EconomyAuthorityService:
    _PRINCIPAL="actor_gameplay.economy_domain"
    def __init__(
        self,
        *,
        store: GameplayEventStore,
        package_registry: object | None = None,
        inventory_registry: InventoryDefinitionRegistry | None = None,
        inventory_authority: object | None = None,
        ownership_authority: object | None = None,
        contract_authority: object | None = None,
    ):
        self._store=store
        self._projector=EconomyProjector()
        self._package_registry = package_registry
        self._inventory_registry = inventory_registry
        self._inventory_authority = (
            inventory_authority
            if inventory_authority is not None
            else (
                InventoryAuthorityService(store=store, registry=inventory_registry)
                if inventory_registry is not None
                else None
            )
        )
        self._ownership_authority = (
            ownership_authority
            if ownership_authority is not None
            else OwnershipAuthorityService(store=store)
        )
        self._contract_authority = contract_authority
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

    def settle_package_declared_negotiated_exchange(
        self, intent: PackageDeclaredNegotiatedExchangeIntentV1
    ) -> AppendBatchResult:
        if (
            not isinstance(intent, PackageDeclaredNegotiatedExchangeIntentV1)
            or intent.capability_ref != "capability:package-declared-negotiated-exchange@1"
        ):
            return self._rejected_append(
                getattr(intent, "command_id", "package-exchange"),
                "package_exchange_capability_denied",
            )
        request_digest = _digest(intent.model_dump(mode="json"))
        duplicate = self._package_exchange_duplicate_result(
            command_id=intent.command_id,
            idempotency_key=intent.idempotency_key,
            request_digest=request_digest,
        )
        if duplicate is not None:
            return duplicate
        try:
            manifest, definition, registry_revision, active_patch_set_revision = (
                self._resolve_package_exchange_definition(
                    capability_ref=intent.capability_ref,
                    outcome_ref=intent.outcome_ref,
                )
            )
            amount_minor = self._resolve_package_exchange_amount(
                definition=definition,
                proposed_amount=intent.proposed_amount,
            )
            expected_key = (
                f"package-negotiated-exchange:{manifest.patch_revision_id}:"
                f"package_declared_negotiated_exchange@1:{intent.proposal_digest}:v1"
            )
            if intent.idempotency_key != expected_key:
                return self._rejected_append(intent.command_id, "package_exchange_idempotency_key_invalid")
            provider_ref = intent.provider_consent.party_ref
            receiver_ref = intent.receiver_consent.party_ref
            if "public-milling-session" in intent.outcome_ref and provider_ref != "organization:district-milling-cooperative":
                return self._rejected_append(intent.command_id, "public_milling_provider_binding_invalid")
            (
                provider_account,
                receiver_account,
                provider_opened,
                receiver_opened,
            ) = self._resolve_package_exchange_accounts(
                provider_ref=provider_ref,
                receiver_ref=receiver_ref,
                currency_ref=definition.price_policy.currency_ref,
            )
            source_fragment, source_event_ids, source_event_revisions = (
                self._resolve_package_exchange_source(
                    definition=definition,
                    provider_ref=provider_ref,
                    receiver_ref=receiver_ref,
                    outcome_ref=intent.outcome_ref,
                    package_revision=manifest.patch_revision_id,
                )
            )
        except (EconomyRuntimeError, GameplayPatchRuntimeError) as exc:
            return self._rejected_append(intent.command_id, str(exc))

        stream = "gameplay:economy"
        expected_revision = self._store.get_stream_head(stream)
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:package-declared-negotiated-exchange@1",
                contract_kind="settlement",
                owner_ref=self._PRINCIPAL,
                stream_ids=(stream,),
                event_types=(
                    "gameplay.economy.account_debited",
                    "gameplay.economy.account_credited",
                    "gameplay.economy.package_declared_negotiated_exchange_settled",
                ),
                projection_scope="authority_only",
            )
        except GovernedAuthorityContractError as exc:
            return self._rejected_append(intent.command_id, str(exc))
        economy_fragment = OwnerAuthorizedFragment(
            fragment_id=(
                "fragment:economy:package-declared-negotiated-exchange:"
                f"{manifest.patch_revision_id}:{intent.proposal_digest}"
            ),
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref="economy:package-declared-negotiated-exchange@1",
            expected_revisions={stream: expected_revision},
            read_set_revisions={stream: expected_revision},
            pinned_revisions={
                "economy": expected_revision,
                "provider_account_opened": provider_opened.stream_revision,
                "receiver_account_opened": receiver_opened.stream_revision,
                **source_event_revisions,
            },
            event_specs={
                stream: (
                    (
                        "gameplay.economy.account_debited",
                        {
                            "account_id": receiver_account.account_id,
                            "amount": amount_minor,
                            "currency_ref": definition.price_policy.currency_ref,
                        },
                    ),
                    (
                        "gameplay.economy.account_credited",
                        {
                            "account_id": provider_account.account_id,
                            "amount": amount_minor,
                            "currency_ref": definition.price_policy.currency_ref,
                        },
                    ),
                    (
                        "gameplay.economy.package_declared_negotiated_exchange_settled",
                        {
                            "economic_outcome_id": definition.economic_outcome_id,
                            "outcome_ref": intent.outcome_ref,
                            "proposal_digest": intent.proposal_digest,
                            "package_revision_id": manifest.patch_revision_id,
                            "package_content_digest": manifest.content_digest,
                            "patch_registry_revision": registry_revision,
                            "active_patch_set_revision": active_patch_set_revision,
                            "price_policy_revision": definition.price_policy.price_policy_revision,
                            "currency_ref": definition.price_policy.currency_ref,
                            "amount_minor": amount_minor,
                            "provider_ref": provider_ref,
                            "receiver_ref": receiver_ref,
                            "provider_account_ref": provider_account.account_id,
                            "receiver_account_ref": receiver_account.account_id,
                            "provider_account_opened_event_id": provider_opened.event_id,
                            "provider_account_opened_stream_revision": provider_opened.stream_revision,
                            "receiver_account_opened_event_id": receiver_opened.event_id,
                            "receiver_account_opened_stream_revision": receiver_opened.stream_revision,
                            "source_evidence_mode": definition.source_evidence_mode,
                            "source_owner_ref": definition.source_owner_ref,
                            "source_evidence_kind": definition.source_evidence_kind,
                            "source_event_ids": list(source_event_ids),
                            "source_selection_rule_ref": definition.source_selection_rule_ref,
                            "consent_rule_ref": definition.consent_rule_ref,
                            "privacy_policy_ref": definition.privacy_policy_ref,
                            "compensation_policy_ref": definition.compensation_policy_ref,
                            "status": "settled",
                        },
                    ),
                )
            },
            event_visibility_policies={stream: ("authority_only", "authority_only", "authority_only")},
        )
        fragments = (economy_fragment,) if source_fragment is None else (economy_fragment, source_fragment)
        recipe = AppendDerivedSettlementRecipe.from_fragments(
            command_id=intent.command_id,
            idempotency_principal_ref=self._PRINCIPAL,
            idempotency_key=intent.idempotency_key,
            causation_id=intent.causation_id,
            correlation_id=intent.correlation_id,
            fragments=fragments,
        )
        batch = recipe.batch.model_copy(
            update={
                "idempotency_record": recipe.batch.idempotency_record.model_copy(
                    update={"payload_digest": request_digest},
                    deep=True,
                ),
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}",
                        transaction_id=recipe.batch.transaction_id,
                        event_id=event.event_id,
                        global_sequence=0,
                        topic="economy.package_declared_negotiated_exchange.scoped_projection",
                        audience="authority:economy",
                        payload_projection={
                            "event_type": event.event_type,
                            "proposal_digest": intent.proposal_digest,
                            "outcome_ref": intent.outcome_ref,
                        },
                    )
                    for event in recipe.batch.events
                    if event.event_type == "gameplay.economy.package_declared_negotiated_exchange_settled"
                ],
            },
            deep=True,
        )
        return self._store.append_batch(batch)

    def package_declared_negotiated_exchange_receipt_for(
        self, *, result: AppendBatchResult | None, scope: str
    ) -> SettlementReceipt:
        if scope != "authority":
            raise EconomyRuntimeError("package_exchange_receipt_scope_denied")
        if result is None:
            raise EconomyRuntimeError("package_exchange_receipt_missing")
        return SettlementReceipt.from_append_result(
            result=result,
            audit_refs=(f"economy_transaction:{result.transaction_id}",),
        )

    def package_declared_negotiated_exchange_projection(
        self, *, scope: str, checkpoint_at: int | None = None
    ) -> dict[str, object]:
        if scope != "authority":
            raise EconomyRuntimeError("package_exchange_projection_scope_denied")
        if checkpoint_at is not None and checkpoint_at < 0:
            raise EconomyRuntimeError("package_exchange_checkpoint_invalid")
        events = [
            event
            for event in self._store.read_stream("gameplay:economy")
            if event.event_type == "gameplay.economy.package_declared_negotiated_exchange_settled"
        ]
        for event in events:
            payload = event.payload
            if payload.get("package_revision_id") == "package:industrial-facilities:v7":
                source_ids = payload.get("source_event_ids")
                if not isinstance(source_ids, list) or len(source_ids) != 1:
                    raise EconomyRuntimeError("package_exchange_replay_invalid")
            if payload.get("family_ref") == "declared_exchange@1" and payload.get("package_revision") is not None:
                registry = self._package_registry
                if registry is None:
                    raise EconomyRuntimeError("package_exchange_replay_invalid")
                try:
                    manifest = registry.candidate(str(payload["package_revision"]))
                    extension = manifest.platform_extension
                    declaration = next(
                        item
                        for item in extension.outcome_declarations
                        if item.declaration_ref == payload["declaration_ref"]
                    )
                    request = next(
                        item
                        for item in extension.capability_binding_requests
                        if item.binding_ref == payload["binding_ref"]
                    )
                    active_bindings = tuple(
                        item
                        for item in registry.active_patch_set.capability_bindings
                        if item.binding_ref == payload["binding_ref"]
                        and item.package_revision == manifest.patch_revision_id
                        and item.content_digest == manifest.content_digest
                        and item.declaration_digest == declaration.declaration_digest
                    )
                except (KeyError, StopIteration, TypeError, AttributeError) as exc:
                    raise EconomyRuntimeError("package_exchange_replay_invalid") from exc
                if (
                    manifest.content_digest != payload.get("content_digest")
                    or declaration.declaration_digest != payload.get("declaration_digest")
                    or declaration.outcome_family_ref != "outcome:declared-exchange@1"
                    or request.capability_ref != "capability:declared-exchange@1"
                    or request.declaration_ref != declaration.declaration_ref
                    or request.source_package_revision != manifest.patch_revision_id
                    or payload.get("package_revision_id") != manifest.patch_revision_id
                    or payload.get("active_patch_set_revision")
                    != registry.active_patch_set.active_patch_set_revision
                    or manifest.patch_revision_id
                    not in registry.active_patch_set.patch_revision_ids
                    or len(active_bindings) != 1
                ):
                    raise EconomyRuntimeError("package_exchange_replay_invalid")
            if payload.get("family_ref") == "fixed_service_exchange@1" and payload.get("package_revision"):
                registry = self._package_registry
                if registry is None or registry.active_patch_set is None:
                    raise EconomyRuntimeError("package_exchange_replay_invalid")
                try:
                    manifest = registry.candidate(str(payload["package_revision"]))
                    declarations = tuple(
                        item
                        for item in (manifest.platform_extension.outcome_declarations if manifest.platform_extension else ())
                        if item.declaration_ref == payload.get("declaration_ref")
                    )
                    outcomes = tuple(
                        item
                        for item in getattr(manifest, "economic_outcomes", ())
                        if item.outcome_ref == payload.get("outcome_ref")
                    )
                except (KeyError, TypeError, AttributeError) as exc:
                    raise EconomyRuntimeError("package_exchange_replay_invalid") from exc
                if (
                    manifest.content_digest != payload.get("content_digest")
                    or len(declarations) != 1
                    or declarations[0].declaration_digest != payload.get("declaration_digest")
                    or len(outcomes) != 1
                    or outcomes[0].price_policy.fixed_amount != payload.get("amount_minor")
                    or outcomes[0].price_policy.currency_ref != payload.get("currency_ref")
                    or declarations[0].source_package_revision != manifest.patch_revision_id
                    or payload.get("active_patch_set_revision") != registry.active_patch_set.active_patch_set_revision
                    or manifest.patch_revision_id not in registry.active_patch_set.patch_revision_ids
                ):
                    raise EconomyRuntimeError("package_exchange_replay_invalid")
            if payload.get("package_revision_id") == "package:industrial-facilities:v7":
                try:
                    source = self._store.get_event(str(source_ids[0]))
                except KeyError:
                    raise EconomyRuntimeError("package_exchange_replay_invalid") from None
                if (
                    source.event_type != "gameplay.inventory.mill_flour_output_received@1"
                    or payload.get("amount_minor") != 8
                    or payload.get("currency_ref") != "currency:local"
                    or payload.get("provider_ref") != source.payload.get("provider_ref")
                ):
                    raise EconomyRuntimeError("package_exchange_replay_invalid")
        if checkpoint_at is None:
            settlements = self._reduce_package_declared_negotiated_exchange_projection(events=events)
        else:
            checkpoint = self._reduce_package_declared_negotiated_exchange_projection(
                events=[event for event in events if event.global_sequence <= checkpoint_at]
            )
            settlements = self._reduce_package_declared_negotiated_exchange_projection(
                events=[event for event in events if event.global_sequence > checkpoint_at],
                settlements=checkpoint,
            )
        projection: dict[str, object] = {"scope": scope, "settlements": settlements}
        projection["projection_hash"] = "sha256:" + sha256(
            json.dumps(projection, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()
        return projection

    @staticmethod
    def _reduce_package_declared_negotiated_exchange_projection(
        *,
        events: Sequence[GameplayEvent],
        settlements: Mapping[str, Mapping[str, object]] | None = None,
    ) -> dict[str, dict[str, object]]:
        reduced = {
            proposal_digest: dict(value)
            for proposal_digest, value in (settlements or {}).items()
        }
        for event in sorted(events, key=lambda item: (item.global_sequence, item.event_id)):
            proposal_digest = event.payload.get("proposal_digest")
            if not isinstance(proposal_digest, str) or not proposal_digest:
                continue
            reduced[proposal_digest] = {
                "status": "settled",
                "settlement_event_id": event.event_id,
                "outcome_ref": event.payload.get("outcome_ref"),
                "source_evidence_mode": event.payload.get("source_evidence_mode"),
                "amount_minor": event.payload.get("amount_minor"),
                "currency_ref": event.payload.get("currency_ref"),
            }
        return {proposal_digest: reduced[proposal_digest] for proposal_digest in sorted(reduced)}

    def _resolve_package_exchange_definition(
        self, *, capability_ref: str, outcome_ref: str
    ) -> tuple[object, PackageDeclaredNegotiatedExchangeDefinition, str, str]:
        if self._package_registry is None:
            raise EconomyRuntimeError("package_exchange_package_inactive")
        active = getattr(self._package_registry, "active_patch_set", None)
        if active is None:
            raise EconomyRuntimeError("package_exchange_package_inactive")
        manifests = self._package_registry.active_manifests(active.active_patch_set_revision)
        capability_id, _, capability_version = capability_ref.partition("@")
        matches: list[tuple[object, PackageDeclaredNegotiatedExchangeDefinition]] = []
        for manifest in manifests:
            capability_allowed = any(
                item.capability_id == capability_id and item.capability_version == capability_version
                for item in manifest.requested_capabilities
            )
            if not capability_allowed:
                continue
            for definition in manifest.economic_outcomes:
                if definition.outcome_ref == outcome_ref and definition.capability_ref == capability_ref:
                    matches.append((manifest, definition))
        if not matches:
            raise EconomyRuntimeError("package_exchange_capability_denied")
        if len(matches) != 1:
            raise EconomyRuntimeError("package_exchange_outcome_ambiguous")
        manifest, definition = matches[0]
        return manifest, definition, active.registry_revision, active.active_patch_set_revision

    @staticmethod
    def _resolve_package_exchange_amount(
        *, definition: PackageDeclaredNegotiatedExchangeDefinition, proposed_amount: int | None
    ) -> int:
        policy = definition.price_policy
        if policy.fixed_amount is not None:
            if proposed_amount is not None and proposed_amount != policy.fixed_amount:
                raise EconomyRuntimeError("package_exchange_price_invalid")
            return policy.fixed_amount
        if (
            proposed_amount is None
            or policy.minimum_amount is None
            or policy.maximum_amount is None
            or not policy.minimum_amount <= proposed_amount <= policy.maximum_amount
        ):
            raise EconomyRuntimeError("package_exchange_price_invalid")
        return proposed_amount

    def _resolve_package_exchange_accounts(
        self,
        *,
        provider_ref: str,
        receiver_ref: str,
        currency_ref: str,
    ) -> tuple[Account, Account, GameplayEvent, GameplayEvent]:
        projection = self._projector.rebuild(self._store.read_events())
        provider_matches = [
            account
            for account in projection.accounts.values()
            if account.owner_ref == provider_ref and account.currency_ref == currency_ref
        ]
        receiver_matches = [
            account
            for account in projection.accounts.values()
            if account.owner_ref == receiver_ref and account.currency_ref == currency_ref
        ]
        if len(provider_matches) != 1 or len(receiver_matches) != 1:
            raise EconomyRuntimeError("package_exchange_party_account_unavailable")
        provider_account = provider_matches[0]
        receiver_account = receiver_matches[0]
        provider_opened = self._store.get_event(provider_account.source_event_id)
        receiver_opened = self._store.get_event(receiver_account.source_event_id)
        if (
            provider_opened.event_type != "gameplay.economy.account_opened"
            or receiver_opened.event_type != "gameplay.economy.account_opened"
            or provider_opened.visibility_policy != "authority_only"
            or receiver_opened.visibility_policy != "authority_only"
        ):
            raise EconomyRuntimeError("package_exchange_party_account_unavailable")
        if receiver_account.balance <= 0:
            raise EconomyRuntimeError("package_exchange_party_account_unavailable")
        return provider_account, receiver_account, provider_opened, receiver_opened

    def _resolve_package_exchange_source(
        self,
        *,
        definition: PackageDeclaredNegotiatedExchangeDefinition,
        provider_ref: str,
        receiver_ref: str,
        outcome_ref: str,
        package_revision: str,
    ) -> tuple[OwnerAuthorizedFragment | None, tuple[str, ...], dict[str, int]]:
        if definition.source_evidence_mode == "inventory_custody@1":
            inventory = self._require_inventory_authority()
            destination_container_id = self._resolve_package_exchange_destination_container(
                actor_ref=receiver_ref,
                inventory=inventory,
            )
            provider_stream = f"gameplay:inventory:{provider_ref}"
            receiver_stream = f"gameplay:inventory:{receiver_ref}"
            if package_revision == "package:industrial-facilities:v7" or "reinforced-mill-flour" in outcome_ref:
                source_candidates = [
                    event for event in self._store.read_stream(provider_stream)
                    if event.event_type == "gameplay.inventory.mill_flour_output_received@1"
                    and event.visibility_policy == "project"
                    and event.payload.get("provider_ref") == provider_ref
                ]
                if len(source_candidates) != 1:
                    raise EconomyRuntimeError("package_exchange_source_ambiguous")
                try:
                    fragment, source_proof = inventory.build_reinforced_mill_flour_output_purchase_fragment(
                        provider_actor_ref=provider_ref,
                        receiver_actor_ref=receiver_ref,
                        source_receipt_event_id=source_candidates[0].event_id,
                        destination_container_id=destination_container_id,
                        outcome_ref=outcome_ref,
                        package_revision=package_revision,
                        expected_provider_revision=self._store.get_stream_head(provider_stream),
                        expected_receiver_revision=self._store.get_stream_head(receiver_stream),
                    )
                except InventoryRuntimeError as exc:
                    if str(exc) == "revision_conflict":
                        raise EconomyRuntimeError("revision_conflict") from exc
                    raise EconomyRuntimeError("package_exchange_source_invalid") from exc
                source_event = self._store.get_event(str(source_proof["source_event_id"]))
                return fragment, (source_event.event_id,), {"inventory_source": source_event.stream_revision}
            try:
                fragment, source_proof = inventory.build_package_declared_negotiated_exchange_fragment(
                    provider_actor_ref=provider_ref,
                    receiver_actor_ref=receiver_ref,
                    source_ref=definition.tradeable_ref or "",
                    traded_definition_id=definition.tradeable_ref or "",
                    destination_container_id=destination_container_id,
                    outcome_ref=outcome_ref,
                    package_revision=package_revision,
                    expected_provider_revision=self._store.get_stream_head(provider_stream),
                    expected_receiver_revision=self._store.get_stream_head(receiver_stream),
                )
            except InventoryRuntimeError as exc:
                if str(exc) == "revision_conflict":
                    raise EconomyRuntimeError("revision_conflict") from exc
                if str(exc) == "inventory_package_exchange_source_ambiguous":
                    raise EconomyRuntimeError("package_exchange_source_ambiguous") from exc
                raise EconomyRuntimeError("package_exchange_source_invalid") from exc
            source_event_id = str(source_proof["source_event_id"])
            source_event = self._store.get_event(source_event_id)
            return fragment, (source_event_id,), {"inventory_source": source_event.stream_revision}
        if definition.source_evidence_mode == "ownership_right@1":
            ownership = self._require_ownership_authority()
            try:
                fragment = ownership.build_package_declared_negotiated_exchange_fragment(
                    provider_holder_ref=provider_ref,
                    receiver_holder_ref=receiver_ref,
                    source_ref=definition.tradeable_ref or "",
                    asset_ref=definition.tradeable_ref or "",
                    outcome_ref=outcome_ref,
                    package_revision=package_revision,
                    expected_revision=self._store.get_stream_head("gameplay:ownership"),
                )
            except OwnershipRuntimeError as exc:
                if str(exc) == "revision_conflict":
                    raise EconomyRuntimeError("revision_conflict") from exc
                if str(exc) in {"ownership_package_exchange_source_ambiguous", "ownership_right_holder_mismatch"}:
                    raise EconomyRuntimeError("package_exchange_source_ambiguous") from exc
                raise EconomyRuntimeError("package_exchange_source_invalid") from exc
            payload = fragment.event_specs["gameplay:ownership"][0][1]
            source_event_id = str(payload["source_event_id"])
            source_event = self._store.get_event(source_event_id)
            return fragment, (source_event_id,), {"ownership_source": source_event.stream_revision}
        return self._resolve_completed_service_source(
            provider_ref=provider_ref,
            receiver_ref=receiver_ref,
            service_ref=definition.typed_service_ref or "",
            source_evidence_kind=definition.source_evidence_kind,
        )

    def _resolve_completed_service_source(
        self,
        *,
        provider_ref: str,
        receiver_ref: str,
        service_ref: str,
        source_evidence_kind: str,
    ) -> tuple[OwnerAuthorizedFragment | None, tuple[str, ...], dict[str, int]]:
        events = self._store.read_stream("gameplay:contracts")
        projection = ContractProjector().rebuild(events)
        candidates = [
            record
            for record in projection.contracts.values()
            if record.contract_type == "simple_service"
            and record.terms_ref == service_ref
            and record.status == "fulfilled"
            and record.party_refs == (provider_ref, receiver_ref)
            and record.completion_evidence_ref is not None
            and source_evidence_kind in {record.completion_evidence_kind, "completed_service@1"}
        ]
        if len(candidates) != 1:
            raise EconomyRuntimeError("package_exchange_source_ambiguous")
        contract_id = candidates[0].contract_id
        completion = next(
            (
                event for event in events
                if event.event_type == "gameplay.contract.service_completion_recorded"
                and event.payload.get("contract_id") == contract_id
            ),
            None,
        )
        fulfilled = next(
            (
                event for event in events
                if event.event_type == "gameplay.contract.record_fulfilled"
                and event.payload.get("contract_id") == contract_id
            ),
            None,
        )
        if completion is None or fulfilled is None or fulfilled.global_sequence <= completion.global_sequence:
            raise EconomyRuntimeError("package_exchange_source_invalid")
        return (
            None,
            (completion.event_id, fulfilled.event_id),
            {
                "contract_completion": completion.stream_revision,
                "contract_fulfilled": fulfilled.stream_revision,
            },
        )

    def _resolve_package_exchange_destination_container(
        self, *, actor_ref: str, inventory: InventoryAuthorityService
    ) -> str:
        projection = inventory._projector.rebuild(actor_ref, self._store.read_events())
        candidates = [
            container_id
            for container_id, container in projection.containers.items()
            if not container.sealed and not container.carrier_item_id
        ]
        if len(candidates) != 1:
            raise EconomyRuntimeError("package_exchange_receiver_container_unavailable")
        return candidates[0]

    def _require_inventory_authority(self) -> InventoryAuthorityService:
        if isinstance(self._inventory_authority, InventoryAuthorityService):
            return self._inventory_authority
        if self._inventory_registry is None:
            raise EconomyRuntimeError("package_exchange_source_invalid")
        self._inventory_authority = InventoryAuthorityService(
            store=self._store,
            registry=self._inventory_registry,
        )
        return self._inventory_authority

    def _require_ownership_authority(self) -> OwnershipAuthorityService:
        if isinstance(self._ownership_authority, OwnershipAuthorityService):
            return self._ownership_authority
        self._ownership_authority = OwnershipAuthorityService(store=self._store)
        return self._ownership_authority

    def _package_exchange_duplicate_result(
        self, *, command_id: str, idempotency_key: str, request_digest: str
    ) -> AppendBatchResult | None:
        record = self._store.get_idempotency_record(self._PRINCIPAL, idempotency_key)
        if record is None:
            return None
        if record.payload_digest != request_digest:
            return self._rejected_append(command_id, "idempotency_key_reused")
        result = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if result is None:
            return self._rejected_append(command_id, "idempotency_record_missing_result")
        return result.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
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
            prior = next(
                (
                    self._store.get_event(event_id)
                    for event_id in existing.committed_event_ids
                    if self._store.get_event(event_id).event_type == "gameplay.economy.tax_obligation_opened"
                ),
                None,
            )
            if (
                prior is not None
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
            "source_tax_due_stream_revision": source.stream_revision,
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
        source_admission_fields = (
            _optional_text(source.payload, "jurisdiction_ref"),
            _optional_text(source.payload, "currency_ref"),
        )
        event_specs: tuple[tuple[str, dict[str, object]], ...] = (("gameplay.economy.tax_obligation_opened", payload),)
        if any(value is not None for value in source_admission_fields):
            jurisdiction_ref, currency_ref = source_admission_fields
            if (
                not isinstance(jurisdiction_ref, str)
                or not isinstance(currency_ref, str)
            ):
                return TaxObligationResult(False, None, self._rejected_append(command_id, "economy_tax_payment_source_invalid"))
            payer_openings = [
                event
                for event in self._store.read_stream("gameplay:economy")
                if event.event_type == "gameplay.economy.account_opened"
                and event.visibility_policy == "authority_only"
                and event.stream_revision <= source.stream_revision
                and event.payload.get("owner_ref") == organization_ref
                and event.payload.get("currency_ref") == currency_ref
            ]
            # The explicit canonical rule is unique-match only. There is no
            # default/first-account selection or caller-provided account hint.
            if len(payer_openings) != 1:
                return TaxObligationResult(False, None, self._rejected_append(command_id, "economy_tax_payer_binding_unavailable"))
            payer_opened = payer_openings[0]
            payer_opened_event_id = payer_opened.event_id
            payer_opened_revision = payer_opened.stream_revision
            payer_binding_event_id = f"event:{command_id}:2"
            payload.update({
                "jurisdiction_ref": jurisdiction_ref,
                "currency_ref": currency_ref,
                "payer_binding_event_id": payer_binding_event_id,
                "payer_binding_stream_revision": expected_revision + 2,
                "payer_account_opened_event_id": payer_opened_event_id,
                "payer_account_opened_stream_revision": payer_opened_revision,
                "payer_account_ref": payer_opened.payload["account_id"],
                "payer_account_owner_ref": organization_ref,
            })
            event_specs = (
                ("gameplay.economy.tax_obligation_opened", payload),
                (
                    "gameplay.economy.tax_obligation_payer_bound",
                    {
                        "obligation_id": obligation_id,
                        "payer_account_ref": payer_opened.payload["account_id"],
                        "payer_account_owner_ref": organization_ref,
                        "payer_binding_rule_ref": "economy:tax-payment:canonical-payer@1",
                        "payer_account_opened_event_id": payer_opened_event_id,
                        "payer_account_opened_stream_revision": payer_opened_revision,
                    },
                ),
            )
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
            event_specs={"gameplay:economy": event_specs},
            event_visibility_policies={"gameplay:economy": tuple("authority_only" for _ in event_specs)},
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
    def settle_tax_payment(self, intent: TaxPaymentIntentV1) -> AppendBatchResult:
        """Settle the one admitted government tax-payment capability.

        The typed intent identifies an obligation only. Every account, stream,
        event, revision, and privacy choice is derived from committed evidence.
        """
        if not isinstance(intent, TaxPaymentIntentV1) or intent.capability_ref != "capability:government-tax-payment@1":
            return self._rejected_append(getattr(intent, "command_id", "tax-payment"), "government_tax_payment_capability_denied")
        command_id = intent.command_id
        request_digest = _digest(intent.model_dump(mode="json"))
        duplicate = self._tax_payment_duplicate_result(command_id=command_id, idempotency_key=intent.idempotency_key, request_digest=request_digest)
        if duplicate is not None:
            return duplicate
        try:
            opening = self._tax_opening(obligation_id=intent.obligation_id)
            jurisdiction_ref = _text(opening.payload, "jurisdiction_ref")
            currency_ref = _text(opening.payload, "currency_ref")
            tax_due_event_id = _text(opening.payload, "source_tax_due_event_id")
            tax_due_revision = _nonnegative(opening.payload, "source_tax_due_stream_revision")
            payer_binding_event_id = _text(opening.payload, "payer_binding_event_id")
            payer_binding_revision = _nonnegative(opening.payload, "payer_binding_stream_revision")
            payer_account_opened_event_id = _text(opening.payload, "payer_account_opened_event_id")
            payer_opened_revision = _nonnegative(opening.payload, "payer_account_opened_stream_revision")
            payer_account_ref = _text(opening.payload, "payer_account_ref")
            payer_owner_ref = _text(opening.payload, "payer_account_owner_ref")
        except EconomyRuntimeError:
            return self._rejected_append(command_id, "government_tax_payment_source_pin_missing")
        economy_stream = "gameplay:economy"
        expected_revision = self._store.get_stream_head(economy_stream)
        try:
            tax_due = self._store.get_event(tax_due_event_id)
            binding = self._store.get_event(payer_binding_event_id)
            payer_opened = self._store.get_event(payer_account_opened_event_id)
        except KeyError:
            return self._rejected_append(command_id, "government_tax_payment_source_missing")
        if (
            tax_due.event_type != "gameplay.economy.tax_due_recorded"
            or tax_due.stream_revision != tax_due_revision
            or tax_due.payload.get("jurisdiction_ref") != jurisdiction_ref
            or tax_due.payload.get("currency_ref") != currency_ref
            or binding.event_type != "gameplay.economy.tax_obligation_payer_bound"
            or binding.stream_revision != payer_binding_revision
            or binding.payload.get("obligation_id") != intent.obligation_id
            or binding.payload.get("payer_account_ref") != payer_account_ref
            or binding.payload.get("payer_account_owner_ref") != payer_owner_ref
            or binding.payload.get("payer_account_opened_event_id") != payer_account_opened_event_id
            or binding.payload.get("payer_account_opened_stream_revision") != payer_opened_revision
            or payer_opened.event_type != "gameplay.economy.account_opened"
            or payer_opened.stream_revision != payer_opened_revision
            or payer_opened.payload.get("account_id") != payer_account_ref
            or payer_opened.payload.get("owner_ref") != payer_owner_ref
            or payer_opened.payload.get("currency_ref") != currency_ref
        ):
            return self._rejected_append(command_id, "government_tax_payment_source_invalid")
        treasury_stream = f"gameplay:government_treasury:{jurisdiction_ref}"
        collector = next(
            (
                event for event in reversed(self._store.read_stream(treasury_stream))
                if event.event_type == "gameplay.government_treasury.collector_account_admitted"
                and event.visibility_policy == "authority_only"
                and event.payload.get("jurisdiction_ref") == jurisdiction_ref
                and event.payload.get("currency_ref") == currency_ref
            ),
            None,
        )
        if collector is None or collector.stream_revision != self._store.get_stream_head(treasury_stream):
            return self._rejected_append(command_id, "government_tax_payment_collector_missing")
        collector_account_ref = collector.payload.get("collector_account_ref")
        collector_owner_ref = collector.payload.get("collector_owner_ref")
        projection = self._projector.rebuild(self._store.read_events())
        payer = projection.accounts.get(payer_account_ref)
        collector_account = projection.accounts.get(str(collector_account_ref))
        amount = opening.payload.get("assessed_amount_minor")
        if (
            payer is None
            or collector_account is None
            or payer.owner_ref != payer_owner_ref
            or payer.currency_ref != currency_ref
            or collector_account.owner_ref != collector_owner_ref
            or collector_account.currency_ref != currency_ref
            or isinstance(amount, bool)
            or not isinstance(amount, int)
            or amount <= 0
            or payer.balance < amount
        ):
            return self._rejected_append(command_id, "government_tax_payment_account_invalid")
        current_state = self._tax_obligation_state(obligation_id=intent.obligation_id)
        if current_state != "open":
            return self._rejected_append(command_id, "government_tax_payment_obligation_not_open")
        required_key = f"tax-payment:{intent.obligation_id}:{payer_account_ref}:v1"
        if not intent.idempotency_key.startswith(required_key):
            return self._rejected_append(command_id, "government_tax_payment_idempotency_invalid")
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:economy-government-tax-payment@1",
                contract_kind="settlement",
                owner_ref=self._PRINCIPAL,
                stream_ids=(economy_stream,),
                event_types=(
                    "gameplay.economy.account_debited",
                    "gameplay.economy.account_credited",
                    "gameplay.economy.tax_payment_settled",
                    "gameplay.economy.tax_obligation_settled",
                ),
                projection_scope="authority_only",
            )
        except GovernedAuthorityContractError as exc:
            return self._rejected_append(command_id, str(exc))
        fragment = OwnerAuthorizedFragment(
            fragment_id=f"fragment:economy:government-tax-payment:{intent.obligation_id}",
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref="economy:government-tax-payment@1",
            expected_revisions={economy_stream: expected_revision},
            read_set_revisions={treasury_stream: collector.stream_revision},
            pinned_revisions={
                "economy": expected_revision,
                "tax_due": tax_due_revision,
                "payer_binding": payer_binding_revision,
                "payer_account_opened": payer_opened_revision,
                "treasury_collector": collector.stream_revision,
            },
            event_specs={economy_stream: (
                ("gameplay.economy.account_debited", {"account_id": payer_account_ref, "amount": amount}),
                ("gameplay.economy.account_credited", {"account_id": collector_account_ref, "amount": amount}),
                ("gameplay.economy.tax_payment_settled", {
                    "obligation_id": intent.obligation_id, "payer_account_ref": payer_account_ref,
                    "collector_account_ref": collector_account_ref, "amount_minor": amount,
                    "tax_due_event_id": tax_due_event_id, "payer_binding_event_id": payer_binding_event_id,
                    "collector_admission_event_id": collector.event_id, "status": "settled",
                }),
                ("gameplay.economy.tax_obligation_settled", {
                    "obligation_id": intent.obligation_id, "prior_state": "open", "current_state": "settled",
                    "payment_event_id": f"event:{command_id}:3", "tax_due_event_id": tax_due_event_id,
                }),
            )},
            event_visibility_policies={economy_stream: ("authority_only",) * 4},
        )
        return self._append_tax_payment(
            command_id=command_id, command_type="gameplay.economy.tax_payment", submitted_at="economy-government-tax-payment",
            source_ref=opening.event_id, idempotency_key=intent.idempotency_key, causation_id=intent.causation_id,
            correlation_id=intent.correlation_id, fragment=fragment, request_digest=request_digest,
        )

    def request_tax_payment_reversal(self, *, settled_payment_event_id: str, command_id: str, idempotency_key: str, causation_id: str, correlation_id: str) -> AppendBatchResult:
        """Record the one committed reversal source permitted for compensation."""
        if not all(isinstance(value, str) and value for value in (settled_payment_event_id, command_id, idempotency_key, causation_id, correlation_id)):
            return self._rejected_append(command_id, "government_tax_payment_reversal_input_invalid")
        request_digest = _digest({
            "settled_payment_event_id": settled_payment_event_id,
            "command_id": command_id,
            "causation_id": causation_id,
            "correlation_id": correlation_id,
        })
        duplicate = self._tax_payment_duplicate_result(
            command_id=command_id,
            idempotency_key=idempotency_key,
            request_digest=request_digest,
        )
        if duplicate is not None:
            return duplicate
        try:
            settled = self._store.get_event(settled_payment_event_id)
        except KeyError:
            return self._rejected_append(command_id, "government_tax_payment_settlement_missing")
        if settled.event_type != "gameplay.economy.tax_payment_settled" or settled.visibility_policy != "authority_only":
            return self._rejected_append(command_id, "government_tax_payment_settlement_invalid")
        obligation_id = settled.payload.get("obligation_id")
        if not isinstance(obligation_id, str) or not obligation_id:
            return self._rejected_append(command_id, "government_tax_payment_settlement_invalid")
        stream = "gameplay:economy"
        revision = self._store.get_stream_head(stream)
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:economy-government-tax-payment@1",
                contract_kind="settlement",
                owner_ref=self._PRINCIPAL,
                stream_ids=(stream,),
                event_types=("gameplay.economy.tax_payment_reversal_requested",),
                projection_scope="authority_only",
            )
        except GovernedAuthorityContractError as exc:
            return self._rejected_append(command_id, str(exc))
        fragment = OwnerAuthorizedFragment(
            fragment_id=f"fragment:economy:government-tax-payment-reversal:{settled.event_id}",
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref="economy:government-tax-payment-reversal@1",
            expected_revisions={stream: revision},
            read_set_revisions={},
            pinned_revisions={"economy": revision, "settled_payment": settled.stream_revision},
            event_specs={stream: (("gameplay.economy.tax_payment_reversal_requested", {
                "settled_payment_event_id": settled.event_id,
                "obligation_id": obligation_id,
            }),)},
            event_visibility_policies={stream: ("authority_only",)},
        )
        return self._append_tax_payment(
            command_id=command_id,
            command_type="gameplay.economy.tax_payment_reversal_request",
            submitted_at="economy-government-tax-payment-reversal",
            source_ref=settled.event_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            fragment=fragment,
            request_digest=request_digest,
        )

    def compensate_tax_payment(self, intent: TaxPaymentCompensationIntentV1) -> AppendBatchResult:
        if not isinstance(intent, TaxPaymentCompensationIntentV1) or intent.capability_ref != "capability:government-tax-payment@1":
            return self._rejected_append(getattr(intent, "command_id", "tax-payment-compensation"), "government_tax_payment_capability_denied")
        command_id = intent.command_id; request_digest = _digest(intent.model_dump(mode="json"))
        duplicate = self._tax_payment_duplicate_result(command_id=command_id, idempotency_key=intent.idempotency_key, request_digest=request_digest)
        if duplicate is not None:
            return duplicate
        try:
            settled = self._store.get_event(intent.settled_payment_event_id)
            reversal = self._store.get_event(intent.reversal_source_event_id)
        except KeyError:
            return self._rejected_append(command_id, "government_tax_payment_compensation_source_missing")
        if (
            settled.event_type != "gameplay.economy.tax_payment_settled"
            or reversal.event_type != "gameplay.economy.tax_payment_reversal_requested"
            or reversal.payload.get("settled_payment_event_id") != settled.event_id
            or reversal.global_sequence <= settled.global_sequence
        ):
            return self._rejected_append(command_id, "government_tax_payment_compensation_source_invalid")
        obligation_id = settled.payload.get("obligation_id")
        payer_account_ref = settled.payload.get("payer_account_ref")
        collector_account_ref = settled.payload.get("collector_account_ref")
        amount = settled.payload.get("amount_minor")
        if not all(isinstance(value, str) and value for value in (obligation_id, payer_account_ref, collector_account_ref)) or isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
            return self._rejected_append(command_id, "government_tax_payment_settlement_invalid")
        stream = "gameplay:economy"; revision = self._store.get_stream_head(stream)
        if self._tax_obligation_state(obligation_id=obligation_id) != "settled":
            return self._rejected_append(command_id, "government_tax_payment_obligation_not_settled")
        if any(event.event_type == "gameplay.economy.tax_payment_compensated" and event.payload.get("settled_payment_event_id") == settled.event_id for event in self._store.read_stream(stream)):
            return self._rejected_append(command_id, "government_tax_payment_already_compensated")
        projection = self._projector.rebuild(self._store.read_events()); collector = projection.accounts.get(collector_account_ref)
        if collector is None or collector.balance < amount:
            return self._rejected_append(command_id, "government_tax_payment_compensation_insufficient_funds")
        try:
            GovernedAuthorityContractCatalog.require_operation(contract_ref="inf:economy-government-tax-payment@1", contract_kind="settlement", owner_ref=self._PRINCIPAL, stream_ids=(stream,), event_types=("gameplay.economy.account_debited", "gameplay.economy.account_credited", "gameplay.economy.tax_payment_compensated", "gameplay.economy.tax_obligation_reopened"), projection_scope="authority_only")
        except GovernedAuthorityContractError as exc:
            return self._rejected_append(command_id, str(exc))
        fragment = OwnerAuthorizedFragment(
            fragment_id=f"fragment:economy:government-tax-payment-compensation:{settled.event_id}", owner_principal_ref=self._PRINCIPAL,
            source_rule_ref="economy:government-tax-payment-compensation@1", expected_revisions={stream: revision},
            read_set_revisions={}, pinned_revisions={"economy": revision, "settled_payment": settled.stream_revision, "reversal": reversal.stream_revision},
            event_specs={stream: (
                ("gameplay.economy.account_debited", {"account_id": collector_account_ref, "amount": amount}),
                ("gameplay.economy.account_credited", {"account_id": payer_account_ref, "amount": amount}),
                ("gameplay.economy.tax_payment_compensated", {"settled_payment_event_id": settled.event_id, "reversal_source_event_id": reversal.event_id, "obligation_id": obligation_id, "amount_minor": amount, "status": "compensated"}),
                ("gameplay.economy.tax_obligation_reopened", {"obligation_id": obligation_id, "prior_state": "settled", "current_state": "open", "compensation_event_id": f"event:{command_id}:3", "reversal_source_event_id": reversal.event_id}),
            )}, event_visibility_policies={stream: ("authority_only",) * 4},
        )
        return self._append_tax_payment(command_id=command_id, command_type="gameplay.economy.tax_payment_compensation", submitted_at="economy-government-tax-payment-compensation", source_ref=reversal.event_id, idempotency_key=intent.idempotency_key, causation_id=intent.causation_id, correlation_id=intent.correlation_id, fragment=fragment, request_digest=request_digest)

    def _tax_obligation_state(self, *, obligation_id: str) -> str:
        state = "open"
        for event in self._store.read_stream("gameplay:economy"):
            if event.payload.get("obligation_id") != obligation_id:
                continue
            if event.event_type == "gameplay.economy.tax_obligation_settled": state = "settled"
            elif event.event_type == "gameplay.economy.tax_obligation_reopened": state = "open"
        return state

    def _tax_payment_duplicate_result(self, *, command_id: str, idempotency_key: str, request_digest: str) -> AppendBatchResult | None:
        record = self._store.get_idempotency_record(self._PRINCIPAL, idempotency_key)
        if record is None: return None
        if record.payload_digest != request_digest: return self._rejected_append(command_id, "idempotency_key_reused")
        result = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        return result.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True) if result is not None else self._rejected_append(command_id, "idempotency_record_missing_result")

    def _append_tax_payment(self, *, command_id: str, command_type: str, submitted_at: str, source_ref: str, idempotency_key: str, causation_id: str, correlation_id: str, fragment: OwnerAuthorizedFragment, request_digest: str) -> AppendBatchResult:
        stream = "gameplay:economy"; specs = fragment.event_specs[stream]
        command = GameplayCommandEnvelope(command_id=command_id, command_type=command_type, command_version=1, principal_ref=self._PRINCIPAL, actor_ref=None, project_ref=None, transaction_id=f"transaction:{command_id}", idempotency_key=idempotency_key, expected_revisions={stream: fragment.expected_revisions[stream]}, read_set_revisions=dict(fragment.read_set_revisions), causation_id=causation_id, correlation_id=correlation_id, source_ref=source_ref, submitted_at=submitted_at, pinned_revisions=dict(fragment.pinned_revisions), payload={"stream_ref": stream, "event_specs": [{"event_type": event_type, "payload": {**payload, "visibility_policy": "authority_only"}} for event_type, payload in specs]})
        batch = SettlementPlan.from_command_envelope(command).to_atomic_event_batch()
        batch = batch.model_copy(update={"owner_fragments": [fragment], "idempotency_record": batch.idempotency_record.model_copy(update={"payload_digest": request_digest}, deep=True), "outbox_entries": [GameplayOutboxEntry(outbox_id=f"outbox:{event.event_id}", transaction_id=batch.transaction_id, event_id=event.event_id, global_sequence=0, topic="economy.tax_payment.scoped_projection", audience="authority:economy", payload_projection={"event_type": event.event_type, "obligation_id": str(event.payload.get("obligation_id", ""))}) for event in batch.events]}, deep=True)
        return self._store.append_batch(batch)

    def tax_payment_receipt_for(self, *, result: AppendBatchResult | None, scope: str) -> SettlementReceipt:
        if scope != "authority": raise EconomyRuntimeError("government_tax_payment_receipt_scope_denied")
        if result is None: raise EconomyRuntimeError("government_tax_payment_receipt_missing")
        return SettlementReceipt.from_append_result(result=result, audit_refs=(f"economy_transaction:{result.transaction_id}",))

    def tax_payment_projection(self, *, scope: str, checkpoint_at: int | None = None) -> dict[str, object]:
        if scope != "authority":
            raise EconomyRuntimeError("government_tax_payment_projection_scope_denied")
        events = [
            event
            for event in self._store.read_stream("gameplay:economy")
            if event.event_type in {
                "gameplay.economy.tax_payment_settled",
                "gameplay.economy.tax_payment_compensated",
                "gameplay.economy.tax_obligation_reopened",
            }
        ]
        if checkpoint_at is not None and checkpoint_at < 0:
            raise EconomyRuntimeError("government_tax_payment_checkpoint_invalid")
        if checkpoint_at is None:
            payments = self._reduce_tax_payment_projection(events=events)
        else:
            checkpoint = self._reduce_tax_payment_projection(
                events=[event for event in events if event.global_sequence <= checkpoint_at]
            )
            payments = self._reduce_tax_payment_projection(
                events=[event for event in events if event.global_sequence > checkpoint_at],
                payments=checkpoint,
            )
        projection: dict[str, object] = {"scope": scope, "payments": payments}
        projection["projection_hash"] = "sha256:" + sha256(json.dumps(projection, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
        return projection

    @staticmethod
    def _reduce_tax_payment_projection(
        *, events: Sequence[GameplayEvent], payments: Mapping[str, Mapping[str, object]] | None = None
    ) -> dict[str, dict[str, object]]:
        reduced = {obligation_id: dict(value) for obligation_id, value in (payments or {}).items()}
        for event in sorted(events, key=lambda item: (item.global_sequence, item.event_id)):
            obligation_id = event.payload.get("obligation_id")
            if not isinstance(obligation_id, str) or not obligation_id:
                continue
            if event.event_type == "gameplay.economy.tax_payment_settled":
                reduced[obligation_id] = {
                    "status": "settled",
                    "payment_status": "settled",
                    "payment_event_id": event.event_id,
                    "amount_minor": event.payload.get("amount_minor"),
                }
            elif event.event_type == "gameplay.economy.tax_payment_compensated":
                reduced.setdefault(obligation_id, {})["payment_status"] = "compensated"
            elif event.event_type == "gameplay.economy.tax_obligation_reopened":
                reduced.setdefault(obligation_id, {})["status"] = "open"
        return {obligation_id: reduced[obligation_id] for obligation_id in sorted(reduced)}

    # Budget lifecycle facts remain Economy-owned.  The family branch below
    # reads only a committed Construction project-step and its active package
    # binding; callers never select amount, currency, account, or streams.
    def _budget_duplicate_result(
        self, *, command_id: str, idempotency_key: str, request: Mapping[str, object], error_prefix: str
    ) -> AppendBatchResult | None:
        record = self._store.get_idempotency_record(self._PRINCIPAL, idempotency_key)
        if record is None:
            return None
        if record.payload_digest != _digest(dict(request)):
            return self._rejected_append(command_id, f"{error_prefix}_idempotency_key_reused")
        result = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if result is None:
            return self._rejected_append(command_id, f"{error_prefix}_idempotency_record_missing_result")
        return result.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)

    def _append_budget_event(
        self,
        *,
        command_id: str,
        command_type: str,
        idempotency_key: str,
        request: Mapping[str, object],
        causation_id: str,
        correlation_id: str,
        submitted_at: str,
        source_ref: str,
        expected_economy_revision: int,
        read_set_revisions: Mapping[str, int],
        payload: Mapping[str, object],
    ) -> AppendBatchResult:
        stream = "gameplay:economy"
        command = GameplayCommandEnvelope(
            command_id=command_id,
            command_type=command_type,
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=None,
            project_ref=None,
            transaction_id=f"transaction:{command_id}",
            idempotency_key=idempotency_key,
            expected_revisions={stream: expected_economy_revision},
            read_set_revisions=dict(read_set_revisions),
            causation_id=causation_id,
            correlation_id=correlation_id,
            source_ref=source_ref,
            submitted_at=submitted_at,
            pinned_revisions={"economy": expected_economy_revision, **dict(read_set_revisions)},
            payload={
                "stream_ref": stream,
                "event_type": str(payload["event_type"]),
                "event_specs": [
                    {
                        "event_type": str(payload["event_type"]),
                        "payload": {
                            **{key: value for key, value in payload.items() if key != "event_type"},
                            "visibility_policy": "authority_only",
                        },
                    }
                ],
            },
        )
        batch = SettlementPlan.from_command_envelope(command).to_atomic_event_batch()
        batch = batch.model_copy(
            update={
                "idempotency_record": batch.idempotency_record.model_copy(
                    update={"payload_digest": _digest(dict(request))}, deep=True
                ),
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}",
                        transaction_id=batch.transaction_id,
                        event_id=event.event_id,
                        global_sequence=0,
                        topic="economy.public_project_budget.scoped_projection",
                        audience="authority:economy",
                        payload_projection={
                            "event_type": event.event_type,
                            "project_ref": str(event.payload.get("project_ref", "")),
                        },
                    )
                    for event in batch.events
                ],
            },
            deep=True,
        )
        return self._store.append_batch(batch)

    def _budget_content_for_step(self, source_event: GameplayEvent) -> Mapping[str, object] | None:
        source = source_event.payload
        if source.get("family_ref") != "bounded_project_budget@1":
            if (
                source.get("project_step_ref") != "project-step:public-project:workshop-bench@1"
                or source.get("catalog_ref") != "inf:construction-public-project-step-completion@1"
            ):
                return None
            return {
                "amount": 12,
                "currency_ref": "currency:local",
                "project_definition_ref": "definition:public-project@1",
                "policy_revision_ref": "policy:economy-public-project-budget-workshop@1",
                "source_work_order_ref": "work-order:public-project:workshop-bench@1",
                "source_project_step_ref": "project-step:public-project:workshop-bench@1",
                "family_ref": None,
            }

        registry = self._package_registry
        active = getattr(registry, "active_patch_set", None) if registry is not None else None
        if active is None:
            return None
        try:
            from app.gameplay.closed_generic_gameplay_families import BoundedProjectBudgetContent

            manifests = registry.active_manifests(active.active_patch_set_revision)
        except Exception:
            return None
        candidates: list[Mapping[str, object]] = []
        for manifest in manifests:
            extension = getattr(manifest, "platform_extension", None)
            if extension is None:
                continue
            declarations = {item.declaration_ref: item for item in extension.outcome_declarations}
            for request in extension.capability_binding_requests:
                if request.capability_ref != "capability:bounded-project-budget@1":
                    continue
                declaration = declarations.get(request.declaration_ref)
                if declaration is None or declaration.outcome_family_ref != "outcome:bounded-project-budget@1":
                    continue
                definitions = tuple(
                    item for item in extension.package_definitions if item.definition_ref in declaration.definition_refs
                )
                bindings = tuple(
                    item
                    for item in active.capability_bindings
                    if item.binding_ref == request.binding_ref
                    and item.package_revision == manifest.patch_revision_id
                    and item.content_digest == manifest.content_digest
                    and item.declaration_digest == declaration.declaration_digest
                )
                if len(definitions) != 1 or len(bindings) != 1:
                    continue
                try:
                    content = BoundedProjectBudgetContent.model_validate(definitions[0].typed_content)
                except Exception:
                    continue
                if (
                    content.source_project_step_ref == source.get("project_step_ref")
                    and content.source_work_order_ref == source.get("source_work_order_ref")
                    and manifest.patch_revision_id == source.get("package_revision")
                    and manifest.content_digest == source.get("content_digest")
                    and declaration.declaration_ref == source.get("declaration_ref")
                    and declaration.declaration_digest == source.get("declaration_digest")
                    and bindings[0].binding_ref == source.get("binding_ref")
                ):
                    candidates.append(
                        {
                            **content.model_dump(mode="python"),
                            "family_ref": "bounded_project_budget@1",
                            "package_revision": manifest.patch_revision_id,
                            "content_digest": manifest.content_digest,
                            "declaration_ref": declaration.declaration_ref,
                            "declaration_digest": declaration.declaration_digest,
                            "binding_ref": bindings[0].binding_ref,
                            "active_patch_set_revision": bindings[0].active_patch_set_revision,
                        }
                    )
        return candidates[0] if len(candidates) == 1 else None

    def _budget_step_source(self, *, source_event_id: str, expected_source_revision: int) -> tuple[GameplayEvent, Mapping[str, object]] | None:
        try:
            source_event = self._store.get_event(source_event_id)
        except KeyError:
            return None
        source = source_event.payload
        if (
            source_event.event_type != "gameplay.construction_production.public_project_step_completed"
            or source_event.visibility_policy != "project"
            or source_event.stream_revision != expected_source_revision
            or self._store.get_stream_head(source_event.stream_id) != expected_source_revision
            or source.get("next_step_status") != "completed"
            or not isinstance(source.get("facility_ref"), str)
            or not isinstance(source.get("project_ref"), str)
        ):
            return None
        content = self._budget_content_for_step(source_event)
        if content is None:
            return None
        return source_event, content

    def record_public_project_budget_commitment(
        self,
        *,
        source_event_id: str,
        expected_source_revision: int,
        expected_economy_stream_revision: int,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        submitted_at: str,
    ) -> AppendBatchResult:
        """Compatibility entry point for the original workshop budget row."""
        return self._record_budget_commitment(
            source_event_id=source_event_id,
            expected_source_revision=expected_source_revision,
            expected_economy_stream_revision=expected_economy_stream_revision,
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            submitted_at=submitted_at,
            require_family=False,
        )

    def settle_bounded_project_budget(self, *, intent: object) -> AppendBatchResult:
        try:
            from app.gameplay.closed_generic_gameplay_families import BoundedProjectBudgetIntent

            typed = intent if isinstance(intent, BoundedProjectBudgetIntent) else BoundedProjectBudgetIntent.model_validate(intent)
        except Exception:
            return self._rejected_append(str(getattr(intent, "command_id", "bounded-project-budget")), "bounded_project_budget_intent_invalid")
        try:
            source = self._store.get_event(typed.source_event_id)
        except KeyError:
            return self._rejected_append(typed.command_id, "bounded_project_budget_source_missing")
        return self._record_budget_commitment(
            source_event_id=typed.source_event_id,
            expected_source_revision=source.stream_revision,
            expected_economy_stream_revision=self._store.get_stream_head("gameplay:economy"),
            command_id=typed.command_id,
            idempotency_key=f"economy:bounded-project-budget:{typed.source_event_id}:{source.stream_revision}:v1",
            causation_id=typed.source_event_id,
            correlation_id=typed.correlation_id,
            submitted_at=typed.submitted_at,
            require_family=True,
        )

    def _record_budget_commitment(
        self,
        *,
        source_event_id: str,
        expected_source_revision: int,
        expected_economy_stream_revision: int,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        submitted_at: str,
        require_family: bool,
    ) -> AppendBatchResult:
        prefix = "bounded_project_budget" if require_family else "economy_public_project_budget"
        request = {
            "source_event_id": source_event_id,
            "expected_source_revision": expected_source_revision,
            "causation_id": causation_id,
            "correlation_id": correlation_id,
            "family": require_family,
        }
        duplicate = self._budget_duplicate_result(command_id=command_id, idempotency_key=idempotency_key, request=request, error_prefix=prefix)
        if duplicate is not None:
            return duplicate
        resolved = self._budget_step_source(source_event_id=source_event_id, expected_source_revision=expected_source_revision)
        if resolved is None:
            return self._rejected_append(command_id, f"{prefix}_source_invalid")
        source_event, content = resolved
        # The original workshop row remains a compatibility input to the new
        # wrapper when no registry is configured.  A configured family must
        # always prove its active immutable binding.
        if require_family and content.get("family_ref") is None and self._package_registry is not None:
            return self._rejected_append(command_id, f"{prefix}_source_invalid")
        if not require_family and content.get("family_ref") == "bounded_project_budget@1":
            return self._rejected_append(command_id, f"{prefix}_source_invalid")
        if self._store.get_stream_head("gameplay:economy") != expected_economy_stream_revision:
            return self._rejected_append(command_id, f"{prefix}_revision_conflict")
        source = source_event.payload
        commitment_ref = f"budget-commitment:public-project:{str(content['source_project_step_ref']).split(':')[-1].removesuffix('@1')}:{source['project_ref']}"
        existing = [
            event for event in self._store.read_stream("gameplay:economy")
            if event.event_type == "gameplay.economy.public_project_budget_commitment_recorded"
            and event.payload.get("source_event_id") == source_event_id
        ]
        if existing:
            return self._rejected_append(command_id, f"{prefix}_duplicate")
        payload: dict[str, object] = {
            "event_type": "gameplay.economy.public_project_budget_commitment_recorded",
            "commitment_ref": commitment_ref,
            "amount_minor": content["amount"],
            "currency_ref": content["currency_ref"],
            "project_ref": source["project_ref"],
            "facility_ref": source["facility_ref"],
            "project_step_ref": content["source_project_step_ref"],
            "project_definition_ref": content["project_definition_ref"],
            "policy_revision": content["policy_revision_ref"],
            "status": "committed",
            "source_event_id": source_event_id,
            "source_event_revision": source_event.stream_revision,
            "source_stream_id": source_event.stream_id,
            "source_stream_head": source_event.stream_revision,
            "catalog_ref": "inf:economy-public-project-budget-commitment@1",
            "descriptor_ref": "descriptor:economy-public-project-budget-commitment@1",
        }
        if require_family:
            payload["family_ref"] = "bounded_project_budget@1"
        if content.get("family_ref"):
            payload.update({key: value for key, value in content.items() if key in {"family_ref", "package_revision", "content_digest", "declaration_ref", "declaration_digest", "binding_ref", "active_patch_set_revision", "source_work_order_ref"}})
        return self._append_budget_event(
            command_id=command_id,
            command_type="gameplay.economy.record_public_project_budget_commitment",
            idempotency_key=idempotency_key,
            request=request,
            causation_id=causation_id,
            correlation_id=correlation_id,
            submitted_at=submitted_at,
            source_ref=source_event_id,
            expected_economy_revision=expected_economy_stream_revision,
            read_set_revisions={source_event.stream_id: expected_source_revision},
            payload=payload,
        )

    def public_project_budget_commitment_receipt_for(self, *, result: AppendBatchResult | None, scope: str) -> SettlementReceipt:
        if scope != "authority":
            raise EconomyRuntimeError("public_project_budget_commitment_receipt_scope_denied")
        if result is None:
            raise EconomyRuntimeError("public_project_budget_commitment_receipt_missing")
        return SettlementReceipt.from_append_result(result=result, audit_refs=(f"economy_transaction:{result.transaction_id}",))

    def public_project_budget_commitment_projection(self, *, scope: str, checkpoint_at: int | None = None) -> dict[str, object]:
        if scope != "authority":
            raise EconomyRuntimeError("public_project_budget_commitment_projection_scope_denied")
        if checkpoint_at is not None and checkpoint_at < 0:
            raise EconomyRuntimeError("public_project_budget_commitment_checkpoint_invalid")
        commitments = {
            str(event.payload["commitment_ref"]): dict(event.payload)
            for event in self._store.read_stream("gameplay:economy")
            if event.event_type == "gameplay.economy.public_project_budget_commitment_recorded"
        }
        return {"scope": scope, "commitments": dict(sorted(commitments.items()))}

    def _budget_commitment_source(
        self, *, commitment_event_id: str, expected_revision: int
    ) -> GameplayEvent | None:
        try:
            event = self._store.get_event(commitment_event_id)
        except KeyError:
            return None
        payload = event.payload
        if (
            event.event_type != "gameplay.economy.public_project_budget_commitment_recorded"
            or event.visibility_policy != "authority_only"
            or event.stream_revision != expected_revision
            or not isinstance(payload.get("amount_minor"), int)
            or payload.get("amount_minor", 0) <= 0
            or not isinstance(payload.get("currency_ref"), str)
            or not isinstance(payload.get("facility_ref"), str)
            or not isinstance(payload.get("project_ref"), str)
        ):
            return None
        return event

    def _budget_acquisition_source(self, commitment: GameplayEvent) -> GameplayEvent | None:
        stream_id = commitment.payload.get("source_stream_id")
        facility_ref = commitment.payload.get("facility_ref")
        if not isinstance(stream_id, str) or not isinstance(facility_ref, str):
            return None
        matches = [
            event
            for event in self._store.read_stream(stream_id)
            if event.event_type == "gameplay.construction_production.facility_acquired"
            and event.visibility_policy == "project"
            and event.payload.get("facility_ref") == facility_ref
            and event.payload.get("plot_ref") == commitment.payload.get("project_ref")
        ]
        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def _budget_reservation_ref(commitment: GameplayEvent) -> str:
        payload = commitment.payload
        if payload.get("family_ref") == "bounded_project_budget@1":
            return f"reservation:bounded-project-budget:{payload['project_step_ref']}:{payload['project_ref']}"
        step = str(payload["project_step_ref"]).split(":")[-1].removesuffix("@1")
        return f"reservation:public-project:{step}:{payload['project_ref']}"

    def reserve_public_project_budget(
        self,
        *,
        commitment_event_id: str,
        expected_commitment_revision: int,
        expected_economy_stream_revision: int,
        expected_acquisition_revision: int,
        expected_facility_stream_revision: int,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        submitted_at: str,
        _family_required: bool = False,
    ) -> AppendBatchResult:
        prefix = "bounded_project_budget_reservation" if _family_required else "economy_public_project_budget_reservation"
        request = {
            "commitment_event_id": commitment_event_id,
            "expected_commitment_revision": expected_commitment_revision,
            "expected_acquisition_revision": expected_acquisition_revision,
            "expected_facility_stream_revision": expected_facility_stream_revision,
            "causation_id": causation_id,
            "correlation_id": correlation_id,
            "family": _family_required,
        }
        duplicate = self._budget_duplicate_result(command_id=command_id, idempotency_key=idempotency_key, request=request, error_prefix=prefix)
        if duplicate is not None:
            return duplicate
        commitment = self._budget_commitment_source(commitment_event_id=commitment_event_id, expected_revision=expected_commitment_revision)
        if commitment is None:
            return self._rejected_append(command_id, f"{prefix}_source_invalid")
        is_family = commitment.payload.get("family_ref") == "bounded_project_budget@1"
        if _family_required and not is_family and self._package_registry is not None:
            return self._rejected_append(command_id, f"{prefix}_source_invalid")
        if not _family_required and is_family:
            return self._rejected_append(command_id, f"{prefix}_source_invalid")
        acquisition = self._budget_acquisition_source(commitment)
        if (
            acquisition is None
            or acquisition.stream_revision != expected_acquisition_revision
            or self._store.get_stream_head(acquisition.stream_id) != expected_facility_stream_revision
        ):
            return self._rejected_append(command_id, f"{prefix}_acquisition_invalid")
        if self._store.get_stream_head("gameplay:economy") != expected_economy_stream_revision:
            return self._rejected_append(command_id, f"{prefix}_revision_conflict")
        projection = self._projector.rebuild(self._store.read_events())
        candidates = [
            account
            for account in projection.accounts.values()
            if account.owner_ref == acquisition.payload.get("owner_ref")
            and account.currency_ref == commitment.payload.get("currency_ref")
        ]
        if not candidates:
            return self._rejected_append(command_id, f"{prefix}_account_missing")
        if len(candidates) != 1:
            error = "bounded_project_budget_reservation_account_ambiguous" if _family_required else "economy_public_project_budget_account_ambiguous"
            return self._rejected_append(command_id, error)
        account = candidates[0]
        amount = int(commitment.payload["amount_minor"])
        reserved = sum(
            reservation.amount_minor
            for reservation in projection.budget_reservations.values()
            if reservation.account_id == account.account_id
        )
        if account.balance - reserved < amount:
            return self._rejected_append(command_id, f"{prefix}_insufficient_funds")
        reservation_ref = self._budget_reservation_ref(commitment)
        if reservation_ref in projection.budget_reservations:
            return self._rejected_append(command_id, f"{prefix}_duplicate")
        payload = {
            "event_type": "gameplay.economy.budget_reserved",
            "reservation_ref": reservation_ref,
            "account_id": account.account_id,
            "amount_minor": amount,
            "currency_ref": commitment.payload["currency_ref"],
            "facility_ref": commitment.payload["facility_ref"],
            "project_ref": commitment.payload["project_ref"],
            "project_step_ref": commitment.payload["project_step_ref"],
            "source_commitment_event_id": commitment.event_id,
            "source_commitment_revision": commitment.stream_revision,
            "source_acquisition_event_id": acquisition.event_id,
            "source_acquisition_revision": acquisition.stream_revision,
            "status": "reserved",
            "catalog_ref": "inf:economy-public-project-budget-reservation@1",
            "descriptor_ref": "descriptor:economy-public-project-budget-reservation@1",
            **{
                key: value
                for key, value in commitment.payload.items()
                if key in {"family_ref", "package_revision", "content_digest", "declaration_ref", "declaration_digest", "binding_ref", "active_patch_set_revision", "source_work_order_ref"}
            },
        }
        if _family_required:
            payload["family_ref"] = "bounded_project_budget@1"
        return self._append_budget_event(
            command_id=command_id,
            command_type="gameplay.economy.reserve_public_project_budget",
            idempotency_key=idempotency_key,
            request=request,
            causation_id=causation_id,
            correlation_id=correlation_id,
            submitted_at=submitted_at,
            source_ref=commitment.event_id,
            expected_economy_revision=expected_economy_stream_revision,
            read_set_revisions={commitment.stream_id: commitment.stream_revision, acquisition.stream_id: expected_facility_stream_revision},
            payload=payload,
        )

    def settle_bounded_project_budget_reservation(self, *, intent: object) -> AppendBatchResult:
        try:
            from app.gameplay.closed_generic_gameplay_families import BoundedProjectBudgetReservationIntent

            typed = intent if isinstance(intent, BoundedProjectBudgetReservationIntent) else BoundedProjectBudgetReservationIntent.model_validate(intent)
            commitment = self._store.get_event(typed.commitment_event_id)
        except Exception:
            return self._rejected_append(str(getattr(intent, "command_id", "bounded-project-budget-reservation")), "bounded_project_budget_reservation_source_missing")
        acquisition = self._budget_acquisition_source(commitment)
        if acquisition is None:
            return self._rejected_append(typed.command_id, "bounded_project_budget_reservation_acquisition_invalid")
        return self.reserve_public_project_budget(
            commitment_event_id=commitment.event_id,
            expected_commitment_revision=commitment.stream_revision,
            expected_economy_stream_revision=self._store.get_stream_head("gameplay:economy"),
            expected_acquisition_revision=acquisition.stream_revision,
            expected_facility_stream_revision=self._store.get_stream_head(acquisition.stream_id),
            command_id=typed.command_id,
            idempotency_key=f"economy:bounded-project-budget-reservation:{commitment.event_id}:{commitment.stream_revision}:v1",
            causation_id=typed.causation_id,
            correlation_id=typed.correlation_id,
            submitted_at=typed.submitted_at,
            _family_required=True,
        )

    def public_project_budget_reservation_receipt_for(self, *, result: AppendBatchResult | None, scope: str) -> SettlementReceipt:
        if scope != "authority":
            raise EconomyRuntimeError("public_project_budget_reservation_receipt_scope_denied")
        if result is None:
            raise EconomyRuntimeError("public_project_budget_reservation_receipt_missing")
        return SettlementReceipt.from_append_result(result=result, audit_refs=(f"economy_transaction:{result.transaction_id}",))

    def public_project_budget_reservation_projection(self, *, scope: str, checkpoint_at: int | None = None) -> dict[str, object]:
        if scope != "authority":
            raise EconomyRuntimeError("public_project_budget_reservation_projection_scope_denied")
        if checkpoint_at is not None and checkpoint_at < 0:
            raise EconomyRuntimeError("public_project_budget_reservation_checkpoint_invalid")
        refs = tuple(
            sorted(
                str(event.payload["reservation_ref"])
                for event in self._store.read_stream("gameplay:economy")
                if event.event_type == "gameplay.economy.budget_reserved"
                and "source_commitment_event_id" in event.payload
            )
        )
        return {"scope": scope, "reservation_refs": refs}

    def consume_public_project_budget(
        self,
        *,
        commitment_event_id: str,
        expected_commitment_revision: int,
        reservation_event_id: str,
        expected_reservation_revision: int,
        activity_event_id: str,
        expected_activity_revision: int,
        expected_economy_stream_revision: int,
        expected_activity_stream_revision: int,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        submitted_at: str,
        _family_required: bool = False,
    ) -> AppendBatchResult:
        prefix = "bounded_project_budget_consumption" if _family_required else "economy_public_project_budget_consumption"
        request = {
            "commitment_event_id": commitment_event_id,
            "expected_commitment_revision": expected_commitment_revision,
            "reservation_event_id": reservation_event_id,
            "expected_reservation_revision": expected_reservation_revision,
            "activity_event_id": activity_event_id,
            "expected_activity_revision": expected_activity_revision,
            "expected_activity_stream_revision": expected_activity_stream_revision,
            "causation_id": causation_id,
            "correlation_id": correlation_id,
            "family": _family_required,
        }
        duplicate = self._budget_duplicate_result(command_id=command_id, idempotency_key=idempotency_key, request=request, error_prefix=prefix)
        if duplicate is not None:
            return duplicate
        commitment = self._budget_commitment_source(commitment_event_id=commitment_event_id, expected_revision=expected_commitment_revision)
        try:
            reservation = self._store.get_event(reservation_event_id)
            activity = self._store.get_event(activity_event_id)
        except KeyError:
            return self._rejected_append(command_id, f"{prefix}_activity_missing")
        if commitment is None or (
            reservation.event_type != "gameplay.economy.budget_reserved"
            or reservation.visibility_policy != "authority_only"
            or reservation.stream_revision != expected_reservation_revision
            or reservation.payload.get("source_commitment_event_id") != commitment_event_id
            or reservation.payload.get("amount_minor") != commitment.payload.get("amount_minor")
            or reservation.payload.get("currency_ref") != commitment.payload.get("currency_ref")
        ):
            return self._rejected_append(command_id, f"{prefix}_source_invalid")
        if self._store.get_stream_head(activity.stream_id) != expected_activity_stream_revision:
            return self._rejected_append(command_id, f"{prefix}_revision_conflict")
        is_family = commitment.payload.get("family_ref") == "bounded_project_budget@1"
        if _family_required and not is_family and self._package_registry is not None:
            return self._rejected_append(command_id, f"{prefix}_source_invalid")
        if not _family_required and is_family:
            return self._rejected_append(command_id, f"{prefix}_source_invalid")
        activity_valid = (
            activity.visibility_policy == "project"
            and activity.stream_revision == expected_activity_revision
            and activity.payload.get("facility_ref") == commitment.payload.get("facility_ref")
            and activity.payload.get("project_ref") == commitment.payload.get("project_ref")
        )
        if is_family:
            activity_valid = activity_valid and (
                activity.event_type == "gameplay.construction_production.public_project_step_completed"
                and activity.event_id == commitment.payload.get("source_event_id")
            )
        else:
            activity_valid = activity_valid and (
                activity.event_type == "gameplay.organization.public_workshop_activity_recorded"
                and activity.payload.get("status") == "completed"
                and activity.payload.get("organization_ref") == "organization:municipal-assessment-office"
                and activity.payload.get("service_ref") == "service:industrial-facility-public-workshop-session@1"
                and activity.payload.get("descriptor_ref") == "descriptor:organization-public-workshop-activity@1"
            )
        if not activity_valid:
            return self._rejected_append(command_id, f"{prefix}_binding_invalid" if activity.payload.get("project_ref") != commitment.payload.get("project_ref") else f"{prefix}_source_invalid")
        if self._store.get_stream_head("gameplay:economy") != expected_economy_stream_revision:
            return self._rejected_append(command_id, f"{prefix}_revision_conflict")
        existing = [
            event for event in self._store.read_stream("gameplay:economy")
            if event.event_type == "gameplay.economy.public_project_budget_consumed"
            and event.payload.get("source_reservation_event_id") == reservation_event_id
        ]
        if existing:
            return self._rejected_append(command_id, f"{prefix}_duplicate")
        payload = {
            "event_type": "gameplay.economy.public_project_budget_consumed",
            "consumption_ref": f"budget-consumption:public-project:{commitment.payload['project_step_ref']}:{commitment.payload['project_ref']}",
            "amount_minor": commitment.payload["amount_minor"],
            "currency_ref": commitment.payload["currency_ref"],
            "facility_ref": commitment.payload["facility_ref"],
            "project_ref": commitment.payload["project_ref"],
            "project_step_ref": commitment.payload["project_step_ref"],
            "source_commitment_event_id": commitment_event_id,
            "source_reservation_event_id": reservation_event_id,
            "source_activity_event_id": activity_event_id,
            "source_activity_revision": activity.stream_revision,
            "status": "consumed",
            "terminal": "v1_terminal_no_compensation",
            "policy_revision": "policy:economy-public-project-budget-consumption@1",
            "descriptor_revision": "descriptor:economy-public-project-budget-consumption@1",
            "catalog_ref": "inf:economy-public-project-budget-consumption@1",
            "descriptor_ref": "descriptor:economy-public-project-budget-consumption@1",
            **{
                key: value
                for key, value in commitment.payload.items()
                if key in {"family_ref", "package_revision", "content_digest", "declaration_ref", "declaration_digest", "binding_ref", "active_patch_set_revision", "source_work_order_ref"}
            },
        }
        if _family_required:
            payload["family_ref"] = "bounded_project_budget@1"
        return self._append_budget_event(
            command_id=command_id,
            command_type="gameplay.economy.consume_public_project_budget",
            idempotency_key=idempotency_key,
            request=request,
            causation_id=causation_id,
            correlation_id=correlation_id,
            submitted_at=submitted_at,
            source_ref=activity_event_id,
            expected_economy_revision=expected_economy_stream_revision,
            # Commitment and reservation are on the write stream itself; only
            # the external activity stream belongs in the read set.
            read_set_revisions={activity.stream_id: expected_activity_stream_revision},
            payload=payload,
        )

    def settle_bounded_project_budget_consumption(self, *, intent: object) -> AppendBatchResult:
        try:
            from app.gameplay.closed_generic_gameplay_families import BoundedProjectBudgetConsumptionIntent

            typed = intent if isinstance(intent, BoundedProjectBudgetConsumptionIntent) else BoundedProjectBudgetConsumptionIntent.model_validate(intent)
            commitment = self._store.get_event(typed.commitment_event_id)
            reservation = self._store.get_event(typed.reservation_event_id)
            activity = self._store.get_event(typed.activity_event_id)
        except Exception:
            return self._rejected_append(str(getattr(intent, "command_id", "bounded-project-budget-consumption")), "bounded_project_budget_consumption_source_missing")
        return self.consume_public_project_budget(
            commitment_event_id=commitment.event_id,
            expected_commitment_revision=commitment.stream_revision,
            reservation_event_id=reservation.event_id,
            expected_reservation_revision=reservation.stream_revision,
            activity_event_id=activity.event_id,
            expected_activity_revision=activity.stream_revision,
            expected_economy_stream_revision=self._store.get_stream_head("gameplay:economy"),
            expected_activity_stream_revision=self._store.get_stream_head(activity.stream_id),
            command_id=typed.command_id,
            idempotency_key=f"economy:bounded-project-budget-consumption:{commitment.event_id}:{reservation.event_id}:{activity.event_id}:v1",
            causation_id=typed.causation_id,
            correlation_id=typed.correlation_id,
            submitted_at=typed.submitted_at,
            _family_required=True,
        )

    def public_project_budget_consumption_receipt_for(self, *, result: AppendBatchResult | None, scope: str) -> SettlementReceipt:
        if scope != "authority":
            raise EconomyRuntimeError("public_project_budget_consumption_receipt_scope_denied")
        if result is None:
            raise EconomyRuntimeError("public_project_budget_consumption_receipt_missing")
        return SettlementReceipt.from_append_result(result=result, audit_refs=(f"economy_transaction:{result.transaction_id}",))

    def public_project_budget_consumption_projection(self, *, scope: str, checkpoint_at: int | None = None) -> dict[str, object]:
        if scope != "authority":
            raise EconomyRuntimeError("public_project_budget_consumption_projection_scope_denied")
        if checkpoint_at is not None and checkpoint_at < 0:
            raise EconomyRuntimeError("public_project_budget_consumption_checkpoint_invalid")
        refs = tuple(sorted(event.event_id for event in self._store.read_stream("gameplay:economy") if event.event_type == "gameplay.economy.public_project_budget_consumed"))
        return {"scope": scope, "consumption_refs": refs}

    def close_public_project_budget(
        self,
        *,
        budget_consumed_event_id: str,
        expected_budget_consumed_revision: int,
        execution_event_id: str,
        expected_execution_revision: int,
        expected_economy_stream_revision: int,
        expected_execution_stream_revision: int,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        submitted_at: str,
        _family_required: bool = False,
    ) -> AppendBatchResult:
        prefix = "bounded_project_budget_close" if _family_required else "economy_public_project_budget_close"
        request = {
            "budget_consumed_event_id": budget_consumed_event_id,
            "expected_budget_consumed_revision": expected_budget_consumed_revision,
            "execution_event_id": execution_event_id,
            "expected_execution_revision": expected_execution_revision,
            "expected_execution_stream_revision": expected_execution_stream_revision,
            "causation_id": causation_id,
            "correlation_id": correlation_id,
            "family": _family_required,
        }
        duplicate = self._budget_duplicate_result(command_id=command_id, idempotency_key=idempotency_key, request=request, error_prefix=prefix)
        if duplicate is not None:
            return duplicate
        try:
            consumed = self._store.get_event(budget_consumed_event_id)
            execution = self._store.get_event(execution_event_id)
        except KeyError:
            return self._rejected_append(command_id, f"{prefix}_execution_missing")
        is_family = consumed.payload.get("family_ref") == "bounded_project_budget@1"
        execution_type = (
            "gameplay.construction_production.public_project_step_completed"
            if is_family
            else "gameplay.organization.public_project_execution_recorded"
        )
        if execution.visibility_policy != "project" or execution.event_type != execution_type:
            return self._rejected_append(command_id, f"{prefix}_execution_invalid")
        if (
            self._store.get_stream_head(execution.stream_id) != expected_execution_stream_revision
            or self._store.get_stream_head("gameplay:economy") != expected_economy_stream_revision
        ):
            return self._rejected_append(command_id, f"{prefix}_revision_conflict")
        if (
            consumed.payload.get("project_ref") != execution.payload.get("project_ref")
            or consumed.payload.get("facility_ref") != execution.payload.get("facility_ref")
        ):
            return self._rejected_append(command_id, f"{prefix}_binding_invalid")
        if (
            consumed.event_type != "gameplay.economy.public_project_budget_consumed"
            or consumed.visibility_policy != "authority_only"
            or consumed.stream_revision != expected_budget_consumed_revision
            or execution.stream_revision != expected_execution_revision
        ):
            return self._rejected_append(command_id, f"{prefix}_source_invalid")
        if _family_required and not is_family and self._package_registry is not None:
            return self._rejected_append(command_id, f"{prefix}_source_invalid")
        if not _family_required and is_family:
            return self._rejected_append(command_id, f"{prefix}_source_invalid")
        if is_family and execution.event_id != consumed.payload.get("source_activity_event_id"):
            return self._rejected_append(command_id, f"{prefix}_binding_invalid")
        existing = [
            event for event in self._store.read_stream("gameplay:economy")
            if event.event_type == "gameplay.economy.public_project_budget_closed"
            and event.payload.get("source_budget_consumed_event_id") == budget_consumed_event_id
        ]
        if existing:
            return self._rejected_append(command_id, f"{prefix}_duplicate")
        payload = {
            "event_type": "gameplay.economy.public_project_budget_closed",
            "closure_ref": f"budget-closure:public-project:{str(consumed.payload['project_step_ref']).split(':')[-1].removesuffix('@1')}:{consumed.payload['project_ref']}",
            "project_ref": consumed.payload["project_ref"],
            "facility_ref": consumed.payload["facility_ref"],
            "project_step_ref": consumed.payload["project_step_ref"],
            "status": "closed",
            "terminal": "v1_terminal_no_compensation",
            "source_budget_consumed_event_id": budget_consumed_event_id,
            "source_budget_consumed_revision": consumed.stream_revision,
            "source_execution_event_id": execution_event_id,
            "source_execution_revision": execution.stream_revision,
            "catalog_ref": "inf:economy-public-project-budget-close@1",
            "descriptor_ref": "descriptor:economy-public-project-budget-close@1",
            "policy_revision": "policy:economy-public-project-budget-close@1",
            **{
                key: value
                for key, value in consumed.payload.items()
                if key in {"family_ref", "package_revision", "content_digest", "declaration_ref", "declaration_digest", "binding_ref", "active_patch_set_revision", "source_work_order_ref"}
            },
        }
        if _family_required:
            payload["family_ref"] = "bounded_project_budget@1"
        return self._append_budget_event(
            command_id=command_id,
            command_type="gameplay.economy.close_public_project_budget",
            idempotency_key=idempotency_key,
            request=request,
            causation_id=causation_id,
            correlation_id=correlation_id,
            submitted_at=submitted_at,
            source_ref=execution_event_id,
            expected_economy_revision=expected_economy_stream_revision,
            read_set_revisions={execution.stream_id: expected_execution_stream_revision},
            payload=payload,
        )

    def settle_bounded_project_budget_close(self, *, intent: object) -> AppendBatchResult:
        try:
            from app.gameplay.closed_generic_gameplay_families import BoundedProjectBudgetCloseIntent

            typed = intent if isinstance(intent, BoundedProjectBudgetCloseIntent) else BoundedProjectBudgetCloseIntent.model_validate(intent)
            consumed = self._store.get_event(typed.budget_consumed_event_id)
            execution = self._store.get_event(typed.execution_event_id)
        except Exception:
            return self._rejected_append(str(getattr(intent, "command_id", "bounded-project-budget-close")), "bounded_project_budget_close_source_missing")
        return self.close_public_project_budget(
            budget_consumed_event_id=consumed.event_id,
            expected_budget_consumed_revision=consumed.stream_revision,
            execution_event_id=execution.event_id,
            expected_execution_revision=execution.stream_revision,
            expected_economy_stream_revision=self._store.get_stream_head("gameplay:economy"),
            expected_execution_stream_revision=self._store.get_stream_head(execution.stream_id),
            command_id=typed.command_id,
            idempotency_key=f"economy:bounded-project-budget-close:{consumed.event_id}:{execution.event_id}:v1",
            causation_id=typed.causation_id,
            correlation_id=typed.correlation_id,
            submitted_at=typed.submitted_at,
            _family_required=True,
        )

    def public_project_budget_close_receipt_for(self, *, result: AppendBatchResult | None, scope: str) -> SettlementReceipt:
        if scope != "authority":
            raise EconomyRuntimeError("public_project_budget_close_receipt_scope_denied")
        if result is None:
            raise EconomyRuntimeError("public_project_budget_close_receipt_missing")
        return SettlementReceipt.from_append_result(result=result, audit_refs=(f"economy_transaction:{result.transaction_id}",))

    def public_project_budget_close_projection(self, *, scope: str, checkpoint_at: int | None = None) -> dict[str, object]:
        if scope != "authority":
            raise EconomyRuntimeError("public_project_budget_close_projection_scope_denied")
        if checkpoint_at is not None and checkpoint_at < 0:
            raise EconomyRuntimeError("public_project_budget_close_checkpoint_invalid")
        rows = [event for event in self._store.read_stream("gameplay:economy") if event.event_type == "gameplay.economy.public_project_budget_closed"]
        for event in rows:
            try:
                consumed = self._store.get_event(str(event.payload["source_budget_consumed_event_id"]))
                execution = self._store.get_event(str(event.payload["source_execution_event_id"]))
            except (KeyError, TypeError):
                raise EconomyRuntimeError("public_project_budget_close_projection_provenance_invalid") from None
            family = consumed.payload.get("family_ref") == "bounded_project_budget@1"
            if (
                consumed.event_type != "gameplay.economy.public_project_budget_consumed"
                or (
                    execution.event_id != consumed.payload.get("source_activity_event_id")
                    if family
                    else execution.payload.get("source_budget_consumed_event_id") != consumed.event_id
                )
                or event.payload.get("project_ref") != consumed.payload.get("project_ref")
            ):
                raise EconomyRuntimeError("public_project_budget_close_projection_provenance_invalid")
        refs = tuple(sorted(str(event.payload.get("closure_ref", event.event_id)) for event in rows))
        return {"scope": scope, "closure_refs": refs}

    def record_grain_intake_acceptance(
        self,
        *,
        source_event_id: str,
        expected_source_revision: int,
        expected_economy_stream_revision: int,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        submitted_at: str,
    ) -> AppendBatchResult:
        prefix = "economy_grain_intake_acceptance"
        request = {
            "source_event_id": source_event_id,
            "expected_source_revision": expected_source_revision,
            "causation_id": causation_id,
            "correlation_id": correlation_id,
        }
        duplicate = self._budget_duplicate_result(command_id=command_id, idempotency_key=idempotency_key, request=request, error_prefix=prefix)
        if duplicate is not None:
            return duplicate
        if (
            isinstance(expected_source_revision, bool)
            or expected_source_revision < 1
            or isinstance(expected_economy_stream_revision, bool)
            or expected_economy_stream_revision < 0
        ):
            return self._rejected_append(command_id, "economy_grain_intake_acceptance_reference_invalid")
        try:
            source = self._store.get_event(source_event_id)
            inventory = self._store.get_event(str(source.payload.get("source_inventory_event_id", "")))
        except KeyError:
            return self._rejected_append(command_id, "economy_grain_intake_acceptance_source_invalid")
        source_payload = source.payload
        inventory_payload = inventory.payload
        if (
            source.event_type != "gameplay.organization.grain_intake_recorded@1"
            or source.visibility_policy != "project"
            or source.stream_id != f"gameplay:organization:{source_payload.get('organization_ref', '')}"
            or source.stream_revision != expected_source_revision
            or self._store.get_stream_head(source.stream_id) != expected_source_revision
            or source_payload.get("descriptor_ref") != "descriptor:organization-grain-intake@1"
            or source_payload.get("catalog_ref") != "inf:organization-grain-intake@1"
            or source_payload.get("policy_revision") != "policy:organization-grain-intake@1"
            or not isinstance(source_payload.get("organization_ref"), str)
            or not isinstance(source_payload.get("project_ref"), str)
            or not isinstance(source_payload.get("item_ref"), str)
            or isinstance(source_payload.get("quantity"), bool)
            or not isinstance(source_payload.get("quantity"), int)
            or source_payload.get("quantity", 0) <= 0
            or inventory.event_type != "gameplay.inventory.grain_harvest_received@1"
            or inventory.visibility_policy != "project"
            or inventory_payload.get("actor_ref") != source_payload.get("organization_ref")
            or inventory_payload.get("project_ref") != source_payload.get("project_ref")
            or inventory_payload.get("item_ref") != source_payload.get("item_ref")
            or inventory_payload.get("quantity") != source_payload.get("quantity")
            or inventory_payload.get("container_id") != source_payload.get("container_id")
            or source_payload.get("source_inventory_revision") != inventory.stream_revision
            or self._store.get_stream_head(inventory.stream_id) != inventory.stream_revision
        ):
            return self._rejected_append(command_id, "economy_grain_intake_acceptance_source_invalid")
        if self._store.get_stream_head("gameplay:economy") != expected_economy_stream_revision:
            return self._rejected_append(command_id, "economy_grain_intake_acceptance_revision_conflict")
        if idempotency_key != f"economy:grain-intake-acceptance:{source.event_id}:{source.stream_revision}:{expected_economy_stream_revision}:v1":
            return self._rejected_append(command_id, "economy_grain_intake_acceptance_idempotency_key_invalid")
        acceptance_ref = f"grain-intake-acceptance:{source_payload['organization_ref']}:{source_payload['project_ref']}:{source_payload['item_ref']}"
        if any(
            event.event_type == "gameplay.economy.grain_intake_accepted@1"
            and event.payload.get("source_event_id") == source.event_id
            for event in self._store.read_stream("gameplay:economy")
        ):
            return self._rejected_append(command_id, "economy_grain_intake_acceptance_duplicate")
        payload = {
            "event_type": "gameplay.economy.grain_intake_accepted@1",
            "acceptance_ref": acceptance_ref,
            "organization_ref": source_payload["organization_ref"],
            "project_ref": source_payload["project_ref"],
            "plot_ref": source_payload.get("plot_ref"),
            "item_ref": source_payload["item_ref"],
            "quantity": source_payload["quantity"],
            "container_id": source_payload.get("container_id"),
            "source_event_id": source.event_id,
            "source_event_revision": source.stream_revision,
            "source_stream_id": source.stream_id,
            "source_stream_head": source.stream_revision,
            "source_inventory_event_id": inventory.event_id,
            "source_inventory_revision": inventory.stream_revision,
            "source_inventory_stream_id": inventory.stream_id,
            "economy_stream_head": expected_economy_stream_revision,
            "status": "accepted",
            "policy_revision": "policy:economy-grain-intake-acceptance@1",
            "descriptor_ref": "descriptor:economy-grain-intake-acceptance@1",
            "descriptor_revision": "descriptor:economy-grain-intake-acceptance@1",
            "catalog_ref": "inf:economy-grain-intake-acceptance@1",
        }
        return self._append_budget_event(
            command_id=command_id,
            command_type="gameplay.economy.record_grain_intake_acceptance",
            idempotency_key=idempotency_key,
            request=request,
            causation_id=causation_id,
            correlation_id=correlation_id,
            submitted_at=submitted_at,
            source_ref=source.event_id,
            expected_economy_revision=expected_economy_stream_revision,
            read_set_revisions={source.stream_id: source.stream_revision, inventory.stream_id: inventory.stream_revision},
            payload=payload,
        )

    def record_production_output_market_eligibility(self, *, intent: object) -> AppendBatchResult:
        """Record one account-neutral eligibility marker from Inventory custody."""
        from app.gameplay.inf2ao_market_eligibility import ProductionOutputMarketEligibilityIntent

        try:
            typed = intent if isinstance(intent, ProductionOutputMarketEligibilityIntent) else ProductionOutputMarketEligibilityIntent.model_validate(intent)
        except Exception:
            return self._rejected_append(str(getattr(intent, "command_id", "production-output-market-eligibility")), "production_output_market_eligibility_intent_invalid")
        if isinstance(typed.expected_source_revision, bool) or isinstance(typed.expected_economy_stream_revision, bool):
            return self._rejected_append(typed.command_id, "production_output_market_eligibility_reference_invalid")
        try:
            source = self._store.get_event(typed.source_event_id)
        except KeyError:
            return self._rejected_append(typed.command_id, "production_output_market_eligibility_source_missing")
        payload = source.payload
        if (
            source.event_type != "gameplay.inventory.production_output_received@1"
            or source.visibility_policy != "project"
            or not source.stream_id.startswith("gameplay:inventory:")
            or source.stream_revision != typed.expected_source_revision
            or self._store.get_stream_head(source.stream_id) != typed.expected_source_revision
            or payload.get("family_ref") != "production_output_custody@1"
            or not isinstance(payload.get("item_ref"), str)
            or not payload.get("item_ref")
            or not isinstance(payload.get("quantity"), int)
            or isinstance(payload.get("quantity"), bool)
            or payload.get("quantity", 0) <= 0
            or not isinstance(payload.get("holder_ref"), str)
            or not payload.get("holder_ref")
            or source.stream_id != f"gameplay:inventory:{payload.get('holder_ref', '')}"
            or not isinstance(payload.get("container_id"), str)
            or not payload.get("container_id")
            or not isinstance(payload.get("project_ref"), str)
            or not payload.get("project_ref")
            or not isinstance(payload.get("facility_ref"), str)
            or not payload.get("facility_ref")
            or not isinstance(payload.get("recipe_ref"), str)
            or not payload.get("recipe_ref")
            or not isinstance(payload.get("mapping_revision"), str)
            or not payload.get("mapping_revision")
        ):
            return self._rejected_append(typed.command_id, "production_output_market_eligibility_source_invalid")
        economy_stream = "gameplay:economy"
        idempotency_key = (
            f"economy:production-output-market-eligibility:{source.event_id}:"
            f"{source.stream_revision}:{typed.expected_economy_stream_revision}:v1"
        )
        request = {
            "source_event_id": source.event_id,
            "expected_source_revision": source.stream_revision,
            "expected_economy_stream_revision": typed.expected_economy_stream_revision,
            "causation_id": typed.causation_id,
            "correlation_id": typed.correlation_id,
        }
        duplicate = self._budget_duplicate_result(
            command_id=typed.command_id,
            idempotency_key=idempotency_key,
            request=request,
            error_prefix="production_output_market_eligibility",
        )
        if duplicate is not None:
            return duplicate
        if self._store.get_stream_head(economy_stream) != typed.expected_economy_stream_revision:
            return self._rejected_append(typed.command_id, "production_output_market_eligibility_revision_conflict")
        if typed.causation_id != source.event_id:
            return self._rejected_append(typed.command_id, "production_output_market_eligibility_causation_invalid")
        if any(
            event.event_type == "gameplay.economy.production_output_market_eligible@1"
            and event.payload.get("source_event_id") == source.event_id
            for event in self._store.read_stream(economy_stream)
        ):
            return self._rejected_append(typed.command_id, "production_output_market_eligibility_duplicate")
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:economy-production-output-market-eligibility@1",
                contract_kind="lifecycle",
                owner_ref=self._PRINCIPAL,
                stream_ids=(economy_stream,),
                event_types=("gameplay.economy.production_output_market_eligible@1",),
                projection_scope="authority_only",
            )
        except GovernedAuthorityContractError as error:
            return self._rejected_append(typed.command_id, str(error))
        event_payload = {
            "eligibility_ref": "eligibility:production-output-market-listing@1",
            "source_event_id": source.event_id,
            "source_event_revision": source.stream_revision,
            "source_stream_id": source.stream_id,
            "source_stream_head": source.stream_revision,
            "item_ref": payload["item_ref"],
            "quantity": payload["quantity"],
            "holder_ref": payload["holder_ref"],
            "container_id": payload["container_id"],
            "facility_ref": payload["facility_ref"],
            "project_ref": payload["project_ref"],
            "recipe_ref": payload["recipe_ref"],
            "mapping_revision": payload["mapping_revision"],
            "policy_revision": "policy:economy-production-output-market-eligibility@1",
            "descriptor_ref": "descriptor:economy-production-output-market-eligibility@1",
            "descriptor_revision": "descriptor:economy-production-output-market-eligibility@1",
            "catalog_ref": "inf:economy-production-output-market-eligibility@1",
            "status": "eligible",
            "terminal": "v1_terminal_no_compensation",
        }
        command = GameplayCommandEnvelope(
            command_id=typed.command_id,
            command_type="gameplay.economy.record_production_output_market_eligibility",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=None,
            project_ref=None,
            transaction_id=f"transaction:{typed.command_id}",
            idempotency_key=idempotency_key,
            expected_revisions={economy_stream: typed.expected_economy_stream_revision},
            read_set_revisions={source.stream_id: source.stream_revision},
            causation_id=typed.causation_id,
            correlation_id=typed.correlation_id,
            source_ref=source.event_id,
            submitted_at=typed.submitted_at,
            pinned_revisions={"economy": typed.expected_economy_stream_revision, "inventory_source": source.stream_revision},
            payload={
                "stream_ref": economy_stream,
                "event_type": "gameplay.economy.production_output_market_eligible@1",
                "event_specs": [{"event_type": "gameplay.economy.production_output_market_eligible@1", "payload": {**event_payload, "visibility_policy": "authority_only"}}],
            },
        )
        batch = SettlementPlan.from_command_envelope(command).to_atomic_event_batch()
        batch = batch.model_copy(
            update={
                "idempotency_record": batch.idempotency_record.model_copy(
                    update={"payload_digest": _digest(request)}, deep=True
                ),
                "outbox_entries": [
                    GameplayOutboxEntry(
                        outbox_id=f"outbox:{event.event_id}",
                        transaction_id=batch.transaction_id,
                        event_id=event.event_id,
                        global_sequence=0,
                        topic="economy.production_output_market_eligibility.scoped_projection",
                        audience="authority:economy",
                        payload_projection={"eligibility_ref": event_payload["eligibility_ref"], "source_event_id": source.event_id},
                    )
                    for event in batch.events
                ],
            },
            deep=True,
        )
        return self._store.append_batch(batch)

    def production_output_market_eligibility_receipt_for(self, *, result: AppendBatchResult | None, scope: str) -> SettlementReceipt:
        if scope != "authority":
            raise EconomyRuntimeError("production_output_market_eligibility_receipt_scope_denied")
        if result is None or not result.committed or len(result.committed_event_ids) != 1:
            raise EconomyRuntimeError("production_output_market_eligibility_receipt_missing")
        return SettlementReceipt.from_append_result(result=result, audit_refs=(f"economy_production_output_market_eligibility:{result.transaction_id}",))

    def production_output_market_eligibility_projection(self, *, scope: str, checkpoint_at: int | None = None) -> dict[str, object]:
        if scope != "authority":
            raise EconomyRuntimeError("production_output_market_eligibility_projection_scope_denied")
        events = sorted(self._store.read_stream("gameplay:economy"), key=lambda event: (event.global_sequence, event.event_id))
        if checkpoint_at is not None and (isinstance(checkpoint_at, bool) or checkpoint_at < 0 or checkpoint_at > max((event.global_sequence for event in events), default=0)):
            raise EconomyRuntimeError("production_output_market_eligibility_checkpoint_invalid")
        rows: dict[str, dict[str, object]] = {}
        source_revisions: dict[str, int] = {"gameplay:economy": self._store.get_stream_head("gameplay:economy")}
        for event in events:
            if event.event_type != "gameplay.economy.production_output_market_eligible@1":
                continue
            payload = event.payload
            try:
                source = self._store.get_event(str(payload["source_event_id"]))
                certification = self._store.get_event(str(source.payload["source_certification_event_id"]))
            except (KeyError, TypeError) as exc:
                raise EconomyRuntimeError("production_output_market_eligibility_projection_source_invalid") from exc
            if (
                event.visibility_policy != "authority_only"
                or event.causation_id != source.event_id
                or payload.get("status") != "eligible"
                or payload.get("eligibility_ref") != "eligibility:production-output-market-listing@1"
                or payload.get("source_stream_id") != source.stream_id
                or payload.get("source_stream_head") != source.stream_revision
                or payload.get("policy_revision") != "policy:economy-production-output-market-eligibility@1"
                or payload.get("descriptor_ref") != "descriptor:economy-production-output-market-eligibility@1"
                or payload.get("descriptor_revision") != "descriptor:economy-production-output-market-eligibility@1"
                or payload.get("catalog_ref") != "inf:economy-production-output-market-eligibility@1"
                or payload.get("terminal") != "v1_terminal_no_compensation"
                or source.event_type != "gameplay.inventory.production_output_received@1"
                or source.visibility_policy != "project"
                or source.stream_id != f"gameplay:inventory:{source.payload.get('holder_ref', '')}"
                or source.stream_revision != payload.get("source_event_revision")
                or source.payload.get("family_ref") != "production_output_custody@1"
                or certification.event_type != "gameplay.construction_production.production_output_certified@1"
                or certification.visibility_policy != "project"
                or certification.payload.get("facility_ref") != source.payload.get("facility_ref")
                or certification.payload.get("project_ref") != source.payload.get("project_ref")
                or certification.payload.get("recipe_ref") != source.payload.get("recipe_ref")
                or certification.payload.get("output_item") != source.payload.get("item_ref")
                or certification.payload.get("quantity") != source.payload.get("quantity")
                or source.payload.get("source_certification_revision") != certification.stream_revision
                or payload.get("item_ref") != source.payload.get("item_ref")
                or payload.get("quantity") != source.payload.get("quantity")
                or payload.get("holder_ref") != source.payload.get("holder_ref")
                or payload.get("container_id") != source.payload.get("container_id")
                or payload.get("facility_ref") != source.payload.get("facility_ref")
                or payload.get("project_ref") != source.payload.get("project_ref")
                or payload.get("recipe_ref") != source.payload.get("recipe_ref")
                or payload.get("mapping_revision") != source.payload.get("mapping_revision")
            ):
                raise EconomyRuntimeError("production_output_market_eligibility_projection_source_invalid")
            source_revisions[source.stream_id] = max(source_revisions.get(source.stream_id, 0), source.stream_revision)
            rows[str(payload.get("eligibility_ref", event.event_id))] = dict(payload)
        return {"scope": scope, "rows": dict(sorted(rows.items())), "source_revision_vector": source_revisions}

    def _settle_family_exchange(self, *, intent: object, family_ref: str) -> AppendBatchResult:
        content = None
        declaration_pin = None
        try:
            from app.gameplay.closed_generic_gameplay_families import DeclaredExchangeIntent, FixedServiceExchangeIntent
            typed = intent
            if family_ref == "declared_exchange@1":
                typed = intent if isinstance(intent, DeclaredExchangeIntent) else DeclaredExchangeIntent.model_validate(intent)
                source = self._store.get_event(typed.source_event_id)
            else:
                typed = intent if isinstance(intent, FixedServiceExchangeIntent) else FixedServiceExchangeIntent.model_validate(intent)
                source = None
        except Exception:
            return self._rejected_append(str(getattr(intent, "command_id", "family-exchange")), f"{family_ref}_intent_invalid")
        if family_ref == "declared_exchange@1":
            if source.stream_revision != typed.expected_source_revision:
                return self._rejected_append(typed.command_id, "declared_exchange_source_revision_invalid")
            if self._store.get_stream_head(source.stream_id) != typed.expected_source_revision or (
                source.event_type == "gameplay.inventory.mill_flour_output_received@1" and source.visibility_policy != "project"
            ) or (source.event_type == "gameplay.contract.record_fulfilled" and source.visibility_policy != "authority_only"):
                return self._rejected_append(typed.command_id, "declared_exchange_source_invalid")
            source_item = source.payload.get("item_ref")
            source_service = source.payload.get("service_ref") or source.payload.get("terms_ref")
            if source.event_type == "gameplay.contract.record_fulfilled" and not source_service:
                contract_record = next(
                    (
                        record
                        for record in ContractProjector().rebuild(
                            self._store.read_stream("gameplay:contracts")
                        ).contracts.values()
                        if record.contract_id == source.payload.get("contract_id")
                    ),
                    None,
                )
                source_service = contract_record.terms_ref if contract_record is not None else None
            candidates = []
            family_bound_revisions: set[str] = set()
            registry = self._package_registry
            active = getattr(registry, "active_patch_set", None) if registry is not None else None
            if active is not None:
                try:
                    manifests = registry.active_manifests(active.active_patch_set_revision)
                    for manifest in manifests:
                        extension = getattr(manifest, "platform_extension", None)
                        if extension is None:
                            continue
                        declarations = {item.declaration_ref: item for item in extension.outcome_declarations}
                        for request in extension.capability_binding_requests:
                            if request.capability_ref != "capability:declared-exchange@1":
                                continue
                            declaration = declarations.get(request.declaration_ref)
                            if declaration is None:
                                continue
                            family_bound_revisions.add(str(manifest.patch_revision_id))
                            definitions = tuple(item for item in extension.package_definitions if item.definition_ref in declaration.definition_refs)
                            if len(definitions) != 1:
                                continue
                            content = definitions[0].typed_content
                            matches = (
                                source_item is not None
                                and content.get("tradeable_definition_ref") == f"definition:{source_item}"
                            ) or (
                                source_service is not None
                                and content.get("service_definition_ref") == f"definition:{source_service}"
                            )
                            if matches:
                                outcome = next((item for item in getattr(manifest, "economic_outcomes", ()) if item.outcome_ref == content.get("outcome_ref")), None)
                                if outcome is None:
                                    # A declaration without a matching immutable
                                    # economic outcome is incomplete. Never infer
                                    # currency or amount from source kind/content.
                                    continue
                                if outcome.price_policy.fixed_amount is None:
                                    # Bounded prices require an explicit,
                                    # owner-authorized amount. This intent has
                                    # no amount slot, so fail closed rather
                                    # than append zero or choose a bound.
                                    continue
                                candidates.append((manifest, declaration, content, outcome, request))
                except Exception:
                    pass
            if len(candidates) != 1:
                legacy_candidates = []
                if active is not None:
                    try:
                        for manifest in registry.active_manifests(active.active_patch_set_revision):
                            if str(manifest.patch_revision_id) in family_bound_revisions:
                                continue
                            for outcome in getattr(manifest, "economic_outcomes", ()):
                                if (source_item and outcome.tradeable_ref == source_item) or (source.event_type == "gameplay.contract.record_fulfilled" and outcome.source_evidence_mode == "completed_service@1"):
                                    legacy_candidates.append((manifest, outcome))
                    except Exception:
                        pass
                if len(legacy_candidates) != 1:
                    return self._rejected_append(typed.command_id, "declared_exchange_source_invalid")
                manifest, outcome = legacy_candidates[0]
                if source.event_type == "gameplay.contract.record_fulfilled":
                    record = next((item for item in ContractProjector().rebuild(self._store.read_stream("gameplay:contracts")).contracts.values() if item.contract_id == source.payload.get("contract_id")), None)
                    if record is None:
                        return self._rejected_append(typed.command_id, "declared_exchange_source_invalid")
                    provider_ref, receiver_ref = record.party_refs
                else:
                    provider_ref = str(source.payload.get("provider_ref") or source.payload.get("actor_ref") or "")
                    accounts = self._projector.rebuild(self._store.read_events()).accounts.values()
                    buyers = [account.owner_ref for account in accounts if account.owner_ref != provider_ref and account.currency_ref == outcome.price_policy.currency_ref and account.balance >= int(outcome.price_policy.fixed_amount or 0)]
                    if len(buyers) != 1:
                        return self._rejected_append(typed.command_id, "declared_exchange_source_invalid")
                    receiver_ref = buyers[0]
                package_revision, outcome_ref = manifest.patch_revision_id, outcome.outcome_ref
                amount, currency = int(outcome.price_policy.fixed_amount or 0), outcome.price_policy.currency_ref
                source_mode = outcome.source_evidence_mode
                source_ids = [source.event_id]
                if source.event_type == "gameplay.contract.record_fulfilled":
                    contract_events = self._store.read_stream("gameplay:contracts")
                    source_ids = [
                        event.event_id for event in contract_events
                        if event.payload.get("contract_id") == source.payload.get("contract_id")
                        and event.event_type in {"gameplay.contract.service_completion_recorded", "gameplay.contract.record_fulfilled"}
                    ]
                content = None
            else:
                manifest, declaration, content, outcome, binding_request = candidates[0]
                if source.event_type == "gameplay.contract.record_fulfilled":
                    record = next(
                        (
                            item
                            for item in ContractProjector()
                            .rebuild(self._store.read_stream("gameplay:contracts"))
                            .contracts.values()
                            if item.contract_id == source.payload.get("contract_id")
                        ),
                        None,
                    )
                    if record is None or len(record.party_refs) != 2:
                        return self._rejected_append(typed.command_id, "declared_exchange_source_invalid")
                    provider_ref, receiver_ref = record.party_refs
                else:
                    provider_ref = str(source.payload.get("provider_ref") or source.payload.get("actor_ref") or "")
                    receiver_ref = ""
                projection = self._projector.rebuild(self._store.read_events())
                if not receiver_ref:
                    receiver_accounts = [account for account in projection.accounts.values() if account.owner_ref != provider_ref and account.currency_ref == outcome.price_policy.currency_ref and account.balance >= int(outcome.price_policy.fixed_amount or 0)]
                    if len(receiver_accounts) != 1:
                        return self._rejected_append(typed.command_id, "declared_exchange_party_account_unavailable")
                    receiver_ref = receiver_accounts[0].owner_ref
                package_revision = manifest.patch_revision_id
                outcome_ref = outcome.outcome_ref
                amount = int(outcome.price_policy.fixed_amount or 0)
                currency = outcome.price_policy.currency_ref
                source_ids = [source.event_id]
                source_mode = "inventory_custody@1" if source_item else "completed_service@1"
        else:
            registry = self._package_registry
            active = getattr(registry, "active_patch_set", None) if registry is not None else None
            candidates = []
            if active is not None:
                try:
                    contract_records = tuple(
                        record
                        for record in ContractProjector()
                        .rebuild(self._store.read_stream("gameplay:contracts"))
                        .contracts.values()
                        if record.status == "fulfilled"
                    )
                    for manifest in registry.active_manifests(active.active_patch_set_revision):
                        for outcome in getattr(manifest, "economic_outcomes", ()):
                            if outcome.source_evidence_mode != "completed_service@1" or outcome.price_policy.fixed_amount is None:
                                continue
                            matching_records = tuple(
                                record
                                for record in contract_records
                                if record.terms_ref == outcome.typed_service_ref
                            )
                            for record in matching_records:
                                candidates.append((manifest, outcome, record))
                except Exception:
                    pass
            if len(candidates) != 1:
                return self._rejected_append(typed.command_id, "fixed_service_exchange_source_invalid")
            manifest, outcome, record = candidates[0]
            if len(record.party_refs) != 2:
                return self._rejected_append(typed.command_id, "fixed_service_exchange_source_invalid")
            provider_ref, receiver_ref = record.party_refs
            package_revision, outcome_ref = manifest.patch_revision_id, outcome.outcome_ref
            amount, currency, source_ids, source_mode = int(outcome.price_policy.fixed_amount or 0), outcome.price_policy.currency_ref, [], "completed_service@1"
            try:
                declarations = tuple(
                    item
                    for item in (manifest.platform_extension.outcome_declarations if manifest.platform_extension else ())
                    if item.policy_revision_ref == outcome.price_policy.price_policy_revision
                    and item.source_package_revision == manifest.patch_revision_id
                )
                declaration_pin = declarations[0] if len(declarations) == 1 else None
            except (AttributeError, IndexError):
                declaration_pin = None
        request_digest = _digest(typed.model_dump(mode="json"))
        identity = getattr(typed, "proposal_digest", None) or getattr(typed, "source_event_id", "source")
        key = f"economy:{family_ref}:{identity}:v1"
        duplicate = self._budget_duplicate_result(command_id=typed.command_id, idempotency_key=key, request={"family": family_ref, "digest": request_digest}, error_prefix=family_ref)
        if duplicate is not None:
            if not duplicate.committed and duplicate.failure is not None and duplicate.failure.error_code.endswith("_idempotency_key_reused"):
                return self._rejected_append(typed.command_id, "idempotency_key_reused")
            return duplicate
        projection = self._projector.rebuild(self._store.read_events())
        provider = next((account for account in projection.accounts.values() if account.owner_ref == provider_ref and account.currency_ref == currency), None)
        receiver = next((account for account in projection.accounts.values() if account.owner_ref == receiver_ref and account.currency_ref == currency), None)
        if provider is None or receiver is None or receiver.balance < amount:
            return self._rejected_append(typed.command_id, f"{family_ref}_party_account_unavailable")
        stream = "gameplay:economy"
        expected = self._store.get_stream_head(stream)
        payload = {
            "family_ref": family_ref,
            "economic_outcome_id": "package_declared_negotiated_exchange@1",
            "outcome_ref": outcome_ref,
            "proposal_digest": getattr(typed, "proposal_digest", None) or typed.source_event_id,
            "package_revision_id": package_revision,
            "currency_ref": currency,
            "amount_minor": amount,
            "provider_ref": provider_ref,
            "receiver_ref": receiver_ref,
            "provider_account_ref": provider.account_id,
            "receiver_account_ref": receiver.account_id,
            "source_event_ids": source_ids,
            "source_evidence_mode": source_mode,
            "status": "settled",
        }
        if family_ref == "fixed_service_exchange@1" and declaration_pin is not None:
            payload.update(
                {
                    "package_revision": manifest.patch_revision_id,
                    "content_digest": manifest.content_digest,
                    "declaration_ref": declaration_pin.declaration_ref,
                    "declaration_digest": declaration_pin.declaration_digest,
                    "active_patch_set_revision": self._package_registry.active_patch_set.active_patch_set_revision if self._package_registry is not None and self._package_registry.active_patch_set is not None else "",
                }
            )
        if content is not None:
            payload.update(
                {
                    "package_revision": manifest.patch_revision_id,
                    "content_digest": manifest.content_digest,
                    "declaration_ref": declaration.declaration_ref,
                    "declaration_digest": declaration.declaration_digest,
                    "binding_ref": binding_request.binding_ref,
                    "active_patch_set_revision": active.active_patch_set_revision,
                }
            )
        command = GameplayCommandEnvelope(command_id=typed.command_id, command_type=f"gameplay.economy.settle_{family_ref}", command_version=1, principal_ref=self._PRINCIPAL, actor_ref=None, project_ref=None, transaction_id=f"transaction:{typed.command_id}", idempotency_key=key, expected_revisions={stream: expected}, read_set_revisions={}, causation_id=typed.causation_id, correlation_id=typed.correlation_id, source_ref=source_ids[0] if source_ids else f"exchange:{outcome_ref}", submitted_at=getattr(typed, "submitted_at", "exchange"), pinned_revisions={"economy": expected}, payload={"stream_ref": stream, "event_specs":[{"event_type":"gameplay.economy.account_debited","payload":{"account_id":receiver.account_id,"amount":amount,"currency_ref":currency,"visibility_policy":"authority_only"}},{"event_type":"gameplay.economy.account_credited","payload":{"account_id":provider.account_id,"amount":amount,"currency_ref":currency,"visibility_policy":"authority_only"}},{"event_type":"gameplay.economy.package_declared_negotiated_exchange_settled","payload":{**payload,"visibility_policy":"authority_only"}}]})
        batch = SettlementPlan.from_command_envelope(command).to_atomic_event_batch()
        batch = batch.model_copy(update={"idempotency_record": batch.idempotency_record.model_copy(update={"payload_digest": _digest({"family": family_ref, "digest": request_digest})}, deep=True)}, deep=True)
        return self._store.append_batch(batch)

    def settle_declared_exchange(self, *, intent: object) -> AppendBatchResult:
        return self._settle_family_exchange(intent=intent, family_ref="declared_exchange@1")

    def settle_fixed_service_exchange(self, *, intent: object) -> AppendBatchResult:
        return self._settle_family_exchange(intent=intent, family_ref="fixed_service_exchange@1")

    def declared_exchange_receipt_for(self, *, result: AppendBatchResult | None, scope: str) -> SettlementReceipt:
        if scope != "authority":
            raise EconomyRuntimeError("declared_exchange_receipt_scope_denied")
        if result is None:
            raise EconomyRuntimeError("declared_exchange_receipt_missing")
        return SettlementReceipt.from_append_result(result=result, audit_refs=(f"economy_transaction:{result.transaction_id}",))

    def declared_exchange_projection(self, *, scope: str, checkpoint_at: int | None = None) -> dict[str, object]:
        return self.package_declared_negotiated_exchange_projection(scope=scope, checkpoint_at=checkpoint_at)

    @staticmethod
    def grain_intake_acceptance_receipt_for(*, result: AppendBatchResult | None, scope: str) -> SettlementReceipt:
        if scope != "authority":
            raise EconomyRuntimeError("grain_intake_acceptance_receipt_scope_denied")
        if result is None:
            raise EconomyRuntimeError("grain_intake_acceptance_receipt_missing")
        return SettlementReceipt.from_append_result(result=result, audit_refs=(f"economy_transaction:{result.transaction_id}",))

    def grain_intake_acceptance_projection(self, *, scope: str, checkpoint_at: int | None = None) -> dict[str, object]:
        if scope != "authority":
            raise EconomyRuntimeError("grain_intake_acceptance_projection_scope_denied")
        if checkpoint_at is not None and (isinstance(checkpoint_at, bool) or checkpoint_at < 0):
            raise EconomyRuntimeError("grain_intake_acceptance_checkpoint_invalid")
        refs: list[str] = []
        for event in self._store.read_stream("gameplay:economy"):
            if event.event_type != "gameplay.economy.grain_intake_accepted@1":
                continue
            payload = event.payload
            try:
                source = self._store.get_event(str(payload["source_event_id"]))
                inventory = self._store.get_event(str(payload["source_inventory_event_id"]))
            except KeyError:
                raise EconomyRuntimeError("grain_intake_acceptance_projection_source_invalid") from None
            if (
                event.visibility_policy != "authority_only"
                or event.causation_id != source.event_id
                or payload.get("source_event_revision") != source.stream_revision
                or payload.get("source_inventory_revision") != inventory.stream_revision
                or not isinstance(payload.get("acceptance_ref"), str)
                or not payload.get("acceptance_ref")
                or payload.get("organization_ref") != source.payload.get("organization_ref")
                or payload.get("project_ref") != source.payload.get("project_ref")
                or payload.get("item_ref") != source.payload.get("item_ref")
                or payload.get("quantity") != source.payload.get("quantity")
                or payload.get("economy_stream_head") != event.stream_revision - 1
            ):
                raise EconomyRuntimeError("grain_intake_acceptance_projection_source_invalid")
            refs.append(str(payload["acceptance_ref"]))
        return {"scope": scope, "acceptance_refs": tuple(sorted(refs))}

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
    def record_tax_due(self, *, command_id:str, organization_ref:str, period_ref:str, assessed_amount_minor:int, policy_revision:str, policy_digest:str, due_calendar_ref:str, evidence_refs:tuple[str,...], source_digest:str, idempotency_key:str, causation_id:str, correlation_id:str, jurisdiction_ref: str | None = None, currency_ref: str | None = None)->AppendBatchResult:
        p=self._projector.rebuild(self._store.read_events())
        if not all((organization_ref, period_ref, policy_revision, policy_digest, due_calendar_ref, source_digest, evidence_refs)) or assessed_amount_minor < 0: raise EconomyRuntimeError("economy_tax_assessment_invalid")
        admission_fields = (jurisdiction_ref, currency_ref)
        if any(value is not None for value in admission_fields) and not all(isinstance(value, str) and value for value in admission_fields):
            raise EconomyRuntimeError("economy_tax_payment_source_invalid")
        payload={"organization_ref":organization_ref,"period_ref":period_ref,"assessed_amount_minor":assessed_amount_minor,"policy_revision":policy_revision,"policy_digest":policy_digest,"due_calendar_ref":due_calendar_ref,"evidence_refs":evidence_refs,"source_digest":source_digest}
        if jurisdiction_ref is not None:
            payload.update({
                "jurisdiction_ref": jurisdiction_ref,
                "currency_ref": currency_ref,
            })
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
def _optional_text(p: Mapping[str, object], k: str) -> str | None:
    value = p.get(k)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise EconomyRuntimeError("economy_event_payload_invalid")
    return value
def _nonnegative(p:Mapping[str,object],k:str)->int:
    v=p.get(k)
    if isinstance(v,bool) or not isinstance(v,int) or v<0: raise EconomyRuntimeError("economy_event_payload_invalid")
    return v
def _optional_nonnegative(p: Mapping[str, object], k: str) -> int | None:
    value = p.get(k)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise EconomyRuntimeError("economy_event_payload_invalid")
    return value
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


def _validate_public_project_budget_provenance(events: Sequence[GameplayEvent]) -> None:
    by_id = {event.event_id: event for event in events}
    for event in events:
        payload = event.payload
        if event.event_type == "gameplay.economy.public_project_budget_commitment_recorded":
            source = by_id.get(str(payload.get("source_event_id", "")))
            if (
                source is None
                or source.event_type != "gameplay.construction_production.public_project_step_completed"
                or payload.get("source_event_revision") != source.stream_revision
                or payload.get("source_stream_id") != source.stream_id
                or payload.get("project_ref") != source.payload.get("project_ref")
                or payload.get("facility_ref") != source.payload.get("facility_ref")
                or payload.get("project_step_ref") != source.payload.get("project_step_ref")
            ):
                raise EconomyRuntimeError("economy_public_project_budget_source_invalid")
        elif event.event_type == "gameplay.economy.budget_reserved" and "source_commitment_event_id" in payload:
            source = by_id.get(str(payload.get("source_commitment_event_id", "")))
            acquisition = by_id.get(str(payload.get("source_acquisition_event_id", "")))
            if (
                source is None
                or source.event_type != "gameplay.economy.public_project_budget_commitment_recorded"
                or payload.get("source_commitment_revision") != source.stream_revision
                or payload.get("amount_minor") != source.payload.get("amount_minor")
                or payload.get("currency_ref") != source.payload.get("currency_ref")
                or payload.get("project_ref") != source.payload.get("project_ref")
                or acquisition is None
                or acquisition.event_type != "gameplay.construction_production.facility_acquired"
                or payload.get("source_acquisition_revision") != acquisition.stream_revision
                or payload.get("facility_ref") != acquisition.payload.get("facility_ref")
            ):
                raise EconomyRuntimeError("economy_public_project_budget_reservation_source_invalid")
        elif event.event_type == "gameplay.economy.public_project_budget_consumed":
            commitment = by_id.get(str(payload.get("source_commitment_event_id", "")))
            reservation = by_id.get(str(payload.get("source_reservation_event_id", "")))
            activity = by_id.get(str(payload.get("source_activity_event_id", "")))
            if (
                commitment is None
                or reservation is None
                or activity is None
                or commitment.event_type != "gameplay.economy.public_project_budget_commitment_recorded"
                or reservation.event_type != "gameplay.economy.budget_reserved"
                or payload.get("amount_minor") != commitment.payload.get("amount_minor")
                or payload.get("currency_ref") != commitment.payload.get("currency_ref")
                or payload.get("project_ref") != activity.payload.get("project_ref")
                or commitment.payload.get("catalog_ref") != "inf:economy-public-project-budget-commitment@1"
                or (
                    (
                        activity.event_type != "gameplay.construction_production.public_project_step_completed"
                        or commitment.payload.get("family_ref") != "bounded_project_budget@1"
                        or activity.event_id != commitment.payload.get("source_event_id")
                    )
                    if commitment.payload.get("family_ref") == "bounded_project_budget@1"
                    else (
                        activity.event_type != "gameplay.organization.public_workshop_activity_recorded"
                        or activity.payload.get("service_ref") != "service:industrial-facility-public-workshop-session@1"
                    )
                )
            ):
                raise EconomyRuntimeError("economy_public_project_budget_consumption_source_invalid")
        elif event.event_type == "gameplay.economy.public_project_budget_closed":
            consumed = by_id.get(str(payload.get("source_budget_consumed_event_id", "")))
            execution = by_id.get(str(payload.get("source_execution_event_id", "")))
            family = consumed is not None and consumed.payload.get("family_ref") == "bounded_project_budget@1"
            if (
                consumed is None
                or execution is None
                or consumed.event_type != "gameplay.economy.public_project_budget_consumed"
                or execution.event_type != (
                    "gameplay.construction_production.public_project_step_completed"
                    if family
                    else "gameplay.organization.public_project_execution_recorded"
                )
                or payload.get("project_ref") != consumed.payload.get("project_ref")
                or payload.get("facility_ref") != consumed.payload.get("facility_ref")
                or (
                    execution.event_id != consumed.payload.get("source_activity_event_id")
                    if family
                    else execution.payload.get("source_budget_consumed_event_id") != consumed.event_id
                )
            ):
                raise EconomyRuntimeError("economy_public_project_budget_close_source_invalid")

__all__=["Account","BudgetReservation","EconomyAuthorityService","EconomyProjection","EconomyProjector","EconomyRuntimeError","ScheduledAccountTransferPolicyInstance","TaxDue","TaxObligationResult"]
