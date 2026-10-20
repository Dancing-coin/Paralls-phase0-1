from __future__ import annotations

from typing import Literal
import hashlib
import json

from pydantic import Field

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import StrictGameplayModel
from app.gameplay.event_schema_registry import EventSchemaRegistration, EventSchemaRegistry, EventSchemaRegistryError
from app.gameplay.settlement_plan import build_atomic_event_batch
from .activation_sources import ActivationSourceReader


PRESENCE_EVENT_SCHEMAS = (
    EventSchemaRegistration("population.presence.spawned", 1, "sha256:population:presence-spawned:v1"),
    EventSchemaRegistration("population.presence.despawned", 1, "sha256:population:presence-despawned:v1"),
)


def register_presence_event_schemas(registry: EventSchemaRegistry) -> None:
    """Opt in to Presence schema1 only; LifeState is an independent owner."""
    for row in PRESENCE_EVENT_SCHEMAS:
        try:
            registry.register(row)
        except EventSchemaRegistryError:
            if registry.get(row.event_type, row.schema_version) != row:
                raise


class PresenceRequest(StrictGameplayModel):
    world_ref: str = Field(min_length=1)
    character_ref: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    expected_revision: int = Field(ge=0, strict=True)


class CharacterSpawnRequest(PresenceRequest):
    activation_event_id: str = Field(min_length=1)


class CharacterDespawnRequest(PresenceRequest):
    incarnation: int = Field(ge=1, strict=True)
    reason: str = Field(min_length=1)


