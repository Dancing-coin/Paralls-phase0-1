"""Typed-terms contract records without an arbitrary contract execution engine."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Mapping, Sequence

from pydantic import ConfigDict, Field

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog, GovernedAuthorityContractError
from app.gameplay.models import AppendBatchResult, GameplayEvent, GameplayFailure, StrictGameplayModel
from app.gameplay.settlement_plan import SettlementPlan as EventStoreSettlementPlan
from app.gameplay.shared_contracts import GameplayCommandEnvelope


class ContractRuntimeError(ValueError):
    pass


class GovernmentDroughtAssessmentContractIntentV1(StrictGameplayModel):
    """Caller request for the one fixed advisory-to-contract admission row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    advisory_event_id: str = Field(min_length=1)
    expected_advisory_revision: int = Field(ge=1)
    expected_contract_revision: int = Field(ge=0)
    command_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    submitted_at: str = Field(min_length=1)


class MunicipalDroughtAssessmentFulfillmentIntentV1(StrictGameplayModel):
    """Caller request for the one fixed municipal assessment fulfillment row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_created_event_id: str = Field(min_length=1)
    expected_contract_created_revision: int = Field(ge=1)
    expected_advisory_revision: int = Field(ge=1)
    expected_contract_head: int = Field(ge=1)
    command_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    submitted_at: str = Field(min_length=1)


class FacilityCommissioningReviewContractIntentV1(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operational_verification_event_id: str = Field(min_length=1)
    expected_operational_verification_revision: int = Field(ge=1)
    expected_contract_revision: int = Field(ge=0)
    command_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    submitted_at: str = Field(min_length=1)


class FacilityCommissioningReviewFulfillmentIntentV1(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_created_event_id: str = Field(min_length=1)
    expected_contract_created_revision: int = Field(ge=1)
    expected_operational_verification_revision: int = Field(ge=1)
    expected_contract_head: int = Field(ge=1)
    command_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    submitted_at: str = Field(min_length=1)


class PublicWorkshopSessionContractIntentV1(StrictGameplayModel):
    """Source-bound admission for the exact public-workshop service row."""

    public_use_event_id: str = Field(min_length=1)
    expected_public_use_revision: int = Field(ge=1)
    expected_contract_revision: int = Field(ge=0)
    command_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    submitted_at: str = Field(min_length=1)


class PublicMillingSessionContractIntentV1(StrictGameplayModel):
    """Source-bound admission for the exact reinforced-mill service row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    public_use_event_id: str = Field(min_length=1)
    expected_public_use_revision: int = Field(ge=1)
    expected_contract_revision: int = Field(ge=0)
    command_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    submitted_at: str = Field(min_length=1)


class PublicWorkshopSessionFulfillmentIntentV1(StrictGameplayModel):
    """Fulfillment request for the exact public-workshop service row."""

    contract_created_event_id: str = Field(min_length=1)
    expected_contract_created_revision: int = Field(ge=1)
    expected_public_use_revision: int = Field(ge=1)
    expected_contract_head: int = Field(ge=1)
    command_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    submitted_at: str = Field(min_length=1)


class PublicMillingSessionFulfillmentIntentV1(StrictGameplayModel):
    """Fulfillment request for the exact reinforced-mill service row."""

    contract_created_event_id: str = Field(min_length=1)
    expected_contract_created_revision: int = Field(ge=1)
    expected_public_use_revision: int = Field(ge=1)
    expected_contract_head: int = Field(ge=1)
    command_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    submitted_at: str = Field(min_length=1)


@dataclass(frozen=True)
class ContractTermsDefinition:
    terms_ref: str
    contract_type: str
    party_count: int
    completion_evidence_kind: str | None = None


class ContractTermsRegistry:
    _SUPPORTED_TYPES = {"simple_transfer", "simple_service"}

    def __init__(self) -> None:
        self._definitions: dict[str, ContractTermsDefinition] = {}

    def register(self, definition: ContractTermsDefinition) -> None:
        if not definition.terms_ref or definition.terms_ref in self._definitions or definition.contract_type not in self._SUPPORTED_TYPES or definition.party_count < 2:
            raise ContractRuntimeError("contract_terms_invalid")
        if definition.completion_evidence_kind is not None and (definition.contract_type != "simple_service" or not definition.completion_evidence_kind):
            raise ContractRuntimeError("contract_terms_invalid")
        self._definitions[definition.terms_ref] = definition

    def get(self, terms_ref: str) -> ContractTermsDefinition:
        try:
            return self._definitions[terms_ref]
        except KeyError as exc:
            raise ContractRuntimeError("contract_terms_unknown") from exc


@dataclass(frozen=True)
class ContractRecord:
    contract_id: str
    contract_type: str
    terms_ref: str
    party_refs: tuple[str, ...]
    completion_evidence_kind: str | None
    completion_evidence_ref: str | None
    status: str
    source_event_id: str


@dataclass(frozen=True)
class ContractProjection:
    contracts: Mapping[str, ContractRecord]
    source_revision_vector: Mapping[str, int]


class ContractProjector:
    _EVENT_TYPES = {
        "gameplay.contract.record_created",
        "gameplay.contract.record_fulfilled",
        "gameplay.contract.record_terminated",
        "gameplay.contract.service_completion_recorded",
    }

    def rebuild(
        self, events: Sequence[GameplayEvent], *, checkpoint_at: int | None = None
    ) -> ContractProjection:
        if checkpoint_at is None:
            return self._reduce(events)
        if checkpoint_at < 0:
            raise ContractRuntimeError("contract_checkpoint_invalid")
        prefix = self._reduce(
            [event for event in events if event.global_sequence <= checkpoint_at]
        )
        return self._reduce(
            [event for event in events if event.global_sequence > checkpoint_at],
            contracts=dict(prefix.contracts),
            revisions=dict(prefix.source_revision_vector),
        )

    def _reduce(
        self,
        events: Sequence[GameplayEvent],
        *,
        contracts: dict[str, ContractRecord] | None = None,
        revisions: dict[str, int] | None = None,
    ) -> ContractProjection:
        contracts = dict(contracts or {})
        revisions = dict(revisions or {})
        for event in sorted(events, key=lambda value: (value.global_sequence, value.event_id)):
            if event.event_type not in self._EVENT_TYPES:
                continue
            payload = event.payload
            contract_id = _text(payload, "contract_id")
            if event.event_type == "gameplay.contract.record_created":
                if contract_id in contracts:
                    raise ContractRuntimeError("contract_duplicate")
                contract_type = _text(payload, "contract_type")
                if contract_type not in ContractTermsRegistry._SUPPORTED_TYPES:
                    raise ContractRuntimeError("contract_type_invalid")
                party_refs = _party_refs(payload)
                contracts[contract_id] = ContractRecord(
                    contract_id=contract_id,
                    contract_type=contract_type,
                    terms_ref=_text(payload, "terms_ref"),
                    party_refs=party_refs,
                    completion_evidence_kind=_optional_text(payload, "completion_evidence_kind"),
                    completion_evidence_ref=None,
                    status="active",
                    source_event_id=event.event_id,
                )
            elif event.event_type == "gameplay.contract.service_completion_recorded":
                prior = contracts.get(contract_id)
                completion_evidence_kind = _text(payload, "completion_evidence_kind")
                completion_evidence_ref = _text(payload, "completion_evidence_ref")
                if prior is None or prior.status != "active" or prior.contract_type != "simple_service" or prior.completion_evidence_kind != completion_evidence_kind or prior.completion_evidence_ref is not None:
                    raise ContractRuntimeError("contract_completion_evidence_invalid")
                _text(payload, "authority_ref")
                contracts[contract_id] = ContractRecord(**{**prior.__dict__, "completion_evidence_ref": completion_evidence_ref, "source_event_id": event.event_id})
            else:
                prior = contracts.get(contract_id)
                if prior is None or prior.status != "active":
                    raise ContractRuntimeError("contract_not_active")
                _text(payload, "authority_ref")
                if event.event_type.endswith("terminated"):
                    _text(payload, "reason")
                    status = "terminated"
                else:
                    status = "fulfilled"
                contracts[contract_id] = ContractRecord(**{**prior.__dict__, "status": status, "source_event_id": event.event_id})
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
        return ContractProjection(
            contracts=MappingProxyType(dict(sorted(contracts.items()))),
            source_revision_vector=MappingProxyType(dict(sorted(revisions.items()))),
        )


