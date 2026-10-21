from __future__ import annotations

import json
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter, model_validator

from app.gameplay.event_schema_registry import EventSchemaRegistration, EventSchemaRegistry, EventSchemaRegistryError
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import ProjectionCheckpoint
from app.gameplay.replay import GameplayProjectionReplay
from .simulation_contracts import (
    CharacterSimulationFrame, FrozenPolicyPins, FrozenRevisionVector, IntersectionPacket, ModuleDefinition, SimulationContract, simulation_digest,
)


class MemberEntry(SimulationContract):
    actor_ref: str = Field(pattern=r"^character:.+$")
    entry_character_revision: int = Field(ge=0)
    participation_policy_pins: FrozenPolicyPins = Field(min_length=1)
    shard_ref: str = Field(default="unpartitioned", min_length=1)
    aggregatable_field_refs: tuple[str, ...] = ()
    protected_field_refs: tuple[str, ...] = ()
    protected_code_refs: tuple[str, ...] = ()
    last_consumed_result_cursor: int = Field(default=0, ge=0)
    lifecycle: Literal["active", "handoff", "excluded", "exited"] = "active"

    @model_validator(mode="after")
    def validate_references(self):
        if any(not ref or not revision for ref, revision in self.participation_policy_pins.items()):
            raise ValueError("member_policy_pin_invalid")
        for name in ("aggregatable_field_refs", "protected_field_refs", "protected_code_refs"):
            values = getattr(self, name)
            if any(not value for value in values) or len(values) != len(set(values)):
                raise ValueError("member_references_invalid")
            object.__setattr__(self, name, tuple(sorted(values)))
        if set(self.aggregatable_field_refs).intersection(self.protected_field_refs):
            raise ValueError("member_protected_field_aggregation_denied")
        return self


class ConfirmedMemberResult(SimulationContract):
    actor_ref: str = Field(pattern=r"^character:.+$")
    result_ref: str = Field(min_length=1)
    source_cursor: int = Field(ge=1)
    source_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_revision_vector: FrozenRevisionVector = Field(min_length=1)
    consumed_core_receipt_ref: str | None = Field(default=None, min_length=1)
    consumed_core_revision: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_consumption(self):
        if (self.consumed_core_receipt_ref is None) != (self.consumed_core_revision is None):
            raise ValueError("member_consumption_credential_incomplete")
        return self


class PopulationMemberLedger(SimulationContract):
    schema_revision: Literal["population-member-ledger@1"] = "population-member-ledger@1"
    cohort_ref: str = Field(min_length=1)
    member_source_ref: str = Field(min_length=1)
    member_source_revision: str = Field(min_length=1)
    situation_revision: str = Field(min_length=1)
    ruleset_revision: str = Field(min_length=1)
    partition_revision: str = Field(min_length=1)
    distribution_policy: Literal["none"] = "none"
    seed: str = Field(min_length=1)
    group_cursor: int = Field(default=0, ge=0)
    group_checkpoint_ref: None = None
    member_entries: tuple[MemberEntry, ...] = Field(min_length=1)
    confirmed_results: tuple[ConfirmedMemberResult, ...] = ()
    receipt_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_members(self):
        actors = {entry.actor_ref for entry in self.member_entries}
        if len(actors) != len(self.member_entries):
            raise ValueError("member_actor_duplicate")
        if self.group_cursor != 0:
            raise ValueError("member_group_protocol_unavailable")
        refs = {item.result_ref for item in self.confirmed_results}
        cursors = {item.source_cursor for item in self.confirmed_results}
        if len(refs) != len(self.confirmed_results) or len(cursors) != len(self.confirmed_results):
            raise ValueError("member_result_duplicate")
        if any(item.actor_ref not in actors for item in self.confirmed_results):
            raise ValueError("member_result_actor_unknown")
        ordered = tuple(sorted(self.confirmed_results, key=lambda item: item.source_cursor))
        for entry in self.member_entries:
            consumed_cursor = 0
            pending_seen = False
            for item in ordered:
                if item.actor_ref != entry.actor_ref:
                    continue
                if item.consumed_core_receipt_ref is None:
                    pending_seen = True
                elif pending_seen:
                    raise ValueError("member_consumption_out_of_order")
                else:
                    consumed_cursor = item.source_cursor
                    if item.consumed_core_revision <= entry.entry_character_revision:
                        raise ValueError("member_core_revision_stale")
            if entry.last_consumed_result_cursor != consumed_cursor:
                raise ValueError("member_consumption_cursor_mismatch")
        object.__setattr__(self, "member_entries", tuple(sorted(self.member_entries, key=lambda item: item.actor_ref)))
        object.__setattr__(self, "confirmed_results", ordered)
        refs = tuple(sorted({item.result_ref for item in ordered} |
                            {item.consumed_core_receipt_ref for item in ordered if item.consumed_core_receipt_ref}))
        if self.receipt_refs and self.receipt_refs != refs:
            raise ValueError("member_receipt_refs_mismatch")
        object.__setattr__(self, "receipt_refs", refs)
        return self


