"""Narrow authority for deed-backed transfer of a reviewed land right."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Mapping

from app.gameplay.credential_runtime import CredentialProjector, CredentialPresentationValidator
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import InventoryDefinitionRegistry, InventoryProjector
from app.gameplay.models import AppendBatchResult
from app.gameplay.ownership_runtime import OwnershipProjector


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
        right_id: str,
        from_holder_ref: str,
        to_holder_ref: str,
        credential_id: str,
        expected_ownership_revision: int,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        command = {
            "kind": "land_right_transfer",
            "command_id": command_id,
            "asset_ref": asset_ref,
            "right_id": right_id,
            "from_holder_ref": from_holder_ref,
            "to_holder_ref": to_holder_ref,
            "credential_id": credential_id,
            "expected_ownership_revision": expected_ownership_revision,
        }
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

        events = self._store.read_events()
        ownership = self._ownership_projector.rebuild(events)
        right = ownership.rights.get(right_id)
        if right is None or right.asset_ref != asset_ref or right.holder_ref != from_holder_ref:
            raise LandRightRuntimeError("land_right_holder_mismatch")
        credentials = self._credential_projector.rebuild(events)
        credential = credentials.links.get(credential_id)
        if (
            credential is None
            or credential.right_id != right_id
            or credential.credential_kind != policy.credential_kind
            or credential.proves != policy.credential_proves
        ):
            raise LandRightRuntimeError("land_right_credential_required")
        presentation = self._credential_validator.verify_right_holder_presentation(
            credential_id=credential_id,
            presenter_ref=from_holder_ref,
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
                "expected_stream_revisions": {
                    self._OWNERSHIP_STREAM: ownership_revision,
                    self._CREDENTIAL_STREAM: credentials.source_revision_vector.get(
                        self._CREDENTIAL_STREAM,
                        0,
                    ),
                    inventory_stream: inventory.source_revision_vector.get(inventory_stream, 0),
                },
                "pinned_revisions": {
                    "ownership": ownership_revision,
                    "credentials": credentials.source_revision_vector.get(self._CREDENTIAL_STREAM, 0),
                    "inventory": inventory.source_revision_vector.get(inventory_stream, 0),
                },
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
        record = self._store.get_idempotency_record(self._PRINCIPAL, idempotency_key)
        if record is None:
            return None
        if record.payload_digest != digest:
            raise LandRightRuntimeError("idempotency_key_reused")
        result = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if result is None:
            raise LandRightRuntimeError("land_right_idempotency_missing_result")
        return result.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)


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
