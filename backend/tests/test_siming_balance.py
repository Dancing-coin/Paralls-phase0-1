from app.models.siming_event import FairnessStateSnapshot, InterventionCandidate
from app.services.siming_balance import SimingBalanceSystem
from app.services.siming_knowledge_graph import SimingKnowledgeGraph
from app.services.siming_policy import SimingInterventionPolicy


def test_balance_uses_graph_and_preserves_policy_snapshot():
    graph = SimingKnowledgeGraph()
    graph.create_conversation('c', 'room', 'scene', 1)
    graph.evaluate_access('alice', 'c', 2)
    graph.evaluate_membership('alice', 'c', 2, has_spoken=True)
    graph.register_information('i', 'evidence', 'alice', 3, 'c')
    graph.evaluate_knowledge('alice', 'i', 3)
    base = FairnessStateSnapshot(snapshot_id='s', room_id='room', scene_id='scene', zone_id='z', causation_id='cause', correlation_id='corr', eligible_actor_ids=['alice', 'bob'], known_fact_ids=['fact'])
    result = SimingBalanceSystem(graph).evaluate_fairness(['alice', 'bob'], 4, snapshot=base)
    assert result.information_distribution.actor_scores == {'alice': 1, 'bob': 0}
    assert result.participation_distribution.actor_scores == {'alice': 1, 'bob': 0}
    assert result.conversation_access_fairness.actor_scores == {'alice': 1, 'bob': 0}
    assert result.evidence_visibility_distribution.actor_scores == {'alice': 1, 'bob': 0}
    assert result.suspicion_heat_distribution is None
    candidate = InterventionCandidate(candidate_id='c', room_id='room', scene_id='scene', zone_id='z', causation_id='cause', correlation_id='corr', proposed_band='opportunity', target_actor_id='alice', established_fact_ids=['fact'])
    assert SimingInterventionPolicy().evaluate(candidate, snapshot=result).accepted
    assert base.information_distribution is None


def test_balance_does_not_count_future_knowledge_or_access():
    graph = SimingKnowledgeGraph()
    graph.register_information('future', 'statement', 'alice', 10)
    graph.evaluate_knowledge('alice', 'future', 10)
    snapshot = SimingBalanceSystem(graph).evaluate_fairness(['alice', 'bob'], 5)
    assert snapshot.information_distribution.actor_scores == {'alice': 0, 'bob': 0}


def test_balance_evaluates_explicit_suspicion_heat():
    snapshot = SimingBalanceSystem(SimingKnowledgeGraph()).evaluate_fairness(
        ['alice', 'bob'], 5, suspicion_heat={'alice': 1.0, 'bob': 0.0}
    )
    assert snapshot.suspicion_heat_distribution.actor_scores == {'alice': 1.0, 'bob': 0.0}
    assert snapshot.suspicion_heat_distribution.gini_coefficient == 0.5