class MemberLedgerRecord(SimulationContract):
    kind: Literal["init"] = "init"
    world_ref: str = Field(min_length=1)
    request_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    ledger: PopulationMemberLedger


class MemberReentryRecord(SimulationContract):
    kind: Literal["reentry"] = "reentry"
    world_ref: str = Field(min_length=1)
    request_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_cohort_ref: str = Field(min_length=1)
    source_revision_vector: FrozenRevisionVector = Field(min_length=1)
    returning_actor_ref: str = Field(pattern=r"^character:.+$")
    ledger: PopulationMemberLedger


class MemberResultRecord(SimulationContract):
    kind: Literal["member"] = "member"
    world_ref: str = Field(min_length=1)
    cohort_ref: str = Field(min_length=1)
    request_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    member: MemberEntry
    confirmed_results: tuple[ConfirmedMemberResult, ...]

    @model_validator(mode="after")
    def validate_actor(self):
        if any(item.actor_ref != self.member.actor_ref for item in self.confirmed_results):
            raise ValueError("member_result_actor_mismatch")
        return self


class MemberHandoffRecord(MemberResultRecord):
    kind: Literal["handoff"] = "handoff"
    intersection: IntersectionPacket

    @model_validator(mode="after")
    def validate_intersection(self):
        if (self.member.lifecycle != "handoff" or self.intersection.actor_ref != self.member.actor_ref
                or self.intersection.group_ref != self.cohort_ref):
            raise ValueError("member_handoff_scope_mismatch")
        return self


_RECORD = TypeAdapter(Annotated[MemberLedgerRecord | MemberResultRecord, Field(discriminator="kind")])
_HANDOFF_RECORD = TypeAdapter(MemberHandoffRecord)
MEMBER_LEDGER_EVENT = "population.world.member_ledger_recorded@1"
MEMBER_LEDGER_EVENT_SCHEMA = EventSchemaRegistration(MEMBER_LEDGER_EVENT, 1,
    simulation_digest(_RECORD.json_schema()))
MEMBER_HANDOFF_EVENT = "population.world.member_handoff_recorded@1"
MEMBER_HANDOFF_EVENT_SCHEMA = EventSchemaRegistration(MEMBER_HANDOFF_EVENT, 1,
    simulation_digest(_HANDOFF_RECORD.json_schema()))
MEMBER_REENTRY_EVENT = "population.world.member_reentry_recorded@1"
_REENTRY_RECORD = TypeAdapter(MemberReentryRecord)
MEMBER_REENTRY_EVENT_SCHEMA = EventSchemaRegistration(MEMBER_REENTRY_EVENT, 1,
    simulation_digest(_REENTRY_RECORD.json_schema()))
MEMBER_LEDGER_OWNER = "world_runtime.cadence"


