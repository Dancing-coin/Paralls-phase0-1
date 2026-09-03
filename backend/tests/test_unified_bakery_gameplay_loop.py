from __future__ import annotations

import pytest

from app.gameplay.bakery_reference_runtime import BakeryReferenceScenario
from app.gameplay.econ1_economy_runtime import EconomyAuthority
from app.gameplay.economy_runtime import EconomyAuthorityService, EconomyProjector
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import ContainerSpec, InventoryProjector
from app.gameplay.shared_contracts import SettlementReceipt


def _scenario_with_expired_permit() -> BakeryReferenceScenario:
    scenario = BakeryReferenceScenario.default()
    return BakeryReferenceScenario(**{**scenario.__dict__, "permit": scenario.permit.model_copy(update={"expires_tick": 0})})


def test_three_period_loop_commits_three_distinct_period_receipts() -> None:
    store = GameplayEventStore()
    periods = BakeryReferenceScenario.default().run_three_periods(store=store)

    assert [period.period_ref for period in periods] == [
        "period:bakery:1",
        "period:bakery:2",
        "period:bakery:3",
    ]

    receipts = [
        SettlementReceipt.from_append_result(
            result=store.get_by_idempotency(EconomyAuthority._PRINCIPAL, f"period-close:period:bakery:{sequence}"),
        )
        for sequence in range(1, 4)
    ]
    assert [receipt.committed_event_ids for receipt in receipts]
    assert len({receipt.transaction_id for receipt in receipts}) == 3


def test_employee_period_records_wage_accrual_and_payment() -> None:
    store = GameplayEventStore()
    scenario = BakeryReferenceScenario.default().with_existing_character_employee("character:char_b")
    scenario.execute_period(1, store=store)
    event_types = [event.event_type for event in store.read_events()]
    assert "gameplay.economy.wage_accrued" in event_types
    assert "gameplay.economy.wage_paid" in event_types
    assert "gameplay.contract.record_created" in event_types


def test_three_period_employee_loop_pays_each_period() -> None:
    store = GameplayEventStore()
    scenario = BakeryReferenceScenario.default().with_existing_character_employee("character:char_b")
    periods = scenario.run_three_periods(store=store)
    event_types = [event.event_type for event in store.read_events()]
    assert len(periods) == 3
    assert event_types.count("gameplay.economy.wage_accrued") == 3
    assert event_types.count("gameplay.economy.wage_paid") == 3


def test_simulation_survival_mode_records_owner_tick_in_period() -> None:
    store = GameplayEventStore()
    scenario = BakeryReferenceScenario.default()
    scenario.execute_period(1, store=store, survival_mode="simulation")
    assert any(event.event_type == "gameplay.survival.need_tick" for event in store.read_events())


@pytest.mark.parametrize(
    ("prepare_store", "scenario", "expected_error"),
    [
        (
            lambda store: _seed_low_flour(store),
            BakeryReferenceScenario.default(),
            "inventory_reservation_insufficient",
        ),
        (
            lambda store: _seed_low_balance(store),
            BakeryReferenceScenario.default(),
            "economy_insufficient_funds",
        ),
        (
            lambda store: None,
            BakeryReferenceScenario.default().with_employee("character:synthetic"),
            "character_record_required",
        ),
        (
            lambda store: None,
            _scenario_with_expired_permit(),
            "permit_expired",
        ),
    ],
)
def test_period_validation_failures_are_zero_write(prepare_store, scenario, expected_error) -> None:
    store = GameplayEventStore()
    prepare_store(store)
    before = tuple(store.read_events())
    with pytest.raises(ValueError, match=expected_error):
        scenario.execute_period(1, store=store)
    assert tuple(store.read_events()) == before


def _seed_low_flour(store: GameplayEventStore) -> None:
    scenario = BakeryReferenceScenario.default()
    service, registry = scenario._inventory_service(store)
    service.create_container(
        command_id="inventory-container:bakery",
        actor_ref=scenario.organization.organization_ref,
        spec=ContainerSpec("container:bakery:stock", 1000, 1000, 100),
        idempotency_key="inventory-container:bakery",
        causation_id="causation:inventory-container:bakery",
        correlation_id="correlation:bakery:inventory",
    )
    service.instantiate(
        command_id="inventory-input:seed",
        actor_ref=scenario.organization.organization_ref,
        item_id="item:flour:seed",
        definition_id="item:flour",
        quantity=1,
        container_id="container:bakery:stock",
        idempotency_key="inventory-input:seed",
        causation_id="causation:inventory-input:seed",
        correlation_id="correlation:bakery:inventory",
    )
    InventoryProjector(registry).rebuild(scenario.organization.organization_ref, store.read_events())


def _seed_low_balance(store: GameplayEventStore) -> None:
    service = EconomyAuthorityService(store=store)
    service.open_account(
        command_id="account-open:account:bakery",
        account_id="account:bakery",
        owner_ref="org:bakery",
        currency_ref="currency:coin",
        initial_balance=3,
        idempotency_key="account-open:account:bakery",
        causation_id="causation:account-open:account:bakery",
        correlation_id="correlation:bakery:accounts",
    )
    EconomyProjector().rebuild(store.read_events())
