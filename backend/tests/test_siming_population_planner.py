from __future__ import annotations

from pathlib import Path

from app.character_agent.models.simulation_seed import CharacterSimulationSeedCandidate
from app.population_continuity.batch import PopulationPlanner
from app.population_continuity.seed_planner import CharacterSeedPlanner
from app.population_continuity.siming_contracts import (
    PopulationCadenceInput,
    PopulationProjection,
    PopulationReadSet,
)


def cadence(**updates: object) -> PopulationCadenceInput:
    values: dict[str, object] = {
        "cadence_id": "cadence:bakery:1",
        "world_ref": "world:bakery",
        "world_mode_ref": "mode:bakery",
        "world_mode_revision": "mode:v1",
        "cadence_source_ref": "world:bakery",
        "cadence_source_revision": 1,
        "window_start": 100,
        "window_end": 101,
        "base_checkpoint_ref": "checkpoint:bakery:1",
        "base_checkpoint_digest": "sha256:checkpoint",
        "base_revision_vector": {"world:bakery": 1},
        "policy_revision": "policy:v1",
        "selector_revision": "selector:v1",
        "ruleset_revision": "ruleset:v1",
        "deterministic_seed": "seed:bakery:1",
        "catch_up_limit": 2,
        "budget": 2,
        "report_scope": "organization:summary",
    }
    values.update(updates)
    return PopulationCadenceInput(**values)


def projection(ref: str, **payload: object) -> PopulationProjection:
    return PopulationProjection(
        ref=ref,
        scope="organization:summary",
        revision_vector={"world:bakery": 1},
        payload=payload,
    )


def read_set_with_projection_order(*refs: str) -> PopulationReadSet:
    return PopulationReadSet.from_inputs(cadence(), tuple(projection(ref, actor_ref=f"character:{ref}", candidate_kind="routine_work") for ref in refs))


def read_set_with_supply_candidate() -> PopulationReadSet:
    return PopulationReadSet.from_inputs(
        cadence(),
        (projection("supply", actor_ref="character:char_a", candidate_kind="schedule_gated_supply", state_deltas={"task": "restock"}),),
    )


def read_set_with_public_frost() -> PopulationReadSet:
    return PopulationReadSet.from_inputs(
        cadence(),
        (projection("frost", actor_ref="character:char_a", candidate_kind="routine_work", event_ref="event:frost:101", exposure_basis="public_propagation", summary="A public frost damaged the bakery crops."),),
    )


def read_set_with_candidate_kind(kind: str) -> PopulationReadSet:
    return PopulationReadSet.from_inputs(cadence(), (projection("candidate", actor_ref="character:char_a", candidate_kind=kind),))


def test_population_cycle_is_deterministic_when_projection_order_changes() -> None:
    planner = PopulationPlanner()
    first = planner.plan_population_cycle(read_set_with_projection_order("a", "b"))
    second = planner.plan_population_cycle(read_set_with_projection_order("b", "a"))
    assert first.model_dump() == second.model_dump()


def test_seed_derivation_requires_owner_receipt_for_objective_change() -> None:
    seeds = CharacterSeedPlanner().derive(read_set_with_supply_candidate(), ())
    assert seeds[0].state_deltas
    assert seeds[0].owner_effect_status == "owner_settlement_required"
    assert seeds[0].materialization_status == "pending"


def test_seed_derivation_records_exposure_without_granting_global_knowledge() -> None:
    seeds = CharacterSeedPlanner().derive(read_set_with_public_frost(), ("receipt:frost:101",))
    candidate = seeds[0].memory_candidates[0]
    assert candidate.visibility_scope == "actor:self"
    assert candidate.exposure_basis in {"affected_directly", "public_propagation"}
    assert candidate.actor_ref == "character:char_a"


def test_unknown_behavior_is_report_only_and_not_owner_bound() -> None:
    report = PopulationPlanner().plan_population_cycle(read_set_with_candidate_kind("new_story_action"))
    assert report.rejected_candidates[0].reason == "capability_not_admitted"
    assert report.owner_bound_intents == ()


def test_routine_b0_behavior_never_requests_an_llm_activation() -> None:
    report = PopulationPlanner().plan_population_cycle(read_set_with_candidate_kind("routine_work"))
    assert report.activation_candidates == ()
    assert report.presentation_seeds


def test_high_value_b2_behavior_is_an_activation_candidate_with_budget_reason() -> None:
    report = PopulationPlanner().plan_population_cycle(read_set_with_candidate_kind("relationship_negotiation"))
    assert report.activation_candidates
    assert report.activation_candidates == ("candidate",)


def test_unregistered_behavior_is_rejected_instead_of_becoming_presentation_seed() -> None:
    report = PopulationPlanner().plan_population_cycle(
        read_set_with_candidate_kind("invented_behavior")
    )
    assert report.presentation_seeds == {}
    assert report.rejected_candidates[0].reason == "capability_not_admitted"


def test_unknown_projection_is_not_turned_into_a_character_seed() -> None:
    assert CharacterSeedPlanner().derive(
        read_set_with_candidate_kind("invented_behavior"), ()
    ) == ()


def test_objective_seed_does_not_accept_an_unrelated_owner_receipt() -> None:
    seed = CharacterSeedPlanner().derive(
        read_set_with_supply_candidate().model_copy(
            update={"projections": (projection("supply", actor_ref="character:char_a", candidate_kind="schedule_gated_supply", owner_receipt_ref="receipt:expected"),)},
            deep=True,
        ),
        ("receipt:unrelated",),
    )[0]
    assert seed.owner_effect_status == "owner_settlement_required"
    assert seed.source_owner_receipt_refs == ()


def test_seed_visibility_is_actor_private_even_when_projection_scope_is_public() -> None:
    read_set = read_set_with_public_frost().model_copy(
        update={"projections": (PopulationProjection(ref="frost", scope="public", revision_vector={"world:bakery": 1}, payload={"actor_ref": "character:char_a", "candidate_kind": "routine_work", "exposure_basis": "public_propagation"}),)},
        deep=True,
    )
    seed = CharacterSeedPlanner().derive(read_set, ())[0]
    assert seed.visibility_scope == "actor:self"
    assert seed.presentation_seed["actor_scope"] == "actor:self"


def test_activation_fallback_and_budget_cost_are_closed() -> None:
    invalid_read_set = PopulationReadSet.from_inputs(
        cadence(),
        (projection("candidate", actor_ref="character:char_a", candidate_kind="relationship_negotiation", fallback="discard", budget_cost=0),),
    )
    invalid = PopulationPlanner().plan_population_cycle(
        invalid_read_set
    )
    assert invalid.activation_candidates == ()
    assert invalid.rejected_candidates[0].reason == "fallback_invalid"


def test_seed_planner_returns_typed_candidates() -> None:
    seeds = CharacterSeedPlanner().derive(read_set_with_supply_candidate(), ("receipt:supply",))
    assert isinstance(seeds[0], CharacterSimulationSeedCandidate)


def test_seed_planner_has_no_direct_write_authority() -> None:
    source = Path(__file__).parents[1].joinpath("app", "population_continuity", "seed_planner.py").read_text()
    assert "append_batch" not in source
    assert "ProfileActivationAuthority" not in source
