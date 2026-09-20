"""Character owner 上的持久子入站；入站不触发感知、模型或占用 provider 槽。"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from app.models.siming_character_bridge import SimingCharacterCompatibilityInput


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


class CharacterCognitionAdmission(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    schema_version: Literal[1] = 1
    child_key: str
    actor_id: str
    delivery_id: str
    source_kind: Literal['ingest_siming_output', 'run_background_cognition_tick']
    source_event: dict[str, JsonValue]
    payload: dict[str, JsonValue]
    source_pins: dict[str, JsonValue]
    parent_effect_key: str
    admitted_at: float
    expires_at: float
    state: Literal['admitted'] = 'admitted'
    input_digest: str
    producer_ts: int | None = None


class CharacterCognitionProgress(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    schema_version: Literal[1] = 1
    child_key: str
    actor_id: str
    input_digest: str
    revision: int = Field(ge=1)
    stage: Literal['entry', 'l2', 'l3', 'suggestion', 'execution']
    status: Literal['commit_started', 'stage_ready', 'provider_pending', 'result_ready', 'completed', 'stale']
    frame: dict[str, JsonValue]
    plan: dict[str, JsonValue] | None = None
    completion: dict[str, JsonValue] | None = None
    request_json: str | None = None
    reason: str = ''
    progress_digest: str


class CharacterCognitionAdmissionService:
    def __init__(self, *, store, assert_owner, validate_source, activation_is_current, delivery_pin_reader=None):
        self.store = store
        self._owner = assert_owner
        self._validate_source = validate_source
        self._activation_is_current = activation_is_current
        self._delivery_pin_reader = delivery_pin_reader
        self._owner()
        self.store.initialize_cognition_admissions()

    def admit(self, *, source_event, actor_id, delivery_id, source_kind, payload, source_pins,
              now, expires_at, producer_ts: int, parent_effect_key='', activation=None):
        self._owner()
        if type(producer_ts) is not int:
            raise ValueError('cognition_admission_business_tick_required')
        source = source_event.model_dump(mode='json')
        key = self.key_for(source_event_id=source['event_id'], actor_id=actor_id, delivery_id=delivery_id)
        inputs = dict(actor_id=actor_id, delivery_id=delivery_id, source_kind=source_kind,
            source_event=source, payload=payload, source_pins=source_pins,
            parent_effect_key=parent_effect_key, expires_at=expires_at, producer_ts=producer_ts)
        entry = CharacterCognitionAdmission(child_key=key, admitted_at=now, input_digest='', **inputs)
        fingerprint = _digest(self._inputs(entry))
        entry = entry.model_copy(update={'input_digest': fingerprint})
        previous = self.read(key)
        if previous is not None:
            if previous.input_digest != fingerprint:
                raise ValueError('cognition_admission_conflict')
            return previous
        if not actor_id or not delivery_id or not source_pins:
            raise ValueError('cognition_admission_source_required')
        if not math.isfinite(now) or not math.isfinite(expires_at) or now >= expires_at:
            raise ValueError('cognition_admission_expired')
        if source_kind == 'run_background_cognition_tick' and payload:
            raise ValueError('background_wake_must_not_inject_perception')
        if source_kind == 'ingest_siming_output':
            delivery = SimingCharacterCompatibilityInput.model_validate(payload)
            if (delivery.actor_id, delivery.delivery_id, delivery.producer_ts) != (actor_id, delivery_id, producer_ts):
                raise ValueError('cognition_admission_delivery_mismatch')
        if activation is not None and (activation.actor_id != actor_id
                or not self._activation_is_current(activation.lock_ref, activation.token)):
            raise ValueError('cognition_admission_activation_invalid')
        self._validate_source(entry)
        # JSON 往返隔离调用方的可变输入；receipt 和索引由原 session transaction 原子保存。
        self.store.save_cognition_admission(entry.model_dump(mode='json'))
        return self.read(key)

    def read_progress(self, key, *, revision=None):
        self._owner()
        raw = self.store.read_cognition_progress(key, revision=revision)
        if raw is None:
            return None
        progress = CharacterCognitionProgress.model_validate(raw)
        entry = self.read(key)
        if (entry is None or progress.actor_id != entry.actor_id or progress.input_digest != entry.input_digest
                or progress.progress_digest != _digest(progress.model_dump(mode='json', exclude={'progress_digest'}))):
            raise ValueError('cognition_progress_digest_mismatch')
        self._validate_progress_frames(progress, entry)
        return progress

    def _validate_progress_frames(self, progress, entry):
        from .cognition_frame import validate_frame
        checked = set()
        frames = [progress.frame]
        if progress.plan:
            frames.extend(progress.plan[name] for name in ('before', 'after') if name in progress.plan)
        for frame in frames:
            validate_frame(self.store, frame, actor_id=entry.actor_id, child_key=entry.child_key, checked=checked)

    def advance_progress(self, *, key, expected_revision, stage, status, frame, now,
                         plan=None, completion=None, request_json=None, reason=''):
        """仅持久化 Character 的显式阶段；调用 owner 仍须在模型/效应边界验原 pin。"""
        self._owner()
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError('cognition_progress_revision_conflict')
        entry = self.read(key)
        if entry is None:
            raise ValueError('cognition_admission_missing')
        previous = self.read_progress(key, revision=expected_revision) if expected_revision else None
        if previous is not None and previous.stage == stage:
            if request_json is None:
                request_json = previous.request_json
            if request_json != previous.request_json:
                raise ValueError('cognition_progress_request_conflict')
            if previous.completion is not None and completion is not None and completion != previous.completion:
                raise ValueError('cognition_progress_completion_conflict')
            if completion is None:
                completion = previous.completion
            if plan is None and status in {'stage_ready', 'completed', 'stale'}:
                plan = previous.plan
        progress = CharacterCognitionProgress(child_key=key, actor_id=entry.actor_id, input_digest=entry.input_digest,
            revision=expected_revision + 1, stage=stage, status=status, frame=frame, plan=plan,
            completion=completion, request_json=request_json, reason=reason, progress_digest='')
        progress = progress.model_copy(update={'progress_digest': _digest(progress.model_dump(mode='json', exclude={'progress_digest'}))})
        existing = self.read_progress(key, revision=progress.revision)
        if existing is not None:
            if existing != progress:
                raise ValueError('cognition_progress_conflict')
            return existing
        if entry.producer_ts is None and status != 'stale':
            raise ValueError('cognition_admission_business_tick_required')
        current = self.read_progress(key)
        if (current.revision if current is not None else 0) != expected_revision:
            raise ValueError('cognition_progress_revision_conflict')
        if status == 'provider_pending' and (request_json is None or not isinstance(json.loads(request_json), dict)):
            raise ValueError('cognition_progress_request_required')
        allowed = False
        if current is None:
            allowed = stage == 'entry' and (status == 'commit_started' or (status == 'stale' and bool(reason)))
        elif current.status not in {'completed', 'stale'}:
            if status == 'stale':
                allowed = (stage == current.stage and bool(reason) and frame == current.frame
                    and plan == current.plan)
            elif stage == current.stage:
                allowed = (current.status, status) in {
                    ('provider_pending', 'result_ready'), ('result_ready', 'commit_started'),
                    ('commit_started', 'stage_ready')}
                if current.status in {'provider_pending', 'result_ready'}:
                    allowed = allowed and frame == current.frame
                if current.status == 'commit_started' and status == 'completed':
                    allowed = stage in {'entry', 'l3', 'suggestion', 'execution'}
                if current.status == 'commit_started' and status in {'stage_ready', 'completed'}:
                    allowed = allowed and plan == current.plan and frame == current.plan.get('after')
            elif current.stage == 'l3' and current.status == 'stage_ready' and stage == 'execution' and status == 'commit_started':
                allowed = True
            elif current.stage == 'l3' and current.status == 'stage_ready' and stage == 'suggestion' and status == 'commit_started':
                allowed = current.frame.get('decision', {}).get('planning_status') == 'continuity_floor'
            elif current.status == 'stage_ready' and status == 'provider_pending':
                allowed = (current.stage, stage) in {('entry', 'l2'), ('l2', 'l3'), ('l3', 'suggestion')}
        if (not allowed or frame.get('actor_id') != entry.actor_id or frame.get('stage') != stage
                or (status == 'commit_started' and plan is None)
                or (status == 'result_ready' and completion is None)):
            raise ValueError('cognition_progress_transition_invalid')
        if not math.isfinite(now) or (now >= entry.expires_at and status != 'stale'):
            raise ValueError('cognition_admission_expired')
        self._validate_progress_frames(progress, entry)
        self.store.save_cognition_progress(progress.model_dump(mode='json'), expected_revision=expected_revision)
        return self.read_progress(key)

    def read_delivery(self, *, dispatch_event, delivery_input, effect_key, expires_at):
        self._owner()
        delivery = SimingCharacterCompatibilityInput.model_validate(delivery_input)
        key = self.key_for(source_event_id=dispatch_event.event_id, actor_id=delivery.actor_id, delivery_id=delivery.delivery_id)
        prior = self.read(key)
        if prior is not None:
            # 父回执丢失后读取原子入站；不因后续 actor 进展重签原 pins。
            expected = dict(source_event=dispatch_event.model_dump(mode='json'), payload=delivery.model_dump(mode='json'),
                source_kind='ingest_siming_output', parent_effect_key=effect_key, expires_at=expires_at)
            if any(getattr(prior, field) != value for field, value in expected.items()):
                raise ValueError('cognition_admission_conflict')
        return prior

    def admit_delivery(self, *, dispatch_event, delivery_input, effect_key, expires_at, now):
        self._owner()
        prior = self.read_delivery(dispatch_event=dispatch_event, delivery_input=delivery_input,
            effect_key=effect_key, expires_at=expires_at)
        if prior is not None:
            return prior
        if self._delivery_pin_reader is None:
            raise ValueError('cognition_delivery_pin_reader_required')
        delivery = SimingCharacterCompatibilityInput.model_validate(delivery_input)
        return self.admit(source_event=dispatch_event, actor_id=delivery.actor_id, delivery_id=delivery.delivery_id,
            source_kind='ingest_siming_output', payload=delivery.model_dump(mode='json'),
            source_pins=self._delivery_pin_reader(dispatch_event.model_copy(deep=True), delivery.model_copy(deep=True)),
            now=now, expires_at=expires_at, producer_ts=delivery.producer_ts, parent_effect_key=effect_key)

    @staticmethod
    def key_for(*, source_event_id: str, actor_id: str, delivery_id: str) -> str:
        values = [source_event_id, actor_id, delivery_id]
        if any(type(value) is not str or not value for value in values):
            raise ValueError('cognition_admission_identity_required')
        return 'character-cognition:' + _digest(values)

    @staticmethod
    def _inputs(entry):
        values = entry.model_dump(mode='json', exclude={'schema_version', 'child_key', 'admitted_at', 'state', 'input_digest'})
        if entry.producer_ts is None:
            # 初始 admission 版本未记录业务 tick；允许精确读取，不能从 wall clock 补造。
            values.pop('producer_ts')
        return values

    @classmethod
    def _validated(cls, raw):
        entry = CharacterCognitionAdmission.model_validate(raw)
        expected_key = cls.key_for(source_event_id=entry.source_event.get('event_id'), actor_id=entry.actor_id, delivery_id=entry.delivery_id)
        if (entry.child_key != expected_key or entry.input_digest != _digest(cls._inputs(entry))
                or not math.isfinite(entry.admitted_at) or not math.isfinite(entry.expires_at)
                or entry.admitted_at >= entry.expires_at):
            raise ValueError('cognition_admission_digest_mismatch')
        return entry

    def read(self, key):
        self._owner()
        raw = self.store.read_cognition_admission(key)
        return None if raw is None else self._validated(raw)

    def list_pending(self, *, limit=32, cursor=None):
        self._owner()
        return tuple(self._validated(raw)
            for raw in self.store.list_cognition_admissions(limit=limit, cursor=cursor))
