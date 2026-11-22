"""Event-sourced credential links that remain separate from ownership truth."""

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Mapping, Sequence

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import InventoryDefinitionRegistry, InventoryProjector
from app.gameplay.models import AppendBatchResult, GameplayEvent
from app.gameplay.owner_runtime_base import OwnerCommitBuilder, StoreReadSnapshot, replay_duplicate
from app.gameplay.ownership_runtime import OwnershipProjector
from app.gameplay.credential_v2_event_schema import (
    CredentialV2EventSchemaError,
    credential_holder_stream_id,
    credential_link_stream_id,
    validate_credential_v2_event,
    validate_credential_v2_holder_event,
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
class BondCredentialLink:
    credential_id: str
    credential_item_ref: str
    issued_holder_ref: str
    issued_holder_inventory_revision: int
    bond_ref: str
    credential_kind: str
    proves: str
    issuer_ref: str
    status: str
    source_event_id: str


@dataclass(frozen=True)
class CredentialProjection:
    links: Mapping[str, CredentialLink | BondCredentialLink]
    source_revision_vector: Mapping[str, int]


@dataclass(frozen=True)
class CredentialPresentationDecision:
    credential_id: str
    right_id: str | None
    credential_present: bool
    presenter_is_right_holder: bool
    authorized: bool
    error_code: str | None
    bond_ref: str | None = None


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
        "gameplay.credential.item_claimed",
        "gameplay.credential.item_released",
    }
    _V2_ISSUED = "gameplay.credential.link_issued"
    _V2_REVOKED = "gameplay.credential.link_revoked"
    _V2_SUPERSEDED = "gameplay.credential.link_superseded"
    _V2_HOLDER_EVENTS = {"gameplay.credential.item_claimed", "gameplay.credential.item_released"}

    def __init__(self, *, credential_kinds: Sequence[str] | None = None,
                 proves: Sequence[str] | None = None) -> None:
        self._credential_kinds = frozenset(self._DEFAULT_CREDENTIAL_KINDS if credential_kinds is None else credential_kinds)
        self._proves = frozenset(self._DEFAULT_PROVES if proves is None else proves)

    def rebuild(self, events: Sequence[GameplayEvent]) -> CredentialProjection:
        links: dict[str, CredentialLink | BondCredentialLink] = {}
        holders: dict[str, str] = {}
        revisions: dict[str, int] = {}
        for event in sorted(events, key=lambda value: (value.global_sequence, value.event_id)):
            if event.event_type not in self._EVENT_TYPES:
                continue
            is_v2 = event.event_type in {self._V2_ISSUED, self._V2_REVOKED, self._V2_SUPERSEDED}
            is_holder = event.event_type in self._V2_HOLDER_EVENTS
            if is_v2:
                try:
                    validate_credential_v2_event(event.model_dump(mode="python"))
                except CredentialV2EventSchemaError as error:
                    raise CredentialRuntimeError(str(error)) from error
            elif is_holder:
                try:
                    validate_credential_v2_holder_event(event.model_dump(mode="python"))
                except CredentialV2EventSchemaError as error:
                    raise CredentialRuntimeError(str(error)) from error
            payload = event.payload
            if event.event_type in {"gameplay.credential.issued", self._V2_ISSUED}:
                credential_id = _text(payload, "credential_id")
                if credential_id in links:
                    raise CredentialRuntimeError("credential_duplicate")
                credential_kind = _text(payload, "credential_kind")
                proves = _text(payload, "proves")
                link_fields = dict(
                    credential_id=credential_id,
                    credential_item_ref=_text(payload, "credential_item_ref"),
                    issued_holder_ref=_text(payload, "issued_holder_ref"),
                    issued_holder_inventory_revision=_nonnegative(payload, "issued_holder_inventory_revision"),
                    credential_kind=credential_kind,
                    proves=proves,
                    issuer_ref=_text(payload, "issuer_ref"),
                    status="active",
                    source_event_id=event.event_id,
                )
                if "right_id" in payload:
                    links[credential_id] = CredentialLink(
                        **link_fields, right_id=_text(payload, "right_id")
                    )
                else:
                    links[credential_id] = BondCredentialLink(
                        **link_fields, bond_ref=_text(payload, "bond_ref")
                    )
            elif event.event_type in {"gameplay.credential.revoked", self._V2_REVOKED}:
                credential_id = _text(payload, "credential_id")
                link = links.get(credential_id)
                if link is None or link.status != "active" or link.issuer_ref != _text(payload, "issuer_ref"):
                    raise CredentialRuntimeError("credential_not_active")
                _text(payload, "reason")
                links[credential_id] = replace(link, status="revoked", source_event_id=event.event_id)
            elif event.event_type in {"gameplay.credential.superseded", self._V2_SUPERSEDED}:
                credential_id = _text(payload, "credential_id")
                replacement_credential_id = _text(payload, "replacement_credential_id")
                link = links.get(credential_id)
                if link is None or link.status != "active" or link.issuer_ref != _text(payload, "issuer_ref") or replacement_credential_id in links:
                    raise CredentialRuntimeError("credential_not_active")
                links[credential_id] = replace(link, status="superseded", source_event_id=event.event_id)
            elif event.event_type == "gameplay.credential.item_claimed":
                item_ref = _text(payload, "item_ref")
                credential_id = _text(payload, "credential_id")
                link = links.get(credential_id)
                if (item_ref in holders or link is None or link.status != "active"
                        or link.credential_item_ref != item_ref):
                    raise CredentialRuntimeError("credential_item_already_linked")
                holders[item_ref] = credential_id
            elif event.event_type == "gameplay.credential.item_released":
                item_ref = _text(payload, "item_ref")
                credential_id = _text(payload, "credential_id")
                link = links.get(credential_id)
                if link is None or link.status == "active" or link.credential_item_ref != item_ref:
                    raise CredentialRuntimeError("credential_item_not_linked")
                current = holders.get(item_ref)
                if current is not None and current != credential_id:
                    raise CredentialRuntimeError("credential_item_not_linked")
                holders.pop(item_ref, None)
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
        return CredentialProjection(
            links=MappingProxyType(dict(sorted(links.items()))),
            source_revision_vector=MappingProxyType(dict(sorted(revisions.items()))),
        )


