from app.population_continuity.decision_surface import PopulationDecisionPlanner
from test_siming_population_decision_planner import candidate, policy


def test_tier_actor_limits_keep_weight_order_duplicates_and_every_deferred_item():
    candidates = tuple(candidate(f"{tier}:{i:03}", actor=f"character:{tier}_{i}", behavior="routine_work").model_copy(
        update={"fidelity_tier": tier}) for tier, count in (("B1", 40), ("B2", 6)) for i in range(count))
    # 同一角色的多条合法义务仍有各自候选/成本，但不占第二个角色名额。
    repeated_actor = candidate("B2:000:extra", actor="character:B2_0", behavior="routine_work")
    offered = (*candidates, repeated_actor)
    planner = PopulationDecisionPlanner()
    decision = planner.select(offered, policy(budget=100, max_candidates=100))
    selected = decision.selected_candidates
    assert len({row.actor_ref for row in selected if row.fidelity_tier == "B1"}) == 32
    assert len({row.actor_ref for row in selected if row.fidelity_tier == "B2"}) == 4
    assert repeated_actor in selected
    assert len(selected) == 37 and decision.budget_used == 37
    assert len(decision.deferred_candidates) == 10
    assert {row.candidate_ref for row in (*selected, *decision.deferred_candidates)} == {row.candidate_ref for row in offered}
    assert planner.select(tuple(reversed(offered)), policy(budget=100, max_candidates=100)) == decision
    retried = planner.select(decision.deferred_candidates, policy(budget=100, max_candidates=100))
    assert retried.selected_candidates == decision.deferred_candidates
    assert retried.deferred_candidates == ()
    # 新边界不能取消既有更紧的总预算或候选上限。
    assert len(planner.select(offered, policy(budget=2, max_candidates=100)).selected_candidates) == 2
    assert len(planner.select(offered, policy(budget=100, max_candidates=1)).selected_candidates) == 1
