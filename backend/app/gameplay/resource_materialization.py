"""Character template resource materialization owner and read-only caller."""

from __future__ import annotations

from typing import Any
import hashlib
import json

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, AtomicEventBatch
from app.gameplay.resource_template_admission import (
    ResourceTemplateAdmission,
    ResourceTemplateAdmissionError,
    ResourceTemplateSource,
)
from app.gameplay.settlement_plan import build_multi_stream_atomic_event_batch


RESOURCE_TEMPLATE_CALLER = "resource-template-consumer"


def _canonical_actor(actor_ref: str) -> str:
    """Profile and resource streams use the character id as their canonical key."""
    if not isinstance(actor_ref, str) or not actor_ref:
        raise ValueError("resource_actor_invalid")
    if actor_ref.startswith("actor:"):
        raise ValueError("resource_actor_alias_not_admitted")
    actor = actor_ref.removeprefix("character:")
    if not actor:
        raise ValueError("resource_actor_invalid")
    return actor


class ResourceMaterializationAuthorityService:
    """Static authored sources are immutable for this service composition.

    The actor-global stream binds its first world/timeline until a separate
    migration owner is admitted. Caller ticks are metadata, not world time.
    """

    def __init__(self, *, store: GameplayEventStore, registry: CharacterProfileRegistry | None = None) -> None:
        self.store = store
        self.registry = registry
        self._registry_snapshot = CharacterProfileRegistry({
            actor: registry.get(actor).model_copy(deep=True) for actor in registry.actor_ids()
        }) if registry is not None else None
        self.admission = ResourceTemplateAdmission()

    def materialize(
        self,
        *,
        actor_ref: str,
        world_ref: str,
        timeline_ref: str,
        world_tick: int,
        idempotency_key: str,
        expected_revision: int,
        source: ResourceTemplateSource | None = None,
        read_stream_revisions: dict[str, int] | None = None,
    ) -> AppendBatchResult:
        actor = _canonical_actor(actor_ref)
        principal = RESOURCE_TEMPLATE_CALLER
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("resource_expected_revision_invalid")
        if type(world_tick) is not int or world_tick < 0:
            raise ValueError("resource_world_tick_invalid")
        for name, value in (("world_ref", world_ref), ("timeline_ref", timeline_ref), ("idempotency_key", idempotency_key)):
            if not isinstance(value, str) or not value:
                raise ValueError(f"resource_{name}_invalid")
        if read_stream_revisions is not None and (
            not isinstance(read_stream_revisions, dict)
            or any(not isinstance(key, str) or not key for key in read_stream_revisions)
            or any(type(value) is not int or value < 0 for value in read_stream_revisions.values())
        ):
            raise ValueError("resource_read_set_invalid")
        prior = self.store.get_by_idempotency(principal, idempotency_key)
        if prior is not None:
            try:
                original = self.store.get_event(prior.committed_event_ids[0])
                trusted = ResourceTemplateSource.model_validate(original.payload["template_source"])
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise ValueError("resource_receipt_incomplete") from exc
            if source is not None and source != trusted:
                raise ValueError("idempotency_key_reused")
            source = trusted
        else:
            if self._registry_snapshot is None:
                raise ValueError("resource_template_source_unavailable")
            trusted = self._registry_snapshot.resource_template_source(actor, world_ref=world_ref, timeline_ref=timeline_ref)
            if source is None:
                source = trusted
            if trusted != source:
                raise ResourceTemplateAdmissionError("resource_template_source_changed")
            if source.valid_from_world_tick != 0 or source.valid_until_world_tick is not None:
                raise ResourceTemplateAdmissionError("resource_template_confirmed_time_required")
            self.admission.admit(
                source, actor_ref=actor, world_ref=world_ref, timeline_ref=timeline_ref,
                now_world_tick=world_tick, caller_principal=principal,
                binding_revision=source.binding_revision,
            )
        request_digest = "sha256:" + hashlib.sha256(json.dumps({
            "actor_ref": actor, "world_ref": world_ref, "timeline_ref": timeline_ref,
            "world_tick": world_tick, "source": source.model_dump(mode="json"),
            "read_stream_revisions": read_stream_revisions or {},
        }, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        stream = f"gameplay:resources:{actor}"
        if prior is None and self.store.get_stream_head(stream) != 0:
            raise ValueError("resource_already_materialized")
        specs: list[tuple[str, dict[str, Any]]] = []
        for entry in source.resources:
            specs.append(("gameplay.resource.materialized", {
                "actor_ref": actor,
                "request_digest": request_digest,
                "resource_id": entry.resource_id,
                "minimum": 0,
                "maximum": entry.maximum,
                "current": entry.initial,
                "template_ref": source.template_ref,
                "template_revision": source.template_revision,
                "definition_version": source.template_revision,
                "resource_schema": "resource.v2",
                "capacity": entry.capacity,
                "base_capacity": entry.base_capacity,
                "locked": 0,
                "debt": 0,
                "debt_ceiling": 0,
                "modifier_ledger": [],
                "modifier_ledger_digest": "sha256:" + hashlib.sha256(b"[]").hexdigest(),
                "template_digest": source.source_digest,
                "template_source": source.model_dump(mode="json"),
                "binding_revision": source.binding_revision,
                "recovery_amount": entry.recovery_amount,
                "recovery_period_world_ticks": entry.recovery_period_world_ticks,
                "debt_policy": entry.debt_policy,
                "lock_issuer_ref": entry.lock_issuer_ref,
                "lock_lifecycle_revision": entry.lock_lifecycle_revision,
                "world_ref": world_ref,
                "timeline_ref": timeline_ref,
                "materialized_world_tick": world_tick,
                "source_receipt_kind": source.receipt_kind,
                "source_receipt_key": source.receipt_key,
            }))
        command_id = f"resource-materialize:{actor}:{idempotency_key}"
        batch = build_multi_stream_atomic_event_batch(
            command_id=command_id,
            principal_ref=principal,
            expected_revisions={stream: 0 if prior is not None else expected_revision},
            event_specs={stream: specs},
            idempotency_key=idempotency_key,
            causation_id=f"cause:{command_id}",
            correlation_id=f"correlation:{command_id}",
            read_stream_revisions=read_stream_revisions or {},
            event_visibility_policies={stream: ["authority_only"] * len(specs)},
        )
        if prior is not None:
            try:
                originals = [self.store.get_event(event_id) for event_id in prior.committed_event_ids]
            except KeyError as exc:
                raise ValueError("resource_receipt_incomplete") from exc
            if originals and any(event.payload.get("request_digest") != request_digest for event in originals):
                raise ValueError("idempotency_key_reused")
            if not self._receipt_is_complete(prior, batch):
                raise ValueError("resource_receipt_incomplete")
            return prior.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
        return self.store.append_batch(batch)

    def _receipt_is_complete(self, result: AppendBatchResult, expected: AtomicEventBatch) -> bool:
        """Validate the complete persisted transaction before replaying its receipt."""
        if not result.committed or result.failure is not None:
            return False
        transaction = self.store.get_transaction(result.transaction_id)
        if transaction is None or result.transaction_id != expected.transaction_id or result.command_id != expected.command_id:
            return False
        events = transaction.events
        if len(events) != len(expected.events) or result.committed_event_ids != [event.event_id for event in events]:
            return False
        if result.resulting_stream_revisions != {expected.events[0].stream_id: len(events)}:
            return False
        if result.global_sequence_range != (events[0].global_sequence, events[-1].global_sequence):
            return False
        normalized = transaction.model_copy(update={"events": [
            event.model_copy(update={"stream_revision": 0, "global_sequence": 0}) for event in events
        ]}, deep=True)
        if normalized != expected:
            return False
        for index, event in enumerate(events, start=1):
            try:
                persisted = self.store.get_event(event.event_id)
            except KeyError:
                return False
            if persisted != event or event.stream_revision != index or event.global_sequence != events[0].global_sequence + index - 1:
                return False
        return True


class CharacterResourceMaterializationCaller:
    """Delegate to the owner's immutable source and original-receipt boundary."""

    def __init__(self, *, registry: CharacterProfileRegistry | None = None,
                 authority: ResourceMaterializationAuthorityService) -> None:
        self.registry = registry or authority.registry
        self.authority = authority

    def materialize(self, *, actor_ref: str, world_ref: str, timeline_ref: str,
                    world_tick: int, idempotency_key: str, expected_revision: int,
                    read_stream_revisions: dict[str, int] | None = None) -> AppendBatchResult:
        actor = _canonical_actor(actor_ref)
        return self.authority.materialize(
            actor_ref=actor, world_ref=world_ref, timeline_ref=timeline_ref,
            world_tick=world_tick, idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            read_stream_revisions=read_stream_revisions,
        )


__all__ = ["CharacterResourceMaterializationCaller", "ResourceMaterializationAuthorityService"]