def register_population_member_ledger_schemas(registry: EventSchemaRegistry) -> None:
    for schema in (MEMBER_LEDGER_EVENT_SCHEMA, MEMBER_HANDOFF_EVENT_SCHEMA, MEMBER_REENTRY_EVENT_SCHEMA):
        try:
            existing = registry.get(schema.event_type, 1)
        except EventSchemaRegistryError:
            registry.register(schema)
        else:
            if existing != schema:
                raise EventSchemaRegistryError("event_schema_digest_conflict")


def build_member_entry(*, frame: CharacterSimulationFrame,
                       module_definitions: tuple[ModuleDefinition, ...]) -> MemberEntry:
    frame = CharacterSimulationFrame.model_validate(frame)
    participation = frame.participation_resolution
    if participation.status != "resolved" or "B0" not in participation.allowed_tiers:
        raise ValueError("member_b0_participation_denied")
    definitions = {item.module_ref: ModuleDefinition.model_validate(item) for item in module_definitions}
    if len(definitions) != len(module_definitions) or not set(frame.module_states).issubset(definitions):
        raise ValueError("member_module_definition_missing")
    aggregatable, protected = [], []
    for module_ref in sorted(frame.module_states):
        definition = definitions[module_ref]
        if "B0" not in definition.supported_tiers:
            raise ValueError("member_module_b0_denied")
        for name in definition.state_schema.shared_fields:
            field_ref = f"{module_ref}.{name}"
            policy = definition.field_policy(name)
            forbidden = set(participation.forbidden_dimensions).intersection(
                (module_ref, definition.category, name, field_ref))
            allowed = policy.aggregatable and not policy.individual_only and not forbidden
            allowed = allowed and name in definition.state_schema.population_allowed_fields
            (aggregatable if allowed else protected).append(field_ref)
    return MemberEntry(actor_ref=frame.actor_ref, entry_character_revision=frame.character_core_revision,
        participation_policy_pins=participation.source_policy_pins, protected_code_refs=frame.codebook_refs,
        aggregatable_field_refs=tuple(aggregatable), protected_field_refs=tuple(protected))


def partition_members(ledger: PopulationMemberLedger, *, seed: str,
                      partition_revision: str) -> PopulationMemberLedger:
    ledger = PopulationMemberLedger.model_validate(ledger)
    if ledger.confirmed_results:
        raise ValueError("member_partition_has_confirmed_results")
    entries = []
    for member in ledger.member_entries:
        # 分片按读取许可归类；不展开保护内容，也不从分片平均值生成个人增量。
        pin = simulation_digest(dict(cohort_ref=ledger.cohort_ref, seed=seed,
            partition_revision=partition_revision, policy_pins=dict(member.participation_policy_pins),
            fields=member.aggregatable_field_refs, protected_fields=member.protected_field_refs,
            lifecycle=member.lifecycle))
        entries.append(MemberEntry.model_validate({**member.model_dump(), "shard_ref": f"shard:{pin[7:]}"}))
    return PopulationMemberLedger.model_validate({**ledger.model_dump(), "seed": seed,
        "partition_revision": partition_revision, "member_entries": tuple(entries)})


def pending_member_results(ledger: PopulationMemberLedger, *, actor_ref: str) -> tuple[str, ...]:
    ledger = PopulationMemberLedger.model_validate(ledger)
    if actor_ref not in {entry.actor_ref for entry in ledger.member_entries}:
        raise ValueError("member_actor_unknown")
    return tuple(item.result_ref for item in ledger.confirmed_results
                 if item.actor_ref == actor_ref and item.consumed_core_receipt_ref is None)


def actor_result_source(store: GameplayEventStore, *, actor_ref: str, result_ref: str):
    """首期仅读取原 Organization 明确收件人的班表确认，不把组织总量映射到个人。"""
    try:
        event = store.get_event(result_ref)
    except KeyError as exc:
        raise ValueError("member_result_unavailable") from exc
    transaction = store.get_transaction(event.transaction_id)
    if (event.event_type != "gameplay.organization.membership_recorded" or event.schema_version != 1
            or transaction is None
            or transaction.idempotency_record.principal_ref != "actor_gameplay.organization_domain"
            or event.stream_id != f"gameplay:organization:{event.payload.get('organization_ref')}"):
        raise ValueError("member_result_attribution_unknown")
    if event.payload.get("recipient_ref") != actor_ref:
        raise ValueError("member_result_actor_mismatch")
    result = store.get_by_idempotency(transaction.idempotency_record.principal_ref,
                                      transaction.idempotency_record.idempotency_key)
    if result is None or not result.committed or event.event_id not in result.committed_event_ids:
        raise ValueError("member_result_unconfirmed")
    return event, result


