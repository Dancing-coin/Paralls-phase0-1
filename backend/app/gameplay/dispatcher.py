from __future__ import annotations

from typing import Callable, Protocol

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AtomicEventBatch, DispatchResult, GameplayEvent, GameplayOutboxEntry
from app.models.authority_event import AuthorityEvent, AuthorityEventRouting, AuthorityEventSource
from app.services.authority_event_bus import AuthorityEventBusPort


class GameplayOutboxDispatcher:
    def __init__(
        self,
        *,
        store: GameplayEventStore,
        bus: AuthorityEventBusPort,
        after_transaction_dispatched: Callable[[AtomicEventBatch], None] | None = None,
    ) -> None:
        self._store = store
        self._bus = bus
        self._after_transaction_dispatched = after_transaction_dispatched
        self._notified_transaction_ids: set[str] = set()

    def dispatch_pending(self, *, limit: int | None = None) -> DispatchResult:
        entries = self._store.list_outbox(include_delivered=False)
        if limit is not None:
            entries = entries[:limit]
        published: list[str] = []
        failed: list[str] = []
        for entry in entries:
            try:
                event = self._store.get_event(entry.event_id)
                self._bus.publish(self._authority_event_for(entry, event))
            except Exception as exc:  # publish failure must not roll back committed truth
                self._store.mark_outbox_retryable(entry.outbox_id, str(exc))
                failed.append(entry.outbox_id)
                continue
            self._store.mark_outbox_delivered(entry.outbox_id)
            published.append(entry.outbox_id)
            self._notify_if_transaction_fully_dispatched(entry.transaction_id)
        return DispatchResult(
            published_count=len(published),
            failed_count=len(failed),
            delivered_outbox_ids=published,
            failed_outbox_ids=failed,
        )

    def _notify_if_transaction_fully_dispatched(self, transaction_id: str) -> None:
        if self._after_transaction_dispatched is None or transaction_id in self._notified_transaction_ids:
            return
        transaction = next(
            (batch for batch in self._store.read_transactions() if batch.transaction_id == transaction_id),
            None,
        )
        if transaction is None or not transaction.outbox_entries:
            return
        delivery_by_id = {entry.outbox_id: entry.delivery_state for entry in self._store.list_outbox()}
        if any(delivery_by_id.get(entry.outbox_id) != "delivered" for entry in transaction.outbox_entries):
            return
        self._notified_transaction_ids.add(transaction_id)
        try:
            self._after_transaction_dispatched(transaction)
        except Exception:
            # The outbox publication is already durable and cannot be rolled back by a mirror observer.
            return

    @staticmethod
    def _authority_event_for(entry: GameplayOutboxEntry, event: GameplayEvent) -> AuthorityEvent:
        projection = entry.payload_projection
        payload = dict(projection.get("payload", {})) if isinstance(projection.get("payload", {}), dict) else {}
        payload.update(
            {
                "outbox_id": entry.outbox_id,
                "transaction_id": event.transaction_id,
                "event_id": event.event_id,
                "stream_id": event.stream_id,
                "stream_revision": event.stream_revision,
                "global_sequence": event.global_sequence,
                "committed_payload": event.payload,
            }
        )
        source_payload = projection.get("source", {})
        routing_payload = projection.get("routing", {})
        source = source_payload if isinstance(source_payload, dict) else {}
        routing = routing_payload if isinstance(routing_payload, dict) else {}
        return AuthorityEvent(
            event_id=event.event_id,
            event_type=entry.topic,
            producer_ts=event.global_sequence,
            room_id=str(projection.get("room_id", "room_demo")),
            scene_id=str(projection.get("scene_id", "scene_demo")),
            zone_id=str(projection.get("zone_id", "zone_focus")),
            source=AuthorityEventSource(
                layer=str(source.get("layer", "gameplay")),
                system=str(source.get("system", "event_store_outbox")),
                actor_id=source.get("actor_id") if isinstance(source.get("actor_id"), str) else None,
            ),
            routing=AuthorityEventRouting(
                audience_mode=str(routing.get("audience_mode", entry.audience)),
                routing_mode=str(routing.get("routing_mode", "event_type")),
                target_ids=[str(target) for target in routing.get("target_ids", [])] if isinstance(routing.get("target_ids", []), list) else [],
            ),
            priority=projection.get("priority", "p1"),  # type: ignore[arg-type]
            ttl=int(projection["ttl"]) if "ttl" in projection and projection["ttl"] is not None else None,
            durability=projection.get("durability", "replayable"),  # type: ignore[arg-type]
            causation_id=event.causation_id,
            correlation_id=event.correlation_id,
            payload=payload,
        )


class StoreBackedSequenceSource(Protocol):
    def read_events(self, *, global_sequence_from: int | None = None, global_sequence_after: int | None = None, limit: int | None = None) -> list[GameplayEvent]:
        raise NotImplementedError


class GameplayBusSequenceConsumer:
    def __init__(self, *, store: StoreBackedSequenceSource, expected_next_global_sequence: int = 1) -> None:
        self._store = store
        self.expected_next_global_sequence = expected_next_global_sequence
        self._gap_start: int | None = None

    def consume(self, event: AuthorityEvent) -> str:
        sequence = int(event.payload.get("global_sequence", 0))
        if sequence != self.expected_next_global_sequence:
            self._gap_start = self.expected_next_global_sequence
            return "gap_detected"
        self.expected_next_global_sequence += 1
        return "accepted"

    def resync_from_store(self) -> list[GameplayEvent]:
        start = self._gap_start or self.expected_next_global_sequence
        return self._store.read_events(global_sequence_from=start)
