import hashlib
import json
from datetime import date
from decimal import Decimal
from enum import IntEnum

from app.population_continuity.siming_contracts import (
    PopulationCadenceInput,
    PopulationReadSet,
    dump_population_projections,
)
from app.population_continuity.siming_contracts import PopulationProjection
from app.services.siming_population_capability import PopulationSimulationCapability
import pytest


def _cadence() -> PopulationCadenceInput:
    return PopulationCadenceInput(
        cadence_id="cadence:b0:1",
        world_ref="world:b0",
        world_mode_ref="world-mode:b0",
        world_mode_revision="mode:1",
        cadence_source_ref="world:world:b0",
        cadence_source_revision=1,
        window_start=0,
        window_end=10,
        base_checkpoint_ref="checkpoint:b0:1",
        base_checkpoint_digest="sha256:b0",
        base_revision_vector={"world:world:b0": 1},
        policy_revision="policy:population:v1",
        selector_revision="selector:population:v1",
        ruleset_revision="rules:population:v1",
        deterministic_seed="seed:b0:1",
        catch_up_limit=2,
        budget=1,
        report_scope="public",
    )


def test_bulk_projection_dump_preserves_individual_json_and_read_set_digest() -> None:
    cadence = _cadence()
    projections = (
        PopulationProjection(
            ref=f"projection:actor_{index}",
            scope="public",
            revision_vector={"world:world:b0": 1},
            payload={"actor_ref": f"character:actor_{index}", "fidelity_tier": "B0"},
        )
        for index in range(2)
    )
    projections = tuple(projections)
    expected_rows = [item.model_dump(mode="json") for item in projections]
    expected_payload = {
        "cadence": cadence.model_dump(mode="json"),
        "projections": expected_rows,
    }
    expected_digest = "sha256:" + hashlib.sha256(
        json.dumps(
            expected_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
    ).hexdigest()

    assert dump_population_projections(projections) == expected_rows
    assert PopulationReadSet.from_inputs(cadence, projections).read_set_digest == expected_digest


class _ProjectionPriority(IntEnum):
    LOW = 1


@pytest.mark.parametrize(
    "payload",
    [
        {"refs": ("a", "b")},
        {"amount": Decimal("1.25"), "due_on": date(2026, 9, 16)},
        {"priority": _ProjectionPriority.LOW},
        {"labels": {1: "one", "2": "two"}},
        {"labels": {2: "two", 10: "ten"}},
        {"label": "居民甲"},
        {"score": float("nan")},
    ],
)
def test_read_set_digest_matches_model_dump_json(payload) -> None:
    cadence = _cadence()
    projection = PopulationProjection(
        ref="projection:actor_a",
        scope="public",
        revision_vector={"world:world:b0": 1},
        payload=payload,
    )
    expected_payload = {
        "cadence": cadence.model_dump(mode="json"),
        "projections": [projection.model_dump(mode="json")],
    }
    expected = "sha256:" + hashlib.sha256(
        json.dumps(
            expected_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
    ).hexdigest()

    assert PopulationReadSet.from_inputs(
        cadence, (projection,)
    ).read_set_digest == expected


def test_b0_path_only_emits_bounded_state_deltas() -> None:
    cadence = _cadence()
    read_set = PopulationReadSet.from_inputs(
        cadence,
        [
            PopulationProjection(
                ref="projection:actor_a",
                scope="public",
                revision_vector={"world:world:b0": 1},
                payload={
                    "actor_ref": "character:actor_a",
                    "fidelity_tier": "B0",
                    "from_tick": 0,
                    "to_tick": 10,
                    "simulation_tick_cursor": 10,
                    "actor_revision": 1,
                    "state_deltas": {"fatigue": 0.1},
                    "scope": "public",
                    "source_revision_vector": {"world:world:b0": 1},
                    "idempotency_key": "b0:cadence:b0:1:character:actor_a",
                },
            ),
            PopulationProjection(
                ref="projection:actor_b",
                scope="public",
                payload={"actor_ref": "character:actor_b", "fidelity_tier": "B1"},
            ),
        ],
    )

    deltas = PopulationSimulationCapability().build_b0_continuous_deltas(cadence, read_set)

    assert len(deltas) == 1
    assert deltas[0]["actor_ref"] == "character:actor_a"
    assert "memory_candidates" not in deltas[0]


@pytest.mark.parametrize(
    ("projection_update", "reason"),
    [
        ({"scope": "actor:actor_a"}, "b0_scope_invalid"),
        ({"revision_vector": {"world:world:b0": 2}}, "b0_source_revision_mismatch"),
        ({"payload": {"source_revision_vector": {"world:world:b0": 2}}}, "b0_source_revision_mismatch"),
        ({"payload": {"from_tick": 1}}, "b0_window_invalid"),
        ({"payload": {"to_tick": 9}}, "b0_window_invalid"),
        ({"payload": {"simulation_tick_cursor": 9}}, "b0_window_invalid"),
        ({"payload": {"state_deltas": {"dynamic_state": {"stress_load": 0.1}}}}, "b0_state_field_not_allowed"),
        ({"payload": {"state_deltas": {"fatigue": 1.1}}}, "b0_state_value_invalid"),
        ({"payload": {"state_deltas": {"next_due_tick": True}}}, "b0_state_value_invalid"),
        ({"payload": {"due_obligation_refs": [5]}}, "b0_due_obligation_invalid"),
        (
            {"payload": {"presentation_seed": [["unexpected", 1]]}},
            "b0_presentation_seed_invalid",
        ),
    ],
)
def test_b0_rejects_non_objective_or_cross_context_state(
    projection_update: dict[str, object], reason: str
) -> None:
    cadence = _cadence()
    payload = {
        "actor_ref": "character:actor_a",
        "fidelity_tier": "B0",
        "from_tick": 0,
        "to_tick": 10,
        "simulation_tick_cursor": 10,
        "actor_revision": 1,
        "state_deltas": {"fatigue": 0.1},
        "scope": "public",
        "source_revision_vector": {"world:world:b0": 1},
        "idempotency_key": "b0:cadence:b0:1:character:actor_a",
    }
    update = dict(projection_update)
    if "payload" in update:
        update["payload"] = {**payload, **dict(update["payload"])}
    projection = PopulationProjection(
        ref="projection:actor_a",
        scope="public",
        revision_vector={"world:world:b0": 1},
        payload=payload,
    ).model_copy(update=update, deep=True)
    read_set = PopulationReadSet.from_inputs(cadence, (projection,))

    result = PopulationSimulationCapability().run_default_decision_cycle(cadence, read_set)

    assert result.status == "requeue"
    assert result.reason == reason
    assert result.production_append_count == 0


def test_b0_rejects_duplicate_actor_projection() -> None:
    cadence = _cadence()
    projections = tuple(
        PopulationProjection(
            ref=f"projection:actor_a:{index}",
            scope="public",
            revision_vector={"world:world:b0": 1},
            payload={
                "actor_ref": "character:actor_a",
                "fidelity_tier": "B0",
                "from_tick": 0,
                "to_tick": 10,
                "simulation_tick_cursor": 10,
                "actor_revision": 1,
                    "state_deltas": {"fatigue": 0.1},
                    "scope": "public",
                    "source_revision_vector": {"world:world:b0": 1},
                    "idempotency_key": "b0:cadence:b0:1:character:actor_a",
            },
        )
        for index in range(2)
    )

    result = PopulationSimulationCapability().run_default_decision_cycle(
        cadence, PopulationReadSet.from_inputs(cadence, projections)
    )

    assert result.status == "requeue"
    assert result.reason == "b0_actor_duplicate"
