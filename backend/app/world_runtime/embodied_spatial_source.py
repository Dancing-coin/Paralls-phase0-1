"""Admit bounded controller observations onto the existing world event spine."""
from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass
from threading import RLock
from typing import Callable
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.gameplay.event_schema_registry import EventSchemaRegistration
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult
from app.gameplay.settlement_plan import build_multi_stream_atomic_event_batch
from app.services.embodied_controller_auth_service import EmbodiedControllerAuthService


SPATIAL_SAMPLE_SCHEMA = EventSchemaRegistration(
    "world.embodied.spatial_sample_admitted", 1, "sha256:embodied-spatial-sample-v1",
)
_PRINCIPAL = "authority:embodied_spatial_source"


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        allow_nan=False).encode()).hexdigest()


def _position(value: object) -> tuple[float, float, float]:
    if (not isinstance(value, (list, tuple)) or len(value) != 3
            or any(type(x) not in (int, float) or not math.isfinite(x) for x in value)):
        raise ValueError("spatial_position_invalid")
    return tuple(float(x) for x in value)


class _ScopeIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    actor_id: str = Field(min_length=1)
    room_id: str = Field(min_length=1)
    scene_id: str = Field(min_length=1)
    scene_instance_id: str = Field(min_length=1)
    zone_id: str = Field(min_length=1)
    scene_revision: int = Field(ge=1)


class EmbodiedSpatialScope(_ScopeIdentity):
    """Internal deployment definition; never admitted from controller payloads."""

    source_ref: str = Field(min_length=1)
    spawn_position: tuple[float, float, float]
    bounds_min: tuple[float, float, float]
    bounds_max: tuple[float, float, float]
    max_speed_mps: float = Field(gt=0, allow_inf_nan=False)
    physics_ticks_per_second: int = Field(ge=1, le=1000)
    max_age_ms: int = Field(ge=1, le=60000)

    @field_validator("spawn_position", "bounds_min", "bounds_max", mode="before")
    @classmethod
    def position_valid(cls, value):
        return _position(value)

    @model_validator(mode="after")
    def bounds_valid(self):
        if any(low >= high or not low <= x <= high
               for low, x, high in zip(self.bounds_min, self.spawn_position, self.bounds_max)):
            raise ValueError("spatial_scope_bounds_invalid")
        return self


class EmbodiedSpatialSample(_ScopeIdentity):
    connection_epoch: int = Field(ge=1)
    physics_tick: int = Field(ge=1)
    position: tuple[float, float, float]

    @field_validator("position", mode="before")
    @classmethod
    def position_valid(cls, value):
        return _position(value)


@dataclass(frozen=True)
class SpatialSourceEvidence:
    position: tuple[float, float, float]
    event_ref: str
    read_stream_revisions: dict[str, int]


