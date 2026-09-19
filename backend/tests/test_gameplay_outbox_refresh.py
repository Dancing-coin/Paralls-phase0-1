from __future__ import annotations

import sqlite3

import pytest

from app.gameplay.dispatcher import GameplayOutboxDispatcher
from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore, GameplayEventStoreSnapshotError
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from test_gameplay_event_store_contract import _batch, _event, _outbox


def batch(number=1, *, outboxes=1, compact=False, hints=True):
    tx, event, stream = f"tx:{number}", f"evt:{number}", f"stream:{number}"
    value = _batch(tx=tx, key=tx, events=[_event(event, stream_id=stream, tx=tx)], expected={stream: 0})
    value["outbox_entries"] = [{**_outbox(event, tx=tx), "outbox_id": f"outbox:{number}:{i:03}"} for i in range(outboxes)]
    if compact:
        for entry in value["outbox_entries"]:
            entry["payload_projection"]["projection_kind"] = "population-runtime"
    if not hints:
        value["projection_refresh_hints"] = []
    return value


@pytest.mark.parametrize("outboxes", [0, 2])
def test_failed_refresh_restarts_without_republishing_and_done_survives_restart(tmp_path, outboxes):
    path = tmp_path / "ledger.db"
    store = DurableGameplayEventStore(path)
    assert store.append_batch(batch(outboxes=outboxes)).committed
    attempts = []
    bus = InMemoryAuthorityEventBus()

    def refresh(transaction):
        attempts.append(transaction.transaction_id)
        if len(attempts) == 1:
            raise RuntimeError("projection offline")

    def dispatch(current):
        return GameplayOutboxDispatcher(store=current, bus=bus, after_transaction_dispatched=refresh).dispatch_pending()

    assert dispatch(store).published_count == outboxes
    assert attempts == ["tx:1"]
    assert dispatch(DurableGameplayEventStore(path)).published_count == 0
    assert attempts == ["tx:1", "tx:1"]
    assert len(bus.list_events()) == outboxes
    dispatch(DurableGameplayEventStore(path))
    assert attempts == ["tx:1", "tx:1"]


def test_done_update_failure_retries_only_refresh(tmp_path):
    path = tmp_path / "ledger.db"
    store = DurableGameplayEventStore(path)
    assert store.append_batch(batch()).committed
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TRIGGER fail_done BEFORE UPDATE OF refresh_state ON transactions BEGIN SELECT RAISE(ABORT, 'done unavailable'); END")
    notified = []
    bus = InMemoryAuthorityEventBus()
    dispatcher = GameplayOutboxDispatcher(store=store, bus=bus, after_transaction_dispatched=lambda tx: notified.append(tx.transaction_id))
    assert dispatcher.dispatch_pending().published_count == 1
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT refresh_state FROM transactions").fetchone() == ("pending",)
        connection.execute("DROP TRIGGER fail_done")
    dispatcher.dispatch_pending()
    dispatcher.dispatch_pending()
    assert notified == ["tx:1", "tx:1"]
    assert len(bus.list_events()) == 1
    store.audit()


@pytest.mark.parametrize("durable", [False, True])
def test_refresh_requires_all_outbox_delivered_and_callback(tmp_path, durable):
    store = DurableGameplayEventStore(tmp_path / "ledger.db") if durable else GameplayEventStore()
    assert store.append_batch(batch(outboxes=2)).committed
    assert store.mark_projection_refreshed("tx:1") is False
    assert store.list_pending_projection_refresh(limit=1) == []
    bus = InMemoryAuthorityEventBus()
    GameplayOutboxDispatcher(store=store, bus=bus).dispatch_pending(limit=1)
    assert store.list_pending_projection_refresh(limit=1) == []
    GameplayOutboxDispatcher(store=store, bus=bus).dispatch_pending()
    assert [tx.transaction_id for tx in store.list_pending_projection_refresh(limit=1)] == ["tx:1"]
    notified = []
    GameplayOutboxDispatcher(store=store, bus=bus, after_transaction_dispatched=lambda tx: notified.append(tx.transaction_id)).dispatch_pending()
    assert notified == ["tx:1"]
    assert store.list_pending_projection_refresh(limit=1) == []
    assert store.mark_projection_refreshed("tx:1") is False


