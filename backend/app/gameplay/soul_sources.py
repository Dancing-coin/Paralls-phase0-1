"""Closed, read-only Resource evidence adapter. This does not grant Soul access."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from types import MappingProxyType
from typing import Mapping

from pydantic import BaseModel, ConfigDict, Field

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AtomicEventBatch, GameplayEvent
from app.gameplay.resource_body_runtime import (
    ResourceBodyRuntimeProjector, ResourceDefinitionRegistry, ResourceEntry,
)
from app.gameplay.resource_materialization import (
    RESOURCE_TEMPLATE_CALLER, ResourceMaterializationAuthorityService,
)


class SoulResourceSourcePin(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    actor_ref: str = Field(min_length=1)
    world_ref: str = Field(min_length=1)
    timeline_ref: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    definition_version: str = Field(min_length=1)


@dataclass(frozen=True)
class SoulResourceSource:
    pin: SoulResourceSourcePin
    entry: ResourceEntry | None
    read_revisions: Mapping[str, int]
    source_event_refs: tuple[str, ...]
    transaction_event_refs: tuple[str, ...]
    last_global_sequence: int
    projection_revision: str


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


class SoulResourceSourceReader:
    """A pinned Resource slice, including absent head0, for a later owner CAS.

    Definitions identify units/bounds only. Neither a resource name nor this
    slice establishes life/mind semantics, Presence, or any of the Soul gates.
    """

    def __init__(self, *, store: GameplayEventStore, definitions: ResourceDefinitionRegistry):
        self._store = store
        self._definitions = definitions

    def read(self, pin: SoulResourceSourcePin) -> SoulResourceSource:
        pin = SoulResourceSourcePin.model_validate(pin.model_dump() if isinstance(pin, SoulResourceSourcePin) else pin)
        if pin.actor_ref.startswith(('actor:', 'character:', 'npc:')):
            raise ValueError('soul_resource_source_actor_alias')
        definition = self._definitions.resolve(pin.resource_id, pin.definition_version)
        stream = f'gameplay:resources:{pin.actor_ref}'
        head = self._store.get_stream_head(stream)
        events = self._store.read_stream(stream, to_revision=head) if head else []
        if len(events) != head or any(event.stream_revision != index for index, event in enumerate(events, 1)):
            raise ValueError('soul_resource_source_history')
        transactions = {}
        originals = {}
        for event in events:
            if event.payload.get('actor_ref') != pin.actor_ref:
                raise ValueError('soul_resource_source_actor')
            if event.transaction_id not in transactions:
                batch = self._original_batch(event)
                self._admit_batch(batch, pin, stream)
                transactions[event.transaction_id] = batch
                originals.update({item.event_id: item for item in batch.events})
            original = originals.get(event.event_id)
            if original is None or _digest(original.model_dump(mode='json')) != _digest(event.model_dump(mode='json')):
                raise ValueError('soul_resource_source_receipt')
        projection = ResourceBodyRuntimeProjector(resource_definitions=self._definitions).rebuild_resources(pin.actor_ref, events)
        entry = projection.entries.get(pin.resource_id)
        if entry is not None and entry.definition_version != pin.definition_version:
            raise ValueError('soul_resource_source_definition_version')
        if entry is not None and (entry.minimum, entry.maximum) != (definition.minimum, definition.maximum):
            raise ValueError('soul_resource_source_definition_bounds')
        ordered = sorted(originals.values(), key=lambda item: item.global_sequence)
        return SoulResourceSource(pin, entry, MappingProxyType({stream: head}),
            tuple(item.event_id for item in events), tuple(item.event_id for item in ordered),
            max((item.global_sequence for item in ordered), default=0), projection.projection_revision)

    def _original_batch(self, source: GameplayEvent) -> AtomicEventBatch:
        invalid = 'soul_resource_source_receipt'
        batch = self._store.get_transaction(source.transaction_id)
        if batch is None or not batch.events:
            raise ValueError(invalid)
        record = batch.idempotency_record
        receipt = self._store.get_by_idempotency(record.principal_ref, record.idempotency_key)
        revisions = {}
        for event in batch.events:
            revisions[event.stream_id] = event.stream_revision
        if (receipt is None or receipt.committed is not True or receipt.failure is not None
                or receipt.transaction_id != batch.transaction_id or receipt.command_id != batch.command_id
                or receipt.committed_event_ids != [item.event_id for item in batch.events]
                or receipt.resulting_stream_revisions != revisions
                or receipt.global_sequence_range != (batch.events[0].global_sequence, batch.events[-1].global_sequence)
                or self._store.get_idempotency_record(record.principal_ref, record.idempotency_key) != record
                or source not in batch.events or batch.outbox_entries or batch.projection_refresh_hints):
            raise ValueError(invalid)
        for index, event in enumerate(batch.events):
            if (event.transaction_id != batch.transaction_id or event.command_id != batch.command_id
                    or type(event.schema_version) is not int or event.schema_version != 1 or event.visibility_policy != 'authority_only'
                    or type(event.stream_revision) is not int or event.stream_revision < 1
                    or type(event.global_sequence) is not int
                    or event.global_sequence != batch.events[0].global_sequence + index
                    or event.global_sequence < 1):
                raise ValueError(invalid)
            try:
                if self._store.get_event(event.event_id) != event:
                    raise ValueError(invalid)
            except KeyError as exc:
                raise ValueError(invalid) from exc
        return batch

    def _admit_batch(self, batch: AtomicEventBatch, pin: SoulResourceSourcePin, stream: str) -> None:
        principal = batch.idempotency_record.principal_ref
        if principal == RESOURCE_TEMPLATE_CALLER:
            if any(event.event_type != 'gameplay.resource.materialized' or event.stream_id != stream for event in batch.events):
                raise ValueError('soul_resource_source_genesis')
            payload = batch.events[0].payload
            if payload.get('world_ref') != pin.world_ref or payload.get('timeline_ref') != pin.timeline_ref:
                raise ValueError('soul_resource_scope_mismatch')
            # With no registry this call can only recover the existing original
            # receipt. A missing/invalid idempotency record cannot cause a write.
            try:
                ResourceMaterializationAuthorityService(store=self._store).materialize(
                    actor_ref=pin.actor_ref, world_ref=pin.world_ref, timeline_ref=pin.timeline_ref,
                    world_tick=payload['materialized_world_tick'], expected_revision=0,
                    idempotency_key=batch.idempotency_record.idempotency_key,
                    read_stream_revisions=dict(batch.read_stream_revisions))
            except (ValueError, KeyError, TypeError) as exc:
                raise ValueError('soul_resource_source_genesis') from exc
        elif principal == 'resource_body_action_authority':
            self._action_batch(batch, pin.actor_ref, stream)
        elif principal == 'resource_reservation_authority':
            self._reservation_batch(batch, pin.actor_ref, stream)
        else:
            raise ValueError('soul_resource_source_owner_unsupported')

    @staticmethod
    def _action_batch(batch: AtomicEventBatch, actor: str, stream: str) -> None:
        invalid = 'soul_resource_source_action'
        if len(batch.events) != 2:
            raise ValueError(invalid)
        resource, action = batch.events
        payload = action.payload
        cost = payload.get('stamina_cost')
        if (type(cost) is not int or cost <= 0
                or any(not isinstance(payload.get(key), str) or not payload[key] for key in ('action_ref', 'stamina_resource_id', 'required_function_id'))):
            raise ValueError(invalid)
        version = payload.get('request_digest_version')
        expected_action = dict(actor_ref=actor, action_ref=payload['action_ref'], stamina_resource_id=payload['stamina_resource_id'],
            stamina_cost=cost, required_function_id=payload['required_function_id'])
        if type(version) is int and version == 2:
            if re.fullmatch(r'sha256:[0-9a-f]{64}', batch.idempotency_record.payload_digest) is None:
                raise ValueError(invalid)
            expected_action['request_digest_version'] = 2
        elif version is not None:
            raise ValueError(invalid)
        resource_revision = batch.expected_stream_revisions.get(stream)
        body_stream, action_stream = f'gameplay:body:{actor}', f'gameplay:actions:{actor}'
        expected_resource = dict(actor_ref=actor, resource_id=payload['stamina_resource_id'], delta=-cost, reason_ref=payload['action_ref'])
        if (resource.event_type != 'gameplay.resource.adjusted' or resource.stream_id != stream
                or action.event_type != 'gameplay.action.settled' or action.stream_id != action_stream
                or dict(resource.payload) != expected_resource or dict(payload) != expected_action
                or type(resource.payload.get('delta')) is not int
                or set(batch.expected_stream_revisions) != {stream, body_stream, action_stream}
                or batch.pinned_revisions != {'resource': resource_revision, 'body': batch.expected_stream_revisions[body_stream]}
                or batch.read_stream_revisions != ({stream: resource_revision, body_stream: batch.expected_stream_revisions[body_stream]} if version == 2 else {})
                or not batch.idempotency_record.idempotency_key.startswith(actor + ':')
                or batch.transaction_id != 'tx:' + batch.command_id
                or batch.result_digest != _digest(dict(actor_ref=actor, action_ref=payload['action_ref'], stamina_cost=cost))):
            raise ValueError(invalid)
        for index, event in enumerate(batch.events, 1):
            if (event.event_id != f'evt:{batch.command_id}:resource-body:{index}'
                    or event.stream_revision != batch.expected_stream_revisions[event.stream_id] + 1
                    or event.causation_id != resource.causation_id or event.correlation_id != resource.correlation_id):
                raise ValueError(invalid)

    @staticmethod
    def _reservation_batch(batch: AtomicEventBatch, actor: str, stream: str) -> None:
        invalid = 'soul_resource_source_reservation'
        pairs = {'gameplay.resource.reservation_created': 'gameplay.resource.lock_created',
            'gameplay.resource.reservation_consumed': 'gameplay.resource.lock_consumed',
            'gameplay.resource.reservation_released': 'gameplay.resource.lock_released'}
        if len(batch.events) != 2:
            raise ValueError(invalid)
        reservation, lock = batch.events
        payload = dict(reservation.payload)
        if (reservation.event_type not in pairs or lock.event_type != pairs[reservation.event_type]
                or dict(lock.payload) != payload or set(payload) != {'actor_ref', 'resource_id', 'reservation_ref', 'lock_ref', 'amount'}
                or payload.get('actor_ref') != actor or type(payload.get('amount')) is not int or payload['amount'] <= 0
                or any(not isinstance(payload.get(key), str) or not payload[key] for key in ('resource_id', 'reservation_ref', 'lock_ref'))
                or set(batch.expected_stream_revisions) != {stream} or batch.pinned_revisions
                or not batch.idempotency_record.idempotency_key.startswith(actor + ':')
                or batch.transaction_id != 'tx:' + batch.command_id
                or batch.result_digest != 'sha256:' + _digest(payload)):
            raise ValueError(invalid)
        reads = {stream: batch.expected_stream_revisions[stream]}
        if reservation.event_type == 'gameplay.resource.reservation_created':
            control = f'gameplay:resource-migration-control:{actor}'
            if control not in batch.read_stream_revisions:
                raise ValueError(invalid)
            reads[control] = batch.read_stream_revisions[control]
        if batch.read_stream_revisions != reads:
            raise ValueError(invalid)
        for index, event in enumerate(batch.events):
            if (event.stream_id != stream or event.stream_revision != batch.expected_stream_revisions[stream] + index + 1
                    or event.event_id != f'evt:{batch.command_id}:{index}'
                    or event.causation_id != reservation.causation_id or event.correlation_id != reservation.correlation_id):
                raise ValueError(invalid)
