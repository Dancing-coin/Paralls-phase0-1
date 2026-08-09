from __future__ import annotations

import pytest

from app.gameplay.bakery_mirror_source import BakeryMirrorSource, BakeryMirrorSourceError
from app.gameplay.bakery_reference_runtime import BakeryReferenceScenario
from app.gameplay.event_store import GameplayEventStore


def test_bakery_mirror_view_derives_facility_and_output_only_after_commit() -> None:
    scenario = BakeryReferenceScenario.default()
    store = GameplayEventStore()
    scenario.execute_period(1, store=store)

    view = BakeryMirrorSource(scenario=scenario, events=store.read_events()).godot_view()

    payload = view.groups["bakery.gameplay"].payload
    assert view.consumer == "godot"
    assert payload["facility_state"] == "acquired"
    assert payload["output_state"] == "sold"
    assert payload["output_count"] == 1


def test_bakery_mirror_rejects_uncommitted_or_incomplete_facts() -> None:
    with pytest.raises(BakeryMirrorSourceError, match="bakery_facility_commit_missing"):
        BakeryMirrorSource(scenario=BakeryReferenceScenario.default(), events=()).godot_view()
