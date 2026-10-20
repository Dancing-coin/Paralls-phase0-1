from pathlib import Path
from hashlib import sha256

from app.gameplay.event_store import DurableGameplayEventStore
from app.gameplay.resource_body_runtime import (
    ResourceBodyRuntimeError,
    ResourceBodyRuntimeProjector,
    ResourceReservationAuthorityService,
    ResourceReservationCommand,
)


ACTOR = "actor:v2"
STREAM = f"gameplay:resources:{ACTOR}"


def _materialize(store: DurableGameplayEventStore) -> None:
    result = store.append_batch({
        "transaction_id": "tx:materialize", "command_id": "materialize",
        "expected_stream_revisions": {STREAM: 0}, "pinned_revisions": {},
        "events": [{"event_id": "evt:materialize", "event_type": "gameplay.resource.materialized", "schema_version": 1,
                    "stream_id": STREAM, "stream_revision": 0, "global_sequence": 0, "transaction_id": "tx:materialize",
                    "command_id": "materialize", "causation_id": "materialize", "correlation_id": "v2",
                    "visibility_policy": "authority_only", "payload": {"actor_ref": ACTOR, "resource_id": "core.stamina",
                    "minimum": 0, "maximum": 10, "current": 7, "definition_version": "v2", "resource_schema": "resource.v2",
                    "capacity": 10, "base_capacity": 10, "locked": 0, "debt": 0, "debt_ceiling": 0,
                    "modifier_ledger": [], "modifier_ledger_digest": "sha256:" + sha256(b"[]").hexdigest()}}],
        "idempotency_record": {"principal_ref": "v2-test", "idempotency_key": "materialize", "payload_digest": "sha256:materialize"},
        "outbox_entries": [], "result_digest": "sha256:materialize", "projection_refresh_hints": [],
    })
    assert result.committed


def _command(operation: str, *, key: str, lock_ref: str | None = "lock:slash") -> ResourceReservationCommand:
    return ResourceReservationCommand(command_id=f"cmd:{key}", actor_ref=ACTOR, authority_principal="gameplay_authority",
        idempotency_key=key, payload_digest=f"sha256:{key}", causation_id=f"cause:{key}", correlation_id="corr:v2",
        operation=operation, resource_id="core.stamina", reservation_ref="reservation:slash", amount=3 if operation == "reserve" else None,
        lock_ref=lock_ref)


def test_v2_reserve_consume_lock_lifecycle_does_not_double_subtract_available(tmp_path: Path) -> None:
    store = DurableGameplayEventStore(tmp_path / "v2-lock.db")
    _materialize(store)
    service = ResourceReservationAuthorityService(store=store)
    projector = ResourceBodyRuntimeProjector()
    reserved = service.apply(_command("reserve", key="reserve"), projector.rebuild_resources(ACTOR, store.read_events()))
    assert reserved.committed
    tx = store.get_transaction(reserved.transaction_id)
    assert tx is not None and len(tx.events) == 2
    projection = projector.rebuild_resources(ACTOR, store.read_events())
    entry = projection.entries["core.stamina"]
    assert (entry.current, entry.reserved, entry.locked, entry.available) == (7, 3, 3, 4)
    assert projection.locks["lock:slash"] == ("reservation:slash", "core.stamina", 3, "open")
    consumed = service.apply(_command("consume", key="consume"), projection)
    assert consumed.committed
    final = projector.rebuild_resources(ACTOR, store.read_events())
    entry = final.entries["core.stamina"]
    assert (entry.current, entry.reserved, entry.locked, entry.available) == (4, 0, 0, 4)
    assert final.locks["lock:slash"][-1] == "consumed"
    store.close()


def test_v2_release_rejects_stale_lock_ref_and_durable_reopen_checkpoint_parity(tmp_path: Path) -> None:
    path = tmp_path / "v2-release.db"
    store = DurableGameplayEventStore(path)
    _materialize(store)
    service = ResourceReservationAuthorityService(store=store)
    projector = ResourceBodyRuntimeProjector()
    service.apply(_command("reserve", key="reserve-release"), projector.rebuild_resources(ACTOR, store.read_events()))
    before = len(store.read_events())
    try:
        service.apply(_command("release", key="release-bad", lock_ref="lock:wrong"), projector.rebuild_resources(ACTOR, store.read_events()))
    except ValueError as exc:
        assert str(exc) == "resource_lock_unknown"
    else:
        raise AssertionError("stale lock ref unexpectedly accepted")
    assert len(store.read_events()) == before
    events = store.read_events()
    full = projector.rebuild_resources(ACTOR, events)
    checkpoint = projector.rebuild_resources(ACTOR, events[:1])
    checkpointed = projector.rebuild_resources(ACTOR, events[1:], checkpoint=checkpoint)
    assert checkpointed == full
    store.close()
    reopened = DurableGameplayEventStore(path)
    assert ResourceBodyRuntimeProjector().rebuild_resources(ACTOR, reopened.read_events()) == full
    reopened.close()


def test_v2_exact_duplicate_replays_pair_and_changed_duplicate_writes_zero(tmp_path: Path) -> None:
    store = DurableGameplayEventStore(tmp_path / "v2-duplicate.db")
    _materialize(store)
    service = ResourceReservationAuthorityService(store=store)
    projector = ResourceBodyRuntimeProjector()
    command = _command("reserve", key="duplicate")
    first = service.apply(command, projector.rebuild_resources(ACTOR, store.read_events()))
    assert first.committed and len(store.read_events()) == 3
    exact = service.apply(command, projector.rebuild_resources(ACTOR, store.read_events()))
    assert exact.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == 3
    changed = command.model_copy(update={"lock_ref": "lock:other", "payload_digest": "sha256:changed"})
    try:
        service.apply(changed, projector.rebuild_resources(ACTOR, store.read_events()))
    except ValueError as exc:
        assert str(exc) == "idempotency_key_reused"
    else:
        raise AssertionError("changed duplicate unexpectedly accepted")
    assert len(store.read_events()) == 3
    store.close()


