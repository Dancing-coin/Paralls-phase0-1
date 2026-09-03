from __future__ import annotations

import pytest

from app.gameplay.bakery_mirror_source import BakeryMirrorSource, BakeryMirrorSourceError
from app.gameplay.bakery_reference_runtime import BakeryReferenceScenario
from app.gameplay.event_store import GameplayEventStore


def test_committed_three_period_mirror_exposes_cross_owner_summary() -> None:
    scenario = BakeryReferenceScenario.default()
    store = GameplayEventStore()
    scenario.run_three_periods(store=store)

    view = BakeryMirrorSource(scenario=scenario, events=store.read_events()).godot_view()
    payload = view.groups["bakery.gameplay"].payload
    assert payload["period_count"] == 3
    assert payload["sale_count"] == 3
    assert payload["permit_count"] == 3
    assert payload["failure_count"] == 0
    assert payload["recovery_count"] == 0


def test_failed_period_mirror_is_rejected_until_recovery_and_next_commit() -> None:
    scenario = BakeryReferenceScenario.default()
    store = GameplayEventStore()
    scenario.execute_period(1, store=store, inject_production_failure=True)
    with pytest.raises(BakeryMirrorSourceError, match="bakery_output_commit_missing"):
        BakeryMirrorSource(scenario=scenario, events=store.read_events()).godot_view()

    scenario.recover_failed_production(run_ref="run:bakery:1", store=store)
    scenario.execute_period(2, store=store)
    view = BakeryMirrorSource(scenario=scenario, events=store.read_events()).godot_view()
    assert view.groups["bakery.gameplay"].payload["recovery_count"] == 1


def test_mirror_does_not_mutate_store_on_rejection() -> None:
    scenario = BakeryReferenceScenario.default()
    store = GameplayEventStore()
    before = len(store.read_events())
    with pytest.raises(BakeryMirrorSourceError):
        BakeryMirrorSource(scenario=scenario, events=store.read_events()).godot_view()
    assert len(store.read_events()) == before
