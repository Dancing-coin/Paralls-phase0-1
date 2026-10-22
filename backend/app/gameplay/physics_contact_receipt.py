"""Authenticated physics/runtime contact evidence for combat admission.

The receipt is an attestation from a registered runtime authority.  Client
``ActionAttempt`` evidence remains useful for diagnostics, but cannot satisfy
this contract by itself.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.gameplay.event_store import GameplayEventStore, GameplayEventStoreSnapshotError
from app.gameplay.models import AppendBatchResult, GameplayFailure
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.models.embodied_interaction import ActionAttempt


PHYSICS_CONTACT_RECEIPT_EVENT = "gameplay.combat.physics_contact_receipt_recorded"
PHYSICS_CONTACT_RECEIPT_PRINCIPAL = "authority:combat:physics-contact-receipt"


def _digest(value: str) -> str:
    if not isinstance(value, str) or len(value) != 71 or not value.startswith("sha256:"):
        raise ValueError("contact_digest_invalid")
    try:
        int(value[7:], 16)
    except ValueError as exc:
        raise ValueError("contact_digest_invalid") from exc
    return value


class PhysicsContactReceipt(BaseModel):
    """Signed, attempt-bound contact fact emitted by a physics authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    authority_ref: str = Field(min_length=1)
    actor_ref: str = Field(min_length=1)
    target_ref: str = Field(min_length=1)
    connection_epoch: int = Field(ge=1, strict=True)
    attempt_id: str = Field(min_length=1)
    physics_tick: int = Field(ge=0, strict=True)
    target_incarnation_ref: str = Field(min_length=1)
    action_descriptor_digest: str
    attempt_payload_digest: str
    contact_source_digest: str
    signature: str = Field(min_length=64, max_length=64)

    _validate_digests = field_validator(
        "action_descriptor_digest", "attempt_payload_digest", "contact_source_digest"
    )(_digest)

    @field_validator("signature")
    @classmethod
    def _validate_signature(cls, value: str) -> str:
        try:
            int(value, 16)
        except ValueError as exc:
            raise ValueError("contact_signature_invalid") from exc
        return value

    def canonical_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude={"signature"})

    def canonical_bytes(self) -> bytes:
        return json.dumps(self.canonical_payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()

    @property
    def receipt_digest(self) -> str:
        return "sha256:" + hashlib.sha256(self.canonical_bytes()).hexdigest()


class PhysicsContactReceiptVerifier:
    """Verify receipts from explicitly registered physics authorities."""

    def __init__(self, authority_secrets: Mapping[str, str]) -> None:
        self._authority_secrets = {
            authority: secret
            for authority, secret in authority_secrets.items()
            if isinstance(authority, str) and authority.strip()
            and isinstance(secret, str) and secret
        }

    @property
    def authority_refs(self) -> tuple[str, ...]:
        return tuple(self._authority_secrets)

    def verify(
        self,
        receipt: PhysicsContactReceipt,
        *,
        attempt: ActionAttempt,
        target_incarnation_ref: str,
    ) -> PhysicsContactReceipt | None:
        secret = self._authority_secrets.get(receipt.authority_ref)
        if secret is None or len(attempt.target_refs) != 1:
            return None
        expected = hmac.new(secret.encode(), receipt.canonical_bytes(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, receipt.signature):
            return None
        if (
            receipt.actor_ref != attempt.actor_ref
            or receipt.target_ref != attempt.target_refs[0]
            or receipt.connection_epoch != attempt.connection_epoch
            or receipt.attempt_id != attempt.attempt_id
            or receipt.physics_tick != attempt.physics_tick
            or receipt.target_incarnation_ref != target_incarnation_ref
            or receipt.action_descriptor_digest != attempt.action_descriptor_digest
            or receipt.attempt_payload_digest != attempt.payload_digest
        ):
            return None
        return receipt


class PhysicsContactReceiptAuthority:
    """Persist authenticated runtime receipts with one immutable result per attempt."""

    def __init__(self, *, store: GameplayEventStore, verifier: PhysicsContactReceiptVerifier) -> None:
        self._store = store
        self._verifier = verifier

    def record(
        self,
        receipt: PhysicsContactReceipt,
        *,
        attempt: ActionAttempt,
        target_incarnation_ref: str,
    ) -> AppendBatchResult:
        verified = self._verifier.verify(
            receipt, attempt=attempt, target_incarnation_ref=target_incarnation_ref
        )
        if verified is None:
            return self._reject(attempt.attempt_id, "contact_receipt_unverified")
        key = self._attempt_key(receipt.authority_ref, attempt)
        payload = {
            "receipt": receipt.model_dump(mode="json"),
            "receipt_digest": receipt.receipt_digest,
            "actor_ref": attempt.actor_ref,
            "target_ref": attempt.target_refs[0],
            "attempt_id": attempt.attempt_id,
            "connection_epoch": attempt.connection_epoch,
            "action_descriptor_digest": attempt.action_descriptor_digest,
            "attempt_payload_digest": attempt.payload_digest,
            "target_incarnation_ref": target_incarnation_ref,
        }
        prior = self._store.get_by_idempotency(PHYSICS_CONTACT_RECEIPT_PRINCIPAL, key)
        if prior is not None:
            prior_event = self._receipt_event(prior)
            if prior_event is None or prior_event.payload != payload:
                return self._reject(attempt.attempt_id, "contact_attempt_receipt_conflict")
            return prior.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)

        command_id = f"physics-contact:{key.removeprefix('contact:')}"
        result = self._store.append_batch(build_atomic_event_batch(
            command_id=command_id,
            principal_ref=PHYSICS_CONTACT_RECEIPT_PRINCIPAL,
            stream_id=f"gameplay:combat:physics-contact:{key.removeprefix('contact:')}",
            expected_revision=0,
            event_specs=((PHYSICS_CONTACT_RECEIPT_EVENT, payload),),
            idempotency_key=key,
            causation_id=attempt.causation_id,
            correlation_id=attempt.correlation_id,
        ))
        if not result.committed and result.failure is not None:
            return self._reject(attempt.attempt_id, "contact_attempt_receipt_conflict")
        return result

    def receipt_for_attempt(self, attempt: ActionAttempt) -> PhysicsContactReceipt | None:
        if len(attempt.target_refs) != 1:
            return None
        for authority_ref in self._verifier.authority_refs:
            key = self._attempt_key(authority_ref, attempt)
            result = self._store.get_by_idempotency(PHYSICS_CONTACT_RECEIPT_PRINCIPAL, key)
            event = self._receipt_event(result) if result is not None else None
            if event is None:
                continue
            try:
                receipt = PhysicsContactReceipt.model_validate(event.payload["receipt"])
            except (KeyError, TypeError, ValueError):
                return None
            if (
                event.payload.get("receipt_digest") != receipt.receipt_digest
                or self._verifier.verify(
                    receipt, attempt=attempt,
                    target_incarnation_ref=receipt.target_incarnation_ref,
                ) is None
            ):
                return None
            return receipt
        return None

    def _receipt_event(self, result: AppendBatchResult) -> Any | None:
        try:
            if not result.committed or len(result.committed_event_ids) != 1:
                return None
            event = self._store.get_event(result.committed_event_ids[0])
            if (
                event.event_type != PHYSICS_CONTACT_RECEIPT_EVENT
                or not self._store.transaction_owns_event(
                    transaction_id=event.transaction_id,
                    event_id=event.event_id,
                    principal_ref=PHYSICS_CONTACT_RECEIPT_PRINCIPAL,
                )
            ):
                return None
            return event
        except (GameplayEventStoreSnapshotError, KeyError, TypeError, ValueError):
            return None

    @staticmethod
    def _attempt_key(authority_ref: str, attempt: ActionAttempt) -> str:
        identity = "\0".join((
            authority_ref, attempt.actor_ref, str(attempt.connection_epoch), attempt.attempt_id,
        ))
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        return f"contact:{digest}"

    @staticmethod
    def _reject(command_id: str, code: str) -> AppendBatchResult:
        return AppendBatchResult(
            committed=False,
            transaction_id=f"rejected:{command_id}",
            command_id=command_id,
            idempotency_status="rejected",
            failure=GameplayFailure(
                error_code=code, message=code, failed_stage="physics_contact_receipt"
            ),
        )


__all__ = [
    "PHYSICS_CONTACT_RECEIPT_EVENT",
    "PHYSICS_CONTACT_RECEIPT_PRINCIPAL",
    "PhysicsContactReceipt",
    "PhysicsContactReceiptAuthority",
    "PhysicsContactReceiptVerifier",
]
