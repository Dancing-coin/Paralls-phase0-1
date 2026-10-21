"""Production equipment preview/confirmation ingress.

The preview is a durable, actor-scoped overlay.  EquipmentCommandService is
still the only owner allowed to append equipment truth; PredictionAuthority
only records the provisional lifecycle and the owner receipt reference.
"""
from __future__ import annotations

from dataclasses import dataclass
from copy import copy
from hashlib import sha256
import json

from app.gameplay.equipment_runtime import EquipmentRuntimeError
from app.gameplay.prediction_authority import PredictionAuthority
from app.services.equipment_command_service import EquipmentCommand, EquipmentCommandService


@dataclass(frozen=True)
class EquipmentPredictionResult:
    prediction: object
    owner: object | None = None
    confirmation: object | None = None


class _PreviewReadStore:
    """Inject the frozen preview read-set into the existing owner append."""

    def __init__(self, store, *, pins, revalidate):
        self._store = store
        self._pins = pins
        self._revalidate = revalidate

    def __getattr__(self, name):
        return getattr(self._store, name)

    def append_batch(self, batch):
        candidate = dict(batch)
        record = candidate["idempotency_record"]
        principal = record.principal_ref if hasattr(record, "principal_ref") else record["principal_ref"]
        if principal == "actor_gameplay.equipment_domain":
            self._revalidate()
            reads = dict(candidate.get("read_stream_revisions", {}))
            for stream, revision in self._pins.items():
                if stream in reads and reads[stream] != revision:
                    raise EquipmentRuntimeError("equipment_prediction_revision_conflict")
                reads[stream] = revision
            candidate["read_stream_revisions"] = reads
        return self._store.append_batch(candidate)


