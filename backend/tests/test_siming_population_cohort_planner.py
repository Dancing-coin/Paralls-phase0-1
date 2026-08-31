from app.population_continuity.batch import PopulationPlanner
from app.population_continuity.seed_planner import CharacterSeedPlanner
from app.population_continuity.siming_contracts import PopulationCadenceInput, PopulationProjection, PopulationReadSet


def cohort_read_set(window: str, budget: int) -> PopulationReadSet:
    cadence = PopulationCadenceInput(
        cadence_id=f"cadence:cohort:{window}", world_ref="world:bakery", world_mode_ref="mode:bakery",
        world_mode_revision="mode:v1", cadence_source_ref="world:bakery", cadence_source_revision=1,
        window_start=0, window_end=1, base_checkpoint_ref="checkpoint:1", base_checkpoint_digest="sha256:cp",
        base_revision_vector={"world:bakery": 1}, policy_revision="policy:v1", selector_revision="selector:v1",
        ruleset_revision="ruleset:v1", deterministic_seed="seed:1", catch_up_limit=3, budget=budget,
        report_scope="organization:summary",
    )
    rows = (
        PopulationProjection(ref=f"projection:char_a:{window.lower()}", scope="organization:summary", revision_vector={"world:bakery": 1}, payload={"actor_ref": "character:char_a", "candidate_kind": "char_a_supply"}),
        PopulationProjection(ref=f"projection:char_b:{window.lower()}", scope="public", revision_vector={"world:bakery": 1}, payload={"actor_ref": "character:char_b", "candidate_kind": "char_b_routine_work", "activation_hints": ["wave"]}),
        PopulationProjection(ref=f"projection:char_c:{window.lower()}", scope="organization:summary", revision_vector={"world:bakery": 1}, payload={"actor_ref": "character:char_c", "candidate_kind": "char_c_social_activation"}),
    )
    return PopulationReadSet.from_inputs(cadence, rows)


def test_three_actor_cohort_classifies_supply_routine_and_social_without_writes() -> None:
    report = PopulationPlanner().plan_three_actor_cohort(cohort_read_set("W0", 3))
    assert report.cohort_member_refs == ("character:char_a", "character:char_b", "character:char_c")
    assert len(report.owner_bound_intents) == 1
    assert report.owner_bound_intents[0].actor_ref == "character:char_a"
    assert report.presentation_seeds["character:char_b"]["behavior_kind"] == "routine_work"
    assert report.activation_candidates == ("projection:char_c:w0",)


def test_budget_two_reports_char_c_unprocessed_without_upgrading_char_b() -> None:
    report = PopulationPlanner().plan_three_actor_cohort(cohort_read_set("W0", 2))
    assert report.selected_cohort_refs == ("projection:char_a:w0", "projection:char_b:w0")
    assert report.unprocessed_cohort_refs == ("projection:char_c:w0",)
    assert report.owner_bound_intents[0].intent_kind == "supply"


def test_routine_work_seed_has_no_memory_candidate_or_objective_effect() -> None:
    base = cohort_read_set("W0", 3)
    read_set = base.model_copy(update={"projections": tuple(p.model_copy(update={"payload": {**p.payload, "candidate_kind": "routine_work"}}) if p.payload["actor_ref"] == "character:char_b" else p for p in base.projections)}, deep=True)
    routine = next(seed for seed in CharacterSeedPlanner().derive(read_set, ()) if seed.actor_ref == "character:char_b")
    assert routine.memory_candidates == ()
    assert routine.state_deltas == {}
    assert routine.owner_effect_status == "not_required"


def test_relationship_negotiation_stays_activation_only() -> None:
    read_set = cohort_read_set("W0", 3).model_copy(update={"projections": tuple(p.model_copy(update={"payload": {**p.payload, "candidate_kind": "relationship_negotiation"}}) if p.payload["actor_ref"] == "character:char_c" else p for p in cohort_read_set("W0", 3).projections)}, deep=True)
    social = next(seed for seed in CharacterSeedPlanner().derive(read_set, ()) if seed.actor_ref == "character:char_c")
    assert social.owner_effect_status == "not_required"
    assert social.memory_candidates == ()
