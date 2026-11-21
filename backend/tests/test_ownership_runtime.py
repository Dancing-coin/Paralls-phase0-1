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
    assert store.read_events()[0].payload.get("bond_type") is None
    assert projection.rights["right:observatory"].bond_type == "ownership"
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


def test_distinct_right_types_coexist_and_replay_independently() -> None:
    store = GameplayEventStore()
    service = OwnershipAuthorityService(store=store)
    service.grant_initial_title(
        command_id="cmd:grant-title",
        asset_ref=ASSET,
        holder_ref="actor:alice",
        right_id="right:title",
        idempotency_key="grant:title",
        causation_id="cause",
        correlation_id="corr",
    )
    custody = service.grant_right(
        command_id="cmd:grant-custody",
        asset_ref=ASSET,
        holder_ref="actor:bob",
        right_id="right:custody",
        bond_type="custody",
        idempotency_key="grant:custody",
        causation_id="cause",
        correlation_id="corr",
    )
    custody_replay = service.grant_right(
        command_id="cmd:grant-custody",
        asset_ref=ASSET,
        holder_ref="actor:bob",
        right_id="right:custody",
        bond_type="custody",
        idempotency_key="grant:custody",
        causation_id="cause",
        correlation_id="corr",
    )
    secondary_custody = service.grant_right(
        command_id="cmd:grant-custody-secondary",
        asset_ref=ASSET,
        holder_ref="actor:eve",
        right_id="right:custody:secondary",
        bond_type="custody",
        idempotency_key="grant:custody:secondary",
        causation_id="cause",
        correlation_id="corr",
    )
    authority = service.grant_right(
        command_id="cmd:grant-authority",
        asset_ref=ASSET,
        holder_ref="actor:carol",
        right_id="right:authority",
        bond_type="authority",
        idempotency_key="grant:authority",
        causation_id="cause",
        correlation_id="corr",
    )
    affiliation = service.grant_right(
        command_id="cmd:grant-affiliation",
        asset_ref=ASSET,
        holder_ref="actor:crew",
        right_id="right:affiliation",
        bond_type="affiliation",
        idempotency_key="grant:affiliation",
        causation_id="cause",
        correlation_id="corr",
    )
    obligation = service.grant_right(
        command_id="cmd:grant-obligation",
        asset_ref=ASSET,
        holder_ref="actor:debtor",
        right_id="right:obligation",
        bond_type="obligation",
        idempotency_key="grant:obligation",
        causation_id="cause",
        correlation_id="corr",
    )

    assert custody.committed and secondary_custody.committed
    assert authority.committed and affiliation.committed and obligation.committed
    assert custody_replay.idempotency_status == "duplicate_replayed"
    projection = OwnershipProjector().rebuild(store.read_events())
    assert projection.active_right_by_asset == {ASSET: "right:title"}
    assert dict(projection.active_right_by_asset_and_type[ASSET]) == {
        "authority": ("right:authority",),
        "custody": ("right:custody", "right:custody:secondary"),
        "affiliation": ("right:affiliation",),
        "obligation": ("right:obligation",),
        "ownership": ("right:title",),
    }
    assert projection.rights["right:authority"].holder_ref == "actor:carol"

    transferred = service.transfer_right(
        command_id="cmd:transfer-custody",
        asset_ref=ASSET,
        right_id="right:custody",
        bond_type="custody",
        from_holder_ref="actor:bob",
        to_holder_ref="actor:dave",
        idempotency_key="transfer:custody",
        causation_id="cause",
        correlation_id="corr",
    )
    assert transferred.committed

    events = store.read_events()
    full = OwnershipProjector().rebuild(events)
    checkpoint = OwnershipProjector().rebuild(events, checkpoint_at=6)
    assert full == checkpoint
    assert full.rights["right:title"].holder_ref == "actor:alice"
    assert full.rights["right:custody"].holder_ref == "actor:dave"
    assert full.rights["right:custody:secondary"].holder_ref == "actor:eve"


