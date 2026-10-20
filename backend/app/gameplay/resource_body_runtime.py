"""Backend-only resource and body-function projection for the first gameplay slice."""

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import json
import re
from types import MappingProxyType
from typing import Literal, Mapping

from pydantic import ConfigDict, Field

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayEvent, StrictGameplayModel


FunctionStatus = Literal["available", "impaired", "unavailable"]


class ResourceBodyRuntimeError(ValueError):
    """Raised when committed resource/body events cannot form a valid read model."""


class ResourceDefinition(StrictGameplayModel):
    """Narrow integer resource definition; decimal policies remain a later phase."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    resource_id: str = Field(min_length=1)
    definition_version: str = Field(min_length=1)
    minimum: int
    maximum: int
    resource_schema: Literal["legacy-v1", "resource.v2"] = "legacy-v1"
    capacity: int | None = None
    base_capacity: int | None = None
    debt_ceiling: int = 0

    def model_post_init(self, __context: object) -> None:
        if self.minimum > self.maximum:
            raise ValueError("resource_definition_bounds_invalid")
        if self.resource_schema == "legacy-v1" and any(
            value is not None for value in (self.capacity, self.base_capacity)
        ):
            raise ValueError("resource_definition_legacy_capacity_invalid")
        if self.resource_schema == "resource.v2":
            if self.capacity is None or self.base_capacity is None:
                raise ValueError("resource_definition_v2_capacity_required")
            capacity = self.capacity
            base_capacity = self.base_capacity
            if self.minimum != 0 or capacity < 0 or base_capacity < 0 or base_capacity > capacity or capacity < self.maximum:
                raise ValueError("resource_definition_v2_capacity_invalid")
        if self.debt_ceiling != 0:
            raise ValueError("resource_definition_debt_ceiling_invalid")


class ResourceDefinitionRegistry:
    """Immutable resource definitions retained for historical replay.

    The registry deliberately has no "latest" resolver.  A resource migration
    names both versions, and resource events carry the resulting version, so a
    future projector never has to infer policy from registration order.
    """

    def __init__(self) -> None:
        self._definitions: dict[str, dict[str, ResourceDefinition]] = {}

    def register(self, definition: ResourceDefinition) -> None:
        versions = self._definitions.setdefault(definition.resource_id, {})
        if definition.definition_version in versions:
            raise ResourceBodyRuntimeError("resource_definition_duplicate")
        versions[definition.definition_version] = definition

    def resolve(self, resource_id: str, definition_version: str) -> ResourceDefinition:
        try:
            return self._definitions[resource_id][definition_version]
        except KeyError as exc:
            raise ResourceBodyRuntimeError("resource_definition_unknown") from exc


RESOURCE_BOUNDS_CLAMP_MIGRATOR_ID = "resource.bounds.clamp_maximum.v1"
RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST = "sha256:" + sha256(
    RESOURCE_BOUNDS_CLAMP_MIGRATOR_ID.encode("utf-8")
).hexdigest()
RESOURCE_V2_POLICY_MIGRATOR_ID = "resource.v2.policy.rebind.v1"
RESOURCE_V2_POLICY_MIGRATOR_CODE_DIGEST = "sha256:" + sha256(
    RESOURCE_V2_POLICY_MIGRATOR_ID.encode("utf-8")
).hexdigest()
RESOURCE_MATERIALIZED_SCHEMA_DIGEST = "schema:resource-materialized:v1"
RESOURCE_BOUNDS_MIGRATED_SCHEMA_DIGEST = "schema:resource-bounds-migrated:v1"


class ResourceBoundsMigrationRequest(StrictGameplayModel):
    """Pinned inputs for the first data-transform migration policy.

    This is intentionally a narrow domain contract: it can only lower a
    resource maximum, clamps the current value explicitly, and rejects all
    outstanding reservations.  It is not a generic projection mutation API.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_ref: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    from_definition_version: str = Field(min_length=1)
    to_definition_version: str = Field(min_length=1)
    expected_projection_revision: str = Field(min_length=1)
    migration_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    migrator_code_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True)
class ResourceBoundsMigrationPlan:
    actor_ref: str
    resource_id: str
    expected_stream_revision: int
    event_type: str
    payload: Mapping[str, object]
    result_digest: str


@dataclass(frozen=True)
class ResourceEntry:
    resource_id: str
    definition_version: str
    current: int
    minimum: int
    maximum: int
    source_event_id: str
    reserved: int = 0
    # v2 bounded-resource semantics. Legacy events leave these at their
    # compatibility values and are never implicitly upgraded.
    capacity: int | None = None
    base_capacity: int | None = None
    locked: int = 0
    debt: int = 0
    debt_ceiling: int = 0
    modifier_ledger_digest: str | None = None
    modifier_ledger: tuple[Mapping[str, object], ...] = ()

    @property
    def available(self) -> int:
        return self.current - self.reserved


@dataclass(frozen=True)
class ResourceStateProjection:
    actor_ref: str
    entries: Mapping[str, ResourceEntry]
    reservations: Mapping[str, tuple[str, int]]
    source_revision_vector: Mapping[str, int]
    projection_revision: str
    locks: Mapping[str, tuple[str, str, int, str]] = MappingProxyType({})


@dataclass(frozen=True)
class BodyInjury:
    injury_id: str
    function_id: str
    capacity_ratio: int
    source_event_id: str


@dataclass(frozen=True)
class FunctionalCapacity:
    function_id: str
    capacity_ratio: int
    status: FunctionStatus
    contributing_source_refs: tuple[str, ...]


@dataclass(frozen=True)
class BodyRuntimeProjection:
    actor_ref: str
    injuries: Mapping[str, BodyInjury]
    functions: Mapping[str, FunctionalCapacity]
    source_revision_vector: Mapping[str, int]
    projection_revision: str


class GameplayActionRequirement(StrictGameplayModel):
    """The gameplay gate consumes stable action facts; it does not own skill grants."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    action_ref: str = Field(min_length=1)
    stamina_resource_id: str = Field(min_length=1)
    stamina_cost: int = Field(gt=0)
    required_function_id: str = Field(min_length=1)


class GameplayActionSettlementCommand(StrictGameplayModel):
    """Trusted backend command for this narrow resource/body settlement path."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    command_id: str = Field(min_length=1)
    actor_ref: str = Field(min_length=1)
    authority_principal: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    payload_digest: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    requirement: GameplayActionRequirement


@dataclass(frozen=True)
class GameplayActionSettlementResult:
    accepted: bool
    reason_code: str | None
    blocked_source_refs: tuple[str, ...]
    append_result: AppendBatchResult | None = None


