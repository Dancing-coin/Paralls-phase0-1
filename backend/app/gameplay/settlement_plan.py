"""Pure adapters from shared gameplay contracts to the existing event-store batch."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from app.gameplay.models import AtomicEventBatch, GameplayEvent, IdempotencyRecord, OwnerAuthorizedFragment
from app.gameplay.shared_contracts import GameplayCommandEnvelope, Reservation


_FINAL_RESERVATION_STATES = frozenset({"final", "consumed", "released", "expired", "compensated"})


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class SettlementPlan:
    """A pre-commit mapping; it owns no state and never appends events."""

    command: GameplayCommandEnvelope
    reservation: Reservation | None = None

    @classmethod
    def from_command_envelope(cls, command: GameplayCommandEnvelope) -> "SettlementPlan":
        return cls(command=command)

    @classmethod
    def from_reservation(cls, reservation: Reservation) -> "SettlementPlan":
        if reservation.status in _FINAL_RESERVATION_STATES:
            raise ValueError("reservation_unknown_or_final")
        command = GameplayCommandEnvelope(
            command_id=f"command:{reservation.reservation_ref}",
            command_type=f"gameplay.reservation.{reservation.status}",
            command_version=1,
            principal_ref=reservation.owner_ref,
            actor_ref=None,
            project_ref=None,
            transaction_id=f"transaction:{reservation.reservation_ref}",
            idempotency_key=f"idempotency:{reservation.reservation_ref}:{reservation.status}",
            expected_revisions={reservation.target_ref: reservation.created_revision},
            causation_id=f"causation:{reservation.reservation_ref}",
            correlation_id=f"correlation:{reservation.reservation_ref}",
            source_ref=reservation.source_obligation_ref,
            submitted_at="reservation",
            pinned_revisions={},
            payload={
                "stream_ref": reservation.target_ref,
                "event_type": f"gameplay.reservation_{reservation.status}",
                "reservation_ref": reservation.reservation_ref,
            },
        )
        return cls(command=command, reservation=reservation)

    def to_atomic_event_batch(self) -> AtomicEventBatch:
        command = self.command
        payload = dict(command.payload)
        stream_ref = str(payload.get("stream_ref", ""))
        event_type = str(payload.get("event_type", command.command_type))
        if not stream_ref or not event_type:
            raise ValueError("invalid_schema")
        transaction_id = command.transaction_id or f"transaction:{command.command_id}"
        event_id = str(payload.get("event_id", f"event:{command.command_id}"))
        event_payload = dict(payload)
        event_payload.pop("stream_ref", None)
        event_payload.pop("event_type", None)
        event = GameplayEvent(
            event_id=event_id,
            event_type=event_type,
            schema_version=command.command_version,
            stream_id=stream_ref,
            stream_revision=0,
            global_sequence=0,
            transaction_id=transaction_id,
            command_id=command.command_id,
            causation_id=command.causation_id,
            correlation_id=command.correlation_id,
            visibility_policy=str(payload.get("visibility_policy", "project")),
            payload=event_payload,
        )
        return AtomicEventBatch(
            transaction_id=transaction_id,
            command_id=command.command_id,
            expected_stream_revisions=dict(command.expected_revisions),
            pinned_revisions=dict(command.pinned_revisions),
            events=[event],
            idempotency_record=IdempotencyRecord(
                principal_ref=command.principal_ref,
                idempotency_key=command.idempotency_key,
                payload_digest=_digest(command.model_dump(mode="json")),
            ),
            result_digest=_digest({"command_id": command.command_id, "payload": payload}),
        )


def build_atomic_event_batch(
    *,
    command_id: str,
    principal_ref: str,
    stream_id: str,
    expected_revision: int,
    event_specs: Sequence[tuple[str, Mapping[str, Any]]],
    idempotency_key: str,
    causation_id: str,
    correlation_id: str,
    pinned_revisions: Mapping[str, int] | None = None,
) -> AtomicEventBatch:
    """Build one owner-scoped batch for a domain authority to submit.

    This remains a pure adapter: callers still choose the owning stream and must
    submit the returned batch through the existing ``GameplayEventStore``.
    """
    if not event_specs:
        raise ValueError("settlement_events_required")
    transaction_id = f"transaction:{command_id}"
    events = [
        GameplayEvent(
            event_id=f"event:{command_id}:{index}",
            event_type=event_type,
            schema_version=1,
            stream_id=stream_id,
            stream_revision=0,
            global_sequence=0,
            transaction_id=transaction_id,
            command_id=command_id,
            causation_id=causation_id,
            correlation_id=correlation_id,
            visibility_policy="project",
            payload=dict(payload),
        )
        for index, (event_type, payload) in enumerate(event_specs, start=1)
    ]
    command_payload = {
        "command_id": command_id,
        "stream_id": stream_id,
        "expected_revision": expected_revision,
        "events": [(event_type, dict(payload)) for event_type, payload in event_specs],
    }
    digest = _digest(command_payload)
    return AtomicEventBatch(
        transaction_id=transaction_id,
        command_id=command_id,
        expected_stream_revisions={stream_id: expected_revision},
        pinned_revisions=dict(pinned_revisions or {}),
        events=events,
        idempotency_record=IdempotencyRecord(
            principal_ref=principal_ref,
            idempotency_key=idempotency_key,
            payload_digest=digest,
        ),
        result_digest=digest,
    )


def build_multi_stream_atomic_event_batch(
    *,
    command_id: str,
    principal_ref: str,
    expected_revisions: Mapping[str, int],
    event_specs: Mapping[str, Sequence[tuple[str, Mapping[str, Any]]]],
    idempotency_key: str,
    causation_id: str,
    correlation_id: str,
    pinned_revisions: Mapping[str, int] | None = None,
) -> AtomicEventBatch:
    """Compose owner proposals into one batch without choosing domain outcomes."""
    if not expected_revisions or set(event_specs) != set(expected_revisions):
        raise ValueError("settlement_revision_vector_incomplete")
    transaction_id = f"transaction:{command_id}"
    events: list[GameplayEvent] = []
    for stream_id in sorted(event_specs):
        specs = event_specs[stream_id]
        if not specs:
            raise ValueError("settlement_events_required")
        for index, (event_type, payload) in enumerate(specs, start=1):
            events.append(GameplayEvent(
                event_id=f"event:{command_id}:{stream_id}:{index}", event_type=event_type, schema_version=1,
                stream_id=stream_id, stream_revision=0, global_sequence=0, transaction_id=transaction_id,
                command_id=command_id, causation_id=causation_id, correlation_id=correlation_id,
                visibility_policy="project", payload=dict(payload),
            ))
    digest = _digest({"command_id": command_id, "expected_revisions": dict(expected_revisions), "events": [(event.stream_id, event.event_type, event.payload) for event in events]})
    return AtomicEventBatch(
        transaction_id=transaction_id, command_id=command_id, expected_stream_revisions=dict(expected_revisions),
        pinned_revisions=dict(pinned_revisions or {}), events=events,
        idempotency_record=IdempotencyRecord(principal_ref=principal_ref, idempotency_key=idempotency_key, payload_digest=digest), result_digest=digest,
    )


def build_multi_stream_atomic_event_batch_from_fragments(
    *,
    command_id: str,
    idempotency_principal_ref: str,
    idempotency_key: str,
    causation_id: str,
    correlation_id: str,
    fragments: Sequence[OwnerAuthorizedFragment],
) -> AtomicEventBatch:
    """Merge disjoint owner-authorized proposals into the one existing append path."""
    if not fragments:
        raise ValueError("settlement_fragments_required")
    expected_revisions: dict[str, int] = {}
    event_specs: dict[str, Sequence[tuple[str, Mapping[str, Any]]]] = {}
    pinned_revisions: dict[str, int] = {}
    for fragment in sorted(fragments, key=lambda item: item.fragment_id):
        overlap = set(expected_revisions) & set(fragment.expected_revisions)
        if overlap:
            raise ValueError("settlement_fragment_stream_overlap")
        expected_revisions.update(fragment.expected_revisions)
        event_specs.update(fragment.event_specs)
        for pin, revision in fragment.pinned_revisions.items():
            prior = pinned_revisions.get(pin)
            if prior is not None and prior != revision:
                raise ValueError("settlement_fragment_pin_conflict")
            pinned_revisions[pin] = revision
    batch = build_multi_stream_atomic_event_batch(
        command_id=command_id,
        principal_ref=idempotency_principal_ref,
        expected_revisions=expected_revisions,
        event_specs=event_specs,
        idempotency_key=idempotency_key,
        causation_id=causation_id,
        correlation_id=correlation_id,
        pinned_revisions=pinned_revisions,
    )
    return batch.model_copy(update={"owner_fragments": list(sorted(fragments, key=lambda item: item.fragment_id))}, deep=True)


__all__ = [
    "OwnerAuthorizedFragment",
    "SettlementPlan",
    "build_atomic_event_batch",
    "build_multi_stream_atomic_event_batch",
    "build_multi_stream_atomic_event_batch_from_fragments",
]