class EquipmentPredictionService:
    """Typed production caller for equipment overlay -> owner confirmation."""

    def __init__(self, *, equipment: EquipmentCommandService,
                 prediction: PredictionAuthority, now=lambda: 0) -> None:
        if equipment.store is not prediction.store:
            raise ValueError("equipment_prediction_store_mismatch")
        self.equipment = equipment
        self.prediction = prediction
        self.now = now

    @staticmethod
    def _digest(command: EquipmentCommand, *, connection_ref: str, binding=None) -> str:
        payload = {"command": command.model_dump(mode="json"), "connection_ref": connection_ref,
                   "binding": binding.model_dump(mode="json") if binding is not None else None}
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return "sha256:" + sha256(raw).hexdigest()

    def _opened(self, prediction_id):
        events = self.equipment.store.read_stream(f"gameplay:prediction:{prediction_id}")
        self.prediction.state(prediction_id)
        opened = events[0]
        batch = self.equipment.store.get_transaction(opened.transaction_id)
        def digest(value):
            return "sha256:" + sha256(json.dumps(value, sort_keys=True,
                separators=(",", ":"), default=str).encode()).hexdigest()
        if (batch is None or batch.idempotency_record.principal_ref != self.prediction.principal
                or len(batch.events) != 1 or batch.events[0] != opened
                or opened != self.equipment.store.get_event(opened.event_id)
                or batch.command_id != opened.command_id
                or batch.expected_stream_revisions != {opened.stream_id: 0}
                or opened.stream_revision != 1 or opened.visibility_policy != "authority_only"
                or batch.idempotency_record.payload_digest != digest({
                    "event_type": opened.event_type, "payload": opened.payload})
                or batch.result_digest != digest((batch.transaction_id, opened.event_type, opened.payload))
                or not self.equipment.store.transaction_owns_event(
                    transaction_id=opened.transaction_id, event_id=opened.event_id,
                    principal_ref=self.prediction.principal)):
            raise EquipmentRuntimeError("equipment_prediction_receipt_invalid")
        return opened

    def preview(self, command: EquipmentCommand, *, connection_ref: str,
                prediction_id: str, idempotency_key: str,
                ttl: int = 30) -> EquipmentPredictionResult:
        if type(ttl) is not int or ttl < 1:
            raise EquipmentRuntimeError("equipment_prediction_ttl_invalid")
        command = EquipmentCommand.model_validate(command.model_dump())
        # Admission checks are repeated by the owner. This early check gives a
        # caller a zero-write denial and freezes the same trusted binding.
        binding = self.equipment.auth.resolve_controller_binding(
            actor_id=command.actor_id, connection_ref=connection_ref)
        if not binding.accepted or binding.binding is None:
            raise EquipmentRuntimeError(binding.error_code or "equipment_controller_required")
        self.equipment._scope(command)
        self.equipment._presence(
            command, f"presence:{command.world_ref}", f"population:{command.world_ref}",
            f"gameplay:character:life:{command.character_ref}",
        )
        if self.equipment.content_source is not None:
            content_pin = self.equipment._read_content_source()
            if content_pin != self.equipment.admitted_content:
                raise EquipmentRuntimeError("equipment_content_source_changed")
            if command.content_revision or command.content_digest:
                from app.services.equipment_command_service import EquipmentContentSource
                if EquipmentContentSource(command.content_revision, command.content_digest) != content_pin:
                    raise EquipmentRuntimeError("equipment_content_source_changed")
            command = command.model_copy(update={"content_revision": content_pin.revision,
                                                  "content_digest": content_pin.digest})
        command_id = self.equipment._command_id(command)
        # Replays must retain the original operational deadline.  Otherwise a
        # duplicate preview after time advances would mutate the durable
        # opened payload and be rejected as an identity conflict.
        existing_expires_at = None
        existing_revisions = None
        try:
            existing_state = self.prediction.state(prediction_id)
            if existing_state.status != "pending" or existing_state.actor_ref != command.actor_ref:
                raise EquipmentRuntimeError("equipment_prediction_terminal")
            existing_expires_at = existing_state.expires_at
            existing_revisions = self._opened(prediction_id).payload["base_revision_vector"]
        except ValueError as exc:
            if str(exc) != "prediction_not_found":
                raise
        expires_at = existing_expires_at if existing_expires_at is not None else self.now() + ttl
        result = self.prediction.open(
            prediction_id=prediction_id, command_id=command_id,
            actor_ref=command.actor_ref, operation="equipment_overlay",
            idempotency_key=idempotency_key,
            base_revision_vector=existing_revisions if existing_revisions is not None else {
                stream: self.equipment.store.get_stream_head(stream)
                for stream in (f"presence:{command.world_ref}", f"population:{command.world_ref}",
                               f"gameplay:character:life:{command.character_ref}",
                               f"gameplay:body:{command.actor_ref}",
                               f"gameplay:inventory:{command.actor_ref}",
                               f"gameplay:equipment:{command.actor_ref}")
            },
            branch_contract_digest=self._digest(command, connection_ref=connection_ref, binding=binding.binding),
            expires_at=expires_at,
        )
        return EquipmentPredictionResult(prediction=result)

    def confirm(self, command: EquipmentCommand, *, connection_ref: str,
                prediction_id: str, confirm_idempotency_key: str) -> EquipmentPredictionResult:
        command = EquipmentCommand.model_validate(command.model_dump())
        state = self.prediction.state(prediction_id)
        if state.operation != "equipment_overlay" or state.actor_ref != command.actor_ref:
            raise EquipmentRuntimeError("equipment_prediction_identity_mismatch")
        if state.status not in {"pending", "confirmed"}:
            raise EquipmentRuntimeError("equipment_prediction_terminal")
        opened = self._opened(prediction_id)
        owner_key = f"{command.actor_ref}:production:v1:{command.idempotency_key}"
        prior_owner = self.equipment.store.get_by_idempotency(
            "actor_gameplay.equipment_domain", owner_key)
        if self.equipment.content_source is not None:
            if prior_owner is not None:
                owner_batch = self.equipment.store.get_transaction(prior_owner.transaction_id)
                content = self.equipment._receipt_content_pin(owner_batch)
            else:
                content = self.equipment._read_content_source()
            if command.content_revision and (command.content_revision != content.revision
                    or command.content_digest != content.digest):
                raise EquipmentRuntimeError("equipment_prediction_intent_changed")
            command = command.model_copy(update={"content_revision": content.revision,
                                                 "content_digest": content.digest})
        binding = self.equipment.auth.resolve_controller_binding(
            actor_id=command.actor_id, connection_ref=connection_ref)
        if not binding.accepted or binding.binding is None:
            raise EquipmentRuntimeError(binding.error_code or "equipment_controller_required")
        if opened.payload.get("branch_contract_digest") != self._digest(
                command, connection_ref=connection_ref, binding=binding.binding):
            raise EquipmentRuntimeError("equipment_prediction_intent_changed")
        if state.command_id != self.equipment._command_id(command):
            raise EquipmentRuntimeError("equipment_prediction_intent_changed")
        if prior_owner is None and state.expires_at is not None and self.now() > state.expires_at:
            self.prediction.expire(prediction_id=prediction_id,
                                   idempotency_key=f"{confirm_idempotency_key}:expired",
                                   reason="operational_deadline")
            raise EquipmentRuntimeError("equipment_prediction_expired")
        base_revisions = opened.payload.get("base_revision_vector", {})
        if prior_owner is None and any(self.equipment.store.get_stream_head(stream) != revision
               for stream, revision in base_revisions.items()):
            raise EquipmentRuntimeError("equipment_prediction_revision_conflict")
        def revalidate():
            if self.prediction.state(prediction_id).status != "pending":
                raise EquipmentRuntimeError("equipment_prediction_terminal")
            current_binding = self.equipment._binding(command, connection_ref)
            if opened.payload["branch_contract_digest"] != self._digest(
                    command, connection_ref=connection_ref, binding=current_binding):
                raise EquipmentRuntimeError("equipment_prediction_binding_changed")
            if state.expires_at is not None and self.now() > state.expires_at:
                raise EquipmentRuntimeError("equipment_prediction_expired")
        preview_store = _PreviewReadStore(self.equipment.store, pins={
            **base_revisions, opened.stream_id: opened.stream_revision},
            revalidate=revalidate)
        equipment = copy(self.equipment)
        equipment.store = preview_store
        owner = equipment.submit(command, connection_ref=connection_ref)
        if not owner.committed:
            return EquipmentPredictionResult(prediction=self.prediction.state(prediction_id), owner=owner)
        confirmation = self.prediction.confirm(
            prediction_id=prediction_id, idempotency_key=confirm_idempotency_key,
            owner_principal="actor_gameplay.equipment_domain",
            owner_idempotency_key=owner_key,
        )
        return EquipmentPredictionResult(prediction=self.prediction.state(prediction_id), owner=owner,
                                         confirmation=confirmation)

    def expire(self, *, prediction_id: str, actor_id: str, connection_ref: str,
               idempotency_key: str, reason: str = "operational_deadline"):
        binding = self.equipment.auth.resolve_controller_binding(
            actor_id=actor_id, connection_ref=connection_ref)
        if not binding.accepted or binding.binding is None:
            raise EquipmentRuntimeError(binding.error_code or "equipment_controller_required")
        actor_ref = actor_id
        state = self.prediction.state(prediction_id)
        if state.actor_ref != actor_ref:
            raise EquipmentRuntimeError("equipment_prediction_scope_denied")
        self._opened(prediction_id)
        if state.expires_at is None or self.now() <= state.expires_at:
            raise EquipmentRuntimeError("equipment_prediction_not_expired")
        return self.prediction.expire(prediction_id=prediction_id,
                                      idempotency_key=idempotency_key, reason=reason)

    def revoke(self, *, prediction_id: str, actor_id: str, connection_ref: str,
               idempotency_key: str, reason: str = "caller_revoked"):
        """Revoke only through an authenticated actor/controller scope."""
        binding = self.equipment.auth.resolve_controller_binding(
            actor_id=actor_id, connection_ref=connection_ref)
        if not binding.accepted or binding.binding is None:
            raise EquipmentRuntimeError(binding.error_code or "equipment_controller_required")
        actor_ref = actor_id
        state = self.prediction.state(prediction_id)
        if state.actor_ref != actor_ref:
            raise EquipmentRuntimeError("equipment_prediction_scope_denied")
        self._opened(prediction_id)
        return self.prediction.revoke(prediction_id=prediction_id,
                                      idempotency_key=idempotency_key, reason=reason)

    def lookup(self, prediction_id: str, *, actor_id: str, connection_ref: str):
        binding = self.equipment.auth.resolve_controller_binding(
            actor_id=actor_id, connection_ref=connection_ref)
        if not binding.accepted or binding.binding is None:
            raise EquipmentRuntimeError(binding.error_code or "equipment_controller_required")
        actor_ref = actor_id
        state = self.prediction.state(prediction_id)
        if state.actor_ref != actor_ref:
            raise EquipmentRuntimeError("equipment_prediction_scope_denied")
        self._opened(prediction_id)
        return state


__all__ = ["EquipmentPredictionResult", "EquipmentPredictionService"]