class CredentialPresentationValidator:
    """Read-only policy precondition for an active credential plus right holder."""

    def __init__(self, *, store: GameplayEventStore, inventory_registry: InventoryDefinitionRegistry,
                 credential_kinds: Sequence[str] | None = None,
                 proves: Sequence[str] | None = None) -> None:
        self._store = store
        self._credential_projector = CredentialProjector(credential_kinds=credential_kinds, proves=proves)
        self._inventory_projector = InventoryProjector(inventory_registry)
        self._ownership_projector = OwnershipProjector()

    def verify_right_holder_presentation(self, *, credential_id: str, presenter_ref: str,
                                         world_tick: int | None = None) -> CredentialPresentationDecision:
        return self._verify_presentation_from_events(
            self._store.read_events(), credential_id=credential_id,
            presenter_ref=presenter_ref, world_tick=world_tick,
        )

    def _verify_presentation_from_events(
        self, events: Sequence[GameplayEvent], *, credential_id: str, presenter_ref: str,
        world_tick: int | None,
    ) -> CredentialPresentationDecision:
        links = self._credential_projector.rebuild(events).links
        link = links.get(credential_id)
        if link is None or link.status != "active":
            return CredentialPresentationDecision(
                credential_id, link.right_id if isinstance(link, CredentialLink) else None,
                False, False, False, "credential_not_active",
                link.bond_ref if isinstance(link, BondCredentialLink) else None,
            )
        inventory = self._inventory_projector.rebuild(presenter_ref, events)
        credential_present = link.credential_item_ref in inventory.items and link.credential_item_ref in inventory.locations
        ownership = self._ownership_projector.rebuild(events)
        bond_ref = link.bond_ref if isinstance(link, BondCredentialLink) else None
        right_id = link.right_id if isinstance(link, CredentialLink) else None
        if bond_ref is None:
            right = ownership.rights.get(right_id)
            bond = None
            presenter_is_right_holder = right is not None and right.holder_ref == presenter_ref
        else:
            right = None
            bond = ownership.bonds.get(bond_ref)
            presenter_is_right_holder = bond is not None and bond.subject_ref == presenter_ref
        if not credential_present:
            error_code = "credential_not_present"
        elif bond_ref is not None and (type(world_tick) is not int or world_tick < 0):
            error_code = "ownership_world_tick_required"
        elif bond_ref is not None and bond is None:
            error_code = "ownership_bond_missing"
        elif bond_ref is not None and bond.status != "active":
            error_code = "ownership_bond_not_active"
        elif bond_ref is not None and bond.term_expires_at is not None and world_tick >= bond.term_expires_at:
            error_code = "ownership_bond_expired"
        elif bond_ref is None and right is None:
            error_code = "ownership_right_missing"
        elif not presenter_is_right_holder:
            error_code = "ownership_bond_subject_mismatch" if bond_ref is not None else "ownership_right_holder_mismatch"
        else:
            error_code = None
        return CredentialPresentationDecision(
            credential_id=credential_id,
            right_id=right_id,
            credential_present=credential_present,
            presenter_is_right_holder=presenter_is_right_holder,
            authorized=error_code is None,
            error_code=error_code,
            bond_ref=bond_ref,
        )


