"""Soul anchor authority. Anchoring records provenance and grants no operation rights."""
from __future__ import annotations

from types import MappingProxyType
from typing import Literal, Mapping

from pydantic import ConfigDict, Field

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import StrictGameplayModel
from app.gameplay.settlement_plan import build_multi_stream_atomic_event_batch
from app.gameplay.soul_sources import SoulResourceSourcePin, SoulResourceSourceReader
from app.gameplay.soul_presence_sources import SoulPresenceSourceReader


_PRINCIPAL = 'soul.anchor_authority'
_PREFIX = 'gameplay:soul:anchor:'


class SoulAnchorRegistration(StrictGameplayModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    world_ref: str = Field(min_length=1)
    package_ref: str = Field(min_length=1)
    version: str = Field(min_length=1)
    timeline_ref: str = Field(min_length=1)
    lifetime: Literal['until_revoked']
    resource_pins: tuple[SoulResourceSourcePin, ...] = Field(min_length=1)


class SoulAnchorRequest(StrictGameplayModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    actor_ref: str = Field(min_length=1)
    world_ref: str = Field(min_length=1)
    package_ref: str = Field(min_length=1)
    version: str = Field(min_length=1)
    incarnation: int = Field(ge=1, strict=True)
    expected_revision: int = Field(ge=0, strict=True)
    idempotency_key: str = Field(min_length=1)


class SoulAnchorReceipt(StrictGameplayModel):
    committed: bool
    incarnation: int | None = None
    committed_event_ids: tuple[str, ...] = ()
    zero_write: bool = False
    stop_reason: str | None = None


class SoulAnchorAuthority:
    def __init__(self, *, store: GameplayEventStore, presence_sources: SoulPresenceSourceReader,
                 resource_sources: SoulResourceSourceReader,
                 registrations: tuple[SoulAnchorRegistration, ...] = ()) -> None:
        if (type(presence_sources) is not SoulPresenceSourceReader
                or type(resource_sources) is not SoulResourceSourceReader
                or presence_sources._store is not store or resource_sources._store is not store):
            raise ValueError('soul_anchor_source_store')
        policies: dict[tuple[str, str, str], SoulAnchorRegistration] = {}
        for item in registrations:
            row = SoulAnchorRegistration.model_validate(item.model_dump(mode='python'))
            key = (row.world_ref, row.package_ref, row.version)
            if key in policies:
                raise ValueError('soul_anchor_registration_duplicate')
            if len(set(row.resource_pins)) != len(row.resource_pins):
                raise ValueError('soul_anchor_registration_duplicate')
            if any(pin.world_ref != row.world_ref or pin.timeline_ref != row.timeline_ref for pin in row.resource_pins):
                raise ValueError('soul_anchor_registration_scope')
            policies[key] = row
        self.store = store
        self._presence = presence_sources
        self._resources = resource_sources
        self._registrations: Mapping[tuple[str, str, str], SoulAnchorRegistration] = MappingProxyType(policies)

    @staticmethod
    def stream_id(world_ref: str, actor_ref: str) -> str:
        return f'{_PREFIX}{world_ref}:{actor_ref}'

    def issue(self, request: SoulAnchorRequest) -> SoulAnchorReceipt:
        request = SoulAnchorRequest.model_validate(request.model_dump(mode='python') if isinstance(request, SoulAnchorRequest) else request)
        stream = self.stream_id(request.world_ref, request.actor_ref)
        try:
            prior = self.store.get_by_idempotency(_PRINCIPAL, request.idempotency_key)
            if prior is not None:
                self._original(request, prior, stream)
                return SoulAnchorReceipt(committed=True, incarnation=request.incarnation,
                    committed_event_ids=tuple(prior.committed_event_ids), zero_write=True)
            registration = self._registrations.get((request.world_ref, request.package_ref, request.version))
            if registration is None:
                return self._reject(request, stream, 'soul_anchor_registration')
            head = self.store.get_stream_head(stream)
            if head != request.expected_revision:
                return self._reject(request, stream, 'revision_conflict')
            if head:
                return self._reject(request, stream, 'soul_anchor_already_bound')
            presence = self._presence.read(actor_ref=request.actor_ref, world_ref=request.world_ref,
                expected_incarnation=request.incarnation)
            if any(pin.actor_ref != request.actor_ref for pin in registration.resource_pins):
                return self._reject(request, stream, 'soul_anchor_registration_actor')
            resources = [self._resources.read(pin) for pin in registration.resource_pins]
            if any(source.entry is None for source in resources):
                return self._reject(request, stream, 'soul_anchor_resource_absent')
            reads = dict(presence.read_revisions)
            for source in resources:
                for ref, revision in source.read_revisions.items():
                    if ref in reads and reads[ref] != revision:
                        return self._reject(request, stream, 'soul_anchor_source_cut_conflict')
                    reads[ref] = revision
            payload = self._payload(request, registration, presence, resources)
            batch = self._batch(request, stream, reads, payload)
            result = self.store.append_batch(batch)
            if not result.committed:
                return self._reject(request, stream, result.failure.error_code if result.failure else 'append_rejected')
            return SoulAnchorReceipt(committed=True, incarnation=request.incarnation,
                committed_event_ids=tuple(result.committed_event_ids))
        except (ValueError, KeyError, TypeError) as exc:
            return self._reject(request, stream, str(exc) or 'soul_anchor_invalid')

    def projection(self, *, world_ref: str, actor_ref: str) -> dict[str, object]:
        stream = self.stream_id(world_ref, actor_ref)
        head = self.store.get_stream_head(stream)
        if head == 0:
            return {}
        events = self.store.read_stream(stream, to_revision=head)
        if len(events) != head or head != 1:
            raise ValueError('soul_anchor_history_invalid')
        event = events[0]
        batch = self.store.get_transaction(event.transaction_id)
        if batch is None:
            raise ValueError('soul_anchor_original_invalid')
        request = SoulAnchorRequest(actor_ref=actor_ref, world_ref=world_ref,
            package_ref=event.payload['package_ref'], version=event.payload['version'],
            incarnation=event.payload['incarnation'], expected_revision=0,
            idempotency_key=batch.idempotency_record.idempotency_key)
        receipt = self.store.get_by_idempotency(_PRINCIPAL, request.idempotency_key)
        self._original(request, receipt, stream)
        return dict(event.payload)

    @staticmethod
    def _payload(request, registration, presence, resources):
        return {
            'actor_ref': request.actor_ref, 'world_ref': request.world_ref,
            'incarnation': presence.incarnation, 'presence_event_id': presence.presence_event_id,
            'activation_event_id': presence.activation_event_id,
            'package_ref': registration.package_ref, 'version': registration.version,
            'timeline_ref': registration.timeline_ref, 'lifetime': registration.lifetime,
            'resource_pins': [pin.model_dump(mode='json') for pin in registration.resource_pins],
            'resource_sources': [{
                'pin': source.pin.model_dump(mode='json'), 'projection_revision': source.projection_revision,
                'source_event_refs': list(source.source_event_refs),
                'transaction_event_refs': list(source.transaction_event_refs),
            } for source in resources],
            'presence_source_event_refs': list(presence.source_event_refs),
        }

    def _batch(self, request, stream, reads, payload):
        return build_multi_stream_atomic_event_batch(
            command_id=f'soul:anchor:{request.world_ref}:{request.actor_ref}', principal_ref=_PRINCIPAL,
            expected_revisions={stream: request.expected_revision},
            event_specs={stream: [('soul.anchor.bound', payload)]},
            event_visibility_policies={stream: ['authority_only']},
            idempotency_key=request.idempotency_key, causation_id=f'presence:{request.actor_ref}:{request.incarnation}',
            correlation_id=f'world:{request.world_ref}', read_stream_revisions=reads, pinned_revisions=reads)

    def _original(self, request, receipt, stream):
        invalid = 'soul_anchor_original_invalid'
        if (receipt is None or receipt.committed is not True or receipt.failure is not None
                or len(receipt.committed_event_ids) != 1 or receipt.idempotency_status != 'new_commit'
                or receipt.projection_refresh_hints):
            raise ValueError(invalid)
        batch = self.store.get_transaction(receipt.transaction_id)
        if batch is None or len(batch.events) != 1:
            raise ValueError(invalid)
        event = batch.events[0]
        self._validate_original_event(event, stream)
        record = batch.idempotency_record
        indexed = self.store.get_by_idempotency(record.principal_ref, record.idempotency_key)
        revision = event.stream_revision
        if (record.principal_ref != _PRINCIPAL or record.idempotency_key != request.idempotency_key
                or batch.expected_stream_revisions != {stream: revision - 1}
                or batch.command_id != f'soul:anchor:{request.world_ref}:{request.actor_ref}'
                or batch.outbox_entries or batch.projection_refresh_hints
                or receipt.transaction_id != batch.transaction_id or receipt.command_id != batch.command_id
                or receipt.committed_event_ids != [event.event_id]
                or receipt.resulting_stream_revisions != {stream: revision}
                or receipt.global_sequence_range != (event.global_sequence, event.global_sequence)
                or indexed is None or not indexed.committed
                or self.store.get_idempotency_record(_PRINCIPAL, request.idempotency_key) != record):
            raise ValueError(invalid)
        payload = dict(event.payload)
        if any(payload.get(key) != getattr(request, key) for key in (
                'actor_ref', 'world_ref', 'package_ref', 'version', 'incarnation')):
            raise ValueError(invalid)
        self._validate_source_cut(payload, batch.read_stream_revisions, event.global_sequence)
        original_request = request.model_copy(update={'expected_revision': revision - 1})
        expected = self._batch(original_request, stream, batch.read_stream_revisions, payload)
        expected.events[0] = expected.events[0].model_copy(update={
            'stream_revision': event.stream_revision, 'global_sequence': event.global_sequence})
        if expected.model_dump(mode='json') != batch.model_dump(mode='json'):
            raise ValueError(invalid)
        return batch

    def _validate_original_event(self, event, stream):
        invalid = 'soul_anchor_original_invalid'
        if (event.event_type != 'soul.anchor.bound' or event.schema_version != 1
                or event.visibility_policy != 'authority_only' or event.stream_id != stream
                or event.stream_revision != 1 or event.global_sequence < 1):
            raise ValueError(invalid)
        batch = self.store.get_transaction(event.transaction_id)
        if batch is None or event not in batch.events or self.store.get_event(event.event_id) != event:
            raise ValueError(invalid)

    def _validate_source_cut(self, payload, reads, anchor_sequence):
        invalid = 'soul_anchor_original_invalid'
        actor, world = payload.get('actor_ref'), payload.get('world_ref')
        population, presence, life = f'population:{world}', f'presence:{world}', f'gameplay:character:life:character:{actor}'
        pins = payload.get('resource_pins')
        sources = payload.get('resource_sources')
        if not isinstance(pins, list) or not pins or not isinstance(sources, list) or len(pins) != len(sources):
            raise ValueError(invalid)
        expected = {population, presence, life}
        refs = set(payload.get('presence_source_event_refs', ()))
        active, _ = self._presence._presence._history(world, head=reads.get(presence))
        if active.get(f'character:{actor}') != payload.get('incarnation'):
            raise ValueError(invalid)
        activation = self._presence._presence._sources.recover(payload.get('activation_event_id'),
            world_ref=world, profile_ref=f'character:{actor}', at_revision=reads.get(population))
        presence_events = self.store.read_stream(presence, to_revision=reads.get(presence))
        expected_presence_refs = set(activation.source_event_refs) | {e.event_id for e in presence_events}
        if refs != expected_presence_refs:
            raise ValueError(invalid)
        spawns = [e for e in presence_events if e.event_id == payload.get('presence_event_id')]
        if (len(spawns) != 1 or spawns[0].event_type != 'population.presence.spawned'
                or spawns[0].payload.get('character_ref') != f'character:{actor}'
                or spawns[0].payload.get('incarnation') != payload.get('incarnation')
                or spawns[0].payload.get('source_activation_event_id') != payload.get('activation_event_id')):
            raise ValueError(invalid)
        for pin, source in zip(pins, sources, strict=True):
            if (not isinstance(pin, dict) or pin.get('actor_ref') != actor
                    or pin.get('world_ref') != world or pin.get('timeline_ref') != payload.get('timeline_ref')):
                raise ValueError(invalid)
            resource_stream = f"gameplay:resources:{actor}"
            expected.add(resource_stream)
            if (not isinstance(source, dict) or source.get('pin') != pin
                    or not isinstance(source.get('source_event_refs'), list)
                    or not isinstance(source.get('transaction_event_refs'), list)
                    or not set(source['source_event_refs']).issubset(set(source['transaction_event_refs']))):
                raise ValueError(invalid)
            validated_pin = SoulResourceSourcePin.model_validate(pin)
            events = self.store.read_stream(resource_stream, to_revision=reads.get(resource_stream))
            if len(events) != reads.get(resource_stream) or [e.event_id for e in events] != source['source_event_refs']:
                raise ValueError(invalid)
            original_events = {}
            for event in events:
                original = self._resources._original_batch(event)
                self._resources._admit_batch(original, validated_pin, resource_stream)
                original_events.update({item.event_id: item for item in original.events})
            ordered = sorted(original_events.values(), key=lambda item: item.global_sequence)
            if [e.event_id for e in ordered] != source['transaction_event_refs']:
                raise ValueError(invalid)
            refs.update(source['transaction_event_refs'])
        if set(reads) != expected or reads.get(life) != 0:
            raise ValueError(invalid)
        for ref in refs:
            try:
                source_event = self.store.get_event(ref)
            except KeyError as exc:
                raise ValueError(invalid) from exc
            if source_event is None or source_event.global_sequence >= anchor_sequence:
                raise ValueError(invalid)

    @staticmethod
    def _reject(request, stream, reason):
        return SoulAnchorReceipt(committed=False, stop_reason=reason)
