import pytest

from app.services.siming_knowledge_graph import SimingKnowledgeGraph
from app.services.siming_balance import SimingBalanceSystem
from app.services.siming_conflict_generator import SimingConflictGenerator
from app.services.siming_runtime import SimingRuntime


def _graph() -> SimingKnowledgeGraph:
    graph = SimingKnowledgeGraph()
    graph.create_conversation("conv-1", "room-1", "scene-1", 100, "private")
    return graph


def test_conversation_creation_is_readable() -> None:
    graph = _graph()
    assert graph.get_conversation("conv-1").started_at == 100


def test_access_quality_uses_space_and_acoustics() -> None:
    graph = _graph()
    assert graph.evaluate_access("a", "conv-1", 110, 1, 1).access_quality == "full"
    assert graph.evaluate_access("b", "conv-1", 110, 0.6, 0.6).access_quality == "partial"
    assert graph.evaluate_access("c", "conv-1", 110, 0.4, 0.4).access_quality == "minimal"
    assert graph.evaluate_access("d", "conv-1", 110, 0.1, 0.1).access_quality == "none"


def test_access_requires_existing_conversation_and_bounded_scores() -> None:
    graph = _graph()
    with pytest.raises(KeyError):
        graph.evaluate_access("a", "missing", 110)
    with pytest.raises(ValueError):
        graph.evaluate_access("a", "conv-1", 110, 1.1, 1)


def test_membership_depends_on_access_and_speech() -> None:
    graph = _graph()
    assert graph.evaluate_membership("a", "conv-1", 110).membership_type == "listener"
    graph.evaluate_access("a", "conv-1", 110)
    assert graph.evaluate_membership("a", "conv-1", 110).membership_type == "candidate"
    assert graph.evaluate_membership("a", "conv-1", 111, has_spoken=True).membership_type == "active_member"
    assert graph.who_is_in_conversation("conv-1") == ["a"]


def test_awareness_requires_observer_access() -> None:
    graph = _graph()
    graph.evaluate_access("b", "conv-1", 110)
    assert graph.evaluate_awareness("a", "b", "conv-1", 110).awareness_level == "unaware"
    graph.evaluate_access("a", "conv-1", 111)
    assert graph.evaluate_awareness("a", "b", "conv-1", 111).awareness_level == "aware_mutual"


def test_conversation_knowledge_requires_nonzero_access() -> None:
    graph = _graph()
    graph.register_information("fact-1", "statement", "a", 110, "conv-1")
    assert graph.evaluate_knowledge("b", "fact-1", 111, "conv-1").knowledge_state == "unknown"
    graph.evaluate_access("b", "conv-1", 112, 0.4, 0.4)
    graph.register_information("fact-2", "statement", "a", 112, "conv-1")
    assert graph.evaluate_knowledge("b", "fact-2", 112, "conv-1").knowledge_state == "suspected"
    graph.evaluate_access("b", "conv-1", 113)
    graph.register_information("fact-3", "statement", "a", 113, "conv-1")
    assert graph.evaluate_knowledge("b", "fact-3", 113, "conv-1").knowledge_state == "known"


def test_unknown_information_does_not_create_knowledge() -> None:
    graph = _graph()
    result = graph.evaluate_knowledge("a", "missing", 110)
    assert result.knowledge_state == "unknown"
    assert graph.who_knows("missing") == []


def test_explicitly_excluded_actor_is_not_a_member() -> None:
    graph = _graph()
    graph.evaluate_access("a", "conv-1", 110)
    result = graph.evaluate_membership("a", "conv-1", 110, explicitly_excluded=True)
    assert result.membership_type == "excluded"
    assert graph.who_is_in_conversation("conv-1") == []


