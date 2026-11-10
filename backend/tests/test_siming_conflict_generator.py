from app.services.siming_conflict_generator import SimingConflictGenerator
from app.services.siming_knowledge_graph import SimingKnowledgeGraph
from app.models.siming_event import FairnessStateSnapshot
from app.services.siming_policy import SimingInterventionPolicy


def test_windows_require_motivation_knowledge_and_physical_evidence():
    graph = SimingKnowledgeGraph()
    graph.create_conversation('c', 'room', 'scene', 1, 'private')
    for actor in ('alice', 'bob', 'eve'):
        graph.evaluate_access(actor, 'c', 2, 1 if actor != 'eve' else .3, 1 if actor != 'eve' else .3)
        graph.evaluate_membership(actor, 'c', 2, has_spoken=actor != 'eve')
    graph.evaluate_awareness('alice', 'bob', 'c', 2)
    graph.register_information('secret', 'secret', 'alice', 3, 'c', 'conversation')
    generator = SimingConflictGenerator(graph)
    result = generator.generate_opportunities(['alice', 'bob', 'eve'], 4, motivations={'alice', 'bob', 'eve'}, physical_presence={'alice', 'bob', 'eve'}, isolated_actors={'bob'})
    by_type = {candidate.opportunity_type: candidate for candidate in result}
    assert all(by_type[k].feasible for k in ('confrontation', 'secret_exposure', 'isolation'))
    without_evidence = generator.generate_opportunities(['alice', 'bob', 'eve'], 4)
    assert without_evidence and not any(candidate.feasible for candidate in without_evidence)


def test_ended_conversation_and_future_information_do_not_create_windows():
    graph = SimingKnowledgeGraph()
    graph.create_conversation('c', 'room', 'scene', 1, 'private')
    graph.evaluate_access('alice', 'c', 2)
    graph.evaluate_membership('alice', 'c', 2, has_spoken=True)
    graph.end_conversation('c', 3)
    assert SimingConflictGenerator(graph).generate_opportunities(['alice'], 4) == []


def test_candidate_requires_policy_and_cannot_target_blocked_actor():
    generator = SimingConflictGenerator(SimingKnowledgeGraph())
    opportunity = generator.generate_opportunities(['alice'], 4, motivations={'alice'}, physical_presence={'alice'}, isolated_actors={'alice'})[0]
    snapshot = FairnessStateSnapshot(snapshot_id='s', room_id='r', scene_id='s', zone_id='z', causation_id='c', correlation_id='c', blocked_actor_ids=['alice'])
    assert generator.approve_candidate(opportunity, snapshot=snapshot, policy=SimingInterventionPolicy()) is None
