"""Bounded Task6 fault matrix over real owner/caller/store paths.

This matrix intentionally composes existing domain slices.  It proves the
failure handling that is currently implemented and records the cross-domain
scope limit in the verifier rather than implying a global cut.
"""

from pathlib import Path

import pytest

from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.facility_repair_admission import FacilityRepairCaller
from app.gameplay.resource_migration_control import ResourceMigrationControlAuthority
from app.gameplay.resource_recovery import ResourceRecoveryAuthorityService

from test_facility_repair_admission import _request
from test_resource_migration_control import _materialized, _pause
from test_resource_recovery import _store
from test_population_activation_presence_service import _proposal, _service


def test_exact_duplicate_and_lost_response_are_receipt_replays() -> None:
    store = _store()
    owner = ResourceRecoveryAuthorityService(store=store)
    first = owner.recover(
        actor_ref="char", world_ref="world", timeline_ref="timeline",
        confirmed_world_tick=20, idempotency_key="matrix:lost-response",
        expected_revision=2,
    )
    # The caller loses the response after commit and retries against the same
    # owner/store.  The persisted receipt is the recovery path.
    replay = ResourceRecoveryAuthorityService(store=store).recover(
        actor_ref="char", world_ref="world", timeline_ref="timeline",
        confirmed_world_tick=20, idempotency_key="matrix:lost-response",
        expected_revision=2,
    )
    assert first.committed and replay.idempotency_status == "duplicate_replayed"
    assert replay.committed_event_ids == first.committed_event_ids
    assert len(store.read_stream("gameplay:resources:char")) == 4


def test_changed_duplicate_is_rejected_without_write() -> None:
    store = _store()
    owner = ResourceRecoveryAuthorityService(store=store)
    owner.recover(actor_ref="char", world_ref="world", timeline_ref="timeline",
                  confirmed_world_tick=20, idempotency_key="matrix:changed",
                  expected_revision=2)
    with pytest.raises(ValueError, match="idempotency_key_reused"):
        owner.recover(actor_ref="char", world_ref="world", timeline_ref="timeline",
                      confirmed_world_tick=19, idempotency_key="matrix:changed",
                      expected_revision=4)
    assert len(store.read_stream("gameplay:resources:char")) == 4


def test_partial_success_retries_only_missing_domain_step() -> None:
    store, service = _service()
    first = service.commit_and_spawn(
        _proposal(), presence_idempotency_key="matrix:partial", presence_expected_revision=99
    )
    assert first.activation.committed and first.recovery_required
    assert not first.presence.committed
    assert len(store.read_stream("population:world:bakery")) == 1
    retry = service.commit_and_spawn(
        _proposal(), presence_idempotency_key="matrix:partial", presence_expected_revision=0
    )
    assert retry.activation.idempotency_status == "duplicate_replayed"
    assert retry.presence.committed
    assert len(store.read_stream("population:world:bakery")) == 1
    assert len(store.read_stream("presence:world:bakery")) == 1


def test_expired_and_revoked_grants_fail_closed() -> None:
    caller = FacilityRepairCaller(store=GameplayEventStore())
    expired = _request(owner_grant=_request().owner_grant.model_copy(update={"valid_until_world_tick": 3}))
    revoked = _request(owner_grant=_request().owner_grant.model_copy(update={"revoked": True}))
    assert caller.admit(expired).stop_reason == "facility_grant_invalid"
    assert caller.admit(revoked).stop_reason == "facility_grant_invalid"


def test_revision_conflict_and_migration_failure_are_zero_write() -> None:
    store = GameplayEventStore()
    _materialized(store)
    owner = ResourceMigrationControlAuthority(store=store)
    with pytest.raises(ValueError, match="resource_migration_resource_revision_conflict"):
        _pause(owner, expected_resource_revision=2)
    assert store.read_stream("gameplay:resource-migration-control:char_a") == []
    # A second migration with an active first pause is rejected as overlap.
    assert _pause(owner).committed
    with pytest.raises(ValueError, match="migration_overlap"):
        _pause(owner, migration_id="migration:2", idempotency_key="pause:2", expected_control_revision=1)


