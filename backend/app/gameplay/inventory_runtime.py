"""Minimal event-sourced item location and container-capacity authority."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Mapping, Sequence

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayEvent, OwnerAuthorizedFragment


class InventoryRuntimeError(ValueError):
    pass


@dataclass(frozen=True)
class ItemDefinition:
    definition_id: str
    definition_version: str
    unit_weight: int
    unit_volume: int
    is_living: bool = False


@dataclass(frozen=True)
class ContainerSpec:
    container_id: str
    capacity_weight: int
    capacity_volume: int
    capacity_slots: int
    sealed: bool = False
    carrier_item_id: str = ""
    content_weight_propagation: str = "include_contents"
    allows_living_items: bool = True


@dataclass(frozen=True)
class InventoryItem:
    item_id: str
    definition_id: str
    quantity: int
    source_event_id: str
    reserved_quantity: int = 0

    @property
    def remaining_quantity(self) -> int:
        return self.quantity - self.reserved_quantity

    @property
    def available_quantity(self) -> int:
        return self.remaining_quantity


@dataclass(frozen=True)
class InventoryReservation:
    reservation_ref: str
    item_id: str
    quantity: int
    source_event_id: str
    work_order_ref: str | None = None
    shift_ref: str | None = None
    reservation_context_ref: str | None = None


@dataclass(frozen=True)
class CommerceCapacityReservation:
    """A bounded delivery/output slot owned by Inventory/Production.

    This is deliberately a reservation reference, not a scheduler or a
    generalized production plan.  P4 only needs a current, owner-backed
    quantity that a clearing authority can revalidate.
    """

    capacity_reservation_ref: str
    available_quantity: int
    source_event_id: str


@dataclass(frozen=True)
class InventoryContainer:
    container_id: str
    capacity_weight: int
    capacity_volume: int
    capacity_slots: int
    sealed: bool
    source_event_id: str
    carrier_item_id: str = ""
    content_weight_propagation: str = "include_contents"
    allows_living_items: bool = True


@dataclass(frozen=True)
class InventoryProjection:
    actor_ref: str
    items: Mapping[str, InventoryItem]
    containers: Mapping[str, InventoryContainer]
    locations: Mapping[str, str]
    source_revision_vector: Mapping[str, int]
    projection_revision: str
    reservations: Mapping[str, InventoryReservation] = field(default_factory=dict)
    capacity_reservations: Mapping[str, CommerceCapacityReservation] = field(default_factory=dict)


@dataclass(frozen=True)
class EncumbranceProjection:
    carrier_ref: str
    carried_weight: int
    carried_volume: int
    source_breakdown: Mapping[str, int]
    source_revision_vector: Mapping[str, int]
    projection_revision: str
    explanation_entries: tuple["EncumbranceExplanationEntry", ...] = ()


@dataclass(frozen=True)
class EncumbranceExplanationEntry:
    item_id: str
    location: str
    propagation_strategy: str
    included_weight: int
    excluded_weight: int
    source_refs: tuple[str, ...]


class InventoryDefinitionRegistry:
    def __init__(self) -> None:
        self._items: dict[str, ItemDefinition] = {}

    def register_item(self, definition: ItemDefinition) -> None:
        if (
            not definition.definition_id
            or not definition.definition_version
            or definition.definition_id in self._items
            or definition.unit_weight < 0
            or definition.unit_volume < 0
            or not isinstance(definition.is_living, bool)
        ):
            raise InventoryRuntimeError("inventory_item_definition_invalid")
        self._items[definition.definition_id] = definition

    def item(self, definition_id: str) -> ItemDefinition:
        try:
            return self._items[definition_id]
        except KeyError as exc:
            raise InventoryRuntimeError("inventory_item_definition_unknown") from exc


class InventoryProjector:
    """Derives item and location truth only from committed Gameplay events."""

    def __init__(self, registry: InventoryDefinitionRegistry) -> None:
        self._registry = registry

    def rebuild(self, actor_ref: str, events: Sequence[GameplayEvent]) -> InventoryProjection:
        items: dict[str, InventoryItem] = {}
        containers: dict[str, InventoryContainer] = {}
        locations: dict[str, str] = {}
        reservations: dict[str, InventoryReservation] = {}
        capacity_reservations: dict[str, CommerceCapacityReservation] = {}
        reserved_quantities: dict[str, int] = {}
        revisions: dict[str, int] = {}
        for event in sorted(events, key=lambda item: (item.global_sequence, item.event_id)):
            if not event.event_type.startswith("gameplay.inventory."):
                continue
            payload = event.payload
            if str(payload.get("actor_ref", "")) != actor_ref:
                # Inventory streams are actor-scoped. Other actors' events are
                # unrelated input, not corruption of this actor's projection.
                continue
            if event.event_type == "gameplay.inventory.container_created":
                container_id = _text(payload, "container_id")
                if container_id in containers:
                    raise InventoryRuntimeError("inventory_container_duplicate")
                containers[container_id] = InventoryContainer(
                    container_id,
                    _nonnegative(payload, "capacity_weight"),
                    _nonnegative(payload, "capacity_volume"),
                    _nonnegative(payload, "capacity_slots"),
                    bool(payload.get("sealed", False)),
                    event.event_id,
                    _optional_text(payload, "carrier_item_id"),
                    _content_weight_propagation(payload.get("content_weight_propagation", "include_contents")),
                    _bool_with_default(payload, "allows_living_items", True),
                )
            elif event.event_type == "gameplay.inventory.item_instantiated":
                item_id = _text(payload, "item_id")
                definition_id = _text(payload, "definition_id")
                if item_id in items:
                    raise InventoryRuntimeError("inventory_item_duplicate")
                self._registry.item(definition_id)
                items[item_id] = InventoryItem(item_id, definition_id, _positive(payload, "quantity"), event.event_id)
            elif event.event_type == "gameplay.inventory.output_received":
                _text(payload, "source_ref")
                _text(payload, "item_ref")
                item_id = _text(payload, "item_id")
                definition_id = _text(payload, "definition_id")
                quantity = _positive(payload, "quantity")
                container_id = _text(payload, "container_id")
                if item_id in items or container_id not in containers:
                    raise InventoryRuntimeError("inventory_output_invalid")
                self._registry.item(definition_id)
                items[item_id] = InventoryItem(item_id, definition_id, quantity, event.event_id)
                locations[item_id] = container_id
            elif event.event_type == "gameplay.inventory.item_moved":
                item_id = _text(payload, "item_id")
                from_container = _text(payload, "from_container_id")
                to_container = _text(payload, "to_container_id")
                if item_id not in items or to_container not in containers:
                    raise InventoryRuntimeError("inventory_move_source_invalid")
                if locations.get(item_id) != from_container and not (from_container == "inventory:unplaced" and item_id not in locations):
                    raise InventoryRuntimeError("inventory_move_source_invalid")
                locations[item_id] = to_container
                item = items[item_id]
                items[item_id] = InventoryItem(item.item_id, item.definition_id, item.quantity, item.source_event_id, item.reserved_quantity)
            elif event.event_type == "gameplay.inventory.item_transferred_out":
                item_id = _text(payload, "item_id")
                from_container = _text(payload, "from_container_id")
                if item_id not in items or locations.get(item_id) != from_container:
                    raise InventoryRuntimeError("inventory_move_source_invalid")
                locations.pop(item_id)
            elif event.event_type == "gameplay.inventory.item_transferred_in":
                item_id = _text(payload, "item_id")
                definition_id = _text(payload, "definition_id")
                quantity = _positive(payload, "quantity")
                to_container = _text(payload, "to_container_id")
                if item_id in items or to_container not in containers:
                    raise InventoryRuntimeError("inventory_move_source_invalid")
                self._registry.item(definition_id)
                items[item_id] = InventoryItem(item_id, definition_id, quantity, event.event_id)
                locations[item_id] = to_container
            elif event.event_type == "gameplay.inventory.item_equipped":
                item_id = _text(payload, "item_id")
                from_container = _text(payload, "from_container_id")
                equipment_location = _text(payload, "equipment_location")
                if item_id not in items or not equipment_location.startswith("equipment:"):
                    raise InventoryRuntimeError("inventory_move_source_invalid")
                if locations.get(item_id) != from_container:
                    raise InventoryRuntimeError("inventory_move_source_invalid")
                locations[item_id] = equipment_location
                item = items[item_id]
                items[item_id] = InventoryItem(item.item_id, item.definition_id, item.quantity, item.source_event_id, item.reserved_quantity)
            elif event.event_type == "gameplay.inventory.item_unequipped":
                item_id = _text(payload, "item_id")
                equipment_location = _text(payload, "equipment_location")
                to_container = _text(payload, "to_container_id")
                if item_id not in items or to_container not in containers or not equipment_location.startswith("equipment:"):
                    raise InventoryRuntimeError("inventory_move_source_invalid")
                if locations.get(item_id) != equipment_location:
                    raise InventoryRuntimeError("inventory_move_source_invalid")
                locations[item_id] = to_container
                item = items[item_id]
                items[item_id] = InventoryItem(item.item_id, item.definition_id, item.quantity, item.source_event_id, item.reserved_quantity)
            elif event.event_type == "gameplay.inventory.reservation_created":
                item_id = _text(payload, "item_id")
                reservation_ref = _text(payload, "reservation_ref")
                quantity = _positive(payload, "quantity")
                item = items.get(item_id)
                location = locations.get(item_id, "")
                if item is None or not location.startswith("container:") or reservation_ref in reservations:
                    raise InventoryRuntimeError("inventory_reservation_source_invalid" if item is None or not location.startswith("container:") else "inventory_reservation_duplicate")
                if item.remaining_quantity < quantity:
                    raise InventoryRuntimeError("inventory_reservation_insufficient")
                reservations[reservation_ref] = InventoryReservation(reservation_ref, item_id, quantity, event.event_id)
                reserved_quantities[item_id] = reserved_quantities.get(item_id, 0) + quantity
                items[item_id] = InventoryItem(item.item_id, item.definition_id, item.quantity, item.source_event_id, reserved_quantities[item_id])
            elif event.event_type == "gameplay.inventory.reservation_consumed":
                reservation_ref = _text(payload, "reservation_ref")
                reservation = reservations.pop(reservation_ref, None)
                if reservation is None:
                    raise InventoryRuntimeError("inventory_reservation_unknown")
                item = items.get(reservation.item_id)
                if item is None:
                    raise InventoryRuntimeError("inventory_reservation_unknown")
                reserved_total = reserved_quantities.get(reservation.item_id, 0) - reservation.quantity
                updated_quantity = item.quantity - reservation.quantity
                if reserved_total < 0 or updated_quantity < 0:
                    raise InventoryRuntimeError("inventory_reservation_unknown")
                if updated_quantity == 0:
                    items.pop(reservation.item_id)
                    locations.pop(reservation.item_id, None)
                    reserved_quantities.pop(reservation.item_id, None)
                else:
                    reserved_quantities[reservation.item_id] = reserved_total
                    items[reservation.item_id] = InventoryItem(item.item_id, item.definition_id, updated_quantity, item.source_event_id, reserved_total)
            elif event.event_type == "gameplay.inventory.reservation_released":
                reservation_ref = _text(payload, "reservation_ref")
                reservation = reservations.pop(reservation_ref, None)
                if reservation is None:
                    raise InventoryRuntimeError("inventory_reservation_unknown")
                item = items.get(reservation.item_id)
                if item is None:
                    raise InventoryRuntimeError("inventory_reservation_unknown")
                reserved_total = reserved_quantities.get(reservation.item_id, 0) - reservation.quantity
                if reserved_total < 0:
                    raise InventoryRuntimeError("inventory_reservation_unknown")
                reserved_quantities[reservation.item_id] = reserved_total
                items[reservation.item_id] = InventoryItem(item.item_id, item.definition_id, item.quantity, item.source_event_id, reserved_total)
            elif event.event_type == "gameplay.inventory.commerce_capacity_reserved":
                capacity_reservation_ref = _text(payload, "capacity_reservation_ref")
                if capacity_reservation_ref in capacity_reservations:
                    raise InventoryRuntimeError("inventory_capacity_reservation_duplicate")
                capacity_reservations[capacity_reservation_ref] = CommerceCapacityReservation(
                    capacity_reservation_ref,
                    _positive(payload, "available_quantity"),
                    event.event_id,
                )
            elif event.event_type == "gameplay.inventory.commerce_capacity_released":
                capacity_reservation_ref = _text(payload, "capacity_reservation_ref")
                if capacity_reservation_ref not in capacity_reservations:
                    raise InventoryRuntimeError("inventory_capacity_reservation_unknown")
                capacity_reservations.pop(capacity_reservation_ref)
            else:
                continue
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
        frozen_items = MappingProxyType(dict(sorted(items.items())))
        frozen_containers = MappingProxyType(dict(sorted(containers.items())))
        frozen_locations = MappingProxyType(dict(sorted(locations.items())))
        frozen_reservations = MappingProxyType(dict(sorted(reservations.items())))
        frozen_capacity_reservations = MappingProxyType(dict(sorted(capacity_reservations.items())))
        frozen_revisions = MappingProxyType(dict(sorted(revisions.items())))
        return InventoryProjection(
            actor_ref,
            frozen_items,
            frozen_containers,
            frozen_locations,
            frozen_revisions,
            f"inventory:{_digest([actor_ref, frozen_items, frozen_containers, frozen_locations, frozen_reservations, frozen_capacity_reservations, frozen_revisions])[:16]}",
            frozen_reservations,
            frozen_capacity_reservations,
        )

    def rebuild_encumbrance(
        self,
        projection: InventoryProjection,
        *,
        carrier_ref: str,
        carried_container_ids: Sequence[str],
        carried_item_ids: Sequence[str] = (),
    ) -> EncumbranceProjection:
        container_ids = tuple(sorted(set(carried_container_ids)))
        if any(container_id not in projection.containers for container_id in container_ids):
            raise InventoryRuntimeError("inventory_container_unknown")
        direct_item_ids = tuple(sorted(set(carried_item_ids)))
        if any(item_id not in projection.items for item_id in direct_item_ids):
            raise InventoryRuntimeError("inventory_item_unknown")

        weights: dict[str, int] = {}
        volumes: dict[str, int] = {}
        explanations: dict[str, EncumbranceExplanationEntry] = {}

        def record(item_id: str, propagation_strategy: str, *, source_container: InventoryContainer | None = None) -> None:
            item = projection.items[item_id]
            definition = self._registry.item(item.definition_id)
            total_weight = definition.unit_weight * item.quantity
            total_volume = definition.unit_volume * item.quantity
            included_weight = total_weight if propagation_strategy != "exclude_contents" else 0
            excluded_weight = total_weight - included_weight
            source_refs = [item.source_event_id]
            if source_container is not None:
                source_refs.append(source_container.source_event_id)
            explanations[item_id] = EncumbranceExplanationEntry(
                item_id=item_id,
                location=projection.locations.get(item_id, "inventory:unplaced"),
                propagation_strategy=propagation_strategy,
                included_weight=included_weight,
                excluded_weight=excluded_weight,
                source_refs=tuple(sorted(set(source_refs))),
            )
            weights[item_id] = included_weight
            volumes[item_id] = total_volume if included_weight else 0

        for item_id, item in projection.items.items():
            if projection.locations.get(item_id) in container_ids:
                container = projection.containers[str(projection.locations[item_id])]
                record(item_id, container.content_weight_propagation, source_container=container)
        for item_id in direct_item_ids:
            record(item_id, "carrier_item")
            for container in projection.containers.values():
                if container.carrier_item_id != item_id:
                    continue
                for contained_item_id in sorted(
                    candidate_id
                    for candidate_id, location in projection.locations.items()
                    if location == container.container_id
                ):
                    record(
                        contained_item_id,
                        container.content_weight_propagation,
                        source_container=container,
                    )

        breakdown = {item_id: weight for item_id, weight in weights.items() if weight > 0}
        volume = sum(volumes.values())
        frozen_breakdown = MappingProxyType(dict(sorted(breakdown.items())))
        frozen_explanations = tuple(explanations[item_id] for item_id in sorted(explanations))
        digest = _digest(
            {
                "carrier_ref": carrier_ref,
                "containers": container_ids,
                "carried_item_ids": direct_item_ids,
                "breakdown": frozen_breakdown,
                "explanation": frozen_explanations,
                "volume": volume,
                "revisions": projection.source_revision_vector,
            }
        )
        return EncumbranceProjection(
            carrier_ref,
            sum(frozen_breakdown.values()),
            volume,
            frozen_breakdown,
            projection.source_revision_vector,
            f"encumbrance:{digest[:16]}",
            frozen_explanations,
        )


class InventoryAuthorityService:
    """Validates a full projection then appends atomic inventory events."""

    _PRINCIPAL = "actor_gameplay.inventory_domain"

    def __init__(self, *, store: GameplayEventStore, registry: InventoryDefinitionRegistry) -> None:
        self._store = store
        self._registry = registry
        self._projector = InventoryProjector(registry)

    def build_commerce_custody_fragment(
        self,
        *,
        seller_actor_ref: str,
        commitment_ref: str,
        custody_refs: tuple[str, ...],
        capacity_reservation_refs: tuple[str, ...],
        delivery_window_ref: str,
        expected_revision: int,
        policy_revision: str,
    ) -> OwnerAuthorizedFragment:
        """Inventory-owned reservation proposal for the P4 commerce batch."""
        if not seller_actor_ref or not custody_refs or not delivery_window_ref:
            raise InventoryRuntimeError("commerce_inventory_reference_invalid")
        if any(not ref.startswith(("reservation:", "custody:")) for ref in custody_refs):
            raise InventoryRuntimeError("commerce_inventory_custody_invalid")
        if any(not ref.startswith("capacity:") for ref in capacity_reservation_refs):
            raise InventoryRuntimeError("commerce_inventory_capacity_invalid")
        stream_id = f"gameplay:inventory:{seller_actor_ref}"
        projection = self._projector.rebuild(seller_actor_ref, self._store.read_events())
        if projection.source_revision_vector.get(stream_id, 0) != expected_revision:
            raise InventoryRuntimeError("revision_conflict")
        missing_custody = [
            ref for ref in custody_refs
            if ref.startswith("reservation:") and ref not in projection.reservations
        ]
        if missing_custody:
            raise InventoryRuntimeError("commerce_inventory_custody_missing")
        if any(ref not in projection.capacity_reservations for ref in capacity_reservation_refs):
            raise InventoryRuntimeError("commerce_inventory_capacity_missing")
        return OwnerAuthorizedFragment(
            fragment_id=f"fragment:inventory:commerce:{seller_actor_ref}:{commitment_ref}",
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref="inventory:commerce-custody-reservation",
            expected_revisions={stream_id: expected_revision},
            pinned_revisions={f"inventory:{seller_actor_ref}": expected_revision},
            event_specs={
                stream_id: (
                    (
                        "gameplay.inventory.custody_reserved_for_commerce",
                        {
                            "commitment_ref": commitment_ref,
                            "actor_ref": seller_actor_ref,
                            "custody_refs": custody_refs,
                            "capacity_reservation_refs": capacity_reservation_refs,
                            "delivery_window_ref": delivery_window_ref,
                            "policy_revision": policy_revision,
                        },
                    ),
                )
            },
        )

    def build_commerce_delivery_fragment(
        self,
        *,
        seller_actor_ref: str,
        delivery_ref: str,
        commitment_ref: str,
        status: str,
        delivered_quantity: int,
        quality_evidence_ref: str,
        delivery_window_ref: str,
        reason: str | None,
        expected_revision: int,
        policy_revision: str,
    ) -> OwnerAuthorizedFragment:
        if status not in {"delivered", "rejected", "cancelled"} or delivered_quantity < 0 or not quality_evidence_ref:
            raise InventoryRuntimeError("commerce_delivery_invalid")
        stream_id = f"gameplay:inventory:{seller_actor_ref}"
        if self._store.get_stream_head(stream_id) != expected_revision:
            raise InventoryRuntimeError("revision_conflict")
        event_type = {
            "delivered": "gameplay.inventory.delivery_committed",
            "rejected": "gameplay.inventory.delivery_rejected",
            "cancelled": "gameplay.inventory.delivery_cancelled",
        }[status]
        return OwnerAuthorizedFragment(
            fragment_id=f"fragment:inventory:delivery:{seller_actor_ref}:{delivery_ref}",
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref="inventory:commerce-delivery",
            expected_revisions={stream_id: expected_revision},
            pinned_revisions={f"inventory:{seller_actor_ref}": expected_revision},
            event_specs={
                stream_id: (
                    (
                        event_type,
                        {
                            "delivery_ref": delivery_ref,
                            "commitment_ref": commitment_ref,
                            "actor_ref": seller_actor_ref,
                            "delivered_quantity": delivered_quantity,
                            "quality_evidence_ref": quality_evidence_ref,
                            "delivery_window_ref": delivery_window_ref,
                            "reason": reason,
                            "policy_revision": policy_revision,
                        },
                    ),
                )
            },
        )

    def create_container(self, *, command_id: str, actor_ref: str, spec: ContainerSpec, idempotency_key: str, causation_id: str, correlation_id: str) -> AppendBatchResult:
        projection = self._projector.rebuild(actor_ref, self._store.read_events())
        if not spec.container_id or spec.container_id in projection.containers:
            raise InventoryRuntimeError("inventory_container_invalid")
        if (
            min(spec.capacity_weight, spec.capacity_volume, spec.capacity_slots) < 0
            or spec.content_weight_propagation not in {"include_contents", "exclude_contents"}
            or not isinstance(spec.allows_living_items, bool)
        ):
            raise InventoryRuntimeError("inventory_container_invalid")
        return self._append(
            command_id,
            actor_ref,
            [
                (
                    "gameplay.inventory.container_created",
                    {
                        "container_id": spec.container_id,
                        "capacity_weight": spec.capacity_weight,
                        "capacity_volume": spec.capacity_volume,
                        "capacity_slots": spec.capacity_slots,
                        "sealed": spec.sealed,
                        "carrier_item_id": spec.carrier_item_id,
                        "content_weight_propagation": spec.content_weight_propagation,
                        "allows_living_items": spec.allows_living_items,
                    },
                )
            ],
            idempotency_key,
            causation_id,
            correlation_id,
        )

    def instantiate(self, *, command_id: str, actor_ref: str, item_id: str, definition_id: str, quantity: int, container_id: str, idempotency_key: str, causation_id: str, correlation_id: str) -> AppendBatchResult:
        self._registry.item(definition_id)
        projection = self._projector.rebuild(actor_ref, self._store.read_events())
        if container_id not in projection.containers:
            raise InventoryRuntimeError("inventory_container_unknown")
        if projection.containers[container_id].sealed:
            raise InventoryRuntimeError("inventory_access_denied")
        if projection.containers[container_id].carrier_item_id:
            raise InventoryRuntimeError("inventory_container_access_requires_equipment")
        if not item_id or quantity <= 0 or item_id in projection.items:
            raise InventoryRuntimeError("inventory_item_invalid")
        item = InventoryItem(item_id, definition_id, quantity, "pending")
        self._require_capacity(projection, container_id, item)
        return self._append(command_id, actor_ref, [("gameplay.inventory.item_instantiated", {"item_id": item_id, "definition_id": definition_id, "quantity": quantity}), ("gameplay.inventory.item_moved", {"item_id": item_id, "from_container_id": "inventory:unplaced", "to_container_id": container_id})], idempotency_key, causation_id, correlation_id)

    def move(self, *, command_id: str, actor_ref: str, item_id: str, from_container_id: str, to_container_id: str, idempotency_key: str, causation_id: str, correlation_id: str) -> AppendBatchResult:
        projection = self._projector.rebuild(actor_ref, self._store.read_events())
        item = projection.items.get(item_id)
        target = projection.containers.get(to_container_id)
        if item is None or projection.locations.get(item_id) != from_container_id:
            raise InventoryRuntimeError("inventory_move_source_invalid")
        if target is None:
            raise InventoryRuntimeError("inventory_container_unknown")
        if target.sealed:
            raise InventoryRuntimeError("inventory_access_denied")
        source = projection.containers.get(from_container_id)
        if target.carrier_item_id or (source is not None and source.carrier_item_id):
            raise InventoryRuntimeError("inventory_container_access_requires_equipment")
        self._require_capacity(projection, to_container_id, item, excluding_item_id=item_id)
        return self._append(command_id, actor_ref, [("gameplay.inventory.item_moved", {"item_id": item_id, "from_container_id": from_container_id, "to_container_id": to_container_id})], idempotency_key, causation_id, correlation_id)

    def reserve_item(
        self,
        *,
        command_id: str,
        actor_ref: str,
        item_id: str,
        reservation_ref: str,
        quantity: int,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        serialized = self._serialize_events(
            command_id,
            actor_ref,
            [("gameplay.inventory.reservation_created", {"item_id": item_id, "reservation_ref": reservation_ref, "quantity": quantity})],
            causation_id,
            correlation_id,
        )
        key = f"{actor_ref}:{idempotency_key}"
        existing_record = self._store.get_idempotency_record(self._PRINCIPAL, key)
        if existing_record is not None:
            if existing_record.payload_digest != _digest(serialized):
                raise InventoryRuntimeError("inventory_idempotency_key_reused")
            result = self._store.get_by_idempotency(self._PRINCIPAL, key)
            assert result is not None
            return result.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
        projection = self._projector.rebuild(actor_ref, self._store.read_events())
        item = projection.items.get(item_id)
        location = projection.locations.get(item_id, "")
        if not item_id or not reservation_ref or quantity <= 0:
            raise InventoryRuntimeError("inventory_reservation_invalid")
        if item is None or not location.startswith("container:"):
            raise InventoryRuntimeError("inventory_reservation_source_invalid")
        if reservation_ref in projection.reservations:
            raise InventoryRuntimeError("inventory_reservation_duplicate")
        if item.remaining_quantity < quantity:
            raise InventoryRuntimeError("inventory_reservation_insufficient")
        return self._store.append_batch(
            {
                "transaction_id": f"tx:{command_id}",
                "command_id": command_id,
                "expected_stream_revisions": {f"gameplay:inventory:{actor_ref}": self._store.get_stream_head(f"gameplay:inventory:{actor_ref}")},
                "pinned_revisions": {"inventory": self._store.get_stream_head(f"gameplay:inventory:{actor_ref}")},
                "events": serialized,
                "idempotency_record": {"principal_ref": self._PRINCIPAL, "idempotency_key": key, "payload_digest": _digest(serialized)},
                "outbox_entries": [],
                "result_digest": _digest(serialized),
                "projection_refresh_hints": [],
            }
        )

    def reserve_commerce_capacity(
        self,
        *,
        command_id: str,
        actor_ref: str,
        capacity_reservation_ref: str,
        available_quantity: int,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        """Record a narrow Inventory/Production-owned capacity reservation."""
        projection = self._projector.rebuild(actor_ref, self._store.read_events())
        if (
            not capacity_reservation_ref.startswith("capacity:")
            or available_quantity <= 0
            or capacity_reservation_ref in projection.capacity_reservations
        ):
            raise InventoryRuntimeError("inventory_capacity_reservation_invalid")
        return self._append(
            command_id,
            actor_ref,
            [
                (
                    "gameplay.inventory.commerce_capacity_reserved",
                    {
                        "capacity_reservation_ref": capacity_reservation_ref,
                        "available_quantity": available_quantity,
                    },
                )
            ],
            idempotency_key,
            causation_id,
            correlation_id,
        )

    def consume_reservation(
        self,
        *,
        command_id: str,
        actor_ref: str,
        reservation_ref: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        serialized = self._serialize_events(
            command_id,
            actor_ref,
            [("gameplay.inventory.reservation_consumed", {"reservation_ref": reservation_ref})],
            causation_id,
            correlation_id,
        )
        key = f"{actor_ref}:{idempotency_key}"
        existing_record = self._store.get_idempotency_record(self._PRINCIPAL, key)
        if existing_record is not None:
            if existing_record.payload_digest != _digest(serialized):
                raise InventoryRuntimeError("inventory_idempotency_key_reused")
            result = self._store.get_by_idempotency(self._PRINCIPAL, key)
            assert result is not None
            return result.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
        projection = self._projector.rebuild(actor_ref, self._store.read_events())
        if reservation_ref not in projection.reservations:
            raise InventoryRuntimeError("inventory_reservation_unknown")
        return self._store.append_batch(
            {
                "transaction_id": f"tx:{command_id}",
                "command_id": command_id,
                "expected_stream_revisions": {f"gameplay:inventory:{actor_ref}": self._store.get_stream_head(f"gameplay:inventory:{actor_ref}")},
                "pinned_revisions": {"inventory": self._store.get_stream_head(f"gameplay:inventory:{actor_ref}")},
                "events": serialized,
                "idempotency_record": {"principal_ref": self._PRINCIPAL, "idempotency_key": key, "payload_digest": _digest(serialized)},
                "outbox_entries": [],
                "result_digest": _digest(serialized),
                "projection_refresh_hints": [],
            }
        )

    def release_reservation(
        self,
        *,
        command_id: str,
        actor_ref: str,
        reservation_ref: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        serialized = self._serialize_events(
            command_id,
            actor_ref,
            [("gameplay.inventory.reservation_released", {"reservation_ref": reservation_ref})],
            causation_id,
            correlation_id,
        )
        key = f"{actor_ref}:{idempotency_key}"
        existing_record = self._store.get_idempotency_record(self._PRINCIPAL, key)
        if existing_record is not None:
            if existing_record.payload_digest != _digest(serialized):
                raise InventoryRuntimeError("inventory_idempotency_key_reused")
            result = self._store.get_by_idempotency(self._PRINCIPAL, key)
            assert result is not None
            return result.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
        projection = self._projector.rebuild(actor_ref, self._store.read_events())
        if reservation_ref not in projection.reservations:
            raise InventoryRuntimeError("inventory_reservation_unknown")
        return self._store.append_batch(
            {
                "transaction_id": f"tx:{command_id}",
                "command_id": command_id,
                "expected_stream_revisions": {f"gameplay:inventory:{actor_ref}": self._store.get_stream_head(f"gameplay:inventory:{actor_ref}")},
                "pinned_revisions": {"inventory": self._store.get_stream_head(f"gameplay:inventory:{actor_ref}")},
                "events": serialized,
                "idempotency_record": {"principal_ref": self._PRINCIPAL, "idempotency_key": key, "payload_digest": _digest(serialized)},
                "outbox_entries": [],
                "result_digest": _digest(serialized),
                "projection_refresh_hints": [],
            }
        )

    def record_output_receipt(
        self,
        *,
        command_id: str,
        actor_ref: str,
        source_ref: str,
        item_ref: str,
        item_id: str,
        definition_id: str,
        container_id: str,
        quantity: int,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        """Record a production output at the inventory owner boundary.

        The recipe/production owner supplies only a typed output reference; this
        method owns the inventory receipt event and keeps custody settlement in
        the existing inventory event stream.
        """
        if not source_ref or not item_ref or not item_id or not definition_id or not container_id or quantity <= 0:
            raise InventoryRuntimeError("inventory_output_invalid")
        self._registry.item(definition_id)
        projection = self._projector.rebuild(actor_ref, self._store.read_events())
        if container_id not in projection.containers:
            raise InventoryRuntimeError("inventory_container_unknown")
        if projection.containers[container_id].sealed:
            raise InventoryRuntimeError("inventory_access_denied")
        if item_id in projection.items:
            raise InventoryRuntimeError("inventory_output_invalid")
        self._require_capacity(projection, container_id, InventoryItem(item_id, definition_id, quantity, "pending"))
        return self._append(
            command_id,
            actor_ref,
            [
                (
                    "gameplay.inventory.output_received",
                    {
                        "source_ref": source_ref,
                        "item_ref": item_ref,
                        "item_id": item_id,
                        "definition_id": definition_id,
                        "container_id": container_id,
                        "quantity": quantity,
                    },
                )
            ],
            idempotency_key,
            causation_id,
            correlation_id,
        )

    def _require_capacity(self, projection: InventoryProjection, container_id: str, candidate: InventoryItem, *, excluding_item_id: str | None = None) -> None:
        container = projection.containers[container_id]
        candidate_definition = self._registry.item(candidate.definition_id)
        if candidate_definition.is_living and not container.allows_living_items:
            raise InventoryRuntimeError("inventory_living_item_rejected")
        entries = [item for item_id, item in projection.items.items() if projection.locations.get(item_id) == container_id and item_id != excluding_item_id]
        weight = sum(self._registry.item(item.definition_id).unit_weight * item.quantity for item in entries) + candidate_definition.unit_weight * candidate.quantity
        volume = sum(self._registry.item(item.definition_id).unit_volume * item.quantity for item in entries) + candidate_definition.unit_volume * candidate.quantity
        if len(entries) + 1 > container.capacity_slots or weight > container.capacity_weight or volume > container.capacity_volume:
            raise InventoryRuntimeError("inventory_capacity_exceeded")

    def _append(self, command_id: str, actor_ref: str, events: Sequence[tuple[str, Mapping[str, object]]], idempotency_key: str, causation_id: str, correlation_id: str) -> AppendBatchResult:
        stream_id = f"gameplay:inventory:{actor_ref}"
        transaction_id = f"tx:{command_id}"
        serialized = self._serialize_events(command_id, actor_ref, events, causation_id, correlation_id)
        return self._store.append_batch({"transaction_id": transaction_id, "command_id": command_id, "expected_stream_revisions": {stream_id: self._store.get_stream_head(stream_id)}, "pinned_revisions": {"inventory": self._store.get_stream_head(stream_id)}, "events": serialized, "idempotency_record": {"principal_ref": self._PRINCIPAL, "idempotency_key": f"{actor_ref}:{idempotency_key}", "payload_digest": _digest(serialized)}, "outbox_entries": [], "result_digest": _digest(serialized), "projection_refresh_hints": []})

    @staticmethod
    def _serialize_events(command_id: str, actor_ref: str, events: Sequence[tuple[str, Mapping[str, object]]], causation_id: str, correlation_id: str) -> list[dict[str, object]]:
        stream_id = f"gameplay:inventory:{actor_ref}"
        transaction_id = f"tx:{command_id}"
        return [
            {
                "event_id": f"evt:{command_id}:inventory:{index}",
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
                "payload": {"actor_ref": actor_ref, **payload},
            }
            for index, (event_type, payload) in enumerate(events, start=1)
        ]


def _text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise InventoryRuntimeError("inventory_event_payload_invalid")
    return value


def _nonnegative(payload: Mapping[str, object], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise InventoryRuntimeError("inventory_event_payload_invalid")
    return value


def _positive(payload: Mapping[str, object], key: str) -> int:
    value = _nonnegative(payload, key)
    if value == 0:
        raise InventoryRuntimeError("inventory_event_payload_invalid")
    return value


def _optional_text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key, "")
    if not isinstance(value, str):
        raise InventoryRuntimeError("inventory_event_payload_invalid")
    return value


def _content_weight_propagation(value: object) -> str:
    if value not in {"include_contents", "exclude_contents"}:
        raise InventoryRuntimeError("inventory_event_payload_invalid")
    return str(value)


def _bool_with_default(payload: Mapping[str, object], key: str, default: bool) -> bool:
    value = payload.get(key, default)
    if not isinstance(value, bool):
        raise InventoryRuntimeError("inventory_event_payload_invalid")
    return value


def _digest(value: object) -> str:
    def default(item: object) -> object:
        if isinstance(item, Mapping):
            return dict(item)
        if hasattr(item, "__dict__"):
            return item.__dict__
        raise TypeError(type(item).__name__)
    return sha256(json.dumps(value, default=default, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
