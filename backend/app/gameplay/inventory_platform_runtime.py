"""Owner-local generic Inventory platform runtime."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping, Sequence

from pydantic import ConfigDict, Field

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import InventoryAuthorityService, InventoryDefinitionRegistry
from app.gameplay.models import AppendBatchResult, OwnerAuthorizedFragment, StrictGameplayModel
from app.gameplay.settlement_plan import build_atomic_event_batch, build_multi_stream_atomic_event_batch
from app.gameplay.shared_contracts import SettlementReceipt


class InventoryPlatformError(ValueError):
    pass


class ItemInstanceRecord(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    item_ref: str = Field(min_length=1)
    definition_ref: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    stackable: bool = True
    source_event_ref: str = Field(min_length=1)


class InventoryLotRecord(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    lot_ref: str = Field(min_length=1)
    definition_ref: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    quality_ref: str = Field(min_length=1)
    provenance_refs: tuple[str, ...] = ()
    expiry_tick: int | None = Field(default=None, ge=0)
    reservation_refs: tuple[str, ...] = ()


class ContainerRecord(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    container_ref: str = Field(min_length=1)
    holder_ref: str = Field(min_length=1)
    parent_container_ref: str | None = None
    capacity_units: int = Field(gt=0)
    used_units: int = Field(ge=0)
    weight_limit: int = Field(gt=0)
    used_weight: int = Field(ge=0)
    sealed: bool = False
    lifecycle_status: Literal["open", "sealed", "retired"] = "open"


class CustodyRecord(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    asset_ref: str = Field(min_length=1)
    holder_ref: str = Field(min_length=1)
    container_ref: str = Field(min_length=1)
    status: Literal["held", "stored", "in_transit", "consumed", "destroyed"] = "stored"
    revision: int = Field(ge=0)
    source_event_ref: str = Field(min_length=1)


class ReservationRecord(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    reservation_ref: str = Field(min_length=1)
    asset_ref: str = Field(min_length=1)
    reservation_kind: Literal["quantity", "capacity", "custody"]
    quantity: int = Field(gt=0)
    purpose_ref: str = Field(min_length=1)
    owner_ref: str = Field(min_length=1)
    source_event_ref: str = Field(min_length=1)
    expected_revision: int = Field(ge=0)
    status: Literal["open", "consumed", "released", "expired"] = "open"


class InventoryPlatformProjection:
    def __init__(self, *, instances: Mapping[str, ItemInstanceRecord] | None = None, lots: Mapping[str, InventoryLotRecord] | None = None, containers: Mapping[str, ContainerRecord] | None = None, custody: Mapping[str, CustodyRecord] | None = None, reservations: Mapping[str, ReservationRecord] | None = None, source_revision_vector: Mapping[str, int] | None = None, applied_event_ids: Sequence[str] = (), last_global_sequence: int = 0) -> None:
        self.instances = MappingProxyType(dict(instances or {}))
        self.lots = MappingProxyType(dict(lots or {}))
        self.containers = MappingProxyType(dict(containers or {}))
        self.custody = MappingProxyType(dict(custody or {}))
        self.reservations = MappingProxyType(dict(reservations or {}))
        self.source_revision_vector = MappingProxyType(dict(source_revision_vector or {}))
        self.applied_event_ids = tuple(applied_event_ids)
        self.last_global_sequence = last_global_sequence

    def to_state(self) -> dict[str, object]:
        return {"instances": {k: v.model_dump(mode="json") for k, v in self.instances.items()}, "lots": {k: v.model_dump(mode="json") for k, v in self.lots.items()}, "containers": {k: v.model_dump(mode="json") for k, v in self.containers.items()}, "custody": {k: v.model_dump(mode="json") for k, v in self.custody.items()}, "reservations": {k: v.model_dump(mode="json") for k, v in self.reservations.items()}, "source_revision_vector": dict(self.source_revision_vector), "applied_event_ids": list(self.applied_event_ids), "last_global_sequence": self.last_global_sequence}


@dataclass(frozen=True)
class InventoryWriteResult:
    committed: bool
    zero_write: bool
    error_code: str | None = None
    append_result: AppendBatchResult | None = None


class InventoryPlatformProjector:
    projector_id = "inventory-platform"
    projector_version = "1"

    def rebuild(self, events: Sequence[object], *, checkpoint: InventoryPlatformProjection | None = None) -> InventoryPlatformProjection:
        projection = checkpoint or InventoryPlatformProjection()
        instances, lots, containers, custody, reservations = map(dict, (projection.instances, projection.lots, projection.containers, projection.custody, projection.reservations))
        revisions = dict(projection.source_revision_vector)
        applied = list(projection.applied_event_ids)
        last_sequence = projection.last_global_sequence
        for event in sorted((e for e in events if getattr(e, "event_id", None)), key=lambda e: (e.global_sequence, e.event_id)):
            if not event.stream_id.startswith("gameplay:inventory:platform:") or event.event_id in applied:
                continue
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
            last_sequence = max(last_sequence, event.global_sequence)
            payload = dict(event.payload)
            typ = event.event_type
            if typ == "gameplay.inventory.item_instantiated@1":
                value = ItemInstanceRecord.model_validate(payload["record"]); instances[value.item_ref] = value
            elif typ == "gameplay.inventory.lot_created@1":
                value = InventoryLotRecord.model_validate(payload["record"]); lots[value.lot_ref] = value
            elif typ == "gameplay.inventory.container_recorded@1":
                value = ContainerRecord.model_validate(payload["record"]); containers[value.container_ref] = value
            elif typ in {"gameplay.inventory.custody_recorded@1", "gameplay.inventory.custody_transferred@1", "gameplay.inventory.custody_consumed@1", "gameplay.inventory.custody_lost@1", "gameplay.inventory.custody_rejected@1"}:
                value = CustodyRecord.model_validate(payload["record"]); custody[value.asset_ref] = value
            elif typ in {"gameplay.inventory.reservation_opened@1", "gameplay.inventory.reservation_consumed@1", "gameplay.inventory.reservation_released@1", "gameplay.inventory.reservation_expired@1"}:
                value = ReservationRecord.model_validate(payload["record"]); reservations[value.reservation_ref] = value
            elif typ == "gameplay.inventory.lot_split@1":
                parent = InventoryLotRecord.model_validate(payload["parent"]); child = InventoryLotRecord.model_validate(payload["child"]); lots[parent.lot_ref] = parent; lots[child.lot_ref] = child
            elif typ == "gameplay.inventory.lot_merged@1":
                merged = InventoryLotRecord.model_validate(payload["merged"]); lots[merged.lot_ref] = merged
                for ref in payload.get("retired_lot_refs", ()): lots.pop(str(ref), None)
            applied.append(event.event_id)
        return InventoryPlatformProjection(instances=dict(sorted(instances.items())), lots=dict(sorted(lots.items())), containers=dict(sorted(containers.items())), custody=dict(sorted(custody.items())), reservations=dict(sorted(reservations.items())), source_revision_vector=dict(sorted(revisions.items())), applied_event_ids=applied, last_global_sequence=last_sequence)


class InventoryPlatformAuthority(InventoryAuthorityService):
    _PRINCIPAL = "actor_gameplay.inventory_domain"

    def __init__(self, *, store: GameplayEventStore) -> None:
        super().__init__(store=store, registry=InventoryDefinitionRegistry())
        self.store = store
        self.projector = InventoryPlatformProjector()

    def projection(self, *, checkpoint_at: int | None = None) -> InventoryPlatformProjection:
        events = self.store.read_events()
        if checkpoint_at is None: return self.projector.rebuild(events)
        checkpoint = self.projector.rebuild([e for e in events if e.global_sequence <= checkpoint_at])
        return self.projector.rebuild([e for e in events if e.global_sequence > checkpoint_at], checkpoint=checkpoint)

    @staticmethod
    def receipt_for(result: InventoryWriteResult) -> SettlementReceipt:
        if result.append_result is None:
            raise InventoryPlatformError("inventory_receipt_result_missing")
        return SettlementReceipt.from_append_result(result=result.append_result)

    # The generic projector intentionally does not reinterpret legacy payloads.
    # Keep inherited mutators out of this surface until their typed projections
    # are explicitly admitted.
    def move(self, **_: object) -> InventoryWriteResult:
        return InventoryWriteResult(False, True, "inventory_legacy_mutator_unadmitted")

    def instantiate(self, **_: object) -> InventoryWriteResult:
        return InventoryWriteResult(False, True, "inventory_legacy_mutator_unadmitted")

    def create_container(self, **_: object) -> InventoryWriteResult:
        return InventoryWriteResult(False, True, "inventory_legacy_mutator_unadmitted")

    def _commit(self, *, command_id: str, idempotency_key: str, subject_ref: str, expected_revision: int, event_type: str, payload: Mapping[str, object], causation_id: str, correlation_id: str, read_revisions: Mapping[str, int] | None = None) -> InventoryWriteResult:
        stream = f"gameplay:inventory:platform:{subject_ref}"
        if self.store.get_stream_head(stream) != expected_revision:
            return InventoryWriteResult(False, True, "revision_conflict")
        batch = build_atomic_event_batch(command_id=command_id, principal_ref=self._PRINCIPAL, stream_id=stream, expected_revision=expected_revision, event_specs=((event_type, dict(payload)),), idempotency_key=idempotency_key, causation_id=causation_id, correlation_id=correlation_id, read_stream_revisions=dict(read_revisions or {}))
        fragment = OwnerAuthorizedFragment(fragment_id=f"fragment:inventory-platform:{command_id}", owner_principal_ref=self._PRINCIPAL, source_rule_ref="inventory-platform:owner-local@1", expected_revisions={stream: expected_revision}, read_set_revisions=dict(read_revisions or {}), pinned_revisions={stream: expected_revision}, event_specs={stream: ((event_type, dict(payload)),)}, event_visibility_policies={stream: ("project",)})
        result = self.store.append_batch(batch.model_copy(update={"owner_fragments": [fragment]}, deep=True))
        return InventoryWriteResult(result.committed, not result.committed, result.failure.error_code if result.failure else None, result)

    def _commit_custody(self, *, command_id: str, idempotency_key: str, record: CustodyRecord, event_type: str, revisions: Mapping[str, int], causation_id: str, correlation_id: str) -> InventoryWriteResult:
        asset_stream = f"gameplay:inventory:platform:{record.asset_ref}"
        container_stream = f"gameplay:inventory:platform:{record.container_ref}"
        expected_revisions = {asset_stream: revisions[asset_stream], container_stream: revisions[container_stream]}
        payload = {"record": record.model_dump(mode="json")}
        batch = build_multi_stream_atomic_event_batch(command_id=command_id, principal_ref=self._PRINCIPAL, expected_revisions=expected_revisions, read_stream_revisions=expected_revisions, event_specs={asset_stream: ((event_type, payload),), container_stream: ((event_type, payload),)}, idempotency_key=idempotency_key, causation_id=causation_id, correlation_id=correlation_id, event_visibility_policies={asset_stream: ("project",), container_stream: ("project",)}, pinned_revisions=expected_revisions)
        fragment = OwnerAuthorizedFragment(fragment_id=f"fragment:inventory-platform:custody:{command_id}", owner_principal_ref=self._PRINCIPAL, source_rule_ref="inventory-platform:custody-atomic@1", expected_revisions=expected_revisions, read_set_revisions=expected_revisions, pinned_revisions=expected_revisions, event_specs={asset_stream: ((event_type, payload),), container_stream: ((event_type, payload),)}, event_visibility_policies={asset_stream: ("project",), container_stream: ("project",)})
        result = self.store.append_batch(batch.model_copy(update={"owner_fragments": [fragment]}, deep=True))
        return InventoryWriteResult(result.committed, not result.committed, result.failure.error_code if result.failure else None, result)

    def record_item(self, *, command_id: str, idempotency_key: str, record: ItemInstanceRecord, expected_revision: int, causation_id: str, correlation_id: str) -> InventoryWriteResult:
        return self._commit(command_id=command_id, idempotency_key=idempotency_key, subject_ref=record.item_ref, expected_revision=expected_revision, event_type="gameplay.inventory.item_instantiated@1", payload={"record": record.model_dump(mode="json")}, causation_id=causation_id, correlation_id=correlation_id)

    def record_lot(self, *, command_id: str, idempotency_key: str, record: InventoryLotRecord, expected_revision: int, causation_id: str, correlation_id: str) -> InventoryWriteResult:
        return self._commit(command_id=command_id, idempotency_key=idempotency_key, subject_ref=record.lot_ref, expected_revision=expected_revision, event_type="gameplay.inventory.lot_created@1", payload={"record": record.model_dump(mode="json")}, causation_id=causation_id, correlation_id=correlation_id)

    def record_container(self, *, command_id: str, idempotency_key: str, record: ContainerRecord, expected_revision: int, causation_id: str, correlation_id: str) -> InventoryWriteResult:
        projection = self.projection()
        if record.parent_container_ref and (record.parent_container_ref == record.container_ref or record.parent_container_ref not in projection.containers): return InventoryWriteResult(False, True, "container_parent_invalid")
        seen = {record.container_ref}; parent = record.parent_container_ref
        while parent is not None:
            if parent in seen: return InventoryWriteResult(False, True, "container_cycle")
            seen.add(parent)
            parent_record = projection.containers.get(parent)
            parent = parent_record.parent_container_ref if parent_record is not None else None
        if record.used_units > record.capacity_units or record.used_weight > record.weight_limit: return InventoryWriteResult(False, True, "container_capacity_exceeded")
        return self._commit(command_id=command_id, idempotency_key=idempotency_key, subject_ref=record.container_ref, expected_revision=expected_revision, event_type="gameplay.inventory.container_recorded@1", payload={"record": record.model_dump(mode="json")}, causation_id=causation_id, correlation_id=correlation_id)

    def record_custody(self, *, command_id: str, idempotency_key: str, record: CustodyRecord, expected_revision: int, causation_id: str, correlation_id: str) -> InventoryWriteResult:
        projection = self.projection()
        if record.asset_ref not in projection.instances and record.asset_ref not in projection.lots:
            return InventoryWriteResult(False, True, "custody_asset_missing")
        prior = projection.custody.get(record.asset_ref)
        if prior is not None and prior.revision >= record.revision:
            return InventoryWriteResult(False, True, "custody_revision_conflict")
        container = projection.containers.get(record.container_ref)
        if container is None or container.lifecycle_status == "retired" or container.sealed:
            return InventoryWriteResult(False, True, "custody_container_unavailable")
        occupancy = sum(1 for item in projection.custody.values() if item.asset_ref != record.asset_ref and item.container_ref == record.container_ref and item.status in {"held", "stored", "in_transit"})
        if occupancy >= container.capacity_units:
            return InventoryWriteResult(False, True, "custody_capacity_exceeded")
        container_stream = f"gameplay:inventory:platform:{record.container_ref}"
        asset_stream = f"gameplay:inventory:platform:{record.asset_ref}"
        revisions = {asset_stream: projection.source_revision_vector.get(asset_stream, 0), container_stream: projection.source_revision_vector.get(container_stream, 0)}
        if revisions[container_stream] != expected_revision:
            return InventoryWriteResult(False, True, "revision_conflict")
        return self._commit_custody(command_id=command_id, idempotency_key=idempotency_key, record=record, event_type="gameplay.inventory.custody_recorded@1", revisions=revisions, causation_id=causation_id, correlation_id=correlation_id)

    def transfer_custody(self, *, command_id: str, idempotency_key: str, record: CustodyRecord, expected_revision: int, causation_id: str, correlation_id: str) -> InventoryWriteResult:
        projection = self.projection(); asset_stream = f"gameplay:inventory:platform:{record.asset_ref}"; container_stream = f"gameplay:inventory:platform:{record.container_ref}"
        revisions = {asset_stream: projection.source_revision_vector.get(asset_stream, 0), container_stream: projection.source_revision_vector.get(container_stream, 0)}
        if revisions[container_stream] != expected_revision:
            return InventoryWriteResult(False, True, "revision_conflict")
        return self._commit_custody(command_id=command_id, idempotency_key=idempotency_key, record=record, event_type="gameplay.inventory.custody_transferred@1", revisions=revisions, causation_id=causation_id, correlation_id=correlation_id)

    def consume_custody(self, *, command_id: str, idempotency_key: str, asset_ref: str, expected_revision: int, causation_id: str, correlation_id: str) -> InventoryWriteResult:
        projection = self.projection()
        current = projection.custody.get(asset_ref)
        if current is None or current.status not in {"held", "stored"}:
            return InventoryWriteResult(False, True, "custody_consume_invalid")
        asset_stream = f"gameplay:inventory:platform:{asset_ref}"; container_stream = f"gameplay:inventory:platform:{current.container_ref}"
        revisions = {asset_stream: projection.source_revision_vector.get(asset_stream, 0), container_stream: projection.source_revision_vector.get(container_stream, 0)}
        if revisions[container_stream] != expected_revision:
            return InventoryWriteResult(False, True, "revision_conflict")
        record = current.model_copy(update={"status": "consumed", "revision": current.revision + 1})
        return self._commit_custody(command_id=command_id, idempotency_key=idempotency_key, record=record, event_type="gameplay.inventory.custody_consumed@1", revisions=revisions, causation_id=causation_id, correlation_id=correlation_id)

    def open_reservation(self, *, command_id: str, idempotency_key: str, record: ReservationRecord, expected_revision: int, causation_id: str, correlation_id: str) -> InventoryWriteResult:
        projection = self.projection()
        if record.asset_ref not in projection.instances and record.asset_ref not in projection.lots:
            return InventoryWriteResult(False, True, "reservation_asset_missing")
        if record.reservation_ref in projection.reservations: return InventoryWriteResult(False, True, "reservation_duplicate")
        if record.reservation_kind == "quantity":
            lot = projection.lots.get(record.asset_ref)
            reserved = sum(r.quantity for r in projection.reservations.values() if r.asset_ref == record.asset_ref and r.status == "open")
            if lot is None or reserved + record.quantity > lot.quantity: return InventoryWriteResult(False, True, "reservation_quantity_exceeded")
        return self._commit(command_id=command_id, idempotency_key=idempotency_key, subject_ref=record.asset_ref, expected_revision=expected_revision, event_type="gameplay.inventory.reservation_opened@1", payload={"record": record.model_dump(mode="json")}, causation_id=causation_id, correlation_id=correlation_id)

    def transition_reservation(self, *, command_id: str, idempotency_key: str, reservation_ref: str, status: Literal["consumed", "released", "expired"], expected_revision: int, causation_id: str, correlation_id: str) -> InventoryWriteResult:
        current = self.projection().reservations.get(reservation_ref)
        if current is None or current.status != "open":
            return InventoryWriteResult(False, True, "reservation_state_invalid")
        record = current.model_copy(update={"status": status})
        return self._commit(command_id=command_id, idempotency_key=idempotency_key, subject_ref=current.asset_ref, expected_revision=expected_revision, event_type=f"gameplay.inventory.reservation_{status}@1", payload={"record": record.model_dump(mode="json")}, causation_id=causation_id, correlation_id=correlation_id)

    def split_lot(self, *, command_id: str, idempotency_key: str, parent_lot_ref: str, child_lot_ref: str, quantity: int, expected_revision: int, causation_id: str, correlation_id: str) -> InventoryWriteResult:
        projection = self.projection(); parent = projection.lots.get(parent_lot_ref)
        if parent is None or quantity <= 0 or quantity >= parent.quantity or child_lot_ref in projection.lots: return InventoryWriteResult(False, True, "lot_split_invalid")
        child = parent.model_copy(update={"lot_ref": child_lot_ref, "quantity": quantity, "provenance_refs": tuple((*parent.provenance_refs, parent_lot_ref))})
        reduced = parent.model_copy(update={"quantity": parent.quantity - quantity})
        return self._commit(command_id=command_id, idempotency_key=idempotency_key, subject_ref=parent_lot_ref, expected_revision=expected_revision, event_type="gameplay.inventory.lot_split@1", payload={"parent": reduced.model_dump(mode="json"), "child": child.model_dump(mode="json"), "parent_lot_ref": parent_lot_ref}, causation_id=causation_id, correlation_id=correlation_id)

    def merge_lots(self, *, command_id: str, idempotency_key: str, first_lot_ref: str, second_lot_ref: str, merged_lot_ref: str, expected_revision: int, causation_id: str, correlation_id: str) -> InventoryWriteResult:
        projection = self.projection(); first, second = projection.lots.get(first_lot_ref), projection.lots.get(second_lot_ref)
        if first is None or second is None or first.definition_ref != second.definition_ref or first.quality_ref != second.quality_ref or first.expiry_tick != second.expiry_tick or merged_lot_ref in projection.lots: return InventoryWriteResult(False, True, "lot_merge_incompatible")
        merged = first.model_copy(update={"lot_ref": merged_lot_ref, "quantity": first.quantity + second.quantity, "provenance_refs": tuple(sorted(set((*first.provenance_refs, *second.provenance_refs, first_lot_ref, second_lot_ref))))})
        read_revisions = {
            f"gameplay:inventory:platform:{first_lot_ref}": projection.source_revision_vector.get(f"gameplay:inventory:platform:{first_lot_ref}", 0),
            f"gameplay:inventory:platform:{second_lot_ref}": projection.source_revision_vector.get(f"gameplay:inventory:platform:{second_lot_ref}", 0),
        }
        return self._commit(command_id=command_id, idempotency_key=idempotency_key, subject_ref=merged_lot_ref, expected_revision=expected_revision, event_type="gameplay.inventory.lot_merged@1", payload={"merged": merged.model_dump(mode="json"), "retired_lot_refs": [first_lot_ref, second_lot_ref]}, causation_id=causation_id, correlation_id=correlation_id, read_revisions=read_revisions)


__all__ = ["ContainerRecord", "CustodyRecord", "InventoryLotRecord", "InventoryPlatformAuthority", "InventoryPlatformError", "InventoryPlatformProjection", "InventoryPlatformProjector", "InventoryWriteResult", "ItemInstanceRecord", "ReservationRecord"]
