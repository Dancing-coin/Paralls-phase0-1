"""Authenticated physics/runtime contact evidence for combat admission.

The receipt is an attestation from a registered runtime authority.  Client
``ActionAttempt`` evidence remains useful for diagnostics, but cannot satisfy
this contract by itself.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.embodied_interaction import ActionAttempt


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


__all__ = ["PhysicsContactReceipt", "PhysicsContactReceiptVerifier"]
