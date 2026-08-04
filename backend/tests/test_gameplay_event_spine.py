from __future__ import annotations

import pytest

from app.gameplay.dispatcher import GameplayBusSequenceConsumer, GameplayOutboxDispatcher
from app.gameplay.event_store import GameplayEventStore
from app.models.authority_event import AuthorityEvent
from app.services.authority_event_bus import InMemoryAuthorityEventBus

from test_gameplay_event_store_contract import _batch, _event, _outbox


class FlakyBus(InMemoryAuthorityEventBus):
    def __init__(self) -> None:
        super().__init__()
        self.fail_next = True

    def publish(self, event: AuthorityEvent) -> None:
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("simulated bus failure")
        super().publish(event)


def test_dispatcher_publishes_only_committed_outbox_after_append_batch() -> None:
    store = GameplayEventStore()
    bus = InMemoryAuthorityEventBus()
    dispatcher = GameplayOutboxDispatcher(store=store, bus=bus)

    assert dispatcher.dispatch_pending().published_count == 0
    assert bus.list_events() == []

    commit = store.append_batch(_batch(events=[_event("evt:session:1", stream_id="session:1")], outbox_entries=[_outbox("evt:session:1")], expected={"session:1": 0}))
    dispatch = dispatcher.dispatch_pending()

    assert commit.committed is True
    assert dispatch.published_count == 1
    published = bus.list_events()[0]
    assert published.event_id == "evt:session:1"
    assert published.event_type == "gameplay.committed"
    assert published.payload["transaction_id"] == commit.transaction_id
    assert published.payload["event_id"] == "evt:session:1"
    assert published.payload["stream_revision"] == 1
    assert published.payload["global_sequence"] == 1
    assert store.list_outbox()[0].delivery_state == "delivered"


def test_dispatch_failure_keeps_committed_truth_and_retries_same_event_identity() -> None:
    store = GameplayEventStore()
    bus = FlakyBus()
    dispatcher = GameplayOutboxDispatcher(store=store, bus=bus)
    store.append_batch(_batch(events=[_event("evt:session:retry", stream_id="session:retry")], outbox_entries=[_outbox("evt:session:retry")], expected={"session:retry": 0}))

    first = dispatcher.dispatch_pending()
    assert first.published_count == 0
    assert first.failed_count == 1
    assert store.read_events()[0].event_id == "evt:session:retry"
    assert store.list_outbox()[0].delivery_state == "retryable"
    assert store.list_outbox()[0].attempt_count == 1

    second = dispatcher.dispatch_pending()

    assert second.published_count == 1
    assert second.failed_count == 0
    assert [event.event_id for event in bus.list_events()] == ["evt:session:retry"]
    assert [event.payload["global_sequence"] for event in bus.list_events()] == [1]
    assert len(store.read_events()) == 1


def test_rejected_batch_never_creates_publishable_outbox() -> None:
    store = GameplayEventStore()
    bus = InMemoryAuthorityEventBus()
    dispatcher = GameplayOutboxDispatcher(store=store, bus=bus)
    invalid_outbox = _outbox("evt:session:bad", tx="tx:gameplay:bad")
    invalid_outbox["payload_projection"] = {"_projection_error": "filter failure"}

    rejected = store.append_batch(
        _batch(
            tx="tx:gameplay:bad",
            key="idempotency:bad",
            events=[_event("evt:session:bad", stream_id="session:bad", tx="tx:gameplay:bad")],
            outbox_entries=[invalid_outbox],
            expected={"session:bad": 0},
        )
    )

    assert rejected.committed is False
    assert dispatcher.dispatch_pending().published_count == 0
    assert bus.list_events() == []


def test_dispatcher_notifies_an_explicit_post_commit_projection_refresh_without_outbox() -> None:
    store = GameplayEventStore()
    notified: list[str] = []
    dispatcher = GameplayOutboxDispatcher(
        store=store,
        bus=InMemoryAuthorityEventBus(),
        after_transaction_dispatched=lambda transaction: notified.append(transaction.transaction_id),
    )
    batch = _batch(
        events=[_event("evt:projection:refresh", stream_id="actor:projection")],
        expected={"actor:projection": 0},
    )
    batch["outbox_entries"] = []
    batch["projection_refresh_hints"] = [
        {
            "projection_id": "godot_mirror",
            "stream_id": "actor:projection",
            "reason": "post_commit_projection_only",
            "actor_refs": ["actor:projection"],
        }
    ]
    assert store.append_batch(batch).committed

    dispatch = dispatcher.dispatch_pending()

    assert dispatch.published_count == 0
    assert notified == ["tx:gameplay:1"]


def test_sequence_gap_consumer_requests_store_backed_resync() -> None:
    store = GameplayEventStore()
    store.append_batch(_batch(events=[_event("evt:session:1", stream_id="session:1")], outbox_entries=[_outbox("evt:session:1")], expected={"session:1": 0}))
    store.append_batch(
        _batch(
            tx="tx:gameplay:2",
            command_id="cmd:gameplay:2",
            key="idempotency:session:2",
            digest="digest:v2",
            events=[_event("evt:session:2", stream_id="session:2", tx="tx:gameplay:2", command_id="cmd:gameplay:2")],
            outbox_entries=[_outbox("evt:session:2", tx="tx:gameplay:2")],
            expected={"session:2": 0},
        )
    )
    bus = InMemoryAuthorityEventBus()
    dispatcher = GameplayOutboxDispatcher(store=store, bus=bus)
    dispatcher.dispatch_pending(limit=1)
    consumer = GameplayBusSequenceConsumer(store=store)
    assert consumer.consume(bus.list_events()[0]) == "accepted"

    dispatcher.dispatch_pending()
    skipped = bus.list_events()[1]
    consumer.expected_next_global_sequence = 1
    gap = consumer.consume(skipped)

    assert gap == "gap_detected"
    assert [event.event_id for event in consumer.resync_from_store()] == ["evt:session:1", "evt:session:2"]


def test_gameplay_spine_does_not_allow_direct_bus_publish_as_settlement_truth() -> None:
    store = GameplayEventStore()
    bus = InMemoryAuthorityEventBus()
    direct = AuthorityEvent.model_validate(
        {
            "event_id": "evt:direct",
            "event_type": "gameplay.committed",
            "producer_ts": 1,
            "room_id": "room_demo",
            "scene_id": "scene_demo",
            "zone_id": "zone_focus",
            "source": {"layer": "gameplay", "system": "test"},
            "routing": {"audience_mode": "room", "routing_mode": "event_type", "target_ids": ["godot_mirror"]},
            "priority": "p1",
            "ttl": 5000,
            "durability": "replayable",
            "causation_id": "cmd:direct",
            "correlation_id": "corr:direct",
            "payload": {"event_id": "evt:direct", "global_sequence": 1, "transaction_id": "tx:direct"},
        }
    )

    bus.publish(direct)

    assert bus.list_events()[0].event_id == "evt:direct"
    with pytest.raises(KeyError):
        store.get_event("evt:direct")
