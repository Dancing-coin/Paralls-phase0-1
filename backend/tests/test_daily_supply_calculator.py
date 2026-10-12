"""合成八维输入只证明数值语义，不证明真实 Owner 来源已齐备。"""
import pytest

from app.population_continuity.daily_supply import calculate_daily_supply, daily_supply_template
from test_social_model_execution_contract import standard_inputs


def test_standard_bounds_are_deterministic_and_read_only():
    inputs = standard_inputs()
    before = inputs.model_dump_json()
    result = calculate_daily_supply(inputs, budget_units=100)
    assert result == calculate_daily_supply(inputs, budget_units=100)
    assert result.status == "ok" and result.work_units == 8
    assert result.report.demand_units == (120, 140)
    assert result.report.confirmed_supply_units == 100
    assert result.report.reachable_supply_units == (48, 62)
    assert result.report.coverage_bps == (3428, 5167)
    assert result.report.upgrade_categories == ("care_households",)
    assert inputs.model_dump_json() == before
    assert "actor_allocations" not in result.report.model_dump()
    assert daily_supply_template().dimensions == (
        "qualification", "custody", "reachability", "process", "commitment", "constraint", "risk", "summary")


@pytest.mark.parametrize("budget", range(8))
def test_budget_exhaustion_never_returns_partial_report(budget):
    result = calculate_daily_supply(standard_inputs(), budget_units=budget)
    assert result.status == "budget_exhausted" and result.report is None
    assert result.work_units == budget


@pytest.mark.parametrize("field", ["qualification_confirmed", "route_open", "process_open",
    "arrival_delay_ticks", "deadline_tick"])
def test_unknown_required_context_is_not_zero_supply(field):
    result = calculate_daily_supply(standard_inputs(**{field: None}), budget_units=100)
    assert result.status == "context_insufficient" and result.report is None


@pytest.mark.parametrize("updates,reason", [
    ({"qualification_confirmed": False}, "qualification_denied"),
    ({"route_open": False}, "route_closed"),
    ({"process_open": False}, "process_closed"),
    ({"arrival_delay_ticks": 21}, "deadline_missed"),
])
def test_confirmed_blocks_return_zero_reachability_with_reason(updates, reason):
    result = calculate_daily_supply(standard_inputs(**updates), budget_units=100)
    assert result.status == "ok"
    assert result.report.reachable_supply_units == (0, 0)
    assert result.report.coverage_bps == (0, 0)
    assert reason in result.report.blocking_reasons


def test_capacity_factor_is_applied_once_before_delivery_ratio():
    result = calculate_daily_supply(standard_inputs(window_capacity_units=80,
        capacity_factor_bps=5000, delivery_ratio_bps=(10000, 10000)), budget_units=100)
    assert result.report.reachable_supply_units == (40, 40)
    assert result.report.coverage_bps == (2857, 3334)


@pytest.mark.parametrize("demand,reachable,coverage", [
    ((0, 0), (48, 62), None), ((0, 140), (48, 62), (3428, 10000)),
    ((1, 1), (48, 62), (10000, 10000)), ((0, 140), (0, 0), (0, 0)),
])
def test_zero_and_saturated_demand_bounds(demand, reachable, coverage):
    supply = 0 if reachable == (0, 0) else 100
    report = calculate_daily_supply(standard_inputs(demand_units=demand,
        confirmed_supply_units=supply), budget_units=100).report
    assert report.coverage_bps == coverage
    assert ("not_required" in report.blocking_reasons) == (demand == (0, 0))


def test_integer_rounding_does_not_overstate_lower_bound():
    report = calculate_daily_supply(standard_inputs(confirmed_supply_units=1,
        delivery_ratio_bps=(4800, 6200)), budget_units=100).report
    assert report.reachable_supply_units == (0, 1)
    assert report.coverage_bps == (0, 84)


def test_model_copy_tampering_is_rejected_before_calculation():
    original = standard_inputs()
    corrupted = original.model_copy(update={"data": original.data.model_copy(update={"confirmed_supply_units": 101})})
    with pytest.raises(ValueError, match="model_input_digest_mismatch"):
        calculate_daily_supply(corrupted, budget_units=100)


@pytest.mark.parametrize("budget", [-1, 101, True, 8.0])
def test_invalid_budget_is_rejected(budget):
    with pytest.raises(ValueError, match="model_budget_invalid"):
        calculate_daily_supply(standard_inputs(), budget_units=budget)
