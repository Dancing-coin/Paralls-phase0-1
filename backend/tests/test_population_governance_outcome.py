from __future__ import annotations

import pytest

from app.population_continuity.decision_surface import (
    PopulationDecision,
    PopulationDecisionCandidate,
    PopulationDecisionPlanner,
    PopulationDecisionPolicy,
)


def _candidate(**updates: object) -> PopulationDecisionCandidate:
    values: dict[str, object] = {
        "candidate_ref": "candidate:a",
        "capability_id": "population:routine-presentation:v1",
        "actor_ref": "character:char_a",
        "cohort_ref": "cohort:w1",
        "behavior_kind": "routine_work",
        "fidelity_tier": "B1",
        "source_projection_refs": ("projection:a",),
        "source_revision_vector": {"world:bakery": 1},
        "estimated_cost": 1,
        "objective_risk": "low",
        "player_proximity": 0.0,
        "narrative_obligation_pressure": 0.0,
        "unresolved_owner_consequence": 0.0,
        "propagation_pressure": 0.0,
        "starvation_credit": 0.0,
        "allowed_outputs": ("presentation_seed",),
        "policy_revision": "policy:v1",
        "selector_revision": "selector:v1",
        "ruleset_revision": "ruleset:v1",
        "idempotency_key": "candidate:a",
    }
    values.update(updates)
    return PopulationDecisionCandidate(**values)


def _policy(**updates: object) -> PopulationDecisionPolicy:
    values: dict[str, object] = {
        "budget": 10,
        "max_candidates": 10,
        "policy_revision": "policy:v1",
        "default_fidelity_tier": "B1",
    }
    values.update(updates)
    return PopulationDecisionPolicy(**values)


def test_budget_exhaustion_records_an_auditable_deferral() -> None:
    decision = PopulationDecisionPlanner().select(
        (_candidate(candidate_ref="candidate:big", estimated_cost=5),),
        _policy(budget=2),
    )

    assert decision.selected_candidates == ()
    assert decision.governance_outcome == "no_op"
    assert len(decision.deferrals) == 1
    deferral = decision.deferrals[0]
    assert deferral.reason == "budget_exhausted"
    assert deferral.candidate_ref == "candidate:big"
    assert deferral.estimated_cost == 5
    assert deferral.budget_remaining == 2


def test_max_candidates_reached_is_distinguished_from_budget_starvation() -> None:
    decision = PopulationDecisionPlanner().select(
        (
            _candidate(candidate_ref="candidate:a", estimated_cost=1),
            _candidate(candidate_ref="candidate:b", estimated_cost=1),
        ),
        _policy(budget=10, max_candidates=1),
    )

    assert len(decision.selected_candidates) == 1
    assert [item.reason for item in decision.deferrals] == ["max_candidates_reached"]


def test_fidelity_tier_limit_records_fidelity_deferral() -> None:
    over_limit = tuple(
        _candidate(
            candidate_ref=f"candidate:b2:{index}",
            actor_ref=f"character:actor_{index}",
            fidelity_tier="B2",
            estimated_cost=1,
        )
        for index in range(6)
    )

    decision = PopulationDecisionPlanner().select(over_limit, _policy(budget=100, max_candidates=100))

    deferred_reasons = {item.reason for item in decision.deferrals}
    assert deferred_reasons == {"fidelity_deferred"}
    assert len(decision.selected_candidates) == 4


def test_successful_selection_reports_accept_outcome() -> None:
    decision = PopulationDecisionPlanner().select((_candidate(),), _policy())

    assert decision.selected_candidates
    assert decision.governance_outcome == "accept"
    assert decision.deferrals == ()


def test_accept_outcome_requires_a_selection() -> None:
    with pytest.raises(ValueError, match="governance_outcome_accept_requires_selection"):
        PopulationDecision(
            selected_candidates=(),
            budget_used=0,
            budget_remaining=0,
            governance_outcome="accept",
            read_set_digest="sha256:x",
            result_digest="sha256:y",
        )


def test_no_op_outcome_rejects_a_selection() -> None:
    with pytest.raises(ValueError, match="governance_outcome_no_op_requires_empty_selection"):
        PopulationDecision(
            selected_candidates=(_candidate(),),
            budget_used=1,
            budget_remaining=9,
            governance_outcome="no_op",
            read_set_digest="sha256:x",
            result_digest="sha256:y",
        )


def test_upgrade_outcome_cannot_settle_an_owner_fact() -> None:
    with pytest.raises(ValueError, match="governance_outcome_upgrade_cannot_settle_owner_fact"):
        PopulationDecision(
            selected_candidates=(
                _candidate(allowed_outputs=("owner_bound_intent", "character_core_command")),
            ),
            budget_used=1,
            budget_remaining=9,
            governance_outcome="upgrade",
            read_set_digest="sha256:x",
            result_digest="sha256:y",
        )


def test_upgrade_outcome_allows_a_presentation_only_selection() -> None:
    decision = PopulationDecision(
        selected_candidates=(_candidate(),),
        budget_used=1,
        budget_remaining=9,
        governance_outcome="upgrade",
        read_set_digest="sha256:x",
        result_digest="sha256:y",
    )

    assert decision.governance_outcome == "upgrade"
