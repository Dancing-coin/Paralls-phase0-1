"""Backend-authoritative, replayable status-tag lifecycle for the Phase 3 slice."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Literal, Mapping

from pydantic import ConfigDict, Field

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.effective_stats import ModifierOperation, StackingPolicy, StatModifier
from app.gameplay.models import AppendBatchResult, GameplayEvent, StrictGameplayModel


StackPolicy = Literal["unique", "stack_count", "independent_sources"]
TagOperation = Literal["apply", "remove", "expire"]


class StatusTagError(ValueError):
    """Raised when tag definitions or committed lifecycle events are invalid."""


class StatusTagModifierTemplate(StrictGameplayModel):
    """A declarative source template; it never runs arbitrary patch code."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    template_id: str = Field(min_length=1)
    stat_id: str = Field(min_length=1)
    operation: ModifierOperation
    value: str = Field(min_length=1)
    priority: int = 0
    stacking_key: str = Field(min_length=1)
    stacking_policy: StackingPolicy = "stack"


class StatusTagDefinition(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tag_id: str = Field(min_length=1)
    definition_version: str = Field(min_length=1)
    stack_policy: StackPolicy = "unique"
    max_stacks: int | None = Field(default=None, ge=1)
    exclusivity_group: str | None = None
    modifier_templates: tuple[StatusTagModifierTemplate, ...] = ()

    def model_post_init(self, __context: object) -> None:
        if self.stack_policy != "stack_count" and self.max_stacks is not None:
            raise ValueError("status_tag_max_stacks_requires_stack_count")


class StatusTagRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, StatusTagDefinition] = {}

    def register(self, definition: StatusTagDefinition) -> None:
        if definition.tag_id in self._definitions:
            raise StatusTagError("status_tag_definition_duplicate")
        self._definitions[definition.tag_id] = definition

    def resolve(self, tag_id: str) -> StatusTagDefinition:
        try:
            return self._definitions[tag_id]
        except KeyError as exc:
            raise StatusTagError("status_tag_not_registered") from exc


@dataclass(frozen=True)
class StatusTagInstance:
    instance_id: str
    tag_id: str
    source_ref: str
    stack_count: int
    source_event_id: str


@dataclass(frozen=True)
class StatusTagStateProjection:
    actor_ref: str
    active_instances: Mapping[str, StatusTagInstance]
    source_revision_vector: Mapping[str, int]
    projection_revision: str


