"""Inventory-owned condition and transport custody lifecycle."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping, Sequence
from pydantic import ConfigDict, Field
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import InventoryAuthorityService, InventoryDefinitionRegistry
from app.gameplay.models import AppendBatchResult, OwnerAuthorizedFragment, StrictGameplayModel
from app.gameplay.settlement_plan import build_atomic_event_batch


class InventoryConditionTransportError(ValueError):
    pass


class ConditionRecord(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    asset_ref: str = Field(min_length=1)
    quality_basis_points: int = Field(ge=0, le=10_000)
    durability_basis_points: int = Field(ge=0, le=10_000)
    expires_at_tick: int | None = Field(default=None, ge=0)
    contamination_basis_points: int = Field(default=0, ge=0, le=10_000)
    policy_ref: str = Field(min_length=1)


class TransportRecord(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    transport_ref: str = Field(min_length=1)
    asset_ref: str = Field(min_length=1)
    source_container_ref: str = Field(min_length=1)
    destination_container_ref: str = Field(min_length=1)
    carrier_ref: str = Field(min_length=1)
    status: Literal["in_transit", "delivered", "lost", "rejected"]
    delivery_window_tick: int = Field(ge=0)
    policy_ref: str = Field(min_length=1)
    source_revision: int = Field(ge=0)


@dataclass(frozen=True)
class InventoryConditionTransportProjection:
    conditions: Mapping[str, ConditionRecord]
    transports: Mapping[str, TransportRecord]
    source_revision_vector: Mapping[str, int]


class InventoryConditionTransportProjector:
    def rebuild(self, events: Sequence[object], *, checkpoint: InventoryConditionTransportProjection | None = None) -> InventoryConditionTransportProjection:
        conditions = dict(checkpoint.conditions) if checkpoint else {}
        transports = dict(checkpoint.transports) if checkpoint else {}
        revisions = dict(checkpoint.source_revision_vector) if checkpoint else {}
        for event in sorted(events, key=lambda e: (e.global_sequence, e.event_id)):
            if not event.stream_id.startswith("gameplay:inventory:platform:condition:") and not event.stream_id.startswith("gameplay:inventory:platform:transport:"):
                continue
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
            if event.event_type == "gameplay.inventory.condition_recorded@1":
                record = ConditionRecord.model_validate(event.payload["record"]); conditions[record.asset_ref] = record
            elif event.event_type.startswith("gameplay.inventory.transport_"):
                record = TransportRecord.model_validate(event.payload["record"]); transports[record.transport_ref] = record
        return InventoryConditionTransportProjection(MappingProxyType(dict(sorted(conditions.items()))), MappingProxyType(dict(sorted(transports.items()))), MappingProxyType(dict(sorted(revisions.items()))))


class InventoryConditionTransportAuthority(InventoryAuthorityService):
    _PRINCIPAL = "actor_gameplay.inventory_domain"
    def __init__(self, *, store: GameplayEventStore) -> None:
        super().__init__(store=store, registry=InventoryDefinitionRegistry())
        self.store = store; self.projector = InventoryConditionTransportProjector()

    def move(self, **_: object) -> AppendBatchResult:
        return AppendBatchResult(committed=False, transaction_id="transaction:unadmitted", command_id="unadmitted", idempotency_status="rejected", failure={"error_code": "inventory_legacy_mutator_unadmitted", "message": "inventory_legacy_mutator_unadmitted", "failed_stage": "admission"})

    def _commit(self, *, command_id: str, idempotency_key: str, subject_ref: str, expected_revision: int, event_type: str, payload: Mapping[str, object], causation_id: str, correlation_id: str) -> AppendBatchResult:
        stream = f"gameplay:inventory:platform:{subject_ref}"
        batch = build_atomic_event_batch(command_id=command_id, principal_ref=self._PRINCIPAL, stream_id=stream, expected_revision=expected_revision, event_specs=((event_type, dict(payload)),), idempotency_key=idempotency_key, causation_id=causation_id, correlation_id=correlation_id)
        fragment = OwnerAuthorizedFragment(fragment_id=f"fragment:inventory-condition:{command_id}", owner_principal_ref=self._PRINCIPAL, source_rule_ref="inventory-condition-transport:owner-local@1", expected_revisions={stream: expected_revision}, read_set_revisions={stream: expected_revision}, pinned_revisions={stream: expected_revision}, event_specs={stream: ((event_type, dict(payload)),)}, event_visibility_policies={stream: ("project",)})
        return self.store.append_batch(batch.model_copy(update={"owner_fragments": [fragment]}, deep=True))

    def record_condition(self, *, command_id: str, idempotency_key: str, record: ConditionRecord, expected_revision: int, causation_id: str, correlation_id: str) -> AppendBatchResult:
        if not record.policy_ref.startswith("policy:"): raise InventoryConditionTransportError("inventory_condition_policy_invalid")
        return self._commit(command_id=command_id, idempotency_key=idempotency_key, subject_ref=f"condition:{record.asset_ref}", expected_revision=expected_revision, event_type="gameplay.inventory.condition_recorded@1", payload={"record": record.model_dump(mode="json")}, causation_id=causation_id, correlation_id=correlation_id)

    def begin_transport(self, *, command_id: str, idempotency_key: str, record: TransportRecord, expected_revision: int, causation_id: str, correlation_id: str) -> AppendBatchResult:
        if record.status != "in_transit": raise InventoryConditionTransportError("inventory_transport_initial_status_invalid")
        return self._commit(command_id=command_id, idempotency_key=idempotency_key, subject_ref=f"transport:{record.transport_ref}", expected_revision=expected_revision, event_type="gameplay.inventory.transport_in_transit@1", payload={"record": record.model_dump(mode="json")}, causation_id=causation_id, correlation_id=correlation_id)

    def transition_transport(self, *, command_id: str, idempotency_key: str, transport_ref: str, status: Literal["delivered", "lost", "rejected"], expected_revision: int, causation_id: str, correlation_id: str) -> AppendBatchResult:
        current = self.projector.rebuild(self.store.read_events()).transports.get(transport_ref)
        if current is None or current.status != "in_transit": raise InventoryConditionTransportError("inventory_transport_state_invalid")
        record = current.model_copy(update={"status": status})
        return self._commit(command_id=command_id, idempotency_key=idempotency_key, subject_ref=f"transport:{transport_ref}", expected_revision=expected_revision, event_type=f"gameplay.inventory.transport_{status}@1", payload={"record": record.model_dump(mode="json")}, causation_id=causation_id, correlation_id=correlation_id)


__all__ = ["ConditionRecord", "InventoryConditionTransportAuthority", "InventoryConditionTransportError", "InventoryConditionTransportProjection", "InventoryConditionTransportProjector", "TransportRecord"]
