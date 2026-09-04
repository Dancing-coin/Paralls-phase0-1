from __future__ import annotations

from app.population_continuity.decision_surface import (
    PopulationCapabilityDescriptor,
    PopulationCapabilityCatalog,
    PopulationDecisionCandidate,
    PopulationDecisionPlanner,
    PopulationDecisionPolicy,
)
from app.population_continuity.siming_contracts import PopulationCadenceInput, PopulationProjection, PopulationReadSet


def read_set() -> PopulationReadSet:
    cadence = PopulationCadenceInput(
        cadence_id="cadence:test:W0", world_ref="world:test", world_mode_ref="mode:test",
        world_mode_revision="policy:test:v1", cadence_source_ref="world:test", cadence_source_revision=1,
        window_start=0, window_end=1, base_checkpoint_ref="checkpoint:test:1", base_checkpoint_digest="sha256:checkpoint",
        base_revision_vector={"world:test": 1}, policy_revision="policy:test:v1", selector_revision="selector:test:v1",
        ruleset_revision="rules:test:v1", deterministic_seed="seed:test:W0", catch_up_limit=3, budget=3,
        report_scope="organization:summary",
    )
    rows = tuple(
        PopulationProjection(
            ref=f"projection:{actor}:W0", scope=scope, revision_vector={"world:test": 1},
            payload={"actor_ref": f"character:{actor}", "candidate_kind": behavior, "source_domain": domain},
        )
        for actor, scope, behavior, domain in (
            ("char_a", "organization:summary", "schedule_gated_supply", "organization"),
            ("char_b", "public", "routine_work", "organization"),
            ("char_c", "public", "relationship_negotiation", "social"),
        )
    )
    return PopulationReadSet.from_inputs(cadence, rows)


def candidate(ref: str, *, actor: str, behavior: str, proximity: float = 0.0, consequence: float = 0.0) -> PopulationDecisionCandidate:
    return PopulationDecisionCandidate(
        candidate_ref=ref,
        actor_ref=actor,
        cohort_ref="cohort:test:W0",
        behavior_kind=behavior,
        fidelity_tier="B2",
        source_projection_refs=(f"projection:{actor.removeprefix('character:')}:W0",),
        source_revision_vector={"world:test": 1},
        evidence_refs=(f"evidence:{ref}",),
        estimated_cost=1,
        objective_risk="low" if behavior == "schedule_gated_supply" else "none",
        player_proximity=proximity,
        narrative_obligation_pressure=0.0,
        unresolved_owner_consequence=consequence,
        propagation_pressure=0.0,
        starvation_credit=0.0,
        allowed_outputs=("owner_bound_intent", "character_core_command") if behavior == "schedule_gated_supply" else ("presentation_seed", "activation_candidate"),
        policy_revision="policy:test:v1",
        selector_revision="selector:test:v1",
        ruleset_revision="rules:test:v1",
        idempotency_key=ref,
    )


def policy(**updates: object) -> PopulationDecisionPolicy:
    values: dict[str, object] = {
        "policy_revision": "policy:test:v1",
        "default_fidelity_tier": "B1",
        "budget": 3,
        "max_candidates": 3,
        "player_proximity_weight": 1.0,
        "owner_consequence_weight": 1.0,
        "propagation_weight": 1.0,
        "narrative_obligation_weight": 1.0,
        "starvation_weight": 1.0,
    }
    values.update(updates)
    return PopulationDecisionPolicy(**values)


def capabilities() -> tuple[PopulationCapabilityDescriptor, ...]:
    return (
        PopulationCapabilityDescriptor(
            capability_id="capability:supply:v1",
            accepted_behavior_kinds=("schedule_gated_supply",),
            required_scopes=("organization:summary",),
            required_source_domains=("organization",),
            target_owner="organization:bakery",
            allowed_output_kinds=("owner_bound_intent", "character_core_command"),
            capability_revision="capability:supply:v1",
            policy_revision="policy:test:v1",
            enabled=True,
        ),
        PopulationCapabilityDescriptor(
            capability_id="capability:routine:v1",
            accepted_behavior_kinds=("routine_work",),
            required_scopes=("public",),
            required_source_domains=("organization",),
            target_owner="character:core",
            allowed_output_kinds=("presentation_seed",),
            capability_revision="capability:routine:v1",
            policy_revision="policy:test:v1",
            enabled=True,
        ),
        PopulationCapabilityDescriptor(
            capability_id="capability:activation:v1",
            accepted_behavior_kinds=("relationship_negotiation",),
            required_scopes=("public",),
            required_source_domains=("social",),
            target_owner="character:activation",
            allowed_output_kinds=("activation_candidate",),
            capability_revision="capability:activation:v1",
            policy_revision="policy:test:v1",
            enabled=True,
        ),
    )