def test_same_right_type_conflict_and_unknown_type_are_zero_write() -> None:
    store = GameplayEventStore()
    service = OwnershipAuthorityService(store=store)
    service.grant_right(
        command_id="cmd:grant-custody",
        asset_ref=ASSET,
        holder_ref="actor:alice",
        right_id="right:custody",
        bond_type="custody",
        idempotency_key="grant:custody",
        causation_id="cause",
        correlation_id="corr",
    )
    before = store.read_events()

    with pytest.raises(OwnershipRuntimeError, match="ownership_right_conflict"):
        service.grant_right(
            command_id="cmd:grant-custody-again",
            asset_ref=ASSET,
            holder_ref="actor:alice",
            right_id="right:custody-again",
            bond_type="custody",
            idempotency_key="grant:custody-again",
            causation_id="cause",
            correlation_id="corr",
        )
    with pytest.raises(OwnershipRuntimeError, match="ownership_right_type_invalid"):
        service.grant_right(
            command_id="cmd:grant-invalid",
            asset_ref=ASSET,
            holder_ref="actor:bob",
            right_id="right:invalid",
            bond_type="unknown",
            idempotency_key="grant:invalid",
            causation_id="cause",
            correlation_id="corr",
        )
    with pytest.raises(OwnershipRuntimeError, match="ownership_right_type_invalid"):
        service.grant_right(
            command_id="cmd:grant-invalid-shape",
            asset_ref=ASSET,
            holder_ref="actor:bob",
            right_id="right:invalid-shape",
            bond_type=[],
            idempotency_key="grant:invalid-shape",
            causation_id="cause",
            correlation_id="corr",
        )

    assert store.read_events() == before


def test_right_transfer_cannot_duplicate_same_type_holder() -> None:
    store = GameplayEventStore()
    service = OwnershipAuthorityService(store=store)
    service.grant_right(
        command_id="cmd:grant-custody-alice",
        asset_ref=ASSET,
        holder_ref="actor:alice",
        right_id="right:custody:alice",
        bond_type="custody",
        idempotency_key="grant:custody:alice",
        causation_id="cause",
        correlation_id="corr",
    )
    service.grant_right(
        command_id="cmd:grant-custody-bob",
        asset_ref=ASSET,
        holder_ref="actor:bob",
        right_id="right:custody:bob",
        bond_type="custody",
        idempotency_key="grant:custody:bob",
        causation_id="cause",
        correlation_id="corr",
    )
    before = store.read_events()

    with pytest.raises(OwnershipRuntimeError, match="ownership_right_conflict"):
        service.transfer_right(
            command_id="cmd:transfer-custody-to-alice",
            asset_ref=ASSET,
            right_id="right:custody:bob",
            bond_type="custody",
            from_holder_ref="actor:bob",
            to_holder_ref="actor:alice",
            idempotency_key="transfer:custody:to-alice",
            causation_id="cause",
            correlation_id="corr",
        )

    assert store.read_events() == before


def test_title_transfer_rejects_non_ownership_bond_without_writes() -> None:
    store = GameplayEventStore()
    service = OwnershipAuthorityService(store=store)
    service.grant_right(
        command_id="cmd:grant-custody",
        asset_ref=ASSET,
        holder_ref="actor:alice",
        right_id="right:custody",
        bond_type="custody",
        idempotency_key="grant:custody",
        causation_id="cause",
        correlation_id="corr",
    )
    before = store.read_events()

    with pytest.raises(OwnershipRuntimeError, match="ownership_right_type_mismatch"):
        service.transfer_title(
            command_id="cmd:transfer-custody-as-title",
            asset_ref=ASSET,
            right_id="right:custody",
            from_holder_ref="actor:alice",
            to_holder_ref="actor:bob",
            idempotency_key="transfer-custody-as-title",
            causation_id="cause",
            correlation_id="corr",
        )

    assert store.read_events() == before
