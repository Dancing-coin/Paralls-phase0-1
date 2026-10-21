from contextlib import closing
import json
import sqlite3
import zlib

import pytest
from zlib_ng import zlib_ng

from app.gameplay.event_store import (
    DurableGameplayEventStore,
    GameplayEventStoreSnapshotError,
    decode_durable_json,
    encode_durable_json,
)
from test_gameplay_event_store_contract import _batch, _event


PREFIX = b"paralls-json-zlib-v1\0"


@pytest.mark.parametrize("text", [
    "", "null", '{"value":1.3497006766680133e-05}',
    json.dumps({"text": "汉字\x00\x7f\U0001f600", "items": [True, None, -0.0]}, ensure_ascii=False),
    json.dumps({"rows": [f"value:{index % 71}" for index in range(10_000)]}),
], ids=["empty", "null", "float", "unicode-controls", "large"])
def test_written_body_is_readable_by_original_decoder_and_preserves_utf8(text):
    body = encode_durable_json(text)
    assert body.startswith(PREFIX)
    assert zlib.decompress(body[len(PREFIX):]) == text.encode("utf-8")
    assert decode_durable_json(body) == text
    assert decode_durable_json(memoryview(body)) == text


@pytest.mark.parametrize("compress", [zlib.compress, zlib_ng.compress])
def test_original_decoder_reads_both_encoders_and_rejects_corrupt_streams(compress):
    compressed = compress(b'{"event_id":"evt:compatibility"}', level=1)
    assert decode_durable_json(PREFIX + compressed) == '{"event_id":"evt:compatibility"}'
    bad_checksum = compressed[:-1] + bytes([compressed[-1] ^ 1])
    for corrupted in (compressed[:-1], bad_checksum, compress(b"\xff", level=1)):
        with pytest.raises(GameplayEventStoreSnapshotError, match="gameplay_snapshot_json_codec_invalid"):
            decode_durable_json(PREFIX + corrupted)


def test_nonexact_text_keeps_legacy_encode_hook_and_exception():
    class Text(str):
        def encode(self, *args, **kwargs):
            return bytearray(b'{"value":"custom"}')

    class InvalidText(str):
        def encode(self, *args, **kwargs):
            return "invalid bytes"

    assert encode_durable_json(Text("unencoded")) == PREFIX + zlib.compress(bytearray(b'{"value":"custom"}'), level=1)
    with pytest.raises(TypeError):
        encode_durable_json(InvalidText("invalid"))
    with pytest.raises(UnicodeEncodeError):
        encode_durable_json("\ud800")


def test_cold_store_recovers_mixed_text_stdlib_and_native_rows(tmp_path):
    path = tmp_path / "mixed.db"
    store = DurableGameplayEventStore(path)
    try:
        assert store.append_batch(_batch()).committed
        second = _batch(tx="tx:second", command_id="cmd:second", key="key:second",
            events=[_event("evt:second", stream_id="stream:second", tx="tx:second", command_id="cmd:second")],
            expected={"stream:second": 0})
        committed = store.append_batch(second)
        assert committed.committed
        store.mark_outbox_delivered("outbox:evt:second")
        expected = store.export_snapshot()
    finally:
        store.close()
    # 将同一数据库的不同正文保留为三种既有合法表示，冷恢复不借助缓存。
    with closing(sqlite3.connect(path)) as connection, connection:
        for table, column, compress in (("transactions", "batch", zlib.compress),
                ("events", "full_value", zlib_ng.compress), ("outbox", "value", None)):
            rows = connection.execute(f"SELECT rowid, {column} FROM {table}").fetchall()
            for rowid, value in rows:
                text = decode_durable_json(value)
                body = PREFIX + compress(text.encode("utf-8"), level=1) if compress else text
                connection.execute(f"UPDATE {table} SET {column}=? WHERE rowid=?", (body, rowid))
    restored = DurableGameplayEventStore(path)
    try:
        assert restored.export_snapshot() == expected
        assert restored.append_batch(second).idempotency_status == "duplicate_replayed"
        assert restored.get_stream_head("stream:second") == 1
        assert restored.get_outbox("outbox:evt:second").delivery_state == "delivered"
        restored.audit()
    finally:
        restored.close()
