"""Atomic zero-consideration gift authority for an item and its full title."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Mapping, Sequence

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import InventoryDefinitionRegistry, InventoryItem, InventoryProjector, InventoryProjection
from app.gameplay.models import AppendBatchResult, GameplayEvent
from app.gameplay.ownership_runtime import OwnershipProjector


class GiftRuntimeError(ValueError):
    pass


@dataclass(frozen=True)
class GiftRecord:
    gift_id: str
    settlement_transaction_id: str
    donor_ref: str
    recipient_ref: str
    asset_ref: str
    item_id: str
    right_id: str
    consideration_amount: int
    source_event_id: str


@dataclass(frozen=True)
class GiftProjection:
    gifts: Mapping[str, GiftRecord]
    source_revision_vector: Mapping[str, int]


class GiftProjector:
    _EVENT_TYPE = "gameplay.commerce.gift_settled"

    def rebuild(self, events: Sequence[GameplayEvent]) -> GiftProjection:
        gifts: dict[str, GiftRecord] = {}
        revisions: dict[str, int] = {}
        for event in sorted(events, key=lambda value: (value.global_sequence, value.event_id)):
            if event.event_type != self._EVENT_TYPE:
                continue
            payload = event.payload
            gift_id = _text(payload, "gift_id")
            if gift_id in gifts:
                raise GiftRuntimeError("economy_transaction_duplicate")
            consideration_amount = _nonnegative(payload, "consideration_amount")
            if consideration_amount != 0:
                raise GiftRuntimeError("economy_gift_consideration_invalid")
            gifts[gift_id] = GiftRecord(
                gift_id=gift_id,
                settlement_transaction_id=event.transaction_id,
                donor_ref=_text(payload, "donor_ref"),
                recipient_ref=_text(payload, "recipient_ref"),
                asset_ref=_text(payload, "asset_ref"),
                item_id=_text(payload, "item_id"),
                right_id=_text(payload, "right_id"),
                consideration_amount=consideration_amount,
                source_event_id=event.event_id,
            )
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
        return GiftProjection(
            gifts=MappingProxyType(dict(sorted(gifts.items()))),
            source_revision_vector=MappingProxyType(dict(sorted(revisions.items()))),
        )


class GiftAuthorityService:
    """Moves a normal item and exclusive full title without economic consideration."""

    _PRINCIPAL = "actor_gameplay.gift_domain"
    _OWNERSHIP_STREAM = "gameplay:ownership"
    _COMMERCE_STREAM = "gameplay:commerce"

    def __init__(self, *, store: GameplayEventStore, inventory_registry: InventoryDefinitionRegistry) -> None:
        self._store = store
        self._registry = inventory_registry
        self._inventory_projector = InventoryProjector(inventory_registry)
        self._ownership_projector = OwnershipProjector()

    def gift_asset(
        self,
        *,
        command_id: str,
        donor_ref: str,
        recipient_ref: str,
        asset_ref: str,
        right_id: str,
        item_id: str,
        source_container_id: str,
        destination_container_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        command = {
            "kind": "gift_asset",
            "command_id": command_id,
            "donor_ref": donor_ref,
            "recipient_ref": recipient_ref,
            "asset_ref": asset_ref,
            "right_id": right_id,
            "item_id": item_id,
            "source_container_id": source_container_id,
            "destination_container_id": destination_container_id,
        }
        digest = _digest(command)
        duplicate = self._duplicate(idempotency_key, digest)
        if duplicate is not None:
            return duplicate
        if not all((donor_ref, recipient_ref, asset_ref, right_id, item_id, source_container_id, destination_container_id)) or donor_ref == recipient_ref:
            raise GiftRuntimeError("economy_gift_invalid")

        events = self._store.read_events()
        ownership = self._ownership_projector.rebuild(events)
        right = ownership.rights.get(right_id)
        if right is None or right.asset_ref != asset_ref or right.holder_ref != donor_ref:
            raise GiftRuntimeError("ownership_right_holder_mismatch")

        donor_inventory = self._inventory_projector.rebuild(donor_ref, events)
        item = donor_inventory.items.get(item_id)
        if item is None or donor_inventory.locations.get(item_id) != source_container_id:
            raise GiftRuntimeError("inventory_move_source_invalid")
        recipient_inventory = self._inventory_projector.rebuild(recipient_ref, events)
        target = recipient_inventory.containers.get(destination_container_id)
        if target is None:
            raise GiftRuntimeError("inventory_container_unknown")
        if target.sealed:
            raise GiftRuntimeError("inventory_access_denied")
        self._require_capacity(recipient_inventory, destination_container_id, item)

        transaction_id = f"tx:{command_id}"
        donor_stream = f"gameplay:inventory:{donor_ref}"
        recipient_stream = f"gameplay:inventory:{recipient_ref}"
        revisions = {
            donor_stream: self._store.get_stream_head(donor_stream),
            recipient_stream: self._store.get_stream_head(recipient_stream),
            self._OWNERSHIP_STREAM: self._store.get_stream_head(self._OWNERSHIP_STREAM),
            self._COMMERCE_STREAM: self._store.get_stream_head(self._COMMERCE_STREAM),
        }
        batch_events = [
            self._event(command_id, 1, "gameplay.inventory.item_transferred_out", donor_stream, transaction_id, causation_id, correlation_id, {"actor_ref": donor_ref, "item_id": item_id, "from_container_id": source_container_id, "to_actor_ref": recipient_ref}),
            self._event(command_id, 2, "gameplay.inventory.item_transferred_in", recipient_stream, transaction_id, causation_id, correlation_id, {"actor_ref": recipient_ref, "item_id": item_id, "definition_id": item.definition_id, "quantity": item.quantity, "to_container_id": destination_container_id, "from_actor_ref": donor_ref}),
            self._event(command_id, 3, "gameplay.ownership.right_transferred", self._OWNERSHIP_STREAM, transaction_id, causation_id, correlation_id, {"right_id": right_id, "asset_ref": asset_ref, "from_holder_ref": donor_ref, "to_holder_ref": recipient_ref}),
            self._event(command_id, 4, "gameplay.commerce.gift_settled", self._COMMERCE_STREAM, transaction_id, causation_id, correlation_id, {"gift_id": f"gift:{command_id}", "donor_ref": donor_ref, "recipient_ref": recipient_ref, "asset_ref": asset_ref, "item_id": item_id, "right_id": right_id, "consideration_amount": 0}),
        ]
        return self._store.append_batch(
            {
                "transaction_id": transaction_id,
                "command_id": command_id,
                "expected_stream_revisions": revisions,
                "pinned_revisions": revisions,
                "events": batch_events,
                "idempotency_record": {"principal_ref": self._PRINCIPAL, "idempotency_key": idempotency_key, "payload_digest": digest},
                "outbox_entries": [],
                "result_digest": digest,
                "projection_refresh_hints": [],
            }
        )

    def _require_capacity(self, projection: InventoryProjection, container_id: str, candidate: InventoryItem) -> None:
        container = projection.containers[container_id]
        entries = [item for item_id, item in projection.items.items() if projection.locations.get(item_id) == container_id]
        weight = sum(self._registry.item(item.definition_id).unit_weight * item.quantity for item in entries) + self._registry.item(candidate.definition_id).unit_weight * candidate.quantity
        volume = sum(self._registry.item(item.definition_id).unit_volume * item.quantity for item in entries) + self._registry.item(candidate.definition_id).unit_volume * candidate.quantity
        if len(entries) + 1 > container.capacity_slots or weight > container.capacity_weight or volume > container.capacity_volume:
            raise GiftRuntimeError("inventory_capacity_exceeded")

    def _duplicate(self, idempotency_key: str, digest: str) -> AppendBatchResult | None:
        record = self._store.get_idempotency_record(self._PRINCIPAL, idempotency_key)
        if record is None:
            return None
        if record.payload_digest != digest:
            raise GiftRuntimeError("idempotency_key_reused")
        result = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if result is None:
            raise GiftRuntimeError("economy_idempotency_missing_result")
        return result.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)

    @staticmethod
    def _event(command_id: str, index: int, event_type: str, stream_id: str, transaction_id: str, causation_id: str, correlation_id: str, payload: Mapping[str, object]) -> dict[str, object]:
        return {
            "event_id": f"evt:{command_id}:gift:{index}",
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


def _text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise GiftRuntimeError("economy_event_payload_invalid")
    return value


def _nonnegative(payload: Mapping[str, object], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise GiftRuntimeError("economy_event_payload_invalid")
    return value


def _digest(value: object) -> str:
    return sha256(json.dumps(value, default=lambda item: dict(item) if isinstance(item, Mapping) else item.__dict__, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


__all__ = ["GiftAuthorityService", "GiftProjection", "GiftProjector", "GiftRecord", "GiftRuntimeError"]
