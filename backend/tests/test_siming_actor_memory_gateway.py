import pytest
from pydantic import ValidationError

from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.character_agent.storage.graph_memory_store import CharacterGraphMemoryStore
from app.character_agent.storage.memory_store import CharacterAgentMemoryStore
from app.character_agent.storage.memory_store_router import CharacterMemoryStoreRouter
from app.models.siming_actor_memory_read import ActorMemoryReadRequest, ActorMemoryRevisionVector
from app.models.siming_heavenly_graph import HeavenlyGraphScope
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.services.siming_actor_memory_gateway import ActorMemoryReadGateway


def _scope(actor_id: str) -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:demo",
        session_id="session:demo",
        story_branch_id="branch:main",
        graph_namespace="actor_private",
        owner_actor_id=actor_id,
    )


def _runtime() -> CharacterAgentRuntime:
    graph = CharacterGraphMemoryStore(
        InMemoryHeavenlyGraphAdapter(), scope_resolver=_scope
    )
    router = CharacterMemoryStoreRouter(
        light_store=CharacterAgentMemoryStore(),
        graph_store=graph,
        heavy_actor_ids=frozenset({"char_b"}),
    )
    router.write_event(
        {
            "event_id": "authority:letter:destroyed",
            "event_index": 100,
            "actor_id": "char_b",
            "event_type": "character_perceived_event",
            "producer_ts": 100,
            "payload": {
                "summary": "letter destroyed",
                "target_actor_id": "obj_letter",
                "percept_channel": "visual",
            },
        }
    )
    return CharacterAgentRuntime(memory_store=router)


def test_gateway_returns_observation_with_revision_vector() -> None:
    gateway = ActorMemoryReadGateway(_runtime())

    result = gateway.read(
        ActorMemoryReadRequest(
            actor_id="char_b", story_branch_id="branch:main", valid_at=100
        )
    )

    assert result.completeness == "complete"
    assert result.bundle.observation_memories[0].observed_entity_id == "obj_letter"
    assert result.revision_vector.observation


def test_revision_mismatch_is_incomplete_not_ignorance() -> None:
    gateway = ActorMemoryReadGateway(_runtime())

    result = gateway.read(
        ActorMemoryReadRequest(
            actor_id="char_b",
            story_branch_id="branch:main",
            valid_at=100,
            expected_revision_vector=ActorMemoryRevisionVector(observation="stale"),
        )
    )

    assert result.completeness == "memory_surface_incomplete"
    assert result.reason == "revision_vector_mismatch"
    assert not hasattr(gateway, "write")


def test_missing_actor_surface_is_complete_empty_bundle() -> None:
    gateway = ActorMemoryReadGateway(_runtime())

    result = gateway.read(
        ActorMemoryReadRequest(
            actor_id="char_b", story_branch_id="branch:main", valid_at=1
        )
    )

    assert result.completeness == "complete"
    assert result.bundle.event_memories == []


def test_request_rejects_private_artifacts() -> None:
    with pytest.raises(ValidationError):
        ActorMemoryReadRequest(
            actor_id="char_b",
            story_branch_id="branch:main",
            valid_at=100,
            raw_patch="private",
        )
