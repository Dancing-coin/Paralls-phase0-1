from __future__ import annotations

import pytest

from app.gameplay.adventure_basic_reference import (
    AdventureBasicScenario3,
    AdventureBasicScenarioError,
)
from app.gameplay.inventory_runtime import InventoryRuntimeError


def _equipped_scenario() -> AdventureBasicScenario3:
    scenario = AdventureBasicScenario3.create()
    assert scenario.equip_storage_ring().committed
    return scenario


def test_scenario3_equipped_storage_ring_moves_cargo_to_the_authorized_interior_and_excludes_its_weight() -> None:
    scenario = _equipped_scenario()

    transfer = scenario.move_to_storage_ring(scenario.cargo_item_id)
    inventory = scenario.inventory()
    encumbrance = scenario.encumbrance()
    explanation = {entry.item_id: entry for entry in encumbrance.explanation_entries}

    assert transfer.committed
    assert inventory.locations[scenario.storage_ring_item_id] == "equipment:finger"
    assert inventory.locations[scenario.cargo_item_id] == scenario.storage_ring_container_id
    assert scenario.storage_ring_access().active
    assert encumbrance.carried_weight == scenario.storage_ring_weight
    assert explanation[scenario.storage_ring_item_id].propagation_strategy == "carrier_item"
    assert explanation[scenario.storage_ring_item_id].included_weight == scenario.storage_ring_weight
    assert explanation[scenario.cargo_item_id].propagation_strategy == "exclude_contents"
    assert explanation[scenario.cargo_item_id].included_weight == 0
    assert explanation[scenario.cargo_item_id].excluded_weight == scenario.cargo_weight
    assert explanation[scenario.cargo_item_id].source_refs


@pytest.mark.parametrize(
    ("item_id", "error_code"),
    [
        ("item:adventure-basic:living-cargo", "inventory_living_item_rejected"),
        ("item:adventure-basic:overflow-cargo", "inventory_capacity_exceeded"),
    ],
)
def test_scenario3_rejects_living_or_over_capacity_ring_contents_without_partial_mutation(
    item_id: str,
    error_code: str,
) -> None:
    scenario = _equipped_scenario()
    before_events = scenario.store.read_events()
    before_inventory = scenario.inventory()

    with pytest.raises(AdventureBasicScenarioError, match=error_code):
        scenario.move_to_storage_ring(item_id)

    assert scenario.store.read_events() == before_events
    assert scenario.inventory() == before_inventory
    assert scenario.storage_ring_access().active


def test_scenario3_refuses_to_unequip_a_non_empty_ring_then_revokes_access_after_emptying() -> None:
    scenario = _equipped_scenario()
    assert scenario.move_to_storage_ring(scenario.cargo_item_id).committed
    before_failed_unequip = scenario.store.read_events()
    before_inventory = scenario.inventory()

    with pytest.raises(AdventureBasicScenarioError, match="equipment_container_non_empty"):
        scenario.unequip_storage_ring()

    assert scenario.store.read_events() == before_failed_unequip
    assert scenario.inventory() == before_inventory
    assert scenario.storage_ring_access().active

    assert scenario.move_from_storage_ring(scenario.cargo_item_id).committed
    unequip = scenario.unequip_storage_ring()

    assert unequip.committed
    assert not scenario.storage_ring_access().active
    assert scenario.inventory().locations[scenario.storage_ring_item_id] == scenario.player_backpack_id
    with pytest.raises(AdventureBasicScenarioError, match="equipment_container_access_denied"):
        scenario.move_to_storage_ring(scenario.cargo_item_id)


def test_scenario3_generic_inventory_writer_cannot_bypass_the_equipment_owned_container_access_gate() -> None:
    scenario = AdventureBasicScenario3.create()
    before = scenario.store.read_events()

    with pytest.raises(InventoryRuntimeError, match="inventory_container_access_requires_equipment"):
        scenario._inventory.move(
            command_id="adventure-basic:scenario-3:forbidden-generic-move",
            actor_ref=scenario.player_ref,
            item_id=scenario.cargo_item_id,
            from_container_id=scenario.player_backpack_id,
            to_container_id=scenario.storage_ring_container_id,
            idempotency_key="adventure-basic:scenario-3:forbidden-generic-move",
            causation_id="adventure-basic:scenario-3",
            correlation_id="adventure-basic:scenario-3",
        )

    assert scenario.store.read_events() == before
