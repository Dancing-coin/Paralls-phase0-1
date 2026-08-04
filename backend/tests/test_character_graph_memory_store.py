from pathlib import Path

import pytest

from app.character_agent.storage.graph_memory_store import CharacterGraphMemoryStore
from app.character_agent.storage.memory_store import CharacterAgentMemoryStore
from app.models.siming_heavenly_graph import HeavenlyGraphScope, HeavenlyNodeQuery
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter


def _scope(actor_id: str) -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:demo",
        session_id="session:demo",
        story_branch_id="branch:main",
        graph_namespace="actor_private",
        owner_actor_id=actor_id,
    )


def _event(
    event_type: str,
    event_id: str,
    producer_ts: int,
    payload: dict[str, object],
    *,
    actor_id: str = "char_b",
) -> dict[str, object]:
    return {
        "event_id": event_id,
        "event_index": producer_ts,
        "actor_id": actor_id,
        "event_type": event_type,
        "producer_ts": producer_ts,
        "payload": payload,
    }


def test_percept_deposits_event_and_observation_in_actor_private_graph() -> None:
    graph = InMemoryHeavenlyGraphAdapter()
    store = CharacterGraphMemoryStore(graph, scope_resolver=_scope)

    store.write_event(
        _event(
            "character_perceived_event",
            "authority:letter:destroyed",
            100,
            {
                "summary": "the letter was destroyed",
                "target_actor_id": "obj_letter",
                "percept_channel": "visual",
            },
        )
    )

    bundle = store.retrieval_record_bundle("char_b")

    assert bundle.event_memories[0].source_event_id == "authority:letter:destroyed"
    assert bundle.observation_memories[0].observed_entity_id == "obj_letter"
    assert {
        node.node_type
        for node in graph.query_nodes(
            HeavenlyNodeQuery(
                scope=_scope("char_b"),
                valid_at=100,
                node_types=["actor_memory:event", "actor_memory:observation"],
                limit=None,
            )
        )
    } == {"actor_memory:event", "actor_memory:observation"}
    assert store.retrieval_record_bundle("char_a").event_memories == []


def test_deposits_all_five_pools_and_replays_source_event_without_duplicates() -> None:
    graph = InMemoryHeavenlyGraphAdapter()
    store = CharacterGraphMemoryStore(graph, scope_resolver=_scope)
    events = [
        _event(
            "character_perceived_event", "evt:percept", 100, {"summary": "letter seen"}
        ),
        _event(
            "knowledge_belief_event",
            "evt:knowledge",
            200,
            {
                "proposition_key": "letter:destroyed",
                "proposition": "letter is destroyed",
                "state": "believed",
                "confidence": 0.9,
            },
        ),
        _event(
            "social_cognition_event",
            "evt:social",
            300,
            {
                "entity_id": "char_a",
                "trust_baseline": 0.4,
            },
        ),
        _event(
            "higher_order_belief_event",
            "evt:higher",
            400,
            {
                "subject_actor_id": "char_a",
                "proposition_key": "letter:destroyed",
                "meta_belief": "char_a knows",
                "confidence": 0.8,
            },
        ),
    ]
    for event in events:
        store.write_event(event)
    store.write_event(events[-1])

    bundle = store.retrieval_record_bundle("char_b")

    assert [
        len(getattr(bundle, name))
        for name in (
            "event_memories",
            "observation_memories",
            "knowledge_memories",
            "social_memories",
            "higher_order_memories",
        )
    ] == [1, 1, 1, 1, 1]
    assert bundle.higher_order_memories[0].subject_actor_id == "char_a"
    assert all(
        node.scope.owner_actor_id == "char_b"
        for node in graph.query_nodes(
            HeavenlyNodeQuery(scope=_scope("char_b"), valid_at=400, limit=None)
        )
    )


def test_repeated_source_event_reaches_graph_idempotency_replay() -> None:
    class RecordingGraph(InMemoryHeavenlyGraphAdapter):
        def __init__(self) -> None:
            super().__init__()
            self.write_results = []

        def write_batch(self, batch):
            result = super().write_batch(batch)
            self.write_results.append(result)
            return result

    graph = RecordingGraph()
    store = CharacterGraphMemoryStore(graph, scope_resolver=_scope)
    event = _event("character_perceived_event", "evt:replay", 100, {"summary": "once"})

    store.write_event(event)
    store.write_event(event)

    assert [result.applied for result in graph.write_results] == [True, False]
    assert [result.replayed for result in graph.write_results] == [False, True]


