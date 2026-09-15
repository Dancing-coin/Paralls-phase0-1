from app.population_continuity.siming_contracts import PopulationCadenceInput, PopulationReadSet
from app.population_continuity.siming_contracts import PopulationProjection
from app.services.siming_population_capability import PopulationSimulationCapability


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
                    "state_deltas": {"fatigue": 0.1},
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
