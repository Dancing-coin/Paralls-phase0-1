"""Narrow authority for deed-backed transfer of a reviewed land right."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Mapping

from app.gameplay.credential_runtime import (
    BondCredentialLink,
    CredentialLink,
    CredentialProjector,
    CredentialPresentationValidator,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import InventoryDefinitionRegistry, InventoryProjector
from app.gameplay.models import AppendBatchResult
from app.gameplay.owner_runtime_base import StoreReadSnapshot, replay_duplicate
from app.gameplay.ownership_runtime import (
    OwnershipAuthorityService,
    OwnershipProjector,
    OwnershipRuntimeError,
)
from app.gameplay.settlement_plan import build_multi_stream_atomic_event_batch_from_fragments


class LandRightRuntimeError(ValueError):
    pass


@dataclass(frozen=True)
class LandRightTransferPolicy:
    asset_ref: str
    credential_kind: str = "deed"
    credential_proves: str = "evidence_only"
    credential_presence_container_ids: tuple[str, ...] = ()


class LandRightTransferAuthority:
    """Transfers a configured land right only with a present, active deed credential."""

    _PRINCIPAL = "actor_gameplay.land_right_transfer_domain"
    _OWNERSHIP_STREAM = "gameplay:ownership"
    _CREDENTIAL_STREAM = "gameplay:credentials"

    def __init__(
        self,
        *,
        store: GameplayEventStore,
        inventory_registry: InventoryDefinitionRegistry,
        policies: tuple[LandRightTransferPolicy, ...],
    ) -> None:
        self._store = store
        self._reads = StoreReadSnapshot(store)
        self._inventory_projector = InventoryProjector(inventory_registry)
        self._ownership_projector = OwnershipProjector()
        self._credential_projector = CredentialProjector()
        self._credential_validator = CredentialPresentationValidator(
            store=store,
            inventory_registry=inventory_registry,
        )
        self._policies = {policy.asset_ref: policy for policy in policies}
        if not self._policies or any(
            not policy.asset_ref
            or policy.credential_kind != "deed"
            or policy.credential_proves not in {"evidence_only", "evidence_and_access"}
            or not policy.credential_presence_container_ids
            or any(not container_id for container_id in policy.credential_presence_container_ids)
            or len(set(policy.credential_presence_container_ids)) != len(policy.credential_presence_container_ids)
            for policy in self._policies.values()
        ):
            raise LandRightRuntimeError("land_right_policy_invalid")

    def transfer(
        self,
        *,
        command_id: str,
        asset_ref: str,
        right_id: str | None = None,
        bond_ref: str | None = None,
        new_bond_ref: str | None = None,
        world_tick: int | None = None,
        from_holder_ref: str,
        to_holder_ref: str,
        credential_id: str,
        expected_ownership_revision: int,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        if (right_id is None) == (bond_ref is None):
            raise LandRightRuntimeError("land_right_reference_invalid")
        if bond_ref is not None and (
            type(bond_ref) is not str or not bond_ref
            or type(new_bond_ref) is not str or not new_bond_ref
            or type(world_tick) is not int or world_tick < 0
        ):
            raise LandRightRuntimeError("land_right_bond_transfer_invalid")
        command = {
            "kind": "land_right_transfer",
            "command_id": command_id,
            "asset_ref": asset_ref,
            "from_holder_ref": from_holder_ref,
            "to_holder_ref": to_holder_ref,
            "credential_id": credential_id,
            "expected_ownership_revision": expected_ownership_revision,
        }
        command["right_id" if right_id is not None else "bond_ref"] = right_id if right_id is not None else bond_ref
        if bond_ref is not None:
            command["new_bond_ref"] = new_bond_ref
            command["world_tick"] = world_tick
        digest = _digest(command)
        duplicate = self._duplicate(idempotency_key, digest)
        if duplicate is not None:
            return duplicate

        policy = self._policies.get(asset_ref)
        if policy is None:
            raise LandRightRuntimeError("land_right_policy_unknown")
        if not to_holder_ref or to_holder_ref == from_holder_ref:
            raise LandRightRuntimeError("land_right_recipient_invalid")
        ownership_revision = self._store.get_stream_head(self._OWNERSHIP_STREAM)
        if expected_ownership_revision != ownership_revision:
            raise LandRightRuntimeError("land_right_revision_conflict")

        events = self._reads.all_events()
        ownership = self._ownership_projector.rebuild(events)
        if ownership.source_revision_vector.get(self._OWNERSHIP_STREAM, 0) != ownership_revision:
            raise LandRightRuntimeError("land_right_revision_conflict")
        credentials = self._credential_projector.rebuild(events)
        credential = credentials.links.get(credential_id)
        if right_id is not None:
            right = ownership.rights.get(right_id)
            if right is None or right.asset_ref != asset_ref or right.holder_ref != from_holder_ref:
                raise LandRightRuntimeError("land_right_holder_mismatch")
            credential_matches = isinstance(credential, CredentialLink) and credential.right_id == right_id
        else:
            bond = ownership.bonds.get(bond_ref)
            if (
                bond is None or bond.status != "active" or bond.target_ref != asset_ref
                or bond.bond_type != "ownership" or bond.subject_ref != from_holder_ref
                or bond.term_expires_at is not None and world_tick >= bond.term_expires_at
            ):
                raise LandRightRuntimeError("land_right_holder_mismatch")
            credential_matches = isinstance(credential, BondCredentialLink) and credential.bond_ref == bond_ref
        if (
            credential is None
            or not credential_matches
            or credential.credential_kind != policy.credential_kind
            or credential.proves != policy.credential_proves
        ):
            raise LandRightRuntimeError("land_right_credential_required")
        presentation = self._credential_validator._verify_presentation_from_events(
            events,
            credential_id=credential_id,
            presenter_ref=from_holder_ref,
            world_tick=world_tick,
        )
        if not presentation.authorized:
            raise LandRightRuntimeError("land_right_credential_required")

        inventory_stream = f"gameplay:inventory:{from_holder_ref}"
        inventory = self._inventory_projector.rebuild(from_holder_ref, events)
        if (
            inventory.locations.get(credential.credential_item_ref)
            not in policy.credential_presence_container_ids
        ):
            raise LandRightRuntimeError("land_right_credential_required")
        transaction_id = f"tx:{command_id}"
        credential_revision_vector = dict(credentials.source_revision_vector)
        for source_event in events:
            if source_event.event_type in {
                "gameplay.credential.item_claimed",
                "gameplay.credential.item_released",
            }:
                credential_revision_vector[source_event.stream_id] = max(
                    credential_revision_vector.get(source_event.stream_id, 0),
                    source_event.stream_revision,
                )
        v1_credential_revision = credential_revision_vector.pop(self._CREDENTIAL_STREAM, None)
        expected_stream_revisions = {
            self._OWNERSHIP_STREAM: ownership_revision,
            inventory_stream: inventory.source_revision_vector.get(inventory_stream, 0),
        }
        if v1_credential_revision is not None:
            expected_stream_revisions[self._CREDENTIAL_STREAM] = v1_credential_revision
        pinned_revisions = {
            "ownership": ownership_revision,
            "inventory": inventory.source_revision_vector.get(inventory_stream, 0),
        }
        if v1_credential_revision is not None:
            pinned_revisions["credentials"] = v1_credential_revision
        pinned_revisions.update(credential_revision_vector)
        if bond_ref is not None:
            inventory_revision = inventory.source_revision_vector.get(inventory_stream, 0)
            read_stream_revisions = {
                **credential_revision_vector,
                inventory_stream: inventory_revision,
            }
            external_pins = {
                "inventory": inventory_revision,
                **credential_revision_vector,
            }
            try:
                ownership_fragment = OwnershipAuthorityService(
                    store=self._store
                ).build_land_right_bond_transfer_fragment(
                    command_id=command_id,
                    bond_ref=bond_ref,
                    new_bond_ref=new_bond_ref,
                    previous_subject=from_holder_ref,
                    new_subject=to_holder_ref,
                    target_ref=asset_ref,
                    source_event_ref=credential.source_event_id,
                    world_tick=world_tick,
                    expected_ownership_revision=ownership_revision,
                    read_stream_revisions=read_stream_revisions,
                    pinned_revisions=external_pins,
                )
            except OwnershipRuntimeError as error:
                raise LandRightRuntimeError("land_right_bond_transfer_invalid") from error
            batch = build_multi_stream_atomic_event_batch_from_fragments(
                command_id=command_id,
                idempotency_principal_ref=self._PRINCIPAL,
                idempotency_key=idempotency_key,
                causation_id=causation_id,
                correlation_id=correlation_id,
                fragments=(ownership_fragment,),
            )
            batch = batch.model_copy(
                update={
                    "idempotency_record": batch.idempotency_record.model_copy(
                        update={"payload_digest": digest}, deep=True
                    ),
                },
                deep=True,
            )
            return self._store.append_batch(batch)

        event = {
            "event_id": f"evt:{command_id}:land-right-transfer",
            "event_type": "gameplay.ownership.right_transferred",
            "schema_version": 1,
            "stream_id": self._OWNERSHIP_STREAM,
            "stream_revision": 0,
            "global_sequence": 0,
            "transaction_id": transaction_id,
            "command_id": command_id,
            "causation_id": causation_id,
            "correlation_id": correlation_id,
            "visibility_policy": "authority_only",
            "payload": {
                "right_id": right_id,
                "asset_ref": asset_ref,
                "from_holder_ref": from_holder_ref,
                "to_holder_ref": to_holder_ref,
                "credential_id": credential_id,
                "policy_ref": f"land_right_policy:{asset_ref}",
            },
        }
        return self._store.append_batch(
            {
                "transaction_id": transaction_id,
                "command_id": command_id,
                "expected_stream_revisions": expected_stream_revisions,
                "read_stream_revisions": credential_revision_vector,
                "pinned_revisions": pinned_revisions,
                "events": [event],
                "idempotency_record": {
                    "principal_ref": self._PRINCIPAL,
                    "idempotency_key": idempotency_key,
                    "payload_digest": digest,
                },
                "outbox_entries": [],
                "result_digest": _digest(event),
                "projection_refresh_hints": [],
            }
        )

    def _duplicate(self, idempotency_key: str, digest: str) -> AppendBatchResult | None:
        return replay_duplicate(
            self._store, principal=self._PRINCIPAL, idempotency_key=idempotency_key,
            payload_digest=digest, error_factory=LandRightRuntimeError,
            missing_result_code="land_right_idempotency_missing_result",
        )


def _digest(value: object) -> str:
    return sha256(
        json.dumps(
            value,
            default=lambda item: dict(item) if isinstance(item, Mapping) else item.__dict__,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


__all__ = [
    "LandRightRuntimeError",
    "LandRightTransferAuthority",
    "LandRightTransferPolicy",
]