class StatusTagCommand(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    command_id: str = Field(min_length=1)
    actor_ref: str = Field(min_length=1)
    authority_principal: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    payload_digest: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    operation: TagOperation
    tag_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    instance_id: str | None = None


@dataclass(frozen=True)
class StatusTagAuthorityResult:
    accepted: bool
    reason_code: str | None
    projection: StatusTagStateProjection
    append_result: AppendBatchResult | None = None


class StatusTagProjector:
    _EVENTS = {"gameplay.status_tag.applied", "gameplay.status_tag.stack_changed", "gameplay.status_tag.removed", "gameplay.status_tag.expired"}

    def __init__(self, registry: StatusTagRegistry) -> None:
        self._registry = registry

    @property
    def registry(self) -> StatusTagRegistry:
        return self._registry

    def rebuild(
        self,
        actor_ref: str,
        events: list[GameplayEvent],
        *,
        checkpoint: StatusTagStateProjection | None = None,
    ) -> StatusTagStateProjection:
        if checkpoint is not None and checkpoint.actor_ref != actor_ref:
            raise StatusTagError("status_tag_actor_mismatch")
        instances: dict[str, StatusTagInstance] = dict(checkpoint.active_instances) if checkpoint is not None else {}
        revisions: dict[str, int] = dict(checkpoint.source_revision_vector) if checkpoint is not None else {}
        for event in sorted((item for item in events if item.event_type in self._EVENTS), key=lambda item: (item.global_sequence, item.event_id)):
            payload = event.payload
            if str(payload.get("actor_ref", "")) != actor_ref:
                raise StatusTagError("status_tag_actor_mismatch")
            tag_id = str(payload.get("tag_id", ""))
            definition = self._registry.resolve(tag_id)
            instance_id = str(payload.get("instance_id", ""))
            if not instance_id:
                raise StatusTagError("status_tag_event_payload_invalid")
            if event.event_type == "gameplay.status_tag.applied":
                if instance_id in instances:
                    raise StatusTagError("status_tag_instance_duplicate")
                source_ref = str(payload.get("source_ref", ""))
                stack_count = _positive_int(payload.get("stack_count"))
                if not source_ref or (definition.max_stacks is not None and stack_count > definition.max_stacks):
                    raise StatusTagError("status_tag_event_payload_invalid")
                instances[instance_id] = StatusTagInstance(instance_id, tag_id, source_ref, stack_count, event.event_id)
            elif event.event_type == "gameplay.status_tag.stack_changed":
                current = instances.get(instance_id)
                stack_count = _positive_int(payload.get("stack_count"))
                if current is None or current.tag_id != tag_id or definition.stack_policy != "stack_count":
                    raise StatusTagError("status_tag_stack_transition_invalid")
                if definition.max_stacks is not None and stack_count > definition.max_stacks:
                    raise StatusTagError("status_tag_stack_transition_invalid")
                instances[instance_id] = StatusTagInstance(instance_id, tag_id, current.source_ref, stack_count, event.event_id)
            else:
                current = instances.get(instance_id)
                if current is None or current.tag_id != tag_id:
                    raise StatusTagError("status_tag_remove_transition_invalid")
                del instances[instance_id]
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
        return StatusTagStateProjection(
            actor_ref=actor_ref,
            active_instances=MappingProxyType(dict(sorted(instances.items()))),
            source_revision_vector=MappingProxyType(dict(sorted(revisions.items()))),
            projection_revision="projection:" + _digest({"actor": actor_ref, "instances": instances, "revisions": revisions})[:16],
        )


def active_status_tag_modifiers(
    projection: StatusTagStateProjection,
    registry: StatusTagRegistry,
) -> list[StatModifier]:
    """Expose only active, declared tag templates as typed effective-stat sources."""

    modifiers: list[StatModifier] = []
    for instance in projection.active_instances.values():
        definition = registry.resolve(instance.tag_id)
        for template in definition.modifier_templates:
            modifiers.append(
                StatModifier(
                    modifier_id=f"status-tag:{instance.instance_id}:{template.template_id}",
                    stat_id=template.stat_id,
                    operation=template.operation,
                    value=template.value,
                    priority=template.priority,
                    stacking_key=template.stacking_key,
                    stacking_policy=template.stacking_policy,
                    source_ref=instance.source_ref,
                    source_event_id=instance.source_event_id,
                )
            )
    return modifiers


class StatusTagAuthorityService:
    """Writes lifecycle events only through the Gameplay event-store batch API."""

    _PRINCIPAL = "status_tag_authority"

    def __init__(
        self,
        *,
        store: GameplayEventStore,
        registry: StatusTagRegistry,
        authority_principal: str = "gameplay_authority",
    ) -> None:
        self._store = store
        self._registry = registry
        self._projector = StatusTagProjector(registry)
        self._authority_principal = authority_principal

    def apply(self, command: StatusTagCommand) -> StatusTagAuthorityResult:
        if command.authority_principal != self._authority_principal:
            raise StatusTagError("status_tag_authority_mismatch")
        stream_id = f"gameplay:status_tags:{command.actor_ref}"
        projection = self._projector.rebuild(command.actor_ref, self._store.read_stream(stream_id))
        receipt_key = f"{command.actor_ref}:{command.idempotency_key}"
        existing = self._store.get_idempotency_record(self._PRINCIPAL, receipt_key)
        if existing is not None:
            if existing.payload_digest != command.payload_digest:
                raise StatusTagError("idempotency_key_reused")
            return StatusTagAuthorityResult(True, None, projection, self._store.get_by_idempotency(self._PRINCIPAL, receipt_key))
        definition = self._registry.resolve(command.tag_id)
        event_type, payload, reason = self._event_for(command, definition, projection)
        if reason is not None:
            return StatusTagAuthorityResult(False, reason, projection)
        transaction_id = f"tx:{command.command_id}"
        result = self._store.append_batch({
            "transaction_id": transaction_id,
            "command_id": command.command_id,
            "expected_stream_revisions": {stream_id: self._store.get_stream_head(stream_id)},
            "pinned_revisions": {},
            "events": [{"event_id": f"evt:{command.command_id}:status-tag", "event_type": event_type, "schema_version": 1, "stream_id": stream_id, "stream_revision": 0, "global_sequence": 0, "transaction_id": transaction_id, "command_id": command.command_id, "causation_id": command.causation_id, "correlation_id": command.correlation_id, "visibility_policy": "authority_only", "payload": payload}],
            "idempotency_record": {"principal_ref": self._PRINCIPAL, "idempotency_key": receipt_key, "payload_digest": command.payload_digest},
            "outbox_entries": [],
            "result_digest": "sha256:" + _digest(payload),
            "projection_refresh_hints": [],
        })
        if not result.committed:
            return StatusTagAuthorityResult(False, result.failure.error_code if result.failure else "status_tag_append_failed", projection, result)
        return StatusTagAuthorityResult(True, None, self._projector.rebuild(command.actor_ref, self._store.read_stream(stream_id)), result)

    def _event_for(self, command: StatusTagCommand, definition: StatusTagDefinition, projection: StatusTagStateProjection) -> tuple[str, dict[str, object], str | None]:
        matches = [item for item in projection.active_instances.values() if item.tag_id == command.tag_id]
        conflicts = [
            item
            for item in projection.active_instances.values()
            if item.tag_id != command.tag_id
            and definition.exclusivity_group is not None
            and self._registry.resolve(item.tag_id).exclusivity_group == definition.exclusivity_group
        ]
        instance_id = command.instance_id or (matches[0].instance_id if matches and definition.stack_policy != "independent_sources" else f"tag:{command.command_id}")
        base = {"actor_ref": command.actor_ref, "tag_id": command.tag_id, "instance_id": instance_id}
        if command.operation == "apply":
            if conflicts:
                return "", base, "status_tag_conflict"
            if definition.stack_policy == "unique" and matches:
                return "", base, "status_tag_already_active"
            if definition.stack_policy == "stack_count" and matches:
                next_count = matches[0].stack_count + 1
                if definition.max_stacks is not None and next_count > definition.max_stacks:
                    return "", base, "status_tag_max_stacks_reached"
                return "gameplay.status_tag.stack_changed", {**base, "stack_count": next_count}, None
            return "gameplay.status_tag.applied", {**base, "source_ref": command.source_ref, "stack_count": 1}, None
        if command.operation in {"remove", "expire"}:
            if instance_id not in projection.active_instances:
                return "", base, "status_tag_instance_not_active"
            return f"gameplay.status_tag.{"expired" if command.operation == "expire" else "removed"}", base, None
        return "", base, "status_tag_operation_invalid"


def _positive_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise StatusTagError("status_tag_event_payload_invalid")
    return value


def _digest(value: object) -> str:
    return sha256(json.dumps(value, default=lambda item: item.__dict__ if isinstance(item, StatusTagInstance) else dict(item), ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
