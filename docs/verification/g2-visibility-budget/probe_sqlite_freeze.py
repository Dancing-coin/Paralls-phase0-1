"""Isolated feasibility probe; not an epoch or production migration."""
from pathlib import Path
import argparse
import json
import sqlite3
import sys

root = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(root / "backend"), str(root / "backend" / "tests")]
from app.gameplay.event_store import DurableGameplayEventStore
from test_gameplay_event_store_contract import _batch, _event, _outbox


def batch(name, revision):
    tx = f"tx:{name}"
    return _batch(tx=tx, command_id=f"cmd:{name}", key=f"key:{name}", digest=f"digest:{name}",
                  events=[_event(f"evt:{name}", stream_id="stream:protected", tx=tx, command_id=f"cmd:{name}")],
                  outbox_entries=[_outbox(f"evt:{name}", tx=tx)], expected={"stream:protected": revision})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    args = parser.parse_args()
    if args.database.exists():
        raise SystemExit("database must not exist")
    store = DurableGameplayEventStore(args.database)
    try:
        first = batch("first", 0)
        assert store.append_batch(first).committed
        # Force the existing store connection to open before another connection
        # installs the gate. The gate blocks every writer, including new ones.
        store.read_events()
        with sqlite3.connect(args.database) as db:
            db.execute("CREATE TRIGGER freeze_protected BEFORE INSERT ON events "
                       "WHEN NEW.stream_id = 'stream:protected' BEGIN "
                       "SELECT RAISE(ABORT, 'experimental_freeze'); END")
        retry = store.append_batch(first)
        blocked = store.append_batch(batch("second", 1))
        assert retry.idempotency_status == "duplicate_replayed"
        assert not blocked.committed
        assert blocked.failure.error_code == "durable_persistence_failed"
        assert len(store.read_events()) == len(store.read_transactions()) == len(store.list_outbox(include_delivered=True)) == 1
        mixed = _batch(tx="tx:mixed", command_id="cmd:mixed", key="key:mixed", digest="digest:mixed",
                       events=[_event("evt:other", stream_id="stream:other", tx="tx:mixed", command_id="cmd:mixed"),
                               _event("evt:protected", stream_id="stream:protected", tx="tx:mixed", command_id="cmd:mixed")],
                       outbox_entries=[_outbox("evt:other", tx="tx:mixed")],
                       expected={"stream:other": 0, "stream:protected": 1})
        mixed_result = store.append_batch(mixed)
        assert not mixed_result.committed
        assert len(store.read_events()) == len(store.read_transactions()) == len(store.list_outbox(include_delivered=True)) == 1
        assert store.get_stream_head("stream:other") == 0
        with sqlite3.connect(args.database) as db:
            raw_error = None
            try:
                db.execute("INSERT INTO events (global_sequence,event_id,stream_id,stream_revision,transaction_id,value) VALUES (99,'raw','stream:protected',2,'raw','{}')")
            except sqlite3.IntegrityError as exc:
                raw_error = str(exc)
            assert raw_error == "experimental_freeze"
            db.execute("DROP TRIGGER freeze_protected")
        assert store.append_batch(batch("second", 1)).committed
        print(json.dumps({"database": str(args.database), "exact_retry": retry.idempotency_status,
                          "blocked_error": blocked.failure.error_code, "raw_error": raw_error,
                          "mixed_error": mixed_result.failure.error_code,
                          "after_removal_events": len(store.read_events())}, indent=2))
    finally:
        store.close()


if __name__ == "__main__":
    main()
