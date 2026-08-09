from __future__ import annotations

import pytest

from app.gameplay.bakery_reference_runtime import BakeryReferenceScenario
from app.gameplay.construction_production_runtime import (
    ConstructionProductionAuthority,
    Facility,
    Recipe,
)
from app.gameplay.econ1_economy_runtime import EconomyAuthority
from app.gameplay.economy_runtime import EconomyProjector
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.organization_government_runtime import GovernmentAuthority, Inspection, Permit
from app.gameplay.inventory_runtime import InventoryDefinitionRegistry, InventoryProjector, ItemDefinition
from app.gameplay.survival_runtime import NeedDefinition, NeedState, SurvivalAuthority, SurvivalMode, SurvivalPolicy


def _facility() -> Facility:
    return Facility(facility_ref="facility:bakery", plot_ref="plot:bakery", facility_kind="bakery", condition=1)


def _recipe() -> Recipe:
    return Recipe(recipe_ref="recipe:bread:v1", inputs={"flour": 2}, output_item="bread", duration_ticks=1)


def test_production_start_and_finish_append_authority_events() -> None:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    started = authority.settle_start_run(
        facility=_facility(), recipe=_recipe(), run_ref="run:1", tick=1,
        command_id="production-start:run:1", idempotency_key="production-start:run:1",
        causation_id="cause:run:1", correlation_id="correlation:run:1",
    )
    completed = authority.settle_finish_run(
        authority.projector().runs["run:1"], tick=2, recipe=_recipe(),
        command_id="production-finish:run:1", idempotency_key="production-finish:run:1",
        causation_id="cause:run:1", correlation_id="correlation:run:1",
    )
    assert completed.committed is True
    assert [event.event_type for event in store.read_events()] == [
        "gameplay.construction_production.run_started",
        "gameplay.construction_production.run_finished",
    ]


def test_survival_disabled_has_no_hidden_write_and_enabled_tick_settles() -> None:
    store = GameplayEventStore()
    definition = NeedDefinition(need_ref="need:food", category="food", decay_per_tick=0.6)
    state = NeedState(need_ref="need:food", value=1, last_tick=0)
    authority = SurvivalAuthority(store=store)
    with pytest.raises(ValueError, match="survival_mode_no_authority_tick"):
        authority.settle_tick(
        actor_ref="character:owner",
        policy=SurvivalPolicy(policy_ref="survival:food", mode=SurvivalMode.DISABLED, revision="policy:v1"),
        definition=definition,
        state=state,
        tick=1,
        command_id="survival:disabled", idempotency_key="survival:disabled", causation_id="cause:disabled", correlation_id="corr:disabled",
    )
    assert store.read_events() == []
    enabled = authority.settle_tick(
        actor_ref="character:owner",
        policy=SurvivalPolicy(policy_ref="survival:food", mode=SurvivalMode.SIMULATION, revision="policy:v1"),
        definition=definition,
        state=state,
        tick=1, command_id="survival:enabled", idempotency_key="survival:enabled", causation_id="cause:enabled", correlation_id="corr:enabled",
    )
    assert enabled.committed is True
    assert store.read_events()[-1].event_type == "gameplay.survival.need_tick"


def test_economy_postings_and_government_assessment_append_events() -> None:
    store = GameplayEventStore()
    purchase = EconomyAuthority.post_purchase(
        store=store,
        buyer_ref="org:bakery",
        seller_ref="supplier:flour",
        item_ref="flour",
        quantity=2,
        total_amount=4,
        quote_ref="quote:flour:1",
        tick=1,
    )
    sale = EconomyAuthority.post_sale(
        store=store,
        seller_ref="org:bakery",
        buyer_ref="demand:aggregate",
        item_ref="bread",
        quantity=1,
        total_amount=10,
        tick=2,
    )
    assessment = GovernmentAuthority.assess_tax_and_settle(
        store=store,
        organization_ref="org:bakery",
        period_ref="period:1",
        revenue=10,
        rate=0.1,
        policy_revision="policy:v1",
    )
    assert purchase.committed and sale.committed and assessment.committed
    assert [event.event_type for event in store.read_events()] == [
        "gameplay.economy.purchase_posted",
        "gameplay.economy.sale_posted",
        "gameplay.government.tax_assessed",
    ]


def test_bakery_period_uses_shared_store_and_is_idempotent() -> None:
    store = GameplayEventStore()
    scenario = BakeryReferenceScenario.default()
    first = scenario.execute_period(1, store=store)
    duplicate = scenario.execute_period(1, store=store)
    assert first.closed is True
    assert duplicate.closed is True
    assert len(store.read_events()) >= 7
    assert any(event.event_type == "gameplay.economy.business_period_closed" for event in store.read_events())


def test_bakery_period_settles_account_balances() -> None:
    store = GameplayEventStore()
    BakeryReferenceScenario.default().execute_period(1, store=store)
    projection = EconomyProjector().rebuild(store.read_events())
    assert projection.balances["account:bakery"] == 106
    assert projection.balances["account:supplier"] == 4
    assert projection.balances["account:demand"] == 90


def test_three_bakery_periods_are_replayable_from_one_event_store() -> None:
    store = GameplayEventStore()
    periods = BakeryReferenceScenario.default().run_three_periods(store=store)
    assert [period.sequence for period in periods] == [1, 2, 3]
    assert len(store.read_events()) >= 30


def test_bakery_period_receives_inputs_and_outputs_through_inventory_owner() -> None:
    store = GameplayEventStore()
    BakeryReferenceScenario.default().execute_period(1, store=store)
    registry = InventoryDefinitionRegistry()
    registry.register_item(ItemDefinition("item:flour", "v1", 1, 1))
    registry.register_item(ItemDefinition("item:bread", "v1", 1, 1))
    inventory = InventoryProjector(registry).rebuild("org:bakery", store.read_events())
    assert "item:flour:1" not in inventory.items
    assert "item:bread:1" not in inventory.items
