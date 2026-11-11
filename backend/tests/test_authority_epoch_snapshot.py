import json
import hashlib
from pathlib import Path

import pytest

from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore, GameplayEventStoreSnapshotError
from test_gameplay_event_store_contract import _batch


def test_authority_registration_snapshot_roundtrip_and_rollback_guard(tmp_path):
    path = tmp_path / "target.db"
    store = DurableGameplayEventStore(path)
    assert store.get_authority_stream("stream:protected") is None
    assert store.append_batch(_batch()).committed
    store.register_authority_stream("stream:protected", "scope:world", 3, "writer:a")
    snapshot = store.export_snapshot()
    assert snapshot["snapshot_schema_version"] == 3
    assert snapshot["authority_streams"] == [{"stream_id": "stream:protected", "scope_ref": "scope:world", "epoch": 3, "writer_ref": "writer:a"}]
    store.close()
    store = DurableGameplayEventStore(path)
    assert store.get_authority_stream("stream:protected") == snapshot["authority_streams"][0]
    assert store.export_snapshot() == snapshot
    missing = dict(snapshot)
    missing.pop("authority_streams")
    with pytest.raises(GameplayEventStoreSnapshotError, match="authority_snapshot_invalid"):
        store.restore_snapshot(missing)
    assert store.export_snapshot() == snapshot
    legacy = dict(snapshot, snapshot_schema_version=2)
    legacy.pop("authority_streams")
    with pytest.raises(GameplayEventStoreSnapshotError, match="authority_snapshot_rollback"):
        store.restore_snapshot(legacy)
    assert store.export_snapshot() == snapshot
    empty = GameplayEventStore().export_snapshot()
    with pytest.raises(GameplayEventStoreSnapshotError, match="gameplay_snapshot_target_conflict"):
        store.restore_snapshot(empty)
    assert store.export_snapshot() == snapshot
    for bad in ([], [{**snapshot["authority_streams"][0], "epoch": 2}]):
        candidate = dict(snapshot, authority_streams=bad)
        with pytest.raises(GameplayEventStoreSnapshotError, match="authority_snapshot_rollback"):
            store.restore_snapshot(candidate)
        assert store.export_snapshot() == snapshot
    store.restore_snapshot(snapshot)
    assert store.export_snapshot() == snapshot
    store.close()
    exported = tmp_path / "export.json"
    exported.write_text(json.dumps(snapshot), encoding="utf-8")
    migrated = DurableGameplayEventStore(exported)
    assert migrated.export_snapshot() == snapshot
    migrated.close()


@pytest.mark.parametrize("version", [1, 2])
def test_legacy_snapshot_json_migration_preserves_ledger(tmp_path, version):
    name = "snapshot-v1-derived.json" if version == 1 else "snapshot-v2.json"
    data = (Path(__file__).parent / "fixtures" / "authority_epoch_legacy" / name).read_bytes()
    expected = {1: "fc1e00dfabea13cfca7130789bfbfd45925117a1b96b88d92a4272cee216ce08", 2: "cca5c3edd6f133716fd18a317397397475a431d55f3cd58653ea8496d28f276e"}
    assert hashlib.sha256(data).hexdigest() == expected[version]
    snapshot = json.loads(data)
    assert GameplayEventStore.from_snapshot(snapshot).read_events()
    path = tmp_path / "legacy.json"
    path.write_bytes(data)
    store = DurableGameplayEventStore(path)
    digests = {"events": "c0390ace9ed6b50a3da075f3e270fbb2f4cb5bee1f1a41ddebf3565de30e650d", "transactions": "c86b9a2fa2629ab9b285c6d6a62371a363fe874e9e2f569578bd400ed1ba4c8e", "transaction_results": "347acdabdb7cd182b748da13ef0c2f254990bffa3eaad688ed3f5ff0d011617d", "idempotency": "977e3b11cadc61c9ebf1af0c61b800ac2d8eddacd9acea9f3a55e1eb1ff92149"}
    for key in ("events", "transactions", "transaction_results", "idempotency"):
        assert store.export_snapshot()[key] == snapshot[key]
        assert hashlib.sha256(json.dumps(store.export_snapshot()[key], sort_keys=True, separators=(",", ":")).encode()).hexdigest() == digests[key]
    store.register_authority_stream("stream:protected", "scope:world", 3, "writer:a")
    registered = store.export_snapshot()
    store.restore_snapshot(registered)
    store.close()
    reopened = DurableGameplayEventStore(path)
    for key, digest in digests.items():
        assert hashlib.sha256(json.dumps(reopened.export_snapshot()[key], sort_keys=True, separators=(",", ":")).encode()).hexdigest() == digest
    reopened.close()
