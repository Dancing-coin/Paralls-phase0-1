"""Backend-authoritative, replayable status-tag lifecycle for the Phase 3 slice."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from fractions import Fraction
from math import ceil
from types import MappingProxyType
from typing import Literal, Mapping

from pydantic import ConfigDict, Field

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.effective_stats import ModifierOperation, StackingPolicy, StatModifier
from app.gameplay.models import AppendBatchResult, GameplayEvent, StrictGameplayModel
from app.world_runtime.temporal_contracts import ClockMapping, ScheduledWork, SimulationTime


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


class StatusTagExpiry(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    timeline_id: str = Field(min_length=1)
    profile_revision: str = Field(min_length=1)
    mapping_id: str = Field(min_length=1)
    mapping_revision: str = Field(min_length=1)
    due_step: int = Field(ge=0)
    due_time_value: str = Field(min_length=1)
    source_clock_ref: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    evidence_freshness: int = Field(ge=0)


@dataclass(frozen=True)
class StatusTagTemporalContext:
    now: SimulationTime
    mapping: ClockMapping
    profile_revision: str
    source_revision: str
    evidence_freshness: int
    step_duration: Fraction = Fraction(1)

    def __post_init__(self) -> None:
        if self.now.timeline_id != self.mapping.target_timeline_ref:
            raise ValueError("status_tag_timeline_mismatch")
        if self.profile_revision != self.mapping.target_profile_revision:
            raise ValueError("status_tag_profile_revision_mismatch")

    def expiry_after(self, steps: int) -> StatusTagExpiry:
        if type(steps) is not int or steps <= 0:
            raise ValueError("status_tag_duration_invalid")
        value = self.now.canonical_time_value + self.step_duration * steps
        return StatusTagExpiry(
            timeline_id=self.now.timeline_id, profile_revision=self.profile_revision,
            mapping_id=self.mapping.mapping_id, mapping_revision=self.mapping.revision,
            due_step=self.now.step_index + steps,
            due_time_value=f"{value.numerator}/{value.denominator}",
            source_clock_ref=self.mapping.source_clock_ref,
            source_revision=self.source_revision, evidence_freshness=self.evidence_freshness,
        )

    def validate_reference(self, expiry: StatusTagExpiry) -> None:
        if expiry.timeline_id != self.now.timeline_id:
            raise ValueError("status_tag_timeline_mismatch")
        if expiry.profile_revision != self.profile_revision:
            raise ValueError("status_tag_profile_revision_stale")
        if (expiry.mapping_id, expiry.mapping_revision) != (self.mapping.mapping_id, self.mapping.revision):
            raise ValueError("status_tag_mapping_stale")
        if (expiry.source_clock_ref, expiry.source_revision) != (self.mapping.source_clock_ref, self.source_revision):
            raise ValueError("status_tag_source_revision_stale")
    def validate_expiry(self, expiry: StatusTagExpiry) -> None:
        self.validate_reference(expiry)
        try:
            numerator, denominator = expiry.due_time_value.split("/", 1)
            due_value = Fraction(int(numerator), int(denominator))
        except (ValueError, ZeroDivisionError) as exc:
            raise ValueError("status_tag_due_time_invalid") from exc
        if self.now.step_index < expiry.due_step or self.now.canonical_time_value < due_value:
            raise ValueError("status_tag_not_due")


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
    expiry: StatusTagExpiry | None = None


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
    expiry: StatusTagExpiry | None = None


@dataclass(frozen=True)
class StatusTagAuthorityResult:
    accepted: bool
    reason_code: str | None
    projection: StatusTagStateProjection
    append_result: AppendBatchResult | None = None


class StatusTagProjector:
    _EVENTS = {"gameplay.status_tag.applied", "gameplay.status_tag.stack_changed", "gameplay.status_tag.removed", "gameplay.status_tag.expired", "gameplay.status_tag.time_migrated"}

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
            if event.event_type == "gameplay.status_tag.time_migrated":
                for row in payload["instances"]:
                    current = instances.get(row["instance_id"])
                    if current is None or current.expiry is None or current.expiry.model_dump(mode="json") != row["old_expiry"]:
                        raise StatusTagError("status_tag_migration_instance_stale")
                    instances[row["instance_id"]] = StatusTagInstance(
                        current.instance_id, current.tag_id, current.source_ref, current.stack_count,
                        current.source_event_id, StatusTagExpiry.model_validate(row["expiry"]))
                revisions[event.stream_id] = event.stream_revision
                continue
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
                expiry_payload = payload.get("expiry")
                expiry = StatusTagExpiry.model_validate(expiry_payload) if expiry_payload is not None else None
                instances[instance_id] = StatusTagInstance(instance_id, tag_id, source_ref, stack_count, event.event_id, expiry)
            elif event.event_type == "gameplay.status_tag.stack_changed":
                current = instances.get(instance_id)
                stack_count = _positive_int(payload.get("stack_count"))
                if current is None or current.tag_id != tag_id or definition.stack_policy != "stack_count":
                    raise StatusTagError("status_tag_stack_transition_invalid")
                if definition.max_stacks is not None and stack_count > definition.max_stacks:
                    raise StatusTagError("status_tag_stack_transition_invalid")
                instances[instance_id] = StatusTagInstance(instance_id, tag_id, current.source_ref, stack_count, event.event_id, current.expiry)
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

    @property
    def projector(self) -> StatusTagProjector:
        return self._projector

    def migrate_time(self, *, actor_ref: str, migration_id: str, expected_revision: int,
                     old_context: StatusTagTemporalContext, new_context: StatusTagTemporalContext,
                     old_profile_revision: str, new_profile_revision: str,
                     old_step_duration: Fraction, new_step_duration: Fraction,
                     boundary_tick: int) -> AppendBatchResult:
        from math import ceil
        stream_id = f"gameplay:status_tags:{actor_ref}"
        key = f"{actor_ref}:time-migration:{migration_id}"
        migration_input = {
            "actor_ref": actor_ref, "migration_id": migration_id, "expected_revision": expected_revision,
            "boundary_tick": boundary_tick,
            "old_profile_revision": old_profile_revision, "new_profile_revision": new_profile_revision,
            "old_step_duration": str(old_step_duration), "new_step_duration": str(new_step_duration),
            "old_context": _temporal_context_digest_value(old_context),
            "new_context": _temporal_context_digest_value(new_context),
        }
        migration_input_digest = "sha256:" + _digest(migration_input)
        existing = self._store.get_by_idempotency(self._PRINCIPAL, key)
        if existing is not None:
            prior_events = tuple(self._store.get_event(event_id) for event_id in existing.committed_event_ids)
            exact = (
                len(prior_events) == 1
                and prior_events[0].event_type == "gameplay.status_tag.time_migrated"
                and prior_events[0].command_id == f"time-migration:{migration_id}:{actor_ref}"
                and prior_events[0].causation_id == migration_id
                and prior_events[0].correlation_id == migration_id
                and prior_events[0].payload.get("migration_id") == migration_id
                and prior_events[0].payload.get("actor_ref") == actor_ref
                and prior_events[0].payload.get("migration_input_digest") == migration_input_digest
            )
            if not exact:
                raise ValueError("idempotency_key_reused")
            return existing.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
        if self._store.get_stream_head(stream_id) != expected_revision:
            raise ValueError("status_tag_revision_stale")
        projection = self._projector.rebuild(actor_ref, self._store.read_stream(stream_id))
        rows = []
        for instance in projection.active_instances.values():
            expiry = instance.expiry
            if expiry is None:
                continue
            old_context.validate_reference(expiry)
            due = Fraction(expiry.due_time_value)
            remaining = max(Fraction(0), due - old_context.now.canonical_time_value)
            due_step = new_context.now.step_index + ceil(remaining / new_step_duration)
            due_value = due_step * new_step_duration
            replacement = StatusTagExpiry(
                timeline_id=expiry.timeline_id, profile_revision=new_profile_revision,
                mapping_id=new_context.mapping.mapping_id, mapping_revision=new_context.mapping.revision,
                due_step=due_step, due_time_value=f"{due_value.numerator}/{due_value.denominator}",
                source_clock_ref=expiry.source_clock_ref, source_revision=new_context.source_revision,
                evidence_freshness=expiry.evidence_freshness)
            rows.append({"instance_id": instance.instance_id, "old_expiry": expiry.model_dump(mode="json"),
                         "expiry": replacement.model_dump(mode="json"),
                         "remaining_world_duration": f"{remaining.numerator}/{remaining.denominator}",
                         "rounding_policy": "ceil",
                         "work_ref": f"status-expiry:{actor_ref}:{instance.instance_id}",
                         "trigger_ref": instance.instance_id})
        payload = {"actor_ref": actor_ref, "migration_id": migration_id, "boundary_tick": boundary_tick,
                   "old_profile_revision": old_profile_revision, "new_profile_revision": new_profile_revision,
                   "old_step_duration": str(old_step_duration), "new_step_duration": str(new_step_duration),
                   "old_mapping_revision": old_context.mapping.revision,
                   "new_mapping_revision": new_context.mapping.revision,
                   "migration_input_digest": migration_input_digest,
                   "instances": rows}
        digest = "sha256:" + _digest(payload)
        command_id = f"time-migration:{migration_id}:{actor_ref}"
        transaction_id = f"tx:{command_id}"
        result = self._store.append_batch({
            "transaction_id": transaction_id, "command_id": command_id,
            "expected_stream_revisions": {stream_id: expected_revision}, "pinned_revisions": {},
            "events": [{"event_id": f"evt:{command_id}", "event_type": "gameplay.status_tag.time_migrated",
                        "schema_version": 1, "stream_id": stream_id, "stream_revision": 0,
                        "global_sequence": 0, "transaction_id": transaction_id, "command_id": command_id,
                        "causation_id": migration_id, "correlation_id": migration_id,
                        "visibility_policy": "authority_only", "payload": payload}],
            "idempotency_record": {"principal_ref": self._PRINCIPAL, "idempotency_key": key,
                                   "payload_digest": digest},
            "outbox_entries": [], "result_digest": digest, "projection_refresh_hints": [],
        })
        if not result.committed:
            raise ValueError(result.failure.error_code if result.failure else "status_tag_migration_failed")
        return result

    def apply(
        self,
        command: StatusTagCommand,
        *,
        temporal: StatusTagTemporalContext | None = None,
        expires_after_steps: int | None = None,
    ) -> StatusTagAuthorityResult:
        if command.authority_principal != self._authority_principal:
            raise StatusTagError("status_tag_authority_mismatch")
        stream_id = f"gameplay:status_tags:{command.actor_ref}"
        projection = self._projector.rebuild(command.actor_ref, self._store.read_stream(stream_id))
        receipt_key = f"{command.actor_ref}:{command.idempotency_key}"
        fingerprint = _request_fingerprint(command, temporal, expires_after_steps)
        existing = self._store.get_idempotency_record(self._PRINCIPAL, receipt_key)
        if existing is not None:
            if existing.payload_digest != command.payload_digest:
                raise StatusTagError("idempotency_key_reused")
            original = self._store.get_by_idempotency(self._PRINCIPAL, receipt_key)
            if original is None or not original.committed or len(original.committed_event_ids) != 1:
                raise StatusTagError("idempotency_receipt_invalid")
            try:
                event = self._store.get_event(original.committed_event_ids[0])
            except KeyError as exc:
                raise StatusTagError("idempotency_receipt_invalid") from exc
            if event.stream_id != stream_id or event.command_id != command.command_id:
                raise StatusTagError("idempotency_key_reused")
            saved = event.payload.get("request_fingerprint")
            if saved is not None:
                if saved != fingerprint:
                    raise StatusTagError("idempotency_key_reused")
            elif (expires_after_steps is not None or command.expiry is not None
                  or event.event_type != f"gameplay.status_tag.{ {'apply': 'applied', 'remove': 'removed', 'expire': 'expired'}[command.operation]}"
                  or event.payload.get("tag_id") != command.tag_id
                  or (command.instance_id is not None and event.payload.get("instance_id") != command.instance_id)
                  or (command.operation == "apply" and event.payload.get("source_ref") != command.source_ref)):
                raise StatusTagError("idempotency_key_reused")
            return StatusTagAuthorityResult(True, None, projection, original)
        definition = self._registry.resolve(command.tag_id)
        if expires_after_steps is not None:
            if command.operation != "apply" or temporal is None or command.expiry is not None:
                raise StatusTagError("status_tag_expiry_contract_invalid")
            expiry = temporal.expiry_after(expires_after_steps)
        else:
            expiry = command.expiry
            if expiry is not None:
                if temporal is None:
                    raise StatusTagError("status_tag_temporal_context_missing")
                temporal.validate_expiry(expiry)
        event_type, payload, reason = self._event_for(command, definition, projection, expiry=expiry)
        if reason is not None:
            return StatusTagAuthorityResult(False, reason, projection)
        payload["request_fingerprint"] = fingerprint
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

    def expiration_work(self, projection: StatusTagStateProjection) -> ScheduledWork:
        expiring = [item for item in projection.active_instances.values() if item.expiry is not None]
        if len(expiring) != 1:
            raise ValueError("status_tag_expiration_work_ambiguous")
        return self._expiration_work(projection, expiring[0])

    def expiration_works(self, projection: StatusTagStateProjection) -> tuple[ScheduledWork, ...]:
        return tuple(self._expiration_work(projection, item) for item in projection.active_instances.values()
                     if item.expiry is not None)

    def _expiration_work(self, projection: StatusTagStateProjection, instance: StatusTagInstance) -> ScheduledWork:
        assert instance.expiry is not None
        numerator, denominator = instance.expiry.due_time_value.split("/", 1)
        stream_id = f"gameplay:status_tags:{projection.actor_ref}"
        return ScheduledWork(
            work_ref=f"status-expiry:{projection.actor_ref}:{instance.instance_id}",
            domain_ref="status_tags",
            due_time=SimulationTime(instance.expiry.timeline_id, instance.expiry.due_step, Fraction(int(numerator), int(denominator))),
            trigger_ref=instance.instance_id,
            ordering_key=(projection.actor_ref, instance.instance_id),
            expected_revision_vector=((stream_id, projection.source_revision_vector.get(stream_id, 0)),),
            owner_contract_ref="status_tag_authority.expiration",
            time_pins=tuple(sorted({
                "timeline_id": instance.expiry.timeline_id,
                "profile_revision": instance.expiry.profile_revision,
                "mapping_id": instance.expiry.mapping_id,
                "mapping_revision": instance.expiry.mapping_revision,
                "source_revision": instance.expiry.source_revision,
                "freshness": instance.expiry.evidence_freshness,
            }.items())),
        )

    def submit_expiration_request(self, work: ScheduledWork, *, temporal: StatusTagTemporalContext) -> StatusTagAuthorityResult:
        if work.owner_contract_ref != "status_tag_authority.expiration" or work.domain_ref != "status_tags":
            raise ValueError("status_tag_expiration_owner_mismatch")
        actor_ref, instance_id = work.ordering_key
        stream_id = f"gameplay:status_tags:{actor_ref}"
        expected_revision = dict(work.expected_revision_vector).get(stream_id)
        if expected_revision is None:
            raise ValueError("status_tag_expiration_revision_missing")
        digest = "sha256:" + sha256(json.dumps(asdict(work), sort_keys=True, default=str).encode()).hexdigest()
        receipt_key = f"{actor_ref}:{work.work_ref}"
        existing = self._store.get_idempotency_record(self._PRINCIPAL, receipt_key)
        if existing is not None:
            if existing.payload_digest != digest:
                raise ValueError("idempotency_key_reused")
            projection = self._projector.rebuild(actor_ref, self._store.read_stream(stream_id))
            original = self._store.get_by_idempotency(self._PRINCIPAL, receipt_key)
            if original is None or not original.committed or len(original.committed_event_ids) != 1:
                raise ValueError("idempotency_receipt_invalid")
            try:
                event = self._store.get_event(original.committed_event_ids[0])
            except KeyError as exc:
                raise ValueError("idempotency_receipt_invalid") from exc
            if event.stream_id != stream_id or event.command_id != work.work_ref or event.event_type != "gameplay.status_tag.expired":
                raise ValueError("idempotency_key_reused")
            return StatusTagAuthorityResult(True, None, projection, original)
        projection = self._projector.rebuild(actor_ref, self._store.read_stream(stream_id))
        instance = projection.active_instances.get(instance_id)
        if instance is None or instance.expiry is None:
            raise ValueError("status_tag_instance_not_active")
        temporal.validate_expiry(instance.expiry)
        if self._expiration_work(projection, instance) != work:
            # Revision remains a conflict; all other frozen inputs must also match.
            if dict(work.expected_revision_vector).get(stream_id) == self._store.get_stream_head(stream_id):
                raise ValueError("status_tag_expiration_work_changed")
        if self._store.get_stream_head(stream_id) != expected_revision:
            raise ValueError("status_tag_revision_stale")
        command = StatusTagCommand(
            command_id=work.work_ref, actor_ref=actor_ref, authority_principal=self._authority_principal,
            idempotency_key=work.work_ref, payload_digest=digest, causation_id=work.trigger_ref,
            correlation_id=work.work_ref, operation="expire", tag_id=instance.tag_id,
            source_ref="status-expiration", instance_id=instance_id, expiry=instance.expiry,
        )
        return self.apply(command, temporal=temporal)

    def _event_for(self, command: StatusTagCommand, definition: StatusTagDefinition, projection: StatusTagStateProjection, *, expiry: StatusTagExpiry | None) -> tuple[str, dict[str, object], str | None]:
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
            payload = {**base, "source_ref": command.source_ref, "stack_count": 1}
            if expiry is not None:
                payload["expiry"] = expiry.model_dump(mode="json")
            return "gameplay.status_tag.applied", payload, None
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
    def encode(item: object) -> object:
        if isinstance(item, StatusTagInstance):
            return item.__dict__
        if isinstance(item, Fraction):
            return str(item)
        if hasattr(item, "__dict__"):
            return item.__dict__
        return str(item)

    return sha256(json.dumps(value, default=encode, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _request_fingerprint(command, temporal, duration):
    value = {"command": command.model_dump(mode="json"), "expires_after_steps": duration}
    if temporal is not None:
        # Expiration retries can occur later; their frozen expiry remains unchanged.
        value["temporal"] = (asdict(temporal) if command.operation == "apply" else {
            "mapping": asdict(temporal.mapping), "profile_revision": temporal.profile_revision,
            "source_revision": temporal.source_revision,
        })
    return sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def _temporal_context_digest_value(context: StatusTagTemporalContext) -> dict[str, object]:
    return {
        "now": {
            "timeline_id": context.now.timeline_id,
            "step_index": context.now.step_index,
            "canonical_time_value": str(context.now.canonical_time_value),
        },
        "mapping": asdict(context.mapping),
        "profile_revision": context.profile_revision,
        "source_revision": context.source_revision,
        "evidence_freshness": context.evidence_freshness,
        "step_duration": str(context.step_duration),
    }
