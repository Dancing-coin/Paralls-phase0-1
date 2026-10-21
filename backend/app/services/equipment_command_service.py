"""Production Equipment admission, designed and implemented in stage three.

Transport supplies intent and a connection reference, never a Body projection.
The existing controller binding authorizes own-custody loadout changes only.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Callable, Literal

from pydantic import Field, model_validator

from app.gameplay.equipment_runtime import EquipmentAuthorityService, EquipmentRuntimeError
from app.gameplay.models import StrictGameplayModel
from app.gameplay.resource_body_runtime import ResourceBodyRuntimeProjector
from app.services.embodied_controller_auth_service import EmbodiedControllerAuthService


@dataclass(frozen=True)
class EquipmentWorldScope:
    world_ref: str
    timeline_ref: str


@dataclass(frozen=True)
class EquipmentContentSource:
    """Immutable pin read through the application's registered content loader."""

    revision: str
    digest: str

    def __post_init__(self):
        if not self.revision or not re.fullmatch(r"sha256:[0-9a-f]{64}", self.digest):
            raise ValueError("equipment_content_pin_invalid")


class EquipmentCommand(StrictGameplayModel):
    command_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    world_ref: str = Field(min_length=1)
    timeline_ref: str = Field(min_length=1)
    incarnation: int = Field(ge=1, strict=True)
    operation: Literal["equip", "unequip"]
    item_id: str = ""
    container_id: str = Field(min_length=1)
    slot_key: str = ""
    activation_id: str = ""
    idempotency_key: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    content_revision: str = ""
    content_digest: str = ""

    @model_validator(mode="after")
    def validate_operation(self):
        if (self.operation == "equip" and (not self.item_id or not self.slot_key or self.activation_id)
                or self.operation == "unequip" and (not self.activation_id or self.item_id or self.slot_key)):
            raise ValueError("equipment_command_shape_invalid")
        if self.actor_id.startswith("character:"):
            raise ValueError("equipment_actor_id_required")
        if bool(self.content_revision) != bool(self.content_digest):
            raise ValueError("equipment_content_pin_incomplete")
        return self

    @property
    def actor_ref(self) -> str:
        return self.actor_id

    @property
    def character_ref(self) -> str:
        return f"character:{self.actor_id}"


class _AdmissionStoreView:
    """Delegates to one existing store and adds atomic read pins to its append."""

    def __init__(self, store, *, actor_ref, pins, metadata_pins, revalidate):
        self._source = store
        self._actor_ref = actor_ref
        self._pins = pins
        self._metadata_pins = metadata_pins
        self._revalidate = revalidate

    def __getattr__(self, name):
        return getattr(self._source, name)

    def read_events(self, **kwargs):
        # The legacy Equipment projector requires actor-scoped input.
        return [event for event in self._source.read_events(**kwargs)
                if event.payload.get("actor_ref") == self._actor_ref]

    def append_batch(self, batch):
        candidate = dict(batch)
        record = candidate["idempotency_record"]
        principal = record.principal_ref if hasattr(record, "principal_ref") else record["principal_ref"]
        # The existing resource bridge performs its own source-transaction
        # recovery. Equipment's pre-commit pins must not invalidate that later
        # phase after Equipment has already advanced its own streams.
        if principal != "actor_gameplay.equipment_domain":
            self._revalidate()
            return self._source.append_batch(batch)
        self._revalidate()
        reads = dict(candidate.get("read_stream_revisions", {}))
        for stream, revision in self._pins.items():
            if stream in reads and reads[stream] != revision:
                raise EquipmentRuntimeError("equipment_source_revision_conflict")
            reads[stream] = revision
        candidate["read_stream_revisions"] = reads
        candidate["pinned_revisions"] = {
            **candidate.get("pinned_revisions", {}), **self._pins, **self._metadata_pins}
        return self._source.append_batch(candidate)


