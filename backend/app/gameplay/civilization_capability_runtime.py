from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import ConfigDict, Field

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayOutboxEntry, OwnerAuthorizedFragment, StrictGameplayModel
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.settlement_plan import build_multi_stream_atomic_event_batch_from_fragments
from app.gameplay.shared_contracts import GameplayCommandEnvelope


CapabilityVisibility = Literal["project", "authority_only", "actor_only", "creator_only"]
ReaderScope = Literal["authority", "actor", "public", "creator"]


def _digest(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class CivilizationCapabilityRecord(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_ref: str = Field(min_length=1)
    jurisdiction_ref: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    effective_tick: int = Field(ge=0)
    visibility: CapabilityVisibility = "project"


class CivilizationCapabilityView(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_ref: str = Field(min_length=1)
    jurisdiction_ref: str = Field(min_length=1)
    capability_revision: int = Field(ge=1)
    policy_revision: str = Field(min_length=1)
    effective_tick: int = Field(ge=0)
    status: Literal["active", "revoked"]
    visibility: CapabilityVisibility
    source_event_refs: tuple[str, ...]
    digest: str = Field(min_length=1)


class CivilizationCapabilityViewResult(StrictGameplayModel):
    accepted: bool
    view: CivilizationCapabilityView | None = None
    error_code: str | None = None


class CivilizationCapabilityAuthority:
    """Narrow event-sourced owner for civilization capability lifecycle facts.

    It deliberately owns neither advancement nor consumer eligibility.  The
    existing gameplay store remains the sole writer and replay source.
    """

    _PRINCIPAL = "authority:civilization_capability"
    _STREAM_PREFIX = "gameplay:civilization_capability:"
    _EVENT_PREFIX = "gameplay.civilization_capability."

    def __init__(self, *, store: GameplayEventStore) -> None:
        self.store = store

    @classmethod
    def capability_stream_id(cls, *, jurisdiction_ref: str) -> str:
        return f"{cls._STREAM_PREFIX}{jurisdiction_ref}"

    @classmethod
    def canonical_contract(cls) -> dict[str, object]:
        return {
            "owner": cls._PRINCIPAL,
            "stream_pattern": f"{cls._STREAM_PREFIX}{{jurisdiction_ref}}",
            "event_types": (
                f"{cls._EVENT_PREFIX}activated",
                f"{cls._EVENT_PREFIX}revoked",
                f"{cls._EVENT_PREFIX}corrected",
            ),
            "write_path": (
                "authority -> GameplayCommandEnvelope/SettlementPlan -> "
                "GameplayEventStore.append_batch -> outbox/replay -> scoped projection"
            ),
            "consumer_binding": "not_admitted",
            "progression": "not_admitted",
        }

    def activate(self, *, envelope: GameplayCommandEnvelope, record: CivilizationCapabilityRecord) -> AppendBatchResult:
        return self._write_record(envelope=envelope, record=record, operation="activated")

    def correct(self, *, envelope: GameplayCommandEnvelope, record: CivilizationCapabilityRecord) -> AppendBatchResult:
        return self._write_record(envelope=envelope, record=record, operation="corrected")

    def revoke(
        self,
        *,
        envelope: GameplayCommandEnvelope,
        capability_ref: str,
        jurisdiction_ref: str,
    ) -> AppendBatchResult:
        if not capability_ref or not jurisdiction_ref:
            return self._rejected(envelope, "civilization_capability_identity_invalid")
        stream_id = self.capability_stream_id(jurisdiction_ref=jurisdiction_ref)
        if not self._is_owner(envelope):
            return self._rejected(envelope, "civilization_capability_authority_required")
        existing_idempotency = self.store.get_by_idempotency(envelope.principal_ref, envelope.idempotency_key)
        projected = self._project_authority().get((jurisdiction_ref, capability_ref))
        if existing_idempotency is None and projected is None:
            return self._rejected(envelope, "civilization_capability_unknown")
        return self._append(
            envelope=envelope,
            stream_id=stream_id,
            operation="revoked",
            payload={
                "capability_ref": capability_ref,
                "jurisdiction_ref": jurisdiction_ref,
                "prior_capability_revision": int(projected["capability_revision"]) if projected is not None else 0,
            },
            visibility="authority_only",
        )

    def view_for(
        self,
        *,
        capability_ref: str,
        jurisdiction_ref: str,
        reader_scope: ReaderScope,
        now_tick: int,
        expected_capability_revision: int | None = None,
    ) -> CivilizationCapabilityViewResult:
        if now_tick < 0:
            return CivilizationCapabilityViewResult(accepted=False, error_code="civilization_capability_tick_invalid")
        projection = self._project_authority()
        selected = projection.get((jurisdiction_ref, capability_ref))
        if selected is None:
            known_jurisdictions = {key[0] for key in projection if key[1] == capability_ref}
            return CivilizationCapabilityViewResult(
                accepted=False,
                error_code=("civilization_capability_jurisdiction_mismatch" if known_jurisdictions else "civilization_capability_unknown"),
            )
        if expected_capability_revision is not None and selected["capability_revision"] != expected_capability_revision:
            return CivilizationCapabilityViewResult(accepted=False, error_code="civilization_capability_revision_conflict")
        if selected["status"] == "revoked":
            return CivilizationCapabilityViewResult(accepted=False, error_code="civilization_capability_revoked")
        if now_tick < selected["effective_tick"]:
            return CivilizationCapabilityViewResult(accepted=False, error_code="civilization_capability_not_effective")
        if not self._visible_to(scope=reader_scope, visibility=selected["visibility"]):
            return CivilizationCapabilityViewResult(accepted=False, error_code="civilization_capability_scope_denied")
        view_payload = dict(selected)
        view_payload["source_event_refs"] = tuple(selected["source_event_refs"])
        view_payload["digest"] = _digest(view_payload)
        return CivilizationCapabilityViewResult(accepted=True, view=CivilizationCapabilityView.model_validate(view_payload))

    def replay(self, *, checkpoint_at: int | None = None):
        replay = GameplayProjectionReplay(projector_id="infra-civilization-capability-read", projector_version="1")
        events = self._events()
        if checkpoint_at is None:
            return replay.full_replay(events)
        checkpoint = replay.create_checkpoint(events[:checkpoint_at])
        return replay.checkpoint_plus_tail_replay(checkpoint, events[checkpoint_at:])

    def _write_record(
        self,
        *,
        envelope: GameplayCommandEnvelope,
        record: CivilizationCapabilityRecord,
        operation: Literal["activated", "corrected"],
    ) -> AppendBatchResult:
        if not self._is_owner(envelope):
            return self._rejected(envelope, "civilization_capability_authority_required")
        stream_id = self.capability_stream_id(jurisdiction_ref=record.jurisdiction_ref)
        existing_idempotency = self.store.get_by_idempotency(envelope.principal_ref, envelope.idempotency_key)
        projected = self._project_authority().get((record.jurisdiction_ref, record.capability_ref))
        if existing_idempotency is None and operation == "corrected" and (projected is None or projected["status"] == "revoked"):
            return self._rejected(envelope, "civilization_capability_correction_unavailable")
        payload = record.model_dump(mode="json")
        if operation == "activated":
            payload["prior_capability_revision"] = 0
        else:
            payload["prior_capability_revision"] = max(int(projected["capability_revision"]) - 1, 0) if projected is not None else 0
        return self._append(
            envelope=envelope,
            stream_id=stream_id,
            operation=operation,
            payload=payload,
            visibility=record.visibility,
        )

    def _append(
        self,
        *,
        envelope: GameplayCommandEnvelope,
        stream_id: str,
        operation: Literal["activated", "corrected", "revoked"],
        payload: dict[str, object],
        visibility: CapabilityVisibility,
    ) -> AppendBatchResult:
        if envelope.expected_revisions != {stream_id: self.store.get_stream_head(stream_id)} and self.store.get_by_idempotency(envelope.principal_ref, envelope.idempotency_key) is None:
            return self._rejected(envelope, "revision_conflict")
        try:
            fragment = OwnerAuthorizedFragment(
                fragment_id=f"fragment:civilization-capability:{operation}:{payload['capability_ref']}:{envelope.command_id}",
                owner_principal_ref=self._PRINCIPAL,
                source_rule_ref=f"civilization-capability:{operation}:v1",
                expected_revisions=dict(envelope.expected_revisions),
                pinned_revisions={"policy": 1},
                event_specs={stream_id: ((f"{self._EVENT_PREFIX}{operation}", payload),)},
                event_visibility_policies={stream_id: (visibility,)},
            )
            batch = build_multi_stream_atomic_event_batch_from_fragments(
                command_id=envelope.command_id,
                idempotency_principal_ref=envelope.principal_ref,
                idempotency_key=envelope.idempotency_key,
                causation_id=envelope.causation_id,
                correlation_id=envelope.correlation_id,
                fragments=(fragment,),
            )
            event = batch.events[0]
            batch = batch.model_copy(
                update={
                    "outbox_entries": [
                        GameplayOutboxEntry(
                            outbox_id=f"outbox:{event.event_id}",
                            transaction_id=batch.transaction_id,
                            event_id=event.event_id,
                            global_sequence=0,
                            topic="world.civilization_capability.scoped_projection",
                            audience=event.visibility_policy,
                            payload_projection={
                                "capability_ref": payload["capability_ref"],
                                "jurisdiction_ref": payload["jurisdiction_ref"],
                                "event_type": event.event_type,
                            },
                        )
                    ]
                },
                deep=True,
            )
        except ValueError as exc:
            return self._rejected(envelope, str(exc))
        return self.store.append_batch(batch)

    def _project_authority(self) -> dict[tuple[str, str], dict[str, object]]:
        projection: dict[tuple[str, str], dict[str, object]] = {}
        for event in self._events():
            payload = event.payload
            jurisdiction_ref = str(payload.get("jurisdiction_ref", ""))
            capability_ref = str(payload.get("capability_ref", ""))
            key = (jurisdiction_ref, capability_ref)
            if not jurisdiction_ref or not capability_ref:
                continue
            previous = projection.get(key)
            if event.event_type == f"{self._EVENT_PREFIX}activated":
                projection[key] = self._active_projection(payload=payload, event_id=event.event_id, revision=1)
                continue
            if previous is None:
                continue
            event_refs = tuple((*previous["source_event_refs"], event.event_id))
            if event.event_type == f"{self._EVENT_PREFIX}corrected":
                projection[key] = self._active_projection(
                    payload=payload,
                    event_id=event.event_id,
                    revision=int(previous["capability_revision"]) + 1,
                    source_event_refs=event_refs,
                )
            elif event.event_type == f"{self._EVENT_PREFIX}revoked":
                projection[key] = {**previous, "status": "revoked", "source_event_refs": event_refs}
        return projection

    @staticmethod
    def _active_projection(
        *,
        payload: dict[str, object],
        event_id: str,
        revision: int,
        source_event_refs: tuple[str, ...] | None = None,
    ) -> dict[str, object]:
        return {
            "capability_ref": str(payload["capability_ref"]),
            "jurisdiction_ref": str(payload["jurisdiction_ref"]),
            "capability_revision": revision,
            "policy_revision": str(payload["policy_revision"]),
            "effective_tick": int(payload["effective_tick"]),
            "status": "active",
            "visibility": str(payload["visibility"]),
            "source_event_refs": source_event_refs or (event_id,),
        }

    def _events(self):
        return [event for event in self.store.read_events() if event.stream_id.startswith(self._STREAM_PREFIX)]

    @classmethod
    def _is_owner(cls, envelope: GameplayCommandEnvelope) -> bool:
        return envelope.principal_ref == cls._PRINCIPAL and envelope.source_ref == cls._PRINCIPAL

    @staticmethod
    def _visible_to(*, scope: ReaderScope, visibility: object) -> bool:
        if scope == "authority":
            return True
        if visibility == "project":
            return True
        return visibility == f"{scope}_only"

    @staticmethod
    def _rejected(envelope: GameplayCommandEnvelope, error_code: str) -> AppendBatchResult:
        return AppendBatchResult(
            committed=False,
            transaction_id=envelope.transaction_id or f"transaction:{envelope.command_id}",
            command_id=envelope.command_id,
            idempotency_status="rejected",
            failure={
                "error_code": error_code,
                "message": error_code,
                "failed_stage": "civilization_capability_admission",
            },
        )


__all__ = [
    "CivilizationCapabilityAuthority",
    "CivilizationCapabilityRecord",
    "CivilizationCapabilityView",
    "CivilizationCapabilityViewResult",
]
