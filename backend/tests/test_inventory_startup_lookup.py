import sqlite3

import pytest

from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.inventory_runtime import ContainerSpec, InventoryAuthorityService, InventoryDefinitionRegistry
from test_gameplay_event_store_contract import _batch, _event


@pytest.mark.parametrize("durable", [False, True])
def test_container_lookup_keeps_non_bootstrap_history_and_filters_before_limit(tmp_path, durable, monkeypatch):
    path = tmp_path / "inventory.sqlite3"
    store = DurableGameplayEventStore(path) if durable else GameplayEventStore()
    service = InventoryAuthorityService(store=store, registry=InventoryDefinitionRegistry())
    actor = "character:char_a"
    for name in ("old-command", "other"):
        assert service.create_container(command_id=name, actor_ref=actor, spec=ContainerSpec(name, 10, 10, 2),
                                        idempotency_key=name, causation_id=name, correlation_id=name).committed
    stream = f"gameplay:inventory:{actor}"
    events = [_event(f"event:{i}", stream_id=stream) for i in range(1000)]
    assert store.append_batch(_batch(events=events, expected={stream: 2})).committed
    if durable:
        # 模拟尚未有新索引的旧 schema2；SQLite 首次补索引后普通 reopen 不重扫。
        with sqlite3.connect(path) as connection:
            connection.execute("DROP INDEX IF EXISTS events_stream_type_revision")
        store = DurableGameplayEventStore(path)
        service = InventoryAuthorityService(store=store, registry=InventoryDefinitionRegistry())
        with sqlite3.connect(path) as connection:
            query = "SELECT value FROM events WHERE stream_id=? AND json_extract(value,'$.event_type')=? AND stream_revision>=? ORDER BY stream_revision LIMIT ?"
            plan = connection.execute("EXPLAIN QUERY PLAN " + query, (stream, "gameplay.inventory.container_created", 1, 1)).fetchall()
            assert any("events_stream_type_revision" in str(row) for row in plan)
    original = store.read_stream

    def typed_only(*args, **kwargs):
        assert kwargs.get("event_type"), "container startup scanned unfiltered history"
        return original(*args, **kwargs)

    monkeypatch.setattr(store, "read_stream", typed_only)
    assert service.has_container(actor_ref=actor, container_id="old-command")
    assert not service.has_container(actor_ref=actor, container_id="missing")
    assert not service.has_container(actor_ref="character:char_b", container_id="old-command")
    selected = store.read_stream(stream, from_revision=2, to_revision=100, event_type="gameplay.inventory.container_created", limit=1)
    assert [event.stream_revision for event in selected] == [2]
    assert store.read_stream(stream, event_type="gameplay.inventory.container_created", limit=0) == []
