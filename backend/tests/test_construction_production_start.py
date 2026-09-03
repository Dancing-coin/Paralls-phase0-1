from __future__ import annotations

import pytest

from app.gameplay.construction_production_runtime import ConstructionProductionAuthority, Facility, Plot, Recipe
from app.gameplay.event_store import GameplayEventStore


def test_start_requires_available_facility_and_retains_only_reservation_refs() -> None:
    facility = Facility(facility_ref="facility:1", plot_ref="plot:1", facility_kind="bakery", condition=1)
    recipe = Recipe(recipe_ref="recipe:bread", inputs={"flour": 2}, output_item="bread", duration_ticks=2)
    run = ConstructionProductionAuthority.start_run(facility=facility, recipe=recipe, run_ref="run:1", tick=3, reservation_refs=("reservation:flour",))
    assert run.finish_tick == 5
    assert run.reservation_refs == ("reservation:flour",)


def test_settle_start_run_rejects_decommissioned_facility_before_append() -> None:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(
        facility_ref="facility:decommissioned",
        plot_ref="plot:decommissioned",
        facility_kind="mill_reinforced",
        condition=1.0,
        revision=2,
        lifecycle_status="decommissioned",
    )
    recipe = Recipe(
        recipe_ref="recipe:decommissioned@1",
        inputs={},
        output_item="item:flour@1",
        duration_ticks=1,
        failure_policy_mode="terminal",
        failure_policy_revision="policy:failure:terminal@1",
    )
    result = authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:decommissioned:1",
        tick=0,
        command_id="command:decommissioned:1",
        idempotency_key="idempotency:decommissioned:1",
        causation_id="cause:decommissioned:1",
        correlation_id="corr:decommissioned:1",
    )
    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "facility_lifecycle_decommissioned"
    assert store.read_events() == []


def test_start_run_rejects_decommissioned_facility_without_constructing_a_run() -> None:
    facility = Facility(
        facility_ref="facility:decommissioned-pure",
        plot_ref="plot:decommissioned-pure",
        facility_kind="mill_reinforced",
        condition=1.0,
        revision=2,
        lifecycle_status="decommissioned",
    )
    recipe = Recipe(
        recipe_ref="recipe:decommissioned-pure@1",
        inputs={},
        output_item="item:flour@1",
        duration_ticks=1,
        failure_policy_mode="terminal",
        failure_policy_revision="policy:failure:terminal@1",
    )
    with pytest.raises(ValueError, match="facility_lifecycle_decommissioned"):
        ConstructionProductionAuthority.start_run(
            facility=facility,
            recipe=recipe,
            run_ref="run:decommissioned-pure:1",
            tick=0,
        )


def test_facility_acquisition_rejects_predecommissioned_state_before_append() -> None:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    plot = Plot(plot_ref="plot:predecommissioned", jurisdiction_ref="jurisdiction:local", owner_ref="organization:builder")
    facility = Facility(
        facility_ref="facility:predecommissioned",
        plot_ref=plot.plot_ref,
        facility_kind="mill",
        condition=1.0,
        revision=1,
        lifecycle_status="decommissioned",
    )
    with pytest.raises(ValueError, match="facility_acquisition_lifecycle_invalid"):
        authority.settle_facility_acquisition(
            plot=plot,
            facility=facility,
            command_id="command:predecommissioned",
            idempotency_key="idempotency:predecommissioned",
            causation_id="cause:predecommissioned",
            correlation_id="corr:predecommissioned",
        )
    assert store.read_events() == []


def test_settle_start_run_rejects_stale_facility_projection_revision_before_append() -> None:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    plot = Plot(plot_ref="plot:stale-facility", jurisdiction_ref="jurisdiction:local", owner_ref="organization:builder", revision=1)
    committed = Facility(
        facility_ref="facility:stale-facility",
        plot_ref=plot.plot_ref,
        facility_kind="mill",
        condition=1.0,
        revision=4,
    )
    assert authority.settle_facility_acquisition(
        plot=plot,
        facility=committed,
        command_id="command:stale-facility:acquire",
        idempotency_key="idempotency:stale-facility:acquire",
        causation_id="cause:stale-facility:acquire",
        correlation_id="corr:stale-facility:acquire",
    ).committed
    stale = committed.model_copy(update={"revision": 3})
    recipe = Recipe(
        recipe_ref="recipe:stale-facility@1",
        inputs={},
        output_item="item:flour@1",
        duration_ticks=1,
        failure_policy_mode="terminal",
        failure_policy_revision="policy:failure:terminal@1",
    )
    result = authority.settle_start_run(
        facility=stale,
        recipe=recipe,
        run_ref="run:stale-facility:1",
        tick=0,
        command_id="command:stale-facility:start",
        idempotency_key="idempotency:stale-facility:start",
        causation_id="cause:stale-facility:start",
        correlation_id="corr:stale-facility:start",
    )
    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "construction_run_facility_revision_conflict"
    assert len(store.read_events()) == 1


def test_settle_start_run_appends_canonical_event_and_rejects_without_write() -> None:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(facility_ref="facility:1", plot_ref="plot:1", facility_kind="bakery", condition=1)
    recipe = Recipe(recipe_ref="recipe:bread", inputs={"flour": 2}, output_item="bread", duration_ticks=2)
    result = authority.settle_start_run(
        facility=facility, recipe=recipe, run_ref="run:1", tick=3,
        reservation_refs=("reservation:flour",), command_id="command:production:start:1",
        idempotency_key="idem:production:start:1", causation_id="cause:production:start:1",
        correlation_id="corr:production:1",
    )
    assert result.committed is True
    assert [event.event_type for event in store.read_events()] == ["gameplay.construction_production.run_started"]
    before = len(store.read_events())
    with pytest.raises(ValueError, match="facility_unavailable"):
        authority.settle_start_run(
            facility=facility.model_copy(update={"condition": 0}), recipe=recipe, run_ref="run:2", tick=3,
            command_id="command:production:start:2", idempotency_key="idem:production:start:2",
            causation_id="cause:production:start:2", correlation_id="corr:production:2",
        )
    assert len(store.read_events()) == before
