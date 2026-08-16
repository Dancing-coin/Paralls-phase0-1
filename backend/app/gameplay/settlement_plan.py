"""Pure adapters from shared gameplay contracts to the existing event-store batch."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from app.gameplay.models import AppendBatchResult, AtomicEventBatch, GameplayEvent, IdempotencyRecord, OwnerAuthorizedFragment
from app.gameplay.shared_contracts import GameplayCommandEnvelope, Reservation, SettlementReceipt


_FINAL_RESERVATION_STATES = frozenset({"final", "consumed", "released", "expired", "compensated"})


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _event_visibility_vector(
    stream_id: str,
    specs: Sequence[tuple[str, Mapping[str, Any]]],
    visibility_policies: Mapping[str, Sequence[str]] | None,
) -> tuple[str, ...]:
    policies = tuple((visibility_policies or {}).get(stream_id, ()))
    if not policies:
        return tuple("project" for _ in specs)
    if len(policies) != len(specs):
        raise ValueError("settlement_event_visibility_incomplete")
    if any(not policy for policy in policies):
        raise ValueError("settlement_event_visibility_invalid")
    return policies


def _fragment_digest_payload(
    *,
    command_id: str,
    idempotency_principal_ref: str,
    idempotency_key: str,
    causation_id: str,
    correlation_id: str,
    fragments: Sequence[OwnerAuthorizedFragment],
) -> dict[str, object]:
    return {
        "command": {
            "command_id": command_id,
            "idempotency_principal_ref": idempotency_principal_ref,
            "idempotency_key": idempotency_key,
            "causation_id": causation_id,
            "correlation_id": correlation_id,
        },
        "fragments": [
            {
                "fragment_id": fragment.fragment_id,
                "owner_principal_ref": fragment.owner_principal_ref,
                "source_rule_ref": fragment.source_rule_ref,
                "write_stream_revisions": dict(sorted(fragment.expected_revisions.items())),
                "read_stream_revisions": dict(sorted(fragment.read_set_revisions.items())),
                "pinned_revisions": dict(sorted(fragment.pinned_revisions.items())),
                "events": [
                    {
                        "stream_id": stream_id,
                        "event_type": event_type,
                        "schema_version": 1,
                        "visibility_policy": visibility_policy,
                        "payload": dict(payload),
                    }
                    for stream_id in sorted(fragment.event_specs)
                    for (event_type, payload), visibility_policy in zip(
                        fragment.event_specs[stream_id],
                        _event_visibility_vector(
                            stream_id,
                            fragment.event_specs[stream_id],
                            fragment.event_visibility_policies,
                        ),
                        strict=False,
                    )
                ],
            }
            for fragment in sorted(fragments, key=lambda item: item.fragment_id)
        ],
    }


def _single_stream_digest_payload(
    *,
    command_id: str,
    stream_id: str,
    expected_revision: int,
    event_specs: Sequence[tuple[str, Mapping[str, Any]]],
    read_stream_revisions: Mapping[str, int] | None,
    pinned_revisions: Mapping[str, int] | None,
) -> dict[str, object]:
    return {
        "command_id": command_id,
        "write_stream_revisions": {stream_id: expected_revision},
        "read_stream_revisions": dict(sorted((read_stream_revisions or {}).items())),
        "pinned_revisions": dict(sorted((pinned_revisions or {}).items())),
        "events": [
            {
                "stream_id": stream_id,
                "event_type": event_type,
                "schema_version": 1,
                "visibility_policy": "project",
                "payload": dict(payload),
            }
            for event_type, payload in event_specs
        ],
    }


def _multi_stream_digest_payload(
    *,
    command_id: str,
    expected_revisions: Mapping[str, int],
    event_specs: Mapping[str, Sequence[tuple[str, Mapping[str, Any]]]],
    read_stream_revisions: Mapping[str, int] | None,
    event_visibility_policies: Mapping[str, Sequence[str]] | None,
    pinned_revisions: Mapping[str, int] | None,
) -> dict[str, object]:
    return {
        "command_id": command_id,
        "write_stream_revisions": dict(sorted(expected_revisions.items())),
        "read_stream_revisions": dict(sorted((read_stream_revisions or {}).items())),
        "pinned_revisions": dict(sorted((pinned_revisions or {}).items())),
        "events": [
            {
                "stream_id": stream_id,
                "event_type": event_type,
                "schema_version": 1,
                "visibility_policy": visibility_policy,
                "payload": dict(payload),
            }
            for stream_id in sorted(event_specs)
            for (event_type, payload), visibility_policy in zip(
                event_specs[stream_id],
                _event_visibility_vector(stream_id, event_specs[stream_id], event_visibility_policies),
                strict=False,
            )
        ],
    }


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
        event_payload = dict(payload)
        event_payload.pop("stream_ref", None)
        event_payload.pop("event_type", None)
        raw_specs = payload.get("event_specs")
        if raw_specs is None:
            specs = ((event_type, event_payload),)
        elif isinstance(raw_specs, (list, tuple)) and raw_specs:
            specs = tuple(
                (str(item["event_type"]), dict(item["payload"]))
                for item in raw_specs
                if isinstance(item, dict) and "event_type" in item and "payload" in item
            )
            if len(specs) != len(raw_specs):
                raise ValueError("invalid_schema")
        else:
            raise ValueError("invalid_schema")
        events = [
            GameplayEvent(
                event_id=str(payload.get("event_id", f"event:{command.command_id}:{index}")),
                event_type=spec_event_type,
                schema_version=command.command_version,
                stream_id=stream_ref,
                stream_revision=0,
                global_sequence=0,
                transaction_id=transaction_id,
                command_id=command.command_id,
                causation_id=command.causation_id,
                correlation_id=command.correlation_id,
                visibility_policy=str(spec_payload.pop("visibility_policy", payload.get("visibility_policy", "project"))),
                payload=spec_payload,
            )
            for index, (spec_event_type, spec_payload) in enumerate(specs, start=1)
        ]
        return AtomicEventBatch(
            transaction_id=transaction_id,
            command_id=command.command_id,
            expected_stream_revisions=dict(command.expected_revisions),
            read_stream_revisions=dict(command.read_set_revisions),
            pinned_revisions=dict(command.pinned_revisions),
            events=events,
            idempotency_record=IdempotencyRecord(
                principal_ref=command.principal_ref,
                idempotency_key=command.idempotency_key,
                payload_digest=_digest(command.model_dump(mode="json")),
            ),
            result_digest=_digest({"command_id": command.command_id, "payload": payload}),
        )


@dataclass(frozen=True)
class AppendDerivedSettlementRecipe:
    """Pure composition of owner fragments and append-derived receipt facts.

    The recipe owns neither a store nor a commit callback. Existing authorities
    remain responsible for submitting ``batch`` through the one event-store
    append path.
    """

    batch: AtomicEventBatch

    @classmethod
    def from_fragments(
        cls,
        *,
        command_id: str,
        idempotency_principal_ref: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        fragments: Sequence[OwnerAuthorizedFragment],
    ) -> "AppendDerivedSettlementRecipe":
        return cls(
            batch=build_multi_stream_atomic_event_batch_from_fragments(
                command_id=command_id,
                idempotency_principal_ref=idempotency_principal_ref,
                idempotency_key=idempotency_key,
                causation_id=causation_id,
                correlation_id=correlation_id,
                fragments=fragments,
            )
        )

    def receipt_from_append_result(
        self,
        *,
        result: AppendBatchResult,
        audit_refs: tuple[str, ...] = (),
        pinned_revisions: Mapping[str, int] | None = None,
        projection_digests: Mapping[str, str] | None = None,
    ) -> SettlementReceipt:
        return SettlementReceipt.from_append_result(
            result=result,
            audit_refs=audit_refs,
            pinned_revisions=dict(pinned_revisions or {}),
            projection_digests=dict(projection_digests or {}),
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
    read_stream_revisions: Mapping[str, int] | None = None,
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
    digest = _digest(
        _single_stream_digest_payload(
            command_id=command_id,
            stream_id=stream_id,
            expected_revision=expected_revision,
            event_specs=event_specs,
            read_stream_revisions=read_stream_revisions,
            pinned_revisions=pinned_revisions,
        )
    )
    return AtomicEventBatch(
        transaction_id=transaction_id,
        command_id=command_id,
        expected_stream_revisions={stream_id: expected_revision},
        read_stream_revisions=dict(read_stream_revisions or {}),
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
    read_stream_revisions: Mapping[str, int] | None = None,
    event_visibility_policies: Mapping[str, Sequence[str]] | None = None,
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
        for index, ((event_type, payload), visibility_policy) in enumerate(
            zip(specs, _event_visibility_vector(stream_id, specs, event_visibility_policies), strict=False),
            start=1,
        ):
            events.append(GameplayEvent(
                event_id=f"event:{command_id}:{stream_id}:{index}", event_type=event_type, schema_version=1,
                stream_id=stream_id, stream_revision=0, global_sequence=0, transaction_id=transaction_id,
                command_id=command_id, causation_id=causation_id, correlation_id=correlation_id,
                visibility_policy=visibility_policy, payload=dict(payload),
            ))
    digest = _digest(
        _multi_stream_digest_payload(
            command_id=command_id,
            expected_revisions=expected_revisions,
            event_specs=event_specs,
            read_stream_revisions=read_stream_revisions,
            event_visibility_policies=event_visibility_policies,
            pinned_revisions=pinned_revisions,
        )
    )
    return AtomicEventBatch(
        transaction_id=transaction_id, command_id=command_id, expected_stream_revisions=dict(expected_revisions),
        read_stream_revisions=dict(read_stream_revisions or {}),
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
    read_stream_revisions: dict[str, int] = {}
    event_specs: dict[str, Sequence[tuple[str, Mapping[str, Any]]]] = {}
    event_visibility_policies: dict[str, Sequence[str]] = {}
    pinned_revisions: dict[str, int] = {}
    for fragment in sorted(fragments, key=lambda item: item.fragment_id):
        overlap = set(expected_revisions) & set(fragment.expected_revisions)
        if overlap:
            raise ValueError("settlement_fragment_stream_overlap")
        expected_revisions.update(fragment.expected_revisions)
        event_specs.update(fragment.event_specs)
        for stream_id, revision in fragment.read_set_revisions.items():
            prior = read_stream_revisions.get(stream_id)
            if prior is not None and prior != revision:
                raise ValueError("settlement_fragment_read_conflict")
            read_stream_revisions[stream_id] = revision
        for stream_id, policies in fragment.event_visibility_policies.items():
            event_visibility_policies[stream_id] = tuple(policies)
        for pin, revision in fragment.pinned_revisions.items():
            prior = pinned_revisions.get(pin)
            if prior is not None and prior != revision:
                raise ValueError("settlement_fragment_pin_conflict")
            pinned_revisions[pin] = revision
    digest = _digest(
        _fragment_digest_payload(
            command_id=command_id,
            idempotency_principal_ref=idempotency_principal_ref,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            fragments=fragments,
        )
    )
    batch = build_multi_stream_atomic_event_batch(
        command_id=command_id,
        principal_ref=idempotency_principal_ref,
        expected_revisions=expected_revisions,
        event_specs=event_specs,
        idempotency_key=idempotency_key,
        causation_id=causation_id,
        correlation_id=correlation_id,
        read_stream_revisions=read_stream_revisions,
        event_visibility_policies=event_visibility_policies,
        pinned_revisions=pinned_revisions,
    )
    return batch.model_copy(
        update={
            "owner_fragments": list(sorted(fragments, key=lambda item: item.fragment_id)),
            "idempotency_record": batch.idempotency_record.model_copy(update={"payload_digest": digest}, deep=True),
            "result_digest": digest,
        },
        deep=True,
    )


__all__ = [
    "AppendDerivedSettlementRecipe",
    "OwnerAuthorizedFragment",
    "SettlementPlan",
    "build_atomic_event_batch",
    "build_multi_stream_atomic_event_batch",
    "build_multi_stream_atomic_event_batch_from_fragments",
]
