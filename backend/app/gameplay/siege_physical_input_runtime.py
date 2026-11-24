"""Persist separately signed physical inputs for the county-siege owners."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.gameplay.event_store import GameplayEventStore, GameplayEventStoreSnapshotError
from app.gameplay.models import AppendBatchResult, GameplayFailure, GameplayEvent
from app.gameplay.settlement_plan import build_multi_stream_atomic_event_batch


GATE_IMPACT_INPUT_EVENT = "gameplay.facility.gate_impact_input_received"
GATE_IMPACT_INPUT_EVENT_V2 = "gameplay.facility.gate_impact_input_received@2"
PRESENCE_ASSESSMENT_INPUT_EVENT = "gameplay.presence.assessment_input_received"
SIEGE_PHYSICAL_INPUT_PRINCIPAL = "authority:siege:physical-input"
_GATE_REF = re.compile(r"^gate-[a-z0-9-]+$")


def _digest(value: str) -> str:
    if not isinstance(value, str) or len(value) != 71 or not value.startswith("sha256:"):
        raise ValueError("siege_input_digest_invalid")
    try:
        int(value[7:], 16)
    except ValueError as exc:
        raise ValueError("siege_input_digest_invalid") from exc
    return value


class _SignedSiegeReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    authority_ref: str = Field(min_length=1)
    receipt_id: str = Field(min_length=1, max_length=160)
    gate_ref: str = Field(min_length=1)
    physics_tick: int = Field(ge=0, strict=True)
    signature: str = Field(min_length=64, max_length=64)

    @field_validator("signature")
    @classmethod
    def validate_signature(cls, value: str) -> str:
        try:
            int(value, 16)
        except ValueError as exc:
            raise ValueError("siege_input_signature_invalid") from exc
        return value

    @field_validator("gate_ref")
    @classmethod
    def validate_gate_ref(cls, value: str) -> str:
        if _GATE_REF.fullmatch(value) is None:
            raise ValueError("siege_input_gate_ref_invalid")
        return value

    def canonical_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude={"signature"})

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")

    @property
    def receipt_digest(self) -> str:
        return "sha256:" + hashlib.sha256(self.canonical_bytes()).hexdigest()


class GateImpactReceipt(_SignedSiegeReceipt):
    impact_kind_ref: str = Field(min_length=1, max_length=160)
    target_incarnation_ref: str = Field(min_length=1, max_length=160)
    contact_source_digest: str
    expected_integrity_revision: int = Field(ge=0, strict=True)

    _validate_contact_digest = field_validator("contact_source_digest")(_digest)


class GateImpactReceiptV2(_SignedSiegeReceipt):
    impact_kind_ref: str = Field(min_length=1, max_length=160)
    target_incarnation_ref: str = Field(min_length=1, max_length=160)
    contact_source_digest: str
    expected_layer_revisions: dict[str, int] = Field(min_length=3, max_length=3)

    _validate_contact_digest = field_validator("contact_source_digest")(_digest)

    @model_validator(mode="after")
    def validate_layer_revisions(self) -> "GateImpactReceiptV2":
        expected_streams = {
            f"fact:facility:{self.gate_ref}:durability",
            f"fact:facility:{self.gate_ref}:latch-durability",
            f"fact:facility:{self.gate_ref}:integrity",
        }
        if (
            set(self.expected_layer_revisions) != expected_streams
            or any(type(revision) is not int or revision < 0
                   for revision in self.expected_layer_revisions.values())
        ):
            raise ValueError("siege_gate_layer_revision_vector_invalid")
        return self


class PresenceAssessmentReceipt(_SignedSiegeReceipt):
    breach_event_id: str = Field(min_length=1, max_length=160)
    assessment_ref: str = Field(min_length=1, max_length=160)
    state: Literal["blocked", "passable"]
    source_event_ids: tuple[str, ...] = Field(min_length=2, max_length=32)
    source_stream_revisions: dict[str, int] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_source_vector(self) -> "PresenceAssessmentReceipt":
        if (
            len(set(self.source_event_ids)) != len(self.source_event_ids)
            or self.breach_event_id not in self.source_event_ids
            or not any(event_id != self.breach_event_id for event_id in self.source_event_ids)
            or any(
                not isinstance(stream_id, str)
                or not stream_id
                or type(revision) is not int
                or revision < 1
                for stream_id, revision in self.source_stream_revisions.items()
            )
        ):
            raise ValueError("siege_presence_evidence_invalid")
        return self


class SiegePhysicalInputAuthority:
    """Authenticate, persist, and replay immutable UE input evidence."""

    def __init__(
        self,
        *,
        store: GameplayEventStore,
        authority_secrets: Mapping[str, str],
        evidence_event_principals: Mapping[str, str] | None = None,
    ) -> None:
        self._store = store
        self._authority_secrets = {
            authority: secret
            for authority, secret in authority_secrets.items()
            if isinstance(authority, str)
            and authority.strip()
            and isinstance(secret, str)
            and secret
        }
        self._evidence_event_principals = dict(evidence_event_principals or {})

    def record_gate_impact(self, receipt: GateImpactReceipt) -> AppendBatchResult:
        if not self._valid_signature(receipt):
            return self._reject(receipt.receipt_id, "siege_input_signature_invalid")
        return self._record(
            receipt,
            event_type=GATE_IMPACT_INPUT_EVENT,
            stream_id=f"gameplay:combat:gate-impact:{receipt.receipt_id}",
        )

    def record_gate_impact_v2(
        self, receipt: GateImpactReceiptV2
    ) -> AppendBatchResult:
        if not self._valid_signature(receipt):
            return self._reject(receipt.receipt_id, "siege_input_signature_invalid")
        return self._record(
            receipt,
            event_type=GATE_IMPACT_INPUT_EVENT_V2,
            stream_id=f"gameplay:combat:gate-impact:{receipt.receipt_id}",
        )

    def record_presence_assessment(
        self, receipt: PresenceAssessmentReceipt
    ) -> AppendBatchResult:
        if not self._valid_signature(receipt):
            return self._reject(receipt.receipt_id, "siege_input_signature_invalid")
        if not self._valid_presence_sources(receipt):
            return self._reject(receipt.receipt_id, "siege_presence_evidence_invalid")
        return self._record(
            receipt,
            event_type=PRESENCE_ASSESSMENT_INPUT_EVENT,
            stream_id=f"gameplay:combat:gate-presence:{receipt.receipt_id}",
        )

    def gate_impact_event(self, *, authority_ref: str, receipt_id: str) -> GameplayEvent | None:
        key = self._idempotency_key(authority_ref, receipt_id)
        result = self._store.get_by_idempotency(SIEGE_PHYSICAL_INPUT_PRINCIPAL, key)
        return self._receipt_event(result, GATE_IMPACT_INPUT_EVENT) if result else None

    def gate_impact_event_v2(
        self, *, authority_ref: str, receipt_id: str
    ) -> GameplayEvent | None:
        key = self._idempotency_key(authority_ref, receipt_id)
        result = self._store.get_by_idempotency(SIEGE_PHYSICAL_INPUT_PRINCIPAL, key)
        return self._receipt_event(result, GATE_IMPACT_INPUT_EVENT_V2) if result else None

    def presence_assessment_event(
        self, *, authority_ref: str, receipt_id: str
    ) -> GameplayEvent | None:
        key = self._idempotency_key(authority_ref, receipt_id)
        result = self._store.get_by_idempotency(SIEGE_PHYSICAL_INPUT_PRINCIPAL, key)
        return self._receipt_event(result, PRESENCE_ASSESSMENT_INPUT_EVENT) if result else None

    def store(self) -> GameplayEventStore:
        return self._store

    def _record(
        self,
        receipt: _SignedSiegeReceipt,
        *,
        event_type: str,
        stream_id: str,
    ) -> AppendBatchResult:
        key = self._idempotency_key(receipt.authority_ref, receipt.receipt_id)
        payload = {
            "receipt": receipt.model_dump(mode="json"),
            "receipt_digest": receipt.receipt_digest,
            "authority_ref": receipt.authority_ref,
            "receipt_id": receipt.receipt_id,
            "gate_ref": receipt.gate_ref,
        }
        prior = self._store.get_by_idempotency(SIEGE_PHYSICAL_INPUT_PRINCIPAL, key)
        if prior is not None:
            event = self._receipt_event(prior, event_type)
            if event is None or event.payload != payload:
                return self._reject(receipt.receipt_id, "siege_input_receipt_conflict")
            return prior.model_copy(
                update={"idempotency_status": "duplicate_replayed"}, deep=True
            )

        command_id = f"siege-input:{key.removeprefix('siege-input:')}"
        return self._store.append_batch(build_multi_stream_atomic_event_batch(
            command_id=command_id,
            principal_ref=SIEGE_PHYSICAL_INPUT_PRINCIPAL,
            expected_revisions={stream_id: 0},
            event_specs={stream_id: ((event_type, payload),)},
            idempotency_key=key,
            causation_id=receipt.receipt_id,
            correlation_id=f"siege:{receipt.gate_ref}",
            event_visibility_policies={stream_id: ("authority_only",)},
        ))

    def _valid_signature(self, receipt: _SignedSiegeReceipt) -> bool:
        secret = self._authority_secrets.get(receipt.authority_ref)
        if secret is None:
            return False
        expected = hmac.new(
            secret.encode("utf-8"), receipt.canonical_bytes(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, receipt.signature)

    def _valid_presence_sources(self, receipt: PresenceAssessmentReceipt) -> bool:
        try:
            breach = self._store.get_event(receipt.breach_event_id)
            if not (
                breach.event_type == "gameplay.pool.threshold_crossed"
                and breach.schema_version == 1
                and breach.visibility_policy == "authority_only"
                and breach.stream_id == f"fact:facility:{receipt.gate_ref}:integrity"
                and breach.payload.get("threshold_ref") == "breach"
                and breach.payload.get("direction") == "enter"
                and self._store.transaction_owns_event(
                    transaction_id=breach.transaction_id,
                    event_id=breach.event_id,
                    principal_ref="actor_gameplay.construction_production_domain",
                )
            ):
                return False
            for event_id in receipt.source_event_ids:
                source = self._store.get_event(event_id)
                if (
                    source.stream_id not in receipt.source_stream_revisions
                    or receipt.source_stream_revisions[source.stream_id] != source.stream_revision
                    or self._store.get_stream_head(source.stream_id)
                    != source.stream_revision
                ):
                    return False
                if source.event_id == breach.event_id:
                    continue
                principal = self._evidence_event_principals.get(source.event_type)
                if (
                    principal is None
                    or source.visibility_policy not in {"project", "authority_only"}
                    or not self._store.transaction_owns_event(
                        transaction_id=source.transaction_id,
                        event_id=source.event_id,
                        principal_ref=principal,
                    )
                ):
                    return False
            return True
        except (GameplayEventStoreSnapshotError, KeyError, TypeError, ValueError):
            return False

    def _receipt_event(
        self, result: AppendBatchResult, event_type: str
    ) -> GameplayEvent | None:
        try:
            if not result.committed or len(result.committed_event_ids) != 1:
                return None
            event = self._store.get_event(result.committed_event_ids[0])
            if (
                event.event_type != event_type
                or not self._store.transaction_owns_event(
                    transaction_id=event.transaction_id,
                    event_id=event.event_id,
                    principal_ref=SIEGE_PHYSICAL_INPUT_PRINCIPAL,
                )
            ):
                return None
            receipt_type = {
                GATE_IMPACT_INPUT_EVENT: GateImpactReceipt,
                GATE_IMPACT_INPUT_EVENT_V2: GateImpactReceiptV2,
                PRESENCE_ASSESSMENT_INPUT_EVENT: PresenceAssessmentReceipt,
            }[event_type]
            receipt = receipt_type.model_validate(event.payload["receipt"])
            if event.payload.get("receipt_digest") != receipt.receipt_digest:
                return None
            if not self._valid_signature(receipt):
                return None
            return event
        except (GameplayEventStoreSnapshotError, KeyError, TypeError, ValueError):
            return None

    @staticmethod
    def _idempotency_key(authority_ref: str, receipt_id: str) -> str:
        digest = hashlib.sha256(f"{authority_ref}\0{receipt_id}".encode()).hexdigest()
        return f"siege-input:{digest}"

    @staticmethod
    def _reject(receipt_id: str, code: str) -> AppendBatchResult:
        return AppendBatchResult(
            committed=False,
            transaction_id=f"rejected:siege-input:{receipt_id}",
            command_id=f"siege-input:{receipt_id}",
            idempotency_status="rejected",
            failure=GameplayFailure(
                error_code=code,
                message=code,
                failed_stage="siege_physical_input",
            ),
        )