def test_eavesdropper_is_distinct_from_active_and_silent_members() -> None:
    graph = _graph()
    graph.evaluate_access("a", "conv-1", 110)
    graph.evaluate_membership("a", "conv-1", 110, has_spoken=True)
    graph.evaluate_access("b", "conv-1", 110, 0.4, 0.4)
    graph.evaluate_membership("b", "conv-1", 110)
    assert graph.who_is_in_conversation("conv-1") == ["a"]
    assert graph.who_is_listening("conv-1") == ["b"]
    assert graph.evaluate_privacy_risk("a", "conv-1").eavesdropper_ids == ["b"]
    graph.register_information("secret-1", "secret", "a", 110, "conv-1", "conversation")
    knowledge = graph.evaluate_knowledge("b", "secret-1", 110, "conv-1")
    assert (knowledge.knowledge_state, knowledge.source_type) == ("suspected", "eavesdrop")


def test_who_knows_returns_only_known_claimants() -> None:
    graph = _graph()
    graph.register_information("fact-1", "statement", "a", 110, "conv-1")
    graph.evaluate_access("a", "conv-1", 110)
    graph.evaluate_access("b", "conv-1", 110, 0.4, 0.4)
    graph.evaluate_knowledge("a", "fact-1", 110, "conv-1")
    graph.evaluate_knowledge("b", "fact-1", 110, "conv-1")
    assert graph.who_knows("fact-1") == ["a"]


def test_ending_conversation_rejects_later_access() -> None:
    graph = _graph()
    graph.end_conversation("conv-1", 120)
    with pytest.raises(ValueError):
        graph.evaluate_access("a", "conv-1", 121)


def test_boundary_change_is_recorded_and_updates_private_risk() -> None:
    graph = _graph()
    change = graph.change_boundary("conv-1", "public", 110, "discussion opened")
    assert (change.old_boundary, change.new_boundary) == ("private", "public")
    graph.evaluate_access("a", "conv-1", 110)
    graph.evaluate_membership("a", "conv-1", 110, has_spoken=True)
    graph.evaluate_access("b", "conv-1", 110, 0.4, 0.4)
    graph.evaluate_membership("b", "conv-1", 110)
    assert graph.evaluate_privacy_risk("a", "conv-1").risk_level == "none"


def test_private_information_is_not_directly_visible_to_other_actors() -> None:
    graph = _graph()
    graph.register_information("secret-1", "secret", "a", 110, "conv-1", "private")
    assert graph.evaluate_knowledge("b", "secret-1", 110).knowledge_state == "unknown"
    assert graph.evaluate_knowledge("a", "secret-1", 110).knowledge_state == "known"


def test_runtime_accepts_an_injected_knowledge_graph_without_changing_tick_api() -> None:
    graph = SimingKnowledgeGraph()
    runtime = SimingRuntime(knowledge_graph=graph)
    assert runtime.knowledge_graph is graph
    assert SimingRuntime().knowledge_graph is not None


def test_runtime_assembles_capabilities_with_shared_graph_and_accepts_injection() -> None:
    graph = _graph()
    graph.evaluate_access("a", "conv-1", 110)
    graph.evaluate_membership("a", "conv-1", 110, has_spoken=True)
    graph.evaluate_access("b", "conv-1", 110)
    graph.evaluate_membership("b", "conv-1", 110, has_spoken=True)
    graph.evaluate_awareness("a", "b", "conv-1", 110)
    runtime = SimingRuntime(knowledge_graph=graph)

    fairness = runtime.balance_system.evaluate_fairness(["a", "b"], 110)
    assert fairness.participation_distribution.actor_scores == {"a": 1.0, "b": 1.0}
    opportunities = runtime.conflict_generator.generate_opportunities(
        ["a", "b"], 110, motivations={"a"}, physical_presence={"a", "b"}
    )
    assert any(item.opportunity_type == "confrontation" and item.feasible for item in opportunities)

    balance = SimingBalanceSystem(graph)
    generator = SimingConflictGenerator(graph)
    injected = SimingRuntime(knowledge_graph=graph, balance_system=balance, conflict_generator=generator)
    assert injected.balance_system is balance
    assert injected.conflict_generator is generator


def test_late_arrival_does_not_learn_earlier_information() -> None:
    graph = _graph()
    graph.register_information("early", "statement", "a", 110, "conv-1")
    graph.evaluate_access("b", "conv-1", 120)
    assert graph.evaluate_knowledge("b", "early", 120, "conv-1").knowledge_state == "unknown"