def test_v2_incomplete_pair_and_tampered_checkpoint_are_rejected(tmp_path: Path) -> None:
    store = DurableGameplayEventStore(tmp_path / "v2-integrity.db")
    _materialize(store)
    service = ResourceReservationAuthorityService(store=store)
    projector = ResourceBodyRuntimeProjector()
    service.apply(_command("reserve", key="integrity"), projector.rebuild_resources(ACTOR, store.read_events()))
    events = store.read_events()
    reservation_only = [event for event in events if event.event_type != "gameplay.resource.lock_created"]
    try:
        projector.rebuild_resources(ACTOR, reservation_only)
    except ResourceBodyRuntimeError as exc:
        assert str(exc) == "resource_lock_batch_incomplete"
    else:
        raise AssertionError("incomplete resource lock batch unexpectedly replayed")
    full = projector.rebuild_resources(ACTOR, events)
    tampered = full.__class__(
        actor_ref=full.actor_ref, entries=full.entries, reservations=full.reservations,
        source_revision_vector=full.source_revision_vector, projection_revision="sha256:" + "0" * 64,
        locks=full.locks,
    )
    try:
        projector.rebuild_resources(ACTOR, [], checkpoint=tampered)
    except ResourceBodyRuntimeError as exc:
        assert str(exc) == "resource_checkpoint_digest_invalid"
    else:
        raise AssertionError("tampered checkpoint unexpectedly accepted")
    store.close()


def test_v2_lock_pair_rejects_tampered_lock_binding_and_amount(tmp_path: Path) -> None:
    store = DurableGameplayEventStore(tmp_path / "v2-lock-pair-tamper.db")
    _materialize(store)
    service = ResourceReservationAuthorityService(store=store)
    projector = ResourceBodyRuntimeProjector()
    service.apply(_command("reserve", key="pair-tamper"), projector.rebuild_resources(ACTOR, store.read_events()))
    events = store.read_events()
    reservation_index = next(i for i, event in enumerate(events) if event.event_type == "gameplay.resource.reservation_created")
    reservation = events[reservation_index]
    events[reservation_index] = reservation.model_copy(update={
        "payload": {**dict(reservation.payload), "lock_ref": "lock:forged"}
    }, deep=True)
    try:
        projector.rebuild_resources(ACTOR, events)
    except ResourceBodyRuntimeError as exc:
        assert str(exc) == "resource_lock_batch_mismatch"
    else:
        raise AssertionError("tampered lock binding unexpectedly replayed")

    events = store.read_events()
    lock_index = next(i for i, event in enumerate(events) if event.event_type == "gameplay.resource.lock_created")
    lock = events[lock_index]
    events[lock_index] = lock.model_copy(update={
        "payload": {**dict(lock.payload), "amount": 4}
    }, deep=True)
    try:
        projector.rebuild_resources(ACTOR, events)
    except ResourceBodyRuntimeError as exc:
        assert str(exc) == "resource_lock_batch_mismatch"
    else:
        raise AssertionError("tampered lock amount unexpectedly replayed")
    store.close()


def test_v2_duplicate_receipt_rejects_transaction_result_digest_drift(tmp_path: Path) -> None:
    store = DurableGameplayEventStore(tmp_path / "v2-lock-digest-tamper.db")
    _materialize(store)
    service = ResourceReservationAuthorityService(store=store)
    projector = ResourceBodyRuntimeProjector()
    command = _command("reserve", key="digest-tamper")
    first = service.apply(command, projector.rebuild_resources(ACTOR, store.read_events()))
    assert first.committed

    class TamperedDigestStore:
        def __getattr__(self, name: str):
            return getattr(store, name)

        def get_transaction(self, transaction_id: str):
            transaction = store.get_transaction(transaction_id)
            if transaction is None:
                return None
            return transaction.model_copy(update={"result_digest": "sha256:forged"}, deep=True)

    service._store = TamperedDigestStore()
    try:
        service.apply(command, projector.rebuild_resources(ACTOR, store.read_events()))
    except ValueError as exc:
        assert str(exc) == "resource_reservation_receipt_incomplete"
    else:
        raise AssertionError("duplicate receipt with a changed transaction digest was accepted")
    store.close()



def test_orphan_lock_release_cannot_bypass_atomic_reservation_pair(tmp_path):
    import pytest
    store = DurableGameplayEventStore(tmp_path / "orphan.db")
    _materialize(store)
    projector = ResourceBodyRuntimeProjector()
    owner = ResourceReservationAuthorityService(store=store)
    owner.apply(_command("reserve", key="orphan-reserve"), projector.rebuild_resources(ACTOR, store.read_events()))
    owner.apply(_command("release", key="orphan-release"), projector.rebuild_resources(ACTOR, store.read_events()))
    events = [event for event in store.read_events() if event.event_type != "gameplay.resource.reservation_released"]
    with pytest.raises(ResourceBodyRuntimeError, match="resource_lock_batch_incomplete"):
        projector.rebuild_resources(ACTOR, events)
    store.close()
