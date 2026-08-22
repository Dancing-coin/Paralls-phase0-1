from app.models.siming_story_graph import StoryDecisionCandidate
from app.services.siming_story_node_orchestrator import StoryNodeOrchestrator


def story_candidate(
    candidate_id: str,
    *,
    fact_gate: bool = True,
    player_choice: bool = True,
    actor_autonomy: bool = True,
    resource_score: float = 0.0,
) -> StoryDecisionCandidate:
    return StoryDecisionCandidate(
        candidate_id=candidate_id,
        runtime_node_ref=f"runtime:{candidate_id}",
        confirmed_fact=fact_gate,
        player_choice=player_choice,
        actor_autonomy=actor_autonomy,
        world_feasibility=True,
        safety=True,
        playability_fairness=True,
        open_obligation=True,
        reachable_attractor=True,
        narrative_score=0.5,
        resource_score=resource_score,
    )


def test_resource_value_cannot_rescue_fact_rejected_candidate() -> None:
    orchestrator = StoryNodeOrchestrator()
    rejected = story_candidate("reuse-rich", fact_gate=False, resource_score=1.0)
    accepted = story_candidate("fresh", fact_gate=True, resource_score=0.0)

    result = orchestrator.rank([rejected, accepted])

    assert [item.candidate_id for item in result.eligible] == ["fresh"]
    assert result.rejected[0].reason == "fact_gate_failed"


def test_orchestrator_rejects_in_fixed_hard_gate_order() -> None:
    orchestrator = StoryNodeOrchestrator()
    candidate = story_candidate(
        "two-failures",
        player_choice=False,
        actor_autonomy=False,
        resource_score=1.0,
    )

    result = orchestrator.rank([candidate])

    assert result.eligible == []
    assert result.rejected[0].reason == "player_choice_gate_failed"