@pytest.mark.parametrize("durable", [False, True])
def test_pages_skip_compact_prefix_keep_shared_event_entries_and_do_not_scan_history(tmp_path, monkeypatch, durable):
    store = DurableGameplayEventStore(tmp_path / "ledger.db") if durable else GameplayEventStore()
    assert store.append_batch(batch(1, outboxes=260, compact=True)).committed
    assert store.append_batch(batch(2, outboxes=260)).committed
    query = store.list_outbox
    sizes = []

    def bounded(**kwargs):
        assert 0 < kwargs["limit"] <= 128
        assert kwargs["include_delivered"] is False
        assert kwargs["topic"] == "gameplay.committed"
        sizes.append(kwargs["limit"])
        return query(**kwargs)

    monkeypatch.setattr(store, "list_outbox", bounded)
    monkeypatch.setattr(store, "read_transactions", lambda **kw: pytest.fail("history scan"))
    notified = []
    dispatcher = GameplayOutboxDispatcher(store=store, bus=InMemoryAuthorityEventBus(), after_transaction_dispatched=lambda tx: notified.append(tx.transaction_id))
    first = dispatcher.dispatch_pending(limit=129, topic="gameplay.committed")
    second = dispatcher.dispatch_pending(topic="gameplay.committed")
    assert first.published_count == 129
    assert second.published_count == 131
    assert first.delivered_outbox_ids + second.delivered_outbox_ids == [f"outbox:2:{i:03}" for i in range(260)]
    assert notified == ["tx:2"]
    assert len(sizes) >= 6


def test_failed_publish_and_refresh_do_not_starve_ready_transactions(tmp_path):
    store = DurableGameplayEventStore(tmp_path / "ledger.db")
    for i in (1, 2, 3):
        assert store.append_batch(batch(i)).committed
    attempts, refreshed = [], []

    class Bus(InMemoryAuthorityEventBus):
        def publish(self, event):
            attempts.append(event.event_id)
            if event.event_id == "evt:1":
                raise RuntimeError("offline")
            super().publish(event)

    def refresh(tx):
        refreshed.append(tx.transaction_id)
        if tx.transaction_id == "tx:2":
            raise RuntimeError("source unavailable")

    dispatcher = GameplayOutboxDispatcher(store=store, bus=Bus(), after_transaction_dispatched=refresh)
    result = dispatcher.dispatch_pending(limit=2)
    assert (result.published_count, result.failed_count) == (1, 1)
    dispatcher.dispatch_pending()
    assert attempts == ["evt:1", "evt:2", "evt:1", "evt:3"]
    assert refreshed == ["tx:2", "tx:2", "tx:3"]


def test_dispatch_high_water_excludes_transactions_appended_by_publish(tmp_path):
    store = DurableGameplayEventStore(tmp_path / "ledger.db")
    assert store.append_batch(batch(outboxes=129)).committed

    class Bus(InMemoryAuthorityEventBus):
        def publish(self, event):
            assert store.append_batch(batch(len(self.list_events()) + 2)).committed
            super().publish(event)

    notified = []
    bus = Bus()
    dispatcher = GameplayOutboxDispatcher(store=store, bus=bus, after_transaction_dispatched=lambda tx: notified.append(tx.transaction_id))
    assert dispatcher.dispatch_pending().published_count == 129
    assert len(bus.list_events()) == 129
    assert notified == ["tx:1"]
    assert len(store.list_outbox(include_delivered=False)) == 129


