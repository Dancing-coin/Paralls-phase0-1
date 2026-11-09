from __future__ import annotations

import pytest

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.ownership_runtime import OwnershipAuthorityService, OwnershipRuntimeError


def test_grant_replay_preserves_receipt_and_rejects_changed_payload() -> None:
    store = GameplayEventStore()
    service = OwnershipAuthorityService(store=store)
    args = dict(command_id="cmd:g1", asset_ref="asset:g1", holder_ref="actor:a",
                right_id="right:g1", idempotency_key="g1", causation_id="cause", correlation_id="corr")
    first = service.grant_initial_title(**args)
    events = store.read_events()
    replay = service.grant_initial_title(**args)
    assert replay == first.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
    assert replay is not first
    with pytest.raises(OwnershipRuntimeError, match="^idempotency_key_reused$"):
        service.grant_initial_title(**(args | {"holder_ref": "actor:b"}))
    assert store.read_events() == events


def test_missing_replay_result_is_rejected_without_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    store = GameplayEventStore()
    service = OwnershipAuthorityService(store=store)
    args = dict(command_id="cmd:g1", asset_ref="asset:g1", holder_ref="actor:a",
                right_id="right:g1", idempotency_key="g1", causation_id="cause", correlation_id="corr")
    service.grant_initial_title(**args)
    events = store.read_events()
    monkeypatch.setattr(store, "get_by_idempotency", lambda *_: None)
    with pytest.raises(OwnershipRuntimeError, match="^ownership_idempotency_missing_result$"):
        service.grant_initial_title(**args)
    assert store.read_events() == events