def parse_member_record(store: GameplayEventStore, event):
    transaction = store.get_transaction(event.transaction_id)
    if (event.event_type not in {MEMBER_LEDGER_EVENT, MEMBER_HANDOFF_EVENT, MEMBER_REENTRY_EVENT} or event.schema_version != 1
            or event.visibility_policy != "authority_only" or transaction is None
            or transaction.idempotency_record.principal_ref != MEMBER_LEDGER_OWNER):
        raise ValueError("member_ledger_source_invalid")
    adapter = (_REENTRY_RECORD if event.event_type == MEMBER_REENTRY_EVENT else
               _HANDOFF_RECORD if event.event_type == MEMBER_HANDOFF_EVENT else _RECORD)
    return adapter.validate_json(json.dumps(event.payload, allow_nan=False))


def member_ledger_replay(stream: str) -> GameplayProjectionReplay:
    registry = EventSchemaRegistry()
    register_population_member_ledger_schemas(registry)
    return GameplayProjectionReplay(projector_id=f"population-member-ledger:{stream}", projector_version="1",
        supported_event_versions={MEMBER_LEDGER_EVENT: 1, MEMBER_HANDOFF_EVENT: 1, MEMBER_REENTRY_EVENT: 1}, event_schema_registry=registry)


def member_ledger_stream(world_ref: str, cohort_ref: str) -> str:
    # V1 元数据地址绑定完整身份；群组根流不会占用成员子流。
    return f"population:members:v1:{simulation_digest((world_ref, cohort_ref))}"


def member_result_stream(ledger_stream: str, actor_ref: str) -> str:
    return f"{ledger_stream}:member:{simulation_digest(actor_ref)}"