class CredentialAuthorityService:
    """Issues document links; only OwnershipAuthorityService changes right holders."""

    _PRINCIPAL = "actor_gameplay.credential_domain"
    _STREAM = "gameplay:credentials"
    _OWNERSHIP_STREAM = "gameplay:ownership"
    _AUTHORITY_SCOPE = "scope:credential-domain"
    _AUTHORITY_EPOCH = 1
    _V2_PRINCIPAL = "actor_gameplay.credential_domain_v2"
    _V2_AUTHORITY_EPOCH = 2
    _CONDITION_REF = "credential_legacy_rule"
    _CONDITION_REVISION = 1

    def __init__(self, *, store: GameplayEventStore, inventory_registry: InventoryDefinitionRegistry,
                 credential_kinds: Sequence[str] | None = None,
                 proves: Sequence[str] | None = None) -> None:
        self._store = store
        self._credential_kinds = frozenset(CredentialProjector._DEFAULT_CREDENTIAL_KINDS if credential_kinds is None else credential_kinds)
        self._proves = frozenset(CredentialProjector._DEFAULT_PROVES if proves is None else proves)
        self._projector = CredentialProjector(credential_kinds=self._credential_kinds, proves=self._proves)
        self._ownership_projector = OwnershipProjector()
        self._inventory_projector = InventoryProjector(inventory_registry)
        self._reads = StoreReadSnapshot(store)
        self._v2_enabled = False

    def activate_authority_fence(self) -> None:
        self._store.register_authority_stream(
            self._STREAM, self._AUTHORITY_SCOPE, self._AUTHORITY_EPOCH, self._PRINCIPAL
        )

    def activate_v2_authority(self) -> None:
        current = self._store.get_authority_stream(self._STREAM)
        target = {
            "stream_id": self._STREAM,
            "scope_ref": self._AUTHORITY_SCOPE,
            "epoch": self._V2_AUTHORITY_EPOCH,
            "writer_ref": self._V2_PRINCIPAL,
        }
        if current is None:
            self._store.register_authority_stream(
                self._STREAM, self._AUTHORITY_SCOPE, self._V2_AUTHORITY_EPOCH, self._V2_PRINCIPAL
            )
        elif current == target:
            pass
        elif (current["scope_ref"], current["epoch"], current["writer_ref"]) == (
                self._AUTHORITY_SCOPE, self._AUTHORITY_EPOCH, self._PRINCIPAL):
            self._store.update_authority_stream(
                self._STREAM, self._AUTHORITY_SCOPE, self._AUTHORITY_EPOCH,
                self._PRINCIPAL, self._V2_AUTHORITY_EPOCH, self._V2_PRINCIPAL,
            )
        else:
            raise CredentialRuntimeError("credential_authority_fence_mismatch")
        self._v2_enabled = True

    def issue_credential(
        self,
        *,
        command_id: str,
        credential_id: str,
        credential_item_ref: str,
        credential_holder_ref: str,
        right_id: str | None = None,
        bond_ref: str | None = None,
        world_tick: int | None = None,
        credential_kind: str,
        proves: str,
        issuer_ref: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        if right_id is not None and (type(right_id) is not str or not right_id):
            raise CredentialRuntimeError("credential_invalid")
        if bond_ref is not None and (type(bond_ref) is not str or not bond_ref):
            raise CredentialRuntimeError("credential_invalid")
        if (right_id is None) == (bond_ref is None):
            raise CredentialRuntimeError("credential_reference_invalid")
        if bond_ref is not None and (not self._v2_enabled or type(world_tick) is not int or world_tick < 0):
            raise CredentialRuntimeError("credential_bond_world_tick_required")
        command = {
            "kind": "issue_credential",
            "command_id": command_id,
            "credential_id": credential_id,
            "credential_item_ref": credential_item_ref,
            "credential_holder_ref": credential_holder_ref,
            "credential_kind": credential_kind,
            "proves": proves,
            "issuer_ref": issuer_ref,
        }
        command["right_id" if right_id is not None else "bond_ref"] = right_id if right_id is not None else bond_ref
        if bond_ref is not None:
            command["world_tick"] = world_tick
        digest = _digest(command)
        event_type = "gameplay.credential.link_issued" if self._v2_enabled else "gameplay.credential.issued"
        principal = self._V2_PRINCIPAL if self._v2_enabled else self._PRINCIPAL
        replay_types = (event_type, "gameplay.credential.item_claimed") if self._v2_enabled else (event_type,)
        duplicate = self._duplicate(idempotency_key, digest, command_id, replay_types, principal=principal)
        if duplicate is not None:
            return duplicate
        credential_events = self._store.read_events()
        projection = self._projector.rebuild(credential_events)
        if credential_id in projection.links or not all((credential_id, credential_item_ref, credential_holder_ref, issuer_ref)):
            raise CredentialRuntimeError("credential_invalid")
        if any(link.credential_item_ref == credential_item_ref and link.status == "active" for link in projection.links.values()):
            raise CredentialRuntimeError("credential_item_already_linked")
        if credential_kind not in self._credential_kinds or proves not in self._proves:
            raise CredentialRuntimeError("credential_invalid")
        ownership = self._ownership_projector.rebuild(credential_events)
        if right_id is not None and right_id not in ownership.rights:
            raise CredentialRuntimeError("ownership_right_missing")
        bond = ownership.bonds.get(bond_ref) if bond_ref is not None else None
        if bond_ref is not None and (
            bond is None or bond.status != "active"
            or bond.subject_ref != credential_holder_ref
            or (bond.term_expires_at is not None and world_tick >= bond.term_expires_at)
        ):
            raise CredentialRuntimeError("ownership_bond_unqualified")
        holder_inventory = self._inventory_projector.rebuild(credential_holder_ref, credential_events)
        if credential_item_ref not in holder_inventory.items or credential_item_ref not in holder_inventory.locations:
            raise CredentialRuntimeError("credential_item_not_present")
        inventory_stream = f"gameplay:inventory:{credential_holder_ref}"
        inventory_revision = self._store.get_stream_head(inventory_stream)
        if self._v2_enabled:
            link_stream = credential_link_stream_id(credential_id)
            holder_stream = credential_holder_stream_id(credential_item_ref)
            event = self._v2_event(command_id, 1, event_type, link_stream, {
                "credential_id": credential_id,
                "credential_item_ref": credential_item_ref,
                "issued_holder_ref": credential_holder_ref,
                "issued_holder_inventory_revision": inventory_revision,
                "credential_kind": credential_kind,
                "proves": proves,
                "issuer_ref": issuer_ref,
                "from_state": "absent",
                "to_state": "issued",
                "condition_ref": self._CONDITION_REF,
                "condition_revision": self._CONDITION_REVISION,
            }, causation_id, correlation_id,
                schema_version=3 if bond_ref is not None else 2)
            if right_id is not None:
                event["payload"]["right_id"] = right_id
            else:
                event["payload"]["bond_ref"] = bond_ref
            claimed = self._holder_event(command_id, 2, "gameplay.credential.item_claimed", holder_stream,
                credential_id, credential_item_ref, "absent", "occupied", causation_id, correlation_id)
            revisions = {
                link_stream: max((event.stream_revision for event in credential_events if event.stream_id == link_stream), default=0),
                holder_stream: max((event.stream_revision for event in credential_events if event.stream_id == holder_stream), default=0),
                inventory_stream: inventory_revision,
            }
            if bond_ref is not None:
                revisions[self._OWNERSHIP_STREAM] = ownership.source_revision_vector.get(self._OWNERSHIP_STREAM, 0)
            else:
                revisions[self._OWNERSHIP_STREAM] = self._store.get_stream_head(self._OWNERSHIP_STREAM)
            return self._append(command_id, idempotency_key, digest, [event, claimed], revisions,
                                principal=principal, v2_streams=(link_stream, holder_stream))
        event = self._event(command_id, 1, "gameplay.credential.issued", {"credential_id": credential_id, "credential_item_ref": credential_item_ref, "issued_holder_ref": credential_holder_ref, "issued_holder_inventory_revision": inventory_revision, "right_id": right_id, "credential_kind": credential_kind, "proves": proves, "issuer_ref": issuer_ref}, causation_id, correlation_id)
        return self._append(command_id, idempotency_key, digest, [event], {self._STREAM: self._store.get_stream_head(self._STREAM), self._OWNERSHIP_STREAM: self._store.get_stream_head(self._OWNERSHIP_STREAM), inventory_stream: inventory_revision})

    def revoke_credential(self, *, command_id: str, credential_id: str, issuer_ref: str, reason: str, idempotency_key: str, causation_id: str, correlation_id: str) -> AppendBatchResult:
        command = {"kind": "revoke_credential", "command_id": command_id, "credential_id": credential_id, "issuer_ref": issuer_ref, "reason": reason}
        digest = _digest(command)
        event_type = "gameplay.credential.link_revoked" if self._v2_enabled else "gameplay.credential.revoked"
        principal = self._V2_PRINCIPAL if self._v2_enabled else self._PRINCIPAL
        replay_types = (event_type, "gameplay.credential.item_released") if self._v2_enabled else (event_type,)
        duplicate = self._duplicate(idempotency_key, digest, command_id, replay_types, principal=principal)
        if duplicate is not None:
            return duplicate
        credential_events = self._store.read_events()
        link = self._projector.rebuild(credential_events).links.get(credential_id)
        if link is None or link.status != "active" or link.issuer_ref != issuer_ref or not reason:
            raise CredentialRuntimeError("credential_not_active")
        if self._v2_enabled:
            link_stream = credential_link_stream_id(credential_id)
            holder_stream = credential_holder_stream_id(link.credential_item_ref)
            event = self._v2_event(command_id, 1, event_type, link_stream, {
                "credential_id": credential_id,
                "issuer_ref": issuer_ref,
                "reason": reason,
                "from_state": "issued",
                "to_state": "revoked",
                "condition_ref": self._CONDITION_REF,
                "condition_revision": self._CONDITION_REVISION,
            }, causation_id, correlation_id)
            released = self._holder_event(command_id, 2, "gameplay.credential.item_released", holder_stream,
                credential_id, link.credential_item_ref, "occupied", "absent", causation_id, correlation_id)
            revisions = {
                link_stream: max((event.stream_revision for event in credential_events if event.stream_id == link_stream), default=0),
                holder_stream: max((event.stream_revision for event in credential_events if event.stream_id == holder_stream), default=0),
            }
            return self._append(command_id, idempotency_key, digest, [event, released], revisions,
                                principal=principal, v2_streams=(link_stream, holder_stream))
        event = self._event(command_id, 1, "gameplay.credential.revoked", {"credential_id": credential_id, "issuer_ref": issuer_ref, "reason": reason}, causation_id, correlation_id)
        return self._append(command_id, idempotency_key, digest, [event], {self._STREAM: self._store.get_stream_head(self._STREAM)})

    def supersede_credential(self, *, command_id: str, prior_credential_id: str, replacement_credential_id: str, replacement_item_ref: str, replacement_holder_ref: str, issuer_ref: str, idempotency_key: str, causation_id: str, correlation_id: str) -> AppendBatchResult:
        command = {"kind": "supersede_credential", "command_id": command_id, "prior_credential_id": prior_credential_id, "replacement_credential_id": replacement_credential_id, "replacement_item_ref": replacement_item_ref, "replacement_holder_ref": replacement_holder_ref, "issuer_ref": issuer_ref}
        digest = _digest(command)
        event_types = (("gameplay.credential.link_superseded", "gameplay.credential.link_issued",
                        "gameplay.credential.item_released", "gameplay.credential.item_claimed")
                       if self._v2_enabled else ("gameplay.credential.superseded", "gameplay.credential.issued"))
        principal = self._V2_PRINCIPAL if self._v2_enabled else self._PRINCIPAL
        duplicate = self._duplicate(idempotency_key, digest, command_id, event_types, principal=principal)
        if duplicate is not None:
            return duplicate
        credential_events = self._reads.all_events()
        projection = self._projector.rebuild(credential_events)
        prior = projection.links.get(prior_credential_id)
        if prior is None or prior.status != "active" or prior.issuer_ref != issuer_ref or replacement_credential_id in projection.links or not replacement_item_ref or not replacement_holder_ref:
            raise CredentialRuntimeError("credential_not_active")
        replacement_inventory = self._inventory_projector.rebuild(replacement_holder_ref, credential_events)
        if replacement_item_ref not in replacement_inventory.items or replacement_item_ref not in replacement_inventory.locations:
            raise CredentialRuntimeError("credential_item_not_present")
        inventory_stream = f"gameplay:inventory:{replacement_holder_ref}"
        inventory_revision = max(
            (event.stream_revision for event in credential_events if event.stream_id == inventory_stream),
            default=0,
        )
        if self._v2_enabled:
            if any(link.credential_item_ref == replacement_item_ref and link.status == "active"
                   and link.credential_id != prior_credential_id for link in projection.links.values()):
                raise CredentialRuntimeError("credential_item_already_linked")
            prior_link_stream = credential_link_stream_id(prior_credential_id)
            replacement_link_stream = credential_link_stream_id(replacement_credential_id)
            prior_holder_stream = credential_holder_stream_id(prior.credential_item_ref)
            replacement_holder_stream = credential_holder_stream_id(replacement_item_ref)
            events = [
                self._v2_event(command_id, 1, "gameplay.credential.link_superseded", prior_link_stream, {
                    "credential_id": prior_credential_id,
                    "replacement_credential_id": replacement_credential_id,
                    "issuer_ref": issuer_ref,
                    "from_state": "issued",
                    "to_state": "superseded",
                    "condition_ref": self._CONDITION_REF,
                    "condition_revision": self._CONDITION_REVISION,
                }, causation_id, correlation_id),
                self._v2_event(command_id, 2, "gameplay.credential.link_issued", replacement_link_stream, {
                    "credential_id": replacement_credential_id,
                    "credential_item_ref": replacement_item_ref,
                    "issued_holder_ref": replacement_holder_ref,
                    "issued_holder_inventory_revision": inventory_revision,
                    **({"right_id": prior.right_id} if isinstance(prior, CredentialLink)
                       else {"bond_ref": prior.bond_ref}),
                    "credential_kind": prior.credential_kind,
                    "proves": prior.proves,
                    "issuer_ref": issuer_ref,
                    "from_state": "absent",
                    "to_state": "issued",
                    "condition_ref": self._CONDITION_REF,
                    "condition_revision": self._CONDITION_REVISION,
                }, causation_id, correlation_id,
                    schema_version=3 if isinstance(prior, BondCredentialLink) else 2),
                self._holder_event(command_id, 3, "gameplay.credential.item_released", prior_holder_stream,
                    prior_credential_id, prior.credential_item_ref, "occupied", "absent", causation_id, correlation_id),
                self._holder_event(command_id, 4, "gameplay.credential.item_claimed", replacement_holder_stream,
                    replacement_credential_id, replacement_item_ref, "absent", "occupied", causation_id, correlation_id),
            ]
            revisions = {
                prior_link_stream: max((event.stream_revision for event in credential_events if event.stream_id == prior_link_stream), default=0),
                replacement_link_stream: max((event.stream_revision for event in credential_events if event.stream_id == replacement_link_stream), default=0),
                prior_holder_stream: max((event.stream_revision for event in credential_events if event.stream_id == prior_holder_stream), default=0),
                replacement_holder_stream: max((event.stream_revision for event in credential_events if event.stream_id == replacement_holder_stream), default=0),
                inventory_stream: inventory_revision,
            }
            return self._append(command_id, idempotency_key, digest, events, revisions,
                                principal=principal, v2_streams=(prior_link_stream, replacement_link_stream,
                                                                 prior_holder_stream, replacement_holder_stream))
        events = [
            self._event(command_id, 1, "gameplay.credential.superseded", {"credential_id": prior_credential_id, "replacement_credential_id": replacement_credential_id, "issuer_ref": issuer_ref}, causation_id, correlation_id),
            self._event(command_id, 2, "gameplay.credential.issued", {"credential_id": replacement_credential_id, "credential_item_ref": replacement_item_ref, "issued_holder_ref": replacement_holder_ref, "issued_holder_inventory_revision": inventory_revision, "right_id": prior.right_id, "credential_kind": prior.credential_kind, "proves": prior.proves, "issuer_ref": issuer_ref}, causation_id, correlation_id),
        ]
        return self._append(command_id, idempotency_key, digest, events, {self._STREAM: projection.source_revision_vector.get(self._STREAM, 0), inventory_stream: inventory_revision})

    def _append(self, command_id: str, idempotency_key: str, digest: str,
                events: list[dict[str, object]], revisions: Mapping[str, int], *,
                principal: str | None = None, v2_streams: tuple[str, ...] = ()) -> AppendBatchResult:
        principal = self._PRINCIPAL if principal is None else principal
        stream_ids = sorted({str(event["stream_id"]) for event in events})
        authority_contexts = []
        for stream_id in dict.fromkeys(v2_streams):
            authority = self._store.get_authority_stream(stream_id)
            if authority is None:
                self._store.register_authority_stream(
                    stream_id, self._AUTHORITY_SCOPE, self._V2_AUTHORITY_EPOCH, self._V2_PRINCIPAL
                )
                authority = self._store.get_authority_stream(stream_id)
            if (authority is None or authority["scope_ref"] != self._AUTHORITY_SCOPE
                    or authority["writer_ref"] != self._V2_PRINCIPAL):
                raise CredentialRuntimeError("credential_authority_fence_mismatch")
        for stream_id in stream_ids:
            authority = self._store.get_authority_stream(stream_id)
            if authority is None:
                continue
            if authority["scope_ref"] != self._AUTHORITY_SCOPE or authority["writer_ref"] != principal:
                raise CredentialRuntimeError("credential_authority_fence_mismatch")
            authority_contexts.append(authority)
        batch = OwnerCommitBuilder.build(
            principal_ref=principal,
            command_id=command_id,
            transaction_id=f"tx:{command_id}",
            idempotency_key=idempotency_key,
            payload_digest=digest,
            events=events,
            expected_stream_revisions=revisions,
            pinned_revisions=revisions,
            result_digest=digest,
        )
        if authority_contexts:
            return self._store.append_batch(batch, authority_contexts=authority_contexts)
        return self._store.append_batch(batch)

    @classmethod
    def _v2_event(cls, command_id: str, index: int, event_type: str, stream_id: str,
                  payload: Mapping[str, object], causation_id: str, correlation_id: str,
                  *, schema_version: int = 2) -> dict[str, object]:
        return {"event_id": f"evt:{command_id}:credential:{index}", "event_type": event_type,
                "schema_version": schema_version, "stream_id": stream_id, "stream_revision": 0,
                "global_sequence": 0, "transaction_id": f"tx:{command_id}",
                "command_id": command_id, "causation_id": causation_id,
                "correlation_id": correlation_id, "visibility_policy": "authority_only",
                "payload": dict(payload)}

    @classmethod
    def _holder_event(cls, command_id: str, index: int, event_type: str, stream_id: str,
                      credential_id: str, item_ref: str, from_state: str, to_state: str,
                      causation_id: str, correlation_id: str) -> dict[str, object]:
        return cls._v2_event(command_id, index, event_type, stream_id, {
            "credential_id": credential_id,
            "item_ref": item_ref,
            "from_state": from_state,
            "to_state": to_state,
            "condition_ref": cls._CONDITION_REF,
            "condition_revision": cls._CONDITION_REVISION,
        }, causation_id, correlation_id)

    @classmethod
    def _event(cls, command_id: str, index: int, event_type: str, payload: Mapping[str, object], causation_id: str, correlation_id: str) -> dict[str, object]:
        return {"event_id": f"evt:{command_id}:credential:{index}", "event_type": event_type, "schema_version": 1, "stream_id": cls._STREAM, "stream_revision": 0, "global_sequence": 0, "transaction_id": f"tx:{command_id}", "command_id": command_id, "causation_id": causation_id, "correlation_id": correlation_id, "visibility_policy": "authority_only", "payload": dict(payload)}

    def _duplicate(self, idempotency_key: str, digest: str, command_id: str,
                   event_types: tuple[str, ...], *, principal: str | None = None) -> AppendBatchResult | None:
        principal = self._PRINCIPAL if principal is None else principal
        if principal == self._V2_PRINCIPAL:
            legacy_types = {
                "gameplay.credential.link_issued": ("gameplay.credential.issued",),
                "gameplay.credential.link_revoked": ("gameplay.credential.revoked",),
                "gameplay.credential.link_superseded": ("gameplay.credential.superseded", "gameplay.credential.issued"),
            }
            legacy = self._duplicate(idempotency_key, digest, command_id, legacy_types[event_types[0]])
            if legacy is not None:
                return legacy
        result = replay_duplicate(
            self._store, principal=principal, idempotency_key=idempotency_key,
            payload_digest=digest, error_factory=CredentialRuntimeError,
            missing_result_code="credential_idempotency_missing_result",
        )
        if result is None:
            return None
        if not result.committed or result.command_id != command_id or result.transaction_id != f"tx:{command_id}":
            raise CredentialRuntimeError("credential_replay_transaction_mismatch")
        batch = self._store.get_transaction(result.transaction_id)
        if (batch is None or batch.transaction_id != result.transaction_id or batch.command_id != command_id
                or batch.idempotency_record.principal_ref != principal
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


__all__ = ["BondCredentialLink", "CredentialAuthorityService", "CredentialLink", "CredentialPresentationDecision", "CredentialPresentationValidator", "CredentialProjection", "CredentialProjector", "CredentialRuntimeError"]
