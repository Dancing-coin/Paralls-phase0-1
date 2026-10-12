from contextlib import closing
import sqlite3

import pytest

from app.gameplay import event_store
from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStoreSnapshotError, encode_durable_json
from app.gameplay.models import GameplayEvent
from test_gameplay_event_store_contract import _batch


@pytest.fixture
def store(tmp_path):
    ledger = DurableGameplayEventStore(tmp_path / "ledger.db")
    try:
        yield ledger
    finally:
        ledger.close()


@pytest.fixture
def decompressions(monkeypatch):
    calls = []
    original = event_store.zlib.decompress

    def decompress(value, *args, **kwargs):
        calls.append(value)
        return original(value, *args, **kwargs)

    monkeypatch.setattr(event_store.zlib, "decompress", decompress)
    return calls


def test_written_json_reuse_keeps_every_validation_and_isolated_return(store, monkeypatch, decompressions):
    assert store.append_batch(_batch()).committed
    original = GameplayEvent.model_validate_json.__func__
    validations = []

    def validate(cls, value, *args, **kwargs):
        validations.append(value)
        return original(cls, value, *args, **kwargs)

    monkeypatch.setattr(GameplayEvent, "model_validate_json", classmethod(validate))
    first = store.get_event("evt:session:reserved")
    first.payload["session_id"] = "caller mutation"
    second = store.get_event("evt:session:reserved")
    third = store.read_stream("session:handoff:1")[0]

    assert second.payload["session_id"] == third.payload["session_id"] == "session:handoff:1"
    assert second is not third
    assert len(validations) == 3
    assert decompressions == []


def test_cached_body_does_not_hide_sql_updates_or_corruption(store, decompressions):
    assert store.append_batch(_batch()).committed
    event = store.get_event("evt:session:reserved")
    decompressions.clear()
    changed = event.model_copy(update={"payload": {"session_id": "external update"}}, deep=True)
    changed_body = encode_durable_json(changed.model_dump_json())
    with closing(sqlite3.connect(store._snapshot_path)) as connection, connection:
        connection.execute("UPDATE events SET full_value=? WHERE event_id=?", (changed_body, event.event_id))
    assert store.get_event(event.event_id).payload == changed.payload
    assert store.get_event(event.event_id).payload == changed.payload
    assert len(decompressions) == 1

    with closing(sqlite3.connect(store._snapshot_path)) as connection, connection:
        connection.execute("UPDATE events SET full_value=? WHERE event_id=?", (changed_body[:-1], event.event_id))
    for _ in range(2):
        with pytest.raises(GameplayEventStoreSnapshotError, match="gameplay_snapshot_row_invalid") as failure:
            store.get_event(event.event_id)
        assert str(failure.value.__cause__) == "gameplay_snapshot_json_codec_invalid"
    assert len(decompressions) == 3


def test_cache_never_reuses_mutable_outbox_state(store, decompressions):
    assert store.append_batch(_batch()).committed
    identity = "outbox:evt:session:reserved"
    store.get_outbox(identity).payload_projection["payload"]["safe_session_id"] = "caller mutation"
    store.mark_outbox_retryable(identity, "temporary failure")
    retry = store.get_outbox(identity)
    assert (retry.delivery_state, retry.attempt_count, retry.last_error) == ("retryable", 1, "temporary failure")
    assert retry.payload_projection["payload"]["safe_session_id"] == "session:handoff:1"
    store.mark_outbox_delivered(identity)
    delivered = store.get_outbox(identity)
    assert (delivered.delivery_state, delivered.attempt_count, delivered.last_error) == ("delivered", 1, None)
    assert all(item.outbox_id != identity for item in store.list_outbox(include_delivered=False))
    assert decompressions == []


def test_rolled_back_cached_bytes_cannot_create_facts(store):
    with pytest.raises(RuntimeError, match="abort"):
        with store.group_commit():
            assert store.append_batch(_batch()).committed
            assert store.get_event("evt:session:reserved").global_sequence == 1
            raise RuntimeError("abort")

    assert store.read_events() == []
    assert store.get_by_idempotency("player:local", "idempotency:handoff:1") is None
    assert store.get_last_global_sequence() == 0
    with pytest.raises(KeyError):
        store.get_event("evt:session:reserved")
    assert store.append_batch(_batch()).committed
    store.audit()


def test_json_cache_evicts_old_content_and_bounds_unicode_memory(store, decompressions):
    first = store._encode_json('"first"')
    recent = None
    for index in range(600):
        recent = store._encode_json(f'"value:{index}"')
        assert len(store._json_text_cache) <= 512
        assert store._json_text_cache_bytes <= 2 * 1024 * 1024
    assert store._decode_json(recent) == '"value:599"'
    assert decompressions == []
    assert store._decode_json(first) == '"first"'
    assert len(decompressions) == 1

    for index in range(12):
        store._encode_json('"' + "汉" * 120_000 + str(index) + '"')
        assert store._json_text_cache_bytes <= 2 * 1024 * 1024
    assert len(store._json_text_cache) < 12
    oversized = store._encode_json('"' + "汉" * 1_100_000 + '"')
    decompressions.clear()
    for _ in range(2):
        assert store._decode_json(oversized).startswith('"汉')
    assert len(decompressions) == 2
    assert oversized not in store._json_text_cache


def test_json_cache_preserves_nonexact_codec_inputs(store, decompressions):
    class EncodedText(str):
        def encode(self, *args, **kwargs):
            return b'"custom encoding"'

    class Blob(bytes):
        pass

    blob = store._encode_json(EncodedText('"original text"'))
    assert store._decode_json(blob) == '"custom encoding"'
    assert len(decompressions) == 1
    assert store._decode_json(Blob(blob)) == '"custom encoding"'
    assert store._decode_json(memoryview(blob)) == '"custom encoding"'
    assert len(decompressions) == 3
    assert store._decode_json('"legacy TEXT"') == '"legacy TEXT"'


def test_close_clears_cached_content_and_prefetched_decode_does_not_retain_it(store):
    assert store.append_batch(_batch()).committed
    with closing(sqlite3.connect(store._snapshot_path)) as connection:
        body = connection.execute("SELECT full_value FROM events LIMIT 1").fetchone()[0]
    assert store._json_text_cache
    store.close()
    assert store._json_text_cache == {}
    assert store._json_text_cache_bytes == 0
    assert store._decode_json(body)
    assert store._json_text_cache == {}
    assert store._json_text_cache_bytes == 0
    with pytest.raises(GameplayEventStoreSnapshotError, match="gameplay_snapshot_row_invalid") as failure:
        store.get_event("evt:session:reserved")
    assert str(failure.value.__cause__) == "gameplay_snapshot_closed"
