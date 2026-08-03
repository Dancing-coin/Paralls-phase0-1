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
from app.gameplay.ownership_runtime import OwnershipProjector


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
    _EVENT_TYPES = {
        "gameplay.credential.issued",
        "gameplay.credential.revoked",
        "gameplay.credential.superseded",
    }

    def rebuild(self, events: Sequence[GameplayEvent]) -> CredentialProjection:
        links: dict[str, CredentialLink] = {}
        revisions: dict[str, int] = {}
        for event in sorted(events, key=lambda value: (value.global_sequence, value.event_id)):
            if event.event_type not in self._EVENT_TYPES:
                continue
            payload = event.payload
            if event.event_type == "gameplay.credential.issued":
                credential_id = _text(payload, "credential_id")
                if credential_id in links:
                    raise CredentialRuntimeError("credential_duplicate")
                credential_kind = _text(payload, "credential_kind")
                proves = _text(payload, "proves")
                if credential_kind not in {"deed", "receipt", "certificate", "key", "contract_document"} or proves not in {"evidence_only", "access_only", "evidence_and_access"}:
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
            elif event.event_type == "gameplay.credential.revoked":
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

    def __init__(self, *, store: GameplayEventStore, inventory_registry: InventoryDefinitionRegistry) -> None:
        self._store = store
        self._projector = CredentialProjector()
        self._ownership_projector = OwnershipProjector()
        self._inventory_projector = InventoryProjector(inventory_registry)

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
        duplicate = self._duplicate(idempotency_key, digest)
        if duplicate is not None:
            return duplicate
        projection = self._projector.rebuild(self._store.read_events())
        if credential_id in projection.links or not all((credential_id, credential_item_ref, credential_holder_ref, right_id, issuer_ref)):
            raise CredentialRuntimeError("credential_invalid")
        if any(link.credential_item_ref == credential_item_ref and link.status == "active" for link in projection.links.values()):
            raise CredentialRuntimeError("credential_item_already_linked")
        if credential_kind not in {"deed", "receipt", "certificate", "key", "contract_document"} or proves not in {"evidence_only", "access_only", "evidence_and_access"}:
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
        duplicate = self._duplicate(idempotency_key, digest)
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
        duplicate = self._duplicate(idempotency_key, digest)
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
        return self._store.append_batch({"transaction_id": f"tx:{command_id}", "command_id": command_id, "expected_stream_revisions": dict(revisions), "pinned_revisions": dict(revisions), "events": events, "idempotency_record": {"principal_ref": self._PRINCIPAL, "idempotency_key": idempotency_key, "payload_digest": digest}, "outbox_entries": [], "result_digest": digest, "projection_refresh_hints": []})

    @classmethod
    def _event(cls, command_id: str, index: int, event_type: str, payload: Mapping[str, object], causation_id: str, correlation_id: str) -> dict[str, object]:
        return {"event_id": f"evt:{command_id}:credential:{index}", "event_type": event_type, "schema_version": 1, "stream_id": cls._STREAM, "stream_revision": 0, "global_sequence": 0, "transaction_id": f"tx:{command_id}", "command_id": command_id, "causation_id": causation_id, "correlation_id": correlation_id, "visibility_policy": "authority_only", "payload": dict(payload)}

    def _duplicate(self, idempotency_key: str, digest: str) -> AppendBatchResult | None:
        record = self._store.get_idempotency_record(self._PRINCIPAL, idempotency_key)
        if record is None:
            return None
        if record.payload_digest != digest:
            raise CredentialRuntimeError("idempotency_key_reused")
        result = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if result is None:
            raise CredentialRuntimeError("credential_idempotency_missing_result")
        return result.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)


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
