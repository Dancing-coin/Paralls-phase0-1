"""Typed-terms contract records without an arbitrary contract execution engine."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Mapping, Sequence

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayEvent


class ContractRuntimeError(ValueError):
    pass


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

    def rebuild(self, events: Sequence[GameplayEvent]) -> ContractProjection:
        contracts: dict[str, ContractRecord] = {}
        revisions: dict[str, int] = {}
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

    def __init__(self, *, store: GameplayEventStore, terms_registry: ContractTermsRegistry, policy_authorities: set[str]) -> None:
        self._store = store
        self._terms_registry = terms_registry
        self._policy_authorities = frozenset(value for value in policy_authorities if value)
        self._projector = ContractProjector()

    def create_contract(self, *, command_id: str, contract_id: str, contract_type: str, terms_ref: str, party_refs: Sequence[str], idempotency_key: str, causation_id: str, correlation_id: str) -> AppendBatchResult:
        command = {"kind": "create_contract", "command_id": command_id, "contract_id": contract_id, "contract_type": contract_type, "terms_ref": terms_ref, "party_refs": tuple(party_refs)}
        digest = _digest(command)
        duplicate = self._duplicate(idempotency_key, digest)
        if duplicate is not None:
            return duplicate
        terms = self._terms_registry.get(terms_ref)
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
        event_type = "gameplay.contract.record_terminated" if reason is not None else "gameplay.contract.record_fulfilled"
        payload: dict[str, object] = {"contract_id": contract_id, "authority_ref": authority_ref}
        if reason is not None:
            payload["reason"] = reason
        event = self._event(command_id, 1, event_type, payload, causation_id, correlation_id)
        return self._append(command_id, idempotency_key, digest, [event], self._store.get_stream_head(self._STREAM))

    def _append(self, command_id: str, idempotency_key: str, digest: str, events: list[dict[str, object]], revision: int) -> AppendBatchResult:
        return self._store.append_batch({"transaction_id": f"tx:{command_id}", "command_id": command_id, "expected_stream_revisions": {self._STREAM: revision}, "pinned_revisions": {self._STREAM: revision}, "events": events, "idempotency_record": {"principal_ref": self._PRINCIPAL, "idempotency_key": idempotency_key, "payload_digest": digest}, "outbox_entries": [], "result_digest": digest, "projection_refresh_hints": []})

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


__all__ = ["ContractAuthorityService", "ContractProjection", "ContractProjector", "ContractRecord", "ContractRuntimeError", "ContractTermsDefinition", "ContractTermsRegistry"]
