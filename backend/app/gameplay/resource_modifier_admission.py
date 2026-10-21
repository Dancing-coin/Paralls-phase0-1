"""本次设计并实现: canonical Equipment-to-Resource modifier admission.

The equipment transaction remains source truth; this bridge writes only the
existing ResourceBody ledger and receipts in the shared event store.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path

import yaml

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayEvent
from app.gameplay.modifier_runtime import ModifierDefinitionRegistry, ModifierTemplate
from app.gameplay.resource_body_runtime import ResourceBodyRuntimeProjector, ResourceDefinitionRegistry
from app.gameplay.settlement_plan import build_multi_stream_atomic_event_batch


EQUIPMENT_PRINCIPAL = "actor_gameplay.equipment_domain"
BRIDGE_PRINCIPAL = "resource_modifier_bridge"
CONTENT_PATH = Path(__file__).resolve().parents[3] / "assets/gameplay/resource-equipment/mana-focus-charm.v1.yaml"


def _digest(value: object) -> str:
    return "sha256:" + sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class ResourceModifierMapping:
    template_id: str
    revision: str
    resource_id: str
    operation: str
    amount: int
    stat_id: str

    @property
    def digest(self) -> str:
        return _digest(asdict(self))


class ResourceModifierMappingRegistry:
    """Immutable explicit mappings; registration order never selects a policy."""

    def __init__(self) -> None:
        self._mappings: dict[str, ResourceModifierMapping] = {}

    def register(self, mapping: ResourceModifierMapping) -> None:
        if mapping.template_id in self._mappings or mapping.operation not in {"capacity_delta", "recovery_delta"} or type(mapping.amount) is not int or "@" not in mapping.revision or "@" not in mapping.template_id:
            raise ValueError("resource_modifier_mapping_invalid")
        self._mappings[mapping.template_id] = mapping

    def resolve(self, template_id: str) -> ResourceModifierMapping:
        try:
            return self._mappings[template_id]
        except KeyError as exc:
            raise ValueError("resource_modifier_mapping_unknown") from exc

    def contains(self, template_id: str) -> bool:
        return template_id in self._mappings


def register_mana_focus_content(*, inventory, equipment, modifiers: ModifierDefinitionRegistry, mappings: ResourceModifierMappingRegistry, raw: bytes | None = None) -> dict[str, object]:
    """Load the formal authored item/profile/template/mapping into existing registries."""
    from app.gameplay.inventory_runtime import ItemDefinition, InventoryRuntimeError
    from app.gameplay.equipment_runtime import EquipmentProfile, EquipmentRuntimeError
    from app.gameplay.modifier_runtime import ModifierRuntimeError
    raw = CONTENT_PATH.read_bytes() if raw is None else raw
    content = yaml.safe_load(raw.decode("utf-8"))
    item, profile, modifier, mapping = (content[name] for name in ("item", "equipment", "modifier", "mapping"))
    item_definition = ItemDefinition(**item)
    profile_definition = EquipmentProfile(profile["profile_id"], (profile["slot_key"],), modifier_template_ids=(modifier["template_id"],))
    modifier_definition = ModifierTemplate(**{**modifier, "value": Decimal(modifier["value"])})
    mapping_definition = ResourceModifierMapping(modifier["template_id"], mapping["revision"], mapping["resource_id"], mapping["operation"], mapping["amount"], modifier["stat_id"])
    try:
        prior = inventory.item(item_definition.definition_id)
        if prior != item_definition:
            raise ValueError("resource_modifier_content_conflict")
    except InventoryRuntimeError:
        inventory.register_item(item_definition)
    try:
        prior = equipment.profile_for(item_definition.definition_id)
        if prior != profile_definition:
            raise ValueError("resource_modifier_content_conflict")
    except EquipmentRuntimeError:
        equipment.register_profile(item_definition.definition_id, profile_definition)
    try:
        prior = modifiers.template(modifier_definition.template_id)
        if prior != modifier_definition:
            raise ValueError("resource_modifier_content_conflict")
    except ModifierRuntimeError:
        modifiers.register_template(modifier_definition)
    if mappings.contains(mapping_definition.template_id):
        if mappings.resolve(mapping_definition.template_id) != mapping_definition:
            raise ValueError("resource_modifier_content_conflict")
    else:
        mappings.register(mapping_definition)
    return {"revision": content["revision"], "slot_key": profile["slot_key"], "raw": raw}


class ResourceModifierBridgeOwner:
    """Derive resource bridge events from persisted canonical equipment transactions."""

    def __init__(self, *, store: GameplayEventStore, mappings: ResourceModifierMappingRegistry, modifiers: ModifierDefinitionRegistry, definitions: ResourceDefinitionRegistry | None = None) -> None:
        self.store, self.mappings, self.modifiers = store, mappings, modifiers
        self.projector = ResourceBodyRuntimeProjector(resource_definitions=definitions)

    def _source(self, transaction_id: str):
        tx = self.store.get_transaction(transaction_id)
        if tx is None or tx.idempotency_record.principal_ref != EQUIPMENT_PRINCIPAL:
            raise ValueError("resource_modifier_source_authority_invalid")
        receipt = self.store.get_by_idempotency(EQUIPMENT_PRINCIPAL, tx.idempotency_record.idempotency_key)
        if receipt is None or not receipt.committed or receipt.transaction_id != transaction_id or receipt.committed_event_ids != [event.event_id for event in tx.events]:
            raise ValueError("resource_modifier_source_receipt_invalid")
        try:
            if any(self.store.get_event(event.event_id) != event or event.visibility_policy != "authority_only" or event.transaction_id != transaction_id or event.command_id != tx.command_id for event in tx.events):
                raise ValueError("resource_modifier_source_event_invalid")
        except KeyError as exc:
            raise ValueError("resource_modifier_source_event_invalid") from exc
        return tx

    def sync_equipment_transaction(self, transaction_id: str) -> tuple[AppendBatchResult, ...]:
        source = self._source(transaction_id)
        results = []
        for event in source.events:
            if event.event_type not in {"gameplay.modifier.source_activated", "gameplay.modifier.source_deactivated"}:
                continue
            results.append(self._apply_source(event))
        return tuple(results)

    def _activation(self, event: GameplayEvent) -> GameplayEvent:
        if event.event_type == "gameplay.modifier.source_activated":
            return event
        actor, instance = event.payload.get("actor_ref"), event.payload.get("modifier_instance_id")
        prior = [item for item in self.store.read_stream(event.stream_id) if item.global_sequence < event.global_sequence and item.event_type == "gameplay.modifier.source_activated" and item.payload.get("actor_ref") == actor and item.payload.get("modifier_instance_id") == instance]
        if not prior:
            raise ValueError("resource_modifier_source_activation_missing")
        return prior[-1]

    def _apply_source(self, event: GameplayEvent) -> AppendBatchResult:
        actor = event.payload.get("actor_ref")
        instance = event.payload.get("modifier_instance_id")
        if not isinstance(actor, str) or not isinstance(instance, str) or event.stream_id != f"gameplay:modifiers:{actor}":
            raise ValueError("resource_modifier_source_scope_invalid")
        source_tx = self._source(event.transaction_id)
        activation = self._activation(event)
        activation_tx = self._source(activation.transaction_id)
        template_id, source_ref = activation.payload.get("template_id"), activation.payload.get("source_ref")
        paired = [item for item in activation_tx.events if item.event_type == "gameplay.equipment.activation_started" and item.stream_id == f"gameplay:equipment:{actor}" and item.payload.get("actor_ref") == actor and item.payload.get("activation_id") == source_ref and instance in item.payload.get("modifier_instance_ids", [])]
        if len(paired) != 1 or any(item.payload.get("actor_ref") != actor for item in source_tx.events):
            raise ValueError("resource_modifier_source_activation_invalid")
        attaching = event.event_type == "gameplay.modifier.source_activated"
        if not attaching and not any(item.event_type == "gameplay.equipment.activation_ended" and item.payload.get("actor_ref") == actor and item.payload.get("activation_id") == source_ref for item in source_tx.events):
            raise ValueError("resource_modifier_source_deactivation_invalid")
        mapping = self.mappings.resolve(str(template_id))
        template = self.modifiers.template(str(template_id))
        if template.stat_id != mapping.stat_id or template.operation != "additive" or template.value != Decimal(mapping.amount) or template.condition_ref is not None:
            raise ValueError("resource_modifier_template_pin_mismatch")
        modifier = {"modifier_ref": instance, "template_id": template_id, "source_event_id": activation.event_id, "operation": mapping.operation, "amount": mapping.amount, "mapping_revision": mapping.revision}
        payload = {"actor_ref": actor, "resource_id": mapping.resource_id, "modifier": modifier, "mapping_digest": mapping.digest, "source_event_id": event.event_id, "source_transaction_id": event.transaction_id}
        key = event.event_id
        prior = self.store.get_by_idempotency(BRIDGE_PRINCIPAL, key)
        if prior is not None:
            if self.store.get_idempotency_record(BRIDGE_PRINCIPAL, key) is None:
                raise ValueError("resource_modifier_idempotency_reused")
            self._verify_receipt(prior, payload, event_type=f"gameplay.resource.modifier_{'attached' if attaching else 'detached'}", stream_id=f"gameplay:resources:{actor}", command_id=f"resource-bridge:{event.event_id}")
            return prior.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
        stream = f"gameplay:resources:{actor}"
        resource_events = self.store.read_stream(stream)
        projection = self.projector.rebuild_resources(actor, resource_events)
        entry = projection.entries.get(mapping.resource_id)
        if entry is None or entry.capacity is None:
            raise ValueError("resource_modifier_materialization_required")
        # The existing projector enforces duplicate, detach, reservation, and capacity invariants.
        event_type = f"gameplay.resource.modifier_{'attached' if attaching else 'detached'}"
        revision = projection.source_revision_vector.get(stream, 0)
        source_head = self.store.get_stream_head(event.stream_id)
        batch = build_multi_stream_atomic_event_batch(command_id=f"resource-bridge:{event.event_id}", principal_ref=BRIDGE_PRINCIPAL, expected_revisions={stream: revision}, event_specs={stream: [(event_type, payload)]}, idempotency_key=key, causation_id=event.event_id, correlation_id=event.correlation_id, read_stream_revisions={stream: revision, event.stream_id: source_head}, event_visibility_policies={stream: ["authority_only"]})
        self.projector.rebuild_resources(actor, batch.events, checkpoint=projection)
        return self.store.append_batch(batch)

    def _verify_receipt(self, receipt: AppendBatchResult, payload: dict, *, event_type: str, stream_id: str, command_id: str) -> None:
        tx = self.store.get_transaction(receipt.transaction_id)
        if (not receipt.committed or tx is None or tx.idempotency_record.principal_ref != BRIDGE_PRINCIPAL
                or tx.command_id != command_id or receipt.command_id != command_id
                or tx.idempotency_record.idempotency_key != payload["source_event_id"]
                or len(tx.events) != 1 or receipt.committed_event_ids != [event.event_id for event in tx.events]):
            raise ValueError("resource_modifier_receipt_incomplete")
        event = tx.events[0]
        try:
            valid = (self.store.get_event(event.event_id) == event and event.payload == payload
                     and event.event_type == event_type and event.stream_id == stream_id
                     and event.visibility_policy == "authority_only"
                     and receipt.resulting_stream_revisions == {event.stream_id: event.stream_revision}
                     and receipt.global_sequence_range == (event.global_sequence, event.global_sequence))
        except KeyError:
            valid = False
        if not valid:
            raise ValueError("resource_modifier_receipt_incomplete")