def test_dispatch_zero_and_negative_limit_do_no_work():
    store = GameplayEventStore()
    assert store.append_batch(batch()).committed
    bus = InMemoryAuthorityEventBus()
    dispatcher = GameplayOutboxDispatcher(store=store, bus=bus)
    assert dispatcher.dispatch_pending(limit=0).published_count == 0
    with pytest.raises(ValueError):
        dispatcher.dispatch_pending(limit=-1)
    assert bus.list_events() == []


def test_pending_refresh_query_skips_blocked_batches_using_indexes(tmp_path, monkeypatch):
    path = tmp_path / "ledger.db"
    store = DurableGameplayEventStore(path)
    for number in range(1, 132):
        assert store.append_batch(batch(number, outboxes=1 if number < 131 else 0)).committed
    plans = []
    rows = store._rows

    def explain(sql, parameters=()):
        with sqlite3.connect(path) as connection:
            plans.append(" ".join(row[3] for row in connection.execute("EXPLAIN QUERY PLAN " + sql, parameters)))
        return rows(sql, parameters)

    monkeypatch.setattr(store, "_rows", explain)
    assert [tx.transaction_id for tx in store.list_pending_projection_refresh(after_sequence=0, through_sequence=131, limit=1)] == ["tx:131"]
    assert "transactions_pending_refresh" in plans[-1]
    assert "SEARCH outbox USING INDEX outbox_transaction_sequence" in plans[-1]
    for topic, index in ((None, "outbox_pending_sequence"), ("gameplay.committed", "outbox_pending_topic_sequence")):
        assert len(store.list_outbox(include_delivered=False, topic=topic, after_cursor=(1, ""), through_sequence=131, limit=1)) == 1
        assert index in plans[-1]
        assert "TEMP B-TREE" not in plans[-1]


def test_refresh_limit_and_high_water_bound_callback_created_work():
    store = GameplayEventStore()
    for number in range(1, 132):
        assert store.append_batch(batch(number, outboxes=0)).committed
    notified = []

    def refresh(tx):
        notified.append(tx.transaction_id)
        assert store.append_batch(batch(len(notified) + 131, outboxes=0)).committed

    dispatcher = GameplayOutboxDispatcher(store=store, bus=InMemoryAuthorityEventBus(), after_transaction_dispatched=refresh)
    dispatcher.dispatch_pending(limit=1)
    assert notified == ["tx:1"]
    dispatcher.dispatch_pending()
    assert len(notified) == 132
    assert notified[-1] == "tx:132"
    assert len(store.list_pending_projection_refresh()) == 131


@pytest.mark.parametrize("durable", [False, True])
def test_snapshot_preserves_refresh_done_and_legacy_absence_requeues_once(tmp_path, durable):
    store = DurableGameplayEventStore(tmp_path / "ledger.db") if durable else GameplayEventStore()
    for number, outboxes, hints in ((1, 1, True), (2, 0, True), (3, 0, False)):
        assert store.append_batch(batch(number, outboxes=outboxes, hints=hints)).committed
    store.mark_outbox_delivered("outbox:1:000")
    assert store.mark_projection_refreshed("tx:1")
    snapshot = store.export_snapshot()
    assert snapshot["pending_projection_refresh_ids"] == ["tx:2"]
    restored = GameplayEventStore.from_snapshot(snapshot)
    assert restored.export_snapshot() == snapshot
    json_path = tmp_path / "import.json"
    restored.save_snapshot(json_path)
    imported = DurableGameplayEventStore(json_path)
    assert imported.export_snapshot() == snapshot
    imported.audit()
    del snapshot["pending_projection_refresh_ids"]
    legacy = GameplayEventStore.from_snapshot(snapshot)
    assert legacy.export_snapshot()["pending_projection_refresh_ids"] == ["tx:1", "tx:2"]


