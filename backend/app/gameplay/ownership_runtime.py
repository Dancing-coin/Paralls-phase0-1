"""Minimal event-sourced full-title authority, separate from custody and economy."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Mapping, Sequence

from pydantic import ConfigDict, Field

from app.gameplay.contract_runtime import ContractProjector
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog, GovernedAuthorityContractError
from app.gameplay.models import AppendBatchResult, GameplayEvent, OwnerAuthorizedFragment, StrictGameplayModel
from app.gameplay.owner_runtime_base import OwnerCommitBuilder, rejected_result, replay_duplicate
from app.gameplay.settlement_plan import SettlementPlan as EventStoreSettlementPlan
from app.gameplay.shared_contracts import GameplayCommandEnvelope


class OwnershipRuntimeError(ValueError):
    pass


class MunicipalDroughtAssessmentCertificateIntentV1(StrictGameplayModel):
    """Caller request for the fixed completed-assessment certificate row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    advisory_event_id: str = Field(min_length=1)
    expected_contract_revision: int = Field(ge=1)
    expected_ownership_revision: int = Field(ge=0)
    command_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    submitted_at: str = Field(min_length=1)


@dataclass(frozen=True)
class OwnershipRight:
    right_id: str
    asset_ref: str
    holder_ref: str
    source_event_id: str
    bond_type: str


@dataclass(frozen=True)
class OwnershipBond:
    bond_ref: str
    subject_ref: str
    target_ref: str
    bond_type: str
    scope: str
    term_expires_at: int | None
    source_event_ref: str
    attributes: Mapping[str, object]
    status: str
    source_event_id: str
    lifecycle_event_id: str | None = None
    related_bond_ref: str | None = None


@dataclass(frozen=True)
class OwnershipProjection:
    rights: Mapping[str, OwnershipRight]
    active_right_by_asset: Mapping[str, str]
    active_right_by_asset_and_type: Mapping[str, Mapping[str, tuple[str, ...]]]
    source_revision_vector: Mapping[str, int]
    projection_revision: str
    bonds: Mapping[str, OwnershipBond] = field(default_factory=lambda: MappingProxyType({}))

    def active_bonds(
        self, target_ref: str, bond_type: str, scope: str, *, world_tick: int
    ) -> tuple[OwnershipBond, ...]:
        _require_world_tick(world_tick)
        return tuple(
            bond
            for bond in self.bonds.values()
            if bond.status == "active"
            and bond.target_ref == target_ref
            and bond.bond_type == bond_type
            and bond.scope == scope
            and (bond.term_expires_at is None or world_tick < bond.term_expires_at)
        )


