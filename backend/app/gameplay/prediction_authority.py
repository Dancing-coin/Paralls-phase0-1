"""Durable provisional prediction ledger for reversible gameplay presentation.

Prediction is an auditable overlay.  It never writes the domain owner stream;
confirmation only records a receipt already committed by that owner.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AtomicEventBatch, AppendBatchResult, GameplayEvent, GameplayFailure, IdempotencyRecord


class PredictionError(ValueError):
    pass


@dataclass(frozen=True)
class PredictionState:
    prediction_id: str
    status: str
    command_id: str
    operation: str
    actor_ref: str
    owner_principal: str | None = None
    owner_idempotency_key: str | None = None
    owner_transaction_id: str | None = None
    owner_event_ids: tuple[str, ...] = ()
    reason: str | None = None
    expires_at: int | None = None


def _digest(value: Any) -> str:
    return "sha256:" + sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


class PredictionAuthority:
    """Append-only lifecycle authority on the shared GameplayEventStore."""

    principal = "gameplay.prediction_authority"

    def __init__(self, *, store: GameplayEventStore) -> None:
        self.store = store

    def open(
        self,
        *, prediction_id: str, command_id: str, actor_ref: str, operation: str,
        idempotency_key: str, base_revision_vector: dict[str, int] | None = None,
        branch_contract_digest: str | None = None, expires_at: int | None = None,
    ) -> AppendBatchResult:
        if not all((prediction_id, command_id, actor_ref, operation, idempotency_key)):
            raise PredictionError("prediction_identity_required")
        stream = self._stream(prediction_id)
        payload = {
            "prediction_id": prediction_id, "command_id": command_id,
            "actor_ref": actor_ref, "operation": operation,
            "base_revision_vector": dict(base_revision_vector or {}),
            "branch_contract_digest": branch_contract_digest,
        }
        if expires_at is not None:
            if type(expires_at) is not int or expires_at < 0:
                raise PredictionError("prediction_expiry_invalid")
            payload["expires_at"] = expires_at
        existing = self.store.read_stream(stream)
        if existing:
            state = self._state_from_events(prediction_id, existing)
            opened = existing[0].payload
            if opened != payload:
                return self._rejected(state, idempotency_key, "prediction_identity_conflict")
            transaction = self.store.get_transaction(existing[0].transaction_id)
            if transaction is not None:
                prior = self.store.get_by_idempotency(self.principal, transaction.idempotency_record.idempotency_key)
                if (prior is not None and transaction.idempotency_record.idempotency_key == idempotency_key
                        and transaction.idempotency_record.payload_digest == _digest({"event_type": "gameplay.prediction.provisional_opened", "payload": payload})):
                    return prior.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            return self._rejected(state, idempotency_key, "prediction_already_open")
        return self._append(
            prediction_id=prediction_id, command_id=command_id,
            idempotency_key=idempotency_key, stream=stream,
            event_type="gameplay.prediction.provisional_opened", payload=payload, expected_revision=0,
        )

    def confirm(
        self, *, prediction_id: str, idempotency_key: str,
        owner_principal: str, owner_idempotency_key: str,
    ) -> AppendBatchResult:
        events = self.store.read_stream(self._stream(prediction_id))
        state = self._state_from_events(prediction_id, events)
        if state.operation == "equipment_overlay" and owner_principal != "actor_gameplay.equipment_domain":
            return self._rejected(state, idempotency_key, "prediction_owner_principal_invalid")
        prior = self._prior_confirm(prediction_id, idempotency_key, owner_principal, owner_idempotency_key)
        if prior is not None and not prior.committed:
            return prior
        if prior is None and self.store.get_idempotency_record(self.principal, idempotency_key) is not None:
            return self._rejected_raw(idempotency_key, "idempotency_key_reused")
        if prior is None:
            self._require_pending(state)
        head_before = events[-1].stream_revision if events else 0
        receipt = self.store.get_by_idempotency(owner_principal, owner_idempotency_key)
        if receipt is None or not receipt.committed:
            return self._rejected(state, idempotency_key, "prediction_owner_receipt_missing")
        transaction = self.store.get_transaction(receipt.transaction_id)
        if transaction is None or transaction.idempotency_record.principal_ref != owner_principal:
            return self._rejected(state, idempotency_key, "prediction_owner_receipt_invalid")
        if receipt.committed_event_ids != [event.event_id for event in transaction.events]:
            return self._rejected(state, idempotency_key, "prediction_owner_event_refs_invalid")
        record = self.store.get_idempotency_record(owner_principal, owner_idempotency_key)
        if (record != transaction.idempotency_record or record is None
                or record.idempotency_key != owner_idempotency_key
                or transaction.transaction_id != receipt.transaction_id
                or transaction.command_id != receipt.command_id
                or not transaction.events):
            return self._rejected(state, idempotency_key, "prediction_owner_receipt_invalid")
        for event in transaction.events:
            try:
                persisted = self.store.get_event(event.event_id)
            except KeyError:
                return self._rejected(state, idempotency_key, "prediction_owner_event_refs_invalid")
            if (persisted != event or event.transaction_id != receipt.transaction_id
                    or not self.store.transaction_owns_event(transaction_id=receipt.transaction_id,
                        event_id=event.event_id, principal_ref=owner_principal)):
                return self._rejected(state, idempotency_key, "prediction_owner_receipt_invalid")
        if state.operation == "equipment_overlay":
            # Equipment's owner contract hashes its pre-append event dictionaries.
            # Store-assigned revisions/sequences must be normalized to that contract.
            raw = [event.model_copy(update={"stream_revision": 0, "global_sequence": 0}).model_dump()
                   for event in transaction.events]
            if transaction.result_digest != _digest(raw).removeprefix("sha256:"):
                return self._rejected(state, idempotency_key, "prediction_owner_receipt_invalid")
        if any(str(event.payload.get("actor_ref", "")) != state.actor_ref for event in transaction.events):
            return self._rejected(state, idempotency_key, "prediction_owner_actor_mismatch")
        if any(event.command_id != state.command_id for event in transaction.events):
            return self._rejected(state, idempotency_key, "prediction_owner_command_mismatch")
        if state.operation == "equipment_overlay" and not any(event.event_type.startswith("gameplay.equipment.") for event in transaction.events):
            return self._rejected(state, idempotency_key, "prediction_owner_operation_mismatch")
        if prior is not None:
            if (state.status != "confirmed" or state.owner_transaction_id != receipt.transaction_id
                    or state.owner_event_ids != tuple(receipt.committed_event_ids)):
                return self._rejected(state, idempotency_key, "prediction_owner_receipt_invalid")
            return prior
        payload = {
            "prediction_id": prediction_id, "command_id": state.command_id,
            "owner_principal": owner_principal, "owner_idempotency_key": owner_idempotency_key,
            "owner_transaction_id": receipt.transaction_id,
            "owner_event_ids": list(receipt.committed_event_ids),
        }
        if self.store.get_stream_head(self._stream(prediction_id)) != head_before:
            return self._rejected(state, idempotency_key, "prediction_revision_conflict")
        return self._append(prediction_id=prediction_id, command_id=f"prediction:{prediction_id}:confirm",
                            idempotency_key=idempotency_key, stream=self._stream(prediction_id),
                            event_type="gameplay.prediction.confirmed", payload=payload, expected_revision=head_before)

    def reject(self, *, prediction_id: str, idempotency_key: str, reason: str,
               owner_principal: str | None = None, owner_idempotency_key: str | None = None) -> AppendBatchResult:
        payload = {"prediction_id": prediction_id, "reason": reason}
        prior = self._prior_lifecycle(idempotency_key, "gameplay.prediction.rejected", payload)
        if prior is not None:
            return prior
        if self.store.get_idempotency_record(self.principal, idempotency_key) is not None:
            return self._rejected_raw(idempotency_key, "idempotency_key_reused")
        events = self.store.read_stream(self._stream(prediction_id))
        state = self._state_from_events(prediction_id, events)
        self._require_pending(state)
        head_before = events[-1].stream_revision if events else 0
        if owner_principal and owner_idempotency_key:
            receipt = self.store.get_by_idempotency(owner_principal, owner_idempotency_key)
            if receipt is None:
                return self._rejected(state, idempotency_key, "prediction_owner_receipt_missing")
        return self._append(prediction_id=prediction_id, command_id=f"prediction:{prediction_id}:reject",
                            idempotency_key=idempotency_key, stream=self._stream(prediction_id),
                            event_type="gameplay.prediction.rejected", payload=payload, expected_revision=head_before)

    def revoke(self, *, prediction_id: str, idempotency_key: str, reason: str) -> AppendBatchResult:
        return self._terminal(prediction_id, idempotency_key, "gameplay.prediction.revoked", reason)

    def expire(self, *, prediction_id: str, idempotency_key: str, reason: str = "expired") -> AppendBatchResult:
        return self._terminal(prediction_id, idempotency_key, "gameplay.prediction.expired", reason)

    def state(self, prediction_id: str) -> PredictionState:
        events = self.store.read_stream(self._stream(prediction_id))
        if not events:
            raise PredictionError("prediction_not_found")
        return self._state_from_events(prediction_id, events)

    def _state_from_events(self, prediction_id: str, events: list[GameplayEvent]) -> PredictionState:
        if any(event.stream_id != self._stream(prediction_id) for event in events):
            raise PredictionError("prediction_stream_mismatch")
        if any(event.payload.get("prediction_id") != prediction_id for event in events):
            raise PredictionError("prediction_identity_mismatch")
        if sum(event.event_type == "gameplay.prediction.provisional_opened" for event in events) > 1:
            raise PredictionError("prediction_multiple_open_events")
        if not events or events[0].event_type != "gameplay.prediction.provisional_opened":
            raise PredictionError("prediction_open_missing")
        allowed = {"gameplay.prediction.provisional_opened", "gameplay.prediction.confirmed", "gameplay.prediction.rejected", "gameplay.prediction.revoked", "gameplay.prediction.expired"}
        if any(event.event_type not in allowed for event in events):
            raise PredictionError("prediction_event_invalid")
        opened = next((e for e in events if e.event_type == "gameplay.prediction.provisional_opened"), None)
        if opened is None or str(opened.payload.get("prediction_id")) != prediction_id:
            raise PredictionError("prediction_open_missing")
        status = "pending"; terminal: GameplayEvent | None = None
        for event in events:
            if event.event_type in {"gameplay.prediction.confirmed", "gameplay.prediction.rejected", "gameplay.prediction.revoked", "gameplay.prediction.expired"}:
                if terminal is not None:
                    raise PredictionError("prediction_multiple_terminal_events")
                terminal = event; status = event.event_type.rsplit(".", 1)[-1]
        payload = terminal.payload if terminal else {}
        return PredictionState(
            prediction_id, status, str(opened.payload["command_id"]), str(opened.payload["operation"]),
            str(opened.payload["actor_ref"]), payload.get("owner_principal"), payload.get("owner_idempotency_key"),
            payload.get("owner_transaction_id"), tuple(payload.get("owner_event_ids", ())), payload.get("reason"),
            opened.payload.get("expires_at"),
        )

    def replay(self, prediction_id: str, *, checkpoint_at: int | None = None) -> PredictionState:
        events = self.store.read_stream(self._stream(prediction_id))
        if checkpoint_at is None:
            return self._state_from_events(prediction_id, events)
        if checkpoint_at <= 0 or len(events) < checkpoint_at:
            raise PredictionError("prediction_checkpoint_missing")
        prefix = events[:checkpoint_at]
        prefix_state = self._state_from_events(prediction_id, prefix)
        tail = events[checkpoint_at:]
        # Apply only the tail transition to the checkpoint state, as a real
        # checkpoint-plus-tail projection would.
        if not tail:
            return prefix_state
        if prefix_state.status != "pending":
            raise PredictionError("prediction_checkpoint_terminal_tail")
        terminal = tail[0]
        if terminal.event_type not in {"gameplay.prediction.confirmed", "gameplay.prediction.rejected", "gameplay.prediction.revoked", "gameplay.prediction.expired"}:
            raise PredictionError("prediction_tail_event_invalid")
        return self._state_from_events(prediction_id, [prefix[0], *tail])

    def _terminal(self, prediction_id: str, idempotency_key: str, event_type: str, reason: str) -> AppendBatchResult:
        payload = {"prediction_id": prediction_id, "reason": reason}
        prior = self._prior_lifecycle(idempotency_key, event_type, {"prediction_id": prediction_id, "reason": reason})
        if prior is not None:
            return prior
        if self.store.get_idempotency_record(self.principal, idempotency_key) is not None:
            return self._rejected_raw(idempotency_key, "idempotency_key_reused")
        events = self.store.read_stream(self._stream(prediction_id))
        state = self._state_from_events(prediction_id, events); self._require_pending(state)
        head_before = events[-1].stream_revision if events else 0
        return self._append(prediction_id=prediction_id, command_id=f"prediction:{prediction_id}:{event_type.rsplit('.',1)[-1]}",
                            idempotency_key=idempotency_key, stream=self._stream(prediction_id), event_type=event_type,
                            payload=payload, expected_revision=head_before)

    def _require_pending(self, state: PredictionState) -> None:
        if state.status != "pending":
            raise PredictionError("prediction_terminal")

    def _rejected(self, state: PredictionState, key: str, code: str) -> AppendBatchResult:
        return AppendBatchResult(committed=False, transaction_id=f"prediction:{state.prediction_id}:rejected", command_id=state.command_id,
                                 idempotency_status="rejected", failure=GameplayFailure(error_code=code, message=code, failed_stage="owner_receipt"))

    def _rejected_raw(self, key: str, code: str) -> AppendBatchResult:
        return AppendBatchResult(committed=False, transaction_id=f"prediction:rejected:{key}", command_id=f"prediction:{key}",
                                 idempotency_status="rejected", failure=GameplayFailure(error_code=code, message=code, failed_stage="idempotency"))

    def _prior_lifecycle(self, key: str, event_type: str, payload: dict[str, Any] | None = None) -> AppendBatchResult | None:
        result = self.store.get_by_idempotency(self.principal, key)
        if result is None:
            return None
        transaction = self.store.get_transaction(result.transaction_id)
        if transaction is None or len(transaction.events) != 1:
            return None
        if transaction.events[0].event_type != event_type:
            return None
        if payload is not None and transaction.idempotency_record.payload_digest != _digest({"event_type": event_type, "payload": payload}):
            return self._rejected_raw(key, "idempotency_key_reused")
        return result.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)

    def _prior_confirm(self, prediction_id: str, key: str, principal: str, owner_key: str) -> AppendBatchResult | None:
        result = self.store.get_by_idempotency(self.principal, key)
        if result is None:
            return None
        transaction = self.store.get_transaction(result.transaction_id)
        if transaction is None or len(transaction.events) != 1 or transaction.events[0].event_type != "gameplay.prediction.confirmed":
            return None
        payload = transaction.events[0].payload
        if payload.get("prediction_id") != prediction_id or payload.get("owner_principal") != principal or payload.get("owner_idempotency_key") != owner_key:
            return self._rejected_raw(key, "idempotency_key_reused")
        return result.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)

    def _append(self, *, prediction_id: str, command_id: str, idempotency_key: str, stream: str, event_type: str, payload: dict[str, Any], expected_revision: int | None = None) -> AppendBatchResult:
        revision = self.store.get_stream_head(stream) if expected_revision is None else expected_revision
        tx = f"prediction-tx:{prediction_id}:{event_type.rsplit('.', 1)[-1]}:{idempotency_key}"
        event = GameplayEvent(event_id=f"{tx}:event", event_type=event_type, schema_version=1, stream_id=stream,
                              stream_revision=revision + 1, global_sequence=0, transaction_id=tx, command_id=command_id,
                              causation_id=command_id, correlation_id=prediction_id, visibility_policy="authority_only", payload=payload)
        batch = AtomicEventBatch(transaction_id=tx, command_id=command_id, expected_stream_revisions={stream: revision},
                                 events=[event], idempotency_record=IdempotencyRecord(principal_ref=self.principal, idempotency_key=idempotency_key,
                                 payload_digest=_digest({"event_type": event_type, "payload": payload})), result_digest=_digest((tx, event_type, payload)))
        return self.store.append_batch(batch)

    @staticmethod
    def _stream(prediction_id: str) -> str:
        return f"gameplay:prediction:{prediction_id}"