def test_known_information_survives_loss_of_access_and_conversation_end() -> None:
    graph = _graph()
    graph.evaluate_access("b", "conv-1", 110)
    graph.register_information("fact", "statement", "a", 110, "conv-1")
    first = graph.evaluate_knowledge("b", "fact", 110, "conv-1")
    graph.evaluate_access("b", "conv-1", 120, 0, 0)
    graph.end_conversation("conv-1", 121)
    assert graph.evaluate_knowledge("b", "fact", 122, "conv-1") == first


def test_future_access_cannot_be_used_for_past_membership() -> None:
    graph = _graph()
    graph.evaluate_access("a", "conv-1", 120)
    assert graph.evaluate_membership("a", "conv-1", 110).membership_type == "listener"


def test_past_membership_query_does_not_overwrite_current_membership() -> None:
    graph = _graph()
    graph.evaluate_access("a", "conv-1", 120)
    graph.evaluate_membership("a", "conv-1", 120, has_spoken=True)
    assert graph.evaluate_membership("a", "conv-1", 110).membership_type == "listener"
    assert graph.who_is_in_conversation("conv-1") == ["a"]


def test_older_access_does_not_replace_latest_privacy_observation() -> None:
    graph = _graph()
    graph.evaluate_access("a", "conv-1", 120, 0, 0)
    graph.evaluate_membership("a", "conv-1", 120)
    graph.evaluate_access("a", "conv-1", 110, 0.4, 0.4)
    assert graph.evaluate_privacy_risk("b", "conv-1").risk_level == "none"


def test_no_access_does_not_count_as_privacy_exposure() -> None:
    graph = _graph()
    graph.evaluate_access("a", "conv-1", 110, 0, 0)
    graph.evaluate_membership("a", "conv-1", 110)
    assert graph.evaluate_privacy_risk("b", "conv-1").risk_level == "none"


def test_membership_keeps_original_join_time() -> None:
    graph = _graph()
    graph.evaluate_access("a", "conv-1", 110)
    graph.evaluate_membership("a", "conv-1", 110, has_spoken=True)
    assert graph.evaluate_membership("a", "conv-1", 120, has_spoken=True).joined_at == 110


def test_past_query_does_not_erase_current_knowledge() -> None:
    graph = _graph()
    graph.evaluate_access("b", "conv-1", 110)
    graph.register_information("fact", "statement", "a", 110, "conv-1")
    graph.evaluate_knowledge("b", "fact", 120, "conv-1")
    assert graph.evaluate_knowledge("b", "fact", 105, "conv-1").knowledge_state == "unknown"
    assert graph.who_knows("fact") == ["b"]


def test_past_query_cannot_reveal_a_future_suspicion() -> None:
    graph = _graph()
    graph.evaluate_access("b", "conv-1", 110, 0.4, 0.4)
    graph.register_information("fact", "statement", "a", 110, "conv-1")
    current = graph.evaluate_knowledge("b", "fact", 120)
    assert current.knowledge_state == "suspected"
    assert graph.evaluate_knowledge("b", "fact", 105).knowledge_state == "unknown"
    assert graph.evaluate_knowledge("b", "fact", 121).knowledge_state == "suspected"


def test_awareness_requires_evidence_of_both_actors_and_symmetric_mutual_access() -> None:
    graph = _graph()
    graph.evaluate_access("a", "conv-1", 110)
    assert graph.evaluate_awareness("a", "absent", "conv-1", 110).awareness_level == "unaware"
    graph.evaluate_access("b", "conv-1", 110, 0.4, 0.4)
    assert graph.evaluate_awareness("a", "b", "conv-1", 110).awareness_level == "aware_present"
    assert graph.evaluate_awareness("b", "a", "conv-1", 110).awareness_level == "aware_present"