class ResourceReservationCommand(StrictGameplayModel):
    """Trusted backend reservation command; no client or Godot route owns it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    command_id: str = Field(min_length=1)
    actor_ref: str = Field(min_length=1)
    authority_principal: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    payload_digest: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    operation: Literal["reserve", "consume", "release"]
    resource_id: str = Field(min_length=1)
    reservation_ref: str = Field(min_length=1)
    amount: int | None = Field(default=None, gt=0)
    lock_ref: str | None = None


class ResourceReservationAuthorityService:
    """Appends explicit reservation events after validating the current read model."""

    _PRINCIPAL = "resource_reservation_authority"

    def __init__(self, *, store: GameplayEventStore, authority_principal: str = "gameplay_authority") -> None:
        self._store = store
        self._authority_principal = authority_principal

    def apply(self, command: ResourceReservationCommand, resources: ResourceStateProjection) -> AppendBatchResult:
        if command.authority_principal != self._authority_principal or resources.actor_ref != command.actor_ref:
            raise ValueError("resource_reservation_authority_mismatch")
        stream_id = _resource_stream(command.actor_ref)
        key = f"{command.actor_ref}:{command.idempotency_key}"
        command_digest = "sha256:" + _digest(command.model_dump(mode="json"))
        record = self._store.get_idempotency_record(self._PRINCIPAL, key)
        if record is not None:
            result = self._store.get_by_idempotency(self._PRINCIPAL, key)
            if result is None:
                raise ValueError("resource_reservation_receipt_unavailable")
            if record.payload_digest != command_digest:
                raise ValueError("idempotency_key_reused")
            expected_type = {
                "reserve": "gameplay.resource.reservation_created",
                "consume": "gameplay.resource.reservation_consumed",
                "release": "gameplay.resource.reservation_released",
            }[command.operation]
            if not self._reservation_receipt_is_complete(
                result, command=command, stream_id=stream_id,
                expected_type=expected_type,
            ):
                raise ValueError("resource_reservation_receipt_incomplete")
            return result.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
        resource_revision = resources.source_revision_vector.get(stream_id, 0)
        if resource_revision != self._store.get_stream_head(stream_id):
            raise ValueError("state_revision_conflict")
        entry = resources.entries.get(command.resource_id)
        if entry is None:
            raise ValueError("resource_not_registered")
        if command.operation == "reserve":
            control_stream = f"gameplay:resource-migration-control:{command.actor_ref}"
            control_revision = self._store.get_stream_head(control_stream)
            if _migration_is_paused(self._store.read_stream(control_stream)):
                raise ValueError("resource_reservation_paused_for_migration")
            is_v2 = entry.capacity is not None
            if is_v2 and not command.lock_ref:
                raise ValueError("resource_lock_required")
            if not is_v2 and command.lock_ref:
                raise ValueError("resource_lock_not_supported")
            if command.amount is None or entry.available < command.amount:
                raise ValueError("resource_insufficient")
            if is_v2 and command.lock_ref in resources.locks:
                raise ValueError("resource_lock_reused")
            event_type, payload = "gameplay.resource.reservation_created", {"actor_ref": command.actor_ref, "resource_id": command.resource_id, "reservation_ref": command.reservation_ref, "amount": command.amount}
            if is_v2:
                payload["lock_ref"] = command.lock_ref
            event_specs = [(event_type, payload)]
            if is_v2:
                event_specs.append(("gameplay.resource.lock_created", {"actor_ref": command.actor_ref, "resource_id": command.resource_id, "reservation_ref": command.reservation_ref, "lock_ref": command.lock_ref, "amount": command.amount}))
        else:
            reservation = resources.reservations.get(command.reservation_ref)
            if reservation is None or reservation[0] != command.resource_id:
                raise ValueError("resource_reservation_unknown")
            entry = resources.entries[command.resource_id]
            is_v2 = entry.capacity is not None
            if not is_v2 and command.lock_ref:
                raise ValueError("resource_lock_not_supported")
            lock = resources.locks.get(command.lock_ref or "")
            if is_v2 and (not command.lock_ref or lock is None or lock[:3] != (command.reservation_ref, command.resource_id, reservation[1]) or lock[3] != "open"):
                raise ValueError("resource_lock_unknown")
            event_type = "gameplay.resource.reservation_consumed" if command.operation == "consume" else "gameplay.resource.reservation_released"
            payload = {"actor_ref": command.actor_ref, "resource_id": command.resource_id, "reservation_ref": command.reservation_ref,
                       "amount": reservation[1]}
            if is_v2:
                payload["lock_ref"] = command.lock_ref
            event_specs = [(event_type, payload)]
            if is_v2:
                event_specs.append((f"gameplay.resource.lock_{command.operation}d", {"actor_ref": command.actor_ref, "resource_id": command.resource_id, "reservation_ref": command.reservation_ref, "lock_ref": command.lock_ref, "amount": reservation[1]}))
        transaction_id = f"tx:{command.command_id}"
        # Keep the projection revision that was validated above.  Reading the
        # head again here would allow a concurrent resource write to slip
        # between validation and append.
        expected_revisions = {stream_id: resource_revision}
        read_revisions = {stream_id: resource_revision}
        if command.operation == "reserve":
            read_revisions[control_stream] = control_revision
        events = [{"event_id": f"evt:{command.command_id}:{index}", "event_type": event_kind, "schema_version": 1, "stream_id": stream_id, "stream_revision": 0, "global_sequence": 0, "transaction_id": transaction_id, "command_id": command.command_id, "causation_id": command.causation_id, "correlation_id": command.correlation_id, "visibility_policy": "authority_only", "payload": event_payload} for index, (event_kind, event_payload) in enumerate(event_specs)]
        return self._store.append_batch({"transaction_id": transaction_id, "command_id": command.command_id, "expected_stream_revisions": expected_revisions, "read_stream_revisions": read_revisions, "pinned_revisions": {}, "events": events, "idempotency_record": {"principal_ref": self._PRINCIPAL, "idempotency_key": key, "payload_digest": command_digest}, "outbox_entries": [], "result_digest": "sha256:" + _digest(payload), "projection_refresh_hints": []})

    def _reservation_receipt_is_complete(
        self,
        result: AppendBatchResult,
        *,
        command: ResourceReservationCommand,
        stream_id: str,
        expected_type: str,
    ) -> bool:
        if not result.committed or result.failure is not None:
            return False
        transaction = self._store.get_transaction(result.transaction_id)
        receipt_key = f"{command.actor_ref}:{command.idempotency_key}"
        if transaction is None or transaction.command_id != command.command_id:
            return False
        if (
            transaction.transaction_id != result.transaction_id
            or transaction.idempotency_record.principal_ref != self._PRINCIPAL
            or transaction.idempotency_record.idempotency_key != receipt_key
            or transaction.idempotency_record.payload_digest
            != "sha256:" + _digest(command.model_dump(mode="json"))
            or transaction.expected_stream_revisions.get(stream_id)
            != transaction.read_stream_revisions.get(stream_id)
        ):
            return False
        if command.operation == "reserve":
            control_stream = f"gameplay:resource-migration-control:{command.actor_ref}"
            if control_stream not in transaction.read_stream_revisions:
                return False
        elif set(transaction.read_stream_revisions) != {stream_id}:
            return False
        events = transaction.events
        expected_count = 2 if command.lock_ref is not None else 1
        if len(events) != expected_count or result.committed_event_ids != [event.event_id for event in events]:
            return False
        event = events[0]
        payload = event.payload
        if (
            event.event_type != expected_type
            or event.schema_version != 1
            or event.stream_id != stream_id
            or event.transaction_id != result.transaction_id
            or event.command_id != command.command_id
            or event.causation_id != command.causation_id
            or event.correlation_id != command.correlation_id
            or event.visibility_policy != "authority_only"
            or payload.get("actor_ref") != command.actor_ref
            or payload.get("resource_id") != command.resource_id
            or payload.get("reservation_ref") != command.reservation_ref
            or (command.operation == "reserve" and payload.get("amount") != command.amount)
        ):
            return False
        if transaction.result_digest != "sha256:" + _digest(dict(payload)):
            return False
        if command.lock_ref is not None:
            lock_event = events[1]
            if (
                lock_event.event_type != f"gameplay.resource.lock_{'created' if command.operation == 'reserve' else command.operation + 'd'}"
                or lock_event.schema_version != 1
                or lock_event.stream_id != stream_id
                or lock_event.transaction_id != result.transaction_id
                or lock_event.command_id != command.command_id
                or lock_event.causation_id != command.causation_id
                or lock_event.correlation_id != command.correlation_id
                or lock_event.visibility_policy != "authority_only"
                or lock_event.payload.get("actor_ref") != command.actor_ref
                or lock_event.payload.get("lock_ref") != command.lock_ref
                or lock_event.payload.get("reservation_ref") != command.reservation_ref
                or lock_event.payload.get("resource_id") != command.resource_id
                or lock_event.payload.get("amount") != payload.get("amount")
            ):
                return False
        if result.resulting_stream_revisions != {stream_id: events[-1].stream_revision}:
            return False
        if result.global_sequence_range != (events[0].global_sequence, events[-1].global_sequence):
            return False
        try:
            return all(self._store.get_event(committed.event_id) == committed for committed in events)
        except KeyError:
            return False


class ResourceBoundsMigrationAuthorityService:
    """Pure planner for the first trusted resource data migration.

    It owns resource facts but has no event-store reference.  The Patch
    lifecycle coordinator validates and binds its event into one authority
    batch together with the state-group and Patch-set transitions.
    """

    def __init__(self, *, definitions: ResourceDefinitionRegistry) -> None:
        self._definitions = definitions

    def plan(
        self,
        request: ResourceBoundsMigrationRequest,
        projection: ResourceStateProjection,
    ) -> ResourceBoundsMigrationPlan:
        if request.migrator_code_digest not in {
            RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST,
            RESOURCE_V2_POLICY_MIGRATOR_CODE_DIGEST,
        }:
            raise ResourceBodyRuntimeError("resource_migration_code_digest_mismatch")
        if projection.actor_ref != request.actor_ref:
            raise ResourceBodyRuntimeError("resource_migration_actor_mismatch")
        if projection.projection_revision != request.expected_projection_revision:
            raise ResourceBodyRuntimeError("resource_migration_projection_revision_conflict")
        if projection.reservations:
            raise ResourceBodyRuntimeError("resource_migration_reservations_present")
        if any(lock[3] == "open" for lock in projection.locks.values()):
            raise ResourceBodyRuntimeError("resource_migration_active_locks_present")
        entry = projection.entries.get(request.resource_id)
        if entry is None:
            raise ResourceBodyRuntimeError("resource_migration_resource_unknown")
        if entry.definition_version != request.from_definition_version:
            raise ResourceBodyRuntimeError("resource_migration_source_definition_mismatch")
        source = self._definitions.resolve(request.resource_id, request.from_definition_version)
        target = self._definitions.resolve(request.resource_id, request.to_definition_version)
        if (entry.minimum, entry.maximum) != (source.minimum, source.maximum):
            raise ResourceBodyRuntimeError("resource_migration_source_bounds_mismatch")
        if target.minimum != source.minimum:
            raise ResourceBodyRuntimeError("resource_migration_policy_invalid")
        if entry.capacity is not None:
            if request.migrator_code_digest != RESOURCE_V2_POLICY_MIGRATOR_CODE_DIGEST:
                raise ResourceBodyRuntimeError("resource_migration_source_already_v2")
            if source.resource_schema != "resource.v2" or target.resource_schema != "resource.v2":
                raise ResourceBodyRuntimeError("resource_migration_v2_policy_invalid")
            if entry.locked != 0 or entry.debt != 0 or entry.modifier_ledger_digest != _modifier_ledger_digest(entry.modifier_ledger):
                raise ResourceBodyRuntimeError("resource_migration_v2_state_not_migratable")
        elif request.migrator_code_digest != RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST:
            raise ResourceBodyRuntimeError("resource_migration_legacy_migrator_invalid")
        elif target.maximum >= source.maximum:
            raise ResourceBodyRuntimeError("resource_migration_policy_invalid")
        target_capacity = target.capacity
        target_base_capacity = target.base_capacity
        next_current = min(entry.current, target.maximum)
        lost_amount = entry.current - next_current
        stream_id = _resource_stream(request.actor_ref)
        expected_stream_revision = projection.source_revision_vector.get(stream_id, 0)
        payload: dict[str, object] = {
            "actor_ref": request.actor_ref,
            "resource_id": request.resource_id,
            "from_definition_version": request.from_definition_version,
            "to_definition_version": request.to_definition_version,
            "source_minimum": source.minimum,
            "source_maximum": source.maximum,
            "target_minimum": target.minimum,
            "target_maximum": target.maximum,
            "previous_current": entry.current,
            "next_current": next_current,
            "lost_amount": lost_amount,
            "migration_kind": (RESOURCE_V2_POLICY_MIGRATOR_ID if entry.capacity is not None
                                else RESOURCE_BOUNDS_CLAMP_MIGRATOR_ID),
            "migration_digest": request.migration_digest,
            "migrator_code_digest": request.migrator_code_digest,
        }
        snapshots = {"source": source.model_dump(mode="json"),
                     "target": target.model_dump(mode="json")}
        payload["definition_snapshots"] = snapshots
        payload["definition_snapshots_digest"] = "sha256:" + _digest(snapshots)
        if target.resource_schema == "resource.v2":
            payload.update({
                "target_resource_schema": target.resource_schema,
                "target_capacity": target_capacity,
                "target_base_capacity": target_base_capacity,
                "target_locked": 0,
                "target_debt": 0,
                "target_debt_ceiling": target.debt_ceiling,
                "target_modifier_ledger": [dict(item) for item in entry.modifier_ledger],
                "target_modifier_ledger_digest": _modifier_ledger_digest(entry.modifier_ledger),
            })
        return ResourceBoundsMigrationPlan(
            actor_ref=request.actor_ref,
            resource_id=request.resource_id,
            expected_stream_revision=expected_stream_revision,
            event_type="gameplay.resource.bounds_migrated",
            payload=MappingProxyType(payload),
            result_digest="sha256:" + _digest(payload),
        )


class ResourceBodyRuntimeProjector:
    """Rebuilds group-owned resource and body read models from Gameplay events."""

    _RESOURCE_EVENT_TYPES = {
        "gameplay.resource.materialized",
        "gameplay.resource.adjusted",
        "gameplay.resource.recovered",
        "gameplay.resource.converted",
        "gameplay.resource.bounds_migrated",
        "gameplay.resource.reservation_created",
        "gameplay.resource.reservation_consumed",
        "gameplay.resource.reservation_released",
        "gameplay.resource.lock_created",
        "gameplay.resource.lock_consumed",
        "gameplay.resource.lock_released",
        "gameplay.resource.modifier_attached",
        "gameplay.resource.modifier_detached",
    }
    _BODY_EVENT_TYPES = {"gameplay.body.injury_applied", "gameplay.body.injury_recovered"}

    def __init__(self, *, resource_definitions: ResourceDefinitionRegistry | None = None) -> None:
        self._resource_definitions = resource_definitions

    def rebuild_resources(
        self,
        actor_ref: str,
        events: list[GameplayEvent],
        *,
        checkpoint: ResourceStateProjection | None = None,
    ) -> ResourceStateProjection:
        if checkpoint is not None and checkpoint.actor_ref != actor_ref:
            raise ResourceBodyRuntimeError("actor_mismatch")
        if checkpoint is not None:
            expected_checkpoint_revision = _projection_revision(
                "resources", actor_ref,
                {"entries": dict(checkpoint.entries), "reservations": dict(checkpoint.reservations), "locks": dict(checkpoint.locks)},
                checkpoint.source_revision_vector,
            )
            if checkpoint.projection_revision != expected_checkpoint_revision:
                raise ResourceBodyRuntimeError("resource_checkpoint_digest_invalid")
        self._validate_resource_batches(events, actor_ref, checkpoint=checkpoint)
        entries: dict[str, ResourceEntry] = dict(checkpoint.entries) if checkpoint is not None else {}
        reservations: dict[str, tuple[str, int]] = dict(checkpoint.reservations) if checkpoint is not None else {}
        locks: dict[str, tuple[str, str, int, str]] = dict(checkpoint.locks) if checkpoint is not None else {}
        revisions: dict[str, int] = dict(checkpoint.source_revision_vector) if checkpoint is not None else {}
        for event in self._ordered_relevant(events, self._RESOURCE_EVENT_TYPES):
            payload = self._actor_payload(event, actor_ref)
            resource_id = str(payload.get("resource_id", ""))
            if not resource_id:
                raise ResourceBodyRuntimeError("resource_event_payload_invalid")
            if event.event_type == "gameplay.resource.materialized":
                if resource_id in entries:
                    raise ResourceBodyRuntimeError("resource_materialized_duplicate")
                minimum = _required_int(payload, "minimum")
                maximum = _required_int(payload, "maximum")
                current = _required_int(payload, "current")
                if minimum > maximum or current < minimum or current > maximum:
                    raise ResourceBodyRuntimeError("resource_materialization_bounds_invalid")
                definition_version = str(payload.get("definition_version", "legacy-v0"))
                if not definition_version:
                    raise ResourceBodyRuntimeError("resource_definition_version_invalid")
                is_v2 = payload.get("resource_schema") == "resource.v2"
                if "resource_schema" in payload and not is_v2:
                    raise ResourceBodyRuntimeError("resource_schema_not_supported")
                if is_v2:
                    capacity = _required_int(payload, "capacity")
                    base_capacity = _required_int(payload, "base_capacity")
                    locked = _required_int(payload, "locked")
                    debt = _required_int(payload, "debt")
                    debt_ceiling = _required_int(payload, "debt_ceiling")
                    ledger = payload.get("modifier_ledger")
                    ledger_digest = payload.get("modifier_ledger_digest")
                    normalized_ledger = _normalize_modifier_ledger(ledger)
                    if (minimum != 0 or capacity < 0 or base_capacity < 0 or locked != 0 or debt < 0 or debt_ceiling != 0
                            or debt != 0 or base_capacity > capacity or maximum > capacity or current > capacity
                            or not isinstance(ledger_digest, str)
                            or not _is_sha256_digest(ledger_digest)
                            or ledger_digest != _modifier_ledger_digest(normalized_ledger)):
                        raise ResourceBodyRuntimeError("resource_v2_materialization_invalid")
                else:
                    capacity = base_capacity = None
                    locked = debt = debt_ceiling = 0
                    ledger_digest = None
                    normalized_ledger = ()
                entries[resource_id] = ResourceEntry(
                    resource_id,
                    definition_version,
                    current,
                    minimum,
                    maximum,
                    event.event_id,
                    0,
                    capacity,
                    base_capacity,
                    locked,
                    debt,
                    debt_ceiling,
                    ledger_digest,
                    normalized_ledger,
                )
            elif event.event_type == "gameplay.resource.converted":
                input_entry = entries.get(resource_id)
                output_resource_id = payload.get("output_resource_id")
                if input_entry is None or not isinstance(output_resource_id, str) or output_resource_id == resource_id:
                    raise ResourceBodyRuntimeError("resource_conversion_identity_invalid")
                output_entry = entries.get(output_resource_id)
                input_delta = _required_int(payload, "input_delta")
                output_delta = _required_int(payload, "output_delta")
                units = _required_int(payload, "units")
                input_amount = _required_int(payload, "input_amount_per_unit")
                output_amount = _required_int(payload, "output_amount_per_unit")
                policy_digest = payload.get("policy_digest")
                if (output_delta <= 0 or input_delta >= 0 or units <= 0 or input_amount <= 0 or output_amount <= 0
                        or input_delta != -units * input_amount or output_delta != units * output_amount
                        or not isinstance(policy_digest, str) or not _is_sha256_digest(policy_digest)):
                    raise ResourceBodyRuntimeError("resource_conversion_delta_invalid")
                input_after = input_entry.current + input_delta
                output_after = output_entry.current + output_delta if output_entry is not None else -1
                if (output_entry is None or input_after < input_entry.minimum + input_entry.reserved
                        or output_after > output_entry.maximum
                        or (input_entry.capacity is not None and input_after > input_entry.capacity)
                        or (output_entry.capacity is not None and output_after > output_entry.capacity)):
                    raise ResourceBodyRuntimeError("resource_conversion_boundary_violation")
                entries[resource_id] = replace(input_entry, current=input_after, source_event_id=event.event_id)
                entries[output_resource_id] = replace(output_entry, current=output_after, source_event_id=event.event_id)
            elif event.event_type in {"gameplay.resource.adjusted", "gameplay.resource.recovered"}:
                entry = entries.get(resource_id)
                if entry is None:
                    raise ResourceBodyRuntimeError("resource_adjust_before_materialization")
                delta = _required_int(payload, "delta")
                updated = entry.current + delta
                if updated < entry.minimum or updated > entry.maximum or (entry.capacity is not None and updated > entry.capacity):
                    raise ResourceBodyRuntimeError("resource_boundary_violation")
                if updated < entry.reserved:
                    raise ResourceBodyRuntimeError("resource_reserved_boundary_violation")
                entries[resource_id] = ResourceEntry(
                    resource_id,
                    entry.definition_version,
                    updated,
                    entry.minimum,
                    entry.maximum,
                    event.event_id,
                    entry.reserved,
                    entry.capacity,
                    entry.base_capacity,
                    entry.locked,
                    entry.debt,
                    entry.debt_ceiling,
                    entry.modifier_ledger_digest,
                    entry.modifier_ledger,
                )
            elif event.event_type == "gameplay.resource.bounds_migrated":
                entry = entries.get(resource_id)
                if entry is None:
                    raise ResourceBodyRuntimeError("resource_migration_before_materialization")
                self._apply_bounds_migration(entry, payload, event.event_id, entries)
            elif event.event_type in {"gameplay.resource.reservation_created", "gameplay.resource.reservation_consumed", "gameplay.resource.reservation_released"}:
                reservation_ref = str(payload.get("reservation_ref", ""))
                if not reservation_ref:
                    raise ResourceBodyRuntimeError("resource_reservation_payload_invalid")
                if event.event_type == "gameplay.resource.reservation_created":
                    amount = _required_int(payload, "amount")
                    entry = entries.get(resource_id)
                    if entry is None or amount < 1 or reservation_ref in reservations or entry.available < amount:
                        raise ResourceBodyRuntimeError("resource_reservation_invalid")
                    reservations[reservation_ref] = (resource_id, amount)
                    entries[resource_id] = ResourceEntry(
                        resource_id,
                        entry.definition_version,
                        entry.current,
                        entry.minimum,
                        entry.maximum,
                        event.event_id,
                        entry.reserved + amount,
                        entry.capacity,
                        entry.base_capacity,
                        entry.locked,
                        entry.debt,
                        entry.debt_ceiling,
                        entry.modifier_ledger_digest,
                        entry.modifier_ledger,
                    )
                else:
                    reserved = reservations.pop(reservation_ref, None)
                    if reserved is None or reserved[0] != resource_id:
                        raise ResourceBodyRuntimeError("resource_reservation_unknown")
                    entry = entries.get(resource_id)
                    if entry is None:
                        raise ResourceBodyRuntimeError("resource_reservation_unknown")
                    amount = reserved[1]
                    if event.event_type == "gameplay.resource.reservation_consumed":
                        updated = entry.current - amount
                        if updated < entry.minimum:
                            raise ResourceBodyRuntimeError("resource_boundary_violation")
                        entries[resource_id] = ResourceEntry(
                            resource_id,
                            entry.definition_version,
                            updated,
                            entry.minimum,
                            entry.maximum,
                            event.event_id,
                            entry.reserved - amount,
                            entry.capacity,
                            entry.base_capacity,
                            entry.locked,
                            entry.debt,
                            entry.debt_ceiling,
                            entry.modifier_ledger_digest,
                            entry.modifier_ledger,
                        )
                    else:
                        entries[resource_id] = ResourceEntry(
                            resource_id,
                            entry.definition_version,
                            entry.current,
                            entry.minimum,
                            entry.maximum,
                            event.event_id,
                            entry.reserved - amount,
                            entry.capacity,
                            entry.base_capacity,
                            entry.locked,
                            entry.debt,
                            entry.debt_ceiling,
                            entry.modifier_ledger_digest,
                            entry.modifier_ledger,
                        )
            elif event.event_type in {"gameplay.resource.modifier_attached", "gameplay.resource.modifier_detached"}:
                entry = entries.get(resource_id)
                if entry is None or entry.capacity is None:
                    raise ResourceBodyRuntimeError("resource_modifier_resource_invalid")
                modifier = _normalize_modifier_item(payload.get("modifier"))
                ledger = list(entry.modifier_ledger)
                modifier_ref = modifier["modifier_ref"]
                if event.event_type == "gameplay.resource.modifier_attached":
                    if any(item["modifier_ref"] == modifier_ref for item in ledger):
                        raise ResourceBodyRuntimeError("resource_modifier_duplicate")
                    ledger.append(modifier)
                else:
                    if not any(dict(item) == modifier for item in ledger):
                        raise ResourceBodyRuntimeError("resource_modifier_unknown")
                    ledger = [item for item in ledger if item["modifier_ref"] != modifier_ref]
                normalized = _normalize_modifier_ledger(ledger)
                capacity = entry.capacity
                current = entry.current
                if modifier["operation"] == "capacity_delta":
                    capacity = max(0, int(entry.base_capacity) + sum(int(item["amount"]) for item in normalized if item["operation"] == "capacity_delta"))
                    current = min(current, capacity)
                if current < entry.reserved:
                    raise ResourceBodyRuntimeError("resource_modifier_locked_boundary_violation")
                entries[resource_id] = replace(entry, source_event_id=event.event_id, current=current, capacity=capacity, modifier_ledger_digest=_modifier_ledger_digest(normalized), modifier_ledger=normalized)
            elif event.event_type in {"gameplay.resource.lock_created", "gameplay.resource.lock_consumed", "gameplay.resource.lock_released"}:
                lock_ref = str(payload.get("lock_ref", ""))
                reservation_ref = str(payload.get("reservation_ref", ""))
                amount = _required_int(payload, "amount")
                if not lock_ref or not reservation_ref or amount < 1:
                    raise ResourceBodyRuntimeError("resource_lock_payload_invalid")
                entry = entries.get(resource_id)
                if entry is None:
                    raise ResourceBodyRuntimeError("resource_lock_unknown")
                prior = locks.get(lock_ref)
                if event.event_type == "gameplay.resource.lock_created":
                    if prior is not None or reservation_ref not in reservations or reservations[reservation_ref] != (resource_id, amount):
                        raise ResourceBodyRuntimeError("resource_lock_invalid")
                    locks[lock_ref] = (reservation_ref, resource_id, amount, "open")
                    entries[resource_id] = ResourceEntry(resource_id, entry.definition_version, entry.current, entry.minimum, entry.maximum, event.event_id, entry.reserved, entry.capacity, entry.base_capacity, entry.locked + amount, entry.debt, entry.debt_ceiling, entry.modifier_ledger_digest, entry.modifier_ledger)
                else:
                    if prior is None or prior[:3] != (reservation_ref, resource_id, amount) or prior[3] != "open":
                        raise ResourceBodyRuntimeError("resource_lock_unknown")
                    status = "consumed" if event.event_type == "gameplay.resource.lock_consumed" else "released"
                    locks[lock_ref] = (prior[0], prior[1], prior[2], status)
                    entries[resource_id] = ResourceEntry(resource_id, entry.definition_version, entry.current, entry.minimum, entry.maximum, event.event_id, entry.reserved, entry.capacity, entry.base_capacity, entry.locked - amount, entry.debt, entry.debt_ceiling, entry.modifier_ledger_digest, entry.modifier_ledger)
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
        for resource_id, entry in entries.items():
            if entry.capacity is None:
                continue
            active_locks = [lock for lock in locks.values() if lock[1] == resource_id and lock[3] == "open"]
            if entry.locked != sum(lock[2] for lock in active_locks):
                raise ResourceBodyRuntimeError("resource_lock_aggregate_invalid")
            active_reservations = [amount for rid, amount in reservations.values() if rid == resource_id]
            if entry.reserved != sum(active_reservations):
                raise ResourceBodyRuntimeError("resource_reservation_aggregate_invalid")
        return ResourceStateProjection(
            actor_ref=actor_ref,
            entries=MappingProxyType(dict(sorted(entries.items()))),
            reservations=MappingProxyType(dict(sorted(reservations.items()))),
            source_revision_vector=_freeze_revisions(revisions),
            projection_revision=_projection_revision("resources", actor_ref, {"entries": entries, "reservations": reservations, "locks": locks}, revisions),
            locks=MappingProxyType(dict(sorted(locks.items()))),
        )

    def _validate_resource_batches(self, events: list[GameplayEvent], actor_ref: str, *, checkpoint: ResourceStateProjection | None = None) -> None:
        grouped: dict[str, list[GameplayEvent]] = {}
        v2_resources = {
            str(event.payload.get("resource_id"))
            for event in events
            if event.event_type == "gameplay.resource.materialized"
            and event.payload.get("resource_schema") == "resource.v2"
            and str(event.payload.get("actor_ref", "")) == actor_ref
        }
        if checkpoint is not None:
            v2_resources.update(resource_id for resource_id, entry in checkpoint.entries.items() if entry.capacity is not None)
        for event in events:
            if event.event_type not in self._RESOURCE_EVENT_TYPES:
                continue
            payload = self._actor_payload(event, actor_ref)
            grouped.setdefault(event.transaction_id, []).append(event)
        for transaction_events in grouped.values():
            resource_events = [event for event in transaction_events if event.event_type.startswith("gameplay.resource.")]
            if not resource_events:
                continue
            kinds = {event.event_type for event in resource_events}
            reservation_kinds = {kind for kind in kinds if kind in {
                "gameplay.resource.reservation_created", "gameplay.resource.reservation_consumed", "gameplay.resource.reservation_released"
            }}
            lock_kinds = {kind for kind in kinds if kind in {
                "gameplay.resource.lock_created", "gameplay.resource.lock_consumed", "gameplay.resource.lock_released"
            }}
            if not reservation_kinds and not lock_kinds:
                continue
            if len(reservation_kinds) != 1:
                raise ResourceBodyRuntimeError("resource_lock_batch_incomplete")
            reservation_event = next(event for event in resource_events if event.event_type in reservation_kinds)
            resource_id = str(reservation_event.payload.get("resource_id", ""))
            # v2 lock events must be paired atomically; a transaction cannot
            # silently mutate reserved without the corresponding lock state.
            if resource_id in v2_resources or reservation_event.payload.get("lock_ref") or lock_kinds:
                expected_lock = {
                    "gameplay.resource.reservation_created": "gameplay.resource.lock_created",
                    "gameplay.resource.reservation_consumed": "gameplay.resource.lock_consumed",
                    "gameplay.resource.reservation_released": "gameplay.resource.lock_released",
                }[reservation_event.event_type]
                if lock_kinds != {expected_lock} or len(resource_events) != 2:
                    raise ResourceBodyRuntimeError("resource_lock_batch_incomplete")
                lock_event = next(event for event in resource_events if event.event_type == expected_lock)
                for key in ("resource_id", "reservation_ref", "actor_ref"):
                    if lock_event.payload.get(key) != reservation_event.payload.get(key):
                        raise ResourceBodyRuntimeError("resource_lock_batch_mismatch")
                if lock_event.payload.get("amount") != reservation_event.payload.get("amount"):
                    raise ResourceBodyRuntimeError("resource_lock_batch_mismatch")
                if reservation_event.payload.get("lock_ref") != lock_event.payload.get("lock_ref"):
                    raise ResourceBodyRuntimeError("resource_lock_batch_mismatch")
    def rebuild_body(
        self,
        actor_ref: str,
        events: list[GameplayEvent],
        *,
        checkpoint: BodyRuntimeProjection | None = None,
    ) -> BodyRuntimeProjection:
        if checkpoint is not None and checkpoint.actor_ref != actor_ref:
            raise ResourceBodyRuntimeError("actor_mismatch")
        injuries: dict[str, BodyInjury] = dict(checkpoint.injuries) if checkpoint is not None else {}
        revisions: dict[str, int] = dict(checkpoint.source_revision_vector) if checkpoint is not None else {}
        for event in self._ordered_relevant(events, self._BODY_EVENT_TYPES):
            payload = self._actor_payload(event, actor_ref)
            injury_id = str(payload.get("injury_id", ""))
            if not injury_id:
                raise ResourceBodyRuntimeError("body_event_payload_invalid")
            if event.event_type == "gameplay.body.injury_applied":
                function_id = str(payload.get("function_id", ""))
                capacity_ratio = _required_int(payload, "capacity_ratio")
                if not function_id or capacity_ratio < 0 or capacity_ratio > 100:
                    raise ResourceBodyRuntimeError("injury_payload_invalid")
                injuries[injury_id] = BodyInjury(injury_id, function_id, capacity_ratio, event.event_id)
            else:
                if injury_id not in injuries:
                    raise ResourceBodyRuntimeError("injury_recover_before_apply")
                del injuries[injury_id]
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
        functions = _derive_functions(injuries)
        return BodyRuntimeProjection(
            actor_ref=actor_ref,
            injuries=MappingProxyType(dict(sorted(injuries.items()))),
            functions=MappingProxyType(functions),
            source_revision_vector=_freeze_revisions(revisions),
            projection_revision=_projection_revision("body", actor_ref, injuries, revisions),
        )

    @staticmethod
    def _ordered_relevant(events: list[GameplayEvent], event_types: set[str]) -> list[GameplayEvent]:
        return sorted(
            (event for event in events if event.event_type in event_types),
            key=lambda event: (event.global_sequence, event.event_id),
        )

    @staticmethod
    def _actor_payload(event: GameplayEvent, actor_ref: str) -> Mapping[str, object]:
        if str(event.payload.get("actor_ref", "")) != actor_ref:
            raise ResourceBodyRuntimeError("actor_mismatch")
        return event.payload

    def _apply_bounds_migration(
        self,
        entry: ResourceEntry,
        payload: Mapping[str, object],
        event_id: str,
        entries: dict[str, ResourceEntry],
    ) -> None:
        source_is_v2 = entry.capacity is not None
        if self._resource_definitions is None:
            raise ResourceBodyRuntimeError("resource_definition_registry_required")
        from_version = str(payload.get("from_definition_version", ""))
        to_version = str(payload.get("to_definition_version", ""))
        migration_kind = str(payload.get("migration_kind", ""))
        migration_digest = str(payload.get("migration_digest", ""))
        code_digest = str(payload.get("migrator_code_digest", ""))
        if (
            not from_version
            or not to_version
            or migration_kind not in {RESOURCE_BOUNDS_CLAMP_MIGRATOR_ID, RESOURCE_V2_POLICY_MIGRATOR_ID}
            or not _is_sha256_digest(migration_digest)
            or code_digest not in {RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST, RESOURCE_V2_POLICY_MIGRATOR_CODE_DIGEST}
        ):
            raise ResourceBodyRuntimeError("resource_migration_payload_invalid")
        if entry.definition_version != from_version or entry.reserved:
            raise ResourceBodyRuntimeError("resource_migration_source_invalid")
        source = self._resource_definitions.resolve(entry.resource_id, from_version)
        target = self._resource_definitions.resolve(entry.resource_id, to_version)
        snapshots = payload.get("definition_snapshots")
        snapshots_digest = payload.get("definition_snapshots_digest")
        if snapshots is not None or snapshots_digest is not None:
            if (not isinstance(snapshots, Mapping) or set(snapshots) != {"source", "target"}
                    or snapshots_digest != "sha256:" + _digest(snapshots)):
                raise ResourceBodyRuntimeError("resource_migration_definition_snapshot_invalid")
            try:
                pinned_source = ResourceDefinition.model_validate(snapshots["source"])
                pinned_target = ResourceDefinition.model_validate(snapshots["target"])
            except (TypeError, ValueError) as exc:
                raise ResourceBodyRuntimeError("resource_migration_definition_snapshot_invalid") from exc
            if pinned_source != source or pinned_target != target:
                raise ResourceBodyRuntimeError("resource_migration_definition_snapshot_mismatch")
        source_minimum = _required_int(payload, "source_minimum")
        source_maximum = _required_int(payload, "source_maximum")
        target_minimum = _required_int(payload, "target_minimum")
        target_maximum = _required_int(payload, "target_maximum")
        previous_current = _required_int(payload, "previous_current")
        next_current = _required_int(payload, "next_current")
        lost_amount = _required_int(payload, "lost_amount")
        if (
            (entry.minimum, entry.maximum, entry.current) != (source_minimum, source_maximum, previous_current)
            or (source.minimum, source.maximum) != (source_minimum, source_maximum)
            or (target.minimum, target.maximum) != (target_minimum, target_maximum)
            or target.minimum != source.minimum
            or (not source_is_v2 and target.maximum >= source.maximum)
            or next_current != min(previous_current, target.maximum)
            or lost_amount != previous_current - next_current
            or not target.minimum <= next_current <= target.maximum
        ):
            raise ResourceBodyRuntimeError("resource_migration_policy_invalid")
        target_schema = str(payload.get("target_resource_schema", "legacy-v1"))
        if target_schema != target.resource_schema:
            raise ResourceBodyRuntimeError("resource_migration_target_schema_invalid")
        if source_is_v2:
            if migration_kind != RESOURCE_V2_POLICY_MIGRATOR_ID or code_digest != RESOURCE_V2_POLICY_MIGRATOR_CODE_DIGEST:
                raise ResourceBodyRuntimeError("resource_migration_v2_policy_invalid")
            if target_schema != "resource.v2":
                raise ResourceBodyRuntimeError("resource_migration_v2_policy_invalid")
        elif migration_kind != RESOURCE_BOUNDS_CLAMP_MIGRATOR_ID or code_digest != RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST:
            raise ResourceBodyRuntimeError("resource_migration_legacy_policy_invalid")
        if target_schema == "resource.v2":
            target_capacity = _required_int(payload, "target_capacity")
            target_base_capacity = _required_int(payload, "target_base_capacity")
            target_locked = _required_int(payload, "target_locked")
            target_debt = _required_int(payload, "target_debt")
            target_debt_ceiling = _required_int(payload, "target_debt_ceiling")
            target_ledger = payload.get("target_modifier_ledger")
            target_ledger_digest = str(payload.get("target_modifier_ledger_digest", ""))
            if (target.resource_schema != "resource.v2" or target.capacity != target_capacity
                    or target.base_capacity != target_base_capacity or target_debt_ceiling != target.debt_ceiling
                    or target_locked != 0 or target_debt != 0
                    or target_capacity < target.maximum or target_base_capacity > target_capacity
                    or not _is_sha256_digest(target_ledger_digest)
                    or target_ledger_digest != _modifier_ledger_digest(_normalize_modifier_ledger(target_ledger))
                    or _normalize_modifier_ledger(target_ledger) != entry.modifier_ledger
                    or entry.reserved != 0 or entry.locked != 0
                    or (source_is_v2 and migration_kind != RESOURCE_V2_POLICY_MIGRATOR_ID)):
                raise ResourceBodyRuntimeError("resource_migration_v2_policy_invalid")
            entries[entry.resource_id] = ResourceEntry(
                entry.resource_id, to_version, next_current, target.minimum, target.maximum,
                event_id, 0, target_capacity, target_base_capacity, 0, 0,
                target_debt_ceiling, target_ledger_digest, _normalize_modifier_ledger(target_ledger),
            )
            return
        entries[entry.resource_id] = ResourceEntry(
            entry.resource_id,
            to_version,
            next_current,
            target.minimum,
            target.maximum,
            event_id,
        )


class ResourceBodyActionSettlementService:
    """Authority-only resource/body gate; accepted actions append one atomic batch."""

    _PRINCIPAL = "resource_body_action_authority"

    def __init__(self, *, store: GameplayEventStore) -> None:
        self._store = store

    def settle(
        self,
        command: GameplayActionSettlementCommand,
        *,
        resources: ResourceStateProjection,
        body: BodyRuntimeProjection,
        enabled_group_ids: tuple[str, ...],
    ) -> GameplayActionSettlementResult:
        if command.authority_principal != self._PRINCIPAL:
            return GameplayActionSettlementResult(False, "authority_principal_mismatch", ())
        if resources.actor_ref != command.actor_ref or body.actor_ref != command.actor_ref:
            raise ValueError("actor_ref_mismatch")
        receipt_key = f"{command.actor_ref}:{command.idempotency_key}"
        expected_digest = "sha256:" + _digest({
            "command_id": command.command_id,
            "actor_ref": command.actor_ref,
            "causation_id": command.causation_id,
            "correlation_id": command.correlation_id,
            "requirement": command.requirement.model_dump(mode="json"),
            "payload_digest": command.payload_digest,
        })
        prior = self._store.get_idempotency_record(self._PRINCIPAL, receipt_key)
        if prior is not None:
            receipt = self._store.get_by_idempotency(self._PRINCIPAL, receipt_key)
            if receipt is None:
                return GameplayActionSettlementResult(False, "action_receipt_unavailable", ())
            error = self._receipt_error(receipt, command=command, expected_digest=expected_digest)
            if error is not None:
                return GameplayActionSettlementResult(False, error, ())
            return GameplayActionSettlementResult(
                True, None, (), receipt.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            )
        required_groups = {"core.resources", "core.body_runtime"}
        if not required_groups.issubset(enabled_group_ids):
            return GameplayActionSettlementResult(False, "state_group_not_enabled", ())
        resource_stream = _resource_stream(command.actor_ref)
        body_stream = _body_stream(command.actor_ref)
        resource_revision = resources.source_revision_vector.get(resource_stream, 0)
        body_revision = body.source_revision_vector.get(body_stream, 0)
        if self._store.get_stream_head(resource_stream) != resource_revision:
            return GameplayActionSettlementResult(False, "state_revision_conflict", ())
        if self._store.get_stream_head(body_stream) != body_revision:
            return GameplayActionSettlementResult(False, "state_revision_conflict", ())
        resource = resources.entries.get(command.requirement.stamina_resource_id)
        if resource is None:
            return GameplayActionSettlementResult(False, "resource_not_registered", ())
        if resource.available < command.requirement.stamina_cost:
            return GameplayActionSettlementResult(False, "resource_insufficient", (resource.source_event_id,))
        capacity = body.functions.get(command.requirement.required_function_id)
        if capacity is not None and capacity.status == "unavailable":
            return GameplayActionSettlementResult(
                False,
                "body_function_unavailable",
                capacity.contributing_source_refs,
            )

        action_stream = _action_stream(command.actor_ref)
        action_revision = self._store.get_stream_head(action_stream)
        transaction_id = f"tx:{command.command_id}"
        append_result = self._store.append_batch(
            {
                "transaction_id": transaction_id,
                "command_id": command.command_id,
                "expected_stream_revisions": {
                    resource_stream: resource_revision,
                    body_stream: body_revision,
                    action_stream: action_revision,
                },
                "read_stream_revisions": {resource_stream: resource_revision, body_stream: body_revision},
                "pinned_revisions": {"resource": resource_revision, "body": body_revision},
                "events": [
                    _event(
                        command,
                        transaction_id,
                        resource_stream,
                        "gameplay.resource.adjusted",
                        1,
                        {
                            "actor_ref": command.actor_ref,
                            "resource_id": resource.resource_id,
                            "delta": -command.requirement.stamina_cost,
                            "reason_ref": command.requirement.action_ref,
                        },
                    ),
                    _event(
                        command,
                        transaction_id,
                        action_stream,
                        "gameplay.action.settled",
                        2,
                        {
                            "actor_ref": command.actor_ref,
                            "action_ref": command.requirement.action_ref,
                            "stamina_resource_id": resource.resource_id,
                            "stamina_cost": command.requirement.stamina_cost,
                            "required_function_id": command.requirement.required_function_id,
                            "request_digest_version": 2,
                        },
                    ),
                ],
                "idempotency_record": {
                    "principal_ref": self._PRINCIPAL,
                    "idempotency_key": receipt_key,
                    "payload_digest": expected_digest,
                },
                "outbox_entries": [],
                "result_digest": _digest(
                    {
                        "actor_ref": command.actor_ref,
                        "action_ref": command.requirement.action_ref,
                        "stamina_cost": command.requirement.stamina_cost,
                    }
                ),
                "projection_refresh_hints": [],
            }
        )
        if not append_result.committed:
            return GameplayActionSettlementResult(
                False,
                append_result.failure.error_code if append_result.failure is not None else "action_settlement_failed",
                (),
                append_result,
            )
        return GameplayActionSettlementResult(True, None, (), append_result)

    def _receipt_error(self, receipt: AppendBatchResult, *, command: GameplayActionSettlementCommand,
                       expected_digest: str) -> str | None:
        """Validate the original complete batch, including the historical HEAD contract."""
        incomplete = "action_receipt_incomplete"
        transaction = self._store.get_transaction(receipt.transaction_id)
        if (not receipt.committed or receipt.failure is not None or transaction is None
                or transaction.transaction_id != f"tx:{command.command_id}"
                or receipt.transaction_id != transaction.transaction_id
                or receipt.command_id != command.command_id
                or transaction.command_id != command.command_id
                or len(transaction.events) != 2):
            return incomplete
        resource_stream = _resource_stream(command.actor_ref)
        body_stream = _body_stream(command.actor_ref)
        action_stream = _action_stream(command.actor_ref)
        expected_streams = {resource_stream, body_stream, action_stream}
        revisions = transaction.expected_stream_revisions
        if (set(revisions) != expected_streams
                or any(type(value) is not int or value < 0 for value in revisions.values())
                or transaction.pinned_revisions != {"resource": revisions[resource_stream], "body": revisions[body_stream]}):
            return incomplete
        resource_event, action_event = transaction.events
        version = action_event.payload.get("request_digest_version")
        if version is None:
            # Legacy HEAD batches stored the original command digest, not a hash of its fields.
            digest = command.payload_digest
            if transaction.read_stream_revisions:
                return incomplete
        elif type(version) is int and version == 2:
            digest = expected_digest
            if transaction.read_stream_revisions != {resource_stream: revisions[resource_stream], body_stream: revisions[body_stream]}:
                return incomplete
        else:
            return incomplete
        record = transaction.idempotency_record
        if (record.principal_ref != self._PRINCIPAL
                or record.idempotency_key != f"{command.actor_ref}:{command.idempotency_key}"):
            return incomplete
        if record.payload_digest != digest:
            return "idempotency_key_reused"
        original_record = self._store.get_idempotency_record(self._PRINCIPAL, record.idempotency_key)
        if original_record != record:
            return incomplete
        resource_payload = {"actor_ref": command.actor_ref, "resource_id": command.requirement.stamina_resource_id,
                            "delta": -command.requirement.stamina_cost, "reason_ref": command.requirement.action_ref}
        action_payload = {"actor_ref": command.actor_ref, "action_ref": command.requirement.action_ref,
                          "stamina_resource_id": command.requirement.stamina_resource_id,
                          "stamina_cost": command.requirement.stamina_cost,
                          "required_function_id": command.requirement.required_function_id}
        if version == 2:
            action_payload["request_digest_version"] = 2
        expected_events = [
            _event(command, transaction.transaction_id, resource_stream, "gameplay.resource.adjusted", 1, resource_payload),
            _event(command, transaction.transaction_id, action_stream, "gameplay.action.settled", 2, action_payload),
        ]
        for event, expected in zip(transaction.events, expected_events, strict=True):
            expected.update(stream_revision=revisions[event.stream_id] + 1 if event.stream_id in revisions else -1,
                            global_sequence=event.global_sequence)
            if event.model_dump() != expected:
                return "idempotency_key_reused"
            try:
                if self._store.get_event(event.event_id) != event:
                    return incomplete
            except KeyError:
                return incomplete
        if (resource_event.global_sequence < 1 or action_event.global_sequence != resource_event.global_sequence + 1
                or receipt.committed_event_ids != [event.event_id for event in transaction.events]
                or receipt.resulting_stream_revisions != {resource_stream: resource_event.stream_revision, action_stream: action_event.stream_revision}
                or receipt.global_sequence_range != (resource_event.global_sequence, action_event.global_sequence)
                or transaction.outbox_entries or transaction.projection_refresh_hints or receipt.projection_refresh_hints
                or transaction.result_digest != _digest({"actor_ref": command.actor_ref,
                    "action_ref": command.requirement.action_ref, "stamina_cost": command.requirement.stamina_cost})):
            return incomplete
        return None


def _derive_functions(injuries: Mapping[str, BodyInjury]) -> dict[str, FunctionalCapacity]:
    grouped: dict[str, list[BodyInjury]] = {}
    for injury in injuries.values():
        grouped.setdefault(injury.function_id, []).append(injury)
    functions: dict[str, FunctionalCapacity] = {}
    for function_id, sources in sorted(grouped.items()):
        capacity_ratio = min(source.capacity_ratio for source in sources)
        status: FunctionStatus = "available" if capacity_ratio == 100 else "impaired" if capacity_ratio > 0 else "unavailable"
        functions[function_id] = FunctionalCapacity(
            function_id=function_id,
            capacity_ratio=capacity_ratio,
            status=status,
            contributing_source_refs=tuple(sorted(source.source_event_id for source in sources)),
        )
    return functions


def _event(
    command: GameplayActionSettlementCommand,
    transaction_id: str,
    stream_id: str,
    event_type: str,
    index: int,
    payload: dict[str, object],
) -> dict[str, object]:
    return {
        "event_id": f"evt:{command.command_id}:resource-body:{index}",
        "event_type": event_type,
        "schema_version": 1,
        "stream_id": stream_id,
        "stream_revision": 0,
        "global_sequence": 0,
        "transaction_id": transaction_id,
        "command_id": command.command_id,
        "causation_id": command.causation_id,
        "correlation_id": command.correlation_id,
        "visibility_policy": "authority_only",
        "payload": payload,
    }


def _required_int(payload: Mapping[str, object], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ResourceBodyRuntimeError("resource_event_payload_invalid")
    return value


def _is_sha256_digest(value: str) -> bool:
    return re.fullmatch(r"sha256:[0-9a-f]{64}", value) is not None


def _normalize_modifier_item(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ResourceBodyRuntimeError("resource_modifier_payload_invalid")
    ref = value.get("modifier_ref")
    operation = value.get("operation")
    amount = value.get("amount")
    source_event_id = value.get("source_event_id")
    template_id = value.get("template_id")
    mapping_revision = value.get("mapping_revision")
    effective_world_tick = value.get("effective_world_tick")
    if effective_world_tick is not None and (type(effective_world_tick) is not int or effective_world_tick < 0):
        raise ResourceBodyRuntimeError("resource_modifier_payload_invalid")
    if not isinstance(ref, str) or not ref or operation not in {"capacity_delta", "recovery_delta"} or isinstance(amount, bool) or not isinstance(amount, int) or not isinstance(source_event_id, str) or not source_event_id or not isinstance(template_id, str) or not template_id:
        raise ResourceBodyRuntimeError("resource_modifier_payload_invalid")
    result = {"modifier_ref": ref, "operation": operation, "amount": amount, "source_event_id": source_event_id, "template_id": template_id}
    if mapping_revision is not None:
        if not isinstance(mapping_revision, str) or "@" not in mapping_revision:
            raise ResourceBodyRuntimeError("resource_modifier_payload_invalid")
        result["mapping_revision"] = mapping_revision
    if effective_world_tick is not None:
        result["effective_world_tick"] = effective_world_tick
    return result


def _normalize_modifier_ledger(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, (list, tuple)):
        raise ResourceBodyRuntimeError("resource_modifier_ledger_invalid")
    normalized = tuple(sorted((_normalize_modifier_item(item) for item in value), key=lambda item: str(item["modifier_ref"])))
    if len({item["modifier_ref"] for item in normalized}) != len(normalized):
        raise ResourceBodyRuntimeError("resource_modifier_duplicate")
    return normalized


def _modifier_ledger_digest(value: tuple[Mapping[str, object], ...]) -> str:
    return "sha256:" + sha256(json.dumps([dict(item) for item in value], sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _projection_revision(kind: str, actor_ref: str, values: Mapping[str, object], revisions: Mapping[str, int]) -> str:
    return f"projection:{_digest({'kind': kind, 'actor_ref': actor_ref, 'values': values, 'revisions': revisions})[:16]}"


def _freeze_revisions(revisions: Mapping[str, int]) -> Mapping[str, int]:
    return MappingProxyType({key: int(revisions[key]) for key in sorted(revisions)})


def _digest(value: object) -> str:
    return sha256(json.dumps(value, default=_json_default, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _json_default(value: object) -> object:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, (ResourceEntry, BodyInjury)):
        return value.__dict__
    raise TypeError(f"unsupported digest value: {type(value)!r}")


def _resource_stream(actor_ref: str) -> str:
    return f"gameplay:resources:{actor_ref}"


def _body_stream(actor_ref: str) -> str:
    return f"gameplay:body:{actor_ref}"


def _action_stream(actor_ref: str) -> str:
    return f"gameplay:actions:{actor_ref}"


def _migration_is_paused(events: list[GameplayEvent]) -> bool:
    states: dict[str, str] = {}
    for event in events:
        migration_id = str(event.payload.get("migration_id", ""))
        if not migration_id:
            continue
        if event.event_type == "gameplay.resource_migration.paused":
            states[migration_id] = "paused"
        elif event.event_type == "gameplay.resource_migration.completed":
            states[migration_id] = "completed"
    return any(state == "paused" for state in states.values())


__all__ = [
    "BodyInjury",
    "BodyRuntimeProjection",
    "FunctionalCapacity",
    "GameplayActionRequirement",
    "GameplayActionSettlementCommand",
    "GameplayActionSettlementResult",
    "ResourceBodyActionSettlementService",
    "ResourceBoundsMigrationAuthorityService",
    "ResourceBoundsMigrationPlan",
    "ResourceBoundsMigrationRequest",
    "ResourceReservationAuthorityService",
    "ResourceReservationCommand",
    "ResourceBodyRuntimeError",
    "ResourceBodyRuntimeProjector",
    "ResourceDefinition",
    "ResourceDefinitionRegistry",
    "ResourceEntry",
    "RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST",
    "RESOURCE_BOUNDS_CLAMP_MIGRATOR_ID",
    "RESOURCE_V2_POLICY_MIGRATOR_CODE_DIGEST",
    "RESOURCE_V2_POLICY_MIGRATOR_ID",
    "ResourceStateProjection",
]
