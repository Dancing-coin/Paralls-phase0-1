from __future__ import annotations

import pytest

from app.gameplay.bakery_reference_runtime import BakeryReferenceScenario
from app.gameplay.construction_production_runtime import ConstructionProductionAuthority
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import InventoryDefinitionRegistry, InventoryProjector, ItemDefinition
from app.gameplay.recipe_production_family import RecipeProductionFailureIntent


def test_injected_production_failure_is_source_pinned_and_recovery_allows_next_period() -> None:
    scenario = BakeryReferenceScenario.default()
    store = GameplayEventStore()

    failed_period = scenario.execute_period(1, store=store, inject_production_failure=True)
    assert failed_period.period_ref.endswith(":failed")
    failure_events = [e for e in store.read_events() if e.event_type == "gameplay.construction_production.run_failed@1"]
    assert len(failure_events) == 1
    failure = failure_events[0]
    assert failure.stream_id == "gameplay:construction_production:facility:bakery"
    assert failure.visibility_policy == "project"
    assert failure.payload["reservation_refs"] == ("reservation:flour:1",)
    assert failure.payload["source_revision_vector"]["stream_head"] == failure.stream_revision - 1
    assert failure.payload["failure_mode"] == "release"

    recovery = scenario.recover_failed_production(run_ref="run:bakery:1", store=store)
    assert recovery.committed

    next_period = scenario.execute_period(2, store=store)
    assert next_period.period_ref == "period:bakery:2"


def test_failure_duplicate_and_changed_duplicate_are_zero_write() -> None:
    scenario = BakeryReferenceScenario.default()
    store = GameplayEventStore()
    scenario.execute_period(1, store=store, inject_production_failure=True)
    authority = ConstructionProductionAuthority(store=store)
    projection = authority.projector()
    stream_id = "gameplay:construction_production:facility:bakery"
    run = projection.runs["run:bakery:1"]
    facility = projection.facilities[run.facility_ref]
    intent = RecipeProductionFailureIntent(
        facility_ref=run.facility_ref,
        run_ref=run.run_ref,
        tick=2,
        expected_stream_revision=store.get_stream_head(stream_id) - 1,
        expected_facility_revision=facility.revision,
        failure_reason="injected_production_failure",
        command_id="duplicate-failure",
        causation_id="duplicate-causation",
        correlation_id="duplicate-correlation",
    )
    before = len(store.read_events())
    duplicate = authority.settle_recipe_production_failure(intent=intent)
    assert duplicate.committed
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == before

    changed = authority.settle_recipe_production_failure(
        intent=intent.model_copy(update={"failure_reason": "different-reason", "command_id": "changed-failure"})
    )
    assert not changed.committed
    assert changed.failure is not None
    assert changed.failure.error_code == "recipe_production_failure_idempotency_reused"
    assert len(store.read_events()) == before

    stale = authority.settle_recipe_production_failure(
        intent=intent.model_copy(
            update={
                "run_ref": "run:bakery:missing",
                "command_id": "stale-failure",
                "expected_stream_revision": 0,
            }
        )
    )
    assert not stale.committed
    assert stale.failure is not None
    assert stale.failure.error_code == "recipe_production_failure_source_missing"
    assert len(store.read_events()) == before


def test_recovery_unknown_reservation_is_zero_write() -> None:
    scenario = BakeryReferenceScenario.default()
    store = GameplayEventStore()
    with pytest.raises(ValueError, match="bakery_failed_run_required"):
        scenario.recover_failed_production(run_ref="run:missing", store=store)
