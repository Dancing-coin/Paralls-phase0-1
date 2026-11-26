from types import SimpleNamespace

import pytest

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.ownership_runtime import OwnershipAuthorityService, OwnershipRuntimeError
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


def test_owner_duplicate_rejects_unresolvable_committed_event_id(monkeypatch) -> None:
    store = GameplayEventStore()
    service = OwnershipAuthorityService(store=store)
    command = {
        "command_id": "cmd:grant",
        "asset_ref": "land:observatory",
        "holder_ref": "actor:alice",
        "right_id": "right:observatory",
        "idempotency_key": "grant",
        "causation_id": "cause",
        "correlation_id": "corr",
    }
    first = service.grant_initial_title(**command)
    assert first.committed
    committed_events = store.read_events()
    original_get = store.get_by_idempotency

    def corrupted_get(principal_ref: str, idempotency_key: str):
        result = original_get(principal_ref, idempotency_key)
        if result is None:
            return None
        return result.model_copy(update={"committed_event_ids": ["evt:missing"]})

    monkeypatch.setattr(store, "get_by_idempotency", corrupted_get)

    with pytest.raises(OwnershipRuntimeError, match="ownership_replay_event_missing"):
        service.grant_initial_title(**command)

    assert store.read_events() == committed_events


def test_owner_duplicate_rejects_committed_event_count_mismatch(monkeypatch) -> None:
    store = GameplayEventStore()
    service = OwnershipAuthorityService(store=store)
    command = {
        "command_id": "cmd:grant",
        "asset_ref": "land:observatory",
        "holder_ref": "actor:alice",
        "right_id": "right:observatory",
        "idempotency_key": "grant",
        "causation_id": "cause",
        "correlation_id": "corr",
    }
    assert service.grant_initial_title(**command).committed
    original_get = store.get_by_idempotency

    def corrupted_get(principal_ref: str, idempotency_key: str):
        result = original_get(principal_ref, idempotency_key)
        if result is None:
            return None
        return result.model_copy(update={"committed_event_ids": []})

    monkeypatch.setattr(store, "get_by_idempotency", corrupted_get)

    with pytest.raises(OwnershipRuntimeError, match="ownership_replay_event_count_mismatch"):
        service.grant_initial_title(**command)


def test_owner_duplicate_rejects_missing_transaction(monkeypatch) -> None:
    store = GameplayEventStore()
    service = OwnershipAuthorityService(store=store)
    command = {
        "command_id": "cmd:grant",
        "asset_ref": "land:observatory",
        "holder_ref": "actor:alice",
        "right_id": "right:observatory",
        "idempotency_key": "grant",
        "causation_id": "cause",
        "correlation_id": "corr",
    }
    assert service.grant_initial_title(**command).committed
    original_get = store.get_by_idempotency

    def corrupted_get(principal_ref: str, idempotency_key: str):
        result = original_get(principal_ref, idempotency_key)
        if result is None:
            return None
        return result.model_copy(update={"transaction_id": "tx:missing"})

    monkeypatch.setattr(store, "get_by_idempotency", corrupted_get)

    with pytest.raises(OwnershipRuntimeError, match="ownership_replay_transaction_mismatch"):
        service.grant_initial_title(**command)