class EquipmentCommandService:
    """Own-controller policy v1; source owners and the ledger remain unchanged.

    ``scope_resolver`` must read the application's existing Population driver;
    it is not a client-provided world/timeline assertion. Registered content is
    injected by application composition, never synthesized by this service.
    """

    def __init__(self, *, store, controller_auth: EmbodiedControllerAuthService,
                 scope_resolver: Callable[[], EquipmentWorldScope | None],
                 inventory_registry, equipment_registry, ability_registry,
                 modifier_registry, slots, resource_modifier_mappings=None,
                 content_source: Callable[[], EquipmentContentSource] | None = None,
                 admitted_content: EquipmentContentSource | None = None):
        self.store = store
        self.auth = controller_auth
        self.scope_resolver = scope_resolver
        self.content_source = content_source
        if admitted_content is not None and content_source is None:
            raise ValueError("equipment_content_loader_required")
        # Composition must admit the same exact bytes used to populate the
        # registries. A live loader cannot silently rotate those definitions.
        self.admitted_content = admitted_content or (
            self._read_content_source() if content_source is not None else None)
        self._owner_arguments = dict(
            inventory_registry=inventory_registry, equipment_registry=equipment_registry,
            ability_registry=ability_registry, modifier_registry=modifier_registry,
            slots=tuple(slots), resource_modifier_mappings=resource_modifier_mappings,
        )

    def submit(self, command: EquipmentCommand, *, connection_ref: str):
        # Freeze the caller's complete intent; mutable transport objects cannot
        # change operation identity between admission and append.
        command = EquipmentCommand.model_validate(command.model_dump())
        existing = self._existing(command)
        existing_command = existing.command_id if existing is not None else None
        content_pin = None
        metadata_pins = {}
        if self.content_source is not None:
            if existing is not None:
                content_pin = self._receipt_content_pin(existing)
                if command.content_revision or command.content_digest:
                    requested_pin = EquipmentContentSource(command.content_revision, command.content_digest)
                    if requested_pin != content_pin:
                        raise EquipmentRuntimeError("equipment_content_pin_mismatch")
            else:
                content_pin = self._read_content_source()
                if content_pin != self.admitted_content:
                    raise EquipmentRuntimeError("equipment_content_source_changed")
                if command.content_revision or command.content_digest:
                    requested_pin = EquipmentContentSource(command.content_revision, command.content_digest)
                    if requested_pin != content_pin:
                        raise EquipmentRuntimeError("equipment_content_source_changed")
            if existing is not None and self._intent_pin(command) not in existing.pinned_revisions:
                raise EquipmentRuntimeError("idempotency_key_reused")
            command = command.model_copy(update={"content_revision": content_pin.revision,
                                                  "content_digest": content_pin.digest})
            metadata_pins = self._content_metadata_pins(content_pin, command)
            if existing is not None and existing.command_id != self._command_id(command):
                raise EquipmentRuntimeError("idempotency_key_reused")
        elif existing is not None and existing.command_id != self._command_id(command):
            raise EquipmentRuntimeError("idempotency_key_reused")
        binding = self._binding(command, connection_ref)
        binding_pin = binding.model_dump()
        self._scope(command)
        presence_stream = f"presence:{command.world_ref}"
        activation_stream = f"population:{command.world_ref}"
        life_stream = f"gameplay:character:life:{command.character_ref}"
        body_stream = f"gameplay:body:{command.actor_ref}"
        pins = {stream: self.store.get_stream_head(stream) for stream in (
            presence_stream, activation_stream, life_stream, body_stream,
            f"gameplay:inventory:{command.actor_ref}", f"gameplay:equipment:{command.actor_ref}",
        )}
        self._presence(command, presence_stream, activation_stream, life_stream)
        body = ResourceBodyRuntimeProjector().rebuild_body(
            command.actor_ref, self.store.read_stream(body_stream))

        def revalidate(*, before_append=True):
            if self._binding(command, connection_ref).model_dump() != binding_pin:
                raise EquipmentRuntimeError("equipment_controller_binding_changed")
            self._scope(command)
            if before_append and self.content_source is not None:
                current = self._read_content_source()
                if current != content_pin:
                    raise EquipmentRuntimeError("equipment_content_source_changed")

        view = _AdmissionStoreView(self.store, actor_ref=command.actor_ref,
                                   pins=pins, metadata_pins=metadata_pins,
                                   revalidate=revalidate)
        owner = EquipmentAuthorityService(store=view, **self._owner_arguments)
        arguments = dict(command_id=existing_command or self._command_id(command),
                         actor_ref=command.actor_ref, body=body,
                         idempotency_key=f"production:v1:{command.idempotency_key}",
                         causation_id=command.causation_id, correlation_id=command.correlation_id)
        revalidate(before_append=False)
        if command.operation == "equip":
            result = owner.equip(**arguments, item_id=command.item_id,
                                 source_container_id=command.container_id, slot_key=command.slot_key)
        else:
            result = owner.unequip(**arguments, activation_id=command.activation_id,
                                   destination_container_id=command.container_id)
        if result.committed:
            self._receipt(result, command, arguments["command_id"])
        return result

    @staticmethod
    def _command_id(command):
        payload = command.model_dump()
        if not command.content_revision:
            payload.pop("content_revision", None)
            payload.pop("content_digest", None)
        identity = sha256(json.dumps(payload, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()
        return f"equipment-command:v1:{identity}"

    def _read_content_source(self):
        source = self.content_source()
        if not isinstance(source, EquipmentContentSource):
            raise EquipmentRuntimeError("equipment_content_source_invalid")
        return source

    def _existing(self, command):
        key = f"{command.actor_ref}:production:v1:{command.idempotency_key}"
        record = self.store.get_idempotency_record("actor_gameplay.equipment_domain", key)
        if record is None:
            return None
        prior = self.store.get_by_idempotency("actor_gameplay.equipment_domain", key)
        if prior is None:
            raise EquipmentRuntimeError("equipment_idempotency_missing_result")
        batch = self.store.get_transaction(prior.transaction_id)
        if batch is None:
            raise EquipmentRuntimeError("equipment_idempotency_missing_result")
        return batch

    @staticmethod
    def _intent_pin(command):
        payload = command.model_dump(exclude={"content_revision", "content_digest"})
        digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return f"equipment-intent:sha256:{digest}"

    @classmethod
    def _content_metadata_pins(cls, pin, command):
        return {
            f"equipment-content-revision:{pin.revision}": 1,
            f"equipment-content-digest:{pin.digest}": 1,
            cls._intent_pin(command): 1,
        }

    @staticmethod
    def _receipt_content_pin(batch):
        revisions = [key.removeprefix("equipment-content-revision:")
                     for key, value in batch.pinned_revisions.items()
                     if key.startswith("equipment-content-revision:") and value == 1]
        digests = [key.removeprefix("equipment-content-digest:")
                   for key, value in batch.pinned_revisions.items()
                   if key.startswith("equipment-content-digest:") and value == 1]
        if len(revisions) != 1 or len(digests) != 1:
            raise EquipmentRuntimeError("equipment_admission_receipt_invalid")
        return EquipmentContentSource(revisions[0], digests[0])

    def _receipt(self, result, command, command_id):
        invalid = "equipment_admission_receipt_invalid"
        batch = self.store.get_transaction(result.transaction_id)
        if (batch is None or batch.command_id != command_id or result.command_id != command_id
                or batch.idempotency_record.principal_ref != "actor_gameplay.equipment_domain"
                or batch.idempotency_record.idempotency_key != f"{command.actor_ref}:production:v1:{command.idempotency_key}"
                or tuple(result.committed_event_ids) != tuple(event.event_id for event in batch.events)):
            raise EquipmentRuntimeError(invalid)
        if self.content_source is not None:
            try:
                pin = self._receipt_content_pin(batch)
            except (ValueError, EquipmentRuntimeError) as exc:
                raise EquipmentRuntimeError(invalid) from exc
            if (pin.revision != command.content_revision or pin.digest != command.content_digest
                    or self._intent_pin(command) not in batch.pinned_revisions):
                raise EquipmentRuntimeError(invalid)
        events = batch.events
        revisions = {}
        raw = []
        for index, event in enumerate(events):
            if (event != self.store.get_event(event.event_id) or event.schema_version != 1
                    or event.global_sequence != events[0].global_sequence + index
                    or event.payload.get("actor_ref") != command.actor_ref
                    or event.command_id != command_id or event.transaction_id != batch.transaction_id
                    or event.causation_id != command.causation_id or event.correlation_id != command.correlation_id
                    or event.visibility_policy != "authority_only"
                    or event.stream_revision != revisions.get(event.stream_id,
                        batch.expected_stream_revisions.get(event.stream_id, -1)) + 1):
                raise EquipmentRuntimeError(invalid)
            revisions[event.stream_id] = event.stream_revision
            raw.append(event.model_copy(update={"stream_revision": 0, "global_sequence": 0}).model_dump())
        digest = sha256(json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if (not events or batch.result_digest != digest
                or result.global_sequence_range != (events[0].global_sequence, events[-1].global_sequence)
                or result.resulting_stream_revisions != revisions
                or not {f"presence:{command.world_ref}", f"population:{command.world_ref}",
                        f"gameplay:character:life:{command.character_ref}", f"gameplay:body:{command.actor_ref}"}
                        .issubset(batch.read_stream_revisions)):
            raise EquipmentRuntimeError(invalid)

    def _binding(self, command, connection_ref):
        result = self.auth.resolve_controller_binding(actor_id=command.actor_id,
                                                       connection_ref=connection_ref)
        if not result.accepted or result.binding is None:
            raise EquipmentRuntimeError(result.error_code or "equipment_controller_required")
        return result.binding

    def _scope(self, command):
        scope = self.scope_resolver()
        if (scope is None or not scope.world_ref or not scope.timeline_ref
                or scope.world_ref != command.world_ref or scope.timeline_ref != command.timeline_ref):
            raise EquipmentRuntimeError("equipment_world_timeline_mismatch")

    def _owned(self, event, principal):
        batch = self.store.get_transaction(event.transaction_id)
        return bool(batch is not None and batch.idempotency_record.principal_ref == principal
                    and any(candidate == event for candidate in batch.events)
                    and self.store.transaction_owns_event(transaction_id=event.transaction_id,
                                                         event_id=event.event_id, principal_ref=principal))

    def _presence(self, command, presence_stream, activation_stream, life_stream):
        events = [event for event in self.store.read_stream(presence_stream)
                  if event.payload.get("character_ref") == command.character_ref]
        if not events:
            raise EquipmentRuntimeError("equipment_presence_required")
        presence = events[-1]
        if (presence.event_type != "population.presence.spawned"
                or presence.payload.get("incarnation") != command.incarnation
                or presence.payload.get("world_ref") != command.world_ref
                or not self._owned(presence, "population.presence_authority")):
            raise EquipmentRuntimeError("equipment_presence_invalid")
        activation = [event for event in self.store.read_stream(activation_stream)
                      if event.payload.get("profile_ref") == command.character_ref
                      and event.event_type.startswith("population.activation.")]
        if not activation or activation[-1].event_type != "population.activation.committed":
            raise EquipmentRuntimeError("equipment_activation_inactive")
        source = activation[-1]
        batch = self.store.get_transaction(source.transaction_id)
        principal = batch.idempotency_record.principal_ref if batch else ""
        if (presence.payload.get("source_activation_event_id") != source.event_id
                or source.payload.get("world_ref") != command.world_ref
                or not principal.startswith(("population:", "world_runtime."))
                or not self._owned(source, principal)):
            raise EquipmentRuntimeError("equipment_activation_invalid")
        life = self.store.read_stream(life_stream, event_type="gameplay.character.life_state_changed")
        if (not life or life[-1].payload.get("to_state") != "alive"
                or life[-1].payload.get("world_ref") != command.world_ref
                or life[-1].payload.get("incarnation") != command.incarnation
                or not self._owned(life[-1], "authority:character:life-state:presence-admission")):
            raise EquipmentRuntimeError("equipment_alive_required")


__all__ = ["EquipmentCommand", "EquipmentCommandService", "EquipmentContentSource", "EquipmentWorldScope"]
