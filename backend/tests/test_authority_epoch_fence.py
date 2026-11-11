from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from test_gameplay_event_store_contract import _batch


STREAM = "session:handoff:1"
CONTEXT = {"stream_id": STREAM, "scope_ref": "scope:world", "epoch": 1, "writer_ref": "writer:a"}


@pytest.fixture(params=["memory", "durable"])
def store(request, tmp_path):
    result = GameplayEventStore() if request.param == "memory" else DurableGameplayEventStore(tmp_path / "store.db")
    result.register_authority_stream(STREAM, "scope:world", 1, "writer:a")
    yield result
    if request.param == "durable":
        result.close()


@pytest.mark.parametrize("contexts", [None, [], [{"stream_id": STREAM}], [CONTEXT, CONTEXT], [{**CONTEXT, "scope_ref": "other"}], [{**CONTEXT, "epoch": 2}], [{**CONTEXT, "writer_ref": "other"}], [CONTEXT, {**CONTEXT, "stream_id": "other"}]])
def test_protected_batch_rejects_invalid_context_atomically(store, contexts):
    result = store.append_batch(_batch(), authority_contexts=contexts)
    assert not result.committed
    assert result.failure.error_code == "authority_context_invalid"
    assert store.read_events() == []
    assert store.list_outbox() == []
    assert store.get_by_idempotency("player:local", "idempotency:handoff:1") is None


def test_retry_survives_epoch_change_without_side_effects(store):
    first = store.append_batch(_batch(), authority_contexts=[CONTEXT])
    assert first.committed
    store.update_authority_stream(STREAM, "scope:world", 1, "writer:a", 2, "writer:b")
    retry = store.append_batch(_batch(), authority_contexts=[CONTEXT])
    assert retry.idempotency_status == "duplicate_replayed"
    assert retry.committed_event_ids == first.committed_event_ids
    changed = store.append_batch(_batch(digest="different"), authority_contexts=[CONTEXT])
    assert changed.failure.error_code == "idempotency_key_reused"
    fresh = _batch(tx="tx:new", command_id="cmd:new", key="key:new")
    assert store.append_batch(fresh, authority_contexts=[CONTEXT]).failure.error_code == "authority_context_invalid"
    assert len(store.read_events()) == 2
    assert len(store.list_outbox()) == 2


def test_multiple_protected_streams_fail_as_one(store):
    other = {"stream_id": "body:char_a", "scope_ref": "scope:body", "epoch": 1, "writer_ref": "writer:b"}
    store.register_authority_stream("body:char_a", "scope:body", 1, "writer:b")
    assert not store.append_batch(_batch(), authority_contexts=[CONTEXT, {**other, "writer_ref": "wrong"}]).committed
    assert store.read_events() == []
    assert store.list_outbox() == []
    assert store.append_batch(_batch(), authority_contexts=[CONTEXT, other]).committed


def test_ordinary_append_cannot_bypass_registered_stream(store):
    assert store.append_batch(_batch()).failure.error_code == "authority_context_invalid"
    assert store.read_events() == []
    assert store.list_outbox() == []


def test_unregistered_stream_remains_unchanged():
    assert GameplayEventStore().append_batch(_batch()).committed


@pytest.mark.parametrize("first", ["append", "update"])
def test_durable_instances_serialize_update_and_append_and_restore(tmp_path, first):
    path = tmp_path / "shared.db"
    a = DurableGameplayEventStore(path)
    b = DurableGameplayEventStore(path)
    a.register_authority_stream(STREAM, "scope:world", 1, "writer:a")
    entered = Event()
    b._database_connection().set_trace_callback(lambda sql: entered.set() if sql == "BEGIN IMMEDIATE" else None)

    def append():
        return b.append_batch(_batch(), authority_contexts=[CONTEXT])

    def update():
        b.update_authority_stream(STREAM, "scope:world", 1, "writer:a", 2, "writer:b")

    with ThreadPoolExecutor(max_workers=1) as pool:
        with a.group_commit():
            if first == "append":
                original = a.append_batch(_batch(), authority_contexts=[CONTEXT])
                assert original.committed
                future = pool.submit(update)
            else:
                a.update_authority_stream(STREAM, "scope:world", 1, "writer:a", 2, "writer:b")
                future = pool.submit(append)
            assert entered.wait(5)
            assert not future.done()
        result = future.result(timeout=10)
    if first == "update":
        assert result.failure.error_code == "authority_context_invalid"
    snapshot = a.export_snapshot()
    a.close()
    b.close()
    reopened = DurableGameplayEventStore(path)
    restored = DurableGameplayEventStore(tmp_path / "restore.db")
    restored.restore_snapshot(snapshot)
    for candidate in (reopened, restored):
        fresh = _batch(tx="tx:new", command_id="cmd:new", key="key:new")
        assert candidate.append_batch(fresh, authority_contexts=[CONTEXT]).failure.error_code == "authority_context_invalid"
        if first == "append":
            assert candidate.append_batch(_batch(), authority_contexts=[CONTEXT]).idempotency_status == "duplicate_replayed"
            assert candidate.append_batch(_batch(digest="different"), authority_contexts=[CONTEXT]).failure.error_code == "idempotency_key_reused"
            assert len(candidate.read_events()) == 2
            assert len(candidate.list_outbox()) == 2
        else:
            assert candidate.read_events() == []
            assert candidate.list_outbox() == []
        candidate.close()
