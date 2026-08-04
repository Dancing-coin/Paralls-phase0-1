from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.character_agent.storage.graph_memory_store import CharacterGraphMemoryStore
from app.character_agent.storage.memory_store import CharacterAgentMemoryStore
from app.character_agent.storage.memory_store_router import CharacterMemoryStoreRouter
from app.models.character_perceived import CharacterPerceivedEvent
from app.models.siming_heavenly_graph import HeavenlyGraphScope
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter


def _scope(actor_id: str) -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:demo",
        session_id="session:demo",
        story_branch_id="branch:main",
        graph_namespace="actor_private",
        owner_actor_id=actor_id,
    )


def _perceived_event(actor_id: str) -> dict[str, object]:
    return {
        "event_id": f"evt:{actor_id}:letter",
        "event_index": 100,
        "actor_id": actor_id,
        "event_type": "character_perceived_event",
        "producer_ts": 100,
        "payload": {
            "summary": "letter removed",
            "target_actor_id": "obj_letter",
            "percept_channel": "visual",
        },
    }


def _router() -> tuple[CharacterMemoryStoreRouter, CharacterAgentMemoryStore, CharacterGraphMemoryStore]:
    light = CharacterAgentMemoryStore()
    graph = CharacterGraphMemoryStore(
        InMemoryHeavenlyGraphAdapter(),
        scope_resolver=_scope,
    )
    return (
        CharacterMemoryStoreRouter(
            light_store=light,
            graph_store=graph,
            heavy_actor_ids=frozenset({"char_b"}),
        ),
        light,
        graph,
    )


def test_router_sends_only_char_b_to_graph() -> None:
    router, light, graph = _router()

    router.write_event(_perceived_event("char_b"))
    router.write_event(_perceived_event("char_a"))

    assert graph.retrieval_record_bundle("char_b").event_memories
    assert not graph.retrieval_record_bundle("char_a").event_memories
    assert light.retrieval_record_bundle("char_a").event_memories


def test_runtime_uses_injected_router() -> None:
    router, _, graph = _router()
    runtime = CharacterAgentRuntime(memory_store=router)

    runtime.ingest_character_perceived_event(
        CharacterPerceivedEvent(
            actor_id="char_b",
            percept_channel="visual",
            producer_ts=100,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="letter removed",
            source_candidate_event_id="evt:char_b:letter",
            target_object_id="obj_letter",
            clarity_score=1.0,
            certainty_score=1.0,
        )
    )

    assert runtime.get_memory_record_bundle("char_b").observation_memories
    assert graph.retrieval_record_bundle("char_b").observation_memories