class OwnershipProjector:
    _EVENT_TYPES = {"gameplay.ownership.right_granted", "gameplay.ownership.right_transferred"}
    _BOND_TYPES = frozenset({"ownership", "custody", "authority", "affiliation", "obligation"})
    _BOND_REVOKE_REASON_CODES = frozenset({
        "party_requested",
        "authority_withdrawn",
        "source_invalidated",
        "terms_violated",
        "administrative_correction",
    })
    _BOND_EVENT_TYPES = {
        "gameplay.ownership.bond_granted",
        "gameplay.ownership.bond_revoked",
        "gameplay.ownership.bond_transferred",
        "gameplay.ownership.bond_expired",
        "gameplay.ownership.bond_superseded",
    }
    def rebuild(
        self, events: Sequence[GameplayEvent], *, checkpoint_at: int | None = None
    ) -> OwnershipProjection:
        if checkpoint_at is None:
            projection = self._reduce(events)
            self._validate_bond_links(projection.bonds)
            return projection
        if checkpoint_at < 0:
            raise OwnershipRuntimeError("ownership_checkpoint_invalid")
        prefix = self._reduce(
            [event for event in events if event.global_sequence <= checkpoint_at]
        )
        projection = self._reduce(
            [event for event in events if event.global_sequence > checkpoint_at],
            rights=dict(prefix.rights),
            by_asset=dict(prefix.active_right_by_asset),
            by_asset_and_type={
                asset_ref: {bond_type: list(right_ids) for bond_type, right_ids in bond_types.items()}
                for asset_ref, bond_types in prefix.active_right_by_asset_and_type.items()
            },
            revisions=dict(prefix.source_revision_vector),
            bonds=dict(prefix.bonds),
        )
        self._validate_bond_links(projection.bonds)
        return projection

    @staticmethod
    def _validate_bond_links(bonds: Mapping[str, OwnershipBond]) -> None:
        for bond in bonds.values():
            if bond.related_bond_ref is None:
                continue
            related = bonds.get(bond.related_bond_ref)
            if related is None:
                raise OwnershipRuntimeError("ownership_bond_lifecycle_link_invalid")
            if bond.status == "transferred" and (
                related.subject_ref == bond.subject_ref
                or related.target_ref != bond.target_ref
                or related.bond_type != bond.bond_type
                or related.scope != bond.scope
            ):
                raise OwnershipRuntimeError("ownership_bond_transfer_invalid")

    def _reduce(
        self,
        events: Sequence[GameplayEvent],
        *,
        rights: dict[str, OwnershipRight] | None = None,
        by_asset: dict[str, str] | None = None,
        by_asset_and_type: dict[str, dict[str, list[str]]] | None = None,
        revisions: dict[str, int] | None = None,
        bonds: dict[str, OwnershipBond] | None = None,
    ) -> OwnershipProjection:
        rights = dict(rights or {})
        by_asset = dict(by_asset or {})
        by_asset_and_type = {
            asset_ref: {bond_type: list(right_ids) for bond_type, right_ids in bond_types.items()}
            for asset_ref, bond_types in (by_asset_and_type or {}).items()
        }
        revisions = dict(revisions or {})
        bonds = dict(bonds or {})
        for event in sorted(events, key=lambda value: (value.global_sequence, value.event_id)):
            if event.event_type in self._BOND_EVENT_TYPES:
                payload = event.payload
                if event.event_type == "gameplay.ownership.bond_granted":
                    bond_ref = _text(payload, "bond_ref")
                    subject_ref = _text(payload, "subject_ref")
                    target_ref = _text(payload, "target_ref")
                    bond_type = payload.get("bond_type")
                    if not isinstance(bond_type, str) or bond_type not in self._BOND_TYPES:
                        raise OwnershipRuntimeError("ownership_bond_type_invalid")
                    scope = _text(payload, "scope")
                    source_event_ref = _text(payload, "source_event_ref")
                    term_expires_at = payload.get("term_expires_at")
                    if term_expires_at is not None and (
                        isinstance(term_expires_at, bool)
                        or not isinstance(term_expires_at, int)
                        or term_expires_at < 0
                    ):
                        raise OwnershipRuntimeError("ownership_bond_term_invalid")
                    attributes = _bond_attributes(payload.get("attributes", {}), bond_type)
                    if bond_ref in bonds:
                        raise OwnershipRuntimeError("ownership_bond_ref_duplicate")
                    key = (bond_type, subject_ref, target_ref, scope)
                    if any(
                        prior.status == "active"
                        and (prior.bond_type, prior.subject_ref, prior.target_ref, prior.scope) == key
                        for prior in bonds.values()
                    ):
                        raise OwnershipRuntimeError("ownership_bond_conflict")
                    bonds[bond_ref] = OwnershipBond(
                        bond_ref=bond_ref,
                        subject_ref=subject_ref,
                        target_ref=target_ref,
                        bond_type=bond_type,
                        scope=scope,
                        term_expires_at=term_expires_at,
                        source_event_ref=source_event_ref,
                        attributes=MappingProxyType(attributes),
                        status="active",
                        source_event_id=event.event_id,
                    )
                elif event.event_type == "gameplay.ownership.bond_revoked":
                    prior = _active_bond(bonds, _text(payload, "bond_ref"))
                    reason_code = _text(payload, "reason_code")
                    if reason_code not in self._BOND_REVOKE_REASON_CODES:
                        raise OwnershipRuntimeError("ownership_bond_revoke_reason_invalid")
                    bonds[prior.bond_ref] = replace(
                        prior, status="revoked", lifecycle_event_id=event.event_id
                    )
                elif event.event_type == "gameplay.ownership.bond_transferred":
                    prior = _active_bond(bonds, _text(payload, "bond_ref"))
                    if prior.subject_ref != _text(payload, "previous_subject"):
                        raise OwnershipRuntimeError("ownership_bond_subject_mismatch")
                    new_subject = _text(payload, "new_subject")
                    new_bond_ref = _text(payload, "new_bond_ref")
                    if new_bond_ref in bonds or new_subject == prior.subject_ref:
                        raise OwnershipRuntimeError("ownership_bond_transfer_invalid")
                    bonds[prior.bond_ref] = replace(
                        prior,
                        status="transferred",
                        lifecycle_event_id=event.event_id,
                        related_bond_ref=new_bond_ref,
                    )
                elif event.event_type == "gameplay.ownership.bond_expired":
                    prior = _active_bond(bonds, _text(payload, "bond_ref"))
                    world_tick = payload.get("world_tick")
                    if (
                        prior.term_expires_at is None
                        or isinstance(world_tick, bool)
                        or not isinstance(world_tick, int)
                        or world_tick < prior.term_expires_at
                    ):
                        raise OwnershipRuntimeError("ownership_bond_expiry_invalid")
                    bonds[prior.bond_ref] = replace(
                        prior, status="expired", lifecycle_event_id=event.event_id
                    )
                else:
                    prior = _active_bond(bonds, _text(payload, "old_bond_ref"))
                    new_bond_ref = _text(payload, "new_bond_ref")
                    if new_bond_ref in bonds:
                        raise OwnershipRuntimeError("ownership_bond_supersede_invalid")
                    bonds[prior.bond_ref] = replace(
                        prior,
                        status="superseded",
                        lifecycle_event_id=event.event_id,
                        related_bond_ref=new_bond_ref,
                    )
                revisions[event.stream_id] = max(
                    revisions.get(event.stream_id, 0), event.stream_revision
                )
                continue
            if event.event_type not in self._EVENT_TYPES:
                continue
            payload = event.payload
            right_id = _text(payload, "right_id")
            asset_ref = _text(payload, "asset_ref")
            if event.event_type == "gameplay.ownership.right_granted":
                bond_type = payload.get("bond_type", "ownership")
                if not isinstance(bond_type, str) or bond_type not in self._BOND_TYPES:
                    raise OwnershipRuntimeError("ownership_right_type_invalid")
                asset_bond_types = by_asset_and_type.setdefault(asset_ref, {})
                holder_ref = _text(payload, "holder_ref")
                active_right_ids = asset_bond_types.setdefault(bond_type, [])
                if (
                    right_id in rights
                    or (bond_type == "ownership" and active_right_ids)
                    or any(rights[active_id].holder_ref == holder_ref for active_id in active_right_ids)
                ):
                    raise OwnershipRuntimeError("ownership_title_conflict")
                rights[right_id] = OwnershipRight(
                    right_id, asset_ref, holder_ref, event.event_id, bond_type
                )
                active_right_ids.append(right_id)
                if bond_type == "ownership":
                    by_asset[asset_ref] = right_id
            else:
                prior = rights.get(right_id)
                if prior is None or prior.asset_ref != asset_ref:
                    raise OwnershipRuntimeError("ownership_right_missing")
                if prior.holder_ref != _text(payload, "from_holder_ref"):
                    raise OwnershipRuntimeError("ownership_right_holder_mismatch")
                bond_type = payload.get("bond_type", prior.bond_type)
                if not isinstance(bond_type, str) or bond_type not in self._BOND_TYPES:
                    raise OwnershipRuntimeError("ownership_right_type_invalid")
                if bond_type != prior.bond_type:
                    raise OwnershipRuntimeError("ownership_right_type_mismatch")
                to_holder_ref = _text(payload, "to_holder_ref")
                if any(
                    active_id != right_id and rights[active_id].holder_ref == to_holder_ref
                    for active_id in by_asset_and_type.get(asset_ref, {}).get(prior.bond_type, [])
                ):
                    raise OwnershipRuntimeError("ownership_right_conflict")
                rights[right_id] = OwnershipRight(
                    right_id, asset_ref, to_holder_ref, event.event_id, prior.bond_type
                )
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
        frozen_rights = MappingProxyType(dict(sorted(rights.items())))
        frozen_assets = MappingProxyType(dict(sorted(by_asset.items())))
        frozen_asset_bond_types = MappingProxyType({
            asset_ref: MappingProxyType({
                bond_type: tuple(right_ids)
                for bond_type, right_ids in sorted(bond_types.items())
            })
            for asset_ref, bond_types in sorted(by_asset_and_type.items())
        })
        frozen_revisions = MappingProxyType(dict(sorted(revisions.items())))
        frozen_bonds = MappingProxyType(dict(sorted(bonds.items())))
        projection_digest_values = [
            frozen_rights,
            frozen_assets,
            frozen_asset_bond_types,
            frozen_revisions,
        ]
        if frozen_bonds:
            projection_digest_values.append(frozen_bonds)
        return OwnershipProjection(
            frozen_rights,
            frozen_assets,
            frozen_asset_bond_types,
            frozen_revisions,
            f"ownership:{_digest(projection_digest_values)[:16]}",
            frozen_bonds,
        )