@pytest.mark.parametrize("pending", [None, "tx:1", [1], ["tx:1", "tx:1"], ["missing"], ["tx:2"], []])
def test_invalid_snapshot_pending_refresh_is_rejected(pending):
    store = GameplayEventStore()
    assert store.append_batch(batch()).committed
    assert store.append_batch(batch(2, outboxes=0, hints=False)).committed
    snapshot = store.export_snapshot()
    snapshot["pending_projection_refresh_ids"] = pending
    with pytest.raises(GameplayEventStoreSnapshotError, match="refresh"):
        GameplayEventStore.from_snapshot(snapshot)


@pytest.mark.parametrize("state", [None, "done", "invalid"])
def test_audit_rejects_refresh_state_inconsistent_with_outbox(tmp_path, state):
    path = tmp_path / "ledger.db"
    store = DurableGameplayEventStore(path)
    assert store.append_batch(batch()).committed
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE transactions SET refresh_state=?", (state,))
    with pytest.raises(GameplayEventStoreSnapshotError):
        store.audit()


@pytest.mark.parametrize("mode", ["registered", "subscribed", "unconfigured"])
def test_main_refresh_failure_keeps_pending_until_required_source_recovers(monkeypatch, mode):
    from app import main
    from test_godot_gameplay_mirror_delivery import _godot_view

    main.reset_runtime_state()

    store = GameplayEventStore()
    monkeypatch.setattr(main.gameplay_outbox_dispatcher, "_store", store)
    publisher = main.gameplay_godot_projection_publisher
    actor = "actor:refresh-test"
    if mode == "registered":
        publisher.register_actor_source(actor_ref=actor, source=lambda: (_ for _ in ()).throw(RuntimeError("source unavailable")))
    elif mode == "subscribed":
        main.gameplay_godot_projection_repository.publish(_godot_view(actor))
        registry = main.gameplay_mirror_subscription_registry
        registry.grant_read_scope(session_ref="session:refresh-test", actor_ref=actor)
        registry.subscribe(session_ref="session:refresh-test", actor_ref=actor)
    value = batch()
    value["projection_refresh_hints"][0]["actor_refs"] = [actor]
    assert store.append_batch(value).committed
    main.gameplay_outbox_dispatcher.dispatch_pending()
    expected = [] if mode == "unconfigured" else ["tx:1"]
    assert store.export_snapshot()["pending_projection_refresh_ids"] == expected
    if expected:
        assert main.gameplay_mirror_outbox_refresh_consumer.results == []
        publisher.register_actor_source(actor_ref=actor, source=lambda: _godot_view(actor))
        assert main.gameplay_outbox_dispatcher.dispatch_pending().published_count == 0
        assert store.export_snapshot()["pending_projection_refresh_ids"] == []
    main.reset_runtime_state()


def test_main_repeated_refresh_preserves_source_revision_after_done_write_failure(tmp_path, monkeypatch):
    from app import main
    from test_godot_gameplay_mirror_delivery import _godot_view

    main.reset_runtime_state()
    path = tmp_path / "ledger.db"
    store = DurableGameplayEventStore(path)
    monkeypatch.setattr(main.gameplay_outbox_dispatcher, "_store", store)
    actor = "actor:refresh-test"
    main.gameplay_godot_projection_publisher.register_actor_source(actor_ref=actor, source=lambda: _godot_view(actor))
    value = batch()
    value["projection_refresh_hints"][0]["actor_refs"] = [actor]
    assert store.append_batch(value).committed
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TRIGGER fail_done BEFORE UPDATE OF refresh_state ON transactions BEGIN SELECT RAISE(ABORT, 'done unavailable'); END")
    assert main.gameplay_outbox_dispatcher.dispatch_pending().published_count == 1
    first = main.gameplay_godot_projection_repository.view_for(actor)
    assert store.export_snapshot()["pending_projection_refresh_ids"] == ["tx:1"]
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TRIGGER fail_done")
    assert main.gameplay_outbox_dispatcher.dispatch_pending().published_count == 0
    assert main.gameplay_godot_projection_repository.view_for(actor) == first
    assert store.export_snapshot()["pending_projection_refresh_ids"] == []
    main.reset_runtime_state()
