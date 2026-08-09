from __future__ import annotations

from app.gameplay.bakery_reference_runtime import BakeryReferenceScenario
from app.gameplay.econ1_economy_runtime import EconomyAuthority
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.organization_government_runtime import GovernmentAuthority


def test_bakery_composes_three_replayable_periods_with_owner_boundaries() -> None:
    scenario = BakeryReferenceScenario.default()
    periods = scenario.run_three_periods()
    assert [period.sequence for period in periods] == [1, 2, 3]
    assert all(period.closed for period in periods)
    assert all(period.policy_revision == "policy:v1" for period in periods)


def test_bakery_reserves_and_consumes_recipe_inputs_through_inventory_authority() -> None:
    store = GameplayEventStore()
    BakeryReferenceScenario.default().execute_period(1, store=store)
    event_types = [event.event_type for event in store.read_events()]
    assert event_types.count("gameplay.inventory.reservation_created") == 2
    assert event_types.count("gameplay.inventory.reservation_consumed") == 2
    input_consumed = event_types.index("gameplay.inventory.reservation_consumed")
    output_received = event_types.index("gameplay.inventory.output_received")
    sale_posted = event_types.index("gameplay.economy.sale_posted")
    assert input_consumed < output_received < sale_posted


def test_bakery_does_not_use_legacy_static_settlement_helpers(monkeypatch) -> None:
    def fail(**_: object) -> None:
        raise AssertionError("legacy static settlement helper called")

    monkeypatch.setattr(EconomyAuthority, "post_purchase", staticmethod(fail))
    monkeypatch.setattr(EconomyAuthority, "post_sale", staticmethod(fail))
    monkeypatch.setattr(GovernmentAuthority, "require_permit_and_settle", staticmethod(fail))
    monkeypatch.setattr(GovernmentAuthority, "assess_tax_and_settle", staticmethod(fail))
    monkeypatch.setattr(EconomyAuthority, "close_period_and_settle", staticmethod(fail))
    result = BakeryReferenceScenario.default().execute_period(1, store=GameplayEventStore())
    assert result.closed