def test_evaluate_emits_multiple_registered_candidates_without_writes() -> None:
    planner = PopulationDecisionPlanner()
    result = planner.evaluate(read_set(), capabilities(), policy())
    assert {item.behavior_kind for item in result} == {
        "schedule_gated_supply", "routine_work", "relationship_negotiation"
    }


def test_select_spends_budget_on_highest_weighted_candidates_and_defers_the_rest() -> None:
    candidates = (
        candidate("candidate:a", actor="character:char_a", behavior="schedule_gated_supply", consequence=1.0),
        candidate("candidate:b", actor="character:char_b", behavior="routine_work"),
        candidate("candidate:c", actor="character:char_c", behavior="relationship_negotiation"),
    )
    decision = PopulationDecisionPlanner().select(candidates, policy(budget=2, max_candidates=2))
    assert decision.budget_used == 2
    assert len(decision.selected_candidates) == 2
    assert len(decision.deferred_candidates) == 1
    assert decision.decision_reason_codes


def test_policy_weight_changes_selection_without_changing_authority_outputs() -> None:
    candidates = (
        candidate("candidate:owner", actor="character:char_a", behavior="schedule_gated_supply", consequence=1.0),
        candidate("candidate:player", actor="character:char_c", behavior="relationship_negotiation", proximity=1.0),
    )
    owner_first = PopulationDecisionPlanner().select(candidates, policy(owner_consequence_weight=10.0, player_proximity_weight=0.0, budget=1))
    player_first = PopulationDecisionPlanner().select(candidates, policy(owner_consequence_weight=0.0, player_proximity_weight=10.0, budget=1))
    assert owner_first.selected_candidates[0].allowed_outputs == ("owner_bound_intent", "character_core_command")
    assert player_first.selected_candidates[0].allowed_outputs == ("presentation_seed", "activation_candidate")
    assert owner_first.selected_candidates[0].candidate_ref != player_first.selected_candidates[0].candidate_ref


def test_unknown_capability_and_private_projection_are_rejected_without_writes() -> None:
    unknown = candidate("candidate:unknown", actor="character:char_a", behavior="unknown_behavior")
    assert PopulationDecisionPlanner().filter_registered((unknown,), capabilities()) == ()


def test_registered_behavior_can_extend_without_actor_specific_mapping() -> None:
    descriptor = PopulationCapabilityDescriptor(
        capability_id="cap:custom:v1", accepted_behavior_kinds=("custom_observation",),
        required_scopes=("public",), required_source_domains=("organization",),
        target_owner="character:core", allowed_output_kinds=("presentation_seed",),
        capability_revision="cap:custom:v1", policy_revision="policy:test:v1", enabled=True,
    )
    projection = read_set().projections[1].model_copy(update={"payload": {**read_set().projections[1].payload, "candidate_kind": "custom_observation"}})
    custom_read_set = read_set().model_copy(update={"projections": (projection,)}, deep=True)
    result = PopulationDecisionPlanner().evaluate(custom_read_set, (descriptor,), policy())
    assert len(result) == 1
    assert result[0].behavior_kind == "custom_observation"


def test_default_capability_catalog_is_read_only_and_policy_pinned() -> None:
    descriptors = PopulationCapabilityCatalog.default("policy:test:v1")
    assert {behavior for descriptor in descriptors for behavior in descriptor.accepted_behavior_kinds} == {
        "schedule_gated_supply", "routine_work", "relationship_negotiation"
    }
    assert all(descriptor.policy_revision == "policy:test:v1" for descriptor in descriptors)
