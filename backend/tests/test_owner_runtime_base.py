from types import SimpleNamespace

from app.gameplay.owner_runtime_base import StoreReadSnapshot


class _SnapshotStore:
    def __init__(self) -> None:
        self.events = []
        self.read_count = 0

    def get_last_global_sequence(self) -> int:
        return len(self.events)

    def read_events(self):
        self.read_count += 1
        return list(self.events)


def test_store_read_snapshot_reuses_events_until_store_head_changes() -> None:
    store = _SnapshotStore()
    snapshot = StoreReadSnapshot(store)

    first = snapshot.all_events()
    second = snapshot.all_events()

    assert first is second
    assert store.read_count == 1

    store.events.append(SimpleNamespace(global_sequence=1))
    third = snapshot.all_events()

    assert third == tuple(store.events)
    assert third is not first
    assert store.read_count == 2
