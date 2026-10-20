"""Soul-owned bounded link, grant and protection fact lifecycle."""
from __future__ import annotations

from types import MappingProxyType
from typing import Literal, Mapping

from pydantic import ConfigDict, Field, model_validator

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import StrictGameplayModel
from app.gameplay.settlement_plan import build_multi_stream_atomic_event_batch
from app.gameplay.soul_runtime import SoulAnchorAuthority, SoulAnchorRequest


_PRINCIPAL = 'soul.fact_authority'
_PREFIX = 'gameplay:soul:fact:'


class SoulFactRegistration(StrictGameplayModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    world_ref: str = Field(min_length=1)
    package_ref: str = Field(min_length=1)
    version: str = Field(min_length=1)
    rule_ref: str = Field(min_length=1)
    kind: Literal['link', 'grant', 'protection']
    operations: tuple[Literal['possess', 'release_possession', 'bind', 'unbind', 'banish', 'recall',
        'sever', 'restore_link', 'curse', 'lift_curse', 'seal', 'unseal', 'block_reincarnation',
        'lift_reincarnation_block', 'alter_identity', 'restore_identity'], ...] = Field(min_length=1)
    lifetime: Literal['until_revoked']
    precedence: int = Field(ge=0, strict=True)

    @model_validator(mode='after')
    def validate_operations(self):
        if len(set(self.operations)) != len(self.operations):
            raise ValueError('soul_fact_registration_duplicate_operation')
        return self


class SoulFactRequest(StrictGameplayModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    world_ref: str = Field(min_length=1)
    actor_ref: str = Field(min_length=1)
    target_ref: str = Field(min_length=1)
    actor_incarnation: int = Field(ge=1, strict=True)
    target_incarnation: int = Field(ge=1, strict=True)
    package_ref: str = Field(min_length=1)
    version: str = Field(min_length=1)
    rule_ref: str = Field(min_length=1)
    operation: Literal['issue', 'revoke']
    original_fact_ref: str | None = None
    expected_revision: int = Field(ge=0, strict=True)
    idempotency_key: str = Field(min_length=1)

    @model_validator(mode='after')
    def validate_operation_reference(self):
        if self.operation == 'revoke' and not self.original_fact_ref:
            raise ValueError('soul_fact_original_required')
        if self.operation == 'issue' and self.original_fact_ref is not None:
            raise ValueError('soul_fact_original_unexpected')
        return self


class SoulFactReceipt(StrictGameplayModel):
    committed: bool
    committed_event_ids: tuple[str, ...] = ()
    zero_write: bool = False
    stop_reason: str | None = None


class SoulFactAuthority:
    """Immutable registration plus trusted composition-held anchor authority."""

    def __init__(self, *, anchors: SoulAnchorAuthority,
                 registrations: tuple[SoulFactRegistration, ...] = ()) -> None:
        if type(anchors) is not SoulAnchorAuthority:
            raise ValueError('soul_fact_anchor_authority')
        policies: dict[tuple[str, str, str, str], SoulFactRegistration] = {}
        for item in registrations:
            row = SoulFactRegistration.model_validate(item.model_dump(mode='python'))
            key = (row.world_ref, row.package_ref, row.version, row.rule_ref)
            if key in policies:
                raise ValueError('soul_fact_registration_duplicate')
            policies[key] = row
        self._anchors = anchors
        self.store: GameplayEventStore = anchors.store
        self._registrations: Mapping[tuple[str, str, str, str], SoulFactRegistration] = MappingProxyType(policies)

    @staticmethod
    def stream_id(world_ref: str, actor_ref: str) -> str:
        return f'{_PREFIX}{world_ref}:{actor_ref}'

    def settle(self, request: SoulFactRequest) -> SoulFactReceipt:
        request = SoulFactRequest.model_validate(
            request.model_dump(mode='python') if isinstance(request, SoulFactRequest) else request)
        stream = self.stream_id(request.world_ref, request.actor_ref)
        try:
            prior = self.store.get_by_idempotency(_PRINCIPAL, request.idempotency_key)
            if prior is not None:
                batch = self._original(request, prior, stream)
                return SoulFactReceipt(committed=True, zero_write=True,
                    committed_event_ids=tuple(prior.committed_event_ids))
            registration = self._registrations.get(
                (request.world_ref, request.package_ref, request.version, request.rule_ref))
            if registration is None:
                return self._reject('soul_fact_registration')
            head = self.store.get_stream_head(stream)
            if head != request.expected_revision:
                return self._reject('revision_conflict')
            projection = self.projection(request)
            active = projection.get('active', False)
            if request.operation == 'issue':
                if active or request.original_fact_ref is not None:
                    return self._reject('soul_fact_transition')
            elif (not active or projection.get('original_fact_ref') != request.original_fact_ref
                    or projection.get('rule_ref') != request.rule_ref
                    or projection.get('registration') != registration.model_dump(mode='json')):
                return self._reject('soul_fact_transition')

            anchors = [self._anchors.projection(world_ref=request.world_ref, actor_ref=request.actor_ref)]
            if not anchors[0] or anchors[0].get('incarnation') != request.actor_incarnation:
                return self._reject('soul_fact_actor_anchor')
            current_sources = [self._anchors._presence.read(actor_ref=request.actor_ref,
                world_ref=request.world_ref, expected_incarnation=request.actor_incarnation)]
            if request.target_ref == request.actor_ref:
                if request.target_incarnation != request.actor_incarnation:
                    return self._reject('soul_fact_target_anchor')
            else:
                target = self._anchors.projection(world_ref=request.world_ref, actor_ref=request.target_ref)
                if not target or target.get('incarnation') != request.target_incarnation:
                    return self._reject('soul_fact_target_anchor')
                anchors.append(target)
                current_sources.append(self._anchors._presence.read(actor_ref=request.target_ref,
                    world_ref=request.world_ref, expected_incarnation=request.target_incarnation))

            reads: dict[str, int] = {}
            for anchor, current_source in zip(anchors, current_sources, strict=True):
                anchor_stream = self._anchors.stream_id(request.world_ref, anchor['actor_ref'])
                reads[anchor_stream] = self.store.get_stream_head(anchor_stream)
                anchor_event = self.store.read_stream(anchor_stream, limit=1)[0]
                anchor_batch = self.store.get_transaction(anchor_event.transaction_id)
                if anchor_batch is None:
                    return self._reject('soul_fact_anchor_receipt')
                if any(self.store.get_stream_head(source) != revision
                       for source, revision in anchor_batch.read_stream_revisions.items()):
                    return self._reject('soul_fact_anchor_source_stale')
                for source, revision in anchor_batch.read_stream_revisions.items():
                    if source in reads and reads[source] != revision:
                        return self._reject('soul_fact_source_cut_conflict')
                    reads[source] = revision
                for source, revision in current_source.read_revisions.items():
                    if source in reads and reads[source] != revision:
                        return self._reject('soul_fact_source_cut_conflict')
                    reads[source] = revision
            reads[stream] = head
            if request.operation == 'issue':
                event_type = f'soul.fact.{registration.kind}.issued'
                payload = {'actor_ref': request.actor_ref, 'target_ref': request.target_ref,
                    'world_ref': request.world_ref, 'actor_incarnation': request.actor_incarnation,
                    'target_incarnation': request.target_incarnation, 'package_ref': request.package_ref,
                    'version': request.version, 'rule_ref': request.rule_ref, 'kind': registration.kind,
                    'precedence': registration.precedence, 'lifetime': registration.lifetime,
                    'active': True, 'original_fact_ref': None,
                    'registration': registration.model_dump(mode='json')}
            else:
                event_type = f'soul.fact.{registration.kind}.revoked'
                payload = {'actor_ref': request.actor_ref, 'target_ref': request.target_ref,
                    'world_ref': request.world_ref, 'actor_incarnation': request.actor_incarnation,
                    'target_incarnation': request.target_incarnation, 'package_ref': request.package_ref,
                    'version': request.version, 'rule_ref': request.rule_ref, 'kind': registration.kind,
                    'precedence': registration.precedence, 'lifetime': registration.lifetime,
                    'active': False, 'original_fact_ref': request.original_fact_ref,
                    'registration': registration.model_dump(mode='json')}
            batch = build_multi_stream_atomic_event_batch(
                command_id=f'soul:fact:{request.world_ref}:{request.actor_ref}:{request.idempotency_key}',
                principal_ref=_PRINCIPAL, expected_revisions={stream: head},
                event_specs={stream: [(event_type, payload)]},
                event_visibility_policies={stream: ['authority_only']},
                idempotency_key=request.idempotency_key, causation_id=f'action:{request.operation}',
                correlation_id=f'world:{request.world_ref}', read_stream_revisions=reads, pinned_revisions=reads)
            result = self.store.append_batch(batch)
            if not result.committed:
                return self._reject(result.failure.error_code if result.failure else 'append_rejected')
            return SoulFactReceipt(committed=True, committed_event_ids=tuple(result.committed_event_ids))
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            return self._reject(str(exc) or 'soul_fact_invalid')

    def projection(self, request: SoulFactRequest) -> dict[str, object]:
        stream = self.stream_id(request.world_ref, request.actor_ref)
        head = self.store.get_stream_head(stream)
        if not head:
            return {}
        events = self.store.read_stream(stream, to_revision=head)
        states: dict[tuple, dict[str, object]] = {}
        for event in events:
            transaction = self.store.get_transaction(event.transaction_id)
            record = (self.store.get_by_idempotency(_PRINCIPAL, transaction.idempotency_record.idempotency_key)
                if transaction is not None else None)
            if record is None:
                raise ValueError('soul_fact_history_invalid')
            self._original_from_event(event, record, stream)
            payload = dict(event.payload)
            key = tuple(payload[field] for field in ('world_ref', 'actor_ref', 'target_ref',
                'actor_incarnation', 'target_incarnation', 'package_ref', 'version', 'rule_ref'))
            state = states.get(key, {})
            if event.event_type.endswith('.issued'):
                if state.get('active'):
                    raise ValueError('soul_fact_history_transition_invalid')
                payload['original_fact_ref'] = event.event_id
            elif (not state.get('active') or state.get('original_fact_ref') != payload.get('original_fact_ref')
                    or state.get('registration') != payload.get('registration')):
                raise ValueError('soul_fact_history_transition_invalid')
            states[key] = payload
        key = tuple(getattr(request, field) for field in ('world_ref', 'actor_ref', 'target_ref',
            'actor_incarnation', 'target_incarnation', 'package_ref', 'version', 'rule_ref'))
        return states.get(key, {})

    def _original(self, request, receipt, stream):
        if (not receipt.committed or receipt.failure is not None or len(receipt.committed_event_ids) != 1
                or receipt.idempotency_status != 'new_commit' or receipt.projection_refresh_hints):
            raise ValueError('soul_fact_original_invalid')
        batch = self.store.get_transaction(receipt.transaction_id)
        if batch is None or len(batch.events) != 1:
            raise ValueError('soul_fact_original_invalid')
        event = batch.events[0]
        if (event.stream_id != stream or event.stream_revision != self.store.get_event(event.event_id).stream_revision
                or event.visibility_policy != 'authority_only' or event.schema_version != 1
                or event.event_type not in {'soul.fact.link.issued', 'soul.fact.link.revoked',
                    'soul.fact.grant.issued', 'soul.fact.grant.revoked',
                    'soul.fact.protection.issued', 'soul.fact.protection.revoked'}
                or event.event_id not in receipt.committed_event_ids):
            raise ValueError('soul_fact_original_invalid')
        if (event.payload.get('active') is not (request.operation == 'issue')
                or any(event.payload.get(key) != getattr(request, field)
               for key, field in {'world_ref': 'world_ref', 'actor_ref': 'actor_ref', 'target_ref': 'target_ref',
                   'actor_incarnation': 'actor_incarnation', 'target_incarnation': 'target_incarnation',
                   'package_ref': 'package_ref', 'version': 'version', 'rule_ref': 'rule_ref'}.items())
                or event.payload.get('original_fact_ref') != request.original_fact_ref):
            raise ValueError('soul_fact_original_invalid')
        if batch.idempotency_record.idempotency_key != request.idempotency_key:
            raise ValueError('soul_fact_original_invalid')
        expected_stream = {stream: event.stream_revision - 1}
        if (batch.expected_stream_revisions != expected_stream or receipt.resulting_stream_revisions != {stream: event.stream_revision}
                or receipt.global_sequence_range != (event.global_sequence, event.global_sequence)
                or self.store.get_idempotency_record(_PRINCIPAL, request.idempotency_key) != batch.idempotency_record):
            raise ValueError('soul_fact_original_invalid')
        self._original_from_event(event, receipt, stream)
        return batch

    def _original_from_event(self, event, receipt, stream):
        batch = self.store.get_transaction(event.transaction_id)
        if (batch is None or receipt is None or not receipt.committed or event not in batch.events
                or self.store.get_event(event.event_id) != event or event.stream_id != stream
                or event.visibility_policy != 'authority_only' or event.event_type not in {
                    'soul.fact.link.issued', 'soul.fact.link.revoked', 'soul.fact.grant.issued',
                    'soul.fact.grant.revoked', 'soul.fact.protection.issued', 'soul.fact.protection.revoked'}
                or len(batch.events) != 1 or batch.outbox_entries or batch.projection_refresh_hints
                or batch.idempotency_record.principal_ref != _PRINCIPAL
                or receipt.committed_event_ids != [event.event_id]
                or receipt.transaction_id != batch.transaction_id
                or receipt.global_sequence_range != (event.global_sequence, event.global_sequence)
                or receipt.resulting_stream_revisions != {stream: event.stream_revision}
                or receipt.idempotency_status != 'new_commit'
                or batch.read_stream_revisions != batch.pinned_revisions
                or event.stream_revision != batch.expected_stream_revisions.get(stream, -2) + 1):
            raise ValueError('soul_fact_history_invalid')
        payload = dict(event.payload)
        registration = SoulFactRegistration.model_validate(payload.get('registration'))
        if (registration.kind != payload.get('kind')
                or registration.world_ref != payload.get('world_ref')
                or registration.package_ref != payload.get('package_ref')
                or registration.version != payload.get('version')
                or registration.rule_ref != payload.get('rule_ref')
                or registration.precedence != payload.get('precedence')
                or registration.lifetime != payload.get('lifetime')
                or event.event_type != f"soul.fact.{registration.kind}.{'issued' if payload.get('active') else 'revoked'}"):
            raise ValueError('soul_fact_registration_snapshot_invalid')
        expected_reads = {stream: event.stream_revision - 1}
        for actor, incarnation in ((payload['actor_ref'], payload['actor_incarnation']),
                                   (payload['target_ref'], payload['target_incarnation'])):
            anchor_stream = self._anchors.stream_id(payload['world_ref'], actor)
            anchor_events = self.store.read_stream(anchor_stream, to_revision=1)
            if len(anchor_events) != 1:
                raise ValueError('soul_fact_anchor_cut_missing')
            anchor_event = anchor_events[0]
            anchor_batch = self.store.get_transaction(anchor_event.transaction_id)
            if anchor_batch is None or anchor_event.global_sequence >= event.global_sequence:
                raise ValueError('soul_fact_anchor_cut_missing')
            anchor_payload = anchor_event.payload
            original_anchor_request = SoulAnchorRequest(actor_ref=actor,
                world_ref=payload['world_ref'], package_ref=anchor_payload['package_ref'],
                version=anchor_payload['version'], incarnation=incarnation, expected_revision=0,
                idempotency_key=anchor_batch.idempotency_record.idempotency_key)
            anchor_receipt = self.store.get_by_idempotency(
                'soul.anchor_authority', original_anchor_request.idempotency_key)
            anchor_batch = self._anchors._original(original_anchor_request, anchor_receipt, anchor_stream)
            expected_reads[anchor_stream] = 1
            for source, revision in anchor_batch.read_stream_revisions.items():
                if source in expected_reads and expected_reads[source] != revision:
                    raise ValueError('soul_fact_anchor_cut_conflict')
                expected_reads[source] = revision
        if expected_reads != batch.read_stream_revisions:
            raise ValueError('soul_fact_anchor_cut_missing')
        request = SoulFactRequest(world_ref=payload['world_ref'], actor_ref=payload['actor_ref'],
            target_ref=payload['target_ref'], actor_incarnation=payload['actor_incarnation'],
            target_incarnation=payload['target_incarnation'], package_ref=payload['package_ref'],
            version=payload['version'], rule_ref=payload['rule_ref'],
            operation='issue' if event.event_type.endswith('.issued') else 'revoke',
            original_fact_ref=payload.get('original_fact_ref') if event.event_type.endswith('.revoked') else None,
            expected_revision=event.stream_revision - 1,
            idempotency_key=batch.idempotency_record.idempotency_key)
        expected = build_multi_stream_atomic_event_batch(
            command_id=event.command_id, principal_ref=_PRINCIPAL,
            expected_revisions={stream: event.stream_revision - 1},
            event_specs={stream: [(event.event_type, payload)]},
            event_visibility_policies={stream: ['authority_only']},
            idempotency_key=request.idempotency_key, causation_id=event.causation_id,
            correlation_id=event.correlation_id, read_stream_revisions=batch.read_stream_revisions,
            pinned_revisions=batch.pinned_revisions)
        expected.events[0] = expected.events[0].model_copy(update={
            'stream_revision': event.stream_revision, 'global_sequence': event.global_sequence})
        if expected.model_dump(mode='json') != batch.model_dump(mode='json'):
            raise ValueError('soul_fact_history_invalid')

    @staticmethod
    def _reject(reason):
        return SoulFactReceipt(committed=False, stop_reason=reason)
