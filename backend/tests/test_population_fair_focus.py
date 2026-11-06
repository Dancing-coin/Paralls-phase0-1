from __future__ import annotations

import pytest

from app.population_continuity.fair_focus import (
    COVERAGE_SOURCES,
    FOCUS_SOURCES,
    CREDIT_CEILING,
    FairFocusQueue,
    FocusCandidate,
    FocusSelection,
)


def _candidate(actor: str, **updates: object) -> FocusCandidate:
    values: dict[str, object] = {
        "actor_ref": actor,
        "source": "fairness_seed",
    }
    values.update(updates)
    return FocusCandidate(**values)


def test_eight_focus_sources_are_declared() -> None:
    assert len(FOCUS_SOURCES) == 8
    assert set(FOCUS_SOURCES) == {
        "world_event",
        "actor_due",
        "relationship_spread",
        "region_pressure",
        "organization_duty",
        "player_interaction",
        "fairness_seed",
        "narrative_obligation",
    }


def test_only_coverage_sources_may_nominate_for_fairness() -> None:
    # Story pressure must not masquerade as fairness.
    assert COVERAGE_SOURCES == frozenset({"fairness_seed", "actor_due"})
    assert COVERAGE_SOURCES < set(FOCUS_SOURCES)


def test_unknown_source_is_rejected() -> None:
    with pytest.raises(Exception):
        _candidate("actor:a", source="plot_dice")


def test_longest_waiting_actor_is_selected_first() -> None:
    queue = FairFocusQueue()
    queue.accrue(["actor:a"])
    queue.accrue(["actor:b"])
    queue.accrue(["actor:b"])

    selection = queue.select(
        [_candidate("actor:a"), _candidate("actor:b")], limit=1
    )

    assert [c.actor_ref for c in selection.selected] == ["actor:b"]


def test_served_actor_has_credit_spent() -> None:
    queue = FairFocusQueue()
    queue.accrue(["actor:a"], amount=0.5)
    selection = queue.select([_candidate("actor:a")], limit=1)

    queue.observe_service([c.actor_ref for c in selection.selected])

    # Without this the queue would keep re-selecting the same actor forever.
    assert queue.credit_for("actor:a") == 0.0


def test_serving_rotates_the_selection() -> None:
    queue = FairFocusQueue()
    roster = ["actor:a", "actor:b"]

    first = queue.select([_candidate("actor:a"), _candidate("actor:b")], limit=1, roster=roster)
    queue.observe_service([c.actor_ref for c in first.selected])
    queue.accrue([c for c in roster if c not in {x.actor_ref for x in first.selected}])

    second = queue.select([_candidate("actor:a"), _candidate("actor:b")], limit=1, roster=roster)

    assert first.selected[0].actor_ref != second.selected[0].actor_ref


def test_ineligible_candidate_is_never_selected() -> None:
    queue = FairFocusQueue()
    queue.accrue(["actor:a"], amount=0.9)

    selection = queue.select(
        [_candidate("actor:a", eligible=False), _candidate("actor:b")], limit=1
    )

    assert [c.actor_ref for c in selection.selected] == ["actor:b"]


def test_priority_outranks_accumulated_credit() -> None:
    queue = FairFocusQueue()
    queue.accrue(["actor:old"], amount=0.5)

    selection = queue.select(
        [_candidate("actor:old"), _candidate("actor:urgent", priority=1.0, source="world_event")],
        limit=1,
    )

    assert [c.actor_ref for c in selection.selected] == ["actor:urgent"]


def test_credit_ceiling_prevents_monopoly() -> None:
    queue = FairFocusQueue()
    for _ in range(100):
        queue.accrue(["actor:a"])

    assert queue.credit_for("actor:a") == CREDIT_CEILING


def test_selection_is_order_independent() -> None:
    first = FairFocusQueue()
    first.accrue(["actor:b"])
    second = FairFocusQueue()
    second.accrue(["actor:b"])

    a = first.select([_candidate("actor:a"), _candidate("actor:b")], limit=1)
    b = second.select([_candidate("actor:b"), _candidate("actor:a")], limit=1)

    assert [c.actor_ref for c in a.selected] == [c.actor_ref for c in b.selected]


def test_budget_exhaustion_defers_instead_of_dropping() -> None:
    queue = FairFocusQueue()
    selection = queue.select(
        [_candidate("actor:a"), _candidate("actor:b")], limit=1
    )

    assert len(selection.selected) == 1
    assert len(selection.deferred) == 1
    assert "focus_budget_exhausted" in selection.reason_codes


