"""Persist separately signed physical inputs for the county-siege owners."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.gameplay.event_store import GameplayEventStore, GameplayEventStoreSnapshotError
from app.gameplay.models import AppendBatchResult, GameplayFailure, GameplayEvent
from app.gameplay.owner_runtime_base import replay_duplicate
from app.gameplay.settlement_plan import build_multi_stream_atomic_event_batch
from app.gameplay.siege_physical_input_event_schema import (
    GATE_IMPACT_INPUT_EVENT,
    GATE_IMPACT_INPUT_EVENT_V2,
    PRESENCE_ASSESSMENT_INPUT_EVENT,
    PRESENCE_ASSESSMENT_INPUT_EVENT_V2,
)


SIEGE_PHYSICAL_INPUT_PRINCIPAL = "authority:siege:physical-input"
FACILITY_GATE_PRINCIPAL = "actor_gameplay.construction_production_domain"
_GATE_REF = re.compile(r"^gate-[a-z0-9-]+$")
_GATE_LAYERS = ("durability", "latch-durability", "integrity")


def facility_impact_command_id(impact_event_id: str) -> str:
    return f"facility-gate-impact:{impact_event_id}"


def _gate_layer_streams(gate_ref: str) -> set[str]:
    return {f"fact:facility:{gate_ref}:{layer}" for layer in _GATE_LAYERS}


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
        if (
            set(self.expected_layer_revisions) != _gate_layer_streams(self.gate_ref)
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


class PresenceAssessmentReceiptV2(_SignedSiegeReceipt):
    impact_event_id: str = Field(min_length=1, max_length=160)
    target_incarnation_ref: str = Field(min_length=1, max_length=160)
    assessment_ref: str = Field(min_length=1, max_length=160)
    state: Literal["blocked", "passable"]
    expected_layer_revisions: dict[str, Annotated[int, Field(ge=1, strict=True)]]
    expected_place_revision: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def validate_layer_revisions(self) -> "PresenceAssessmentReceiptV2":
        if set(self.expected_layer_revisions) != _gate_layer_streams(self.gate_ref):
            raise ValueError("siege_gate_layer_revision_vector_invalid")
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

    def record_gate_impact(
        self, receipt: GateImpactReceipt, *, event_time: int | None = None,
    ) -> AppendBatchResult:
        if not self._valid_signature(receipt):
            return self._reject(receipt.receipt_id, "siege_input_signature_invalid")
        return self._record(
            receipt,
            event_type=GATE_IMPACT_INPUT_EVENT,
            stream_id=f"gameplay:combat:gate-impact:{receipt.receipt_id}",
            event_time=event_time,
        )

    def record_gate_impact_v2(
        self, receipt: GateImpactReceiptV2, *, event_time: int | None = None,
    ) -> AppendBatchResult:
        if not self._valid_signature(receipt):
            return self._reject(receipt.receipt_id, "siege_input_signature_invalid")
        return self._record(
            receipt,
            event_type=GATE_IMPACT_INPUT_EVENT_V2,
            stream_id=f"gameplay:combat:gate-impact:{receipt.receipt_id}",
            event_time=event_time,
        )

    def record_presence_assessment(
        self, receipt: PresenceAssessmentReceipt | PresenceAssessmentReceiptV2,
        *, event_time: int | None = None,
    ) -> AppendBatchResult:
        if not self._valid_signature(receipt):
            return self._reject(receipt.receipt_id, "siege_input_signature_invalid")
        if isinstance(receipt, PresenceAssessmentReceiptV2):
            return self._record(
                receipt,
                event_type=PRESENCE_ASSESSMENT_INPUT_EVENT_V2,
                stream_id=f"gameplay:combat:gate-presence:{receipt.receipt_id}",
                event_time=event_time,
            )
        if not self._valid_presence_sources(receipt):
            return self._reject(receipt.receipt_id, "siege_presence_evidence_invalid")
        return self._record(
            receipt,
            event_type=PRESENCE_ASSESSMENT_INPUT_EVENT,
            stream_id=f"gameplay:combat:gate-presence:{receipt.receipt_id}",
            event_time=event_time,
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
        if result is None:
            return None
        return (
            self._receipt_event(result, PRESENCE_ASSESSMENT_INPUT_EVENT)
            or self._receipt_event(result, PRESENCE_ASSESSMENT_INPUT_EVENT_V2)
        )

    def store(self) -> GameplayEventStore:
        return self._store

    def _record(
        self,
        receipt: _SignedSiegeReceipt,
        *,
        event_type: str,
        stream_id: str,
        event_time: int | None,
    ) -> AppendBatchResult:
        if event_time is not None and (type(event_time) is not int or event_time < 0):
            return self._reject(receipt.receipt_id, "siege_input_event_time_invalid")
        key = self._idempotency_key(receipt.authority_ref, receipt.receipt_id)
        payload = {
            "receipt": receipt.model_dump(mode="json"),
            "receipt_digest": receipt.receipt_digest,
            "authority_ref": receipt.authority_ref,
            "receipt_id": receipt.receipt_id,
            "gate_ref": receipt.gate_ref,
        }
        command_id = f"siege-input:{key.removeprefix('siege-input:')}"
        idempotency_record = self._store.get_idempotency_record(
            SIEGE_PHYSICAL_INPUT_PRINCIPAL, key
        )
        if idempotency_record is not None:
            try:
                prior = replay_duplicate(
                    self._store,
                    principal=SIEGE_PHYSICAL_INPUT_PRINCIPAL,
                    idempotency_key=key,
                    payload_digest=idempotency_record.payload_digest,
                    error_factory=ValueError,
                    missing_result_code="replay_missing_result",
                    transaction_mismatch_code="replay_transaction_mismatch",
                    event_count_mismatch_code="replay_event_count_mismatch",
                    event_missing_code="replay_event_missing",
                    expected_event_types=(event_type,),
                    expected_command_id=command_id,
                    expected_transaction_id=f"transaction:{command_id}",
                )
            except ValueError as error:
                return self._reject(receipt.receipt_id, f"siege_input_{error}")
            event = self._receipt_event(prior, event_type)
            if event is None or event.stream_id != stream_id or event.payload != payload:
                return self._reject(receipt.receipt_id, "siege_input_receipt_conflict")
            return prior

        if isinstance(receipt, PresenceAssessmentReceiptV2) and not self._valid_impact_source(receipt):
            return self._reject(receipt.receipt_id, "siege_presence_evidence_invalid")

        batch = build_multi_stream_atomic_event_batch(
            command_id=command_id,
            principal_ref=SIEGE_PHYSICAL_INPUT_PRINCIPAL,
            expected_revisions={stream_id: 0},
            event_specs={stream_id: ((event_type, payload),)},
            idempotency_key=key,
            causation_id=receipt.receipt_id,
            correlation_id=f"siege:{receipt.gate_ref}",
            event_visibility_policies={stream_id: ("authority_only",)},
        )
        if event_time is not None:
            batch = batch.model_copy(update={
                "events": [
                    event.model_copy(update={"event_time": event_time}, deep=True)
                    for event in batch.events
                ],
            }, deep=True)
        return self._store.append_batch(batch)

    def _valid_signature(self, receipt: _SignedSiegeReceipt) -> bool:
        secret = self._authority_secrets.get(receipt.authority_ref)
        if secret is None:
            return False
        expected = hmac.new(
            secret.encode("utf-8"), receipt.canonical_bytes(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, receipt.signature)

    def _valid_impact_source(self, receipt: PresenceAssessmentReceiptV2) -> bool:
        try:
            event = self._store.get_event(receipt.impact_event_id)
        except KeyError:
            return False
        if event.event_type != GATE_IMPACT_INPUT_EVENT_V2 or not self._store.transaction_owns_event(
            transaction_id=event.transaction_id,
            event_id=event.event_id,
            principal_ref=SIEGE_PHYSICAL_INPUT_PRINCIPAL,
        ):
            return False
        impact = GateImpactReceiptV2.model_validate(event.payload["receipt"])
        facility = self._store.get_by_idempotency(
            FACILITY_GATE_PRINCIPAL, facility_impact_command_id(event.event_id)
        )
        return (
            facility is not None
            and facility.committed
            and impact.gate_ref == receipt.gate_ref
            and impact.target_incarnation_ref == receipt.target_incarnation_ref
            and impact.physics_tick <= receipt.physics_tick
            and all(
                revision >= facility.resulting_stream_revisions.get(stream, impact.expected_layer_revisions[stream])
                and revision == self._store.get_stream_head(stream)
                for stream, revision in receipt.expected_layer_revisions.items()
            )
        )

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
                PRESENCE_ASSESSMENT_INPUT_EVENT_V2: PresenceAssessmentReceiptV2,
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
