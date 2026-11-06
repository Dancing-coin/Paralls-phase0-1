from __future__ import annotations

import pytest

from app.population_continuity.seed_planner import CharacterSeedPlanner
from app.population_continuity.siming_contracts import (
    PopulationCadenceInput,
    PopulationProjection,
    PopulationReadSet,
)


def _cadence(**updates: object) -> PopulationCadenceInput:
    values: dict[str, object] = {
        "cadence_id": "cadence:test:W1",
        "world_ref": "world:bakery",
        "world_mode_ref": "mode:bakery",
        "world_mode_revision": "1",
        "cadence_source_ref": "world:bakery",
        "cadence_source_revision": 1,
        "window_start": 100,
        "window_end": 102,
        "base_checkpoint_ref": "checkpoint:bakery:1",
        "base_checkpoint_digest": "sha256:checkpoint",
        "policy_revision": "policy:v1",
        "selector_revision": "selector:v1",
        "ruleset_revision": "ruleset:v1",
        "deterministic_seed": "sha256:seed",
        "catch_up_limit": 2,
        "budget": 3,
        "report_scope": "public",
        "base_revision_vector": {"world:bakery": 1},
    }
    values.update(updates)
    return PopulationCadenceInput(**values)


def _read_set(payload: dict[str, object], **cadence_updates: object) -> PopulationReadSet:
    cadence = _cadence(**cadence_updates)
    projection = PopulationProjection(
        ref="projection:char_a:W1",
        scope="public",
        revision_vector={"world:bakery": 1},
        payload={"actor_ref": "character:char_a", "candidate_kind": "schedule_gated_supply", **payload},
    )
    return PopulationReadSet(
        cadence=cadence, projections=(projection,), read_set_digest="sha256:readset"
    )


def _seed_memory(read_set: PopulationReadSet):
    seeds = CharacterSeedPlanner().derive(read_set, ())
    assert len(seeds) == 1
    assert len(seeds[0].memory_candidates) == 1
    return seeds[0].memory_candidates[0]


def test_default_known_time_matches_window_end_for_compatibility() -> None:
    candidate = _seed_memory(_read_set({"exposure_basis": "affected_directly"}))

    assert candidate.event_valid_at == 102
    assert candidate.knowledge_available_at == 102


def test_knowledge_available_at_can_lag_event_valid_at() -> None:
    candidate = _seed_memory(
        _read_set(
            {
                "exposure_basis": "affected_directly",
                "event_valid_at": 101,
                "knowledge_available_at": 105,
            }
        )
    )

    # "happened" and "learned" are separate facts; the actor may learn later.
    assert candidate.event_valid_at == 101
    assert candidate.knowledge_available_at == 105
    assert candidate.event_valid_at < candidate.knowledge_available_at


def test_knowledge_before_event_is_rejected() -> None:
    with pytest.raises(ValueError, match="seed_memory_time_order_invalid"):
        _seed_memory(
            _read_set(
                {
                    "exposure_basis": "affected_directly",
                    "event_valid_at": 105,
                    "knowledge_available_at": 101,
                }
            )
        )


@pytest.mark.parametrize("forged", [True, False, -1, "101", 101.5])
def test_forged_tick_values_are_rejected(forged: object) -> None:
    with pytest.raises(ValueError, match="seed_memory_tick_invalid"):
        _seed_memory(
            _read_set({"exposure_basis": "affected_directly", "knowledge_available_at": forged})
        )


def test_event_recorded_at_is_independent() -> None:
    candidate = _seed_memory(
        _read_set(
            {
                "exposure_basis": "affected_directly",
                "event_valid_at": 100,
                "event_recorded_at": 101,
                "knowledge_available_at": 103,
            }
        )
    )

    assert (candidate.event_valid_at, candidate.event_recorded_at, candidate.knowledge_available_at) == (
        100,
        101,
        103,
    )
