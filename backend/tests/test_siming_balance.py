import pytest

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
    assert result.suspicion_heat_distribution.actor_scores == {'alice': 0.5, 'bob': 0.5}
    assert result.overall_fairness_score == 0.6
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


def test_fairness_snapshot_new_fields_keep_legacy_defaults():
    snapshot = FairnessStateSnapshot(
        snapshot_id='legacy', room_id='room', scene_id='scene', zone_id='zone',
        causation_id='cause', correlation_id='corr',
    )
    assert snapshot.information_distribution is None
    assert snapshot.participation_distribution is None
    assert snapshot.conversation_access_fairness is None
    assert snapshot.suspicion_heat_distribution is None
    assert snapshot.evidence_visibility_distribution is None
    assert snapshot.overall_fairness_score == 1.0
    assert not snapshot.needs_intervention
    assert snapshot.intervention_urgency == 'none'


@pytest.mark.parametrize(
    'actor_count,explicit_heat,expected_score,urgency',
    [(1, True, 1.0, 'none'), (2, True, 0.5, 'low'),
     (3, False, 7 / 15, 'medium'), (3, True, 1 / 3, 'high'),
     (4, True, 0.25, 'critical')],
)
def test_balance_detects_concentrated_opportunities_across_five_dimensions(
    actor_count, explicit_heat, expected_score, urgency,
):
    graph = SimingKnowledgeGraph()
    graph.create_conversation('c', 'room', 'scene', 1)
    graph.evaluate_access('actor:0', 'c', 2)
    graph.evaluate_membership('actor:0', 'c', 2, has_spoken=True)
    graph.register_information('clue', 'evidence', 'actor:0', 3, 'c')
    graph.evaluate_knowledge('actor:0', 'clue', 3)
    actors = [f'actor:{index}' for index in range(actor_count)]
    heat = {actor: float(actor == 'actor:0') for actor in actors} if explicit_heat else None

    result = SimingBalanceSystem(graph).evaluate_fairness(actors, 4, suspicion_heat=heat)

    assert result.overall_fairness_score == pytest.approx(expected_score)
    assert result.intervention_urgency == urgency
    assert result.needs_intervention == (expected_score < 0.6)
    if actor_count > 1:
        assert 'actor:1' in result.evidence_visibility_distribution.marginalized_actors
        assert 'actor:1' in result.participation_distribution.marginalized_actors


@pytest.mark.parametrize('heat', [
    {'alice': 0.5}, {'alice': 0.5, 'bob': 0.5, 'outsider': 0.5},
    {'alice': -0.1, 'bob': 0.5}, {'alice': 1.1, 'bob': 0.5},
    {'alice': float('nan'), 'bob': 0.5}, {'alice': float('inf'), 'bob': 0.5},
])
def test_balance_rejects_incomplete_or_invalid_suspicion_heat(heat):
    with pytest.raises(ValueError, match='suspicion heat'):
        SimingBalanceSystem(SimingKnowledgeGraph()).evaluate_fairness(
            ['alice', 'bob'], 4, suspicion_heat=heat,
        )


@pytest.mark.parametrize('initial_active,later_excluded,expected', [
    (False, False, 0.0), (True, True, 1.0),
])
def test_future_membership_changes_do_not_rewrite_past_participation(
    initial_active, later_excluded, expected,
):
    graph = SimingKnowledgeGraph()
    graph.create_conversation('c', 'room', 'scene', 1)
    graph.evaluate_access('alice', 'c', 2)
    graph.evaluate_membership('alice', 'c', 2, has_spoken=initial_active)
    graph.evaluate_membership('alice', 'c', 10, has_spoken=True,
                              explicitly_excluded=later_excluded)

    result = SimingBalanceSystem(graph).evaluate_fairness(['alice'], 5)

    assert result.participation_distribution.actor_scores == {'alice': expected}