def test_backdated_shared_reference_has_anchor_at_relation_time() -> None:
    graph = InMemoryHeavenlyGraphAdapter()
    store = CharacterGraphMemoryStore(graph, scope_resolver=_scope)
    store.write_event(
        _event(
            "social_cognition_event",
            "evt:later",
            200,
            {"entity_id": "char_a"},
        )
    )

    store.write_event(
        _event(
            "higher_order_belief_event",
            "evt:earlier",
            100,
            {
                "subject_actor_id": "char_a",
                "proposition_key": "letter:destroyed",
                "meta_belief": "char_a knows",
                "confidence": 0.8,
            },
        )
    )

    assert graph.query_nodes(
        HeavenlyNodeQuery(
            scope=_scope("char_b"),
            valid_at=100,
            node_types=["actor_memory_anchor:actor"],
            limit=None,
        )
    )


def test_fallback_observation_ids_do_not_create_actor_or_object_anchors() -> None:
    graph = InMemoryHeavenlyGraphAdapter()
    store = CharacterGraphMemoryStore(graph, scope_resolver=_scope)
    store.write_event(
        _event("character_perceived_event", "evt:scene", 100, {"summary": "scene"})
    )
    store.write_event(
        _event(
            "character_perceived_event",
            "evt:candidate",
            101,
            {
                "summary": "candidate",
                "source_candidate_event_id": "candidate:letter:1",
            },
        )
    )

    assert not [
        node
        for node in graph.query_nodes(
            HeavenlyNodeQuery(scope=_scope("char_b"), valid_at=101, limit=None)
        )
        if node.node_type.startswith("actor_memory_anchor:")
    ]


def test_recall_honors_matching_branch_and_temporal_bound() -> None:
    store = CharacterGraphMemoryStore(
        InMemoryHeavenlyGraphAdapter(), scope_resolver=_scope
    )
    store.write_event(
        _event("character_perceived_event", "evt:100", 100, {"summary": "first"})
    )
    store.write_event(
        _event(
            "character_agent_dialogue_response", "evt:200", 200, {"content": "second"}
        )
    )

    at_100 = store.retrieval_record_bundle(
        "char_b", story_branch_id="branch:main", valid_at=100
    )

    assert [record.source_event_id for record in at_100.event_memories] == ["evt:100"]
    with pytest.raises(ValueError, match="story branch"):
        store.retrieval_record_bundle("char_b", story_branch_id="branch:alternate")
    assert (
        CharacterAgentMemoryStore()
        .retrieval_record_bundle(
            "char_b",
            story_branch_id="branch:alternate",
            valid_at=100,
        )
        .event_memories
        == []
    )


def test_rejects_scope_owner_mismatch() -> None:
    store = CharacterGraphMemoryStore(
        InMemoryHeavenlyGraphAdapter(),
        scope_resolver=lambda _: _scope("char_a"),
    )

    with pytest.raises(ValueError, match="owner"):
        store.write_event(
            _event(
                "character_perceived_event",
                "evt:bad-scope",
                100,
                {"summary": "blocked"},
            )
        )


def test_sqlite_restart_recalls_durable_records(tmp_path: Path) -> None:
    path = tmp_path / "character-memory.sqlite3"
    graph = SQLiteHeavenlyGraphAdapter(path)
    store = CharacterGraphMemoryStore(graph, scope_resolver=_scope)
    for event in [
        _event("character_perceived_event", "evt:restart", 100, {"summary": "durable"}),
        _event(
            "knowledge_belief_event",
            "evt:restart:knowledge",
            200,
            {
                "proposition_key": "letter:destroyed",
                "confidence": 0.9,
            },
        ),
        _event(
            "social_cognition_event",
            "evt:restart:social",
            300,
            {
                "entity_id": "char_a",
            },
        ),
        _event(
            "higher_order_belief_event",
            "evt:restart:higher",
            400,
            {
                "subject_actor_id": "char_a",
                "proposition_key": "letter:destroyed",
                "meta_belief": "char_a knows",
                "confidence": 0.8,
            },
        ),
    ]:
        store.write_event(event)
    graph.close()

    reopened = SQLiteHeavenlyGraphAdapter(path)
    try:
        restored = CharacterGraphMemoryStore(reopened, scope_resolver=_scope)
        bundle = restored.retrieval_record_bundle("char_b")
        assert bundle.event_memories[0].summary == "durable"
        assert [
            len(getattr(bundle, name))
            for name in (
                "event_memories",
                "observation_memories",
                "knowledge_memories",
                "social_memories",
                "higher_order_memories",
            )
        ] == [1, 1, 1, 1, 1]
    finally:
        reopened.close()
