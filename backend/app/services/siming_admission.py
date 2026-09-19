"""Siming 入站账本；事实与幂等性均复用 Heavenly Graph，不执行业务副作用。"""
from app.models.siming_heavenly_graph import GraphValidity, GraphProvenance, HeavenlyGraphScope
from app.models.authority_event import AuthorityEvent
from app.services.siming_heavenly_memory import SimingHeavenlyMemoryService
from app.models.siming_heavenly_memory import (
    SIMING_ADMISSION_TERMINAL, SimingAdmissionKey, SimingAdmissionMemoryEntry,
    SimingAdmissionReceipt, SimingAdmissionPage, SimingAdmissionCursor, SimingAdmissionTransition, SimingAdmissionEffectReceipt,
)
from app.services.siming_continuation import digest, SimingTurnFrame, SimingProviderRequest, SimingProviderCompletion, CANDIDATE_TIMELINE_REQUEUE, candidate_timeline_changed
from app.services.siming_heavenly_graph_port import HeavenlyGraphIdempotencyConflict, HeavenlyGraphRevisionConflict


class SimingAdmissionService:
    def __init__(self, memory: SimingHeavenlyMemoryService) -> None:
        self._memory = memory

    def read_room_head(self, scope):
        return self._memory._graph.read_siming_room_head(scope)

    def read_room_pending(self, scope):
        node = self._memory._graph.read_siming_room_pending(scope)
        return None if node is None else SimingAdmissionReceipt(entry=SimingAdmissionMemoryEntry.model_validate(node.attributes))

    def read(self, key: SimingAdmissionKey, *, revision: int | None = None) -> SimingAdmissionReceipt | None:
        entry = self._memory.read_admission(key=key, revision=revision)
        return None if entry is None else SimingAdmissionReceipt(entry=entry)

    def admit(self, *, scope: HeavenlyGraphScope, source: AuthorityEvent, now: float,
              expires_at: float, policy_version: str, source_outbox_ref: str | None = None,
              source_transaction_ref: str | None = None) -> SimingAdmissionReceipt:
        key = SimingAdmissionKey(scope=scope, source_event_id=source.event_id)
        source_json = source.model_dump(mode='json')
        source_digest = digest(source_json)
        existing = self.read(key)
        if existing:
            if existing.entry.source_digest != source_digest:
                raise ValueError('siming_admission_source_conflict')
            return existing.model_copy(update={'replayed': True})
        if expires_at <= now:
            raise ValueError('siming_admission_expired')
        from app.models.siming_heavenly_graph import SimingOperationalRoomHead
        prior_head = self.read_room_head(scope)
        if prior_head is None and self.read_room_pending(scope) is not None:
            raise ValueError("siming_room_order_unavailable")
        head = SimingOperationalRoomHead(scope=scope.model_copy(update={'scene_id': None}),
            revision=1 if prior_head is None else prior_head.revision + 1,
            last_sequence=1 if prior_head is None else prior_head.last_sequence + 1,
            completed_sequence=0 if prior_head is None else prior_head.completed_sequence,
            after_state={} if prior_head is None else prior_head.after_state)
        entry = SimingAdmissionMemoryEntry(key=key, room_sequence=head.last_sequence, revision=1, source=source_json,
            source_digest=source_digest, admitted_at=now, expires_at=expires_at,
            due_at=now, policy_version=policy_version, source_outbox_ref=source_outbox_ref,
            source_transaction_ref=source_transaction_ref)
        try:
            self._write(entry, now, room_head=head)
        except (HeavenlyGraphIdempotencyConflict, HeavenlyGraphRevisionConflict):
            # 另一 owner/进程已提交同 K；只允许重放相同 canonical source。
            existing = self.read(key)
            if existing is None or existing.entry.source_digest != source_digest:
                raise ValueError('siming_admission_source_conflict') from None
            return existing.model_copy(update={'replayed': True})
        return SimingAdmissionReceipt(entry=entry)

    def advance(self, key: SimingAdmissionKey, *, expected_revision: int,
                transition: SimingAdmissionTransition, now: float) -> SimingAdmissionReceipt:
        current = self.read(key)
        if current is None:
            raise ValueError('siming_admission_missing')
        transition_digest = digest(transition.model_dump(mode='json', exclude={'room_head'} if transition.room_head is None else set()))
        if current.entry.revision != expected_revision:
            prior = self.read(key, revision=expected_revision + 1)
            if prior and prior.entry.transition_digest == transition_digest:
                return prior.model_copy(update={'replayed': True})
            raise ValueError('siming_admission_revision_conflict')
        entry = current.entry
        if entry.state in SIMING_ADMISSION_TERMINAL:
            raise ValueError('siming_admission_terminal')
        if now >= entry.expires_at and transition.state not in {'stale', 'cancelled', 'failed'}:
            raise ValueError('siming_admission_expired')
        self._validate_transition(entry, transition, now)
        return self._commit_transition(entry, transition, now, transition_digest)

    def _commit_transition(self, entry, transition, now, transition_digest):
        key, expected_revision = entry.key, entry.revision
        updated = SimingAdmissionMemoryEntry.model_validate({**entry.model_dump(mode='json'),
            'revision': expected_revision + 1, 'state': transition.state,
            'due_at': entry.due_at if transition.due_at is None else transition.due_at,
            'transition': transition.model_dump(mode='json'), 'transition_digest': transition_digest,
            'provider_revision': expected_revision + 1 if transition.state == 'provider_pending' else entry.provider_revision,
            'result_revision': (None if transition.state == 'provider_pending' else
                                expected_revision + 1 if transition.state == 'result_ready' else entry.result_revision),
            'commit_revision': (None if transition.state == 'provider_pending' else
                                expected_revision + 1 if transition.state == 'commit_started' and entry.state != 'commit_started'
                                else entry.commit_revision)})
        try:
            self._write(updated, now, room_head=transition.room_head)
        except (HeavenlyGraphIdempotencyConflict, HeavenlyGraphRevisionConflict):
            prior = self.read(key, revision=expected_revision + 1)
            if prior is None or prior.entry.transition_digest != transition_digest:
                raise ValueError('siming_admission_revision_conflict') from None
            return prior.model_copy(update={'replayed': True})
        return SimingAdmissionReceipt(entry=updated)

    def reconcile_effect_receipts(self, key, *, expected_revision, now, reason, room_head, read_existing):
        """只读原 effect 拥有者证据后记账；不通过普通 advance 放宽过期执行权限。"""
        current = self.read(key)
        if current is None or current.entry.revision != expected_revision:
            raise ValueError('siming_admission_revision_conflict')
        entry = current.entry
        if entry.state != 'commit_started':
            raise ValueError('siming_admission_plan_required')
        receipts = {item.effect_key: item for item in entry.transition.receipts}
        for effect in entry.transition.effects:
            if effect.effect_key in receipts:
                continue
            proof = read_existing(effect)
            if proof is not None:
                receipts[effect.effect_key] = SimingAdmissionEffectReceipt(effect_key=effect.effect_key, receipt=proof)
        missing = [effect.effect_key for effect in entry.transition.effects if effect.effect_key not in receipts]
        finished = (not missing and any(effect.kind == 'audit_bundle' for effect in entry.transition.effects)
            and any(effect.kind == 'runtime_state' and effect.payload['after']['stage'] == 'completed'
                    for effect in entry.transition.effects))
        transition = SimingAdmissionTransition(state='completed' if finished else 'stale',
            reason=reason + ';receipt_only;missing_effects=' + ','.join(missing),
            receipts=list(receipts.values()), room_head=room_head)
        self._validate_transition(entry, transition, now)
        transition_digest = digest(transition.model_dump(mode='json'))
        return self._commit_transition(entry, transition, now, transition_digest)

    def expire(self, key: SimingAdmissionKey, *, now: float) -> SimingAdmissionReceipt:
        receipt = self.read(key)
        if receipt is None:
            raise ValueError('siming_admission_missing')
        if receipt.entry.state in SIMING_ADMISSION_TERMINAL:
            return receipt.model_copy(update={'replayed': True})
        if now < receipt.entry.expires_at:
            raise ValueError('siming_admission_not_expired')
        return self.advance(key, expected_revision=receipt.entry.revision, now=now,
            transition=SimingAdmissionTransition(state='stale', reason='wall_ttl_expired'))

    @staticmethod
    def _validate_transition(entry: SimingAdmissionMemoryEntry, transition: SimingAdmissionTransition, now: float) -> None:
        allowed = {
            'admitted': {'due', 'provider_pending', 'commit_started'},
            'due': {'provider_pending', 'commit_started'},
            'requeued': {'due', 'provider_pending', 'commit_started'},
            'provider_pending': {'result_ready', 'provider_pending'},
            'result_ready': {'commit_started'},
            'commit_started': {'completed', 'provider_pending', 'commit_started'},
        }
        if transition.state not in allowed.get(entry.state, set()) | {'stale', 'cancelled', 'failed', 'requeued'}:
            raise ValueError('siming_admission_invalid_transition')
        previous = entry.transition
        if entry.state == 'commit_started' and transition.state in {'requeued', 'provider_pending'}:
            if {receipt.effect_key for receipt in previous.receipts} != {effect.effect_key for effect in previous.effects}:
                raise ValueError('siming_admission_outstanding_effect')
        requeue = transition.state == 'requeued' and transition.reason == CANDIDATE_TIMELINE_REQUEUE
        retry = entry.state == 'requeued' and previous.reason == CANDIDATE_TIMELINE_REQUEUE
        if requeue:
            if entry.state != 'provider_pending' or previous.stage != 'candidate' or transition.provider is None:
                raise ValueError('siming_admission_requeue_origin')
            old = SimingTurnFrame.model_validate_json(previous.provider.frame_json)
            refreshed = SimingTurnFrame.model_validate_json(transition.provider.frame_json)
            if (transition.stage != previous.stage or transition.ordinal != previous.ordinal
                    or transition.room_head is not None or transition.due_at != now
                    or now >= min(entry.expires_at, old.expires_at)
                    or transition.provider.request_json != previous.provider.request_json
                    or transition.provider.provider_identity != previous.provider.provider_identity
                    or transition.provider.pin_digest != digest(refreshed.pin)
                    or refreshed.model_dump(exclude={'pin'}) != old.model_dump(exclude={'pin'})
                    or not candidate_timeline_changed(old.pin, refreshed.pin)):
                raise ValueError('siming_admission_requeue_changed_prefix')
        if retry and transition.state not in {'provider_pending', 'stale', 'cancelled', 'failed'}:
            raise ValueError('siming_admission_requeue_successor')
        if transition.state == 'provider_pending':
            provider = transition.provider
            if provider is None:
                raise ValueError('siming_admission_provider_required')
            frame = SimingTurnFrame.model_validate_json(provider.frame_json)
            request = SimingProviderRequest.model_validate_json(provider.request_json)
            if frame.synchronous or frame.job is None or frame.request is None:
                raise ValueError('siming_admission_frame_not_pending')
            if (frame.stage != transition.stage or request.stage != transition.stage
                    or frame.request != request or frame.job.request_json != provider.request_json.encode()
                    or frame.job.stage != transition.stage):
                raise ValueError('siming_admission_request_mismatch')
            if (digest(frame.pin) != provider.pin_digest or frame.job.pin_digest != provider.pin_digest):
                raise ValueError('siming_admission_pin_mismatch')
            if (digest(frame.siming_input.source_event.model_dump(mode='json')) != entry.source_digest
                    or request.event.model_dump(mode='json') != entry.source
                    or frame.job.source_event_id != entry.key.source_event_id):
                raise ValueError('siming_admission_source_conflict')
            if frame.expires_at <= now:
                raise ValueError('siming_admission_frame_expired')
            if entry.state == 'provider_pending':
                old = SimingTurnFrame.model_validate_json(previous.provider.frame_json)
                if (transition.stage != previous.stage or transition.ordinal != previous.ordinal
                        or provider.provider_identity != previous.provider.provider_identity
                        or provider.request_json != previous.provider.request_json
                        or provider.pin_digest != previous.provider.pin_digest
                        or frame.model_dump(mode='json', exclude={'turn_id', 'job'}) != old.model_dump(mode='json', exclude={'turn_id', 'job'})
                        or frame.job.attempt != old.job.attempt + 1
                        or frame.job.token == old.job.token):
                    raise ValueError('siming_admission_retry_changed_request')
            if retry:
                old = SimingTurnFrame.model_validate_json(previous.provider.frame_json)
                if (transition.stage != 'candidate' or transition.ordinal != previous.ordinal + 1
                        or provider.request_json != previous.provider.request_json
                        or provider.provider_identity != previous.provider.provider_identity
                        or frame.model_dump(exclude={'turn_id', 'job', 'pin', 'expires_at'}) != old.model_dump(exclude={'turn_id', 'job', 'pin', 'expires_at'})
                        or frame.expires_at > min(old.expires_at, entry.expires_at)
                        or frame.job.attempt != old.job.attempt + 1 or frame.job.token == old.job.token
                        or (frame.pin != old.pin and not candidate_timeline_changed(old.pin, frame.pin))):
                    raise ValueError('siming_admission_requeue_changed_request')
        elif transition.provider is not None and not requeue:
            raise ValueError('siming_admission_unexpected_provider')
        if transition.state == 'result_ready' or (requeue and transition.completion_json is not None):
            import hashlib
            if transition.completion_json is None or previous is None or previous.provider is None:
                raise ValueError('siming_admission_completion_required')
            completion = SimingProviderCompletion.model_validate_json(transition.completion_json)
            if completion.request_digest != hashlib.sha256(previous.provider.request_json.encode()).hexdigest():
                raise ValueError('siming_admission_request_digest_mismatch')
            if transition.stage != previous.stage or transition.ordinal != previous.ordinal:
                raise ValueError('siming_admission_completion_stage_mismatch')
        elif transition.completion_json is not None:
            raise ValueError('siming_admission_unexpected_completion')
        if transition.state == 'commit_started':
            if entry.state in {'result_ready', 'commit_started'} and (transition.stage, transition.ordinal) != (previous.stage, previous.ordinal):
                raise ValueError('siming_admission_effect_stage_mismatch')
            expected_keys = [entry.key.effect_key(transition.stage, transition.ordinal, index) for index, effect in enumerate(transition.effects)]
            if [effect.effect_key for effect in transition.effects] != expected_keys:
                raise ValueError('siming_admission_effect_key_mismatch')
            if entry.state == 'commit_started' and transition.effects != previous.effects:
                raise ValueError('siming_admission_effect_plan_conflict')
        elif transition.effects:
            raise ValueError('siming_admission_unexpected_effects')
        if transition.receipts or transition.state == 'completed' or (entry.state == 'commit_started' and transition.state == 'commit_started'):
            if entry.state != 'commit_started' or previous is None:
                raise ValueError('siming_admission_receipt_without_plan')
            keys = {effect.effect_key for effect in previous.effects}
            receipt_keys = [receipt.effect_key for receipt in transition.receipts]
            if len(receipt_keys) != len(set(receipt_keys)) or not set(receipt_keys) <= keys:
                raise ValueError('siming_admission_receipt_key_mismatch')
            prior_receipts = {receipt.effect_key: receipt for receipt in previous.receipts}
            current_receipts = {receipt.effect_key: receipt for receipt in transition.receipts}
            if any(current_receipts.get(key) != value for key, value in prior_receipts.items()):
                raise ValueError('siming_admission_receipt_conflict')
            if transition.state == 'completed' and set(receipt_keys) != keys:
                raise ValueError('siming_admission_missing_effect_receipt')

    def list_pending(self, *, scope: HeavenlyGraphScope, limit: int = 32,
                     cursor: SimingAdmissionCursor | None = None) -> SimingAdmissionPage:
        if not 1 <= limit <= 256:
            raise ValueError('siming_admission_page_limit')
        if cursor is not None and cursor.scope != scope:
            raise ValueError('siming_admission_cursor_scope')
        entries = self._memory.list_pending_admissions(scope=scope, limit=limit + 1, cursor=cursor)
        more = len(entries) > limit
        entries = entries[:limit]
        last = entries[-1] if entries else None
        return SimingAdmissionPage(entries=entries, next_cursor=(
            SimingAdmissionCursor(scope=scope, due_at=last.due_at, entry_id=last.entry_id) if more else None))

    def list_pending_all(self, *, limit: int = 32,
                         cursor: SimingAdmissionCursor | None = None) -> SimingAdmissionPage:
        if not 1 <= limit <= 256:
            raise ValueError('siming_admission_page_limit')
        entries = self._memory.list_pending_admissions(scope=None, limit=limit + 1, cursor=cursor)
        more = len(entries) > limit
        entries = entries[:limit]
        last = entries[-1] if entries else None
        return SimingAdmissionPage(entries=entries, next_cursor=(
            SimingAdmissionCursor(scope=last.key.scope, due_at=last.due_at, entry_id=last.entry_id) if more else None))

    def _write(self, entry: SimingAdmissionMemoryEntry, now: float, *, room_head=None) -> None:
        self._memory.write_entry(scope=entry.key.scope, entry=entry,
            validity=GraphValidity(valid_from=0), recorded_at=int(now), revision=entry.revision,
            supersedes_revision=entry.revision - 1 if entry.revision > 1 else None,
            provenance=GraphProvenance(source_kind='runtime_outcome', source_ref=entry.key.source_event_id,
                causation_id=entry.source['causation_id'], correlation_id=entry.source['correlation_id'],
                producer_system='siming_admission'),
            transaction_id=f'{entry.entry_id}:revision:{entry.revision}',
            idempotency_key=f'{entry.entry_id}:revision:{entry.revision}', siming_room_head=room_head)
