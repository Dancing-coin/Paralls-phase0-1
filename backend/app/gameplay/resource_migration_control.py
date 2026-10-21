"""Durable D17 pause and reservation-drain observation owner."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult
from app.gameplay.resource_body_runtime import ResourceBodyRuntimeProjector, ResourceBoundsMigrationAuthorityService, ResourceBoundsMigrationRequest, ResourceDefinitionRegistry
from app.gameplay.models import GameplayEvent
from app.gameplay.settlement_plan import build_multi_stream_atomic_event_batch


CONTROL_PRINCIPAL = "resource_migration_control"
MIGRATION_PRINCIPAL = "resource_migration_owner"


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _actor(actor_ref: str) -> str:
    if not isinstance(actor_ref, str) or not actor_ref or actor_ref.startswith("actor:"):
        raise ValueError("resource_migration_actor_invalid")
    return actor_ref.removeprefix("character:")


@dataclass(frozen=True)
class DrainObservation:
    status: str
    actor_ref: str
    migration_id: str
    resource_stream_revision: int
    reservation_refs: tuple[str, ...]
    observation_digest: str


class ResourceMigrationControlAuthority:
    """Owner for durable pause facts; it does not mutate resource reservations."""

    def __init__(self, *, store: GameplayEventStore, definitions: ResourceDefinitionRegistry | None = None) -> None:
        self.store = store
        self.definitions = definitions

    def _validate_pause_receipt(self, receipt, *, actor: str, migration_id: str,
                                 idempotency_key: str, request_digest: str,
                                 control_stream: str) -> None:
        command_id = f"resource-migration-pause:{actor}:{migration_id}"
        if not receipt.committed or receipt.command_id != command_id or not receipt.transaction_id:
            raise ValueError("resource_migration_receipt_incomplete")
        transaction = self.store.get_transaction(receipt.transaction_id)
        if (transaction is None or transaction.command_id != command_id
                or transaction.idempotency_record.principal_ref != CONTROL_PRINCIPAL
                or transaction.idempotency_record.idempotency_key != idempotency_key
                or len(transaction.events) != 1
                or set(transaction.expected_stream_revisions) != {control_stream}):
            raise ValueError("resource_migration_receipt_incomplete")
        event = transaction.events[0]
        if (event.stream_id != control_stream or event.event_type != "gameplay.resource_migration.paused"
                or event.visibility_policy != "authority_only" or event.transaction_id != transaction.transaction_id
                or event.command_id != command_id or event.payload.get("actor_ref") != actor
                or event.payload.get("migration_id") != migration_id
                or event.payload.get("request_digest") != request_digest):
            raise ValueError("resource_migration_receipt_incomplete")
        if (receipt.committed_event_ids != [event.event_id]
                or receipt.resulting_stream_revisions != {control_stream: event.stream_revision}
                or receipt.global_sequence_range != (event.global_sequence, event.global_sequence)):
            raise ValueError("resource_migration_receipt_incomplete")
        try:
            persisted = self.store.get_event(event.event_id)
        except KeyError as exc:
            raise ValueError("resource_migration_receipt_incomplete") from exc
        if persisted.model_dump(mode="json") != event.model_dump(mode="json"):
            raise ValueError("resource_migration_receipt_incomplete")

    def pause(
        self,
        *,
        actor_ref: str,
        migration_id: str,
        source_definition_revision: str,
        target_definition_revision: str,
        schema_digest: str,
        codec_digest: str,
        migrator_digest: str,
        expected_resource_revision: int,
        expected_control_revision: int,
        idempotency_key: str,
        authority_principal: str,
        read_stream_revisions: dict[str, int] | None = None,
    ) -> AppendBatchResult:
        actor = _actor(actor_ref)
        values = (migration_id, source_definition_revision, target_definition_revision,
                  schema_digest, codec_digest, migrator_digest, idempotency_key, authority_principal)
        if any(not isinstance(value, str) or not value for value in values):
            raise ValueError("resource_migration_identity_invalid")
        if any(type(value) is not int or value < 0 for value in (expected_resource_revision, expected_control_revision)):
            raise ValueError("resource_migration_revision_invalid")
        read_set = dict(read_stream_revisions or {})
        if any(not isinstance(key, str) or not key or type(value) is not int or value < 0 for key, value in read_set.items()):
            raise ValueError("resource_migration_read_set_invalid")
        resource_stream = f"gameplay:resources:{actor}"
        control_stream = f"gameplay:resource-migration-control:{actor}"
        if resource_stream in read_set and read_set[resource_stream] != expected_resource_revision:
            raise ValueError("resource_migration_read_set_conflict")
        if control_stream in read_set and read_set[control_stream] != expected_control_revision:
            raise ValueError("resource_migration_read_set_conflict")
        request = {
            "actor_ref": actor, "migration_id": migration_id,
            "source_definition_revision": source_definition_revision,
            "target_definition_revision": target_definition_revision,
            "schema_digest": schema_digest, "codec_digest": codec_digest,
            "migrator_digest": migrator_digest,
            "expected_resource_revision": expected_resource_revision,
            "read_stream_revisions": read_set,
            "authority_principal": authority_principal,
        }
        request_digest = _digest(request)
        prior = self.store.get_by_idempotency(CONTROL_PRINCIPAL, idempotency_key)
        if prior is not None:
            if not prior.committed_event_ids:
                raise ValueError("resource_migration_receipt_incomplete")
            try:
                event = self.store.get_event(prior.committed_event_ids[0])
            except KeyError as exc:
                raise ValueError("resource_migration_receipt_incomplete") from exc
            if event.payload.get("request_digest") != request_digest:
                raise ValueError("resource_migration_idempotency_reused")
            self._validate_pause_receipt(prior, actor=actor, migration_id=migration_id,
                                         idempotency_key=idempotency_key, request_digest=request_digest,
                                         control_stream=control_stream)
            return prior.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
        if self.store.get_stream_head(resource_stream) != expected_resource_revision:
            raise ValueError("resource_migration_resource_revision_conflict")
        if self.store.get_stream_head(control_stream) != expected_control_revision:
            raise ValueError("resource_migration_control_revision_conflict")
        prior_states: dict[str, str] = {}
        for prior_event in self.store.read_stream(control_stream):
            prior_id = str(prior_event.payload.get("migration_id", ""))
            if not prior_id:
                continue
            if prior_event.event_type == "gameplay.resource_migration.paused":
                prior_states[prior_id] = "paused"
            elif prior_event.event_type == "gameplay.resource_migration.completed":
                prior_states[prior_id] = "completed"
        if migration_id in prior_states:
            raise ValueError("resource_migration_id_already_used")
        if any(state == "paused" and prior_id != migration_id for prior_id, state in prior_states.items()):
            raise ValueError("resource_migration_overlap")
        event = {
            "actor_ref": actor, "migration_id": migration_id,
            "state": "paused", "source_definition_revision": source_definition_revision,
            "target_definition_revision": target_definition_revision,
            "schema_digest": schema_digest, "codec_digest": codec_digest,
            "migrator_digest": migrator_digest,
            "resource_stream_revision": expected_resource_revision,
            "control_stream_revision": expected_control_revision + 1,
            "authority_principal": authority_principal,
            "request_digest": request_digest,
        }
        batch = build_multi_stream_atomic_event_batch(
            command_id=f"resource-migration-pause:{actor}:{migration_id}",
            principal_ref=CONTROL_PRINCIPAL,
            expected_revisions={control_stream: expected_control_revision},
            event_specs={control_stream: [("gameplay.resource_migration.paused", event)]},
            idempotency_key=idempotency_key,
            causation_id=f"cause:{migration_id}", correlation_id=f"correlation:{migration_id}",
            read_stream_revisions={resource_stream: expected_resource_revision, **read_set},
            event_visibility_policies={control_stream: ["authority_only"]},
        )
        return self.store.append_batch(batch)

    def observe_drain(
        self, *, actor_ref: str, migration_id: str, expected_resource_revision: int,
        read_stream_revisions: dict[str, int] | None = None,
    ) -> DrainObservation:
        actor = _actor(actor_ref)
        if not isinstance(migration_id, str) or not migration_id:
            raise ValueError("resource_migration_id_invalid")
        if type(expected_resource_revision) is not int or expected_resource_revision < 0:
            raise ValueError("resource_migration_revision_invalid")
        resource_stream = f"gameplay:resources:{actor}"
        read_set = dict(read_stream_revisions or {})
        if any(not isinstance(key, str) or not key or type(value) is not int or value < 0 for key, value in read_set.items()):
            raise ValueError("resource_migration_read_set_invalid")
        actual_revision = self.store.get_stream_head(resource_stream)
        if actual_revision != expected_resource_revision:
            return DrainObservation("revision_conflict", actor, migration_id, actual_revision, (), _digest({"status": "revision_conflict", "revision": actual_revision}))
        for stream_id, expected_revision in read_set.items():
            if self.store.get_stream_head(stream_id) != expected_revision:
                return DrainObservation("revision_conflict", actor, migration_id, actual_revision, (), _digest({"status": "revision_conflict", "revision": actual_revision, "read_set": read_set}))
        control_stream = f"gameplay:resource-migration-control:{actor}"
        if not any(event.event_type == "gameplay.resource_migration.paused" and event.payload.get("migration_id") == migration_id for event in self.store.read_stream(control_stream)):
            return DrainObservation("unknown", actor, migration_id, actual_revision, (), _digest({"status": "unknown", "revision": actual_revision, "migration_id": migration_id}))
        events = self.store.read_stream(resource_stream)
        if self.store.get_stream_head(resource_stream) != actual_revision:
            latest_revision = self.store.get_stream_head(resource_stream)
            return DrainObservation("revision_conflict", actor, migration_id, latest_revision, (), _digest({"status": "revision_conflict", "revision": latest_revision}))
        for stream_id, expected_revision in read_set.items():
            if self.store.get_stream_head(stream_id) != expected_revision:
                return DrainObservation("revision_conflict", actor, migration_id, actual_revision, (), _digest({"status": "revision_conflict", "revision": actual_revision, "read_set": read_set}))
        try:
            projection = ResourceBodyRuntimeProjector(resource_definitions=self.definitions).rebuild_resources(actor, events)
        except Exception:
            return DrainObservation("unknown", actor, migration_id, actual_revision, (), _digest({"status": "unknown", "revision": actual_revision}))
        refs = tuple(sorted(projection.reservations))
        status = "drained" if not refs else "pending"
        return DrainObservation(status, actor, migration_id, actual_revision, refs, _digest({"status": status, "revision": actual_revision, "reservation_refs": refs}))


class ResourceMigrationOwner:
    """This-phase D06 owner for one paused, drained resource stream.

    It reuses the existing migration planner and event store. The owner never
    invents a definition: callers must provide both registered revisions.
    """

    def __init__(self, *, store: GameplayEventStore, definitions: ResourceDefinitionRegistry) -> None:
        self.store = store
        self.definitions = definitions

    def _validate_duplicate_receipt(self, prior, *, request_digest: str, command_id: str,
                                    stream: str, control: str) -> None:
        """Re-read the durable transaction before replaying a migration receipt."""
        if not prior.committed or prior.command_id != command_id or not prior.transaction_id:
            raise ValueError("resource_migration_receipt_incomplete")
        transaction = self.store.get_transaction(prior.transaction_id)
        if transaction is None or transaction.command_id != command_id:
            raise ValueError("resource_migration_receipt_incomplete")
        expected_ids = tuple(event.event_id for event in transaction.events)
        if tuple(prior.committed_event_ids) != expected_ids or len(expected_ids) < 2:
            raise ValueError("resource_migration_receipt_incomplete")
        expected_revisions: dict[str, int] = {}
        for event in transaction.events:
            expected_revisions[event.stream_id] = event.stream_revision
        if prior.resulting_stream_revisions != expected_revisions:
            raise ValueError("resource_migration_receipt_incomplete")
        if prior.global_sequence_range != (transaction.events[0].global_sequence,
                                           transaction.events[-1].global_sequence):
            raise ValueError("resource_migration_receipt_incomplete")
        if transaction.idempotency_record.principal_ref != MIGRATION_PRINCIPAL:
            raise ValueError("resource_migration_receipt_incomplete")
        if set(transaction.expected_stream_revisions) != {stream, control}:
            raise ValueError("resource_migration_receipt_incomplete")
        if sum(event.stream_id == stream for event in transaction.events) < 1 or \
                sum(event.stream_id == control for event in transaction.events) != 1 or \
                not any(event.event_type == "gameplay.resource_migration.completed" and event.stream_id == control
                         for event in transaction.events):
            raise ValueError("resource_migration_receipt_incomplete")
        if any(event.transaction_id != transaction.transaction_id or event.command_id != command_id
               for event in transaction.events):
            raise ValueError("resource_migration_receipt_incomplete")
        try:
            persisted = [self.store.get_event(event_id) for event_id in expected_ids]
        except KeyError as exc:
            raise ValueError("resource_migration_receipt_incomplete") from exc
        if [event.model_dump(mode="json") for event in persisted] != [event.model_dump(mode="json") for event in transaction.events]:
            raise ValueError("resource_migration_receipt_incomplete")
        if any(event.payload.get("request_digest") != request_digest for event in persisted):
            raise ValueError("resource_migration_idempotency_reused")

    def apply(self, *, actor_ref: str, migration_id: str, from_definition_version: str,
              to_definition_version: str, migration_digest: str, migrator_code_digest: str,
              authority_principal: str, idempotency_key: str) -> AppendBatchResult:
        actor = _actor(actor_ref)
        stream = f"gameplay:resources:{actor}"
        control = f"gameplay:resource-migration-control:{actor}"
        command_id = f"resource-migration-apply:{actor}:{migration_id}"
        request = {"actor_ref": actor, "migration_id": migration_id,
                   "from_definition_version": from_definition_version,
                   "to_definition_version": to_definition_version,
                   "migration_digest": migration_digest, "migrator_code_digest": migrator_code_digest,
                   "authority_principal": authority_principal}
        request_digest = _digest(request)
        prior = self.store.get_by_idempotency(MIGRATION_PRINCIPAL, idempotency_key)
        if prior is not None:
            self._validate_duplicate_receipt(prior, request_digest=request_digest,
                                             command_id=command_id, stream=stream, control=control)
            return prior.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
        frozen_revisions = {stream: self.store.get_stream_head(stream),
                            control: self.store.get_stream_head(control)}
        control_events = self.store.read_stream(control)
        paused_events = [event for event in control_events
                         if event.event_type == "gameplay.resource_migration.paused"
                         and event.payload.get("migration_id") == migration_id]
        if not paused_events:
            raise ValueError("resource_migration_not_paused")
        if any(event.event_type == "gameplay.resource_migration.completed"
               and event.payload.get("migration_id") == migration_id for event in control_events):
            raise ValueError("resource_migration_already_completed")
        paused = paused_events[-1].payload
        if (paused.get("source_definition_revision") != from_definition_version
                or paused.get("target_definition_revision") != to_definition_version):
            raise ValueError("migration_revision_pin_mismatch")
        paused_digest = str(paused.get("migrator_digest", ""))
        if paused_digest.startswith("sha256:") and paused_digest != migrator_code_digest:
            raise ValueError("migration_code_digest_pin_mismatch")
        projection = ResourceBodyRuntimeProjector(resource_definitions=self.definitions).rebuild_resources(actor, self.store.read_stream(stream))
        if projection.reservations or any(lock[3] == "open" for lock in projection.locks.values()):
            raise ValueError("resource_migration_not_drained")
        if not projection.entries:
            raise ValueError("resource_migration_resource_unknown")
        planner = ResourceBoundsMigrationAuthorityService(definitions=self.definitions)
        plans = []
        for resource_id, entry in sorted(projection.entries.items()):
            if entry.definition_version != from_definition_version:
                raise ValueError("resource_migration_source_definition_mismatch")
            plans.append(planner.plan(ResourceBoundsMigrationRequest(
                actor_ref=actor, resource_id=resource_id,
                from_definition_version=from_definition_version,
                to_definition_version=to_definition_version,
                expected_projection_revision=projection.projection_revision,
                migration_digest=migration_digest,
                migrator_code_digest=migrator_code_digest,
            ), projection))
        specs = [(plan.event_type, {**dict(plan.payload), "migration_id": migration_id, "request_digest": request_digest}) for plan in plans]
        specs.append(("gameplay.resource_migration.completed", {**request, "request_digest": request_digest, "resource_ids": [plan.resource_id for plan in plans]}))
        tx = build_multi_stream_atomic_event_batch(
            command_id=command_id, principal_ref=MIGRATION_PRINCIPAL,
            expected_revisions=frozen_revisions,
            event_specs={stream: specs[:-1], control: [specs[-1]]},
            idempotency_key=idempotency_key, causation_id=f"cause:{command_id}",
            correlation_id=f"correlation:{command_id}",
            read_stream_revisions=frozen_revisions,
            event_visibility_policies={stream: ["authority_only"] * len(plans), control: ["authority_only"]},
        )
        return self.store.append_batch(tx)


__all__ = ["DrainObservation", "ResourceMigrationControlAuthority", "ResourceMigrationOwner"]