def test_awareness_history_preserves_shared_knowledge_and_current_state() -> None:
    graph = _graph()
    for actor in ("a", "b"):
        graph.evaluate_access(actor, "conv-1", 110)
    graph.evaluate_awareness("a", "b", "conv-1", 110)
    graph.register_information("shared", "statement", "a", 110, "conv-1")
    for actor in ("a", "b"):
        graph.evaluate_knowledge(actor, "shared", 110)
    graph.evaluate_access("b", "conv-1", 120, 0, 0)
    graph.evaluate_awareness("a", "b", "conv-1", 120)

    assert graph.awareness_at("a", "b", "conv-1", 110) == "aware_mutual"
    assert graph.evaluate_higher_order_knowledge("a", "b", "shared", 120).knowledge_state == "known"
    graph.evaluate_awareness("a", "b", "conv-1", 105)
    assert graph.awareness_at("a", "b", "conv-1", 120) == "unaware"


def test_higher_order_knowledge_requires_observed_shared_access() -> None:
    graph = _graph()
    graph.evaluate_access("a", "conv-1", 110)
    graph.evaluate_access("b", "conv-1", 110)
    graph.evaluate_awareness("a", "b", "conv-1", 110)
    graph.register_information("shared", "statement", "a", 110, "conv-1")
    graph.evaluate_knowledge("a", "shared", 110)
    graph.evaluate_knowledge("b", "shared", 110)

    result = graph.evaluate_higher_order_knowledge("a", "b", "shared", 110)

    assert (result.knowledge_state, result.source_type) == ("known", "inference")
    assert graph.who_knows("shared") == ["a", "b"]
    assert graph.who_knows_knows("shared", "b") == ["a"]


def test_higher_order_knowledge_rejects_unobserved_or_late_access() -> None:
    graph = _graph()
    graph.evaluate_access("a", "conv-1", 110)
    graph.evaluate_access("b", "conv-1", 120)
    graph.register_information("shared", "statement", "a", 110, "conv-1")
    graph.evaluate_knowledge("a", "shared", 110)
    graph.evaluate_knowledge("b", "shared", 120)

    result = graph.evaluate_higher_order_knowledge("a", "b", "shared", 120)

    assert result.knowledge_state == "unknown"
    assert graph.who_knows_knows("shared", "b") == []


def test_higher_order_knowledge_does_not_use_future_claims_or_erase_current_claim() -> None:
    graph = _graph()
    for actor in ("a", "b"):
        graph.evaluate_access(actor, "conv-1", 110)
    graph.evaluate_awareness("a", "b", "conv-1", 110)
    graph.register_information("shared", "statement", "a", 110, "conv-1")
    for actor in ("a", "b"):
        graph.evaluate_knowledge(actor, "shared", 120)

    assert graph.evaluate_higher_order_knowledge("a", "b", "shared", 115).knowledge_state == "unknown"
    assert graph.evaluate_higher_order_knowledge("a", "b", "shared", 120).knowledge_state == "known"
    assert graph.evaluate_higher_order_knowledge("a", "b", "shared", 105).knowledge_state == "unknown"
    assert graph.who_knows_knows("shared", "b") == ["a"]


def test_shared_knowledge_without_awareness_does_not_reveal_another_actors_knowledge() -> None:
    graph = _graph()
    for actor in ("a", "b"):
        graph.evaluate_access(actor, "conv-1", 110)
    graph.register_information("shared", "statement", "a", 110, "conv-1")
    for actor in ("a", "b"):
        graph.evaluate_knowledge(actor, "shared", 110)

    assert graph.who_knows("shared") == ["a", "b"]
    assert graph.evaluate_higher_order_knowledge("a", "b", "shared", 110).knowledge_state == "unknown"


@pytest.mark.parametrize("quality", [0.4, 1.0])
def test_private_information_cannot_leak_through_conversation_access(quality) -> None:
    graph = _graph()
    graph.evaluate_membership("b", "conv-1", 110)
    graph.evaluate_access("b", "conv-1", 110, quality, quality)
    graph.register_information("secret", "secret", "a", 110, "conv-1", "private")
    assert graph.evaluate_knowledge("b", "secret", 110, "conv-1").knowledge_state == "unknown"
