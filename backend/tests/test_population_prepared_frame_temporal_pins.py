from __future__ import annotations

import json

import pytest

from app.population_continuity.prepared_frame import PreparedPopulationFrame
from app.population_continuity.siming_contracts import (
    PopulationCadenceInput,
    PopulationProjection,
    PopulationReadSet,
    dump_population_projections,
)


def _cadence() -> PopulationCadenceInput:
    return PopulationCadenceInput.model_validate(dict(
        cadence_id="cadence:pins", world_ref="world:pins", world_mode_ref="mode:pins",
        world_mode_revision="mode:v1", cadence_source_ref="source:pins", cadence_source_revision=0,
        base_checkpoint_ref="checkpoint:0", base_checkpoint_digest="sha256:0",
        window_start=0, window_end=60, policy_revision="policy:population:v1",
        selector_revision="selector:generic:population:v1", ruleset_revision="rules:population:v1",
        deterministic_seed="seed", catch_up_limit=1, budget=3, report_scope="public",
        base_revision_vector={"world:pins": 1},
    ))


def _projections() -> tuple[PopulationProjection, ...]:
    # Deliberately unsorted: both paths must sort by ref before digesting.
    return (
        PopulationProjection(ref="projection:b", scope="public",
            revision_vector={"world:pins": 1}, payload={"actor_ref": "character:b"}),
        PopulationProjection(ref="projection:a", scope="public",
            revision_vector={"world:pins": 1}, payload={"actor_ref": "character:a"}),
    )


def _frame(projections) -> PreparedPopulationFrame:
    ordered = tuple(sorted(projections, key=lambda item: item.ref))
    return PreparedPopulationFrame(
        projections_json=json.dumps(dump_population_projections(ordered), sort_keys=True,
            separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode(),
        projection_refs=tuple(item.ref for item in ordered),
    )


def _pins() -> dict[str, str | int]:
    return {
        "timeline_id": "timeline:main", "profile_revision": "profile:v1",
        "mapping_id": "mapping:main", "mapping_revision": "mapping:v1",
        "source_clock_ref": "clock:world", "source_revision": "clock:v1",
        "sampled_at": 60, "received_at": 60, "freshness": "fresh",
        "activation_revision": "activation:v1", "window_start": 0, "window_ticks": 60,
        "canonical_unit_ref": "unit:second", "step_duration": "1s",
    }


@pytest.mark.parametrize("pins", [None, {}, "full"], ids=["none", "empty", "full"])
def test_prepared_frame_digest_matches_validated_read_set(pins) -> None:
    pins = _pins() if pins == "full" else pins
    cadence, projections = _cadence(), _projections()

    slow = PopulationReadSet.from_inputs(cadence, projections, temporal_pins=pins)
    fast = _frame(projections).read_set(cadence, projections, temporal_pins=pins)

    # The fast path skips validation, so its digest must be byte-identical to the
    # validated path or a pinned window would look stale on the capability side.
    assert fast.read_set_digest == slow.read_set_digest
    assert dict(fast.temporal_pins) == dict(slow.temporal_pins)


def test_pins_change_the_digest() -> None:
    cadence, projections = _cadence(), _projections()
    frame = _frame(projections)

    unpinned = frame.read_set(cadence, projections)
    pinned = frame.read_set(cadence, projections, temporal_pins=_pins())

    # Dropping pins on the fast path would silently merge two distinct read sets.
    assert unpinned.read_set_digest != pinned.read_set_digest


def test_fast_path_result_still_passes_full_validation() -> None:
    cadence, projections = _cadence(), _projections()

    fast = _frame(projections).read_set(cadence, projections, temporal_pins=_pins())

    PopulationReadSet.model_validate(fast.model_dump())


def test_mismatched_projection_refs_fall_back_to_validated_path_with_pins() -> None:
    cadence, projections = _cadence(), _projections()
    frame = _frame(projections[:1])

    result = frame.read_set(cadence, projections, temporal_pins=_pins())

    expected = PopulationReadSet.from_inputs(cadence, projections, temporal_pins=_pins())
    assert result.read_set_digest == expected.read_set_digest
    assert dict(result.temporal_pins) == _pins()