class EmbodiedSpatialSource:
    def __init__(self, *, store: GameplayEventStore, auth: EmbodiedControllerAuthService,
                 scopes: list[EmbodiedSpatialScope], clock_ms: Callable[[], int] | None = None):
        self._store, self._auth = store, auth
        self._scopes = {scope.actor_id: scope for scope in scopes}
        if len(self._scopes) != len(scopes):
            raise ValueError("spatial_scope_actor_duplicate")
        self._clock_ms = clock_ms or (lambda: time.monotonic_ns() // 1_000_000)
        self._process_epoch = uuid4().hex
        self._lock = RLock()

    @staticmethod
    def stream_id(actor_id: str) -> str:
        return "world:embodied-spatial:" + _digest(actor_id)

    def _scope(self, identity: _ScopeIdentity) -> EmbodiedSpatialScope:
        scope = self._scopes.get(identity.actor_id)
        if scope is None or any(getattr(scope, name) != getattr(identity, name)
                                for name in _ScopeIdentity.model_fields):
            raise ValueError("spatial_scope_mismatch")
        return scope

    def _now(self) -> int:
        value = self._clock_ms()
        if type(value) is not int or value < 0:
            raise ValueError("spatial_clock_invalid")
        return value

    def _validate_event(self, event, actor_id: str) -> None:
        try:
            payload = event.payload
            sample = EmbodiedSpatialSample.model_validate(payload["sample"])
            scope = EmbodiedSpatialScope.model_validate(payload["scope"])
            if (event.event_type != SPATIAL_SAMPLE_SCHEMA.event_type or event.schema_version != 1
                    or event.visibility_policy != "authority_only" or sample.actor_id != actor_id
                    or event.stream_id != self.stream_id(actor_id)
                    or event.correlation_id != scope.source_ref
                    or payload["sample_key"] != "spatial:" + _digest([payload["process_epoch"], payload["binding_id"], sample.physics_tick])
                    or event.command_id != payload["sample_key"]
                    or any(getattr(scope, name) != getattr(sample, name) for name in _ScopeIdentity.model_fields)
                    or payload["sample_digest"] != _digest(payload["sample"])
                    or payload["scope_digest"] != _digest(payload["scope"])
                    or type(payload["received_at_ms"]) is not int or payload["received_at_ms"] < 0
                    or not all(isinstance(payload.get(k), str) and payload[k]
                               for k in ("process_epoch", "binding_id", "connection_ref"))
                    or not self._store.transaction_owns_event(transaction_id=event.transaction_id,
                        event_id=event.event_id, principal_ref=_PRINCIPAL)):
                raise ValueError("invalid spatial event")
            transaction = self._store.get_transaction(event.transaction_id)
            if (transaction is None or len(transaction.events) != 1
                    or transaction.events[0] != event
                    or transaction.command_id != event.command_id
                    or transaction.idempotency_record.idempotency_key != payload["sample_key"]):
                raise ValueError("invalid spatial transaction")
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError("spatial_recovery_invalid") from exc

    def _latest(self, actor_id: str):
        stream = self.stream_id(actor_id)
        head = self._store.get_stream_head(stream)
        if head == 0:
            return None
        events = self._store.read_stream(stream, from_revision=head, limit=1)
        if len(events) != 1 or events[0].stream_revision != head:
            raise ValueError("spatial_recovery_invalid")
        self._validate_event(events[0], actor_id)
        return events[0]

    def accept(self, sample: EmbodiedSpatialSample, *, connection_ref: str) -> AppendBatchResult:
        sample = EmbodiedSpatialSample.model_validate(sample)
        scope = self._scope(sample)
        binding_result = self._auth.resolve_controller_binding(actor_id=sample.actor_id, connection_ref=connection_ref)
        binding = binding_result.binding
        if not binding_result.accepted or binding is None:
            raise ValueError(binding_result.error_code or "controller_binding_required")
        if binding.connection_epoch != sample.connection_epoch:
            raise ValueError("spatial_binding_epoch_mismatch")
        raw = sample.model_dump(mode="json")
        digest = _digest(raw)
        key = "spatial:" + _digest([self._process_epoch, binding.binding_id, sample.physics_tick])
        with self._lock:
            receipt = self._store.get_by_idempotency(_PRINCIPAL, key)
            if receipt is not None:
                if not receipt.committed or len(receipt.committed_event_ids) != 1:
                    raise ValueError("spatial_recovery_invalid")
                try:
                    event = self._store.get_event(receipt.committed_event_ids[0])
                except KeyError as exc:
                    raise ValueError("spatial_recovery_invalid") from exc
                self._validate_event(event, sample.actor_id)
                if event.payload["sample_key"] != key:
                    raise ValueError("spatial_recovery_invalid")
                if event.payload["sample_digest"] != digest:
                    raise ValueError("spatial_duplicate_changed")
                return receipt
            latest = self._latest(sample.actor_id)
            now = self._now()
            previous = latest.payload if latest is not None else None
            same_binding = previous is not None and previous["process_epoch"] == self._process_epoch and previous["binding_id"] == binding.binding_id
            origin = scope.spawn_position if previous is None else tuple(previous["sample"]["position"])
            if previous is not None and previous["scope_digest"] != _digest(scope.model_dump(mode="json")):
                raise ValueError("spatial_scope_migration_required")
            distance_limit = 0.
            if same_binding:
                old_tick = previous["sample"]["physics_tick"]
                if sample.physics_tick <= old_tick:
                    raise ValueError("spatial_tick_stale")
                elapsed_ms = now - previous["received_at_ms"]
                if elapsed_ms < 0:
                    raise ValueError("spatial_clock_reversed")
                elapsed = min(elapsed_ms / 1000, (sample.physics_tick - old_tick) / scope.physics_ticks_per_second)
                distance_limit = scope.max_speed_mps * elapsed
            if (any(not low <= x <= high for low, x, high in zip(scope.bounds_min, sample.position, scope.bounds_max))
                    or math.dist(origin, sample.position) > distance_limit + 1e-6):
                raise ValueError("spatial_continuity_rejected")
            stream = self.stream_id(sample.actor_id)
            revision = latest.stream_revision if latest is not None else 0
            payload = dict(sample=raw, sample_digest=digest, sample_key=key,
                scope=scope.model_dump(mode="json"), scope_digest=_digest(scope.model_dump(mode="json")),
                binding_id=binding.binding_id, connection_ref=connection_ref,
                process_epoch=self._process_epoch, received_at_ms=now)
            batch = build_multi_stream_atomic_event_batch(command_id=key, principal_ref=_PRINCIPAL,
                expected_revisions={stream: revision}, event_specs={stream: ((SPATIAL_SAMPLE_SCHEMA.event_type, payload),)},
                event_visibility_policies={stream: ("authority_only",)}, idempotency_key=key,
                causation_id=f"controller:{binding.binding_id}:{sample.physics_tick}", correlation_id=scope.source_ref)
            receipt = self._store.append_batch(batch)
            if not receipt.committed:
                raise ValueError("spatial_commit_failed")
            return receipt

    def read(self, *, actor_id: str, room_id: str, scene_id: str, scene_instance_id: str,
             zone_id: str, scene_revision: int) -> SpatialSourceEvidence:
        scope = self._scope(_ScopeIdentity(actor_id=actor_id, room_id=room_id, scene_id=scene_id,
            scene_instance_id=scene_instance_id, zone_id=zone_id, scene_revision=scene_revision))
        event = self._latest(actor_id)
        if event is None:
            raise ValueError("spatial_source_missing")
        payload = event.payload
        if payload["scope_digest"] != _digest(scope.model_dump(mode="json")):
            raise ValueError("spatial_scope_mismatch")
        if payload["process_epoch"] != self._process_epoch:
            raise ValueError("spatial_source_previous_process")
        binding_result = self._auth.resolve_controller_binding(actor_id=actor_id, connection_ref=payload["connection_ref"])
        binding = binding_result.binding
        if (not binding_result.accepted or binding is None or binding.binding_id != payload["binding_id"]
                or binding.connection_epoch != payload["sample"]["connection_epoch"]):
            raise ValueError("spatial_source_binding_revoked")
        age = self._now() - payload["received_at_ms"]
        if age < 0 or age > scope.max_age_ms:
            raise ValueError("spatial_source_stale")
        return SpatialSourceEvidence(position=tuple(payload["sample"]["position"]), event_ref=event.event_id,
            read_stream_revisions={event.stream_id: event.stream_revision})