class ContractAuthorityService:
    """Authority lifecycle for contracts backed by registered typed terms only."""

    _PRINCIPAL = "actor_gameplay.contract_domain"
    _STREAM = "gameplay:contracts"
    _MUNICIPAL_ASSESSMENT_TERMS = "service:municipal-drought-assessment@1"
    _MUNICIPAL_ASSESSMENT_EVIDENCE = "evidence:municipal-drought-assessment@1"
    _MUNICIPAL_ASSESSMENT_PROVIDER = "organization:municipal-assessment-office"
    _MUNICIPAL_ASSESSMENT_RECEIVER = "organization:district-works"
    _MUNICIPAL_ASSESSMENT_POLICY = "policy:municipal-drought-assessment-fulfillment@1"
    _MUNICIPAL_ASSESSMENT_POLICY_AUTHORITY = "authority:municipal-assessment"
    _FACILITY_COMMISSIONING_TERMS = "service:industrial-facility-commissioning-review@1"
    _FACILITY_COMMISSIONING_EVIDENCE = "evidence:industrial-facility-commissioning-review@1"
    _FACILITY_COMMISSIONING_POLICY = "policy:industrial-facility-commissioning-review@1"
    _FACILITY_COMMISSIONING_POLICY_AUTHORITY = "authority:municipal-assessment"
    _PUBLIC_WORKSHOP_TERMS = "service:industrial-facility-public-workshop-session@1"
    _PUBLIC_WORKSHOP_EVIDENCE = "evidence:industrial-facility-public-workshop-session@1"
    _PUBLIC_WORKSHOP_POLICY = "policy:industrial-facility-public-workshop-session-price@1"
    _PUBLIC_WORKSHOP_POLICY_AUTHORITY = "authority:municipal-assessment"
    _PUBLIC_WORKSHOP_PROVIDER = "organization:municipal-assessment-office"
    _PUBLIC_MILLING_TERMS = "service:industrial-facility-public-milling-session@1"
    _PUBLIC_MILLING_EVIDENCE = "evidence:industrial-facility-public-milling-session@1"
    _PUBLIC_MILLING_POLICY = "policy:industrial-facility-public-milling-session-price@1"
    _PUBLIC_MILLING_POLICY_AUTHORITY = "authority:district-milling"
    _PUBLIC_MILLING_PROVIDER = "organization:district-milling-cooperative"

    def __init__(self, *, store: GameplayEventStore, terms_registry: ContractTermsRegistry, policy_authorities: set[str]) -> None:
        self._store = store
        self._terms_registry = terms_registry
        self._policy_authorities = frozenset(value for value in policy_authorities if value)
        self._projector = ContractProjector()

    def create_contract(self, *, command_id: str, contract_id: str, contract_type: str, terms_ref: str, party_refs: Sequence[str], idempotency_key: str, causation_id: str, correlation_id: str) -> AppendBatchResult:
        command = {"kind": "create_contract", "command_id": command_id, "contract_id": contract_id, "contract_type": contract_type, "terms_ref": terms_ref, "party_refs": tuple(party_refs)}
        digest = _digest(command)
        terms = self._terms_registry.get(terms_ref)
        if terms_ref == self._MUNICIPAL_ASSESSMENT_TERMS:
            raise ContractRuntimeError("municipal_drought_contract_admission_required")
        if terms_ref == self._FACILITY_COMMISSIONING_TERMS:
            raise ContractRuntimeError("facility_commissioning_review_row_required")
        if terms_ref == self._PUBLIC_WORKSHOP_TERMS:
            raise ContractRuntimeError("public_workshop_session_row_required")
        if terms_ref == self._PUBLIC_MILLING_TERMS:
            raise ContractRuntimeError("public_milling_session_row_required")
        duplicate = self._duplicate(idempotency_key, digest)
        if duplicate is not None:
            return duplicate
        normalized_parties = tuple(party_refs)
        if not contract_id or contract_type not in ContractTermsRegistry._SUPPORTED_TYPES or terms.contract_type != contract_type:
            raise ContractRuntimeError("contract_terms_type_mismatch")
        if len(normalized_parties) != terms.party_count or len(set(normalized_parties)) != len(normalized_parties) or any(not party for party in normalized_parties):
            raise ContractRuntimeError("contract_parties_invalid")
        projection = self._projector.rebuild(self._store.read_events())
        if contract_id in projection.contracts:
            raise ContractRuntimeError("contract_duplicate")
        event = self._event(command_id, 1, "gameplay.contract.record_created", {"contract_id": contract_id, "contract_type": contract_type, "terms_ref": terms_ref, "party_refs": list(normalized_parties), "completion_evidence_kind": terms.completion_evidence_kind}, causation_id, correlation_id)
        return self._append(command_id, idempotency_key, digest, [event], self._store.get_stream_head(self._STREAM))

    def create_municipal_drought_assessment_from_advisory(
        self, intent: GovernmentDroughtAssessmentContractIntentV1
    ) -> AppendBatchResult:
        existing = self._store.get_by_idempotency(self._PRINCIPAL, intent.idempotency_key)
        if existing is not None:
            if len(existing.committed_event_ids) == 1:
                prior = self._store.get_event(existing.committed_event_ids[0])
                if (
                    prior.event_type == "gameplay.contract.record_created"
                    and prior.payload.get("advisory_event_id") == intent.advisory_event_id
                    and prior.causation_id == intent.causation_id
                    and prior.correlation_id == intent.correlation_id
                ):
                    return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            return self._rejected_append(intent.command_id, "idempotency_key_reused")
        try:
            advisory = self._store.get_event(intent.advisory_event_id)
        except KeyError:
            return self._rejected_append(intent.command_id, "municipal_drought_contract_source_missing")
        jurisdiction_ref = advisory.payload.get("jurisdiction_ref")
        if (
            advisory.event_type != "gameplay.government.drought_advisory_issued"
            or advisory.visibility_policy != "project"
            or advisory.stream_id != f"gameplay:government:advisory:{jurisdiction_ref}"
            or advisory.stream_revision != intent.expected_advisory_revision
            or not isinstance(jurisdiction_ref, str)
            or not jurisdiction_ref
        ):
            return self._rejected_append(intent.command_id, "municipal_drought_contract_source_invalid")
        if self._store.get_stream_head(advisory.stream_id) != intent.expected_advisory_revision:
            return self._rejected_append(intent.command_id, "municipal_drought_contract_source_revision_conflict")
        if self._store.get_stream_head(self._STREAM) != intent.expected_contract_revision:
            return self._rejected_append(intent.command_id, "revision_conflict")
        try:
            terms = self._terms_registry.get(self._MUNICIPAL_ASSESSMENT_TERMS)
        except ContractRuntimeError:
            return self._rejected_append(intent.command_id, "municipal_drought_contract_terms_missing")
        if terms != ContractTermsDefinition(self._MUNICIPAL_ASSESSMENT_TERMS, "simple_service", 2, self._MUNICIPAL_ASSESSMENT_EVIDENCE):
            return self._rejected_append(intent.command_id, "municipal_drought_contract_terms_invalid")
        canonical_key = f"contract:municipal-drought-assessment:{intent.advisory_event_id}:{intent.expected_advisory_revision}:{jurisdiction_ref}:{intent.expected_contract_revision}:v1"
        if intent.idempotency_key != canonical_key:
            return self._rejected_append(intent.command_id, "municipal_drought_contract_idempotency_key_invalid")
        contract_id = f"contract:municipal-drought-assessment:{jurisdiction_ref}:{intent.advisory_event_id}"
        if contract_id in self._projector.rebuild(self._store.read_events()).contracts:
            return self._rejected_append(intent.command_id, "municipal_drought_contract_already_created")
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:government-drought-advisory-municipal-assessment-contract@1",
                contract_kind="contract_admission",
                owner_ref=self._PRINCIPAL,
                stream_ids=(self._STREAM,),
                event_types=("gameplay.contract.record_created",),
                projection_scope="authority_only",
            )
        except GovernedAuthorityContractError as exc:
            return self._rejected_append(intent.command_id, str(exc))
        command = GameplayCommandEnvelope(
            command_id=intent.command_id,
            command_type="gameplay.contract.create_municipal_drought_assessment",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=None,
            project_ref=None,
            transaction_id=f"transaction:{intent.command_id}",
            idempotency_key=intent.idempotency_key,
            expected_revisions={self._STREAM: intent.expected_contract_revision},
            read_set_revisions={advisory.stream_id: intent.expected_advisory_revision},
            causation_id=intent.causation_id,
            correlation_id=intent.correlation_id,
            source_ref=intent.advisory_event_id,
            submitted_at=intent.submitted_at,
            pinned_revisions={"government_advisory": intent.expected_advisory_revision, "contract": intent.expected_contract_revision},
            payload={
                "stream_ref": self._STREAM,
                "event_type": "gameplay.contract.record_created",
                "visibility_policy": "authority_only",
                "contract_id": contract_id,
                "contract_type": "simple_service",
                "terms_ref": self._MUNICIPAL_ASSESSMENT_TERMS,
                "party_refs": [self._MUNICIPAL_ASSESSMENT_PROVIDER, self._MUNICIPAL_ASSESSMENT_RECEIVER],
                "completion_evidence_kind": self._MUNICIPAL_ASSESSMENT_EVIDENCE,
                "advisory_event_id": intent.advisory_event_id,
                "advisory_stream_id": advisory.stream_id,
                "advisory_stream_revision": intent.expected_advisory_revision,
                "jurisdiction_ref": jurisdiction_ref,
            },
        )
        return self._store.append_batch(EventStoreSettlementPlan.from_command_envelope(command).to_atomic_event_batch())

    def create_facility_commissioning_review_from_verification(
        self, intent: FacilityCommissioningReviewContractIntentV1
    ) -> AppendBatchResult:
        existing = self._store.get_by_idempotency(self._PRINCIPAL, intent.idempotency_key)
        if existing is not None:
            if len(existing.committed_event_ids) == 1:
                prior = self._store.get_event(existing.committed_event_ids[0])
                if (
                    prior.event_type == "gameplay.contract.record_created"
                    and prior.payload.get("operational_verification_event_id") == intent.operational_verification_event_id
                    and prior.command_id == intent.command_id
                    and prior.causation_id == intent.causation_id
                    and prior.correlation_id == intent.correlation_id
                ):
                    return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            return self._rejected_append(intent.command_id, "idempotency_key_reused")
        try:
            verification = self._store.get_event(intent.operational_verification_event_id)
        except KeyError:
            return self._rejected_append(intent.command_id, "facility_commissioning_source_missing")
        stream_id = verification.stream_id
        if (
            verification.event_type != "gameplay.construction_production.facility_operationally_verified"
            or verification.visibility_policy != "project"
            or verification.stream_revision != intent.expected_operational_verification_revision
            or self._store.get_stream_head(stream_id) != intent.expected_operational_verification_revision
        ):
            return self._rejected_append(intent.command_id, "facility_commissioning_source_invalid")
        facility_ref = verification.payload.get("facility_ref")
        project_ref = verification.payload.get("project_ref")
        if not isinstance(facility_ref, str) or not isinstance(project_ref, str) or not facility_ref or not project_ref:
            return self._rejected_append(intent.command_id, "facility_commissioning_source_invalid")
        acquisition = next(
            (
                event for event in self._store.read_stream(stream_id)
                if event.event_type == "gameplay.construction_production.facility_acquired"
                and event.payload.get("facility_ref") == facility_ref
                and event.payload.get("plot_ref") == project_ref
                and event.visibility_policy == "project"
            ),
            None,
        )
        receiver_ref = acquisition.payload.get("owner_ref") if acquisition is not None else None
        if acquisition is None or not isinstance(receiver_ref, str) or not receiver_ref.startswith("organization:"):
            return self._rejected_append(intent.command_id, "facility_commissioning_binding_invalid")
        if self._store.get_stream_head(self._STREAM) != intent.expected_contract_revision:
            return self._rejected_append(intent.command_id, "revision_conflict")
        try:
            terms = self._terms_registry.get(self._FACILITY_COMMISSIONING_TERMS)
        except ContractRuntimeError:
            return self._rejected_append(intent.command_id, "facility_commissioning_terms_missing")
        if terms != ContractTermsDefinition(self._FACILITY_COMMISSIONING_TERMS, "simple_service", 2, self._FACILITY_COMMISSIONING_EVIDENCE):
            return self._rejected_append(intent.command_id, "facility_commissioning_terms_invalid")
        canonical_key = f"contract:facility-commissioning-review:{intent.operational_verification_event_id}:{intent.expected_operational_verification_revision}:{intent.expected_contract_revision}:v1"
        if intent.idempotency_key != canonical_key:
            return self._rejected_append(intent.command_id, "facility_commissioning_idempotency_key_invalid")
        contract_id = f"contract:facility-commissioning-review:{facility_ref}:{intent.operational_verification_event_id}"
        if contract_id in self._projector.rebuild(self._store.read_events()).contracts:
            return self._rejected_append(intent.command_id, "facility_commissioning_already_created")
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:facility-commissioning-review-contract-admission@1",
                contract_kind="contract_admission",
                owner_ref=self._PRINCIPAL,
                stream_ids=(self._STREAM,),
                event_types=("gameplay.contract.record_created",),
                projection_scope="authority_only",
            )
        except GovernedAuthorityContractError as exc:
            return self._rejected_append(intent.command_id, str(exc))
        command = GameplayCommandEnvelope(
            command_id=intent.command_id,
            command_type="gameplay.contract.create_facility_commissioning_review",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=None,
            project_ref=project_ref,
            transaction_id=f"transaction:{intent.command_id}",
            idempotency_key=intent.idempotency_key,
            expected_revisions={self._STREAM: intent.expected_contract_revision},
            read_set_revisions={stream_id: intent.expected_operational_verification_revision},
            causation_id=intent.causation_id,
            correlation_id=intent.correlation_id,
            source_ref=intent.operational_verification_event_id,
            submitted_at=intent.submitted_at,
            pinned_revisions={"operational_verification": intent.expected_operational_verification_revision, "acquisition": acquisition.stream_revision, "contract": intent.expected_contract_revision},
            payload={
                "stream_ref": self._STREAM,
                "event_type": "gameplay.contract.record_created",
                "visibility_policy": "authority_only",
                "contract_id": contract_id,
                "contract_type": "simple_service",
                "terms_ref": self._FACILITY_COMMISSIONING_TERMS,
                "party_refs": [self._MUNICIPAL_ASSESSMENT_PROVIDER, receiver_ref],
                "completion_evidence_kind": self._FACILITY_COMMISSIONING_EVIDENCE,
                "operational_verification_event_id": intent.operational_verification_event_id,
                "operational_verification_revision": intent.expected_operational_verification_revision,
                "facility_ref": facility_ref,
                "project_ref": project_ref,
                "acquisition_event_id": acquisition.event_id,
                "acquisition_event_revision": acquisition.stream_revision,
                "receiver_ref": receiver_ref,
            },
        )
        return self._store.append_batch(EventStoreSettlementPlan.from_command_envelope(command).to_atomic_event_batch())

    def create_public_workshop_session_from_public_use(
        self, intent: PublicWorkshopSessionContractIntentV1
    ) -> AppendBatchResult:
        """Admit one public-workshop service from the exact Construction source."""
        existing = self._store.get_by_idempotency(self._PRINCIPAL, intent.idempotency_key)
        if existing is not None:
            if len(existing.committed_event_ids) == 1:
                prior = self._store.get_event(existing.committed_event_ids[0])
                if (
                    prior.event_type == "gameplay.contract.record_created"
                    and prior.payload.get("public_use_event_id") == intent.public_use_event_id
                    and prior.command_id == intent.command_id
                    and prior.causation_id == intent.causation_id
                    and prior.correlation_id == intent.correlation_id
                ):
                    return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            return self._rejected_append(intent.command_id, "idempotency_key_reused")
        try:
            source = self._store.get_event(intent.public_use_event_id)
        except KeyError:
            return self._rejected_append(intent.command_id, "public_workshop_source_missing")
        if (
            source.event_type != "gameplay.construction_production.facility_public_use_enabled"
            or source.visibility_policy != "project"
            or source.stream_revision != intent.expected_public_use_revision
            or self._store.get_stream_head(source.stream_id) != intent.expected_public_use_revision
            or source.payload.get("facility_kind") != "oven"
            or source.payload.get("next_public_use_status") != "enabled"
        ):
            return self._rejected_append(intent.command_id, "public_workshop_source_invalid")
        facility_ref = source.payload.get("facility_ref")
        project_ref = source.payload.get("project_ref")
        if not isinstance(facility_ref, str) or not facility_ref or not isinstance(project_ref, str) or not project_ref:
            return self._rejected_append(intent.command_id, "public_workshop_binding_invalid")
        verification_event_id = source.payload.get("verification_event_id")
        verification_revision = source.payload.get("verification_event_revision")
        try:
            verification = self._store.get_event(str(verification_event_id))
        except (KeyError, TypeError):
            return self._rejected_append(intent.command_id, "public_workshop_verification_missing")
        if (
            not isinstance(verification_event_id, str)
            or not verification_event_id
            or not isinstance(verification_revision, int)
            or isinstance(verification_revision, bool)
            or verification.event_type != "gameplay.construction_production.facility_operationally_verified"
            or verification.visibility_policy != "project"
            or verification.stream_id != source.stream_id
            or verification.stream_revision != verification_revision
            or verification.payload.get("facility_ref") != facility_ref
            or verification.payload.get("project_ref") != project_ref
        ):
            return self._rejected_append(intent.command_id, "public_workshop_verification_invalid")
        acquisitions = [
            event
            for event in self._store.read_stream(source.stream_id)
            if event.event_type == "gameplay.construction_production.facility_acquired"
            and event.visibility_policy == "project"
            and event.payload.get("facility_ref") == facility_ref
            and event.payload.get("plot_ref") == project_ref
            and isinstance(event.payload.get("owner_ref"), str)
            and str(event.payload.get("owner_ref")).startswith(("organization:", "org:"))
        ]
        if len(acquisitions) != 1:
            return self._rejected_append(
                intent.command_id,
                "public_workshop_binding_missing" if not acquisitions else "public_workshop_binding_ambiguous",
            )
        receiver_ref = str(acquisitions[0].payload["owner_ref"])
        if self._store.get_stream_head(self._STREAM) != intent.expected_contract_revision:
            return self._rejected_append(intent.command_id, "revision_conflict")
        try:
            terms = self._terms_registry.get(self._PUBLIC_WORKSHOP_TERMS)
        except ContractRuntimeError:
            return self._rejected_append(intent.command_id, "public_workshop_terms_missing")
        if terms != ContractTermsDefinition(self._PUBLIC_WORKSHOP_TERMS, "simple_service", 2, self._PUBLIC_WORKSHOP_EVIDENCE):
            return self._rejected_append(intent.command_id, "public_workshop_terms_invalid")
        canonical_key = (
            f"contract:public-workshop-session:{intent.public_use_event_id}:"
            f"{intent.expected_public_use_revision}:{intent.expected_contract_revision}:v1"
        )
        if intent.idempotency_key != canonical_key:
            return self._rejected_append(intent.command_id, "public_workshop_idempotency_key_invalid")
        contract_id = f"contract:public-workshop-session:{facility_ref}:{intent.public_use_event_id}"
        if contract_id in self._projector.rebuild(self._store.read_events()).contracts:
            return self._rejected_append(intent.command_id, "public_workshop_already_created")
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:public-workshop-session-contract-admission@1",
                contract_kind="contract_admission",
                owner_ref=self._PRINCIPAL,
                stream_ids=(self._STREAM,),
                event_types=("gameplay.contract.record_created",),
                projection_scope="authority_only",
            )
        except GovernedAuthorityContractError as exc:
            return self._rejected_append(intent.command_id, str(exc))
        command = GameplayCommandEnvelope(
            command_id=intent.command_id,
            command_type="gameplay.contract.create_public_workshop_session",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=None,
            project_ref=project_ref,
            transaction_id=f"transaction:{intent.command_id}",
            idempotency_key=intent.idempotency_key,
            expected_revisions={self._STREAM: intent.expected_contract_revision},
            read_set_revisions={source.stream_id: intent.expected_public_use_revision},
            causation_id=intent.causation_id,
            correlation_id=intent.correlation_id,
            source_ref=intent.public_use_event_id,
            submitted_at=intent.submitted_at,
            pinned_revisions={
                "public_use": intent.expected_public_use_revision,
                "acquisition": acquisitions[0].stream_revision,
                "contract": intent.expected_contract_revision,
            },
            payload={
                "stream_ref": self._STREAM,
                "event_type": "gameplay.contract.record_created",
                "visibility_policy": "authority_only",
                "contract_id": contract_id,
                "contract_type": "simple_service",
                "terms_ref": self._PUBLIC_WORKSHOP_TERMS,
                "party_refs": [self._PUBLIC_WORKSHOP_PROVIDER, receiver_ref],
                "completion_evidence_kind": self._PUBLIC_WORKSHOP_EVIDENCE,
                "public_use_event_id": intent.public_use_event_id,
                "public_use_stream_id": source.stream_id,
                "public_use_stream_revision": intent.expected_public_use_revision,
                "facility_ref": facility_ref,
                "project_ref": project_ref,
                "facility_kind": "oven",
                "acquisition_event_id": acquisitions[0].event_id,
                "acquisition_stream_revision": acquisitions[0].stream_revision,
                "verification_event_id": verification.event_id,
                "verification_stream_revision": verification.stream_revision,
            },
        )
        return self._store.append_batch(EventStoreSettlementPlan.from_command_envelope(command).to_atomic_event_batch())

    def create_public_milling_session_from_public_use(
        self, intent: PublicMillingSessionContractIntentV1
    ) -> AppendBatchResult:
        """Admit one fixed service contract from the reinforced-mill row only."""
        existing = self._store.get_by_idempotency(self._PRINCIPAL, intent.idempotency_key)
        if existing is not None:
            if len(existing.committed_event_ids) == 1:
                prior = self._store.get_event(existing.committed_event_ids[0])
                if (
                    prior.event_type == "gameplay.contract.record_created"
                    and prior.payload.get("public_use_event_id") == intent.public_use_event_id
                    and prior.command_id == intent.command_id
                    and prior.causation_id == intent.causation_id
                    and prior.correlation_id == intent.correlation_id
                ):
                    return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            return self._rejected_append(intent.command_id, "public_milling_idempotency_key_reused")
        try:
            source = self._store.get_event(intent.public_use_event_id)
        except KeyError:
            return self._rejected_append(intent.command_id, "public_milling_source_missing")
        if (
            source.event_type != "gameplay.construction_production.facility_public_use_enabled"
            or source.visibility_policy != "project"
            or source.stream_revision != intent.expected_public_use_revision
            or self._store.get_stream_head(source.stream_id) != intent.expected_public_use_revision
            or source.payload.get("row_ref") != "construction:facility-mill-reinforced-public-use@1"
            or source.payload.get("facility_kind") != "mill_reinforced"
            or source.payload.get("next_public_use_status") != "enabled"
        ):
            return self._rejected_append(intent.command_id, "public_milling_source_invalid")
        facility_ref = source.payload.get("facility_ref")
        project_ref = source.payload.get("project_ref")
        reinforcement_id = source.payload.get("reinforcement_event_id")
        try:
            reinforcement = self._store.get_event(str(reinforcement_id))
        except (KeyError, TypeError):
            return self._rejected_append(intent.command_id, "public_milling_reinforcement_missing")
        if (
            not isinstance(facility_ref, str) or not facility_ref
            or not isinstance(project_ref, str) or not project_ref
            or reinforcement.event_type != "gameplay.construction_production.facility_transformed"
            or reinforcement.visibility_policy != "project"
            or reinforcement.stream_id != source.stream_id
            or reinforcement.payload.get("prior_kind") != "mill"
            or reinforcement.payload.get("next_kind") != "mill_reinforced"
            or reinforcement.payload.get("package_revision") != "package:industrial-facilities:v2"
            or reinforcement.payload.get("content_digest") != "sha256:8deea88c5e49c2aa06f30bbf1bd78ed103e26d8fb31769fe5564dbb7cc279896"
            or reinforcement.event_id != reinforcement_id
        ):
            return self._rejected_append(intent.command_id, "public_milling_reinforcement_invalid")
        verification_id = source.payload.get("verification_event_id")
        try:
            verification = self._store.get_event(str(verification_id))
        except (KeyError, TypeError):
            return self._rejected_append(intent.command_id, "public_milling_verification_missing")
        if (
            verification.event_type != "gameplay.construction_production.facility_operationally_verified"
            or verification.visibility_policy != "project"
            or verification.stream_id != source.stream_id
            or verification.event_id != verification_id
            or verification.payload.get("facility_ref") != facility_ref
            or verification.payload.get("project_ref") != project_ref
            or source.payload.get("verification_event_revision") != verification.stream_revision
        ):
            return self._rejected_append(intent.command_id, "public_milling_verification_invalid")
        acquisitions = [
            event for event in self._store.read_stream(source.stream_id)
            if event.event_type == "gameplay.construction_production.facility_acquired"
            and event.visibility_policy == "project"
            and event.payload.get("facility_ref") == facility_ref
            and event.payload.get("plot_ref") == project_ref
            and isinstance(event.payload.get("owner_ref"), str)
            and str(event.payload.get("owner_ref")).startswith(("organization:", "org:"))
        ]
        if len(acquisitions) != 1:
            return self._rejected_append(
                intent.command_id,
                "public_milling_binding_missing" if not acquisitions else "public_milling_binding_ambiguous",
            )
        receiver_ref = str(acquisitions[0].payload["owner_ref"])
        if self._store.get_stream_head(self._STREAM) != intent.expected_contract_revision:
            return self._rejected_append(intent.command_id, "public_milling_revision_conflict")
        try:
            terms = self._terms_registry.get(self._PUBLIC_MILLING_TERMS)
        except ContractRuntimeError:
            return self._rejected_append(intent.command_id, "public_milling_terms_missing")
        if terms != ContractTermsDefinition(self._PUBLIC_MILLING_TERMS, "simple_service", 2, self._PUBLIC_MILLING_EVIDENCE):
            return self._rejected_append(intent.command_id, "public_milling_terms_invalid")
        canonical_key = (
            f"contract:public-milling-session:{intent.public_use_event_id}:"
            f"{intent.expected_public_use_revision}:{intent.expected_contract_revision}:v1"
        )
        if intent.idempotency_key != canonical_key:
            return self._rejected_append(intent.command_id, "public_milling_idempotency_key_invalid")
        contract_id = f"contract:public-milling-session:{facility_ref}:{intent.public_use_event_id}"
        if contract_id in self._projector.rebuild(self._store.read_events()).contracts:
            return self._rejected_append(intent.command_id, "public_milling_already_created")
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:industrial-facility-public-milling-session-contract-admission@1",
                contract_kind="contract_admission",
                owner_ref=self._PRINCIPAL,
                stream_ids=(self._STREAM,),
                event_types=("gameplay.contract.record_created",),
                projection_scope="authority_only",
            )
        except GovernedAuthorityContractError as exc:
            return self._rejected_append(intent.command_id, str(exc))
        command = GameplayCommandEnvelope(
            command_id=intent.command_id,
            command_type="gameplay.contract.create_public_milling_session",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=None,
            project_ref=project_ref,
            transaction_id=f"transaction:{intent.command_id}",
            idempotency_key=intent.idempotency_key,
            expected_revisions={self._STREAM: intent.expected_contract_revision},
            read_set_revisions={source.stream_id: intent.expected_public_use_revision},
            causation_id=intent.causation_id,
            correlation_id=intent.correlation_id,
            source_ref=intent.public_use_event_id,
            submitted_at=intent.submitted_at,
            pinned_revisions={
                "public_use": intent.expected_public_use_revision,
                "verification": verification.stream_revision,
                "reinforcement": reinforcement.stream_revision,
                "acquisition": acquisitions[0].stream_revision,
                "contract": intent.expected_contract_revision,
            },
            payload={
                "stream_ref": self._STREAM,
                "event_type": "gameplay.contract.record_created",
                "visibility_policy": "authority_only",
                "contract_id": contract_id,
                "contract_type": "simple_service",
                "terms_ref": self._PUBLIC_MILLING_TERMS,
                "party_refs": [self._PUBLIC_MILLING_PROVIDER, receiver_ref],
                "completion_evidence_kind": self._PUBLIC_MILLING_EVIDENCE,
                "public_use_event_id": intent.public_use_event_id,
                "public_use_stream_id": source.stream_id,
                "public_use_stream_revision": intent.expected_public_use_revision,
                "facility_ref": facility_ref,
                "project_ref": project_ref,
                "facility_kind": "mill_reinforced",
                "acquisition_event_id": acquisitions[0].event_id,
                "acquisition_stream_revision": acquisitions[0].stream_revision,
                "verification_event_id": verification.event_id,
                "verification_stream_revision": verification.stream_revision,
                "reinforcement_event_id": reinforcement.event_id,
                "reinforcement_stream_revision": reinforcement.stream_revision,
                "package_revision": "package:industrial-facilities:v6",
                "policy_revision": self._PUBLIC_MILLING_POLICY,
            },
        )
        return self._store.append_batch(EventStoreSettlementPlan.from_command_envelope(command).to_atomic_event_batch())

    def fulfill_public_milling_session_by_policy(
        self, intent: PublicMillingSessionFulfillmentIntentV1
    ) -> AppendBatchResult:
        """Fulfill only the reinforced-mill service contract admitted by INF-2AL."""
        request_digest = _digest(intent.model_dump(mode="json"))
        existing = self._store.get_by_idempotency(self._PRINCIPAL, intent.idempotency_key)
        if existing is not None:
            if len(existing.committed_event_ids) == 2:
                prior = self._store.get_event(existing.committed_event_ids[0])
                if prior.payload.get("fulfillment_request_digest") == request_digest:
                    return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            return self._rejected_append(intent.command_id, "public_milling_fulfillment_idempotency_key_reused")
        try:
            created = self._store.get_event(intent.contract_created_event_id)
        except KeyError:
            return self._rejected_append(intent.command_id, "public_milling_fulfillment_source_missing")
        payload = created.payload
        contract_id = payload.get("contract_id")
        source_event_id = payload.get("public_use_event_id")
        if (
            created.event_type != "gameplay.contract.record_created"
            or created.stream_id != self._STREAM
            or created.stream_revision != intent.expected_contract_created_revision
            or created.visibility_policy != "authority_only"
            or payload.get("terms_ref") != self._PUBLIC_MILLING_TERMS
            or payload.get("completion_evidence_kind") != self._PUBLIC_MILLING_EVIDENCE
            or not isinstance(contract_id, str)
            or not isinstance(source_event_id, str)
            or payload.get("public_use_stream_revision") != intent.expected_public_use_revision
        ):
            return self._rejected_append(intent.command_id, "public_milling_fulfillment_source_invalid")
        try:
            source = self._store.get_event(source_event_id)
        except KeyError:
            return self._rejected_append(intent.command_id, "public_milling_fulfillment_public_use_missing")
        if (
            source.event_type != "gameplay.construction_production.facility_public_use_enabled"
            or source.visibility_policy != "project"
            or source.stream_revision != intent.expected_public_use_revision
            or source.payload.get("row_ref") != "construction:facility-mill-reinforced-public-use@1"
            or source.payload.get("facility_kind") != "mill_reinforced"
            or source.payload.get("facility_ref") != payload.get("facility_ref")
            or source.payload.get("project_ref") != payload.get("project_ref")
        ):
            return self._rejected_append(intent.command_id, "public_milling_fulfillment_public_use_invalid")
        if self._store.get_stream_head(self._STREAM) != intent.expected_contract_head:
            return self._rejected_append(intent.command_id, "public_milling_fulfillment_revision_conflict")
        record = self._projector.rebuild(self._store.read_events()).contracts.get(contract_id)
        if (
            record is None
            or record.source_event_id != intent.contract_created_event_id
            or record.status != "active"
            or record.contract_type != "simple_service"
            or record.terms_ref != self._PUBLIC_MILLING_TERMS
            or record.completion_evidence_ref is not None
            or self._PUBLIC_MILLING_POLICY_AUTHORITY not in self._policy_authorities
        ):
            return self._rejected_append(intent.command_id, "public_milling_fulfillment_eligibility_invalid")
        canonical_key = (
            f"contract:public-milling-session:fulfillment:{intent.contract_created_event_id}:"
            f"{intent.expected_contract_created_revision}:{intent.expected_public_use_revision}:"
            f"{intent.expected_contract_head}:v1"
        )
        if intent.idempotency_key != canonical_key:
            return self._rejected_append(intent.command_id, "public_milling_fulfillment_idempotency_key_invalid")
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:industrial-facility-public-milling-session-contract-fulfillment@1",
                contract_kind="contract_admission",
                owner_ref=self._PRINCIPAL,
                stream_ids=(self._STREAM,),
                event_types=("gameplay.contract.service_completion_recorded", "gameplay.contract.record_fulfilled"),
                projection_scope="authority_only",
            )
        except GovernedAuthorityContractError as exc:
            return self._rejected_append(intent.command_id, str(exc))
        evidence_ref = f"evidence:industrial-facility-public-milling-session:completed:{contract_id}"
        command = GameplayCommandEnvelope(
            command_id=intent.command_id,
            command_type="gameplay.contract.fulfill_public_milling_session",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=None,
            project_ref=payload.get("project_ref"),
            transaction_id=f"transaction:{intent.command_id}",
            idempotency_key=intent.idempotency_key,
            expected_revisions={self._STREAM: intent.expected_contract_head},
            read_set_revisions={source.stream_id: intent.expected_public_use_revision},
            causation_id=intent.causation_id,
            correlation_id=intent.correlation_id,
            source_ref=intent.contract_created_event_id,
            submitted_at=intent.submitted_at,
            pinned_revisions={
                "contract_created": intent.expected_contract_created_revision,
                "public_use": intent.expected_public_use_revision,
                "contract": intent.expected_contract_head,
            },
            payload={
                "stream_ref": self._STREAM,
                "event_type": "gameplay.contract.service_completion_recorded",
                "visibility_policy": "authority_only",
                "event_specs": [
                    {"event_type": "gameplay.contract.service_completion_recorded", "payload": {
                        "contract_id": contract_id, "authority_ref": self._PUBLIC_MILLING_POLICY_AUTHORITY,
                        "policy_ref": self._PUBLIC_MILLING_POLICY, "completion_evidence_kind": self._PUBLIC_MILLING_EVIDENCE,
                        "completion_evidence_ref": evidence_ref, "contract_created_event_id": intent.contract_created_event_id,
                        "fulfillment_request_digest": request_digest,
                    }},
                    {"event_type": "gameplay.contract.record_fulfilled", "payload": {
                        "contract_id": contract_id, "authority_ref": self._PUBLIC_MILLING_POLICY_AUTHORITY,
                        "policy_ref": self._PUBLIC_MILLING_POLICY, "contract_created_event_id": intent.contract_created_event_id,
                    }},
                ],
            },
        )
        return self._store.append_batch(EventStoreSettlementPlan.from_command_envelope(command).to_atomic_event_batch())

    def fulfill_facility_commissioning_review_by_policy(
        self, intent: FacilityCommissioningReviewFulfillmentIntentV1
    ) -> AppendBatchResult:
        request_digest = _digest(intent.model_dump(mode="json"))
        existing = self._store.get_by_idempotency(self._PRINCIPAL, intent.idempotency_key)
        if existing is not None:
            if len(existing.committed_event_ids) == 2:
                completion = self._store.get_event(existing.committed_event_ids[0])
                fulfilled = self._store.get_event(existing.committed_event_ids[1])
                if completion.event_type == "gameplay.contract.service_completion_recorded" and fulfilled.event_type == "gameplay.contract.record_fulfilled" and completion.payload.get("contract_created_event_id") == intent.contract_created_event_id and completion.payload.get("fulfillment_request_digest") == request_digest and completion.command_id == intent.command_id and completion.causation_id == intent.causation_id and completion.correlation_id == intent.correlation_id:
                    return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            return self._rejected_append(intent.command_id, "idempotency_key_reused")
        try:
            created = self._store.get_event(intent.contract_created_event_id)
        except KeyError:
            return self._rejected_append(intent.command_id, "facility_commissioning_fulfillment_source_missing")
        payload = created.payload
        contract_id = payload.get("contract_id")
        source_event_id = payload.get("operational_verification_event_id")
        if (created.event_type != "gameplay.contract.record_created" or created.stream_id != self._STREAM or created.stream_revision != intent.expected_contract_created_revision or created.visibility_policy != "authority_only" or payload.get("terms_ref") != self._FACILITY_COMMISSIONING_TERMS or payload.get("completion_evidence_kind") != self._FACILITY_COMMISSIONING_EVIDENCE or not isinstance(contract_id, str) or not isinstance(source_event_id, str) or payload.get("operational_verification_revision") != intent.expected_operational_verification_revision):
            return self._rejected_append(intent.command_id, "facility_commissioning_fulfillment_source_invalid")
        try:
            verification = self._store.get_event(source_event_id)
        except KeyError:
            return self._rejected_append(intent.command_id, "facility_commissioning_fulfillment_verification_missing")
        if verification.event_type != "gameplay.construction_production.facility_operationally_verified" or verification.visibility_policy != "project" or verification.stream_revision != intent.expected_operational_verification_revision:
            return self._rejected_append(intent.command_id, "facility_commissioning_fulfillment_verification_invalid")
        if self._store.get_stream_head(self._STREAM) != intent.expected_contract_head:
            return self._rejected_append(intent.command_id, "facility_commissioning_fulfillment_revision_conflict")
        record = self._projector.rebuild(self._store.read_events()).contracts.get(contract_id)
        if record is None or record.source_event_id != intent.contract_created_event_id or record.status != "active" or record.completion_evidence_ref is not None or self._FACILITY_COMMISSIONING_POLICY_AUTHORITY not in self._policy_authorities:
            return self._rejected_append(intent.command_id, "facility_commissioning_fulfillment_eligibility_invalid")
        canonical_key = f"contract:facility-commissioning-review:fulfillment:{intent.contract_created_event_id}:{intent.expected_contract_created_revision}:{intent.expected_operational_verification_revision}:{intent.expected_contract_head}:v1"
        if intent.idempotency_key != canonical_key:
            return self._rejected_append(intent.command_id, "facility_commissioning_fulfillment_idempotency_key_invalid")
        try:
            GovernedAuthorityContractCatalog.require_operation(contract_ref="inf:facility-commissioning-review-contract-fulfillment@1", contract_kind="contract_admission", owner_ref=self._PRINCIPAL, stream_ids=(self._STREAM,), event_types=("gameplay.contract.service_completion_recorded", "gameplay.contract.record_fulfilled"), projection_scope="authority_only")
        except GovernedAuthorityContractError as exc:
            return self._rejected_append(intent.command_id, str(exc))
        evidence_ref = f"evidence:industrial-facility-commissioning-review:completed:{contract_id}"
        command = GameplayCommandEnvelope(command_id=intent.command_id, command_type="gameplay.contract.fulfill_facility_commissioning_review", command_version=1, principal_ref=self._PRINCIPAL, actor_ref=None, project_ref=payload.get("project_ref"), transaction_id=f"transaction:{intent.command_id}", idempotency_key=intent.idempotency_key, expected_revisions={self._STREAM: intent.expected_contract_head}, read_set_revisions={verification.stream_id: intent.expected_operational_verification_revision}, causation_id=intent.causation_id, correlation_id=intent.correlation_id, source_ref=intent.contract_created_event_id, submitted_at=intent.submitted_at, pinned_revisions={"contract_created": intent.expected_contract_created_revision, "operational_verification": intent.expected_operational_verification_revision, "contract": intent.expected_contract_head}, payload={"stream_ref": self._STREAM, "event_type": "gameplay.contract.service_completion_recorded", "visibility_policy": "authority_only", "event_specs": [{"event_type": "gameplay.contract.service_completion_recorded", "payload": {"contract_id": contract_id, "authority_ref": self._FACILITY_COMMISSIONING_POLICY_AUTHORITY, "policy_ref": self._FACILITY_COMMISSIONING_POLICY, "completion_evidence_kind": self._FACILITY_COMMISSIONING_EVIDENCE, "completion_evidence_ref": evidence_ref, "contract_created_event_id": intent.contract_created_event_id, "fulfillment_request_digest": request_digest}}, {"event_type": "gameplay.contract.record_fulfilled", "payload": {"contract_id": contract_id, "authority_ref": self._FACILITY_COMMISSIONING_POLICY_AUTHORITY, "policy_ref": self._FACILITY_COMMISSIONING_POLICY, "contract_created_event_id": intent.contract_created_event_id}}]})
        return self._store.append_batch(EventStoreSettlementPlan.from_command_envelope(command).to_atomic_event_batch())

    def fulfill_public_workshop_session_by_policy(
        self, intent: PublicWorkshopSessionFulfillmentIntentV1
    ) -> AppendBatchResult:
        """Fulfill only the public-workshop terms admitted by INF-2AG."""
        request_digest = _digest(intent.model_dump(mode="json"))
        existing = self._store.get_by_idempotency(self._PRINCIPAL, intent.idempotency_key)
        if existing is not None:
            if existing.committed:
                prior_ids = tuple(existing.committed_event_ids)
                if len(prior_ids) == 2:
                    prior = self._store.get_event(prior_ids[0])
                    if prior.payload.get("fulfillment_request_digest") == request_digest:
                        return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            return self._rejected_append(intent.command_id, "idempotency_key_reused")
        try:
            created = self._store.get_event(intent.contract_created_event_id)
        except KeyError:
            return self._rejected_append(intent.command_id, "public_workshop_fulfillment_source_missing")
        payload = created.payload
        contract_id = payload.get("contract_id")
        source_event_id = payload.get("public_use_event_id")
        if (
            created.event_type != "gameplay.contract.record_created"
            or created.stream_id != self._STREAM
            or created.stream_revision != intent.expected_contract_created_revision
            or created.visibility_policy != "authority_only"
            or payload.get("terms_ref") != self._PUBLIC_WORKSHOP_TERMS
            or payload.get("completion_evidence_kind") != self._PUBLIC_WORKSHOP_EVIDENCE
            or not isinstance(contract_id, str)
            or not isinstance(source_event_id, str)
            or payload.get("public_use_stream_revision") != intent.expected_public_use_revision
        ):
            return self._rejected_append(intent.command_id, "public_workshop_fulfillment_source_invalid")
        try:
            source = self._store.get_event(source_event_id)
        except KeyError:
            return self._rejected_append(intent.command_id, "public_workshop_fulfillment_public_use_missing")
        if (
            source.event_type != "gameplay.construction_production.facility_public_use_enabled"
            or source.visibility_policy != "project"
            or source.stream_revision != intent.expected_public_use_revision
            or source.payload.get("facility_ref") != payload.get("facility_ref")
            or source.payload.get("project_ref") != payload.get("project_ref")
        ):
            return self._rejected_append(intent.command_id, "public_workshop_fulfillment_public_use_invalid")
        if self._store.get_stream_head(self._STREAM) != intent.expected_contract_head:
            return self._rejected_append(intent.command_id, "public_workshop_fulfillment_revision_conflict")
        record = self._projector.rebuild(self._store.read_events()).contracts.get(contract_id)
        if (
            record is None
            or record.source_event_id != intent.contract_created_event_id
            or record.status != "active"
            or record.contract_type != "simple_service"
            or record.terms_ref != self._PUBLIC_WORKSHOP_TERMS
            or record.completion_evidence_ref is not None
            or self._PUBLIC_WORKSHOP_POLICY_AUTHORITY not in self._policy_authorities
        ):
            return self._rejected_append(intent.command_id, "public_workshop_fulfillment_eligibility_invalid")
        canonical_key = (
            f"contract:public-workshop-session:fulfillment:{intent.contract_created_event_id}:"
            f"{intent.expected_contract_created_revision}:{intent.expected_public_use_revision}:"
            f"{intent.expected_contract_head}:v1"
        )
        if intent.idempotency_key != canonical_key:
            return self._rejected_append(intent.command_id, "public_workshop_fulfillment_idempotency_key_invalid")
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:public-workshop-session-contract-fulfillment@1",
                contract_kind="contract_admission",
                owner_ref=self._PRINCIPAL,
                stream_ids=(self._STREAM,),
                event_types=("gameplay.contract.service_completion_recorded", "gameplay.contract.record_fulfilled"),
                projection_scope="authority_only",
            )
        except GovernedAuthorityContractError as exc:
            return self._rejected_append(intent.command_id, str(exc))
        evidence_ref = f"evidence:industrial-facility-public-workshop-session:completed:{contract_id}"
        command = GameplayCommandEnvelope(
            command_id=intent.command_id,
            command_type="gameplay.contract.fulfill_public_workshop_session",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=None,
            project_ref=payload.get("project_ref"),
            transaction_id=f"transaction:{intent.command_id}",
            idempotency_key=intent.idempotency_key,
            expected_revisions={self._STREAM: intent.expected_contract_head},
            read_set_revisions={source.stream_id: intent.expected_public_use_revision},
            causation_id=intent.causation_id,
            correlation_id=intent.correlation_id,
            source_ref=intent.contract_created_event_id,
            submitted_at=intent.submitted_at,
            pinned_revisions={
                "contract_created": intent.expected_contract_created_revision,
                "public_use": intent.expected_public_use_revision,
                "contract": intent.expected_contract_head,
            },
            payload={
                "stream_ref": self._STREAM,
                "event_type": "gameplay.contract.service_completion_recorded",
                "visibility_policy": "authority_only",
                "event_specs": [
                    {
                        "event_type": "gameplay.contract.service_completion_recorded",
                        "payload": {
                            "contract_id": contract_id,
                            "authority_ref": self._PUBLIC_WORKSHOP_POLICY_AUTHORITY,
                            "policy_ref": self._PUBLIC_WORKSHOP_POLICY,
                            "completion_evidence_kind": self._PUBLIC_WORKSHOP_EVIDENCE,
                            "completion_evidence_ref": evidence_ref,
                            "contract_created_event_id": intent.contract_created_event_id,
                            "fulfillment_request_digest": request_digest,
                        },
                    },
                    {
                        "event_type": "gameplay.contract.record_fulfilled",
                        "payload": {
                            "contract_id": contract_id,
                            "authority_ref": self._PUBLIC_WORKSHOP_POLICY_AUTHORITY,
                            "policy_ref": self._PUBLIC_WORKSHOP_POLICY,
                            "contract_created_event_id": intent.contract_created_event_id,
                        },
                    },
                ],
            },
        )
        return self._store.append_batch(EventStoreSettlementPlan.from_command_envelope(command).to_atomic_event_batch())

    def fulfill_municipal_drought_assessment_by_policy(
        self, intent: MunicipalDroughtAssessmentFulfillmentIntentV1
    ) -> AppendBatchResult:
        request_digest = _digest(intent.model_dump(mode="json"))
        existing = self._store.get_by_idempotency(self._PRINCIPAL, intent.idempotency_key)
        if existing is not None:
            if len(existing.committed_event_ids) == 2:
                completion = self._store.get_event(existing.committed_event_ids[0])
                fulfilled = self._store.get_event(existing.committed_event_ids[1])
                if (
                    completion.event_type == "gameplay.contract.service_completion_recorded"
                    and fulfilled.event_type == "gameplay.contract.record_fulfilled"
                    and completion.payload.get("contract_created_event_id")
                    == intent.contract_created_event_id
                    and completion.payload.get("fulfillment_request_digest")
                    == request_digest
                    and completion.command_id == intent.command_id
                    and completion.causation_id == intent.causation_id
                    and completion.correlation_id == intent.correlation_id
                ):
                    return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            return self._rejected_append(intent.command_id, "idempotency_key_reused")
        try:
            created = self._store.get_event(intent.contract_created_event_id)
        except KeyError:
            return self._rejected_append(intent.command_id, "municipal_drought_fulfillment_source_missing")
        payload = created.payload
        contract_id = payload.get("contract_id")
        advisory_event_id = payload.get("advisory_event_id")
        jurisdiction_ref = payload.get("jurisdiction_ref")
        if (
            created.event_type != "gameplay.contract.record_created"
            or created.stream_id != self._STREAM
            or created.stream_revision != intent.expected_contract_created_revision
            or created.visibility_policy != "authority_only"
            or not isinstance(contract_id, str)
            or not isinstance(advisory_event_id, str)
            or not isinstance(jurisdiction_ref, str)
            or not contract_id
            or not advisory_event_id
            or not jurisdiction_ref
            or payload.get("contract_type") != "simple_service"
            or payload.get("terms_ref") != self._MUNICIPAL_ASSESSMENT_TERMS
            or payload.get("completion_evidence_kind") != self._MUNICIPAL_ASSESSMENT_EVIDENCE
            or payload.get("party_refs") != [
                self._MUNICIPAL_ASSESSMENT_PROVIDER,
                self._MUNICIPAL_ASSESSMENT_RECEIVER,
            ]
            or payload.get("advisory_stream_revision") != intent.expected_advisory_revision
            or contract_id
            != f"contract:municipal-drought-assessment:{jurisdiction_ref}:{advisory_event_id}"
        ):
            return self._rejected_append(intent.command_id, "municipal_drought_fulfillment_source_invalid")
        try:
            advisory = self._store.get_event(advisory_event_id)
        except KeyError:
            return self._rejected_append(intent.command_id, "municipal_drought_fulfillment_advisory_missing")
        if (
            advisory.event_type != "gameplay.government.drought_advisory_issued"
            or advisory.visibility_policy != "project"
            or advisory.stream_id != f"gameplay:government:advisory:{jurisdiction_ref}"
            or advisory.stream_revision != intent.expected_advisory_revision
            or self._store.get_stream_head(advisory.stream_id) != intent.expected_advisory_revision
            or self._store.get_stream_head(self._STREAM) != intent.expected_contract_head
        ):
            return self._rejected_append(intent.command_id, "municipal_drought_fulfillment_revision_conflict")
        try:
            terms = self._terms_registry.get(self._MUNICIPAL_ASSESSMENT_TERMS)
        except ContractRuntimeError:
            return self._rejected_append(intent.command_id, "municipal_drought_fulfillment_terms_missing")
        record = self._projector.rebuild(self._store.read_events()).contracts.get(contract_id)
        if (
            terms
            != ContractTermsDefinition(
                self._MUNICIPAL_ASSESSMENT_TERMS,
                "simple_service",
                2,
                self._MUNICIPAL_ASSESSMENT_EVIDENCE,
            )
            or record is None
            or record.source_event_id != intent.contract_created_event_id
            or record.status != "active"
            or record.completion_evidence_ref is not None
            or self._MUNICIPAL_ASSESSMENT_POLICY_AUTHORITY not in self._policy_authorities
        ):
            return self._rejected_append(intent.command_id, "municipal_drought_fulfillment_eligibility_invalid")
        canonical_key = (
            "contract:municipal-drought-assessment:fulfillment:"
            f"{intent.contract_created_event_id}:{intent.expected_contract_created_revision}:"
            f"{intent.expected_advisory_revision}:{intent.expected_contract_head}:v1"
        )
        if intent.idempotency_key != canonical_key:
            return self._rejected_append(intent.command_id, "municipal_drought_fulfillment_idempotency_key_invalid")
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:municipal-drought-assessment-contract-fulfillment@1",
                contract_kind="contract_admission",
                owner_ref=self._PRINCIPAL,
                stream_ids=(self._STREAM,),
                event_types=(
                    "gameplay.contract.service_completion_recorded",
                    "gameplay.contract.record_fulfilled",
                ),
                projection_scope="authority_only",
            )
        except GovernedAuthorityContractError as exc:
            return self._rejected_append(intent.command_id, str(exc))
        evidence_ref = f"evidence:municipal-drought-assessment:completed:{contract_id}"
        command = GameplayCommandEnvelope(
            command_id=intent.command_id,
            command_type="gameplay.contract.fulfill_municipal_drought_assessment",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=None,
            project_ref=None,
            transaction_id=f"transaction:{intent.command_id}",
            idempotency_key=intent.idempotency_key,
            expected_revisions={self._STREAM: intent.expected_contract_head},
            read_set_revisions={advisory.stream_id: intent.expected_advisory_revision},
            causation_id=intent.causation_id,
            correlation_id=intent.correlation_id,
            source_ref=intent.contract_created_event_id,
            submitted_at=intent.submitted_at,
            pinned_revisions={
                "contract_created": intent.expected_contract_created_revision,
                "government_advisory": intent.expected_advisory_revision,
                "contract": intent.expected_contract_head,
            },
            payload={
                "stream_ref": self._STREAM,
                "event_type": "gameplay.contract.service_completion_recorded",
                "visibility_policy": "authority_only",
                "event_specs": [
                    {
                        "event_type": "gameplay.contract.service_completion_recorded",
                        "payload": {
                            "contract_id": contract_id,
                            "authority_ref": self._MUNICIPAL_ASSESSMENT_POLICY_AUTHORITY,
                            "policy_ref": self._MUNICIPAL_ASSESSMENT_POLICY,
                            "completion_evidence_kind": self._MUNICIPAL_ASSESSMENT_EVIDENCE,
                            "completion_evidence_ref": evidence_ref,
                            "contract_created_event_id": intent.contract_created_event_id,
                            "contract_created_revision": intent.expected_contract_created_revision,
                            "advisory_event_id": advisory_event_id,
                            "advisory_revision": intent.expected_advisory_revision,
                            "fulfillment_request_digest": request_digest,
                        },
                    },
                    {
                        "event_type": "gameplay.contract.record_fulfilled",
                        "payload": {
                            "contract_id": contract_id,
                            "authority_ref": self._MUNICIPAL_ASSESSMENT_POLICY_AUTHORITY,
                            "policy_ref": self._MUNICIPAL_ASSESSMENT_POLICY,
                            "contract_created_event_id": intent.contract_created_event_id,
                        },
                    },
                ],
            },
        )
        return self._store.append_batch(
            EventStoreSettlementPlan.from_command_envelope(command).to_atomic_event_batch()
        )

    def fulfill_contract_by_policy(self, *, command_id: str, contract_id: str, authority_ref: str, idempotency_key: str, causation_id: str, correlation_id: str) -> AppendBatchResult:
        return self._transition(command_id=command_id, contract_id=contract_id, authority_ref=authority_ref, reason=None, idempotency_key=idempotency_key, causation_id=causation_id, correlation_id=correlation_id)

    def terminate_contract_by_policy(self, *, command_id: str, contract_id: str, authority_ref: str, reason: str, idempotency_key: str, causation_id: str, correlation_id: str) -> AppendBatchResult:
        return self._transition(command_id=command_id, contract_id=contract_id, authority_ref=authority_ref, reason=reason, idempotency_key=idempotency_key, causation_id=causation_id, correlation_id=correlation_id)

    def complete_simple_service_by_policy(self, *, command_id: str, contract_id: str, authority_ref: str, completion_evidence_kind: str, completion_evidence_ref: str, idempotency_key: str, causation_id: str, correlation_id: str) -> AppendBatchResult:
        command = {"kind": "complete_simple_service", "command_id": command_id, "contract_id": contract_id, "authority_ref": authority_ref, "completion_evidence_kind": completion_evidence_kind, "completion_evidence_ref": completion_evidence_ref}
        digest = _digest(command)
        duplicate = self._duplicate(idempotency_key, digest)
        if duplicate is not None:
            return duplicate
        if authority_ref not in self._policy_authorities:
            raise ContractRuntimeError("contract_policy_denied")
        record = self._projector.rebuild(self._store.read_events()).contracts.get(contract_id)
        if record is None or record.status != "active":
            raise ContractRuntimeError("contract_not_active")
        if record.terms_ref in {
            self._MUNICIPAL_ASSESSMENT_TERMS,
            self._FACILITY_COMMISSIONING_TERMS,
            self._PUBLIC_WORKSHOP_TERMS,
        }:
            raise ContractRuntimeError("municipal_drought_fulfillment_row_required")
        terms = self._terms_registry.get(record.terms_ref)
        if record.contract_type != "simple_service" or not completion_evidence_ref or record.completion_evidence_kind != completion_evidence_kind or terms.completion_evidence_kind != completion_evidence_kind:
            raise ContractRuntimeError("contract_completion_evidence_invalid")
        events = [
            self._event(command_id, 1, "gameplay.contract.service_completion_recorded", {"contract_id": contract_id, "authority_ref": authority_ref, "completion_evidence_kind": completion_evidence_kind, "completion_evidence_ref": completion_evidence_ref}, causation_id, correlation_id),
            self._event(command_id, 2, "gameplay.contract.record_fulfilled", {"contract_id": contract_id, "authority_ref": authority_ref}, causation_id, correlation_id),
        ]
        return self._append(command_id, idempotency_key, digest, events, self._store.get_stream_head(self._STREAM))

    def _transition(self, *, command_id: str, contract_id: str, authority_ref: str, reason: str | None, idempotency_key: str, causation_id: str, correlation_id: str) -> AppendBatchResult:
        kind = "terminate_contract" if reason is not None else "fulfill_contract"
        command = {"kind": kind, "command_id": command_id, "contract_id": contract_id, "authority_ref": authority_ref, "reason": reason}
        digest = _digest(command)
        duplicate = self._duplicate(idempotency_key, digest)
        if duplicate is not None:
            return duplicate
        if authority_ref not in self._policy_authorities:
            raise ContractRuntimeError("contract_policy_denied")
        if reason is not None and not reason:
            raise ContractRuntimeError("contract_termination_reason_required")
        record = self._projector.rebuild(self._store.read_events()).contracts.get(contract_id)
        if record is None or record.status != "active":
            raise ContractRuntimeError("contract_not_active")
        if record.terms_ref in {self._MUNICIPAL_ASSESSMENT_TERMS, self._FACILITY_COMMISSIONING_TERMS}:
            raise ContractRuntimeError("municipal_drought_fulfillment_row_required")
        event_type = "gameplay.contract.record_terminated" if reason is not None else "gameplay.contract.record_fulfilled"
        payload: dict[str, object] = {"contract_id": contract_id, "authority_ref": authority_ref}
        if reason is not None:
            payload["reason"] = reason
        event = self._event(command_id, 1, event_type, payload, causation_id, correlation_id)
        return self._append(command_id, idempotency_key, digest, [event], self._store.get_stream_head(self._STREAM))

    def _append(self, command_id: str, idempotency_key: str, digest: str, events: list[dict[str, object]], revision: int) -> AppendBatchResult:
        return self._store.append_batch({"transaction_id": f"tx:{command_id}", "command_id": command_id, "expected_stream_revisions": {self._STREAM: revision}, "pinned_revisions": {self._STREAM: revision}, "events": events, "idempotency_record": {"principal_ref": self._PRINCIPAL, "idempotency_key": idempotency_key, "payload_digest": digest}, "outbox_entries": [], "result_digest": digest, "projection_refresh_hints": []})

    def accept_ogs_social_conflict_eligibility(self, *, source_event: object, expected_source_revision: int, command_id: str, idempotency_key: str, expected_contract_revision: int, causation_id: str, correlation_id: str) -> AppendBatchResult:
        """Record a Contract-owned eligibility marker from one exact Social case.

        This does not create a contract, obligation, payment, or penalty. The
        target Contract owner may later admit a separate terms-specific row.
        """
        from app.gameplay.organization_government_social_recipes import validate_ogs_recipe_source
        if getattr(source_event, "event_type", None) != "gameplay.social.norm_conflict_recorded@1" or getattr(source_event, "visibility_policy", None) != "project":
            return self._rejected_append(command_id, "ogs_social_recipe_source_invalid")
        source_revision = int(getattr(source_event, "stream_revision", 0))
        source_stream = str(getattr(source_event, "stream_id", ""))
        if source_revision != expected_source_revision or self._store.get_stream_head(source_stream) != expected_source_revision:
            return self._rejected_append(command_id, "ogs_social_recipe_source_stale")
        recipe = validate_ogs_recipe_source(recipe_ref="recipe:social-conflict-contract-eligibility@1", source_owner_ref="authority:p5:social", source_event_type=source_event.event_type, source_privacy_scope="project", source_revision=source_revision, expected_source_revision=expected_source_revision)
        if self._store.get_stream_head(self._STREAM) != expected_contract_revision:
            return self._rejected_append(command_id, "ogs_social_recipe_contract_revision_conflict")
        payload = {"acceptance_ref": f"acceptance:{recipe.recipe_ref}:{source_event.event_id}", "recipe_ref": recipe.recipe_ref, "source_event_id": source_event.event_id, "source_stream_id": source_stream, "source_stream_revision": source_revision, "source_owner_ref": recipe.source_owner_ref, "target_owner_ref": recipe.target_owner_ref}
        digest = _digest({"kind": "ogs_social_recipe_acceptance", **payload})
        event = self._event(command_id, 1, "gameplay.contract.ogs_social_conflict_eligibility_accepted@1", payload, causation_id, correlation_id)
        return self._append(command_id, idempotency_key, digest, [event], expected_contract_revision)

    @staticmethod
    def _rejected_append(command_id: str, error_code: str) -> AppendBatchResult:
        return AppendBatchResult(
            committed=False,
            transaction_id=f"transaction:{command_id}",
            command_id=command_id,
            idempotency_status="rejected",
            failure=GameplayFailure(error_code=error_code, message=error_code, failed_stage="municipal_drought_contract_admission"),
        )

    def _duplicate(self, idempotency_key: str, digest: str) -> AppendBatchResult | None:
        record = self._store.get_idempotency_record(self._PRINCIPAL, idempotency_key)
        if record is None:
            return None
        if record.payload_digest != digest:
            raise ContractRuntimeError("idempotency_key_reused")
        result = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if result is None:
            raise ContractRuntimeError("contract_idempotency_missing_result")
        return result.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)

    @classmethod
    def _event(cls, command_id: str, index: int, event_type: str, payload: Mapping[str, object], causation_id: str, correlation_id: str) -> dict[str, object]:
        return {"event_id": f"evt:{command_id}:contract:{index}", "event_type": event_type, "schema_version": 1, "stream_id": cls._STREAM, "stream_revision": 0, "global_sequence": 0, "transaction_id": f"tx:{command_id}", "command_id": command_id, "causation_id": causation_id, "correlation_id": correlation_id, "visibility_policy": "authority_only", "payload": dict(payload)}


