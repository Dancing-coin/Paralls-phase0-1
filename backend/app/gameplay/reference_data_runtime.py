from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import ConfigDict, Field

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayOutboxEntry, OwnerAuthorizedFragment, StrictGameplayModel
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.settlement_plan import SettlementPlan, build_multi_stream_atomic_event_batch_from_fragments
from app.gameplay.shared_contracts import GameplayCommandEnvelope


def _digest(payload: object) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


class ReferenceDatasetRecord(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_ref: str = Field(min_length=1)
    provenance: str = Field(min_length=1)
    license_ref: str = Field(min_length=1)
    schema_revision: str = Field(min_length=1)
    digest: str = Field(min_length=1)
    classification: str = Field(min_length=1)
    allowed_scopes: tuple[str, ...] = Field(min_length=1)
    license_status: Literal["permitted", "restricted"]


class ReferenceDatasetView(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_ref: str = Field(min_length=1)
    provenance: str = Field(min_length=1)
    license_ref: str = Field(min_length=1)
    schema_revision: str = Field(min_length=1)
    digest: str = Field(min_length=1)
    classification: str = Field(min_length=1)
    allowed_scopes: tuple[str, ...] = Field(min_length=1)
    license_status: Literal["permitted", "restricted"]
    dataset_revision: int = Field(ge=1)
    status: Literal["active", "revoked"]
    source_event_refs: tuple[str, ...] = Field(min_length=1)
    source_revision_vector: dict[str, int] = Field(min_length=1)
    projection_digest: str = Field(min_length=1)


class ReferenceDatasetViewResult(StrictGameplayModel):
    accepted: bool
    view: ReferenceDatasetView | None = None
    error_code: str | None = None


class ReferenceDataAuthority:
    """The sole event-sourced owner for reference-data license admission."""

    _PRINCIPAL = "authority:reference_data"
    _STREAM_PREFIX = "gameplay:reference_data:"
    _EVENT_PREFIX = "gameplay.reference_data."

    def __init__(self, *, store: GameplayEventStore) -> None:
        self.store = store

    @classmethod
    def dataset_stream_id(cls, *, dataset_ref: str) -> str:
        return f"{cls._STREAM_PREFIX}{dataset_ref}"

    def register(self, *, envelope: GameplayCommandEnvelope, record: ReferenceDatasetRecord) -> AppendBatchResult:
        return self._write_record(envelope=envelope, record=record, operation="dataset_registered")

    def correct(self, *, envelope: GameplayCommandEnvelope, record: ReferenceDatasetRecord) -> AppendBatchResult:
        return self._write_record(envelope=envelope, record=record, operation="dataset_corrected")

    def revoke(self, *, envelope: GameplayCommandEnvelope, dataset_ref: str) -> AppendBatchResult:
        if not dataset_ref:
            return self._rejected(envelope, "reference_dataset_identity_invalid")
        if not self._is_owner(envelope):
            return self._rejected(envelope, "reference_data_authority_required")
        projected = self._project_authority().get(dataset_ref)
        if self.store.get_by_idempotency(envelope.principal_ref, envelope.idempotency_key) is None and projected is None:
            return self._rejected(envelope, "reference_dataset_unknown")
        return self._append(envelope=envelope, stream_id=self.dataset_stream_id(dataset_ref=dataset_ref), operation="dataset_revoked", payload={"dataset_ref": dataset_ref})

    def view_for(self, *, dataset_ref: str, reader_scope: Literal["authority", "creator", "public"], expected_dataset_revision: int | None = None) -> ReferenceDatasetViewResult:
        if reader_scope != "authority":
            return ReferenceDatasetViewResult(accepted=False, error_code="reference_dataset_scope_denied")
        projected = self._project_authority().get(dataset_ref)
        if projected is None:
            return ReferenceDatasetViewResult(accepted=False, error_code="reference_dataset_unknown")
        if expected_dataset_revision is not None and projected["dataset_revision"] != expected_dataset_revision:
            return ReferenceDatasetViewResult(accepted=False, error_code="reference_dataset_revision_conflict")
        if projected["status"] == "revoked":
            return ReferenceDatasetViewResult(accepted=False, error_code="reference_dataset_revoked")
        return ReferenceDatasetViewResult(accepted=True, view=ReferenceDatasetView.model_validate(projected))

    def replay(self, *, checkpoint_at: int | None = None):
        replay = GameplayProjectionReplay(projector_id="infra-reference-data-license-admission", projector_version="1")
        events = self._events()
        if checkpoint_at is None:
            return replay.full_replay(events)
        checkpoint = replay.create_checkpoint(events[:checkpoint_at])
        return replay.checkpoint_plus_tail_replay(checkpoint, events[checkpoint_at:])

    def _write_record(self, *, envelope: GameplayCommandEnvelope, record: ReferenceDatasetRecord, operation: Literal["dataset_registered", "dataset_corrected"]) -> AppendBatchResult:
        if not self._is_owner(envelope):
            return self._rejected(envelope, "reference_data_authority_required")
        projected = self._project_authority().get(record.dataset_ref)
        existing = self.store.get_by_idempotency(envelope.principal_ref, envelope.idempotency_key)
        if existing is None and operation == "dataset_registered" and projected is not None:
            return self._rejected(envelope, "reference_dataset_already_registered")
        if existing is None and operation == "dataset_corrected" and (projected is None or projected["status"] == "revoked"):
            return self._rejected(envelope, "reference_dataset_correction_unavailable")
        return self._append(envelope=envelope, stream_id=self.dataset_stream_id(dataset_ref=record.dataset_ref), operation=operation, payload=record.model_dump(mode="json"))

    def _append(self, *, envelope: GameplayCommandEnvelope, stream_id: str, operation: Literal["dataset_registered", "dataset_corrected", "dataset_revoked"], payload: dict[str, object]) -> AppendBatchResult:
        if self.store.get_by_idempotency(envelope.principal_ref, envelope.idempotency_key) is None and envelope.expected_revisions != {stream_id: self.store.get_stream_head(stream_id)}:
            return self._rejected(envelope, "revision_conflict")
        try:
            SettlementPlan.from_command_envelope(envelope)
            fragment = OwnerAuthorizedFragment(
                fragment_id=f"fragment:reference-data:{operation}:{payload['dataset_ref']}:{envelope.command_id}",
                owner_principal_ref=self._PRINCIPAL,
                source_rule_ref=f"reference-data:{operation}:v1",
                expected_revisions=dict(envelope.expected_revisions),
                pinned_revisions={"schema": 1},
                event_specs={stream_id: ((f"{self._EVENT_PREFIX}{operation}", payload),)},
                event_visibility_policies={stream_id: ("authority_only",)},
            )
            batch = build_multi_stream_atomic_event_batch_from_fragments(command_id=envelope.command_id, idempotency_principal_ref=envelope.principal_ref, idempotency_key=envelope.idempotency_key, causation_id=envelope.causation_id, correlation_id=envelope.correlation_id, fragments=(fragment,))
            event = batch.events[0]
            batch = batch.model_copy(update={"outbox_entries": [GameplayOutboxEntry(outbox_id=f"outbox:{event.event_id}", transaction_id=batch.transaction_id, event_id=event.event_id, global_sequence=0, topic="world.reference_data.scoped_projection", audience="authority_only", payload_projection={"dataset_ref": payload["dataset_ref"], "event_type": event.event_type, "dataset_digest": payload.get("digest", "")})]}, deep=True)
        except ValueError as exc:
            return self._rejected(envelope, str(exc))
        return self.store.append_batch(batch)

    def _project_authority(self) -> dict[str, dict[str, object]]:
        projection: dict[str, dict[str, object]] = {}
        for event in self._events():
            dataset_ref = str(event.payload.get("dataset_ref", ""))
            previous = projection.get(dataset_ref)
            if event.event_type == f"{self._EVENT_PREFIX}dataset_registered":
                projection[dataset_ref] = self._active_projection(
                    event_id=event.event_id,
                    payload=event.payload,
                    revision=1,
                    stream_id=event.stream_id,
                    stream_revision=event.stream_revision,
                )
            elif event.event_type == f"{self._EVENT_PREFIX}dataset_corrected" and previous is not None:
                projection[dataset_ref] = self._active_projection(
                    event_id=event.event_id,
                    payload=event.payload,
                    revision=int(previous["dataset_revision"]) + 1,
                    stream_id=event.stream_id,
                    stream_revision=event.stream_revision,
                    source_event_refs=tuple((*previous["source_event_refs"], event.event_id)),
                )
            elif event.event_type == f"{self._EVENT_PREFIX}dataset_revoked" and previous is not None:
                projection[dataset_ref] = {
                    **previous,
                    "status": "revoked",
                    "source_event_refs": tuple((*previous["source_event_refs"], event.event_id)),
                    "source_revision_vector": {event.stream_id: event.stream_revision},
                }
        return projection

    @staticmethod
    def _active_projection(*, event_id: str, payload: dict[str, object], revision: int, stream_id: str, stream_revision: int, source_event_refs: tuple[str, ...] | None = None) -> dict[str, object]:
        base = {"dataset_ref": str(payload["dataset_ref"]), "provenance": str(payload["provenance"]), "license_ref": str(payload["license_ref"]), "schema_revision": str(payload["schema_revision"]), "digest": str(payload["digest"]), "classification": str(payload["classification"]), "allowed_scopes": tuple(payload["allowed_scopes"]), "license_status": str(payload["license_status"]), "dataset_revision": revision, "status": "active", "source_event_refs": source_event_refs or (event_id,), "source_revision_vector": {stream_id: stream_revision}}
        return {**base, "projection_digest": _digest(base)}

    def _events(self):
        return [event for event in self.store.read_events() if event.stream_id.startswith(self._STREAM_PREFIX)]

    @classmethod
    def _is_owner(cls, envelope: GameplayCommandEnvelope) -> bool:
        return envelope.principal_ref == cls._PRINCIPAL and envelope.source_ref == cls._PRINCIPAL

    @staticmethod
    def _rejected(envelope: GameplayCommandEnvelope, error_code: str) -> AppendBatchResult:
        return AppendBatchResult(committed=False, transaction_id=envelope.transaction_id or f"transaction:{envelope.command_id}", command_id=envelope.command_id, idempotency_status="rejected", failure={"error_code": error_code, "message": error_code, "failed_stage": "reference_data_admission"})


__all__ = ["ReferenceDataAuthority", "ReferenceDatasetRecord", "ReferenceDatasetView", "ReferenceDatasetViewResult"]
