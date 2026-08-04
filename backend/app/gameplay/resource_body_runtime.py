"""Backend-only resource and body-function projection for the first gameplay slice."""

from __future__ import annotations

from dataclasses import dataclass
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

    def model_post_init(self, __context: object) -> None:
        if self.minimum > self.maximum:
            raise ValueError("resource_definition_bounds_invalid")


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
        if resources.source_revision_vector.get(stream_id, 0) != self._store.get_stream_head(stream_id):
            raise ValueError("state_revision_conflict")
        key = f"{command.actor_ref}:{command.idempotency_key}"
        record = self._store.get_idempotency_record(self._PRINCIPAL, key)
        if record is not None:
            if record.payload_digest != command.payload_digest:
                raise ValueError("idempotency_key_reused")
            result = self._store.get_by_idempotency(self._PRINCIPAL, key)
            assert result is not None
            return result
        entry = resources.entries.get(command.resource_id)
        if entry is None:
            raise ValueError("resource_not_registered")
        if command.operation == "reserve":
            if command.amount is None or entry.available < command.amount:
                raise ValueError("resource_insufficient")
            event_type, payload = "gameplay.resource.reservation_created", {"actor_ref": command.actor_ref, "resource_id": command.resource_id, "reservation_ref": command.reservation_ref, "amount": command.amount}
        else:
            event_type = "gameplay.resource.reservation_consumed" if command.operation == "consume" else "gameplay.resource.reservation_released"
            payload = {"actor_ref": command.actor_ref, "resource_id": command.resource_id, "reservation_ref": command.reservation_ref}
        transaction_id = f"tx:{command.command_id}"
        return self._store.append_batch({"transaction_id": transaction_id, "command_id": command.command_id, "expected_stream_revisions": {stream_id: self._store.get_stream_head(stream_id)}, "pinned_revisions": {}, "events": [{"event_id": f"evt:{command.command_id}:reservation", "event_type": event_type, "schema_version": 1, "stream_id": stream_id, "stream_revision": 0, "global_sequence": 0, "transaction_id": transaction_id, "command_id": command.command_id, "causation_id": command.causation_id, "correlation_id": command.correlation_id, "visibility_policy": "authority_only", "payload": payload}], "idempotency_record": {"principal_ref": self._PRINCIPAL, "idempotency_key": key, "payload_digest": command.payload_digest}, "outbox_entries": [], "result_digest": "sha256:" + _digest(payload), "projection_refresh_hints": []})


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
        if request.migrator_code_digest != RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST:
            raise ResourceBodyRuntimeError("resource_migration_code_digest_mismatch")
        if projection.actor_ref != request.actor_ref:
            raise ResourceBodyRuntimeError("resource_migration_actor_mismatch")
        if projection.projection_revision != request.expected_projection_revision:
            raise ResourceBodyRuntimeError("resource_migration_projection_revision_conflict")
        if projection.reservations:
            raise ResourceBodyRuntimeError("resource_migration_reservations_present")
        entry = projection.entries.get(request.resource_id)
        if entry is None:
            raise ResourceBodyRuntimeError("resource_migration_resource_unknown")
        if entry.definition_version != request.from_definition_version:
            raise ResourceBodyRuntimeError("resource_migration_source_definition_mismatch")
        source = self._definitions.resolve(request.resource_id, request.from_definition_version)
        target = self._definitions.resolve(request.resource_id, request.to_definition_version)
        if (entry.minimum, entry.maximum) != (source.minimum, source.maximum):
            raise ResourceBodyRuntimeError("resource_migration_source_bounds_mismatch")
        if target.minimum != source.minimum or target.maximum >= source.maximum:
            raise ResourceBodyRuntimeError("resource_migration_policy_invalid")
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
            "migration_kind": RESOURCE_BOUNDS_CLAMP_MIGRATOR_ID,
            "migration_digest": request.migration_digest,
            "migrator_code_digest": request.migrator_code_digest,
        }
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
        "gameplay.resource.bounds_migrated",
        "gameplay.resource.reservation_created",
        "gameplay.resource.reservation_consumed",
        "gameplay.resource.reservation_released",
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
        entries: dict[str, ResourceEntry] = dict(checkpoint.entries) if checkpoint is not None else {}
        reservations: dict[str, tuple[str, int]] = dict(checkpoint.reservations) if checkpoint is not None else {}
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
                entries[resource_id] = ResourceEntry(
                    resource_id,
                    definition_version,
                    current,
                    minimum,
                    maximum,
                    event.event_id,
                )
            elif event.event_type == "gameplay.resource.adjusted":
                entry = entries.get(resource_id)
                if entry is None:
                    raise ResourceBodyRuntimeError("resource_adjust_before_materialization")
                delta = _required_int(payload, "delta")
                updated = entry.current + delta
                if updated < entry.minimum or updated > entry.maximum:
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
                )
            elif event.event_type == "gameplay.resource.bounds_migrated":
                entry = entries.get(resource_id)
                if entry is None:
                    raise ResourceBodyRuntimeError("resource_migration_before_materialization")
                self._apply_bounds_migration(entry, payload, event.event_id, entries)
            else:
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
                        )
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
        return ResourceStateProjection(
            actor_ref=actor_ref,
            entries=MappingProxyType(dict(sorted(entries.items()))),
            reservations=MappingProxyType(dict(sorted(reservations.items()))),
            source_revision_vector=_freeze_revisions(revisions),
            projection_revision=_projection_revision("resources", actor_ref, entries, revisions),
        )

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
            or migration_kind != RESOURCE_BOUNDS_CLAMP_MIGRATOR_ID
            or not _is_sha256_digest(migration_digest)
            or code_digest != RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST
        ):
            raise ResourceBodyRuntimeError("resource_migration_payload_invalid")
        if entry.definition_version != from_version or entry.reserved:
            raise ResourceBodyRuntimeError("resource_migration_source_invalid")
        source = self._resource_definitions.resolve(entry.resource_id, from_version)
        target = self._resource_definitions.resolve(entry.resource_id, to_version)
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
            or target.maximum >= source.maximum
            or next_current != min(previous_current, target.maximum)
            or lost_amount != previous_current - next_current
            or not target.minimum <= next_current <= target.maximum
        ):
            raise ResourceBodyRuntimeError("resource_migration_policy_invalid")
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
        if resources.actor_ref != command.actor_ref or body.actor_ref != command.actor_ref:
            raise ValueError("actor_ref_mismatch")
        required_groups = {"core.resources", "core.body_runtime"}
        if not required_groups.issubset(enabled_group_ids):
            return GameplayActionSettlementResult(False, "state_group_not_enabled", ())
        resource_stream = _resource_stream(command.actor_ref)
        body_stream = _body_stream(command.actor_ref)
        if self._store.get_stream_head(resource_stream) != resources.source_revision_vector.get(resource_stream, 0):
            return GameplayActionSettlementResult(False, "state_revision_conflict", ())
        if self._store.get_stream_head(body_stream) != body.source_revision_vector.get(body_stream, 0):
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
        transaction_id = f"tx:{command.command_id}"
        append_result = self._store.append_batch(
            {
                "transaction_id": transaction_id,
                "command_id": command.command_id,
                "expected_stream_revisions": {
                    resource_stream: self._store.get_stream_head(resource_stream),
                    body_stream: self._store.get_stream_head(body_stream),
                    action_stream: self._store.get_stream_head(action_stream),
                },
                "pinned_revisions": {
                    "resource": self._store.get_stream_head(resource_stream),
                    "body": self._store.get_stream_head(body_stream),
                },
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
                        },
                    ),
                ],
                "idempotency_record": {
                    "principal_ref": self._PRINCIPAL,
                    "idempotency_key": f"{command.actor_ref}:{command.idempotency_key}",
                    "payload_digest": command.payload_digest,
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
    "ResourceStateProjection",
]
