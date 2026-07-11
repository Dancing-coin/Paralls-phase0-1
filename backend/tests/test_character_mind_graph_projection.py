from app.character_agent.mind.frame_builder import CharacterMindFrameBuilder
from app.character_agent.mind.graph_projection import (
    GraphMemoryProjectionProvider,
    NoopGraphMemoryProjectionProvider,
)


class FakeGraphProjectionProvider(GraphMemoryProjectionProvider):
    def project_memory_context(
        self,
        *,
        actor_id: str,
        memory_bundle: dict[str, object],
    ) -> dict[str, object]:
        return {
            "knowledge_context": {
                "summary": "B is a medic",
                "source_refs": ["knowledge_graph:node:b_medic"],
            },
            "relationship_context": {
                "summary": "char_a trusts char_b through social memory evidence",
                "top_target": "char_b",
                "source_refs": ["social_graph:edge:char_a:char_b"],
            },
            "higher_order_belief": {
                "summary": "A suspects B is protecting a child",
                "source_refs": ["higher_order_graph:belief:b_motive"],
            },
        }


class MutatingGraphProjectionProvider(GraphMemoryProjectionProvider):
    def project_memory_context(
        self,
        *,
        actor_id: str,
        memory_bundle: dict[str, object],
    ) -> dict[str, object]:
        knowledge_memories = memory_bundle.setdefault("knowledge_memories", [])
        social_memories = memory_bundle.setdefault("social_memories", [])
        higher_order_memories = memory_bundle.setdefault("higher_order_memories", [])
        if isinstance(knowledge_memories, list):
            knowledge_memories.append({"memory_id": "knowledge:mutated", "proposition": "mutated"})
        if isinstance(social_memories, list):
            social_memories.append({"memory_id": "social:mutated", "entity_id": "char_z"})
        if isinstance(higher_order_memories, list):
            higher_order_memories.append(
                {
                    "memory_id": "higher:mutated",
                    "subject_actor_id": "char_z",
                    "proposition_key": "mutated_belief",
                    "meta_belief": "mutated",
                }
            )
        return {}


def test_noop_graph_provider_returns_empty_projection() -> None:
    assert NoopGraphMemoryProjectionProvider().project_memory_context(
        actor_id="char_a",
        memory_bundle={},
    ) == {}


def test_graph_projection_enriches_memory_cards_without_becoming_authority() -> None:
    frame = CharacterMindFrameBuilder(
        graph_projection_provider=FakeGraphProjectionProvider(),
    ).build_frame(
        actor_id="char_a",
        producer_ts=1,
        memory_bundle={
            "knowledge_memories": [{"memory_id": "knowledge:1", "proposition": "B is a medic"}],
            "social_memories": [{"memory_id": "social:1", "entity_id": "char_b"}],
            "higher_order_memories": [
                {
                    "memory_id": "higher:1",
                    "subject_actor_id": "char_b",
                    "proposition_key": "b_motive",
                    "meta_belief": "B may be protecting a child",
                }
            ],
        },
    )

    cards = {card.factor_type: card for card in frame.memory_evidence.cards}

    assert cards["knowledge_context"].payload["graph_projection"]["summary"] == "B is a medic"
    assert cards["relationship_context"].payload["graph_projection"]["top_target"] == "char_b"
    assert cards["higher_order_belief"].payload["graph_projection"]["summary"].startswith(
        "A suspects"
    )
    assert cards["relationship_context"].scope == "actor_private"
    assert "social_graph:edge:char_a:char_b" in cards["relationship_context"].source_refs
    assert "cognition_owner" not in cards["relationship_context"].payload


def test_graph_provider_mutation_does_not_change_authoritative_memory_counts_or_refs() -> None:
    frame = CharacterMindFrameBuilder(
        graph_projection_provider=MutatingGraphProjectionProvider(),
    ).build_frame(
        actor_id="char_a",
        producer_ts=1,
        memory_bundle={
            "knowledge_memories": [{"memory_id": "knowledge:1", "proposition": "B is a medic"}],
            "social_memories": [{"memory_id": "social:1", "entity_id": "char_b"}],
            "higher_order_memories": [
                {
                    "memory_id": "higher:1",
                    "subject_actor_id": "char_b",
                    "proposition_key": "b_motive",
                    "meta_belief": "B may be protecting a child",
                }
            ],
        },
    )

    cards = {card.factor_type: card for card in frame.memory_evidence.cards}

    assert frame.memory_evidence.summary["knowledge_memory_count"] == 1
    assert frame.memory_evidence.summary["social_memory_count"] == 1
    assert frame.memory_evidence.summary["higher_order_memory_count"] == 1
    assert cards["knowledge_context"].source_refs == ["knowledge_memory:knowledge:1"]
    assert cards["relationship_context"].source_refs == ["social_memory:char_a:char_b"]
    assert cards["higher_order_belief"].source_refs == ["higher_order_memory:higher:1"]
    assert "knowledge_memory:knowledge:mutated" not in frame.provenance.source_refs
    assert "social_memory:char_a:char_z" not in frame.provenance.source_refs
    assert "higher_order_memory:higher:mutated" not in frame.provenance.source_refs


def test_graph_projection_does_not_create_memory_truth_without_owned_memory_support() -> None:
    frame = CharacterMindFrameBuilder(
        graph_projection_provider=FakeGraphProjectionProvider(),
    ).build_frame(
        actor_id="char_a",
        producer_ts=1,
        memory_bundle={},
    )

    cards = {card.factor_type: card for card in frame.memory_evidence.cards}

    assert "graph_projection" not in cards["knowledge_context"].payload
    assert "graph_projection" not in cards["relationship_context"].payload
    assert "graph_projection" not in cards["higher_order_belief"].payload
    assert "knowledge_graph:node:b_medic" not in cards["knowledge_context"].source_refs
    assert "social_graph:edge:char_a:char_b" not in cards["relationship_context"].source_refs
    assert "higher_order_graph:belief:b_motive" not in cards["higher_order_belief"].source_refs
