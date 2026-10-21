"""Explicit self-draw command producer, designed and implemented in stage three.

Run inside RuntimeExecution, together with controller binding/revocation. This
service selects results only: it neither awards inventory nor debits money.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from pydantic import BaseModel, ConfigDict, Field

from app.gameplay.event_schema_registry import EventSchemaRegistration
from app.gameplay.settlement_plan import build_multi_stream_atomic_event_batch
from app.gameplay.shared_contracts import SettlementReceipt


ECONOMY_RANDOM_COMMAND_SCHEMAS = (
    EventSchemaRegistration("economy.random.command.requested@1", 1,
                            "sha256:economy-random-explicit-command-v1"),
)


class EconomyRandomCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    request_id: str = Field(min_length=1, max_length=128)
    actor_ref: str = Field(min_length=1)
    policy_ref: str = Field(min_length=1)
    world_ref: str = Field(min_length=1)
    timeline_ref: str = Field(min_length=1)
    world_tick: int = Field(ge=0)


@dataclass(frozen=True)
class EconomyRandomCommandResult:
    operation_ref: str
    trigger_receipt: SettlementReceipt
    economy_receipt: SettlementReceipt
    candidate_ref: str
    result_ref: str


def _digest(value) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class EconomyRandomCommandService:
    """Uses existing controller identity, Population admission and Economy owner."""
    PRINCIPAL = "service:economy-random-command"

    def __init__(self, *, store, controller_auth, caller):
        if caller.store is not store or caller.authority._store is not store:
            raise ValueError("economy_random_command_store_mismatch")
        self.store = store
        self.controller_auth = controller_auth
        self.caller = caller

    def _binding(self, command, connection_ref):
        result = self.controller_auth.resolve_controller_binding(
            actor_id=command.actor_ref, connection_ref=connection_ref)
        if not result.accepted or result.binding is None:
            raise ValueError(result.error_code or "controller_binding_required")
        # Snapshot mutable auth records before any owner/store call.
        return result.binding.model_copy(deep=True)

    def submit(self, command: EconomyRandomCommand, *, connection_ref: str) -> EconomyRandomCommandResult:
        binding = self._binding(command, connection_ref)
        identity = _digest([command.actor_ref, command.request_id])
        operation = f"random-command:{identity}"
        command_id = f"cmd:{operation}"
        stream = f"economy-random-commands:{command.actor_ref}"
        payload = {"request": command.model_dump(mode="json"),
                   "request_digest": "sha256:" + _digest(command.model_dump(mode="json")),
                   "operation_ref": operation,
                   "authenticated_principal_ref": binding.authenticated_principal_ref}
        trigger = self.store.get_by_idempotency(self.PRINCIPAL, operation)
        if trigger is None:
            trigger_payload = {**payload, "binding_origin": binding.model_dump(mode="json")}
            batch = build_multi_stream_atomic_event_batch(
                command_id=command_id, principal_ref=self.PRINCIPAL,
                expected_revisions={stream: self.store.get_stream_head(stream)},
                event_specs={stream: (("economy.random.command.requested@1", trigger_payload),)},
                event_visibility_policies={stream: ("authority_only",)},
                idempotency_key=operation, causation_id=f"controller-command:{command.request_id}",
                correlation_id=operation)
            trigger = self.store.append_batch(batch)
        if not trigger.committed or len(trigger.committed_event_ids) != 1:
            raise ValueError("economy_random_trigger_commit_failed")
        event = self.store.get_event(trigger.committed_event_ids[0])
        transaction = self.store.get_transaction(trigger.transaction_id)
        origin = event.payload.get("binding_origin")
        if (set(event.payload) != {*payload, "binding_origin"}
                or any(event.payload.get(key) != value for key, value in payload.items())
                or not isinstance(origin, dict)
                or origin.get("actor_id") != command.actor_ref
                or origin.get("authenticated_principal_ref") != binding.authenticated_principal_ref
                or event.command_id != command_id
                or event.event_type != "economy.random.command.requested@1"
                or event.schema_version != 1 or event.stream_id != stream
                or event.visibility_policy != "authority_only"
                or event.causation_id != f"controller-command:{command.request_id}"
                or event.correlation_id != operation or transaction is None
                or transaction.command_id != command_id
                or transaction.idempotency_record.principal_ref != self.PRINCIPAL
                or transaction.idempotency_record.idempotency_key != operation
                or list(transaction.events) != [event]
                or not self.store.transaction_owns_event(transaction_id=trigger.transaction_id,
                      event_id=event.event_id, principal_ref=self.PRINCIPAL)):
            raise ValueError("economy_random_trigger_identity_conflict")
        current = self._binding(command, connection_ref)
        if current != binding:
            raise ValueError("economy_random_binding_changed")
        owner = self.caller.authority
        prior = self.store.get_by_idempotency(owner._PRINCIPAL, operation)
        replayed = prior is not None
        if prior is None:
            prior = self.caller.submit(
                policy_ref=command.policy_ref, operation_ref=operation,
                effect_ref=f"effect:{operation}", target_ref=command.actor_ref,
                actor_ref=command.actor_ref, world_ref=command.world_ref,
                timeline_ref=command.timeline_ref, world_tick=command.world_tick,
                draw_index=0, idempotency_key=operation, command_id=f"settle:{operation}",
                pins=None, causation_id=event.event_id, correlation_id=operation)
        if not prior.committed:
            raise ValueError(prior.failure.error_code if prior.failure else "economy_random_uncommitted")
        receipt = owner.lookup_random_business_receipt(idempotency_key=operation, scope="authority")
        if replayed:
            receipt = receipt.model_copy(update={"idempotency_status": "duplicate_replayed"})
        result_event = self.store.get_event(receipt.committed_event_ids[0])
        expected = {"operation_ref": operation, "target_ref": command.actor_ref,
                    "world_ref": command.world_ref, "timeline_ref": command.timeline_ref,
                    "world_tick": command.world_tick, "candidate_registry_ref": command.policy_ref,
                    "effect_ref": f"effect:{operation}", "draw_index": 0}
        if (any(result_event.payload.get(key) != value for key, value in expected.items())
                or result_event.command_id != f"settle:{operation}"
                or result_event.causation_id != event.event_id
                or result_event.correlation_id != operation
                or event.global_sequence >= result_event.global_sequence):
            raise ValueError("economy_random_result_identity_conflict")
        return EconomyRandomCommandResult(
            operation_ref=operation,
            trigger_receipt=SettlementReceipt.from_append_result(result=trigger),
            economy_receipt=receipt, candidate_ref=result_event.payload["candidate_ref"],
            result_ref=result_event.payload["result_ref"])