def test_durable_new_instance_replays_receipt_and_full_checkpoint_tail_match(tmp_path: Path) -> None:
    path = tmp_path / "task6-matrix.sqlite3"
    store = DurableGameplayEventStore(path)
    owner = ResourceRecoveryAuthorityService(store=store)
    # Use the established fixture on this exact Durable instance.
    from test_resource_recovery import _cadence, _append
    _cadence(store)
    _append(store, "gameplay:resources:char", [("gameplay.resource.materialized", {
        "actor_ref": "char", "resource_id": "core.stamina", "minimum": 0,
        "maximum": 10, "current": 2, "definition_version": "v1",
        "materialized_world_tick": 0, "world_ref": "world", "timeline_ref": "timeline",
        "recovery_amount": 3, "recovery_period_world_ticks": 5,
    })], "matrix:materialize")
    first = owner.recover(actor_ref="char", world_ref="world", timeline_ref="timeline",
                          confirmed_world_tick=20, idempotency_key="matrix:durable",
                          expected_revision=1)
    store.close()
    reopened = DurableGameplayEventStore(path)
    replay = ResourceRecoveryAuthorityService(store=reopened).recover(
        actor_ref="char", world_ref="world", timeline_ref="timeline",
        confirmed_world_tick=20, idempotency_key="matrix:durable", expected_revision=1,
    )
    assert replay.idempotency_status == "duplicate_replayed"
    events = reopened.read_stream("gameplay:resources:char")
    from app.gameplay.resource_body_runtime import ResourceBodyRuntimeProjector
    projector = ResourceBodyRuntimeProjector()
    full = projector.rebuild_resources("char", events)
    tail = projector.rebuild_resources("char", events[1:], checkpoint=projector.rebuild_resources("char", events[:1]))
    assert tail == full
    assert replay.committed_event_ids == first.committed_event_ids
    reopened.close()


def test_world_batch_partial_commit_survives_durable_reopen_without_duplicate_events(tmp_path: Path) -> None:
    from app.gameplay.econ1_economy_runtime import EconomyAuthority
    from app.gameplay.organization_government_runtime import OrganizationAuthority
    from app.world_runtime.batch_settlement import BatchSettlementCoordinator, EconomyWageBatchAdapter, OrganizationWindowBatchAdapter
    from test_world_batch_settlement_recovery import _plan as batch_plan, _setup as batch_setup

    path = tmp_path / "task6-batch-reopen.sqlite3"
    store = DurableGameplayEventStore(path)
    _, org, econ, first, second = batch_setup(store=store)
    plan = batch_plan(first, second)
    partial = BatchSettlementCoordinator(adapters=(org, econ)).execute(plan, budget=1)
    assert partial.stage == "pending_recovery" and len(store.read_events()) == 1
    store.close()

    reopened = DurableGameplayEventStore(path)
    org2 = OrganizationWindowBatchAdapter(owner=OrganizationAuthority(store=reopened), store=reopened)
    econ2 = EconomyWageBatchAdapter(owner=EconomyAuthority(store=reopened), store=reopened)
    recovered = BatchSettlementCoordinator(adapters=(org2, econ2)).execute(plan, budget=1)
    assert recovered.stage == "completed"
    assert [receipt.status for receipt in recovered.receipts] == ["committed", "committed"]
    assert len(reopened.read_events()) == 2
    replay = BatchSettlementCoordinator(adapters=(org2, econ2)).execute(plan, budget=0)
    assert replay.stage == "completed" and replay.receipts == recovered.receipts
    assert len(reopened.read_events()) == 2
    reopened.close()


def test_same_durable_cut_replays_batch_and_resource_owner_events_together(tmp_path: Path) -> None:
    """One ledger cut must replay mixed admitted owners identically."""
    from app.gameplay.replay import GameplayProjectionReplay
    from app.world_runtime.batch_settlement import BatchSettlementCoordinator
    from test_world_batch_settlement_recovery import _plan as batch_plan, _setup as batch_setup
    from test_resource_recovery import _append, _cadence

    path = tmp_path / "task6-same-cut.sqlite3"
    store = DurableGameplayEventStore(path)
    _cadence(store)
    _append(store, "gameplay:resources:char", [("gameplay.resource.materialized", {
        "actor_ref": "char", "resource_id": "core.stamina", "minimum": 0, "maximum": 10,
        "current": 2, "definition_version": "v1", "materialized_world_tick": 0,
        "world_ref": "world", "timeline_ref": "timeline", "recovery_amount": 3,
        "recovery_period_world_ticks": 5,
    })], "same-cut:materialize")
    _, org, econ, first, second = batch_setup(store=store)
    plan = batch_plan(first, second)
    assert BatchSettlementCoordinator(adapters=(org, econ)).execute(plan, budget=2).stage == "completed"
    recovery = ResourceRecoveryAuthorityService(store=store).recover(
        actor_ref="char", world_ref="world", timeline_ref="timeline", confirmed_world_tick=20,
        idempotency_key="same-cut:recovery", expected_revision=1,
    )
    assert recovery.committed
    events = store.read_events()
    assert {event.stream_id for event in events} >= {
        "population-cadence:world", "gameplay:resources:char",
        "gameplay:organization:window:window:1", "gameplay:economy:wage:character:char_b",
    }
    replay = GameplayProjectionReplay(projector_id="task6-same-cut", projector_version="1")
    full = replay.full_replay(events)
    cut = max(1, len(events) // 2)
    checkpoint = replay.create_checkpoint(events[:cut])
    checkpoint_tail = replay.checkpoint_plus_tail_replay(checkpoint, events[cut:])
    assert full.succeeded and checkpoint_tail.succeeded
    assert full.projection_hash == checkpoint_tail.projection_hash
    assert full.state == checkpoint_tail.state
    store.close()
