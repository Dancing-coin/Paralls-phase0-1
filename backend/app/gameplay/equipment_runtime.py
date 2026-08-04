"""Minimal event-sourced equipment authority coordinated with inventory placement."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Mapping, Sequence

from app.gameplay.ability_runtime import AbilityDefinitionRegistry
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import InventoryDefinitionRegistry, InventoryItem, InventoryProjector, InventoryProjection
from app.gameplay.modifier_runtime import ModifierDefinitionRegistry
from app.gameplay.models import AppendBatchResult, GameplayEvent
from app.gameplay.resource_body_runtime import BodyRuntimeProjection


class EquipmentRuntimeError(ValueError):
    pass


@dataclass(frozen=True)
class EquipmentProfile:
    profile_id: str
    compatible_slot_keys: tuple[str, ...]
    required_body_function_ids: tuple[str, ...] = ()
    ability_grant_path_ids: tuple[str, ...] = ()
    modifier_template_ids: tuple[str, ...] = ()
    required_slot_keys: tuple[str, ...] = ()
    container_access_container_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class EquipmentSlotDefinition:
    slot_key: str
    required_body_function_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class EquipmentActivation:
    activation_id: str
    item_id: str
    profile_id: str
    slot_key: str
    slot_keys: tuple[str, ...]
    equipment_location: str
    ability_grant_ids: tuple[str, ...]
    modifier_instance_ids: tuple[str, ...]
    source_event_id: str
    container_access_container_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class EquipmentProjection:
    actor_ref: str
    activations: Mapping[str, EquipmentActivation]
    active_by_slot: Mapping[str, str]
    ended_activation_ids: tuple[str, ...]
    source_revision_vector: Mapping[str, int]
    projection_revision: str


class EquipmentDefinitionRegistry:
    def __init__(self) -> None:
        self._profiles_by_definition_id: dict[str, EquipmentProfile] = {}

    def register_profile(self, definition_id: str, profile: EquipmentProfile) -> None:
        if (
            not definition_id
            or not profile.profile_id
            or not profile.compatible_slot_keys
            or definition_id in self._profiles_by_definition_id
            or any(not slot_key for slot_key in profile.compatible_slot_keys)
            or any(not function_id for function_id in profile.required_body_function_ids)
            or any(not path_id for path_id in profile.ability_grant_path_ids)
            or len(set(profile.ability_grant_path_ids)) != len(profile.ability_grant_path_ids)
            or any(not template_id for template_id in profile.modifier_template_ids)
            or len(set(profile.modifier_template_ids)) != len(profile.modifier_template_ids)
            or any(not slot_key for slot_key in profile.required_slot_keys)
            or len(set(profile.required_slot_keys)) != len(profile.required_slot_keys)
            or any(not container_id for container_id in profile.container_access_container_ids)
            or len(set(profile.container_access_container_ids)) != len(profile.container_access_container_ids)
        ):
            raise EquipmentRuntimeError("equipment_profile_invalid")
        self._profiles_by_definition_id[definition_id] = profile

    def profile_for(self, definition_id: str) -> EquipmentProfile:
        try:
            return self._profiles_by_definition_id[definition_id]
        except KeyError as exc:
            raise EquipmentRuntimeError("equipment_item_not_equippable") from exc


class EquipmentProjector:
    """Rebuilds active slots only from committed equipment lifecycle events."""

    _EVENT_TYPES = {
        "gameplay.equipment.activation_started",
        "gameplay.equipment.activation_ended",
    }

    def rebuild(self, actor_ref: str, events: Sequence[GameplayEvent]) -> EquipmentProjection:
        activations: dict[str, EquipmentActivation] = {}
        active_by_slot: dict[str, str] = {}
        ended: list[str] = []
        revisions: dict[str, int] = {}
        for event in sorted(events, key=lambda item: (item.global_sequence, item.event_id)):
            if event.event_type not in self._EVENT_TYPES:
                continue
            payload = event.payload
            if str(payload.get("actor_ref", "")) != actor_ref:
                raise EquipmentRuntimeError("equipment_actor_mismatch")
            activation_id = _text(payload, "activation_id")
            if event.event_type == "gameplay.equipment.activation_started":
                item_id = _text(payload, "item_id")
                profile_id = _text(payload, "profile_id")
                slot_key = _text(payload, "slot_key")
                slot_keys = _text_tuple(payload.get("slot_keys", (slot_key,)))
                equipment_location = _text(payload, "equipment_location")
                ability_grant_ids = _text_tuple(payload.get("ability_grant_ids", ()))
                modifier_instance_ids = _text_tuple(payload.get("modifier_instance_ids", ()))
                container_access_container_ids = _text_tuple(payload.get("container_access_container_ids", ()))
                if (
                    activation_id in activations
                    or not slot_keys
                    or slot_key not in slot_keys
                    or any(occupied_slot in active_by_slot for occupied_slot in slot_keys)
                    or not equipment_location.startswith("equipment:")
                ):
                    raise EquipmentRuntimeError("equipment_activation_invalid")
                activations[activation_id] = EquipmentActivation(
                    activation_id,
                    item_id,
                    profile_id,
                    slot_key,
                    slot_keys,
                    equipment_location,
                    ability_grant_ids,
                    modifier_instance_ids,
                    event.event_id,
                    container_access_container_ids,
                )
                for occupied_slot in slot_keys:
                    active_by_slot[occupied_slot] = activation_id
            else:
                activation = activations.pop(activation_id, None)
                if activation is None:
                    raise EquipmentRuntimeError("equipment_activation_not_found")
                if any(active_by_slot.get(occupied_slot) != activation_id for occupied_slot in activation.slot_keys):
                    raise EquipmentRuntimeError("equipment_activation_invalid")
                for occupied_slot in activation.slot_keys:
                    del active_by_slot[occupied_slot]
                ended.append(activation_id)
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
        frozen_activations = MappingProxyType(dict(sorted(activations.items())))
        frozen_slots = MappingProxyType(dict(sorted(active_by_slot.items())))
        frozen_revisions = MappingProxyType(dict(sorted(revisions.items())))
        return EquipmentProjection(
            actor_ref,
            frozen_activations,
            frozen_slots,
            tuple(ended),
            frozen_revisions,
            f"equipment:{_digest([actor_ref, frozen_activations, frozen_slots, ended, frozen_revisions])[:16]}",
        )


class EquipmentAuthorityService:
    """Appends equipment and inventory state transitions in one authority batch."""

    _PRINCIPAL = "actor_gameplay.equipment_domain"

    def __init__(
        self,
        *,
        store: GameplayEventStore,
        inventory_registry: InventoryDefinitionRegistry,
        equipment_registry: EquipmentDefinitionRegistry,
        ability_registry: AbilityDefinitionRegistry,
        modifier_registry: ModifierDefinitionRegistry,
        slots: Sequence[EquipmentSlotDefinition],
    ) -> None:
        self._store = store
        self._inventory_registry = inventory_registry
        self._equipment_registry = equipment_registry
        self._ability_registry = ability_registry
        self._modifier_registry = modifier_registry
        self._inventory_projector = InventoryProjector(inventory_registry)
        self._equipment_projector = EquipmentProjector()
        slot_definitions = tuple(slots)
        if (
            not slot_definitions
            or any(not slot.slot_key for slot in slot_definitions)
            or len({slot.slot_key for slot in slot_definitions}) != len(slot_definitions)
        ):
            raise EquipmentRuntimeError("equipment_slot_invalid")
        self._slots = {slot.slot_key: slot for slot in slot_definitions}

    def equip(
        self,
        *,
        command_id: str,
        actor_ref: str,
        item_id: str,
        source_container_id: str,
        slot_key: str,
        body: BodyRuntimeProjection,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        command = {
            "kind": "equip",
            "command_id": command_id,
            "actor_ref": actor_ref,
            "item_id": item_id,
            "source_container_id": source_container_id,
            "slot_key": slot_key,
        }
        digest = _digest(command)
        duplicate = self._duplicate(actor_ref, idempotency_key, digest)
        if duplicate is not None:
            return duplicate
        inventory, equipment = self._projections(actor_ref)
        self._validate_body(actor_ref, body)
        item = inventory.items.get(item_id)
        if item is None or inventory.locations.get(item_id) != source_container_id:
            raise EquipmentRuntimeError("equipment_source_placement_mismatch")
        if slot_key not in self._slots:
            raise EquipmentRuntimeError("equipment_slot_unknown")
        profile = self._equipment_registry.profile_for(item.definition_id)
        occupied_slot_keys = _occupied_slot_keys(slot_key, profile)
        if any(occupied_slot not in profile.compatible_slot_keys for occupied_slot in occupied_slot_keys):
            raise EquipmentRuntimeError("equipment_slot_incompatible")
        slots = []
        for occupied_slot in occupied_slot_keys:
            slot = self._slots.get(occupied_slot)
            if slot is None:
                raise EquipmentRuntimeError("equipment_slot_unknown")
            slots.append(slot)
        if any(occupied_slot in equipment.active_by_slot for occupied_slot in occupied_slot_keys):
            raise EquipmentRuntimeError("equipment_slot_occupied")
        self._require_body_functions(
            body,
            (*profile.required_body_function_ids, *(function_id for slot in slots for function_id in slot.required_body_function_ids)),
        )
        equipment_location = _equipment_location(slot_key)
        activation_id = f"activation:{command_id}"
        ability_grant_ids = tuple(
            f"ability-grant:{activation_id}:{path_id}"
            for path_id in profile.ability_grant_path_ids
        )
        for path_id in profile.ability_grant_path_ids:
            self._ability_registry.path(path_id)
        modifier_instance_ids = tuple(
            f"modifier:{activation_id}:{template_id}"
            for template_id in profile.modifier_template_ids
        )
        for template_id in profile.modifier_template_ids:
            self._modifier_registry.template(template_id)
        inventory_stream = _inventory_stream(actor_ref)
        equipment_stream = _equipment_stream(actor_ref)
        ability_stream = _ability_stream(actor_ref)
        modifier_stream = _modifier_stream(actor_ref)
        body_stream = _body_stream(actor_ref)
        transaction_id = f"tx:{command_id}"
        events: list[dict[str, object]] = [
            _event(
                command_id,
                transaction_id,
                inventory_stream,
                "gameplay.inventory.item_equipped",
                1,
                causation_id,
                correlation_id,
                {"actor_ref": actor_ref, "item_id": item_id, "from_container_id": source_container_id, "equipment_location": equipment_location},
            ),
            _event(
                command_id,
                transaction_id,
                equipment_stream,
                "gameplay.equipment.activation_started",
                2,
                causation_id,
                correlation_id,
                {
                    "actor_ref": actor_ref,
                    "activation_id": activation_id,
                    "item_id": item_id,
                    "profile_id": profile.profile_id,
                    "slot_key": slot_key,
                    "slot_keys": list(occupied_slot_keys),
                    "equipment_location": equipment_location,
                    "ability_grant_ids": list(ability_grant_ids),
                    "modifier_instance_ids": list(modifier_instance_ids),
                    "container_access_container_ids": list(profile.container_access_container_ids),
                },
            ),
        ]
        for index, (instance_id, template_id) in enumerate(zip(modifier_instance_ids, profile.modifier_template_ids), start=3):
            events.append(
                _event(
                    command_id,
                    transaction_id,
                    modifier_stream,
                    "gameplay.modifier.source_activated",
                    index,
                    causation_id,
                    correlation_id,
                    {"actor_ref": actor_ref, "modifier_instance_id": instance_id, "template_id": template_id, "source_ref": activation_id},
                )
            )
        for index, (grant_id, path_id) in enumerate(
            zip(ability_grant_ids, profile.ability_grant_path_ids),
            start=3 + len(modifier_instance_ids),
        ):
            events.append(
                _event(
                    command_id,
                    transaction_id,
                    ability_stream,
                    "gameplay.ability.grant_activated",
                    index,
                    causation_id,
                    correlation_id,
                    {"actor_ref": actor_ref, "grant_id": grant_id, "skill_ids": [], "path_ids": [path_id], "source_ref": activation_id},
                )
            )
        return self._append(command_id, transaction_id, actor_ref, idempotency_key, digest, events, inventory, equipment, body, body_stream)

    def unequip(
        self,
        *,
        command_id: str,
        actor_ref: str,
        activation_id: str,
        destination_container_id: str,
        body: BodyRuntimeProjection,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        command = {
            "kind": "unequip",
            "command_id": command_id,
            "actor_ref": actor_ref,
            "activation_id": activation_id,
            "destination_container_id": destination_container_id,
        }
        digest = _digest(command)
        duplicate = self._duplicate(actor_ref, idempotency_key, digest)
        if duplicate is not None:
            return duplicate
        inventory, equipment = self._projections(actor_ref)
        self._validate_body(actor_ref, body)
        activation = equipment.activations.get(activation_id)
        if activation is None:
            raise EquipmentRuntimeError("equipment_activation_not_found")
        if inventory.locations.get(activation.item_id) != activation.equipment_location:
            raise EquipmentRuntimeError("equipment_source_placement_mismatch")
        if any(
            location in activation.container_access_container_ids
            for location in inventory.locations.values()
        ):
            raise EquipmentRuntimeError("equipment_container_non_empty")
        self._require_destination_capacity(inventory, destination_container_id, inventory.items[activation.item_id])
        inventory_stream = _inventory_stream(actor_ref)
        equipment_stream = _equipment_stream(actor_ref)
        body_stream = _body_stream(actor_ref)
        transaction_id = f"tx:{command_id}"
        ability_stream = _ability_stream(actor_ref)
        modifier_stream = _modifier_stream(actor_ref)
        events: list[dict[str, object]] = []
        for index, grant_id in enumerate(activation.ability_grant_ids, start=1):
            events.append(
                _event(
                    command_id,
                    transaction_id,
                    ability_stream,
                    "gameplay.ability.grant_revoked",
                    index,
                    causation_id,
                    correlation_id,
                    {"actor_ref": actor_ref, "grant_id": grant_id},
                )
            )
        for index, instance_id in enumerate(activation.modifier_instance_ids, start=len(events) + 1):
            events.append(
                _event(
                    command_id,
                    transaction_id,
                    modifier_stream,
                    "gameplay.modifier.source_deactivated",
                    index,
                    causation_id,
                    correlation_id,
                    {"actor_ref": actor_ref, "modifier_instance_id": instance_id},
                )
            )
        inventory_index = len(events) + 1
        events.extend([
            _event(
                command_id,
                transaction_id,
                inventory_stream,
                "gameplay.inventory.item_unequipped",
                inventory_index,
                causation_id,
                correlation_id,
                {"actor_ref": actor_ref, "item_id": activation.item_id, "equipment_location": activation.equipment_location, "to_container_id": destination_container_id},
            ),
            _event(
                command_id,
                transaction_id,
                equipment_stream,
                "gameplay.equipment.activation_ended",
                inventory_index + 1,
                causation_id,
                correlation_id,
                {"actor_ref": actor_ref, "activation_id": activation_id},
            ),
        ])
        return self._append(command_id, transaction_id, actor_ref, idempotency_key, digest, events, inventory, equipment, body, body_stream)

    def swap(
        self,
        *,
        command_id: str,
        actor_ref: str,
        outgoing_activation_id: str,
        incoming_item_id: str,
        incoming_source_container_id: str,
        incoming_slot_key: str,
        outgoing_destination_container_id: str,
        body: BodyRuntimeProjection,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        command = {
            "kind": "swap",
            "command_id": command_id,
            "actor_ref": actor_ref,
            "outgoing_activation_id": outgoing_activation_id,
            "incoming_item_id": incoming_item_id,
            "incoming_source_container_id": incoming_source_container_id,
            "incoming_slot_key": incoming_slot_key,
            "outgoing_destination_container_id": outgoing_destination_container_id,
        }
        digest = _digest(command)
        duplicate = self._duplicate(actor_ref, idempotency_key, digest)
        if duplicate is not None:
            return duplicate
        inventory, equipment = self._projections(actor_ref)
        self._validate_body(actor_ref, body)
        outgoing = equipment.activations.get(outgoing_activation_id)
        if outgoing is None:
            raise EquipmentRuntimeError("equipment_activation_not_found")
        if inventory.locations.get(outgoing.item_id) != outgoing.equipment_location:
            raise EquipmentRuntimeError("equipment_source_placement_mismatch")
        incoming = inventory.items.get(incoming_item_id)
        if incoming is None or inventory.locations.get(incoming_item_id) != incoming_source_container_id:
            raise EquipmentRuntimeError("equipment_source_placement_mismatch")
        self._require_destination_capacity(
            inventory,
            outgoing_destination_container_id,
            inventory.items[outgoing.item_id],
            excluded_item_ids=(incoming_item_id,),
        )
        profile = self._equipment_registry.profile_for(incoming.definition_id)
        if incoming_slot_key not in self._slots:
            raise EquipmentRuntimeError("equipment_slot_unknown")
        incoming_slot_keys = _occupied_slot_keys(incoming_slot_key, profile)
        if any(slot_key not in profile.compatible_slot_keys for slot_key in incoming_slot_keys):
            raise EquipmentRuntimeError("equipment_slot_incompatible")
        slots = []
        for slot_key in incoming_slot_keys:
            slot = self._slots.get(slot_key)
            if slot is None:
                raise EquipmentRuntimeError("equipment_slot_unknown")
            slots.append(slot)
        if any(
            slot_key in equipment.active_by_slot and equipment.active_by_slot[slot_key] != outgoing_activation_id
            for slot_key in incoming_slot_keys
        ):
            raise EquipmentRuntimeError("equipment_slot_occupied")
        self._require_body_functions(
            body,
            (*profile.required_body_function_ids, *(function_id for slot in slots for function_id in slot.required_body_function_ids)),
        )
        incoming_activation_id = f"activation:{command_id}"
        incoming_grant_ids = tuple(
            f"ability-grant:{incoming_activation_id}:{path_id}"
            for path_id in profile.ability_grant_path_ids
        )
        for path_id in profile.ability_grant_path_ids:
            self._ability_registry.path(path_id)
        incoming_modifier_ids = tuple(
            f"modifier:{incoming_activation_id}:{template_id}"
            for template_id in profile.modifier_template_ids
        )
        for template_id in profile.modifier_template_ids:
            self._modifier_registry.template(template_id)
        inventory_stream = _inventory_stream(actor_ref)
        equipment_stream = _equipment_stream(actor_ref)
        ability_stream = _ability_stream(actor_ref)
        modifier_stream = _modifier_stream(actor_ref)
        body_stream = _body_stream(actor_ref)
        transaction_id = f"tx:{command_id}"
        events: list[dict[str, object]] = []
        for index, grant_id in enumerate(outgoing.ability_grant_ids, start=1):
            events.append(
                _event(
                    command_id, transaction_id, ability_stream, "gameplay.ability.grant_revoked", index,
                    causation_id, correlation_id, {"actor_ref": actor_ref, "grant_id": grant_id},
                )
            )
        for index, instance_id in enumerate(outgoing.modifier_instance_ids, start=len(events) + 1):
            events.append(
                _event(
                    command_id, transaction_id, modifier_stream, "gameplay.modifier.source_deactivated", index,
                    causation_id, correlation_id, {"actor_ref": actor_ref, "modifier_instance_id": instance_id},
                )
            )
        events.extend(
            [
                _event(
                    command_id, transaction_id, inventory_stream, "gameplay.inventory.item_unequipped", len(events) + 1,
                    causation_id, correlation_id,
                    {"actor_ref": actor_ref, "item_id": outgoing.item_id, "equipment_location": outgoing.equipment_location, "to_container_id": outgoing_destination_container_id},
                ),
                _event(
                    command_id, transaction_id, equipment_stream, "gameplay.equipment.activation_ended", len(events) + 2,
                    causation_id, correlation_id, {"actor_ref": actor_ref, "activation_id": outgoing_activation_id},
                ),
                _event(
                    command_id, transaction_id, inventory_stream, "gameplay.inventory.item_equipped", len(events) + 3,
                    causation_id, correlation_id,
                    {"actor_ref": actor_ref, "item_id": incoming_item_id, "from_container_id": incoming_source_container_id, "equipment_location": _equipment_location(incoming_slot_key)},
                ),
                _event(
                    command_id, transaction_id, equipment_stream, "gameplay.equipment.activation_started", len(events) + 4,
                    causation_id, correlation_id,
                    {"actor_ref": actor_ref, "activation_id": incoming_activation_id, "item_id": incoming_item_id, "profile_id": profile.profile_id, "slot_key": incoming_slot_key, "slot_keys": list(incoming_slot_keys), "equipment_location": _equipment_location(incoming_slot_key), "ability_grant_ids": list(incoming_grant_ids), "modifier_instance_ids": list(incoming_modifier_ids)},
                ),
            ]
        )
        for index, (instance_id, template_id) in enumerate(
            zip(incoming_modifier_ids, profile.modifier_template_ids), start=len(events) + 1
        ):
            events.append(
                _event(
                    command_id, transaction_id, modifier_stream, "gameplay.modifier.source_activated", index,
                    causation_id, correlation_id,
                    {"actor_ref": actor_ref, "modifier_instance_id": instance_id, "template_id": template_id, "source_ref": incoming_activation_id},
                )
            )
        for index, (grant_id, path_id) in enumerate(
            zip(incoming_grant_ids, profile.ability_grant_path_ids), start=len(events) + 1
        ):
            events.append(
                _event(
                    command_id, transaction_id, ability_stream, "gameplay.ability.grant_activated", index,
                    causation_id, correlation_id,
                    {"actor_ref": actor_ref, "grant_id": grant_id, "skill_ids": [], "path_ids": [path_id], "source_ref": incoming_activation_id},
                )
            )
        return self._append(command_id, transaction_id, actor_ref, idempotency_key, digest, events, inventory, equipment, body, body_stream)

    def _projections(self, actor_ref: str) -> tuple[InventoryProjection, EquipmentProjection]:
        events = self._store.read_events()
        return self._inventory_projector.rebuild(actor_ref, events), self._equipment_projector.rebuild(actor_ref, events)

    def _duplicate(self, actor_ref: str, idempotency_key: str, digest: str) -> AppendBatchResult | None:
        key = f"{actor_ref}:{idempotency_key}"
        record = self._store.get_idempotency_record(self._PRINCIPAL, key)
        if record is None:
            return None
        if record.payload_digest != digest:
            raise EquipmentRuntimeError("idempotency_key_reused")
        result = self._store.get_by_idempotency(self._PRINCIPAL, key)
        if result is None:
            raise EquipmentRuntimeError("equipment_idempotency_missing_result")
        return result.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)

    def _validate_body(self, actor_ref: str, body: BodyRuntimeProjection) -> None:
        if body.actor_ref != actor_ref:
            raise EquipmentRuntimeError("equipment_actor_mismatch")
        body_stream = _body_stream(actor_ref)
        if body.source_revision_vector.get(body_stream, 0) != self._store.get_stream_head(body_stream):
            raise EquipmentRuntimeError("revision_conflict")

    @staticmethod
    def _require_body_functions(body: BodyRuntimeProjection, function_ids: Sequence[str]) -> None:
        for function_id in sorted(set(function_ids)):
            capacity = body.functions.get(function_id)
            if capacity is not None and capacity.status != "available":
                raise EquipmentRuntimeError("equipment_body_requirement_failed")

    def _require_destination_capacity(
        self,
        inventory: InventoryProjection,
        destination_container_id: str,
        candidate: InventoryItem,
        *,
        excluded_item_ids: Sequence[str] = (),
    ) -> None:
        container = inventory.containers.get(destination_container_id)
        if container is None:
            raise EquipmentRuntimeError("equipment_destination_rejected")
        if container.sealed:
            raise EquipmentRuntimeError("equipment_destination_rejected")
        entries = [
            item
            for item_id, item in inventory.items.items()
            if inventory.locations.get(item_id) == destination_container_id
            and item_id != candidate.item_id
            and item_id not in excluded_item_ids
        ]
        weight = sum(self._inventory_registry.item(item.definition_id).unit_weight * item.quantity for item in entries)
        volume = sum(self._inventory_registry.item(item.definition_id).unit_volume * item.quantity for item in entries)
        definition = self._inventory_registry.item(candidate.definition_id)
        if (
            len(entries) + 1 > container.capacity_slots
            or weight + definition.unit_weight * candidate.quantity > container.capacity_weight
            or volume + definition.unit_volume * candidate.quantity > container.capacity_volume
        ):
            raise EquipmentRuntimeError("equipment_destination_rejected")

    def _append(
        self,
        command_id: str,
        transaction_id: str,
        actor_ref: str,
        idempotency_key: str,
        digest: str,
        events: list[dict[str, object]],
        inventory: InventoryProjection,
        equipment: EquipmentProjection,
        body: BodyRuntimeProjection,
        body_stream: str,
    ) -> AppendBatchResult:
        inventory_stream = _inventory_stream(actor_ref)
        equipment_stream = _equipment_stream(actor_ref)
        ability_stream = _ability_stream(actor_ref)
        modifier_stream = _modifier_stream(actor_ref)
        return self._store.append_batch(
            {
                "transaction_id": transaction_id,
                "command_id": command_id,
                "expected_stream_revisions": {
                    inventory_stream: inventory.source_revision_vector.get(inventory_stream, 0),
                    equipment_stream: equipment.source_revision_vector.get(equipment_stream, 0),
                    ability_stream: self._store.get_stream_head(ability_stream),
                    modifier_stream: self._store.get_stream_head(modifier_stream),
                    body_stream: body.source_revision_vector.get(body_stream, 0),
                },
                "pinned_revisions": {
                    "inventory": inventory.source_revision_vector.get(inventory_stream, 0),
                    "equipment": equipment.source_revision_vector.get(equipment_stream, 0),
                    "ability": self._store.get_stream_head(ability_stream),
                    "modifier": self._store.get_stream_head(modifier_stream),
                    "body": body.source_revision_vector.get(body_stream, 0),
                },
                "events": events,
                "idempotency_record": {
                    "principal_ref": self._PRINCIPAL,
                    "idempotency_key": f"{actor_ref}:{idempotency_key}",
                    "payload_digest": digest,
                },
                "outbox_entries": [],
                "result_digest": _digest(events),
                "projection_refresh_hints": [],
            }
        )


class EquipmentContainerAccessAuthority:
    """Moves items through a container only while its owning equipment is active."""

    _PRINCIPAL = "actor_gameplay.equipment_container_access"

    def __init__(
        self,
        *,
        store: GameplayEventStore,
        inventory_registry: InventoryDefinitionRegistry,
    ) -> None:
        self._store = store
        self._inventory_registry = inventory_registry
        self._inventory_projector = InventoryProjector(inventory_registry)
        self._equipment_projector = EquipmentProjector()

    def move(
        self,
        *,
        command_id: str,
        actor_ref: str,
        activation_id: str,
        item_id: str,
        from_container_id: str,
        to_container_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        command = {
            "kind": "equipment_container_move",
            "command_id": command_id,
            "actor_ref": actor_ref,
            "activation_id": activation_id,
            "item_id": item_id,
            "from_container_id": from_container_id,
            "to_container_id": to_container_id,
        }
        digest = _digest(command)
        duplicate = self._duplicate(actor_ref, idempotency_key, digest)
        if duplicate is not None:
            return duplicate

        events = self._store.read_events()
        inventory = self._inventory_projector.rebuild(actor_ref, events)
        equipment = self._equipment_projector.rebuild(actor_ref, events)
        activation = equipment.activations.get(activation_id)
        if activation is None:
            raise EquipmentRuntimeError("equipment_container_access_denied")
        access_container_ids = set(activation.container_access_container_ids)
        if not access_container_ids or not ({from_container_id, to_container_id} & access_container_ids):
            raise EquipmentRuntimeError("equipment_container_access_denied")
        item = inventory.items.get(item_id)
        target = inventory.containers.get(to_container_id)
        if item is None or inventory.locations.get(item_id) != from_container_id:
            raise EquipmentRuntimeError("equipment_container_move_source_invalid")
        if target is None or target.sealed:
            raise EquipmentRuntimeError("equipment_container_destination_rejected")
        for container_id in access_container_ids:
            container = inventory.containers.get(container_id)
            if container is None or container.carrier_item_id != activation.item_id:
                raise EquipmentRuntimeError("equipment_container_binding_invalid")
        self._require_destination_capacity(inventory, to_container_id, item)

        inventory_stream = _inventory_stream(actor_ref)
        equipment_stream = _equipment_stream(actor_ref)
        transaction_id = f"tx:{command_id}"
        event = _event(
            command_id,
            transaction_id,
            inventory_stream,
            "gameplay.inventory.item_moved",
            1,
            causation_id,
            correlation_id,
            {
                "actor_ref": actor_ref,
                "item_id": item_id,
                "from_container_id": from_container_id,
                "to_container_id": to_container_id,
            },
        )
        return self._store.append_batch(
            {
                "transaction_id": transaction_id,
                "command_id": command_id,
                "expected_stream_revisions": {
                    inventory_stream: inventory.source_revision_vector.get(inventory_stream, 0),
                    equipment_stream: equipment.source_revision_vector.get(equipment_stream, 0),
                },
                "pinned_revisions": {
                    "inventory": inventory.source_revision_vector.get(inventory_stream, 0),
                    "equipment": equipment.source_revision_vector.get(equipment_stream, 0),
                },
                "events": [event],
                "idempotency_record": {
                    "principal_ref": self._PRINCIPAL,
                    "idempotency_key": f"{actor_ref}:{idempotency_key}",
                    "payload_digest": digest,
                },
                "outbox_entries": [],
                "result_digest": _digest([event]),
                "projection_refresh_hints": [],
            }
        )

    def _duplicate(self, actor_ref: str, idempotency_key: str, digest: str) -> AppendBatchResult | None:
        key = f"{actor_ref}:{idempotency_key}"
        record = self._store.get_idempotency_record(self._PRINCIPAL, key)
        if record is None:
            return None
        if record.payload_digest != digest:
            raise EquipmentRuntimeError("idempotency_key_reused")
        result = self._store.get_by_idempotency(self._PRINCIPAL, key)
        if result is None:
            raise EquipmentRuntimeError("equipment_container_idempotency_missing_result")
        return result.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)

    def _require_destination_capacity(
        self,
        inventory: InventoryProjection,
        container_id: str,
        candidate: InventoryItem,
    ) -> None:
        container = inventory.containers[container_id]
        definition = self._inventory_registry.item(candidate.definition_id)
        if definition.is_living and not container.allows_living_items:
            raise EquipmentRuntimeError("inventory_living_item_rejected")
        entries = [
            item
            for item_id, item in inventory.items.items()
            if inventory.locations.get(item_id) == container_id and item_id != candidate.item_id
        ]
        weight = sum(
            self._inventory_registry.item(item.definition_id).unit_weight * item.quantity
            for item in entries
        ) + definition.unit_weight * candidate.quantity
        volume = sum(
            self._inventory_registry.item(item.definition_id).unit_volume * item.quantity
            for item in entries
        ) + definition.unit_volume * candidate.quantity
        if (
            len(entries) + 1 > container.capacity_slots
            or weight > container.capacity_weight
            or volume > container.capacity_volume
        ):
            raise EquipmentRuntimeError("inventory_capacity_exceeded")


def _event(
    command_id: str,
    transaction_id: str,
    stream_id: str,
    event_type: str,
    index: int,
    causation_id: str,
    correlation_id: str,
    payload: dict[str, object],
) -> dict[str, object]:
    return {
        "event_id": f"evt:{command_id}:equipment:{index}",
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
        "payload": payload,
    }


def _text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise EquipmentRuntimeError("equipment_event_payload_invalid")
    return value


def _text_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or any(not isinstance(item, str) or not item for item in value):
        raise EquipmentRuntimeError("equipment_event_payload_invalid")
    return tuple(value)


def _digest(value: object) -> str:
    def default(item: object) -> object:
        if isinstance(item, Mapping):
            return dict(item)
        if hasattr(item, "__dict__"):
            return item.__dict__
        raise TypeError(type(item).__name__)

    return sha256(json.dumps(value, default=default, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _inventory_stream(actor_ref: str) -> str:
    return f"gameplay:inventory:{actor_ref}"


def _equipment_stream(actor_ref: str) -> str:
    return f"gameplay:equipment:{actor_ref}"


def _ability_stream(actor_ref: str) -> str:
    return f"gameplay:abilities:{actor_ref}"


def _modifier_stream(actor_ref: str) -> str:
    return f"gameplay:modifiers:{actor_ref}"


def _body_stream(actor_ref: str) -> str:
    return f"gameplay:body:{actor_ref}"


def _equipment_location(slot_key: str) -> str:
    return f"equipment:{slot_key}"


def _occupied_slot_keys(requested_slot_key: str, profile: EquipmentProfile) -> tuple[str, ...]:
    return tuple(dict.fromkeys((requested_slot_key, *profile.required_slot_keys)))


__all__ = [
    "EquipmentActivation",
    "EquipmentAuthorityService",
    "EquipmentContainerAccessAuthority",
    "EquipmentDefinitionRegistry",
    "EquipmentProfile",
    "EquipmentProjector",
    "EquipmentProjection",
    "EquipmentRuntimeError",
    "EquipmentSlotDefinition",
]