def _party_refs(payload: Mapping[str, object]) -> tuple[str, ...]:
    value = payload.get("party_refs")
    if not isinstance(value, list) or len(value) < 2 or any(not isinstance(item, str) or not item for item in value) or len(set(value)) != len(value):
        raise ContractRuntimeError("contract_event_payload_invalid")
    return tuple(value)


def _text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ContractRuntimeError("contract_event_payload_invalid")
    return value


def _optional_text(payload: Mapping[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ContractRuntimeError("contract_event_payload_invalid")
    return value


def _digest(value: object) -> str:
    return sha256(json.dumps(value, default=lambda item: dict(item) if isinstance(item, Mapping) else item.__dict__, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


__all__ = [
    "ContractAuthorityService",
    "ContractProjection",
    "ContractProjector",
    "ContractRecord",
    "ContractRuntimeError",
    "ContractTermsDefinition",
    "ContractTermsRegistry",
    "GovernmentDroughtAssessmentContractIntentV1",
    "MunicipalDroughtAssessmentFulfillmentIntentV1",
    "FacilityCommissioningReviewContractIntentV1",
    "FacilityCommissioningReviewFulfillmentIntentV1",
    "PublicWorkshopSessionContractIntentV1",
    "PublicWorkshopSessionFulfillmentIntentV1",
]
