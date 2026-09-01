import pytest
from pydantic import ValidationError

from app.population_continuity import PopulationDecision, PopulationDecisionCandidate


def candidate_payload() -> dict:
    return {
        "candidate_ref": "candidate:char_a:supply:W0",
        "actor_ref": "character:char_a",
        "cohort_ref": "cohort:bakery:W0",
        "behavior_kind": "schedule_gated_supply",
        "fidelity_tier": "B2",
        "source_projection_refs": ("projection:char_a:W0",),
        "source_revision_vector": {"world:bakery": 1},
        "evidence_refs": ("event:frost:1",),
        "estimated_cost": 1,
        "objective_risk": "low",
        "player_proximity": 0.2,
        "narrative_obligation_pressure": 0.0,
        "unresolved_owner_consequence": 1.0,
        "propagation_pressure": 0.0,
        "starvation_credit": 0.0,
        "allowed_outputs": ("owner_bound_intent", "character_core_command"),
        "policy_revision": "mode:v1",
        "selector_revision": "selector:cohort-bakery:v1",
        "ruleset_revision": "rules:cohort-bakery:v1",
        "idempotency_key": "candidate:char_a:supply:W0",
    }


def test_candidate_preserves_bounded_decision_fields() -> None:
    candidate = PopulationDecisionCandidate(**candidate_payload())
    assert candidate.fidelity_tier == "B2"


def test_unknown_output_kind_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PopulationDecisionCandidate.model_validate({**candidate_payload(), "allowed_outputs": ("free_form_write",)})


def test_decision_budget_and_digests_are_explicit() -> None:
    decision = PopulationDecision(
        selected_candidates=(),
        deferred_candidates=(),
        rejected_candidates=(),
        unprocessed_refs=("bucket:far",),
        budget_used=0,
        budget_remaining=3,
        fidelity_counts={},
        decision_reason_codes=("budget_reserved_for_player",),
        read_set_digest="sha256:read",
        result_digest="sha256:result",
    )
    assert decision.budget_remaining == 3
    assert decision.read_set_digest == "sha256:read"


def test_nested_mappings_are_immutable() -> None:
    candidate = PopulationDecisionCandidate(**candidate_payload())
    decision = PopulationDecision(
        budget_used=0,
        budget_remaining=3,
        fidelity_counts={"B2": 1},
        read_set_digest="sha256:read",
        result_digest="sha256:result",
    )
    with pytest.raises(TypeError):
        candidate.source_revision_vector["world:bakery"] = 2
    with pytest.raises(TypeError):
        decision.fidelity_counts["B0"] = 1
