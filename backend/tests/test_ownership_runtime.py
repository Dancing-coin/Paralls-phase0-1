from __future__ import annotations

import pytest

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.ownership_runtime import OwnershipAuthorityService, OwnershipProjector, OwnershipRuntimeError


ASSET = "land:observatory"


def test_initial_title_and_independent_transfer_are_event_derived() -> None:
    store = GameplayEventStore()
    service = OwnershipAuthorityService(store=store)
    assert service.grant_initial_title(
        command_id="cmd:grant",
        asset_ref=ASSET,
        holder_ref="actor:alice",
        right_id="right:observatory",
        idempotency_key="grant",
        causation_id="cause",
        correlation_id="corr",
    ).committed

    transferred = service.transfer_title(
        command_id="cmd:transfer",
        asset_ref=ASSET,
        right_id="right:observatory",
        from_holder_ref="actor:alice",
        to_holder_ref="actor:bob",
        idempotency_key="transfer",
        causation_id="cause",
        correlation_id="corr",
    )

    assert transferred.committed
    projection = OwnershipProjector().rebuild(store.read_events())
    assert projection.rights["right:observatory"].holder_ref == "actor:bob"
    assert projection.active_right_by_asset == {ASSET: "right:observatory"}
    assert [event.event_type for event in store.read_events()] == [
        "gameplay.ownership.right_granted",
        "gameplay.ownership.right_transferred",
    ]


def test_duplicate_or_wrong_holder_does_not_change_title() -> None:
    store = GameplayEventStore()
    service = OwnershipAuthorityService(store=store)
    service.grant_initial_title(
        command_id="cmd:grant",
        asset_ref=ASSET,
        holder_ref="actor:alice",
        right_id="right:observatory",
        idempotency_key="grant",
        causation_id="cause",
        correlation_id="corr",
    )
    before = store.read_events()
    with pytest.raises(OwnershipRuntimeError, match="ownership_right_holder_mismatch"):
        service.transfer_title(
            command_id="cmd:bad-transfer",
            asset_ref=ASSET,
            right_id="right:observatory",
            from_holder_ref="actor:bob",
            to_holder_ref="actor:carol",
            idempotency_key="bad-transfer",
            causation_id="cause",
            correlation_id="corr",
        )
    assert store.read_events() == before

    first = service.transfer_title(
        command_id="cmd:transfer",
        asset_ref=ASSET,
        right_id="right:observatory",
        from_holder_ref="actor:alice",
        to_holder_ref="actor:bob",
        idempotency_key="transfer",
        causation_id="cause",
        correlation_id="corr",
    )
    replay = service.transfer_title(
        command_id="cmd:transfer",
        asset_ref=ASSET,
        right_id="right:observatory",
        from_holder_ref="actor:alice",
        to_holder_ref="actor:bob",
        idempotency_key="transfer",
        causation_id="cause",
        correlation_id="corr",
    )
    assert first.committed and replay.committed
    assert replay.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == 2