def test_starved_actors_are_reported_with_reasons() -> None:
    queue = FairFocusQueue()
    queue.accrue(["actor:a"])
    queue.accrue(["actor:b"])

    selection = queue.select([_candidate("actor:a")], limit=1, roster=["actor:a", "actor:b"])

    assert "actor:b" in selection.starved_actors
    assert "actors_still_waiting" in selection.reason_codes


def test_coverage_is_one_when_nobody_carries_credit() -> None:
    selection = FairFocusQueue().select([], limit=5, roster=["actor:a", "actor:b"])

    assert selection.coverage == 1.0


def test_coverage_falls_when_actors_are_waiting() -> None:
    queue = FairFocusQueue()
    queue.accrue(["actor:a"])
    queue.accrue(["actor:b"])

    selection = queue.select([], limit=5, roster=["actor:a", "actor:b", "actor:c"])

    # Two of three actors unreached, one reached.
    assert selection.coverage == pytest.approx(1 / 3)
    assert "no_eligible_focus" in selection.reason_codes


def test_negative_limit_is_rejected() -> None:
    with pytest.raises(ValueError, match="focus_limit_negative"):
        FairFocusQueue().select([], limit=-1)


def test_served_count_must_match_selection() -> None:
    with pytest.raises(ValueError, match="served_count_mismatch"):
        FocusSelection(served_this_cycle=2, selected=())


def test_decision_surface_spends_credit_for_selected_actors() -> None:
    from app.population_continuity.decision_surface import (
        PopulationDecisionCandidate,
        PopulationDecisionPlanner,
        PopulationDecisionPolicy,
    )

    queue = FairFocusQueue()
    queue.accrue(["character:char_a"], amount=0.7)
    candidate = PopulationDecisionCandidate(
        candidate_ref="candidate:a",
        capability_id="population:routine-presentation:v1",
        actor_ref="character:char_a",
        cohort_ref="cohort:1",
        behavior_kind="routine_work",
        fidelity_tier="B1",
        source_projection_refs=("projection:a",),
        source_revision_vector={"world:bakery": 1},
        estimated_cost=1,
        objective_risk="low",
        player_proximity=0.0,
        narrative_obligation_pressure=0.0,
        unresolved_owner_consequence=0.0,
        propagation_pressure=0.0,
        starvation_credit=0.0,
        allowed_outputs=("presentation_seed",),
        policy_revision="policy:1",
        selector_revision="selector:1",
        ruleset_revision="ruleset:1",
        idempotency_key="candidate:a",
    )
    policy = PopulationDecisionPolicy(
        policy_revision="policy:1",
        default_fidelity_tier="B1",
        budget=10,
        max_candidates=10,
    )

    PopulationDecisionPlanner().select((candidate,), policy, focus_queue=queue)

    # The planner is what actually knows who was served, so it is what must
    # spend the credit; otherwise coverage never improves.
    assert queue.credit_for("character:char_a") == 0.0


def test_decision_surface_keeps_credit_for_deferred_actors() -> None:
    from app.population_continuity.decision_surface import (
        PopulationDecisionCandidate,
        PopulationDecisionPlanner,
        PopulationDecisionPolicy,
    )

    queue = FairFocusQueue()
    queue.accrue(["character:char_b"], amount=0.4)
    candidate = PopulationDecisionCandidate(
        candidate_ref="candidate:b",
        capability_id="population:routine-presentation:v1",
        actor_ref="character:char_b",
        cohort_ref="cohort:1",
        behavior_kind="routine_work",
        fidelity_tier="B1",
        source_projection_refs=("projection:b",),
        source_revision_vector={"world:bakery": 1},
        estimated_cost=99,
        objective_risk="low",
        player_proximity=0.0,
        narrative_obligation_pressure=0.0,
        unresolved_owner_consequence=0.0,
        propagation_pressure=0.0,
        starvation_credit=0.0,
        allowed_outputs=("presentation_seed",),
        policy_revision="policy:1",
        selector_revision="selector:1",
        ruleset_revision="ruleset:1",
        idempotency_key="candidate:b",
    )
    policy = PopulationDecisionPolicy(
        policy_revision="policy:1", default_fidelity_tier="B1", budget=1, max_candidates=10
    )

    PopulationDecisionPlanner().select((candidate,), policy, focus_queue=queue)

    # Budget exhaustion must not look like service.
    assert queue.credit_for("character:char_b") >= 0.4
