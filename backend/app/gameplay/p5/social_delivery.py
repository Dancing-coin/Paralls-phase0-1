"""Recipient-scoped Social delivery records.

This is the first production delivery slice designed and implemented in this
stage. It keeps world validity (the effective window) separate from the
operational submission cutoff and uses the existing Gameplay ledger/outbox.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayEvent, GameplayOutboxEntry, OwnerAuthorizedFragment
from app.gameplay.p5.social_knowledge import _is_visible
from app.gameplay.settlement_plan import build_atomic_event_batch


_PRINCIPAL = "authority:p5:social-delivery"
_RECORDED = "gameplay.social.delivery_recorded@1"
_EXPIRED = "gameplay.social.delivery_expired@1"
_REVOCATION = "gameplay.social.visibility_revoked"


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


def _delivery_stream(recipient_ref: str, delivery_ref: str) -> str:
    return f"gameplay:social:delivery:{recipient_ref}:{delivery_ref}"


@dataclass(frozen=True)
class SocialDeliveryWindow:
    effective_from: int
    effective_to: int
    operational_cutoff: int | None

    def validate(self) -> str | None:
        if self.effective_from < 0 or self.effective_to <= self.effective_from:
            return "social_delivery_world_window_invalid"
        if self.operational_cutoff is not None and self.operational_cutoff < 0:
            return "social_delivery_operational_cutoff_invalid"
        return None


@dataclass(frozen=True)
class SocialDeliveryResult:
    committed: bool
    error_code: str | None = None
    append_result: AppendBatchResult | None = None


@dataclass(frozen=True)
class SocialDeliveryView:
    recipient_ref: str
    deliveries: tuple[dict[str, object], ...]
    source_revision_vector: dict[str, int]
    projection_hash: str


class SocialDeliveryAuthority:
    """Owner/caller for one recipient-scoped Social delivery lifecycle."""

    def __init__(self, *, store: GameplayEventStore) -> None:
        self._store = store

    def record_delivery(
        self,
        *,
        delivery_ref: str,
        source_stream_id: str,
        source_revision: int,
        source_event_id: str,
        recipient_ref: str,
        window: SocialDeliveryWindow,
        world_now: int,
        operational_now: int | None = None,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> SocialDeliveryResult:
        window_error = window.validate()
        if window_error or not all((delivery_ref, source_stream_id, source_event_id, recipient_ref, command_id, idempotency_key)):
            return SocialDeliveryResult(False, window_error or "social_delivery_identity_invalid")
        # A committed request is recovered from its receipt before testing
        # present-time admission. Recovery never creates a new delivery.
        existing = self._store.get_idempotency_record(_PRINCIPAL, idempotency_key)
        if existing is not None:
            result = self._store.get_by_idempotency(_PRINCIPAL, idempotency_key)
            prior = self._prior_event(result)
            identity = {
                "delivery_ref": delivery_ref, "source_stream_id": source_stream_id,
                "source_revision": source_revision, "source_event_id": source_event_id,
                "recipient_ref": recipient_ref, "effective_from": window.effective_from,
                "effective_to": window.effective_to, "operational_cutoff": window.operational_cutoff,
            }
            if (prior is not None and prior.event_type == _RECORDED
                    and prior.command_id == command_id
                    and prior.causation_id == causation_id
                    and prior.correlation_id == correlation_id
                    and all(prior.payload.get(key) == value for key, value in identity.items())):
                return SocialDeliveryResult(True, "duplicate_replayed", result)
            return SocialDeliveryResult(False, "idempotency_key_reused")
        if world_now < window.effective_from or world_now >= window.effective_to:
            return SocialDeliveryResult(False, "social_delivery_world_window_closed")
        if window.operational_cutoff is not None:
            if type(operational_now) is not int or operational_now < 0:
                return SocialDeliveryResult(False, "social_delivery_operational_time_invalid")
            if operational_now > window.operational_cutoff:
                return SocialDeliveryResult(False, "social_delivery_operational_late")
        source = self._source_event(source_stream_id, source_event_id)
        if source is None:
            return SocialDeliveryResult(False, "social_delivery_source_missing")
        if source_revision != self._store.get_stream_head(source_stream_id) or source.stream_revision != source_revision:
            return SocialDeliveryResult(False, "social_delivery_source_revision_stale")
        if not self._source_visible(source, recipient_ref) or self._revoked(source, recipient_ref):
            return SocialDeliveryResult(False, "social_delivery_visibility_revoked")
        stream_id = _delivery_stream(recipient_ref, delivery_ref)
        payload = {
            "delivery_ref": delivery_ref,
            "source_stream_id": source_stream_id,
            "source_revision": source_revision,
            "source_event_id": source_event_id,
            "source_payload_digest": _digest(source.payload),
            "recipient_ref": recipient_ref,
            "visibility": "actor:" + recipient_ref,
            "effective_from": window.effective_from,
            "effective_to": window.effective_to,
            "operational_cutoff": window.operational_cutoff,
        }
        batch = build_atomic_event_batch(
            command_id=command_id,
            principal_ref=_PRINCIPAL,
            stream_id=stream_id,
            expected_revision=self._store.get_stream_head(stream_id),
            read_stream_revisions={source_stream_id: self._store.get_stream_head(source_stream_id)},
            event_specs=((_RECORDED, payload),),
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
        )
        batch = batch.model_copy(update={
            "events": [event.model_copy(update={"visibility_policy": f"actor:{recipient_ref}"}, deep=True) for event in batch.events],
            "read_stream_revisions": {source_stream_id: source_revision},
            "owner_fragments": [OwnerAuthorizedFragment(
                fragment_id=f"fragment:social-delivery:{command_id}",
                owner_principal_ref=_PRINCIPAL,
                source_rule_ref="social-delivery:recipient-window@1",
                expected_revisions={stream_id: self._store.get_stream_head(stream_id)},
                read_set_revisions={source_stream_id: source_revision},
                pinned_revisions={},
                event_specs={stream_id: ((_RECORDED, payload),)},
                event_visibility_policies={stream_id: (f"actor:{recipient_ref}",)},
            )],
            "outbox_entries": [GameplayOutboxEntry(
                outbox_id=f"outbox:event:{command_id}:1",
                transaction_id=batch.transaction_id,
                event_id=f"event:{command_id}:1",
                global_sequence=0,
                topic="social.delivery.recipient_projection",
                audience=f"actor:{recipient_ref}",
                payload_projection={"delivery_ref": delivery_ref, "recipient_ref": recipient_ref, "status": "recorded"},
            )],
        }, deep=True)
        result = self._store.append_batch(batch)
        return SocialDeliveryResult(result.committed, None if result.committed else (result.failure.error_code if result.failure else "social_delivery_append_failed"), result)

    def expire_delivery(
        self, *, delivery_ref: str, recipient_ref: str, world_now: int, operational_now: int | None = None,
        command_id: str, idempotency_key: str, causation_id: str, correlation_id: str,
    ) -> SocialDeliveryResult:
        stream_id = _delivery_stream(recipient_ref, delivery_ref)
        events = self._store.read_events(event_type=_RECORDED)
        recorded = next((event for event in events if event.stream_id == stream_id), None)
        if recorded is None:
            return SocialDeliveryResult(False, "social_delivery_missing")
        payload = recorded.payload
        digest_payload = {"delivery_ref": delivery_ref, "recipient_ref": recipient_ref, "world_now": world_now, "operational_now": operational_now}
        batch = build_atomic_event_batch(
            command_id=command_id, principal_ref=_PRINCIPAL, stream_id=stream_id,
            expected_revision=self._store.get_stream_head(stream_id),
            event_specs=((_EXPIRED, digest_payload),), idempotency_key=idempotency_key,
            causation_id=causation_id, correlation_id=correlation_id,
        )
        existing = self._store.get_idempotency_record(_PRINCIPAL, idempotency_key)
        if existing is not None:
            result = self._store.get_by_idempotency(_PRINCIPAL, idempotency_key)
            prior = self._prior_event(result)
            if prior is not None and prior.event_type == _EXPIRED and prior.payload == digest_payload:
                if (
                    prior.command_id != command_id
                    or prior.causation_id != causation_id
                    or prior.correlation_id != correlation_id
                    or prior.transaction_id != result.transaction_id
                ):
                    return SocialDeliveryResult(False, "idempotency_key_reused")
                return SocialDeliveryResult(True, "duplicate_replayed", result)
            return SocialDeliveryResult(False, "idempotency_key_reused")
        source = self._source_event(str(payload["source_stream_id"]), str(payload["source_event_id"]))
        if source is None or self._revoked(source, recipient_ref):
            return SocialDeliveryResult(False, "social_delivery_visibility_revoked")
        if (
            source.stream_revision != int(payload["source_revision"])
            or self._store.get_stream_head(str(payload["source_stream_id"])) != int(payload["source_revision"])
            or _digest(source.payload) != payload.get("source_payload_digest")
        ):
            return SocialDeliveryResult(False, "social_delivery_source_revision_stale")
        if payload.get("operational_cutoff") is not None:
            if type(operational_now) is not int or operational_now < 0:
                return SocialDeliveryResult(False, "social_delivery_operational_time_invalid")
            if operational_now > int(payload["operational_cutoff"]):
                return SocialDeliveryResult(False, "social_delivery_operational_late")
        if world_now < int(payload["effective_to"]):
            return SocialDeliveryResult(False, "social_delivery_world_window_open")
        batch = batch.model_copy(update={
            "events": [event.model_copy(update={"visibility_policy": f"actor:{recipient_ref}"}, deep=True) for event in batch.events],
            "owner_fragments": [OwnerAuthorizedFragment(
                fragment_id=f"fragment:social-delivery-expiry:{command_id}", owner_principal_ref=_PRINCIPAL,
                source_rule_ref="social-delivery:expiry@1", expected_revisions={stream_id: recorded.stream_revision},
                read_set_revisions={str(payload["source_stream_id"]): int(payload["source_revision"])}, pinned_revisions={},
                event_specs={stream_id: ((_EXPIRED, digest_payload),)}, event_visibility_policies={stream_id: (f"actor:{recipient_ref}",)},
            )],
            "outbox_entries": [GameplayOutboxEntry(
                outbox_id=f"outbox:event:{command_id}:1", transaction_id=batch.transaction_id, event_id=f"event:{command_id}:1",
                global_sequence=0, topic="social.delivery.recipient_projection", audience=f"actor:{recipient_ref}",
                payload_projection={"delivery_ref": delivery_ref, "recipient_ref": recipient_ref, "status": "expired"},
            )],
        }, deep=True)
        result = self._store.append_batch(batch)
        return SocialDeliveryResult(result.committed, None if result.committed else (result.failure.error_code if result.failure else "social_delivery_expiry_failed"), result)

    def view_for(self, *, recipient_ref: str, world_now: int, checkpoint_at: int | None = None) -> SocialDeliveryView:
        """Build the recipient projection at an optional global-sequence cut.

        The cut is read from the same GameplayEventStore used by the live
        authority.  It is therefore a replay boundary, rather than a second
        projection store.  Events after the boundary cannot affect either the
        delivery rows or their source/revocation checks.
        """
        if checkpoint_at is not None and checkpoint_at < 0:
            raise ValueError("social_delivery_checkpoint_invalid")
        if checkpoint_at is not None:
            latest = self._store.read_events()
            latest_sequence = latest[-1].global_sequence if latest else 0
            if checkpoint_at > latest_sequence:
                raise ValueError("social_delivery_checkpoint_future")
        historical = self._read_events_at(checkpoint_at)
        rows: list[dict[str, object]] = []
        revisions: dict[str, int] = {}
        recorded_events = [event for event in historical if event.event_type == _RECORDED]
        for event in recorded_events:
            payload = event.payload
            if payload.get("recipient_ref") != recipient_ref:
                continue
            if any(e.stream_id == event.stream_id and e.event_type == _EXPIRED for e in historical):
                continue
            source = self._source_event(
                str(payload.get("source_stream_id")), str(payload.get("source_event_id")),
                events=historical,
            )
            if (source is None or _digest(source.payload) != payload.get("source_payload_digest")
                    or self._revoked(source, recipient_ref, events=historical)
                    or not self._source_visible(source, recipient_ref)):
                continue
            if not (int(payload["effective_from"]) <= world_now < int(payload["effective_to"])):
                continue
            rows.append(dict(payload))
            revisions[str(payload["source_stream_id"])] = int(payload["source_revision"])
        return SocialDeliveryView(recipient_ref, tuple(rows), revisions, _digest(rows))

    def _read_events_at(self, checkpoint_at: int | None) -> list[GameplayEvent]:
        if checkpoint_at is None:
            return self._store.read_events()
        return [event for event in self._store.read_events() if event.global_sequence <= checkpoint_at]

    def _source_event(self, stream_id: str, event_id: str, *, events: list[GameplayEvent] | None = None) -> GameplayEvent | None:
        if events is not None:
            return next((event for event in events if event.event_id == event_id and event.stream_id == stream_id), None)
        try:
            event = self._store.get_event(event_id)
        except KeyError:
            return None
        return event if event.stream_id == stream_id else None

    def _prior_event(self, result: AppendBatchResult | None) -> GameplayEvent | None:
        if result is None or not result.committed or len(result.committed_event_ids) != 1:
            return None
        batch = self._store.get_transaction(result.transaction_id)
        if batch is None or tuple(event.event_id for event in batch.events) != tuple(result.committed_event_ids):
            return None
        try:
            return self._store.get_event(result.committed_event_ids[0])
        except KeyError:
            return None

    def _revoked(self, source: GameplayEvent, recipient_ref: str, *, events: list[GameplayEvent] | None = None) -> bool:
        events = self._store.read_events() if events is None else events
        return any(
            event.event_type == _REVOCATION
            and event.payload.get("recipient_ref") == recipient_ref
            and (
                event.payload.get("source_event_id") == source.event_id
                or (event.stream_id == source.stream_id and event.payload.get("fact_ref") == source.payload.get("fact_ref"))
            )
            for event in events
        )

    @staticmethod
    def _source_visible(source: GameplayEvent, recipient_ref: str) -> bool:
        # Government public milling notices are project-visible source facts;
        # the admitted caller may project them into a recipient-private stream.
        if (
            source.event_type == "gameplay.government.public_milling_notice_recorded"
            and source.visibility_policy == "project"
            and source.payload.get("notice_kind") == "public_milling_session_completed"
            and source.payload.get("status") == "completed"
            and source.payload.get("project_ref")
        ):
            return True
        return _is_visible(source.visibility_policy, recipient_ref)


__all__ = ["SocialDeliveryAuthority", "SocialDeliveryResult", "SocialDeliveryView", "SocialDeliveryWindow"]
