"""Closed activation evidence for Presence; no serialized source can grant trust."""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from types import MappingProxyType
from typing import Mapping

from app.gameplay.models import GameplayEvent
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.population_continuity.activation import ProfileActivationAuthority
from app.population_continuity.models import ActivationGrant, ActivationProposal


_COMMITTED = 'population.activation.committed'
_LIFECYCLE = frozenset((_COMMITTED, 'population.activation.suspended',
    'population.activation.requeued', 'population.activation.locked'))


@dataclass(frozen=True)
class ActivationSource:
    event_id: str
    world_ref: str
    profile_ref: str
    identity_digest: str
    read_revisions: Mapping[str, int]
    source_event_refs: tuple[str, ...]
    last_global_sequence: int


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


class ActivationSourceReader:
    """Composition binds a real authority, exact producer and immutable grants.

    Deployment grants authorize new admission. Historical receipt identity is
    reconstructed from its original values, independently of current content.
    Consumers must atomically CAS the returned read revisions when writing.
    """

    def __init__(self, *, authority: ProfileActivationAuthority, producer_ref: str):
        if type(authority) is not ProfileActivationAuthority:
            raise ValueError('activation_source_authority')
        if not isinstance(producer_ref, str) or not producer_ref.strip():
            raise ValueError('activation_source_producer')
        self._authority = authority
        self._store = authority.store
        self._producer = producer_ref
        # Tuples of primitives prevent mutation through retained Pydantic objects.
        grants = [ActivationGrant.model_validate(item.model_dump()) for item in authority.grants]
        self._grants = tuple((g.profile_ref, g.world_ref, g.package_revision,
            g.policy_revision, tuple(g.scope_grant)) for g in grants)

    def recover(self, event_id: str, *, world_ref: str, profile_ref: str) -> ActivationSource:
        """Validate an original activation, without asserting current permission."""
        event = self._event(event_id)
        self._validate(event, world_ref=world_ref, profile_ref=profile_ref)
        if event.event_type != _COMMITTED:
            raise ValueError('activation_source_not_committed')
        return self._source(event, event.stream_revision, (event,))

    def read(self, event_id: str, *, world_ref: str, profile_ref: str) -> ActivationSource:
        """Admit only the latest activation under current deployment/content pins."""
        if not self._grants:
            raise ValueError('activation_source_grants_required')
        event = self._event(event_id)
        self._validate(event, world_ref=world_ref, profile_ref=profile_ref)
        if event.event_type != _COMMITTED:
            raise ValueError('activation_source_not_committed')
        payload = event.payload
        if not any((profile_ref, world_ref, payload['package_revision'], payload['policy_revision']) == g[:4]
                and set(payload['scope_grant']).issubset(g[4]) for g in self._grants):
            raise ValueError('activation_source_grant')
        try:
            identity = self._authority.registry.authored_identity_digest(profile_ref)
        except KeyError as exc:
            raise ValueError('activation_source_profile') from exc
        if identity != payload['identity_digest']:
            raise ValueError('activation_source_profile')
        head = self._store.get_stream_head(event.stream_id)
        events = self._store.read_stream(event.stream_id, to_revision=head) if head else []
        if (len(events) != head or event.stream_revision > head
                or any(type(item.stream_revision) is not int or item.stream_revision != index
                    for index, item in enumerate(events, 1))):
            raise ValueError('activation_source_history')
        lifecycle = []
        for candidate in events:
            # Verify membership before trusting the index's type/subject filter.
            # Otherwise a changed suspend row could disappear from this actor.
            original = self._store.get_transaction(candidate.transaction_id)
            if (original is None or not any(_canonical(item.model_dump(mode='json'))
                    == _canonical(candidate.model_dump(mode='json')) for item in original.events)):
                raise ValueError('activation_source_history')
            if candidate.event_type in _LIFECYCLE and candidate.payload.get('profile_ref') == profile_ref:
                self._validate(candidate, world_ref=world_ref, profile_ref=profile_ref)
                lifecycle.append(candidate)
        if not lifecycle or _canonical(lifecycle[-1].model_dump(mode='json')) != _canonical(event.model_dump(mode='json')):
            raise ValueError('activation_source_inactive')
        return self._source(event, head, lifecycle, last_sequence=max(item.global_sequence for item in events))

    @staticmethod
    def _source(event, head, events, *, last_sequence=None):
        return ActivationSource(event.event_id, event.payload['world_ref'], event.payload['profile_ref'],
            event.payload['identity_digest'], MappingProxyType({event.stream_id: head}),
            tuple(item.event_id for item in events), event.global_sequence if last_sequence is None else last_sequence)

    def _event(self, event_id):
        try:
            return self._store.get_event(event_id)
        except KeyError as exc:
            raise ValueError('activation_source_missing') from exc

    def _validate(self, event: GameplayEvent, *, world_ref: str, profile_ref: str):
        invalid = 'activation_source_receipt'
        if (event.event_type not in _LIFECYCLE or event.stream_id != f'population:{world_ref}'
                or event.payload.get('world_ref') != world_ref or event.payload.get('profile_ref') != profile_ref
                or not profile_ref.startswith('character:') or not profile_ref.removeprefix('character:')
                or type(event.schema_version) is not int or event.schema_version != 1
                or event.visibility_policy != 'project'
                or type(event.stream_revision) is not int or event.stream_revision < 1
                or type(event.global_sequence) is not int or event.global_sequence < 1):
            raise ValueError(invalid)
        batch = self._store.get_transaction(event.transaction_id)
        if batch is None or len(batch.events) != 1:
            raise ValueError(invalid)
        record = batch.idempotency_record
        payload = dict(event.payload)
        identity = payload.get('identity_digest')
        if not isinstance(identity, str) or re.fullmatch(r'sha256:[0-9a-f]{64}', identity) is None:
            raise ValueError(invalid)
        if event.event_type == _COMMITTED:
            if record.principal_ref != self._producer:
                raise ValueError('activation_source_producer')
            fields = {'profile_ref', 'identity_digest', 'world_ref', 'package_revision', 'policy_revision',
                'scope_grant', 'cadence_class', 'activation_reason'}
            if set(payload) != fields or not isinstance(payload['scope_grant'], list):
                raise ValueError(invalid)
            # Reuse the real producer's typed input contract, never current data.
            ActivationProposal(proposal_id=event.command_id, profile_ref=profile_ref, world_ref=world_ref,
                package_revision=payload['package_revision'], policy_revision=payload['policy_revision'],
                activation_reason=payload['activation_reason'], scope_grant=payload['scope_grant'],
                cadence_class=payload['cadence_class'], expected_revisions={event.stream_id: event.stream_revision - 1},
                idempotency_key=record.idempotency_key, correlation_id=event.correlation_id, source_ref=self._producer)
            principal, pins = self._producer, {'package': 1, 'policy': 1}
            if event.causation_id != event.command_id:
                raise ValueError(invalid)
        else:
            if set(payload) != {'profile_ref', 'identity_digest', 'world_ref'}:
                raise ValueError(invalid)
            operation = {'population.activation.suspended': 'suspend', 'population.activation.requeued': 'requeue',
                'population.activation.locked': 'lock'}[event.event_type]
            command = f'{operation}:{world_ref}:{profile_ref}:{event.stream_revision - 1}'
            if (event.command_id != command or record.idempotency_key != command
                    or event.causation_id != command or event.correlation_id != f'correlation:{world_ref}'):
                raise ValueError(invalid)
            principal, pins = 'world_runtime.activation_authority', {}
        expected = build_atomic_event_batch(command_id=event.command_id, principal_ref=principal,
            stream_id=event.stream_id, expected_revision=event.stream_revision - 1,
            event_specs=[(event.event_type, payload)], idempotency_key=record.idempotency_key,
            causation_id=event.causation_id, correlation_id=event.correlation_id, pinned_revisions=pins)
        expected.events[0] = expected.events[0].model_copy(update={
            'stream_revision': event.stream_revision, 'global_sequence': event.global_sequence})
        receipt = self._store.get_by_idempotency(record.principal_ref, record.idempotency_key)
        if (_canonical(batch.model_dump(mode='json')) != _canonical(expected.model_dump(mode='json'))
                or _canonical(batch.events[0].model_dump(mode='json')) != _canonical(event.model_dump(mode='json'))
                or self._store.get_idempotency_record(record.principal_ref, record.idempotency_key) != record
                or receipt is None or receipt.committed is not True or receipt.failure is not None
                or receipt.idempotency_status != 'new_commit'
                or receipt.command_id != batch.command_id or receipt.transaction_id != batch.transaction_id
                or receipt.committed_event_ids != [event.event_id]
                or _canonical(receipt.resulting_stream_revisions) != _canonical({event.stream_id: event.stream_revision})
                or receipt.global_sequence_range != (event.global_sequence, event.global_sequence)
                or receipt.projection_refresh_hints):
            raise ValueError(invalid)