class PresenceReceipt(StrictGameplayModel):
    committed: bool
    status: Literal["spawned", "despawned", "rejected"]
    world_ref: str
    character_ref: str
    incarnation: int | None = None
    source_activation_event_id: str | None = None
    committed_event_ids: tuple[str, ...] = ()
    revision_vector: dict[str, int] = Field(default_factory=dict)
    idempotency_status: str = "rejected"
    zero_write: bool = False
    stop_reason: str | None = None


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class PopulationPresenceAuthority:
    """Presence owns incarnation facts, separately from activation and LifeState.

    New spawn requires a trusted actual activation source. Until a named Life
    adapter is integrated, only Life-stream absence can be admitted atomically.
    """

    _PRINCIPAL = "population.presence_authority"
    _STREAM_PREFIX = "presence:"

    def __init__(self, *, store: GameplayEventStore,
                 activation_sources: ActivationSourceReader | None = None) -> None:
        if activation_sources is not None and (type(activation_sources) is not ActivationSourceReader
                or activation_sources._store is not store):
            raise ValueError("presence_source_store")
        self.store = store
        self._sources = activation_sources

    @classmethod
    def stream_id(cls, world_ref: str) -> str:
        return f"{cls._STREAM_PREFIX}{world_ref}"

    def spawn(self, request: CharacterSpawnRequest) -> PresenceReceipt:
        prior = self.store.get_by_idempotency(self._PRINCIPAL, request.idempotency_key)
        if prior is not None:
            return self._recover(prior, request, "spawned")
        if self._sources is None:
            return self._rejected(request, "activation_source_unavailable")
        stream = self.stream_id(request.world_ref)
        head = self.store.get_stream_head(stream)
        if head != request.expected_revision:
            return self._rejected(request, "revision_conflict")
        try:
            source = self._sources.read(request.activation_event_id,
                world_ref=request.world_ref, profile_ref=request.character_ref)
            active, maximum = self._history(request.world_ref, head=head)
        except ValueError as exc:
            return self._rejected(request, str(exc))
        life_stream = f"gameplay:character:life:{request.character_ref}"
        life_head = self.store.get_stream_head(life_stream)
        if life_head != 0:
            return self._rejected(request, "life_source_unavailable")
        if request.character_ref in active:
            return self._rejected(request, "presence_already_active")
        incarnation = maximum.get(request.character_ref, 0) + 1
        reads = dict(source.read_revisions) | {life_stream: 0}
        batch = self._batch(request, "spawned", incarnation, reads=reads)
        result = self.store.append_batch(batch)
        if not result.committed:
            return self._rejected(request, result.failure.error_code if result.failure else "append_rejected")
        return self._receipt(result, request, "spawned", incarnation)

    def despawn(self, request: CharacterDespawnRequest) -> PresenceReceipt:
        prior = self.store.get_by_idempotency(self._PRINCIPAL, request.idempotency_key)
        if prior is not None:
            return self._recover(prior, request, "despawned")
        stream = self.stream_id(request.world_ref)
        head = self.store.get_stream_head(stream)
        # Capture/check before the scan; never approve a future caller head.
        if head != request.expected_revision:
            return self._rejected(request, "revision_conflict")
        try:
            active, _ = self._history(request.world_ref, head=head)
        except ValueError as exc:
            return self._rejected(request, str(exc))
        if active.get(request.character_ref) != request.incarnation:
            return self._rejected(request, "presence_incarnation_not_active")
        result = self.store.append_batch(self._batch(request, "despawned", request.incarnation))
        if not result.committed:
            return self._rejected(request, result.failure.error_code if result.failure else "append_rejected")
        return self._receipt(result, request, "despawned", request.incarnation)

    def projection(self, world_ref: str, *, checkpoint_at: int | None = None) -> dict[str, dict[str, object]]:
        if checkpoint_at is not None and (type(checkpoint_at) is not int or checkpoint_at < 0):
            raise ValueError("presence_checkpoint_invalid")
        head = self.store.get_stream_head(self.stream_id(world_ref))
        active, _ = self._history(world_ref, head=head, checkpoint_at=checkpoint_at)
        return {character: {"incarnation": incarnation, "status": "present"}
            for character, incarnation in active.items()}

    @staticmethod
    def _request_digest(request: PresenceRequest, operation: str) -> str:
        value = {"operation": operation, "request": request.model_dump(mode="json")}
        return "sha256:" + hashlib.sha256(_canonical(value).encode()).hexdigest()

    def _batch(self, request, operation, incarnation, *, reads=None):
        payload = dict(world_ref=request.world_ref, character_ref=request.character_ref,
            incarnation=incarnation, request_digest=self._request_digest(request, operation))
        if operation == "spawned":
            payload["source_activation_event_id"] = request.activation_event_id
            verb, cause = "spawn", request.activation_event_id
        else:
            payload["reason"] = request.reason
            verb, cause = "despawn", f"presence:{request.character_ref}:{incarnation}"
        return build_atomic_event_batch(
            command_id=f"presence:{verb}:{request.world_ref}:{request.character_ref}:{incarnation}",
            principal_ref=self._PRINCIPAL, stream_id=self.stream_id(request.world_ref),
            expected_revision=request.expected_revision,
            event_specs=[(f"population.presence.{operation}", payload)],
            idempotency_key=request.idempotency_key, causation_id=cause,
            correlation_id=f"correlation:{request.world_ref}",
            read_stream_revisions=reads, pinned_revisions=reads)

    def _validated_event(self, event, world_ref):
        invalid = "presence_original_receipt_invalid"
        if (event.event_type not in ("population.presence.spawned", "population.presence.despawned")
                or type(event.schema_version) is not int or event.schema_version != 1
                or event.visibility_policy != "project" or event.stream_id != self.stream_id(world_ref)
                or type(event.stream_revision) is not int or event.stream_revision < 1
                or type(event.global_sequence) is not int or event.global_sequence < 1):
            raise ValueError(invalid)
        payload = event.payload
        character, incarnation = payload.get("character_ref"), payload.get("incarnation")
        if (not isinstance(character, str) or not character.startswith("character:")
                or not character.removeprefix("character:") or payload.get("world_ref") != world_ref
                or type(incarnation) is not int or incarnation < 1):
            raise ValueError(invalid)
        batch = self.store.get_transaction(event.transaction_id)
        if batch is None or len(batch.events) != 1:
            raise ValueError(invalid)
        record = batch.idempotency_record
        base = dict(world_ref=world_ref, character_ref=character,
            expected_revision=event.stream_revision - 1, idempotency_key=record.idempotency_key)
        operation = event.event_type.removeprefix("population.presence.")
        reads = None
        if operation == "spawned":
            if set(payload) != {"world_ref", "character_ref", "incarnation", "source_activation_event_id", "request_digest"}:
                raise ValueError(invalid)
            request = CharacterSpawnRequest(**base, activation_event_id=payload["source_activation_event_id"])
            population, life = f"population:{world_ref}", f"gameplay:character:life:{character}"
            reads = batch.read_stream_revisions
            if (self._sources is None or set(reads) != {population, life}
                    or type(reads[life]) is not int or reads[life] != 0
                    or type(reads[population]) is not int or reads[population] < 1):
                raise ValueError(invalid)
            try:
                source = self._sources.recover(request.activation_event_id, world_ref=world_ref,
                    profile_ref=character, at_revision=reads[population])
            except ValueError as exc:
                raise ValueError(invalid) from exc
            if source.last_global_sequence >= event.global_sequence:
                raise ValueError(invalid)
        else:
            if set(payload) != {"world_ref", "character_ref", "incarnation", "reason", "request_digest"}:
                raise ValueError(invalid)
            request = CharacterDespawnRequest(**base, incarnation=incarnation, reason=payload["reason"])
        expected = self._batch(request, operation, incarnation, reads=reads)
        expected.events[0] = expected.events[0].model_copy(update={
            "stream_revision": event.stream_revision, "global_sequence": event.global_sequence})
        receipt = self.store.get_by_idempotency(record.principal_ref, record.idempotency_key)
        try:
            indexed = self.store.get_event(event.event_id)
        except KeyError as exc:
            raise ValueError(invalid) from exc
        if (_canonical(batch.model_dump(mode="json")) != _canonical(expected.model_dump(mode="json"))
                or _canonical(batch.events[0].model_dump(mode="json")) != _canonical(event.model_dump(mode="json"))
                or _canonical(indexed.model_dump(mode="json")) != _canonical(event.model_dump(mode="json"))
                or self.store.get_idempotency_record(record.principal_ref, record.idempotency_key) != record
                or receipt is None or receipt.committed is not True or receipt.failure is not None
                or receipt.idempotency_status != "new_commit" or receipt.transaction_id != batch.transaction_id
                or receipt.command_id != batch.command_id or receipt.committed_event_ids != [event.event_id]
                or _canonical(receipt.resulting_stream_revisions) != _canonical({event.stream_id: event.stream_revision})
                or _canonical(receipt.global_sequence_range) != _canonical((event.global_sequence, event.global_sequence))
                or receipt.projection_refresh_hints):
            raise ValueError(invalid)
        return request, operation

    def _history(self, world_ref, *, head, checkpoint_at=None):
        if type(head) is not int or head < 0:
            raise ValueError("presence_history_head")
        stream = self.stream_id(world_ref)
        events = self.store.read_stream(stream, to_revision=head) if head else []
        if len(events) != head:
            raise ValueError("presence_history_incomplete")
        active, maximum = {}, {}
        last_sequence = 0
        for revision, event in enumerate(events, 1):
            if (type(event.stream_revision) is not int or event.stream_revision != revision
                    or type(event.global_sequence) is not int or event.global_sequence <= last_sequence):
                raise ValueError("presence_history_order")
            last_sequence = event.global_sequence
            if checkpoint_at is not None and event.global_sequence > checkpoint_at:
                break
            request, operation = self._validated_event(event, world_ref)
            character, incarnation = request.character_ref, event.payload["incarnation"]
            if operation == "spawned":
                if character in active or incarnation != maximum.get(character, 0) + 1:
                    raise ValueError("presence_history_spawn_transition")
                active[character] = maximum[character] = incarnation
            elif active.get(character) != incarnation:
                raise ValueError("presence_history_despawn_transition")
            else:
                active.pop(character)
        return active, maximum

    def _recover(self, prior, request, operation):
        try:
            if len(prior.committed_event_ids) != 1:
                raise ValueError("presence_original_receipt_invalid")
            event = self.store.get_event(prior.committed_event_ids[0])
            original, actual_operation = self._validated_event(event, request.world_ref)
            # The caller's current CAS hint is not original request identity.
            retry = request.model_copy(update={"expected_revision": original.expected_revision})
            if actual_operation != operation or _canonical(retry.model_dump(mode="json")) != _canonical(original.model_dump(mode="json")):
                raise ValueError("idempotency_key_reused")
            self._history(request.world_ref, head=event.stream_revision)
            return self._receipt(prior, original, operation, event.payload["incarnation"], duplicate=True)
        except (ValueError, KeyError, TypeError):
            return self._rejected(request, "presence_original_receipt_invalid")

    @staticmethod
    def _receipt(result, request, operation, incarnation, *, duplicate=False):
        return PresenceReceipt(committed=True, status=operation, world_ref=request.world_ref,
            character_ref=request.character_ref, incarnation=incarnation,
            source_activation_event_id=request.activation_event_id if operation == "spawned" else None,
            committed_event_ids=tuple(result.committed_event_ids), revision_vector=dict(result.resulting_stream_revisions),
            idempotency_status="duplicate_replayed" if duplicate else result.idempotency_status,
            zero_write=duplicate)

    @staticmethod
    def _rejected(request: PresenceRequest, reason: str) -> PresenceReceipt:
        return PresenceReceipt(committed=False, status="rejected", world_ref=request.world_ref,
            character_ref=request.character_ref, zero_write=True, stop_reason=reason)


__all__ = ["CharacterDespawnRequest", "CharacterSpawnRequest", "PopulationPresenceAuthority",
    "PresenceReceipt", "PRESENCE_EVENT_SCHEMAS", "register_presence_event_schemas"]