def read_member_ledger_state(store: GameplayEventStore, *, stream: str, world_ref: str,
                             cohort_ref: str, checkpoint: ProjectionCheckpoint | None = None,
                             max_revisions=None):
    roots = store.read_stream(stream)
    if len(roots) != 1:
        raise ValueError("member_ledger_unavailable")
    root = parse_member_record(store, roots[0])
    if not isinstance(root, (MemberLedgerRecord, MemberReentryRecord)) or root.world_ref != world_ref or root.ledger.cohort_ref != cohort_ref:
        raise ValueError("member_ledger_scope_mismatch")
    if isinstance(root, MemberLedgerRecord) and root.ledger.confirmed_results:
        raise ValueError("member_ledger_initial_results_denied")
    if isinstance(root, MemberReentryRecord):
        source_stream = member_ledger_stream(world_ref, root.source_cohort_ref)
        source_roots = store.read_stream(source_stream)
        if (len(source_roots) != 1 or source_roots[0].global_sequence >= roots[0].global_sequence
                or root.source_revision_vector.get(source_stream) != 1):
            raise ValueError("member_reentry_source_invalid")
        source, _, _ = read_member_ledger_state(store, stream=source_stream, world_ref=world_ref,
            cohort_ref=root.source_cohort_ref, max_revisions=root.source_revision_vector)
        old = next((item for item in source.member_entries if item.actor_ref == root.returning_actor_ref), None)
        new = next((item for item in root.ledger.member_entries if item.actor_ref == root.returning_actor_ref), None)
        if (old is None or old.lifecycle != "handoff" or new is None or new.lifecycle != "active"
                or new.last_consumed_result_cursor != 0 or new.entry_character_revision < old.entry_character_revision
                or pending_member_results(source, actor_ref=root.returning_actor_ref)
                or new.model_dump(exclude={"lifecycle", "last_consumed_result_cursor", "entry_character_revision",
                    "participation_policy_pins", "shard_ref"}) != old.model_dump(exclude={"lifecycle",
                    "last_consumed_result_cursor", "entry_character_revision", "participation_policy_pins", "shard_ref"})
                or tuple(item for item in root.ledger.member_entries if item.actor_ref != root.returning_actor_ref)
                    != tuple(item for item in source.member_entries if item.actor_ref != root.returning_actor_ref)
                or root.ledger.confirmed_results != tuple(item for item in source.confirmed_results
                    if item.actor_ref != root.returning_actor_ref)
                or root.ledger.model_dump(exclude={"cohort_ref", "member_entries", "confirmed_results", "receipt_refs"})
                    != source.model_dump(exclude={"cohort_ref", "member_entries", "confirmed_results", "receipt_refs"})):
            raise ValueError("member_reentry_source_invalid")
    events = list(roots)
    for member in root.ledger.member_entries:
        actor_stream = member_result_stream(stream, member.actor_ref)
        events.extend(store.read_stream(actor_stream, to_revision=max_revisions.get(actor_stream, 0))
            if max_revisions is not None and max_revisions.get(actor_stream, 0) else
            (() if max_revisions is not None else store.read_stream(actor_stream)))
    events.sort(key=lambda item: item.global_sequence)
    replay = member_ledger_replay(stream)
    if checkpoint is None:
        result = replay.full_replay(events)
    else:
        prefix = [event for event in events if event.global_sequence <= checkpoint.last_global_sequence]
        vector = {event.stream_id: event.stream_revision for event in prefix}
        state = {}
        for event in prefix:
            state[event.stream_id] = dict(last_event_id=event.event_id, last_event_type=event.event_type,
                last_payload=event.payload, event_count=event.stream_revision)
        if (not prefix or checkpoint.last_global_sequence != prefix[-1].global_sequence
                or checkpoint.source_revision_vector != vector or checkpoint.state != state
                or checkpoint.applied_event_ids != sorted(event.event_id for event in prefix)):
            raise ValueError("member_checkpoint_invalid")
        result = replay.checkpoint_plus_tail_replay(checkpoint,
            [event for event in events if event.global_sequence > checkpoint.last_global_sequence])
    if not result.succeeded:
        raise ValueError("member_checkpoint_invalid" if checkpoint is not None else "member_ledger_replay_invalid")
    entries, confirmed = [], []
    for initial in root.ledger.member_entries:
        actor_stream = member_result_stream(stream, initial.actor_ref)
        head = result.state.get(actor_stream)
        if head is None:
            entries.append(initial)
            confirmed.extend(item for item in root.ledger.confirmed_results if item.actor_ref == initial.actor_ref)
            continue
        event = store.get_event(head["last_event_id"])
        record = parse_member_record(store, event)
        if (not isinstance(record, MemberResultRecord) or record.world_ref != world_ref
                or record.cohort_ref != cohort_ref or record.member.actor_ref != initial.actor_ref
                or record.member.model_dump(exclude={"last_consumed_result_cursor", "lifecycle"})
                != initial.model_dump(exclude={"last_consumed_result_cursor", "lifecycle"})):
            raise ValueError("member_ledger_scope_mismatch")
        entries.append(record.member)
        confirmed.extend(record.confirmed_results)
    ledger = PopulationMemberLedger.model_validate({**root.ledger.model_dump(),
        "member_entries": tuple(entries), "confirmed_results": tuple(confirmed), "receipt_refs": ()})
    for item in ledger.confirmed_results:
        event, owner_receipt = actor_result_source(store, actor_ref=item.actor_ref, result_ref=item.result_ref)
        if (event.global_sequence != item.source_cursor or simulation_digest(event.model_dump(mode="json")) != item.source_digest
                or dict(item.source_revision_vector) != owner_receipt.resulting_stream_revisions):
            raise ValueError("member_result_source_mismatch")
    return ledger, result.source_revision_vector, events
