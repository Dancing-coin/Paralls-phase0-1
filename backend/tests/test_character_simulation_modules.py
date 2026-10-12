import pytest

from app.population_continuity.activation_policy import resolve_participation
from app.population_continuity.character_modules import evaluate_modules, farmer_module_definitions
from app.population_continuity.flood_scenario import flood_module_states, flood_participation_policies
from test_character_simulation_frame import frame


def farmer_frame(actor="character:char_b", **states):
    values = dict(flood_module_states(actor_ref=actor))
    values.update(states)
    return frame(actor_ref=actor, profile_ref=actor, module_states=values,
        participation=resolve_participation(policies=flood_participation_policies(
            actor_ref=actor, scenario_revision="flood:v1"), tick=10),
        module_definitions=farmer_module_definitions())


def test_eight_module_declarations_default_protected_fields_to_individual_only():
    definitions = farmer_module_definitions()
    assert {item.category for item in definitions} == {
        "identity", "needs", "schedule", "household", "supply", "situation", "affect", "behavior"}
    assert len(definitions) == 8
    household = next(item for item in definitions if item.module_ref == "household")
    assert household.field_policy("protected_refs").individual_only
    assert all(item.distribution_policy == "none" for item in definitions)


def test_care_obligation_prevents_routine_override_and_preserves_input():
    value = farmer_frame("character:char_a")
    before = value.model_dump_json()
    proposals = evaluate_modules(value, to_tick=20)
    assert any(item.proposal_kind == "upgrade_request" for item in proposals)
    assert not any(item.proposal_kind == "activity_candidate" for item in proposals)
    assert all(item.actor_ref == "character:char_a" for item in proposals)
    assert value.model_dump_json() == before


def test_normal_farmer_has_pure_continuity_and_activity_candidates():
    value = farmer_frame()
    proposals = evaluate_modules(value, to_tick=20)
    assert {item.proposal_kind for item in proposals} >= {"continuity_delta", "activity_candidate"}
    delta = next(item for item in proposals if item.proposal_kind == "continuity_delta")
    assert delta.typed_payload.state_delta["fatigue"] < 0.2
    assert delta.read_dependencies == value.source_revision_vector
    assert proposals == evaluate_modules(value, to_tick=20)
    assert all(item.expiry_tick <= value.participation_resolution.review_tick for item in proposals)


def test_supply_pressure_only_produces_an_admitted_action_candidate():
    value = farmer_frame(supply={"shortage": True})
    proposal = next(item for item in evaluate_modules(value, to_tick=20)
        if item.proposal_kind == "action_candidate")
    assert proposal.typed_payload.capability_ref == "population:schedule-gated-supply:v1"
    assert "delivered" not in proposal.typed_payload.model_dump()


@pytest.mark.parametrize("actor", ["character:char_a", "character:char_b", "character:char_c"])
def test_flood_policy_never_relaxes_individual_protection(actor):
    resolution = resolve_participation(policies=flood_participation_policies(
        actor_ref=actor, scenario_revision="flood:v1"), tick=10)
    assert ("B0" in resolution.allowed_tiers) == (actor == "character:char_b")
    assert "household.members" in resolution.forbidden_dimensions
    assert "private_memory" in resolution.forbidden_dimensions


def test_flood_expiry_removes_b0_without_resetting_inputs():
    policies = flood_participation_policies(actor_ref="character:char_b", scenario_revision="flood:v1")
    assert "B0" not in resolve_participation(policies=policies, tick=7200).allowed_tiers
    assert "B3" in resolve_participation(policies=policies, tick=7200).allowed_tiers


def test_scenario_does_not_grant_unregistered_actor_or_unknown_rules():
    with pytest.raises(ValueError, match="flood_actor_unknown"):
        flood_module_states(actor_ref="character:unknown")
    with pytest.raises(ValueError, match="flood_rules_unknown"):
        flood_participation_policies(actor_ref="character:char_a", scenario_revision="unknown")


def test_unknown_need_state_is_not_treated_as_safe_zero():
    value = farmer_frame(needs={"fatigue": None, "need_pressure": 0.1, "revision": 0})
    with pytest.raises(ValueError, match="module_needs_context_insufficient"):
        evaluate_modules(value, to_tick=20)


def test_stale_frame_and_reverse_window_are_rejected():
    value = farmer_frame()
    with pytest.raises(ValueError, match="module_window_invalid"):
        evaluate_modules(value, to_tick=9)
    with pytest.raises(ValueError, match="module_frame_invalid"):
        evaluate_modules(value.model_copy(update={"frame_digest": "bad"}), to_tick=20)
