"""Minimal event-sourced item location and container-capacity authority."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Mapping, Sequence

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayEvent, GameplayFailure, OwnerAuthorizedFragment
from app.gameplay.shared_contracts import SettlementReceipt


class InventoryRuntimeError(ValueError):
    pass


_REINFORCED_MILL_FLOUR_PROVIDER = "organization:district-milling-cooperative"
_REINFORCED_MILL_FLOUR_PROVIDER_CONTAINER = "container:district-milling-cooperative:mill-output"
_REINFORCED_MILL_FLOUR_ITEM = "item:industrial-facilities:flour@1"
_REINFORCED_MILL_FLOUR_RECIPE = "recipe:industrial-facilities:mill-flour@1"
_REINFORCED_MILL_FLOUR_OUTPUT_EVENT = "gameplay.inventory.mill_flour_output_received@1"
_REINFORCED_MILL_FLOUR_SOURCE_EVENT = (
    "gameplay.construction_production.mill_flour_output_certified@1"
)
_GRAIN_HARVEST_PROVIDER = "organization:district-milling-cooperative"
_GRAIN_HARVEST_CONTAINER = "container:district-milling-cooperative:grain-intake"
_GRAIN_HARVEST_ITEM = "grain:wheat@1"
_GRAIN_HARVEST_SPECIES = "grain:wheat"
_GRAIN_HARVEST_EVENT = "gameplay.inventory.grain_harvest_received@1"
_GRAIN_HARVEST_SOURCE_EVENT = "gameplay.ecology.grain_harvested"
_HARVEST_TO_CUSTODY_EVENT = "gameplay.inventory.harvest_received@1"


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
class GrainHarvestCustodyView:
    holder_ref: str
    rows: tuple[Mapping[str, object], ...]
    source_revision_vector: Mapping[str, int]
    projection_hash: str


@dataclass(frozen=True)
class HarvestToCustodyView:
    rows: tuple[Mapping[str, object], ...]
    source_revision_vector: Mapping[str, int]
    projection_hash: str


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
        ordered_events = sorted(events, key=lambda item: (item.global_sequence, item.event_id))
        events_by_id = {event.event_id: event for event in ordered_events}
        for event in ordered_events:
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
            elif event.event_type == _REINFORCED_MILL_FLOUR_OUTPUT_EVENT:
                if (
                    _text(payload, "provider_ref") != _REINFORCED_MILL_FLOUR_PROVIDER
                    or _text(payload, "item_ref") != _REINFORCED_MILL_FLOUR_ITEM
                    or _text(payload, "definition_id") != _REINFORCED_MILL_FLOUR_ITEM
                    or _positive(payload, "quantity") != 10
                    or _text(payload, "container_id") != _REINFORCED_MILL_FLOUR_PROVIDER_CONTAINER
                    or _text(payload, "recipe_ref") != _REINFORCED_MILL_FLOUR_RECIPE
                    or _text(payload, "source_certification_event_id") == ""
                ):
                    raise InventoryRuntimeError("inventory_output_invalid")
                item_id = _text(payload, "item_id")
                container_id = _text(payload, "container_id")
                if item_id in items or container_id not in containers:
                    raise InventoryRuntimeError("inventory_output_invalid")
                self._registry.item(_REINFORCED_MILL_FLOUR_ITEM)
                items[item_id] = InventoryItem(
                    item_id,
                    _REINFORCED_MILL_FLOUR_ITEM,
                    10,
                    event.event_id,
                )
                locations[item_id] = container_id
            elif event.event_type == _HARVEST_TO_CUSTODY_EVENT:
                source_event = events_by_id.get(payload.get("source_harvest_event_id"))
                if (
                    event.visibility_policy != "project"
                    or _text(payload, "actor_ref") == ""
                    or _text(payload, "holder_ref") != _text(payload, "actor_ref")
                    or _text(payload, "item_ref") != _text(payload, "definition_id")
                    or _positive(payload, "quantity") <= 0
                    or _text(payload, "container_id") == ""
                    or _text(payload, "source_harvest_event_id") == ""
                    or source_event is None
                    or source_event.event_type != _GRAIN_HARVEST_SOURCE_EVENT
                    or source_event.visibility_policy != "project"
                    or source_event.stream_revision != payload.get("source_harvest_revision")
                    or source_event.payload.get("project_ref") != payload.get("project_ref")
                    or source_event.payload.get("plot_ref") != payload.get("plot_ref")
                    or f"definition:{source_event.payload.get('species')}@1" != payload.get("crop_definition_ref")
                    or source_event.payload.get("item_definition") != payload.get("item_ref")
                    or source_event.payload.get("yield_quantity") != payload.get("quantity")
                ):
                    raise InventoryRuntimeError("harvest_to_custody_replay_invalid")
                item_id = _text(payload, "item_id")
                container_id = _text(payload, "container_id")
                if item_id in items or container_id not in containers:
                    raise InventoryRuntimeError("harvest_to_custody_event_invalid")
                self._registry.item(_text(payload, "item_ref"))
                items[item_id] = InventoryItem(
                    item_id,
                    _text(payload, "item_ref"),
                    _positive(payload, "quantity"),
                    event.event_id,
                )
                locations[item_id] = container_id
            elif event.event_type == _GRAIN_HARVEST_EVENT:
                source_event = events_by_id.get(payload.get("source_harvest_event_id"))
                if (
                    event.visibility_policy != "project"
                    or _text(payload, "actor_ref") != _GRAIN_HARVEST_PROVIDER
                    or _text(payload, "holder_ref") != _GRAIN_HARVEST_PROVIDER
                    or _text(payload, "item_ref") != _GRAIN_HARVEST_ITEM
                    or _text(payload, "definition_id") != _GRAIN_HARVEST_ITEM
                    or _positive(payload, "quantity") != 10
                    or _text(payload, "container_id") != _GRAIN_HARVEST_CONTAINER
                    or _text(payload, "source_harvest_event_id") == ""
                    or source_event is None
                    or source_event.event_type != _GRAIN_HARVEST_SOURCE_EVENT
                    or source_event.visibility_policy != "project"
                    or source_event.stream_revision != payload.get("source_harvest_revision")
                    or source_event.payload.get("project_ref") != payload.get("project_ref")
                    or source_event.payload.get("plot_ref") != payload.get("plot_ref")
                    or source_event.payload.get("item_definition") != _GRAIN_HARVEST_ITEM
                    or source_event.payload.get("yield_quantity") != 10
                ):
                    raise InventoryRuntimeError("inventory_grain_harvest_replay_invalid")
                item_id = _text(payload, "item_id")
                container_id = _text(payload, "container_id")
                if item_id in items or container_id not in containers:
                    raise InventoryRuntimeError("inventory_grain_harvest_event_invalid")
                self._registry.item(_GRAIN_HARVEST_ITEM)
                items[item_id] = InventoryItem(item_id, _GRAIN_HARVEST_ITEM, 10, event.event_id)
                locations[item_id] = container_id
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

    def __init__(
        self,
        *,
        store: GameplayEventStore,
        registry: InventoryDefinitionRegistry,
        package_registry: object | None = None,
    ) -> None:
        self._store = store
        self._registry = registry
        self._projector = InventoryProjector(registry)
        self._package_registry = package_registry

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

    def record_reinforced_mill_flour_output_receipt(
        self,
        *,
        certification_event_id: str,
        expected_certification_revision: int,
        expected_inventory_stream_revision: int,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        provider_ref = _REINFORCED_MILL_FLOUR_PROVIDER
        provider_stream = f"gameplay:inventory:{provider_ref}"
        if (
            not certification_event_id
            or expected_certification_revision < 1
            or expected_inventory_stream_revision < 0
            or not command_id
            or not idempotency_key
            or not causation_id
            or not correlation_id
        ):
            return self._rejected_append(
                command_id,
                "inventory_mill_flour_output_reference_invalid",
            )
        request_digest = _digest(
            {
                "certification_event_id": certification_event_id,
                "expected_certification_revision": expected_certification_revision,
                "expected_inventory_stream_revision": expected_inventory_stream_revision,
                "command_id": command_id,
                "idempotency_key": idempotency_key,
                "causation_id": causation_id,
                "correlation_id": correlation_id,
            }
        )
        key = f"{provider_ref}:{idempotency_key}"
        existing = self._store.get_idempotency_record(self._PRINCIPAL, key)
        if existing is not None:
            if existing.payload_digest != request_digest:
                return self._rejected_append(command_id, "idempotency_key_reused")
            replay = self._store.get_by_idempotency(self._PRINCIPAL, key)
            if replay is None:
                return self._rejected_append(
                    command_id,
                    "inventory_mill_flour_output_receipt_missing",
                )
            return replay.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
        try:
            certification = self._store.get_event(certification_event_id)
        except KeyError:
            return self._rejected_append(
                command_id,
                "inventory_mill_flour_output_source_missing",
            )
        if self._store.get_stream_head(provider_stream) != expected_inventory_stream_revision:
            return self._rejected_append(command_id, "revision_conflict")
        if not self._is_valid_reinforced_mill_flour_certification(
            certification_event=certification,
            expected_certification_revision=expected_certification_revision,
        ):
            return self._rejected_append(
                command_id,
                "inventory_mill_flour_output_source_invalid",
            )
        projection = self._projector.rebuild(provider_ref, self._store.read_events())
        container = projection.containers.get(_REINFORCED_MILL_FLOUR_PROVIDER_CONTAINER)
        if container is None or container.sealed or container.carrier_item_id:
            return self._rejected_append(
                command_id,
                "inventory_mill_flour_output_source_invalid",
            )
        item_id = self._reinforced_mill_flour_item_id(certification_event_id)
        if item_id in projection.items or any(
            event.event_type == _REINFORCED_MILL_FLOUR_OUTPUT_EVENT
            and event.payload.get("source_certification_event_id") == certification_event_id
            and event.payload.get("actor_ref") == provider_ref
            for event in self._store.read_stream(provider_stream)
        ):
            return self._rejected_append(
                command_id,
                "inventory_mill_flour_output_duplicate",
            )
        self._require_capacity(
            projection,
            _REINFORCED_MILL_FLOUR_PROVIDER_CONTAINER,
            InventoryItem(item_id, _REINFORCED_MILL_FLOUR_ITEM, 10, "pending"),
        )
        payload = {
            "actor_ref": provider_ref,
            "provider_ref": provider_ref,
            "project_ref": certification.payload["project_ref"],
            "facility_ref": certification.payload["facility_ref"],
            "run_ref": certification.payload["run_ref"],
            "recipe_ref": _REINFORCED_MILL_FLOUR_RECIPE,
            "item_ref": _REINFORCED_MILL_FLOUR_ITEM,
            "item_id": item_id,
            "definition_id": _REINFORCED_MILL_FLOUR_ITEM,
            "quantity": 10,
            "container_id": _REINFORCED_MILL_FLOUR_PROVIDER_CONTAINER,
            "source_certification_event_id": certification.event_id,
            "source_certification_revision": certification.stream_revision,
            "source_run_finished_event_id": certification.payload["source_run_finished_event_id"],
            "source_reinforcement_event_id": certification.payload["source_reinforcement_event_id"],
        }
        event = {
            "event_id": f"evt:{command_id}:inventory:1",
            "event_type": _REINFORCED_MILL_FLOUR_OUTPUT_EVENT,
            "schema_version": 1,
            "stream_id": provider_stream,
            "stream_revision": 0,
            "global_sequence": 0,
            "transaction_id": f"tx:{command_id}",
            "command_id": command_id,
            "causation_id": causation_id,
            "correlation_id": correlation_id,
            "visibility_policy": "project",
            "payload": payload,
        }
        return self._store.append_batch(
            {
                "transaction_id": f"tx:{command_id}",
                "command_id": command_id,
                "expected_stream_revisions": {
                    provider_stream: expected_inventory_stream_revision
                },
                "read_stream_revisions": {
                    certification.stream_id: expected_certification_revision
                },
                "pinned_revisions": {
                    "inventory": expected_inventory_stream_revision,
                    "construction_source": expected_certification_revision,
                },
                "events": [event],
                "idempotency_record": {
                    "principal_ref": self._PRINCIPAL,
                    "idempotency_key": key,
                    "payload_digest": request_digest,
                },
                "owner_fragments": [],
                "outbox_entries": [],
                "result_digest": _digest(event),
                "projection_refresh_hints": [],
            }
        )

    def record_grain_harvest_custody_receipt(
        self,
        *,
        harvest_event_id: str,
        expected_harvest_revision: int,
        expected_inventory_stream_revision: int,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        family_ref: str | None = None,
    ) -> AppendBatchResult:
        """Record exactly one fixed district grain-harvest custody lot."""
        provider_stream = f"gameplay:inventory:{_GRAIN_HARVEST_PROVIDER}"
        if (
            not harvest_event_id
            or expected_harvest_revision < 1
            or expected_inventory_stream_revision < 0
            or not command_id
            or not idempotency_key
            or not causation_id
            or not correlation_id
        ):
            return self._rejected_append(command_id, "inventory_grain_harvest_reference_invalid")
        request_digest = _digest(
            {
                "harvest_event_id": harvest_event_id,
                "expected_harvest_revision": expected_harvest_revision,
                "expected_inventory_stream_revision": expected_inventory_stream_revision,
                "command_id": command_id,
                "idempotency_key": idempotency_key,
                "causation_id": causation_id,
                "correlation_id": correlation_id,
            }
        )
        key = f"{_GRAIN_HARVEST_PROVIDER}:{idempotency_key}"
        existing = self._store.get_idempotency_record(self._PRINCIPAL, key)
        if existing is not None:
            if existing.payload_digest != request_digest:
                return self._rejected_append(command_id, "idempotency_key_reused")
            replay = self._store.get_by_idempotency(self._PRINCIPAL, key)
            if replay is None:
                return self._rejected_append(command_id, "inventory_grain_harvest_receipt_missing")
            return replay.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
        try:
            harvest = self._store.get_event(harvest_event_id)
        except KeyError:
            return self._rejected_append(command_id, "inventory_grain_harvest_source_missing")
        if (
            harvest.event_type != _GRAIN_HARVEST_SOURCE_EVENT
            or harvest.visibility_policy != "project"
            or harvest.stream_revision != expected_harvest_revision
            or self._store.get_stream_head(harvest.stream_id) != expected_harvest_revision
            or harvest.payload.get("species") != _GRAIN_HARVEST_SPECIES
            or harvest.payload.get("item_definition") != _GRAIN_HARVEST_ITEM
            or harvest.payload.get("yield_quantity") != 10
            or harvest.payload.get("terminal") != "v1_terminal_no_compensation"
            or not isinstance(harvest.payload.get("project_ref"), str)
            or not harvest.payload.get("project_ref")
            or not isinstance(harvest.payload.get("plot_ref"), str)
            or not harvest.payload.get("plot_ref")
        ):
            return self._rejected_append(command_id, "inventory_grain_harvest_source_invalid")
        if self._store.get_stream_head(provider_stream) != expected_inventory_stream_revision:
            return self._rejected_append(command_id, "revision_conflict")
        if idempotency_key != (
            f"inventory:grain-harvest-custody:{harvest.event_id}:"
            f"{harvest.stream_revision}:{expected_inventory_stream_revision}:v1"
        ) or causation_id != harvest.event_id:
            return self._rejected_append(command_id, "inventory_grain_harvest_idempotency_key_invalid")
        projection = self._projector.rebuild(_GRAIN_HARVEST_PROVIDER, self._store.read_events())
        container = projection.containers.get(_GRAIN_HARVEST_CONTAINER)
        if container is None or container.sealed or container.carrier_item_id:
            return self._rejected_append(command_id, "inventory_grain_harvest_container_unavailable")
        item_id = f"item:grain-harvest:{harvest.event_id}"
        if item_id in projection.items or any(
            event.event_type == _GRAIN_HARVEST_EVENT
            and event.payload.get("source_harvest_event_id") == harvest.event_id
            for event in self._store.read_stream(provider_stream)
        ):
            return self._rejected_append(command_id, "inventory_grain_harvest_duplicate")
        try:
            self._registry.item(_GRAIN_HARVEST_ITEM)
            self._require_capacity(
                projection,
                _GRAIN_HARVEST_CONTAINER,
                InventoryItem(item_id, _GRAIN_HARVEST_ITEM, 10, "pending"),
            )
        except InventoryRuntimeError as exc:
            return self._rejected_append(command_id, str(exc))
        event = {
            "event_id": f"evt:{command_id}:inventory:1",
            "event_type": _GRAIN_HARVEST_EVENT,
            "schema_version": 1,
            "stream_id": provider_stream,
            "stream_revision": 0,
            "global_sequence": 0,
            "transaction_id": f"tx:{command_id}",
            "command_id": command_id,
            "causation_id": causation_id,
            "correlation_id": correlation_id,
            "visibility_policy": "project",
            "payload": {
                "actor_ref": _GRAIN_HARVEST_PROVIDER,
                "holder_ref": _GRAIN_HARVEST_PROVIDER,
                "project_ref": harvest.payload["project_ref"],
                "plot_ref": harvest.payload["plot_ref"],
                "item_ref": _GRAIN_HARVEST_ITEM,
                "item_id": item_id,
                "definition_id": _GRAIN_HARVEST_ITEM,
                "quantity": 10,
                "container_id": _GRAIN_HARVEST_CONTAINER,
                "source_harvest_event_id": harvest.event_id,
                "source_harvest_revision": harvest.stream_revision,
                "policy_revision": "policy:inventory-grain-harvest-custody@1",
                "descriptor_ref": "descriptor:inventory-grain-harvest-custody@1",
                "descriptor_revision": "descriptor:inventory-grain-harvest-custody@1",
                "catalog_ref": "inf:inventory-grain-harvest-custody@1",
                "terminal": "v1_terminal_no_compensation",
                **({"family_ref": family_ref} if family_ref is not None else {}),
            },
        }
        return self._store.append_batch(
            {
                "transaction_id": f"tx:{command_id}",
                "command_id": command_id,
                "expected_stream_revisions": {provider_stream: expected_inventory_stream_revision},
                "read_stream_revisions": {harvest.stream_id: expected_harvest_revision},
                "pinned_revisions": {
                    "inventory": expected_inventory_stream_revision,
                    "harvest": expected_harvest_revision,
                },
                "events": [event],
                "idempotency_record": {
                    "principal_ref": self._PRINCIPAL,
                    "idempotency_key": key,
                    "payload_digest": request_digest,
                },
                "owner_fragments": [],
                "outbox_entries": [],
                "result_digest": _digest(event),
                "projection_refresh_hints": [],
            }
        )

    def settle_harvest_to_custody(self, *, intent: object) -> AppendBatchResult:
        """Settle one admitted harvest content instance without caller coordinates."""
        from app.gameplay.closed_generic_gameplay_families import HarvestToCustodyIntent

        try:
            typed_intent = intent if isinstance(intent, HarvestToCustodyIntent) else HarvestToCustodyIntent.model_validate(intent)
        except Exception:
            return self._rejected_append(str(getattr(intent, "command_id", "harvest-to-custody")), "harvest_to_custody_intent_invalid")
        registry = self._package_registry
        active = getattr(registry, "active_patch_set", None) if registry is not None else None
        if active is None:
            return self._rejected_append(typed_intent.command_id, "harvest_to_custody_package_inactive")
        try:
            manifests = registry.active_manifests(active.active_patch_set_revision)
            harvest = self._store.get_event(typed_intent.harvest_event_id)
        except Exception:
            return self._rejected_append(typed_intent.command_id, "harvest_to_custody_source_missing")
        if (
            harvest.event_type != _GRAIN_HARVEST_SOURCE_EVENT
            or harvest.visibility_policy != "project"
            or harvest.stream_revision != typed_intent.expected_harvest_revision
            or self._store.get_stream_head(harvest.stream_id) != typed_intent.expected_harvest_revision
            or not isinstance(harvest.payload.get("project_ref"), str)
            or not harvest.payload.get("project_ref")
            or not isinstance(harvest.payload.get("plot_ref"), str)
            or not harvest.payload.get("plot_ref")
            or not isinstance(harvest.payload.get("species"), str)
            or not isinstance(harvest.payload.get("item_definition"), str)
            or not isinstance(harvest.payload.get("yield_quantity"), int)
            or isinstance(harvest.payload.get("yield_quantity"), bool)
            or harvest.payload.get("yield_quantity", 0) <= 0
            or harvest.payload.get("terminal") != "v1_terminal_no_compensation"
        ):
            return self._rejected_append(typed_intent.command_id, "harvest_to_custody_source_invalid")

        from app.gameplay.closed_generic_gameplay_families import HarvestToCustodyContent

        candidates: list[tuple[object, object, object, HarvestToCustodyContent]] = []
        for manifest in manifests:
            extension = manifest.platform_extension
            if extension is None:
                continue
            declarations = {item.declaration_ref: item for item in extension.outcome_declarations}
            for request in extension.capability_binding_requests:
                if request.capability_ref != "capability:harvest-to-custody@1":
                    continue
                declaration = declarations.get(request.declaration_ref)
                bindings = tuple(
                    binding
                    for binding in active.capability_bindings
                    if binding.binding_ref == request.binding_ref
                    and binding.package_revision == manifest.patch_revision_id
                    and binding.descriptor_ref == "descriptor:inventory-harvest-to-custody@1"
                    and binding.active_patch_set_revision == active.active_patch_set_revision
                )
                if declaration is None or len(bindings) != 1:
                    continue
                definitions = tuple(
                    definition
                    for definition in extension.package_definitions
                    if definition.definition_ref in declaration.definition_refs
                )
                if len(definitions) != 1:
                    continue
                try:
                    content = HarvestToCustodyContent.model_validate(definitions[0].typed_content)
                except Exception:
                    continue
                if (
                    content.crop_definition_ref == f"definition:{harvest.payload['species']}@1"
                    and content.item_definition_ref == f"item:{harvest.payload['item_definition']}"
                ):
                    candidates.append((manifest, declaration, bindings[0], content))
        if not candidates:
            return self._rejected_append(typed_intent.command_id, "harvest_to_custody_content_unknown")
        if len(candidates) != 1:
            return self._rejected_append(typed_intent.command_id, "harvest_to_custody_binding_ambiguous")
        manifest, declaration, binding, content = candidates[0]
        item_ref = content.item_definition_ref.removeprefix("item:")
        try:
            holder_ref = _resolve_harvest_binding(content.holder_binding_ref, prefix="binding:holder:")
            container_id = _resolve_harvest_binding(content.container_binding_ref, prefix="binding:container:")
        except InventoryRuntimeError as exc:
            return self._rejected_append(typed_intent.command_id, str(exc))
        provider_stream = f"gameplay:inventory:{holder_ref}"
        quantity = int(harvest.payload["yield_quantity"])
        item_id = f"item:harvest:{harvest.event_id}"
        key = (
            f"inventory:harvest-to-custody:{binding.binding_ref}:{manifest.patch_revision_id}:"
            f"{harvest.event_id}:{harvest.stream_revision}:{typed_intent.expected_inventory_stream_revision}:v1"
        )
        request_digest = _digest(
            {
                "harvest_event_id": typed_intent.harvest_event_id,
                "expected_harvest_revision": typed_intent.expected_harvest_revision,
                "expected_inventory_stream_revision": typed_intent.expected_inventory_stream_revision,
                "command_id": typed_intent.command_id,
                "idempotency_key": key,
                "causation_id": typed_intent.harvest_event_id,
                "correlation_id": typed_intent.correlation_id,
            }
        )
        existing = self._store.get_idempotency_record(self._PRINCIPAL, f"{holder_ref}:{key}")
        if existing is not None:
            if existing.payload_digest != request_digest:
                return self._rejected_append(typed_intent.command_id, "idempotency_key_reused")
            replay = self._store.get_by_idempotency(self._PRINCIPAL, f"{holder_ref}:{key}")
            if replay is None:
                return self._rejected_append(typed_intent.command_id, "harvest_to_custody_receipt_missing")
            return replay.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
        if self._store.get_stream_head(provider_stream) != typed_intent.expected_inventory_stream_revision:
            return self._rejected_append(typed_intent.command_id, "revision_conflict")
        projection = self._projector.rebuild(holder_ref, self._store.read_events())
        container = projection.containers.get(container_id)
        if container is None or container.sealed or container.carrier_item_id:
            return self._rejected_append(typed_intent.command_id, "harvest_to_custody_container_unavailable")
        if item_id in projection.items or any(
            event.event_type == _HARVEST_TO_CUSTODY_EVENT
            and event.payload.get("source_harvest_event_id") == harvest.event_id
            for event in self._store.read_stream(provider_stream)
        ):
            return self._rejected_append(typed_intent.command_id, "harvest_to_custody_duplicate")
        try:
            self._registry.item(item_ref)
            self._require_capacity(
                projection,
                container_id,
                InventoryItem(item_id, item_ref, quantity, "pending"),
            )
        except InventoryRuntimeError as exc:
            return self._rejected_append(typed_intent.command_id, str(exc))
        event = {
            "event_id": f"evt:{typed_intent.command_id}:inventory:1",
            "event_type": _HARVEST_TO_CUSTODY_EVENT,
            "schema_version": 1,
            "stream_id": provider_stream,
            "stream_revision": 0,
            "global_sequence": 0,
            "transaction_id": f"tx:{typed_intent.command_id}",
            "command_id": typed_intent.command_id,
            "causation_id": typed_intent.harvest_event_id,
            "correlation_id": typed_intent.correlation_id,
            "visibility_policy": "project",
            "payload": {
                "actor_ref": holder_ref,
                "holder_ref": holder_ref,
                "project_ref": harvest.payload["project_ref"],
                "plot_ref": harvest.payload["plot_ref"],
                "crop_definition_ref": content.crop_definition_ref,
                "item_ref": item_ref,
                "item_id": item_id,
                "definition_id": item_ref,
                "quantity": quantity,
                "container_id": container_id,
                "source_harvest_event_id": harvest.event_id,
                "source_harvest_revision": harvest.stream_revision,
                "policy_revision": content.policy_revision_ref,
                "descriptor_ref": "descriptor:inventory-harvest-to-custody@1",
                "descriptor_revision": "descriptor:inventory-harvest-to-custody@1",
                "catalog_ref": "inf:inventory-harvest-to-custody@1",
                "package_revision": manifest.patch_revision_id,
                "declaration_ref": declaration.declaration_ref,
                "binding_ref": binding.binding_ref,
                "active_patch_set_revision": active.active_patch_set_revision,
                "terminal": "v1_terminal_no_compensation",
                "family_ref": "harvest_to_custody@1",
            },
        }
        return self._store.append_batch(
            {
                "transaction_id": f"tx:{typed_intent.command_id}",
                "command_id": typed_intent.command_id,
                "expected_stream_revisions": {provider_stream: typed_intent.expected_inventory_stream_revision},
                "read_stream_revisions": {harvest.stream_id: typed_intent.expected_harvest_revision},
                "pinned_revisions": {
                    "inventory": typed_intent.expected_inventory_stream_revision,
                    "harvest": typed_intent.expected_harvest_revision,
                },
                "events": [event],
                "idempotency_record": {
                    "principal_ref": self._PRINCIPAL,
                    "idempotency_key": f"{holder_ref}:{key}",
                    "payload_digest": request_digest,
                },
                "owner_fragments": [],
                "outbox_entries": [],
                "result_digest": _digest(event),
                "projection_refresh_hints": [],
            }
        )

    def grain_harvest_custody_receipt_for(
        self, *, result: AppendBatchResult, scope: str
    ) -> SettlementReceipt:
        if scope != "project":
            raise InventoryRuntimeError("inventory_grain_harvest_receipt_scope_denied")
        if not result.committed or len(result.committed_event_ids) != 1:
            raise InventoryRuntimeError("inventory_grain_harvest_receipt_missing")
        return SettlementReceipt.from_append_result(
            result=result,
            audit_refs=(f"inventory_grain_harvest:{result.transaction_id}",),
        )

    def grain_harvest_custody_view_for(
        self, *, checkpoint_at: int | None = None
    ) -> GrainHarvestCustodyView:
        if checkpoint_at is not None and checkpoint_at < 0:
            raise InventoryRuntimeError("inventory_grain_harvest_checkpoint_invalid")
        events = sorted(self._store.read_events(), key=lambda event: (event.global_sequence, event.event_id))
        max_sequence = max((event.global_sequence for event in events), default=0)
        if checkpoint_at is not None and checkpoint_at > max_sequence:
            raise InventoryRuntimeError("inventory_grain_harvest_checkpoint_invalid")
        events_by_id = {event.event_id: event for event in events}
        ordered = events if checkpoint_at is None else [
            *[event for event in events if event.global_sequence <= checkpoint_at],
            *[event for event in events if event.global_sequence > checkpoint_at],
        ]
        rows: list[Mapping[str, object]] = []
        for event in ordered:
            if event.event_type != _GRAIN_HARVEST_EVENT:
                continue
            source = events_by_id.get(event.payload.get("source_harvest_event_id"))
            try:
                valid = (
                    event.visibility_policy == "project"
                    and event.stream_id == f"gameplay:inventory:{_GRAIN_HARVEST_PROVIDER}"
                    and _text(event.payload, "actor_ref") == _GRAIN_HARVEST_PROVIDER
                    and _text(event.payload, "holder_ref") == _GRAIN_HARVEST_PROVIDER
                    and _text(event.payload, "container_id") == _GRAIN_HARVEST_CONTAINER
                    and _text(event.payload, "item_ref") == _GRAIN_HARVEST_ITEM
                    and _text(event.payload, "definition_id") == _GRAIN_HARVEST_ITEM
                    and _positive(event.payload, "quantity") == 10
                    and source is not None
                    and source.event_type == _GRAIN_HARVEST_SOURCE_EVENT
                    and source.visibility_policy == "project"
                    and source.stream_revision == event.payload.get("source_harvest_revision")
                    and source.payload.get("project_ref") == event.payload.get("project_ref")
                    and source.payload.get("plot_ref") == event.payload.get("plot_ref")
                    and source.payload.get("item_definition") == _GRAIN_HARVEST_ITEM
                    and source.payload.get("yield_quantity") == 10
                )
            except InventoryRuntimeError:
                valid = False
            if not valid:
                raise InventoryRuntimeError("inventory_grain_harvest_replay_invalid")
            rows.append(dict(event.payload))
        source_revision_vector = {
            f"gameplay:inventory:{_GRAIN_HARVEST_PROVIDER}": self._store.get_stream_head(
                f"gameplay:inventory:{_GRAIN_HARVEST_PROVIDER}"
            )
        }
        for row in rows:
            source_ref = row.get("source_harvest_event_id")
            source = events_by_id.get(source_ref)
            if source is not None:
                source_revision_vector[source.stream_id] = max(
                    source_revision_vector.get(source.stream_id, 0), source.stream_revision
                )
        payload = {
            "holder_ref": _GRAIN_HARVEST_PROVIDER,
            "rows": rows,
            "source_revision_vector": source_revision_vector,
        }
        return GrainHarvestCustodyView(
            holder_ref=_GRAIN_HARVEST_PROVIDER,
            rows=tuple(rows),
            source_revision_vector=source_revision_vector,
            projection_hash="sha256:" + sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
            ).hexdigest(),
        )

    def harvest_to_custody_view_for(
        self, *, checkpoint_at: int | None = None
    ) -> HarvestToCustodyView:
        if checkpoint_at is not None and checkpoint_at < 0:
            raise InventoryRuntimeError("harvest_to_custody_checkpoint_invalid")
        events = sorted(self._store.read_events(), key=lambda event: (event.global_sequence, event.event_id))
        max_sequence = max((event.global_sequence for event in events), default=0)
        if checkpoint_at is not None and checkpoint_at > max_sequence:
            raise InventoryRuntimeError("harvest_to_custody_checkpoint_invalid")
        events_by_id = {event.event_id: event for event in events}
        rows: list[Mapping[str, object]] = []
        source_revision_vector: dict[str, int] = {}
        for event in events:
            if event.event_type != _HARVEST_TO_CUSTODY_EVENT:
                continue
            source = events_by_id.get(event.payload.get("source_harvest_event_id"))
            payload = event.payload
            if (
                event.visibility_policy != "project"
                or not isinstance(payload.get("holder_ref"), str)
                or not payload["holder_ref"]
                or payload.get("actor_ref") != payload.get("holder_ref")
                or not isinstance(payload.get("item_ref"), str)
                or payload.get("item_ref") != payload.get("definition_id")
                or not isinstance(payload.get("quantity"), int)
                or isinstance(payload.get("quantity"), bool)
                or payload["quantity"] <= 0
                or not isinstance(payload.get("container_id"), str)
                or not payload["container_id"]
                or source is None
                or source.event_type != _GRAIN_HARVEST_SOURCE_EVENT
                or source.visibility_policy != "project"
                or source.stream_revision != payload.get("source_harvest_revision")
                or source.payload.get("project_ref") != payload.get("project_ref")
                or source.payload.get("plot_ref") != payload.get("plot_ref")
                or source.payload.get("item_definition") != payload.get("item_ref")
                or source.payload.get("yield_quantity") != payload.get("quantity")
                or f"definition:{source.payload.get('species')}@1" != payload.get("crop_definition_ref")
            ):
                raise InventoryRuntimeError("harvest_to_custody_replay_invalid")
            rows.append(dict(payload))
            source_revision_vector[event.stream_id] = max(
                source_revision_vector.get(event.stream_id, 0), event.stream_revision
            )
            source_revision_vector[source.stream_id] = max(
                source_revision_vector.get(source.stream_id, 0), source.stream_revision
            )
        payload = {
            "rows": rows,
            "source_revision_vector": source_revision_vector,
        }
        return HarvestToCustodyView(
            rows=tuple(rows),
            source_revision_vector=source_revision_vector,
            projection_hash="sha256:" + sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
            ).hexdigest(),
        )

    def reinforced_mill_flour_output_receipt_for(
        self, *, result: AppendBatchResult, scope: str
    ) -> SettlementReceipt:
        if scope != "project":
            raise InventoryRuntimeError("inventory_mill_flour_output_receipt_scope_denied")
        if not result.committed or len(result.committed_event_ids) != 1:
            raise InventoryRuntimeError("inventory_mill_flour_output_receipt_missing")
        return SettlementReceipt.from_append_result(
            result=result,
            audit_refs=(f"inventory_mill_flour_output:{result.transaction_id}",),
        )

    def build_reinforced_mill_flour_output_purchase_fragment(
        self,
        *,
        provider_actor_ref: str,
        receiver_actor_ref: str,
        source_receipt_event_id: str,
        destination_container_id: str,
        outcome_ref: str,
        package_revision: str,
        expected_provider_revision: int,
        expected_receiver_revision: int,
    ) -> tuple[OwnerAuthorizedFragment, dict[str, object]]:
        if (
            provider_actor_ref != _REINFORCED_MILL_FLOUR_PROVIDER
            or not receiver_actor_ref
            or not source_receipt_event_id
            or not destination_container_id
            or not outcome_ref
            or not (
                package_revision == "package:industrial-facilities:v7"
                or package_revision.startswith("package:declared-exchange:")
            )
        ):
            raise InventoryRuntimeError("inventory_package_exchange_invalid")
        all_events = self._store.read_events()
        provider = self._projector.rebuild(provider_actor_ref, all_events)
        receiver = self._projector.rebuild(receiver_actor_ref, all_events)
        provider_stream = f"gameplay:inventory:{provider_actor_ref}"
        receiver_stream = f"gameplay:inventory:{receiver_actor_ref}"
        if provider.source_revision_vector.get(provider_stream, 0) != expected_provider_revision:
            raise InventoryRuntimeError("revision_conflict")
        if receiver.source_revision_vector.get(receiver_stream, 0) != expected_receiver_revision:
            raise InventoryRuntimeError("revision_conflict")
        destination = receiver.containers.get(destination_container_id)
        if destination is None:
            raise InventoryRuntimeError("inventory_container_unknown")
        if destination.sealed:
            raise InventoryRuntimeError("inventory_access_denied")
        if destination.carrier_item_id:
            raise InventoryRuntimeError("inventory_container_access_requires_equipment")
        source_receipt = self._store.get_event(source_receipt_event_id)
        if (
            source_receipt.event_type != _REINFORCED_MILL_FLOUR_OUTPUT_EVENT
            or source_receipt.visibility_policy != "project"
        ):
            raise InventoryRuntimeError("inventory_package_exchange_source_ambiguous")
        if self._store.get_stream_head(provider_stream) != source_receipt.stream_revision:
            raise InventoryRuntimeError("revision_conflict")
        if (
            source_receipt.payload.get("actor_ref") != provider_actor_ref
            or source_receipt.payload.get("provider_ref") != provider_actor_ref
            or source_receipt.payload.get("item_ref") != _REINFORCED_MILL_FLOUR_ITEM
            or source_receipt.payload.get("definition_id") != _REINFORCED_MILL_FLOUR_ITEM
            or source_receipt.payload.get("quantity") != 10
            or source_receipt.payload.get("container_id")
            != _REINFORCED_MILL_FLOUR_PROVIDER_CONTAINER
            or source_receipt.payload.get("recipe_ref") != _REINFORCED_MILL_FLOUR_RECIPE
        ):
            raise InventoryRuntimeError("inventory_package_exchange_source_ambiguous")
        matches = [
            item
            for item in provider.items.values()
            if item.source_event_id == source_receipt_event_id
            and item.definition_id == _REINFORCED_MILL_FLOUR_ITEM
            and item.quantity == 10
            and item.available_quantity == 10
            and provider.locations.get(item.item_id)
            == _REINFORCED_MILL_FLOUR_PROVIDER_CONTAINER
        ]
        if len(matches) != 1:
            raise InventoryRuntimeError("inventory_package_exchange_source_ambiguous")
        item = matches[0]
        self._require_capacity(receiver, destination_container_id, item)
        fragment = OwnerAuthorizedFragment(
            fragment_id=(
                "fragment:inventory:reinforced-mill-flour-output-purchase:"
                f"{provider_actor_ref}:{receiver_actor_ref}:{source_receipt_event_id}"
            ),
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref="inventory:reinforced-mill-flour-output-purchase@1",
            expected_revisions={
                provider_stream: expected_provider_revision,
                receiver_stream: expected_receiver_revision,
            },
            pinned_revisions={
                f"inventory:{provider_actor_ref}": expected_provider_revision,
                f"inventory:{receiver_actor_ref}": expected_receiver_revision,
                "inventory_source": source_receipt.stream_revision,
            },
            event_specs={
                provider_stream: (
                    (
                        "gameplay.inventory.item_transferred_out",
                        {
                            "source_ref": _REINFORCED_MILL_FLOUR_ITEM,
                            "actor_ref": provider_actor_ref,
                            "item_id": item.item_id,
                            "from_container_id": _REINFORCED_MILL_FLOUR_PROVIDER_CONTAINER,
                            "to_actor_ref": receiver_actor_ref,
                            "outcome_ref": outcome_ref,
                            "package_revision": package_revision,
                            "source_event_id": source_receipt.event_id,
                            "source_selection_rule_ref": "exchange:reinforced-mill-certified-output@1",
                        },
                    ),
                ),
                receiver_stream: (
                    (
                        "gameplay.inventory.item_transferred_in",
                        {
                            "source_ref": _REINFORCED_MILL_FLOUR_ITEM,
                            "actor_ref": receiver_actor_ref,
                            "item_id": item.item_id,
                            "definition_id": item.definition_id,
                            "quantity": item.quantity,
                            "to_container_id": destination_container_id,
                            "from_actor_ref": provider_actor_ref,
                            "outcome_ref": outcome_ref,
                            "package_revision": package_revision,
                            "source_event_id": source_receipt.event_id,
                            "source_selection_rule_ref": "exchange:reinforced-mill-certified-output@1",
                        },
                    ),
                ),
            },
            event_visibility_policies={
                provider_stream: ("authority_only",),
                receiver_stream: ("authority_only",),
            },
        )
        return fragment, {
            "source_event_id": source_receipt.event_id,
            "source_event_revision": source_receipt.stream_revision,
            "item_id": item.item_id,
            "definition_id": item.definition_id,
        }

    def build_package_declared_negotiated_exchange_fragment(
        self,
        *,
        provider_actor_ref: str,
        receiver_actor_ref: str,
        source_ref: str,
        traded_definition_id: str,
        destination_container_id: str,
        outcome_ref: str,
        package_revision: str,
        expected_provider_revision: int,
        expected_receiver_revision: int,
    ) -> tuple[OwnerAuthorizedFragment, dict[str, object]]:
        if (
            not provider_actor_ref
            or not receiver_actor_ref
            or not source_ref
            or not traded_definition_id
            or not destination_container_id
            or not outcome_ref
            or not package_revision
        ):
            raise InventoryRuntimeError("inventory_package_exchange_invalid")
        self._registry.item(traded_definition_id)
        all_events = self._store.read_events()
        provider = self._projector.rebuild(provider_actor_ref, all_events)
        receiver = self._projector.rebuild(receiver_actor_ref, all_events)
        provider_stream = f"gameplay:inventory:{provider_actor_ref}"
        receiver_stream = f"gameplay:inventory:{receiver_actor_ref}"
        if provider.source_revision_vector.get(provider_stream, 0) != expected_provider_revision:
            raise InventoryRuntimeError("revision_conflict")
        if receiver.source_revision_vector.get(receiver_stream, 0) != expected_receiver_revision:
            raise InventoryRuntimeError("revision_conflict")
        destination = receiver.containers.get(destination_container_id)
        if destination is None:
            raise InventoryRuntimeError("inventory_container_unknown")
        if destination.sealed:
            raise InventoryRuntimeError("inventory_access_denied")
        if destination.carrier_item_id:
            raise InventoryRuntimeError("inventory_container_access_requires_equipment")
        matches: list[tuple[InventoryItem, str, GameplayEvent]] = []
        for item in provider.items.values():
            if item.definition_id != traded_definition_id or item.available_quantity != item.quantity or item.quantity != 1:
                continue
            container_id = provider.locations.get(item.item_id)
            if not isinstance(container_id, str) or not container_id.startswith("container:"):
                continue
            container = provider.containers.get(container_id)
            if container is None or container.sealed or container.carrier_item_id:
                continue
            source_event = self._store.get_event(item.source_event_id)
            if source_event.event_type not in {
                "gameplay.inventory.item_instantiated",
                "gameplay.inventory.output_received",
                "gameplay.inventory.item_transferred_in",
            }:
                continue
            matches.append((item, container_id, source_event))
        if len(matches) != 1:
            raise InventoryRuntimeError("inventory_package_exchange_source_ambiguous")
        item, from_container_id, source_event = matches[0]
        self._require_capacity(receiver, destination_container_id, item)
        source_rule_ref = "exchange:unique-owned-source@1"
        fragment = OwnerAuthorizedFragment(
            fragment_id=(
                "fragment:inventory:package-declared-negotiated-exchange:"
                f"{provider_actor_ref}:{receiver_actor_ref}:{outcome_ref}"
            ),
            owner_principal_ref=self._PRINCIPAL,
            source_rule_ref="inventory:package-declared-negotiated-exchange@1",
            expected_revisions={
                provider_stream: expected_provider_revision,
                receiver_stream: expected_receiver_revision,
            },
            pinned_revisions={
                f"inventory:{provider_actor_ref}": expected_provider_revision,
                f"inventory:{receiver_actor_ref}": expected_receiver_revision,
            },
            event_specs={
                provider_stream: (
                    (
                        "gameplay.inventory.item_transferred_out",
                        {
                            "source_ref": source_ref,
                            "actor_ref": provider_actor_ref,
                            "item_id": item.item_id,
                            "from_container_id": from_container_id,
                            "to_actor_ref": receiver_actor_ref,
                            "outcome_ref": outcome_ref,
                            "package_revision": package_revision,
                            "source_event_id": source_event.event_id,
                            "source_selection_rule_ref": source_rule_ref,
                        },
                    ),
                ),
                receiver_stream: (
                    (
                        "gameplay.inventory.item_transferred_in",
                        {
                            "source_ref": source_ref,
                            "actor_ref": receiver_actor_ref,
                            "item_id": item.item_id,
                            "definition_id": item.definition_id,
                            "quantity": item.quantity,
                            "to_container_id": destination_container_id,
                            "from_actor_ref": provider_actor_ref,
                            "outcome_ref": outcome_ref,
                            "package_revision": package_revision,
                            "source_event_id": source_event.event_id,
                            "source_selection_rule_ref": source_rule_ref,
                        },
                    ),
                ),
            },
            event_visibility_policies={
                provider_stream: ("authority_only",),
                receiver_stream: ("authority_only",),
            },
        )
        return fragment, {
            "source_event_id": source_event.event_id,
            "source_event_revision": source_event.stream_revision,
            "item_id": item.item_id,
            "definition_id": item.definition_id,
        }

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
    def _reinforced_mill_flour_item_id(certification_event_id: str) -> str:
        return f"item:industrial-facilities:flour:certified:{_digest(certification_event_id)[:16]}"

    def _is_valid_reinforced_mill_flour_certification(
        self,
        *,
        certification_event: GameplayEvent,
        expected_certification_revision: int,
    ) -> bool:
        payload = certification_event.payload
        events_by_id = {
            event.event_id: event for event in self._store.read_events()
        }
        started = events_by_id.get(str(payload.get("source_run_started_event_id", "")))
        finished = events_by_id.get(str(payload.get("source_run_finished_event_id", "")))
        reinforcement = events_by_id.get(
            str(payload.get("source_reinforcement_event_id", ""))
        )
        acquisition = (
            events_by_id.get(str(reinforcement.payload.get("acquisition_event_id", "")))
            if reinforcement is not None
            else None
        )
        stream_id = certification_event.stream_id
        return (
            certification_event.event_type == _REINFORCED_MILL_FLOUR_SOURCE_EVENT
            and certification_event.visibility_policy == "project"
            and certification_event.stream_revision == expected_certification_revision
            and self._store.get_stream_head(certification_event.stream_id)
            == expected_certification_revision
            and stream_id == "gameplay:construction_production:facility:mill-reinforcement:1"
            and payload.get("facility_ref") == "facility:mill-reinforcement:1"
            and bool(payload.get("project_ref"))
            and payload.get("recipe_ref") == _REINFORCED_MILL_FLOUR_RECIPE
            and payload.get("output_item") == _REINFORCED_MILL_FLOUR_ITEM
            and payload.get("quantity") == 10
            and started is not None
            and started.event_type == "gameplay.construction_production.run_started"
            and started.stream_id == stream_id
            and started.stream_revision == payload.get("source_run_started_revision")
            and finished is not None
            and finished.event_type == "gameplay.construction_production.run_finished"
            and finished.stream_id == stream_id
            and finished.stream_revision == payload.get("source_run_finished_revision")
            and finished.payload.get("run_ref") == payload.get("run_ref")
            and finished.payload.get("recipe_ref") == _REINFORCED_MILL_FLOUR_RECIPE
            and finished.payload.get("output_item") == _REINFORCED_MILL_FLOUR_ITEM
            and reinforcement is not None
            and reinforcement.event_type
            == "gameplay.construction_production.facility_transformed"
            and reinforcement.stream_id == stream_id
            and reinforcement.stream_revision
            == payload.get("source_reinforcement_revision")
            and reinforcement.visibility_policy == "project"
            and reinforcement.payload.get("facility_ref")
            == payload.get("facility_ref")
            and reinforcement.payload.get("project_ref")
            == payload.get("project_ref")
            and reinforcement.payload.get("prior_kind") == "mill"
            and reinforcement.payload.get("next_kind") == "mill_reinforced"
            and reinforcement.payload.get("package_revision")
            == "package:industrial-facilities:v2"
            and reinforcement.payload.get("content_digest")
            == "sha256:8deea88c5e49c2aa06f30bbf1bd78ed103e26d8fb31769fe5564dbb7cc279896"
            and reinforcement.payload.get("declaration_ref")
            == "declaration:industrial-facilities-mill-to-mill-reinforced@1"
            and reinforcement.payload.get("declaration_digest")
            == "sha256:73d3313283bf584254281a2ca1b60d888585f6ba89e6370a30d622e4529b1bc8"
            and acquisition is not None
            and acquisition.event_type
            == "gameplay.construction_production.facility_acquired"
            and acquisition.stream_id == stream_id
            and acquisition.visibility_policy == "project"
            and acquisition.payload.get("facility_ref")
            == payload.get("facility_ref")
            and acquisition.payload.get("plot_ref")
            == payload.get("project_ref")
        )

    @staticmethod
    def _rejected_append(command_id: str, error_code: str) -> AppendBatchResult:
        return AppendBatchResult(
            committed=False,
            transaction_id=f"tx:{command_id}",
            command_id=command_id,
            idempotency_status="rejected",
            failure=GameplayFailure(
                error_code=error_code,
                message=error_code,
                failed_stage="inventory_commit",
            ),
        )

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


def _resolve_harvest_binding(binding_ref: str, *, prefix: str) -> str:
    if not binding_ref.startswith(prefix) or not binding_ref.endswith("@1"):
        raise InventoryRuntimeError("harvest_to_custody_binding_invalid")
    value = binding_ref[len(prefix) : -2]
    if not value:
        raise InventoryRuntimeError("harvest_to_custody_binding_invalid")
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
