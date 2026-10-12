from __future__ import annotations

import pytest

from app.gameplay.event_store import DurableGameplayEventStore
from test_gameplay_event_store_contract import _batch, _event, _outbox


@pytest.mark.parametrize("topic", [None, "gameplay.committed"])
@pytest.mark.parametrize("legacy_missing_indexes", [False, True])
def test_pending_lookup_does_not_visit_delivered_history(tmp_path, topic, legacy_missing_indexes):
    path = tmp_path / "ledger.db"
    store = DurableGameplayEventStore(path)
    history = [
        {**_outbox("evt:history"), "outbox_id": f"history:{i:04}"}
        for i in range(2000)
    ]
    assert store.append_batch(_batch(
        events=[_event("evt:history", stream_id="stream:history")],
        outbox_entries=history, expected={"stream:history": 0},
    )).committed
    with store.group_commit():
        for entry in history:
            store.mark_outbox_delivered(entry["outbox_id"])
    pending = [
        {**_outbox("evt:pending", tx="tx:pending"), "outbox_id": key}
        for key in ("pending:z", "pending:a", "pending:m")
    ]
    assert store.append_batch(_batch(
        tx="tx:pending", key="pending", command_id="cmd:pending",
        events=[_event("evt:pending", stream_id="stream:pending", tx="tx:pending",
                       command_id="cmd:pending")],
        outbox_entries=pending, expected={"stream:pending": 0},
    )).committed
    store.mark_outbox_retryable("pending:m", "offline")
    if legacy_missing_indexes:
        connection = store._database_connection()
        with connection:
            connection.execute("DROP INDEX outbox_pending_sequence")
            connection.execute("DROP INDEX outbox_pending_topic_sequence")
    store.close()
    store = DurableGameplayEventStore(path)
    connection = store._database_connection()
    assert connection.execute("PRAGMA synchronous").fetchone() == (2,)

    # 使用执行步骤约束查询工作量，避免机器负载造成墙钟性能测试抖动。
    progress_calls = 0
    def budget():
        nonlocal progress_calls
        progress_calls += 1
        return int(progress_calls >= 2)

    connection.set_progress_handler(budget, 1000)
    try:
        first = store.list_outbox(include_delivered=False, topic=topic, limit=1)
        assert [row.outbox_id for row in first] == ["pending:a"]
        second = store.list_outbox(include_delivered=False, topic=topic,
            after_cursor=(first[0].global_sequence, first[0].outbox_id),
            through_sequence=2, limit=1)
        assert [row.outbox_id for row in second] == ["pending:m"]
        assert second[0].delivery_state == "retryable" and second[0].attempt_count == 1
        assert store.list_outbox(include_delivered=False, topic=topic,
                                through_sequence=1, limit=1) == []
    finally:
        if store._connection is connection:
            connection.set_progress_handler(None, 0)
    first[0].payload_projection.clear()
    assert store.get_outbox("pending:a").payload_projection
    assert [row.outbox_id for row in store.list_outbox(
        include_delivered=False, transaction_id="tx:pending", topic=topic
    )] == ["pending:a", "pending:m", "pending:z"]
    store.close()
