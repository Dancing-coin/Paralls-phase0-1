"""Event-sourced credential links that remain separate from ownership truth."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Mapping, Sequence

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import InventoryDefinitionRegistry, InventoryProjector
from app.gameplay.models import AppendBatchResult, GameplayEvent
from app.gameplay.owner_runtime_base import replay_duplicate
from app.gameplay.ownership_runtime import OwnershipProjector
from app.gameplay.credential_v2_event_schema import (
    CredentialV2EventSchemaError,
    validate_credential_v2_event,
)


class CredentialRuntimeError(ValueError):
    pass


@dataclass(frozen=True)
class CredentialLink:
    credential_id: str
    credential_item_ref: str
    issued_holder_ref: str
    issued_holder_inventory_revision: int
    right_id: str
    credential_kind: str
    proves: str
    issuer_ref: str
    status: str
    source_event_id: str


@dataclass(frozen=True)
class CredentialProjection:
    links: Mapping[str, CredentialLink]
    source_revision_vector: Mapping[str, int]


@dataclass(frozen=True)
class CredentialPresentationDecision:
    credential_id: str
    right_id: str | None
    credential_present: bool
    presenter_is_right_holder: bool
    authorized: bool
    error_code: str | None


class CredentialProjector:
    _DEFAULT_CREDENTIAL_KINDS = frozenset({"deed", "receipt", "certificate", "key", "contract_document"})
    _DEFAULT_PROVES = frozenset({"evidence_only", "access_only", "evidence_and_access"})
    _EVENT_TYPES = {
        "gameplay.credential.issued",
        "gameplay.credential.revoked",
        "gameplay.credential.superseded",
        "gameplay.credential.link_issued",
        "gameplay.credential.link_revoked",
        "gameplay.credential.link_superseded",
    }
    _V2_ISSUED = "gameplay.credential.link_issued"
    _V2_REVOKED = "gameplay.credential.link_revoked"
    _V2_SUPERSEDED = "gameplay.credential.link_superseded"

    def __init__(self, *, credential_kinds: Sequence[str] | None = None,
                 proves: Sequence[str] | None = None) -> None:
        self._credential_kinds = frozenset(self._DEFAULT_CREDENTIAL_KINDS if credential_kinds is None else credential_kinds)
        self._proves = frozenset(self._DEFAULT_PROVES if proves is None else proves)

    def rebuild(self, events: Sequence[GameplayEvent]) -> CredentialProjection:
        links: dict[str, CredentialLink] = {}
        revisions: dict[str, int] = {}
        for event in sorted(events, key=lambda value: (value.global_sequence, value.event_id)):
            if event.event_type not in self._EVENT_TYPES:
                continue
            is_v2 = event.event_type in {self._V2_ISSUED, self._V2_REVOKED, self._V2_SUPERSEDED}
            if is_v2:
                try:
                    validate_credential_v2_event(event.model_dump(mode="python"))
                except CredentialV2EventSchemaError as error:
                    raise CredentialRuntimeError(str(error)) from error
            payload = event.payload
            if event.event_type in {"gameplay.credential.issued", self._V2_ISSUED}:
                credential_id = _text(payload, "credential_id")
                if credential_id in links:
                    raise CredentialRuntimeError("credential_duplicate")
                credential_kind = _text(payload, "credential_kind")
                proves = _text(payload, "proves")
                if credential_kind not in self._credential_kinds or proves not in self._proves:
                    raise CredentialRuntimeError("credential_invalid")
                links[credential_id] = CredentialLink(
                    credential_id=credential_id,
                    credential_item_ref=_text(payload, "credential_item_ref"),
                    issued_holder_ref=_text(payload, "issued_holder_ref"),
                    issued_holder_inventory_revision=_nonnegative(payload, "issued_holder_inventory_revision"),
                    right_id=_text(payload, "right_id"),
                    credential_kind=credential_kind,
                    proves=proves,
                    issuer_ref=_text(payload, "issuer_ref"),
                    status="active",
                    source_event_id=event.event_id,
                )
            elif event.event_type in {"gameplay.credential.revoked", self._V2_REVOKED}:
                credential_id = _text(payload, "credential_id")
                link = links.get(credential_id)
                if link is None or link.status != "active" or link.issuer_ref != _text(payload, "issuer_ref"):
                    raise CredentialRuntimeError("credential_not_active")
                _text(payload, "reason")
                links[credential_id] = CredentialLink(**{**link.__dict__, "status": "revoked", "source_event_id": event.event_id})
            else:
                credential_id = _text(payload, "credential_id")
                replacement_credential_id = _text(payload, "replacement_credential_id")
                link = links.get(credential_id)
                if link is None or link.status != "active" or link.issuer_ref != _text(payload, "issuer_ref") or replacement_credential_id in links:
                    raise CredentialRuntimeError("credential_not_active")
                links[credential_id] = CredentialLink(**{**link.__dict__, "status": "superseded", "source_event_id": event.event_id})
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
        return CredentialProjection(
            links=MappingProxyType(dict(sorted(links.items()))),
            source_revision_vector=MappingProxyType(dict(sorted(revisions.items()))),
        )


class CredentialPresentationValidator:
    """Read-only policy precondition for an active credential plus right holder."""

    def __init__(self, *, store: GameplayEventStore, inventory_registry: InventoryDefinitionRegistry) -> None:
        self._store = store
        self._credential_projector = CredentialProjector()
        self._inventory_projector = InventoryProjector(inventory_registry)
        self._ownership_projector = OwnershipProjector()

    def verify_right_holder_presentation(self, *, credential_id: str, presenter_ref: str) -> CredentialPresentationDecision:
        links = self._credential_projector.rebuild(self._store.read_events()).links
        link = links.get(credential_id)
        if link is None or link.status != "active":
            return CredentialPresentationDecision(credential_id, None if link is None else link.right_id, False, False, False, "credential_not_active")
        inventory = self._inventory_projector.rebuild(presenter_ref, self._store.read_events())
        credential_present = link.credential_item_ref in inventory.items and link.credential_item_ref in inventory.locations
        right = self._ownership_projector.rebuild(self._store.read_events()).rights.get(link.right_id)
        presenter_is_right_holder = right is not None and right.holder_ref == presenter_ref
        if not credential_present:
            error_code = "credential_not_present"
        elif right is None:
            error_code = "ownership_right_missing"
        elif not presenter_is_right_holder:
            error_code = "ownership_right_holder_mismatch"
        else:
            error_code = None
        return CredentialPresentationDecision(
            credential_id=credential_id,
            right_id=link.right_id,
            credential_present=credential_present,
            presenter_is_right_holder=presenter_is_right_holder,
            authorized=error_code is None,
            error_code=error_code,
        )


class CredentialAuthorityService:
    """Issues document links; only OwnershipAuthorityService changes right holders."""

    _PRINCIPAL = "actor_gameplay.credential_domain"
    _STREAM = "gameplay:credentials"
    _OWNERSHIP_STREAM = "gameplay:ownership"
    _AUTHORITY_SCOPE = "scope:credential-domain"
    _AUTHORITY_EPOCH = 1

    def __init__(self, *, store: GameplayEventStore, inventory_registry: InventoryDefinitionRegistry,
                 credential_kinds: Sequence[str] | None = None,
                 proves: Sequence[str] | None = None) -> None:
        self._store = store
        self._credential_kinds = frozenset(CredentialProjector._DEFAULT_CREDENTIAL_KINDS if credential_kinds is None else credential_kinds)
        self._proves = frozenset(CredentialProjector._DEFAULT_PROVES if proves is None else proves)
        self._projector = CredentialProjector(credential_kinds=self._credential_kinds, proves=self._proves)
        self._ownership_projector = OwnershipProjector()
        self._inventory_projector = InventoryProjector(inventory_registry)

    def activate_authority_fence(self) -> None:
        self._store.register_authority_stream(
            self._STREAM, self._AUTHORITY_SCOPE, self._AUTHORITY_EPOCH, self._PRINCIPAL
        )

    def issue_credential(
        self,
        *,
        command_id: str,
        credential_id: str,
        credential_item_ref: str,
        credential_holder_ref: str,
        right_id: str,
        credential_kind: str,
        proves: str,
        issuer_ref: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        command = {
            "kind": "issue_credential",
            "command_id": command_id,
            "credential_id": credential_id,
            "credential_item_ref": credential_item_ref,
            "credential_holder_ref": credential_holder_ref,
            "right_id": right_id,
            "credential_kind": credential_kind,
            "proves": proves,
            "issuer_ref": issuer_ref,
        }
        digest = _digest(command)
        duplicate = self._duplicate(idempotency_key, digest, command_id, ("gameplay.credential.issued",))
        if duplicate is not None:
            return duplicate
        projection = self._projector.rebuild(self._store.read_events())
        if credential_id in projection.links or not all((credential_id, credential_item_ref, credential_holder_ref, right_id, issuer_ref)):
            raise CredentialRuntimeError("credential_invalid")
        if any(link.credential_item_ref == credential_item_ref and link.status == "active" for link in projection.links.values()):
            raise CredentialRuntimeError("credential_item_already_linked")
        if credential_kind not in self._credential_kinds or proves not in self._proves:
            raise CredentialRuntimeError("credential_invalid")
        if right_id not in self._ownership_projector.rebuild(self._store.read_events()).rights:
            raise CredentialRuntimeError("ownership_right_missing")
        holder_inventory = self._inventory_projector.rebuild(credential_holder_ref, self._store.read_events())
        if credential_item_ref not in holder_inventory.items or credential_item_ref not in holder_inventory.locations:
            raise CredentialRuntimeError("credential_item_not_present")
        inventory_stream = f"gameplay:inventory:{credential_holder_ref}"
        inventory_revision = self._store.get_stream_head(inventory_stream)
        event = self._event(command_id, 1, "gameplay.credential.issued", {"credential_id": credential_id, "credential_item_ref": credential_item_ref, "issued_holder_ref": credential_holder_ref, "issued_holder_inventory_revision": inventory_revision, "right_id": right_id, "credential_kind": credential_kind, "proves": proves, "issuer_ref": issuer_ref}, causation_id, correlation_id)
        return self._append(command_id, idempotency_key, digest, [event], {self._STREAM: self._store.get_stream_head(self._STREAM), self._OWNERSHIP_STREAM: self._store.get_stream_head(self._OWNERSHIP_STREAM), inventory_stream: inventory_revision})

    def revoke_credential(self, *, command_id: str, credential_id: str, issuer_ref: str, reason: str, idempotency_key: str, causation_id: str, correlation_id: str) -> AppendBatchResult:
        command = {"kind": "revoke_credential", "command_id": command_id, "credential_id": credential_id, "issuer_ref": issuer_ref, "reason": reason}
        digest = _digest(command)
        duplicate = self._duplicate(idempotency_key, digest, command_id, ("gameplay.credential.revoked",))
        if duplicate is not None:
            return duplicate
        link = self._projector.rebuild(self._store.read_events()).links.get(credential_id)
        if link is None or link.status != "active" or link.issuer_ref != issuer_ref or not reason:
            raise CredentialRuntimeError("credential_not_active")
        event = self._event(command_id, 1, "gameplay.credential.revoked", {"credential_id": credential_id, "issuer_ref": issuer_ref, "reason": reason}, causation_id, correlation_id)
        return self._append(command_id, idempotency_key, digest, [event], {self._STREAM: self._store.get_stream_head(self._STREAM)})

    def supersede_credential(self, *, command_id: str, prior_credential_id: str, replacement_credential_id: str, replacement_item_ref: str, replacement_holder_ref: str, issuer_ref: str, idempotency_key: str, causation_id: str, correlation_id: str) -> AppendBatchResult:
        command = {"kind": "supersede_credential", "command_id": command_id, "prior_credential_id": prior_credential_id, "replacement_credential_id": replacement_credential_id, "replacement_item_ref": replacement_item_ref, "replacement_holder_ref": replacement_holder_ref, "issuer_ref": issuer_ref}
        digest = _digest(command)
        duplicate = self._duplicate(idempotency_key, digest, command_id, ("gameplay.credential.superseded", "gameplay.credential.issued"))
        if duplicate is not None:
            return duplicate
        projection = self._projector.rebuild(self._store.read_events())
        prior = projection.links.get(prior_credential_id)
        if prior is None or prior.status != "active" or prior.issuer_ref != issuer_ref or replacement_credential_id in projection.links or not replacement_item_ref or not replacement_holder_ref:
            raise CredentialRuntimeError("credential_not_active")
        replacement_inventory = self._inventory_projector.rebuild(replacement_holder_ref, self._store.read_events())
        if replacement_item_ref not in replacement_inventory.items or replacement_item_ref not in replacement_inventory.locations:
            raise CredentialRuntimeError("credential_item_not_present")
        inventory_stream = f"gameplay:inventory:{replacement_holder_ref}"
        inventory_revision = self._store.get_stream_head(inventory_stream)
        events = [
            self._event(command_id, 1, "gameplay.credential.superseded", {"credential_id": prior_credential_id, "replacement_credential_id": replacement_credential_id, "issuer_ref": issuer_ref}, causation_id, correlation_id),
            self._event(command_id, 2, "gameplay.credential.issued", {"credential_id": replacement_credential_id, "credential_item_ref": replacement_item_ref, "issued_holder_ref": replacement_holder_ref, "issued_holder_inventory_revision": inventory_revision, "right_id": prior.right_id, "credential_kind": prior.credential_kind, "proves": prior.proves, "issuer_ref": issuer_ref}, causation_id, correlation_id),
        ]
        return self._append(command_id, idempotency_key, digest, events, {self._STREAM: self._store.get_stream_head(self._STREAM), inventory_stream: inventory_revision})

    def _append(self, command_id: str, idempotency_key: str, digest: str, events: list[dict[str, object]], revisions: Mapping[str, int]) -> AppendBatchResult:
        stream_ids = sorted({str(event["stream_id"]) for event in events})
        authority_contexts = []
        for stream_id in stream_ids:
            authority = self._store.get_authority_stream(stream_id)
            if authority is None:
                continue
            if authority is None or authority["scope_ref"] != self._AUTHORITY_SCOPE or authority["writer_ref"] != self._PRINCIPAL:
                raise CredentialRuntimeError("credential_authority_fence_mismatch")
            authority_contexts.append(authority)
        batch = {"transaction_id": f"tx:{command_id}", "command_id": command_id, "expected_stream_revisions": dict(revisions), "pinned_revisions": dict(revisions), "events": events, "idempotency_record": {"principal_ref": self._PRINCIPAL, "idempotency_key": idempotency_key, "payload_digest": digest}, "outbox_entries": [], "result_digest": digest, "projection_refresh_hints": []}
        if authority_contexts:
            return self._store.append_batch(batch, authority_contexts=authority_contexts)
        return self._store.append_batch(batch)

    @classmethod
    def _event(cls, command_id: str, index: int, event_type: str, payload: Mapping[str, object], causation_id: str, correlation_id: str) -> dict[str, object]:
        return {"event_id": f"evt:{command_id}:credential:{index}", "event_type": event_type, "schema_version": 1, "stream_id": cls._STREAM, "stream_revision": 0, "global_sequence": 0, "transaction_id": f"tx:{command_id}", "command_id": command_id, "causation_id": causation_id, "correlation_id": correlation_id, "visibility_policy": "authority_only", "payload": dict(payload)}

    def _duplicate(self, idempotency_key: str, digest: str, command_id: str,
                   event_types: tuple[str, ...]) -> AppendBatchResult | None:
        result = replay_duplicate(
            self._store, principal=self._PRINCIPAL, idempotency_key=idempotency_key,
            payload_digest=digest, error_factory=CredentialRuntimeError,
            missing_result_code="credential_idempotency_missing_result",
        )
        if result is None:
            return None
        if not result.committed or result.command_id != command_id or result.transaction_id != f"tx:{command_id}":
            raise CredentialRuntimeError("credential_replay_transaction_mismatch")
        batch = self._store.get_transaction(result.transaction_id)
        if (batch is None or batch.transaction_id != result.transaction_id or batch.command_id != command_id
                or batch.idempotency_record.principal_ref != self._PRINCIPAL
                or batch.idempotency_record.idempotency_key != idempotency_key
                or batch.idempotency_record.payload_digest != digest):
            raise CredentialRuntimeError("credential_replay_transaction_mismatch")
        ids = result.committed_event_ids
        if len(ids) != len(event_types) or len(set(ids)) != len(ids) or len(batch.events) != len(event_types):
            raise CredentialRuntimeError("credential_replay_event_count_mismatch")
        resolved = []
        for event_id in ids:
            try:
                resolved.append(self._store.get_event(event_id))
            except KeyError as error:
                raise CredentialRuntimeError("credential_replay_event_missing") from error
        if (ids != [event.event_id for event in batch.events]
                or tuple(event.event_type for event in resolved) != event_types
                or any(event != original or event.transaction_id != batch.transaction_id or event.command_id != command_id
                       for event, original in zip(resolved, batch.events))
                or result.global_sequence_range != (resolved[0].global_sequence, resolved[-1].global_sequence)
                or result.resulting_stream_revisions != {event.stream_id: event.stream_revision for event in resolved}):
            raise CredentialRuntimeError("credential_replay_transaction_mismatch")
        return result


def _text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise CredentialRuntimeError("credential_event_payload_invalid")
    return value


def _nonnegative(payload: Mapping[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or value < 0:
        raise CredentialRuntimeError("credential_event_payload_invalid")
    return value


def _digest(value: object) -> str:
    return sha256(json.dumps(value, default=lambda item: dict(item) if isinstance(item, Mapping) else item.__dict__, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


__all__ = ["CredentialAuthorityService", "CredentialLink", "CredentialPresentationDecision", "CredentialPresentationValidator", "CredentialProjection", "CredentialProjector", "CredentialRuntimeError"]
