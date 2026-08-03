from __future__ import annotations

import pytest

from app.gameplay.adventure_basic_reference import AdventureBasicScenario1, AdventureBasicScenarioError
from app.gameplay.ability_runtime import AbilityStateProjector
from app.gameplay.economy_runtime import EconomyProjector
from app.gameplay.equipment_runtime import EquipmentProjector
from app.gameplay.inventory_runtime import InventoryProjector
from app.gameplay.modifier_runtime import ModifierStateProjector
from app.gameplay.ownership_runtime import OwnershipProjector


def test_scenario1_seeds_purchase_and_equips_the_sword_through_existing_authorities() -> None:
    scenario = AdventureBasicScenario1.create()

    purchase = scenario.purchase_sword()
    purchase_events = scenario.store.read_transactions()[-1].events
    equip = scenario.equip_sword()
    equip_events = scenario.store.read_transactions()[-1].events

    assert purchase.committed and equip.committed
    assert [event.event_type for event in purchase_events] == [
        "gameplay.economy.account_debited",
        "gameplay.economy.account_credited",
        "gameplay.inventory.item_transferred_out",
        "gameplay.inventory.item_transferred_in",
        "gameplay.ownership.right_transferred",
        "gameplay.commerce.fixed_offer_consumed",
        "gameplay.commerce.purchase_settled",
    ]
    assert [event.event_type for event in equip_events] == [
        "gameplay.inventory.item_equipped",
        "gameplay.equipment.activation_started",
        "gameplay.modifier.source_activated",
        "gameplay.ability.grant_activated",
    ]
    assert EconomyProjector().rebuild(scenario.store.read_events()).balances == {
        scenario.player_account_id: 40,
        scenario.merchant_account_id: 80,
    }
    assert InventoryProjector(scenario.inventory_registry).rebuild(
        scenario.player_ref, scenario.store.read_events()
    ).locations == {scenario.sword_item_id: "equipment:right_hand"}
    assert OwnershipProjector().rebuild(scenario.store.read_events()).rights[
        scenario.sword_right_id
    ].holder_ref == scenario.player_ref
    assert EquipmentProjector().rebuild(scenario.player_ref, scenario.store.read_events()).active_by_slot == {
        "right_hand": "activation:adventure-basic:equip-sword"
    }
    assert AbilityStateProjector(scenario.ability_registry).rebuild(
        scenario.player_ref, scenario.store.read_events()
    ).grants
    assert ModifierStateProjector(scenario.modifier_registry).rebuild(
        scenario.player_ref, scenario.store.read_events()
    ).active_modifiers


def test_scenario1_insufficient_funds_rejects_before_purchase_or_equip_writes() -> None:
    scenario = AdventureBasicScenario1.create(player_copper=79)
    before = scenario.store.read_events()

    with pytest.raises(AdventureBasicScenarioError, match="economy_insufficient_funds"):
        scenario.purchase_sword()

    assert scenario.store.read_events() == before