class OwnershipAuthorityService:
    _PRINCIPAL = "actor_gameplay.ownership_domain"
    _MUNICIPAL_TERMS = "service:municipal-drought-assessment@1"
    _MUNICIPAL_EVIDENCE = "evidence:municipal-drought-assessment@1"
    _MUNICIPAL_HOLDER = "organization:district-works"
    _MUNICIPAL_CERTIFICATE_ASSET_PREFIX = "asset:municipal-drought-assessment-certificate:"
    _MUNICIPAL_CERTIFICATE_RIGHT_PREFIX = "right:municipal-drought-assessment-certificate:"

    def __init__(self, *, store: GameplayEventStore) -> None:
        self._store = store
        self._projector = OwnershipProjector()

    def grant_initial_title(self, *, command_id: str, asset_ref: str, holder_ref: str, right_id: str, idempotency_key: str, causation_id: str, correlation_id: str) -> AppendBatchResult:
        if (
            asset_ref.startswith(self._MUNICIPAL_CERTIFICATE_ASSET_PREFIX)
            or right_id.startswith(self._MUNICIPAL_CERTIFICATE_RIGHT_PREFIX)
        ):
            raise OwnershipRuntimeError("municipal_certificate_row_required")
        command = {"kind": "grant", "command_id": command_id, "asset_ref": asset_ref, "holder_ref": holder_ref, "right_id": right_id}
        digest = _digest(command)
        duplicate = self._duplicate(idempotency_key, digest)
        if duplicate is not None:
            return duplicate
        projection = self._projector.rebuild(self._store.read_events())
        if not asset_ref or not holder_ref or not right_id or right_id in projection.rights or asset_ref in projection.active_right_by_asset:
            raise OwnershipRuntimeError("ownership_title_conflict")
        return self._append(command_id, idempotency_key, digest, "gameplay.ownership.right_granted", {"right_id": right_id, "asset_ref": asset_ref, "holder_ref": holder_ref}, causation_id, correlation_id, projection)

    def transfer_title(self, *, command_id: str, asset_ref: str, right_id: str, from_holder_ref: str, to_holder_ref: str, idempotency_key: str, causation_id: str, correlation_id: str) -> AppendBatchResult:
        if (
            asset_ref.startswith(self._MUNICIPAL_CERTIFICATE_ASSET_PREFIX)
            or right_id.startswith(self._MUNICIPAL_CERTIFICATE_RIGHT_PREFIX)
        ):
            raise OwnershipRuntimeError("municipal_certificate_title_transfer_forbidden")
        command = {"kind": "transfer", "command_id": command_id, "asset_ref": asset_ref, "right_id": right_id, "from_holder_ref": from_holder_ref, "to_holder_ref": to_holder_ref}
        digest = _digest(command)
        duplicate = self._duplicate(idempotency_key, digest)
        if duplicate is not None:
            return duplicate
        projection = self._projector.rebuild(self._store.read_events())
        right = projection.rights.get(right_id)
        if right is None or right.asset_ref != asset_ref:
            raise OwnershipRuntimeError("ownership_right_missing")
        if right.bond_type != "ownership":
            raise OwnershipRuntimeError("ownership_right_type_mismatch")
        if right.holder_ref != from_holder_ref or not to_holder_ref:
            raise OwnershipRuntimeError("ownership_right_holder_mismatch")
        return self._append(command_id, idempotency_key, digest, "gameplay.ownership.right_transferred", {"right_id": right_id, "asset_ref": asset_ref, "from_holder_ref": from_holder_ref, "to_holder_ref": to_holder_ref}, causation_id, correlation_id, projection)

    def grant_right(
        self,
        *,
        command_id: str,
        asset_ref: str,
        holder_ref: str,
        right_id: str,
        bond_type: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        if not isinstance(bond_type, str) or bond_type not in OwnershipProjector._BOND_TYPES:
            raise OwnershipRuntimeError("ownership_right_type_invalid")
        if bond_type == "ownership" and (
            asset_ref.startswith(self._MUNICIPAL_CERTIFICATE_ASSET_PREFIX)
            or right_id.startswith(self._MUNICIPAL_CERTIFICATE_RIGHT_PREFIX)
        ):
            raise OwnershipRuntimeError("municipal_certificate_row_required")
        command = {
            "kind": "grant",
            "command_id": command_id,
            "asset_ref": asset_ref,
            "holder_ref": holder_ref,
            "right_id": right_id,
            "bond_type": bond_type,
        }
        digest = _digest(command)
        duplicate = self._duplicate(idempotency_key, digest)
        if duplicate is not None:
            return duplicate
        projection = self._projector.rebuild(self._store.read_events())
        active_by_type = projection.active_right_by_asset_and_type.get(asset_ref, {})
        active_right_ids = active_by_type.get(bond_type, ())
        if (
            not asset_ref
            or not holder_ref
            or not right_id
            or right_id in projection.rights
            or (bond_type == "ownership" and active_right_ids)
            or any(projection.rights[active_id].holder_ref == holder_ref for active_id in active_right_ids)
        ):
            raise OwnershipRuntimeError("ownership_right_conflict")
        return self._append(
            command_id,
            idempotency_key,
            digest,
            "gameplay.ownership.right_granted",
            {"right_id": right_id, "asset_ref": asset_ref, "holder_ref": holder_ref, "bond_type": bond_type},
            causation_id,
            correlation_id,
            projection,
        )

    def transfer_right(
        self,
        *,
        command_id: str,
        asset_ref: str,
        right_id: str,
        bond_type: str,
        from_holder_ref: str,
        to_holder_ref: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        if not isinstance(bond_type, str) or bond_type not in OwnershipProjector._BOND_TYPES:
            raise OwnershipRuntimeError("ownership_right_type_invalid")
        if bond_type == "ownership" and (
            asset_ref.startswith(self._MUNICIPAL_CERTIFICATE_ASSET_PREFIX)
            or right_id.startswith(self._MUNICIPAL_CERTIFICATE_RIGHT_PREFIX)
        ):
            raise OwnershipRuntimeError("municipal_certificate_title_transfer_forbidden")
        command = {
            "kind": "transfer",
            "command_id": command_id,
            "asset_ref": asset_ref,
            "right_id": right_id,
            "bond_type": bond_type,
            "from_holder_ref": from_holder_ref,
            "to_holder_ref": to_holder_ref,
        }
        digest = _digest(command)
        duplicate = self._duplicate(idempotency_key, digest)
        if duplicate is not None:
            return duplicate
        projection = self._projector.rebuild(self._store.read_events())
        right = projection.rights.get(right_id)
        if right is None or right.asset_ref != asset_ref:
            raise OwnershipRuntimeError("ownership_right_missing")
        if right.bond_type != bond_type:
            raise OwnershipRuntimeError("ownership_right_type_mismatch")
        if right.holder_ref != from_holder_ref or not to_holder_ref:
            raise OwnershipRuntimeError("ownership_right_holder_mismatch")
        if any(
            active_id != right_id and projection.rights[active_id].holder_ref == to_holder_ref
            for active_id in projection.active_right_by_asset_and_type.get(asset_ref, {}).get(bond_type, ())
        ):
            raise OwnershipRuntimeError("ownership_right_conflict")
        return self._append(
            command_id,
            idempotency_key,
            digest,
            "gameplay.ownership.right_transferred",
            {
                "right_id": right_id,
                "asset_ref": asset_ref,
                "from_holder_ref": from_holder_ref,
                "to_holder_ref": to_holder_ref,
                "bond_type": bond_type,
            },
            causation_id,
            correlation_id,
            projection,
        )

    def grant_bond(
        self,
        *,
        command_id: str,
        bond_ref: str,
        subject_ref: str,
        target_ref: str,
        bond_type: str,
        scope: str,
        term_expires_at: int | None,
        source_event_ref: str,
        attributes: Mapping[str, object] | None = None,
        world_tick: int,
        expected_ownership_revision: int,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        _require_world_tick(world_tick)
        attributes = _bond_attributes({} if attributes is None else attributes, bond_type)
        _require_ownership_revision(expected_ownership_revision)
        if term_expires_at is not None and (
            isinstance(term_expires_at, bool)
            or not isinstance(term_expires_at, int)
            or term_expires_at < 0
        ):
            raise OwnershipRuntimeError("ownership_bond_term_invalid")
        if (
            not all(isinstance(value, str) and value for value in (
                bond_ref, subject_ref, target_ref, scope, source_event_ref,
            ))
        ):
            raise OwnershipRuntimeError("ownership_bond_invalid")
        if idempotency_key != bond_ref:
            raise OwnershipRuntimeError("ownership_bond_idempotency_invalid")
        command = {
            "kind": "bond_grant",
            "command_id": command_id,
            "bond_ref": bond_ref,
            "subject_ref": subject_ref,
            "target_ref": target_ref,
            "bond_type": bond_type,
            "scope": scope,
            "term_expires_at": term_expires_at,
            "source_event_ref": source_event_ref,
            "attributes": attributes,
        }
        digest = _digest(command)
        duplicate = self._duplicate(idempotency_key, digest)
        if duplicate is not None:
            return duplicate
        self._require_bond_source(source_event_ref)
        if term_expires_at is not None and term_expires_at <= world_tick:
            raise OwnershipRuntimeError("ownership_bond_term_invalid")
        projection = self._projector.rebuild(self._store.read_events())
        revision = projection.source_revision_vector.get("gameplay:ownership", 0)
        if expected_ownership_revision != revision:
            raise OwnershipRuntimeError("revision_conflict")
        if bond_ref in projection.bonds:
            raise OwnershipRuntimeError("ownership_bond_ref_duplicate")
        key = (bond_type, subject_ref, target_ref, scope)
        expired = tuple(
            bond
            for bond in projection.bonds.values()
            if bond.status == "active"
            and (bond.bond_type, bond.subject_ref, bond.target_ref, bond.scope) == key
            and bond.term_expires_at is not None
            and world_tick >= bond.term_expires_at
        )
        if any(
            bond.status == "active"
            and (bond.bond_type, bond.subject_ref, bond.target_ref, bond.scope) == key
            and (bond.term_expires_at is None or world_tick < bond.term_expires_at)
            for bond in projection.bonds.values()
        ):
            raise OwnershipRuntimeError("ownership_bond_conflict")
        events = tuple(
            ("gameplay.ownership.bond_expired", {
                "bond_ref": bond.bond_ref,
                "world_tick": world_tick,
            })
            for bond in expired
        ) + ((
            "gameplay.ownership.bond_granted",
            _bond_granted_payload(
                bond_ref,
                subject_ref,
                target_ref,
                bond_type,
                scope,
                term_expires_at,
                source_event_ref,
                attributes,
            ),
        ),)
        return self._append_bond_events(
            command_id=command_id,
            idempotency_key=idempotency_key,
            payload_digest=digest,
            expected_revision=revision,
            causation_id=causation_id,
            correlation_id=correlation_id,
            events=events,
        )

    def revoke_bond(
        self,
        *,
        command_id: str,
        bond_ref: str,
        reason_code: str,
        world_tick: int,
        expected_ownership_revision: int,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        _require_world_tick(world_tick)
        _require_ownership_revision(expected_ownership_revision)
        if not all(isinstance(value, str) and value for value in (bond_ref, reason_code)):
            raise OwnershipRuntimeError("ownership_bond_revoke_invalid")
        if reason_code not in OwnershipProjector._BOND_REVOKE_REASON_CODES:
            raise OwnershipRuntimeError("ownership_bond_revoke_reason_invalid")
        command = {
            "kind": "bond_revoke",
            "command_id": command_id,
            "bond_ref": bond_ref,
            "reason_code": reason_code,
        }
        digest = _digest(command)
        duplicate = self._duplicate(idempotency_key, digest)
        if duplicate is not None:
            return duplicate
        projection = self._projector.rebuild(self._store.read_events())
        revision = projection.source_revision_vector.get("gameplay:ownership", 0)
        if expected_ownership_revision != revision:
            raise OwnershipRuntimeError("revision_conflict")
        bond = _active_bond(projection.bonds, bond_ref)
        if bond.term_expires_at is not None and world_tick >= bond.term_expires_at:
            raise OwnershipRuntimeError("ownership_bond_expired")
        return self._append_bond_events(
            command_id=command_id,
            idempotency_key=idempotency_key,
            payload_digest=digest,
            expected_revision=revision,
            causation_id=causation_id,
            correlation_id=correlation_id,
            events=(("gameplay.ownership.bond_revoked", {
                "bond_ref": bond_ref,
                "reason_code": reason_code,
            }),),
        )

    def transfer_bond(
        self,
        *,
        command_id: str,
        bond_ref: str,
        new_bond_ref: str,
        new_subject: str,
        source_event_ref: str,
        world_tick: int,
        expected_ownership_revision: int,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        _require_world_tick(world_tick)
        _require_ownership_revision(expected_ownership_revision)
        if not all(isinstance(value, str) and value for value in (
            bond_ref, new_bond_ref, new_subject, source_event_ref,
        )):
            raise OwnershipRuntimeError("ownership_bond_transfer_invalid")
        command = {
            "kind": "bond_transfer",
            "command_id": command_id,
            "bond_ref": bond_ref,
            "new_bond_ref": new_bond_ref,
            "new_subject": new_subject,
            "source_event_ref": source_event_ref,
        }
        digest = _digest(command)
        duplicate = self._duplicate(idempotency_key, digest)
        if duplicate is not None:
            return duplicate
        self._require_bond_source(source_event_ref)
        projection = self._projector.rebuild(self._store.read_events())
        revision = projection.source_revision_vector.get("gameplay:ownership", 0)
        if expected_ownership_revision != revision:
            raise OwnershipRuntimeError("revision_conflict")
        prior = self._require_current_bond(projection, bond_ref, world_tick)
        if new_bond_ref in projection.bonds:
            raise OwnershipRuntimeError("ownership_bond_ref_duplicate")
        if new_subject == prior.subject_ref:
            raise OwnershipRuntimeError("ownership_bond_transfer_invalid")
        self._require_bond_key_available(
            projection,
            subject_ref=new_subject,
            target_ref=prior.target_ref,
            bond_type=prior.bond_type,
            scope=prior.scope,
            world_tick=world_tick,
            excluding_bond_ref=bond_ref,
        )
        expired_key_bonds = self._expired_bonds_for_key(
            projection,
            subject_ref=new_subject,
            target_ref=prior.target_ref,
            bond_type=prior.bond_type,
            scope=prior.scope,
            world_tick=world_tick,
        )
        granted = _bond_granted_payload(
            new_bond_ref,
            new_subject,
            prior.target_ref,
            prior.bond_type,
            prior.scope,
            prior.term_expires_at,
            source_event_ref,
            prior.attributes,
        )
        return self._append_bond_events(
            command_id=command_id,
            idempotency_key=idempotency_key,
            payload_digest=digest,
            expected_revision=revision,
            causation_id=causation_id,
            correlation_id=correlation_id,
            events=tuple(
                ("gameplay.ownership.bond_expired", {
                    "bond_ref": bond.bond_ref,
                    "world_tick": world_tick,
                })
                for bond in expired_key_bonds
            ) + (
                ("gameplay.ownership.bond_transferred", {
                    "bond_ref": bond_ref,
                    "previous_subject": prior.subject_ref,
                    "new_subject": new_subject,
                    "new_bond_ref": new_bond_ref,
                }),
                ("gameplay.ownership.bond_granted", granted),
            ),
        )

    def build_land_right_bond_transfer_fragment(
        self,
        *,
        command_id: str,
        bond_ref: str,
        new_bond_ref: str,
        previous_subject: str,
        new_subject: str,
        target_ref: str,
        source_event_ref: str,
        world_tick: int,
        expected_ownership_revision: int,
        read_stream_revisions: Mapping[str, int],
        pinned_revisions: Mapping[str, int],
    ) -> OwnerAuthorizedFragment:
        _require_world_tick(world_tick)
        _require_ownership_revision(expected_ownership_revision)
        if not all(isinstance(value, str) and value for value in (
            command_id, bond_ref, new_bond_ref, previous_subject, new_subject,
            target_ref, source_event_ref,
        )):
            raise OwnershipRuntimeError("ownership_bond_transfer_invalid")
        self._require_bond_source(source_event_ref)
        events = self._store.read_events()
        projection = self._projector.rebuild(events)
        revision = projection.source_revision_vector.get("gameplay:ownership", 0)
        if expected_ownership_revision != revision:
            raise OwnershipRuntimeError("revision_conflict")
        prior = self._require_current_bond(projection, bond_ref, world_tick)
        if (
            prior.subject_ref != previous_subject
            or prior.target_ref != target_ref
            or prior.bond_type != "ownership"
            or new_subject == previous_subject
            or new_bond_ref in projection.bonds
        ):
            raise OwnershipRuntimeError("ownership_bond_transfer_invalid")
        self._require_bond_key_available(
            projection,
            subject_ref=new_subject,
            target_ref=prior.target_ref,
            bond_type=prior.bond_type,
            scope=prior.scope,
            world_tick=world_tick,
            excluding_bond_ref=bond_ref,
        )
        expired_key_bonds = self._expired_bonds_for_key(
            projection,
            subject_ref=new_subject,
            target_ref=prior.target_ref,
            bond_type=prior.bond_type,
            scope=prior.scope,
            world_tick=world_tick,
        )
        event_specs = tuple(
            ("gameplay.ownership.bond_expired", {
                "bond_ref": bond.bond_ref,
                "world_tick": world_tick,
            })
            for bond in expired_key_bonds
        ) + (
            ("gameplay.ownership.bond_transferred", {
                "bond_ref": bond_ref,
                "previous_subject": previous_subject,
                "new_subject": new_subject,
                "new_bond_ref": new_bond_ref,
            }),
            ("gameplay.ownership.bond_granted", _bond_granted_payload(
                new_bond_ref,
                new_subject,
                prior.target_ref,
                prior.bond_type,
                prior.scope,
                prior.term_expires_at,
                source_event_ref,
                prior.attributes,
            )),
        )
        return OwnerAuthorizedFragment(
            fragment_id=f"fragment:ownership:land-right-transfer:{command_id}",
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref="ownership:land-right-bond-transfer@1",
            expected_revisions={"gameplay:ownership": revision},
            read_set_revisions=dict(read_stream_revisions),
            event_specs={"gameplay:ownership": event_specs},
            event_visibility_policies={
                "gameplay:ownership": tuple("authority_only" for _ in event_specs),
            },
            pinned_revisions={"ownership": revision, **dict(pinned_revisions)},
        )

    def supersede_bond(
        self,
        *,
        command_id: str,
        old_bond_ref: str,
        new_bond_ref: str,
        subject_ref: str,
        target_ref: str,
        bond_type: str,
        scope: str,
        term_expires_at: int | None,
        source_event_ref: str,
        attributes: Mapping[str, object] | None = None,
        world_tick: int,
        expected_ownership_revision: int,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        _require_world_tick(world_tick)
        attributes = _bond_attributes({} if attributes is None else attributes, bond_type)
        _require_ownership_revision(expected_ownership_revision)
        if term_expires_at is not None and (
            isinstance(term_expires_at, bool)
            or not isinstance(term_expires_at, int)
            or term_expires_at < 0
        ):
            raise OwnershipRuntimeError("ownership_bond_term_invalid")
        if (
            not all(isinstance(value, str) and value for value in (
                old_bond_ref, new_bond_ref, subject_ref, target_ref, scope, source_event_ref,
            ))
            or new_bond_ref == old_bond_ref
        ):
            raise OwnershipRuntimeError("ownership_bond_supersede_invalid")
        command = {
            "kind": "bond_supersede",
            "command_id": command_id,
            "old_bond_ref": old_bond_ref,
            "new_bond_ref": new_bond_ref,
            "subject_ref": subject_ref,
            "target_ref": target_ref,
            "bond_type": bond_type,
            "scope": scope,
            "term_expires_at": term_expires_at,
            "source_event_ref": source_event_ref,
            "attributes": attributes,
        }
        digest = _digest(command)
        duplicate = self._duplicate(idempotency_key, digest)
        if duplicate is not None:
            return duplicate
        self._require_bond_source(source_event_ref)
        if term_expires_at is not None and term_expires_at <= world_tick:
            raise OwnershipRuntimeError("ownership_bond_term_invalid")
        projection = self._projector.rebuild(self._store.read_events())
        revision = projection.source_revision_vector.get("gameplay:ownership", 0)
        if expected_ownership_revision != revision:
            raise OwnershipRuntimeError("revision_conflict")
        self._require_current_bond(projection, old_bond_ref, world_tick)
        if new_bond_ref in projection.bonds:
            raise OwnershipRuntimeError("ownership_bond_ref_duplicate")
        self._require_bond_key_available(
            projection,
            subject_ref=subject_ref,
            target_ref=target_ref,
            bond_type=bond_type,
            scope=scope,
            world_tick=world_tick,
            excluding_bond_ref=old_bond_ref,
        )
        expired_key_bonds = self._expired_bonds_for_key(
            projection,
            subject_ref=subject_ref,
            target_ref=target_ref,
            bond_type=bond_type,
            scope=scope,
            world_tick=world_tick,
            excluding_bond_ref=old_bond_ref,
        )
        granted = _bond_granted_payload(
            new_bond_ref,
            subject_ref,
            target_ref,
            bond_type,
            scope,
            term_expires_at,
            source_event_ref,
            attributes,
        )
        return self._append_bond_events(
            command_id=command_id,
            idempotency_key=idempotency_key,
            payload_digest=digest,
            expected_revision=revision,
            causation_id=causation_id,
            correlation_id=correlation_id,
            events=tuple(
                ("gameplay.ownership.bond_expired", {
                    "bond_ref": bond.bond_ref,
                    "world_tick": world_tick,
                })
                for bond in expired_key_bonds
            ) + (
                ("gameplay.ownership.bond_superseded", {
                    "old_bond_ref": old_bond_ref,
                    "new_bond_ref": new_bond_ref,
                }),
                ("gameplay.ownership.bond_granted", granted),
            ),
        )

    def expire_bond(
        self,
        *,
        command_id: str,
        bond_ref: str,
        world_tick: int,
        expected_ownership_revision: int,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        _require_world_tick(world_tick)
        _require_ownership_revision(expected_ownership_revision)
        if not isinstance(bond_ref, str) or not bond_ref:
            raise OwnershipRuntimeError("ownership_bond_expiry_invalid")
        command = {
            "kind": "bond_expire",
            "command_id": command_id,
            "bond_ref": bond_ref,
        }
        digest = _digest(command)
        duplicate = self._duplicate(idempotency_key, digest)
        if duplicate is not None:
            return duplicate
        projection = self._projector.rebuild(self._store.read_events())
        revision = projection.source_revision_vector.get("gameplay:ownership", 0)
        if expected_ownership_revision != revision:
            raise OwnershipRuntimeError("revision_conflict")
        bond = _active_bond(projection.bonds, bond_ref)
        if bond.term_expires_at is None or world_tick < bond.term_expires_at:
            raise OwnershipRuntimeError("ownership_bond_not_due")
        return self._append_bond_events(
            command_id=command_id,
            idempotency_key=idempotency_key,
            payload_digest=digest,
            expected_revision=revision,
            causation_id=causation_id,
            correlation_id=correlation_id,
            events=(("gameplay.ownership.bond_expired", {
                "bond_ref": bond_ref,
                "world_tick": world_tick,
            }),),
        )

    def _require_current_bond(
        self, projection: OwnershipProjection, bond_ref: str, world_tick: int
    ) -> OwnershipBond:
        bond = _active_bond(projection.bonds, bond_ref)
        if bond.term_expires_at is not None and world_tick >= bond.term_expires_at:
            raise OwnershipRuntimeError("ownership_bond_expired")
        return bond

    def _require_bond_source(self, source_event_ref: str) -> None:
        try:
            self._store.get_event(source_event_ref)
        except KeyError as exc:
            raise OwnershipRuntimeError("ownership_bond_source_missing") from exc

    def _require_bond_key_available(
        self,
        projection: OwnershipProjection,
        *,
        subject_ref: str,
        target_ref: str,
        bond_type: str,
        scope: str,
        world_tick: int,
        excluding_bond_ref: str | None = None,
    ) -> None:
        for bond in projection.bonds.values():
            if (
                bond.bond_ref != excluding_bond_ref
                and bond.status == "active"
                and (bond.term_expires_at is None or world_tick < bond.term_expires_at)
                and (bond.bond_type, bond.subject_ref, bond.target_ref, bond.scope)
                == (bond_type, subject_ref, target_ref, scope)
            ):
                raise OwnershipRuntimeError("ownership_bond_conflict")

    @staticmethod
    def _expired_bonds_for_key(
        projection: OwnershipProjection,
        *,
        subject_ref: str,
        target_ref: str,
        bond_type: str,
        scope: str,
        world_tick: int,
        excluding_bond_ref: str | None = None,
    ) -> tuple[OwnershipBond, ...]:
        return tuple(
            bond
            for bond in projection.bonds.values()
            if bond.bond_ref != excluding_bond_ref
            and bond.status == "active"
            and bond.term_expires_at is not None
            and world_tick >= bond.term_expires_at
            and (bond.bond_type, bond.subject_ref, bond.target_ref, bond.scope)
            == (bond_type, subject_ref, target_ref, scope)
        )

    def _append_bond_events(
        self,
        *,
        command_id: str,
        idempotency_key: str,
        payload_digest: str,
        expected_revision: int,
        causation_id: str,
        correlation_id: str,
        events: tuple[tuple[str, Mapping[str, object]], ...],
    ) -> AppendBatchResult:
        stream_id = "gameplay:ownership"
        transaction_id = f"tx:{command_id}"
        event_specs = [
            {
                "event_id": f"evt:{command_id}:ownership-bond:{index}",
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
            for index, (event_type, payload) in enumerate(events, start=1)
        ]
        return self._store.append_batch({
            "transaction_id": transaction_id,
            "command_id": command_id,
            "expected_stream_revisions": {stream_id: expected_revision},
            "pinned_revisions": {"ownership": expected_revision},
            "events": event_specs,
            "idempotency_record": {
                "principal_ref": self._PRINCIPAL,
                "idempotency_key": idempotency_key,
                "payload_digest": payload_digest,
            },
            "outbox_entries": [],
            "result_digest": _digest(event_specs),
            "projection_refresh_hints": [],
        })

    def grant_municipal_drought_assessment_certificate(
        self, intent: MunicipalDroughtAssessmentCertificateIntentV1
    ) -> AppendBatchResult:
        existing = self._store.get_by_idempotency(self._PRINCIPAL, intent.idempotency_key)
        if existing is not None:
            if len(existing.committed_event_ids) == 1:
                prior = self._store.get_event(existing.committed_event_ids[0])
                if (
                    prior.event_type == "gameplay.ownership.right_granted"
                    and prior.payload.get("advisory_event_id") == intent.advisory_event_id
                    and prior.causation_id == intent.causation_id
                    and prior.correlation_id == intent.correlation_id
                ):
                    return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            return self._rejected_append(intent.command_id, "idempotency_key_reused")
        try:
            advisory = self._store.get_event(intent.advisory_event_id)
        except KeyError:
            return self._rejected_append(intent.command_id, "municipal_certificate_advisory_missing")
        jurisdiction_ref = advisory.payload.get("jurisdiction_ref")
        if (
            advisory.event_type != "gameplay.government.drought_advisory_issued"
            or advisory.visibility_policy != "project"
            or not isinstance(jurisdiction_ref, str)
            or not jurisdiction_ref
        ):
            return self._rejected_append(intent.command_id, "municipal_certificate_advisory_invalid")
        contract_id = f"contract:municipal-drought-assessment:{jurisdiction_ref}:{intent.advisory_event_id}"
        contract_stream = "gameplay:contracts"
        if self._store.get_stream_head(contract_stream) != intent.expected_contract_revision:
            return self._rejected_append(intent.command_id, "municipal_certificate_contract_revision_conflict")
        contracts = ContractProjector().rebuild(self._store.read_stream(contract_stream))
        contract = contracts.contracts.get(contract_id)
        if (
            contract is None
            or contract.contract_type != "simple_service"
            or contract.terms_ref != self._MUNICIPAL_TERMS
            or contract.party_refs != ("organization:municipal-assessment-office", self._MUNICIPAL_HOLDER)
            or contract.completion_evidence_kind != self._MUNICIPAL_EVIDENCE
            or contract.completion_evidence_ref is None
            or contract.status != "fulfilled"
        ):
            return self._rejected_append(intent.command_id, "municipal_certificate_contract_invalid")
        ownership_stream = "gameplay:ownership"
        if self._store.get_stream_head(ownership_stream) != intent.expected_ownership_revision:
            return self._rejected_append(intent.command_id, "revision_conflict")
        asset_ref = f"asset:municipal-drought-assessment-certificate:{contract_id}"
        right_id = f"right:municipal-drought-assessment-certificate:{contract_id}"
        projection = self._projector.rebuild(self._store.read_events())
        if right_id in projection.rights or asset_ref in projection.active_right_by_asset:
            return self._rejected_append(intent.command_id, "municipal_certificate_already_granted")
        canonical_key = f"ownership:municipal-drought-assessment-certificate:{contract_id}:{intent.expected_contract_revision}:{intent.expected_ownership_revision}:v1"
        if intent.idempotency_key != canonical_key:
            return self._rejected_append(intent.command_id, "municipal_certificate_idempotency_key_invalid")
        try:
            GovernedAuthorityContractCatalog.require_operation(
                contract_ref="inf:contract-completed-municipal-drought-assessment-certificate@1",
                contract_kind="settlement",
                owner_ref=self._PRINCIPAL,
                stream_ids=(ownership_stream,),
                event_types=("gameplay.ownership.right_granted",),
                projection_scope="authority_only",
            )
        except GovernedAuthorityContractError as exc:
            return self._rejected_append(intent.command_id, str(exc))
        command = GameplayCommandEnvelope(
            command_id=intent.command_id,
            command_type="gameplay.ownership.grant_municipal_drought_assessment_certificate",
            command_version=1,
            principal_ref=self._PRINCIPAL,
            actor_ref=None,
            project_ref=None,
            transaction_id=f"transaction:{intent.command_id}",
            idempotency_key=intent.idempotency_key,
            expected_revisions={ownership_stream: intent.expected_ownership_revision},
            read_set_revisions={contract_stream: intent.expected_contract_revision},
            causation_id=intent.causation_id,
            correlation_id=intent.correlation_id,
            source_ref=intent.advisory_event_id,
            submitted_at=intent.submitted_at,
            pinned_revisions={"contract": intent.expected_contract_revision, "ownership": intent.expected_ownership_revision},
            payload={
                "stream_ref": ownership_stream,
                "event_type": "gameplay.ownership.right_granted",
                "visibility_policy": "authority_only",
                "right_id": right_id,
                "asset_ref": asset_ref,
                "holder_ref": self._MUNICIPAL_HOLDER,
                "contract_id": contract_id,
                "advisory_event_id": intent.advisory_event_id,
            },
        )
        return self._store.append_batch(EventStoreSettlementPlan.from_command_envelope(command).to_atomic_event_batch())

    def build_package_declared_negotiated_exchange_fragment(
        self,
        *,
        provider_holder_ref: str,
        receiver_holder_ref: str,
        source_ref: str,
        asset_ref: str,
        outcome_ref: str,
        package_revision: str,
        expected_revision: int,
    ) -> OwnerAuthorizedFragment:
        """Build the fixed INF-2AC ownership transfer fragment.

        Ownership computes the active right from committed title truth; the
        caller may not nominate a right_id directly for this admitted outcome.
        """
        if (
            not provider_holder_ref
            or not receiver_holder_ref
            or not source_ref
            or not asset_ref
            or not outcome_ref
            or not package_revision
        ):
            raise OwnershipRuntimeError("ownership_package_exchange_invalid")
        if asset_ref.startswith(self._MUNICIPAL_CERTIFICATE_ASSET_PREFIX):
            raise OwnershipRuntimeError("municipal_certificate_title_transfer_forbidden")
        projection = self._projector.rebuild(self._store.read_events())
        stream_id = "gameplay:ownership"
        if projection.source_revision_vector.get(stream_id, 0) != expected_revision:
            raise OwnershipRuntimeError("revision_conflict")
        right_id = projection.active_right_by_asset.get(asset_ref)
        if right_id is None:
            raise OwnershipRuntimeError("ownership_package_exchange_source_ambiguous")
        right = projection.rights.get(right_id)
        if right is None or right.holder_ref != provider_holder_ref:
            raise OwnershipRuntimeError("ownership_right_holder_mismatch")
        if right.right_id.startswith(self._MUNICIPAL_CERTIFICATE_RIGHT_PREFIX):
            raise OwnershipRuntimeError("municipal_certificate_title_transfer_forbidden")
        return OwnerAuthorizedFragment(
            fragment_id=(
                "fragment:ownership:package-declared-negotiated-exchange:"
                f"{provider_holder_ref}:{receiver_holder_ref}:{outcome_ref}"
            ),
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref="ownership:package-declared-negotiated-exchange@1",
            expected_revisions={stream_id: expected_revision},
            pinned_revisions={"ownership": expected_revision},
            event_specs={
                stream_id: (
                    (
                        "gameplay.ownership.right_transferred",
                        {
                            "source_ref": source_ref,
                            "right_id": right.right_id,
                            "asset_ref": asset_ref,
                            "from_holder_ref": provider_holder_ref,
                            "to_holder_ref": receiver_holder_ref,
                            "outcome_ref": outcome_ref,
                            "package_revision": package_revision,
                            "source_event_id": right.source_event_id,
                            "source_selection_rule_ref": "exchange:unique-owned-source@1",
                        },
                    ),
                )
            },
            event_visibility_policies={stream_id: ("authority_only",)},
        )

    def _duplicate(self, idempotency_key: str, digest: str) -> AppendBatchResult | None:
        return replay_duplicate(
            self._store, principal=self._PRINCIPAL, idempotency_key=idempotency_key,
            payload_digest=digest, error_factory=OwnershipRuntimeError,
            missing_result_code="ownership_idempotency_missing_result",
            transaction_mismatch_code="ownership_replay_transaction_mismatch",
            event_count_mismatch_code="ownership_replay_event_count_mismatch",
            event_missing_code="ownership_replay_event_missing",
        )

    def _append(self, command_id: str, idempotency_key: str, digest: str, event_type: str, payload: dict[str, str], causation_id: str, correlation_id: str, projection: OwnershipProjection) -> AppendBatchResult:
        stream_id = "gameplay:ownership"
        transaction_id = f"tx:{command_id}"
        event = {"event_id": f"evt:{command_id}:ownership", "event_type": event_type, "schema_version": 1, "stream_id": stream_id, "stream_revision": 0, "global_sequence": 0, "transaction_id": transaction_id, "command_id": command_id, "causation_id": causation_id, "correlation_id": correlation_id, "visibility_policy": "authority_only", "payload": payload}
        return self._store.append_batch(OwnerCommitBuilder.build(
            principal_ref=self._PRINCIPAL,
            command_id=command_id,
            transaction_id=transaction_id,
            idempotency_key=idempotency_key,
            payload_digest=digest,
            events=[event],
            expected_stream_revisions={stream_id: projection.source_revision_vector.get(stream_id, 0)},
            pinned_revisions={"ownership": projection.source_revision_vector.get(stream_id, 0)},
            result_digest=_digest(event),
        ))

    @staticmethod
    def _rejected_append(command_id: str, error_code: str) -> AppendBatchResult:
        return rejected_result(
            command_id=command_id, error_code=error_code,
            stage="municipal_certificate_admission", transaction_prefix="transaction",
        )


def _text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise OwnershipRuntimeError("ownership_event_payload_invalid")
    return value


def _active_bond(
    bonds: Mapping[str, OwnershipBond], bond_ref: str
) -> OwnershipBond:
    bond = bonds.get(bond_ref)
    if bond is None or bond.status != "active":
        raise OwnershipRuntimeError("ownership_bond_not_active")
    return bond


def _bond_attributes(
    attributes: object, bond_type: str
) -> dict[str, object]:
    if bond_type not in OwnershipProjector._BOND_TYPES:
        raise OwnershipRuntimeError("ownership_bond_type_invalid")
    if not isinstance(attributes, Mapping) or len(attributes) > 8:
        raise OwnershipRuntimeError("ownership_bond_attributes_invalid")
    normalized: dict[str, object] = {}
    for key, value in attributes.items():
        if type(key) is not str:
            raise OwnershipRuntimeError("ownership_bond_attributes_invalid")
        if isinstance(value, Decimal):
            if not value.is_finite():
                raise OwnershipRuntimeError("ownership_bond_attributes_invalid")
            normalized[key] = format(value, "f")
        elif type(value) in {str, int, bool}:
            normalized[key] = value
        else:
            raise OwnershipRuntimeError("ownership_bond_attributes_invalid")
    return dict(sorted(normalized.items()))


def _bond_granted_payload(
    bond_ref: str,
    subject_ref: str,
    target_ref: str,
    bond_type: str,
    scope: str,
    term_expires_at: int | None,
    source_event_ref: str,
    attributes: Mapping[str, object],
) -> dict[str, object]:
    payload: dict[str, object] = {
        "bond_ref": bond_ref,
        "subject_ref": subject_ref,
        "target_ref": target_ref,
        "bond_type": bond_type,
        "scope": scope,
        "source_event_ref": source_event_ref,
    }
    if term_expires_at is not None:
        payload["term_expires_at"] = term_expires_at
    if attributes:
        payload["attributes"] = dict(attributes)
    return payload


def _require_world_tick(world_tick: int) -> None:
    if isinstance(world_tick, bool) or not isinstance(world_tick, int) or world_tick < 0:
        raise OwnershipRuntimeError("ownership_world_tick_invalid")


def _require_ownership_revision(revision: int) -> None:
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        raise OwnershipRuntimeError("ownership_revision_invalid")


def _digest(value: object) -> str:
    def default(item: object) -> object:
        if isinstance(item, Mapping):
            return dict(item)
        if hasattr(item, "__dict__"):
            return item.__dict__
        raise TypeError(type(item).__name__)
    return sha256(json.dumps(value, default=default, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


__all__ = ["MunicipalDroughtAssessmentCertificateIntentV1", "OwnershipAuthorityService", "OwnershipBond", "OwnershipProjection", "OwnershipProjector", "OwnershipRight", "OwnershipRuntimeError"]
