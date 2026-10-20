from __future__ import annotations

import pytest

from app.gameplay.event_store import DurableGameplayEventStore
from app.gameplay.inventory_runtime import InventoryAuthorityService
from app.population_continuity.inventory_owner_adapter import InventoryOutputCustodyOwnerExecutor
from app.population_continuity.roster import PopulationRoster
from app.population_continuity.runtime_publication import RuntimeCadencePublisher
from app.population_continuity.siming_contracts import PopulationReadSet
from app.population_continuity.world import WorldContinuityRuntime
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.siming_population_capability import PopulationSimulationCapability
from test_population_runtime_driver import _mode
from test_siming_population_inventory_vertical import _fixture, _read_set


def _context(*, admitted=True, durable_path=None):
    store, inventory, certification = _fixture()
    if durable_path is not None:
        store.save_snapshot(durable_path)
        store = DurableGameplayEventStore(durable_path)
        inventory = InventoryAuthorityService(store=store, registry=inventory._registry, package_registry=inventory._package_registry)
    world = WorldContinuityRuntime(
        store=store, mode=_mode().model_copy(update={"world_ref": "world:bakery"}),
        roster=PopulationRoster(actor_ids=("worker",)),
    )
    assert world.resume().committed
    cadence = world.build_population_cadence(window_start=0, window_end=60)
    publisher = RuntimeCadencePublisher(
        world_runtime=world, event_bus=InMemoryAuthorityEventBus(),
        room_id="room", scene_id="scene", zone_id="zone",
    )
    if admitted:
        assert publisher(cadence) is not None
    projections = _read_set(certification).projections
    read_set = PopulationReadSet.from_inputs(cadence, projections)
    return store, inventory, publisher, read_set


def _run(inventory, read_set):
    return PopulationSimulationCapability(owner_executors={
        "population:inventory-output-custody:v1": InventoryOutputCustodyOwnerExecutor(authority=inventory),
    }).run_default_decision_cycle(read_set.cadence, read_set)


def _revoke(publisher, read_set):
    result = publisher.revoke_cadence(
        cadence_id=read_set.cadence.cadence_id, reason_code="operator_stop",
        caller_principal_ref="world_admin",
    )
    assert result.committed


def test_original_admitted_cadence_reaches_inventory_and_replays_without_write():
    store, inventory, _, read_set = _context()
    first = _run(inventory, read_set)
    assert first.owner_receipts[0].committed
    sequence = store.get_last_global_sequence()
    again = _run(inventory, read_set)
    assert again.owner_receipts[0].idempotency_status == "duplicate_replayed"
    assert again.owner_receipts[0].zero_write
    assert store.get_last_global_sequence() == sequence


@pytest.mark.parametrize("denial", ["unadmitted", "revoked", "changed_cadence"])
def test_inventory_denies_untrusted_or_revoked_cadence_without_write(denial):
    store, inventory, publisher, read_set = _context(admitted=denial != "unadmitted")
    if denial == "revoked":
        _revoke(publisher, read_set)
    elif denial == "changed_cadence":
        read_set = PopulationReadSet.from_inputs(
            read_set.cadence.model_copy(update={"window_end": 61}), read_set.projections,
        )
    sequence = store.get_last_global_sequence()
    result = _run(inventory, read_set)
    assert not result.owner_receipts[0].committed
    assert result.owner_receipts[0].zero_write
    assert store.get_last_global_sequence() == sequence


@pytest.mark.parametrize("durable", [False, True])
def test_revocation_between_admission_check_and_inventory_append_is_zero_write(monkeypatch, tmp_path, durable):
    store, inventory, publisher, read_set = _context(
        durable_path=tmp_path / "inventory.db" if durable else None,
    )
    append = store.append_batch
    raced = []

    def append_after_revocation(batch):
        if any(event.event_type == "gameplay.inventory.production_output_received@1" for event in batch.events):
            _revoke(publisher, read_set)
            raced.append(store.get_last_global_sequence())
        return append(batch)

    monkeypatch.setattr(store, "append_batch", append_after_revocation)
    result = _run(inventory, read_set)
    assert raced, "must reach the original inventory append after checking cadence"
    assert not result.owner_receipts[0].committed
    assert result.owner_receipts[0].zero_write
    assert store.get_last_global_sequence() == raced[0]
    if durable:
        store.close()


def test_durable_reopen_keeps_revocation_effective_for_original_inventory_owner(tmp_path):
    path = tmp_path / "inventory.db"
    store, inventory, publisher, read_set = _context(durable_path=path)
    _revoke(publisher, read_set)
    sequence = store.get_last_global_sequence()
    store.close()
    reopened = DurableGameplayEventStore(path)
    try:
        authority = InventoryAuthorityService(store=reopened, registry=inventory._registry, package_registry=inventory._package_registry)
        result = _run(authority, read_set)
        assert not result.owner_receipts[0].committed
        assert result.owner_receipts[0].zero_write
        assert reopened.get_last_global_sequence() == sequence
    finally:
        reopened.close()
