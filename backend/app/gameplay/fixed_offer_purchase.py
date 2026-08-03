"""Atomic fixed-offer purchase authority across economy, inventory, and title."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Mapping, Sequence

from app.gameplay.economy_runtime import EconomyProjector
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import InventoryDefinitionRegistry, InventoryItem, InventoryProjector
from app.gameplay.models import AppendBatchResult, GameplayEvent
from app.gameplay.ownership_runtime import OwnershipProjector


class PurchaseRuntimeError(ValueError):
    pass


@dataclass(frozen=True)
class FixedOffer:
    offer_id: str
    seller_ref: str
    asset_ref: str
    right_id: str
    item_id: str
    source_container_id: str
    price_amount: int
    currency_ref: str
    offer_revision: int
    consumed: bool
    source_event_id: str


@dataclass(frozen=True)
class PurchaseTransaction:
    purchase_id: str
    settlement_transaction_id: str
    offer_id: str
    buyer_ref: str
    seller_ref: str
    asset_ref: str
    item_id: str
    amount: int
    currency_ref: str
    source_event_id: str


@dataclass(frozen=True)
class FixedOfferProjection:
    offers: Mapping[str, FixedOffer]
    transactions: Mapping[str, PurchaseTransaction]
    source_revision_vector: Mapping[str, int]


class FixedOfferProjector:
    _STREAM = "gameplay:commerce"

    def rebuild(self, events: Sequence[GameplayEvent]) -> FixedOfferProjection:
        offers: dict[str, FixedOffer] = {}
        transactions: dict[str, PurchaseTransaction] = {}
        revisions: dict[str, int] = {}
        for event in sorted(events, key=lambda value: (value.global_sequence, value.event_id)):
            if event.event_type not in {"gameplay.commerce.fixed_offer_published", "gameplay.commerce.fixed_offer_consumed", "gameplay.commerce.purchase_settled"}:
                continue
            payload = event.payload
            offer_id = _text(payload, "offer_id")
            if event.event_type == "gameplay.commerce.fixed_offer_published":
                if offer_id in offers:
                    raise PurchaseRuntimeError("economy_offer_duplicate")
                offers[offer_id] = FixedOffer(
                    offer_id=offer_id,
                    seller_ref=_text(payload, "seller_ref"),
                    asset_ref=_text(payload, "asset_ref"),
                    right_id=_text(payload, "right_id"),
                    item_id=_text(payload, "item_id"),
                    source_container_id=_text(payload, "source_container_id"),
                    price_amount=_positive(payload, "price_amount"),
                    currency_ref=_text(payload, "currency_ref"),
                    offer_revision=event.stream_revision,
                    consumed=False,
                    source_event_id=event.event_id,
                )
            elif event.event_type == "gameplay.commerce.fixed_offer_consumed":
                prior = offers.get(offer_id)
                if prior is None or prior.consumed:
                    raise PurchaseRuntimeError("economy_offer_not_found")
                offers[offer_id] = FixedOffer(**{**prior.__dict__, "consumed": True, "source_event_id": event.event_id})
            else:
                purchase_id = _text(payload, "purchase_id")
                if purchase_id in transactions:
                    raise PurchaseRuntimeError("economy_transaction_duplicate")
                offer = offers.get(offer_id)
                if offer is None or not offer.consumed:
                    raise PurchaseRuntimeError("economy_transaction_invalid")
                transactions[purchase_id] = PurchaseTransaction(
                    purchase_id=purchase_id,
                    settlement_transaction_id=event.transaction_id,
                    offer_id=offer_id,
                    buyer_ref=_text(payload, "buyer_ref"),
                    seller_ref=_text(payload, "seller_ref"),
                    asset_ref=_text(payload, "asset_ref"),
                    item_id=_text(payload, "item_id"),
                    amount=_positive(payload, "amount"),
                    currency_ref=_text(payload, "currency_ref"),
                    source_event_id=event.event_id,
                )
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
        return FixedOfferProjection(
            offers=MappingProxyType(dict(sorted(offers.items()))),
            transactions=MappingProxyType(dict(sorted(transactions.items()))),
            source_revision_vector=MappingProxyType(dict(sorted(revisions.items()))),
        )


class FixedOfferAuthorityService:
    """Settles a quoted item and its full title in one append-only authority batch."""

    _OFFER_PRINCIPAL = "actor_gameplay.fixed_offer_domain"
    _PURCHASE_PRINCIPAL = "actor_gameplay.fixed_offer_purchase_domain"
    _ECONOMY_STREAM = "gameplay:economy"
    _OWNERSHIP_STREAM = "gameplay:ownership"
    _COMMERCE_STREAM = "gameplay:commerce"

    def __init__(self, *, store: GameplayEventStore, inventory_registry: InventoryDefinitionRegistry) -> None:
        self._store = store
        self._registry = inventory_registry
        self._inventory_projector = InventoryProjector(inventory_registry)
        self._offer_projector = FixedOfferProjector()
        self._economy_projector = EconomyProjector()
        self._ownership_projector = OwnershipProjector()

    def offer_projection(self) -> FixedOfferProjection:
        return self._offer_projector.rebuild(self._store.read_events())

    def publish_offer(
        self,
        *,
        command_id: str,
        offer_id: str,
        seller_ref: str,
        asset_ref: str,
        right_id: str,
        item_id: str,
        source_container_id: str,
        price_amount: int,
        currency_ref: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        command = {
            "kind": "publish_fixed_offer",
            "command_id": command_id,
            "offer_id": offer_id,
            "seller_ref": seller_ref,
            "asset_ref": asset_ref,
            "right_id": right_id,
            "item_id": item_id,
            "source_container_id": source_container_id,
            "price_amount": price_amount,
            "currency_ref": currency_ref,
        }
        digest = _digest(command)
        duplicate = self._duplicate(self._OFFER_PRINCIPAL, idempotency_key, digest)
        if duplicate is not None:
            return duplicate
        offers = self.offer_projection()
        ownership = self._ownership_projector.rebuild(self._store.read_events())
        seller_inventory = self._inventory_projector.rebuild(seller_ref, self._store.read_events())
        right = ownership.rights.get(right_id)
        if not all((offer_id, seller_ref, asset_ref, right_id, item_id, source_container_id, currency_ref)) or price_amount <= 0:
            raise PurchaseRuntimeError("economy_offer_invalid")
        if offer_id in offers.offers:
            raise PurchaseRuntimeError("economy_offer_duplicate")
        if right is None or right.asset_ref != asset_ref or right.holder_ref != seller_ref:
            raise PurchaseRuntimeError("ownership_right_holder_mismatch")
        if item_id not in seller_inventory.items or seller_inventory.locations.get(item_id) != source_container_id:
            raise PurchaseRuntimeError("inventory_move_source_invalid")
        stream_revisions = {
            self._COMMERCE_STREAM: self._store.get_stream_head(self._COMMERCE_STREAM),
            self._OWNERSHIP_STREAM: self._store.get_stream_head(self._OWNERSHIP_STREAM),
            f"gameplay:inventory:{seller_ref}": self._store.get_stream_head(f"gameplay:inventory:{seller_ref}"),
        }
        event = self._event(
            command_id,
            1,
            "gameplay.commerce.fixed_offer_published",
            self._COMMERCE_STREAM,
            f"tx:{command_id}",
            causation_id,
            correlation_id,
            {
                "offer_id": offer_id,
                "seller_ref": seller_ref,
                "asset_ref": asset_ref,
                "right_id": right_id,
                "item_id": item_id,
                "source_container_id": source_container_id,
                "price_amount": price_amount,
                "currency_ref": currency_ref,
            },
        )
        return self._append(command_id, self._OFFER_PRINCIPAL, idempotency_key, digest, [event], stream_revisions)

    def purchase(
        self,
        *,
        command_id: str,
        offer_id: str,
        expected_offer_revision: int,
        buyer_ref: str,
        buyer_account_id: str,
        seller_account_id: str,
        destination_container_id: str,
        accepted_amount: int,
        accepted_currency_ref: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        command = {
            "kind": "purchase_fixed_offer",
            "command_id": command_id,
            "offer_id": offer_id,
            "expected_offer_revision": expected_offer_revision,
            "buyer_ref": buyer_ref,
            "buyer_account_id": buyer_account_id,
            "seller_account_id": seller_account_id,
            "destination_container_id": destination_container_id,
            "accepted_amount": accepted_amount,
            "accepted_currency_ref": accepted_currency_ref,
        }
        digest = _digest(command)
        duplicate = self._duplicate(self._PURCHASE_PRINCIPAL, idempotency_key, digest)
        if duplicate is not None:
            return duplicate
        events = self._store.read_events()
        offers = self._offer_projector.rebuild(events)
        offer = offers.offers.get(offer_id)
        if offer is None or offer.consumed:
            raise PurchaseRuntimeError("economy_offer_not_found")
        if expected_offer_revision != offer.offer_revision:
            raise PurchaseRuntimeError("economy_offer_stale")
        if accepted_amount != offer.price_amount or accepted_currency_ref != offer.currency_ref:
            raise PurchaseRuntimeError("economy_price_changed")
        if not buyer_ref or buyer_ref == offer.seller_ref or not destination_container_id:
            raise PurchaseRuntimeError("economy_purchase_invalid")

        economy = self._economy_projector.rebuild(events)
        buyer_account = economy.accounts.get(buyer_account_id)
        seller_account = economy.accounts.get(seller_account_id)
        if buyer_account is None or seller_account is None or buyer_account.owner_ref != buyer_ref or seller_account.owner_ref != offer.seller_ref:
            raise PurchaseRuntimeError("economy_account_invalid")
        if buyer_account.currency_ref != offer.currency_ref or seller_account.currency_ref != offer.currency_ref:
            raise PurchaseRuntimeError("economy_currency_mismatch")
        if buyer_account.balance < offer.price_amount:
            raise PurchaseRuntimeError("economy_insufficient_funds")

        ownership = self._ownership_projector.rebuild(events)
        right = ownership.rights.get(offer.right_id)
        if right is None or right.asset_ref != offer.asset_ref or right.holder_ref != offer.seller_ref:
            raise PurchaseRuntimeError("ownership_right_holder_mismatch")

        seller_inventory = self._inventory_projector.rebuild(offer.seller_ref, events)
        item = seller_inventory.items.get(offer.item_id)
        if item is None or seller_inventory.locations.get(offer.item_id) != offer.source_container_id:
            raise PurchaseRuntimeError("inventory_move_source_invalid")
        buyer_inventory = self._inventory_projector.rebuild(buyer_ref, events)
        destination = buyer_inventory.containers.get(destination_container_id)
        if destination is None:
            raise PurchaseRuntimeError("inventory_container_unknown")
        if destination.sealed:
            raise PurchaseRuntimeError("inventory_access_denied")
        self._require_capacity(buyer_inventory, destination_container_id, item)

        transaction_id = f"tx:{command_id}"
        seller_stream = f"gameplay:inventory:{offer.seller_ref}"
        buyer_stream = f"gameplay:inventory:{buyer_ref}"
        stream_revisions = {
            self._ECONOMY_STREAM: self._store.get_stream_head(self._ECONOMY_STREAM),
            self._OWNERSHIP_STREAM: self._store.get_stream_head(self._OWNERSHIP_STREAM),
            seller_stream: self._store.get_stream_head(seller_stream),
            buyer_stream: self._store.get_stream_head(buyer_stream),
            self._COMMERCE_STREAM: self._store.get_stream_head(self._COMMERCE_STREAM),
        }
        batch_events = [
            self._event(command_id, 1, "gameplay.economy.account_debited", self._ECONOMY_STREAM, transaction_id, causation_id, correlation_id, {"account_id": buyer_account_id, "amount": offer.price_amount}),
            self._event(command_id, 2, "gameplay.economy.account_credited", self._ECONOMY_STREAM, transaction_id, causation_id, correlation_id, {"account_id": seller_account_id, "amount": offer.price_amount}),
            self._event(command_id, 3, "gameplay.inventory.item_transferred_out", seller_stream, transaction_id, causation_id, correlation_id, {"actor_ref": offer.seller_ref, "item_id": offer.item_id, "from_container_id": offer.source_container_id, "to_actor_ref": buyer_ref}),
            self._event(command_id, 4, "gameplay.inventory.item_transferred_in", buyer_stream, transaction_id, causation_id, correlation_id, {"actor_ref": buyer_ref, "item_id": offer.item_id, "definition_id": item.definition_id, "quantity": item.quantity, "to_container_id": destination_container_id, "from_actor_ref": offer.seller_ref}),
            self._event(command_id, 5, "gameplay.ownership.right_transferred", self._OWNERSHIP_STREAM, transaction_id, causation_id, correlation_id, {"right_id": offer.right_id, "asset_ref": offer.asset_ref, "from_holder_ref": offer.seller_ref, "to_holder_ref": buyer_ref}),
            self._event(command_id, 6, "gameplay.commerce.fixed_offer_consumed", self._COMMERCE_STREAM, transaction_id, causation_id, correlation_id, {"offer_id": offer_id, "buyer_ref": buyer_ref, "accepted_amount": accepted_amount, "currency_ref": accepted_currency_ref}),
            self._event(command_id, 7, "gameplay.commerce.purchase_settled", self._COMMERCE_STREAM, transaction_id, causation_id, correlation_id, {"purchase_id": f"purchase:{command_id}", "offer_id": offer_id, "buyer_ref": buyer_ref, "seller_ref": offer.seller_ref, "asset_ref": offer.asset_ref, "item_id": offer.item_id, "amount": offer.price_amount, "currency_ref": offer.currency_ref}),
        ]
        return self._append(command_id, self._PURCHASE_PRINCIPAL, idempotency_key, digest, batch_events, stream_revisions)

    def _require_capacity(self, projection: object, container_id: str, candidate: InventoryItem) -> None:
        containers = projection.containers
        entries = [item for item_id, item in projection.items.items() if projection.locations.get(item_id) == container_id]
        weight = sum(self._registry.item(item.definition_id).unit_weight * item.quantity for item in entries) + self._registry.item(candidate.definition_id).unit_weight * candidate.quantity
        volume = sum(self._registry.item(item.definition_id).unit_volume * item.quantity for item in entries) + self._registry.item(candidate.definition_id).unit_volume * candidate.quantity
        container = containers[container_id]
        if len(entries) + 1 > container.capacity_slots or weight > container.capacity_weight or volume > container.capacity_volume:
            raise PurchaseRuntimeError("inventory_capacity_exceeded")

    def _duplicate(self, principal: str, idempotency_key: str, digest: str) -> AppendBatchResult | None:
        record = self._store.get_idempotency_record(principal, idempotency_key)
        if record is None:
            return None
        if record.payload_digest != digest:
            raise PurchaseRuntimeError("idempotency_key_reused")
        result = self._store.get_by_idempotency(principal, idempotency_key)
        if result is None:
            raise PurchaseRuntimeError("economy_idempotency_missing_result")
        return result.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)

    def _append(self, command_id: str, principal: str, idempotency_key: str, digest: str, events: list[dict[str, object]], expected_stream_revisions: Mapping[str, int]) -> AppendBatchResult:
        return self._store.append_batch(
            {
                "transaction_id": f"tx:{command_id}",
                "command_id": command_id,
                "expected_stream_revisions": dict(expected_stream_revisions),
                "pinned_revisions": dict(expected_stream_revisions),
                "events": events,
                "idempotency_record": {"principal_ref": principal, "idempotency_key": idempotency_key, "payload_digest": digest},
                "outbox_entries": [],
                "result_digest": digest,
                "projection_refresh_hints": [],
            }
        )

    @staticmethod
    def _event(command_id: str, index: int, event_type: str, stream_id: str, transaction_id: str, causation_id: str, correlation_id: str, payload: Mapping[str, object]) -> dict[str, object]:
        return {
            "event_id": f"evt:{command_id}:commerce:{index}",
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
        raise PurchaseRuntimeError("economy_event_payload_invalid")
    return value


def _positive(payload: Mapping[str, object], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise PurchaseRuntimeError("economy_event_payload_invalid")
    return value


def _digest(value: object) -> str:
    return sha256(json.dumps(value, default=lambda item: dict(item) if isinstance(item, Mapping) else item.__dict__, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


__all__ = ["FixedOffer", "FixedOfferAuthorityService", "FixedOfferProjection", "FixedOfferProjector", "PurchaseRuntimeError", "PurchaseTransaction"]
