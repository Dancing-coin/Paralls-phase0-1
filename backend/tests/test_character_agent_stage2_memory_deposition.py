from app.character_agent.models.knowledge_state import KnowledgeState
from app.character_agent.storage.memory_store import CharacterAgentMemoryStore


def test_settlement_result_deposits_stable_knowledge_proposition_for_environment_outcome() -> None:
    store = CharacterAgentMemoryStore()

    store.write_event(
        {
            "event_id": "evt:settlement:3001",
            "event_index": 1,
            "actor_id": "char_c",
            "event_type": "character_agent_settlement_result",
            "producer_ts": 3001,
            "payload": {
                "result_type": "environment_state_result",
                "target_environment_id": "env_lamp",
                "change_summary": "env_lamp changed from stable to alerted",
                "stable_state_summary": "environment_request accepted",
            },
        }
    )

    bundle = store.retrieval_bundle("char_c")

    assert bundle["knowledge_memories"]
    assert bundle["knowledge_memories"][0]["proposition_key"] == (
        "settlement:environment:env_lamp:environment_state_result"
    )
    assert bundle["knowledge_memories"][0]["proposition"] == (
        "environment env_lamp environment_state_result: env_lamp changed from stable to alerted"
    )
    assert bundle["knowledge_memories"][0]["state"] == KnowledgeState.BELIEVED.value
    assert bundle["knowledge_memories"][0]["source_event_id"] == "evt:settlement:3001"
    assert bundle["knowledge_memories"][0]["producer_ts"] == 3001


def test_settlement_result_uses_constraint_summary_when_depositing_knowledge() -> None:
    store = CharacterAgentMemoryStore()

    store.write_event(
        {
            "event_id": "evt:settlement:3002",
            "event_index": 2,
            "actor_id": "char_c",
            "event_type": "character_agent_settlement_result",
            "producer_ts": 3002,
            "payload": {
                "result_type": "constraint_state_result",
                "target_object_id": "obj_letter",
                "constraint_summary": "obj_letter is out of reach",
            },
        }
    )

    bundle = store.retrieval_bundle("char_c")

    assert bundle["knowledge_memories"]
    assert bundle["knowledge_memories"][0]["proposition_key"] == (
        "settlement:object:obj_letter:constraint_state_result"
    )
    assert bundle["knowledge_memories"][0]["proposition"] == (
        "object obj_letter constraint_state_result: obj_letter is out of reach"
    )
    assert bundle["knowledge_memories"][0]["state"] == KnowledgeState.NOTICED.value
    assert bundle["knowledge_memories"][0]["source_event_id"] == "evt:settlement:3002"


def test_relational_belief_event_deposits_stage2_social_memory_shape() -> None:
    store = CharacterAgentMemoryStore()

    store.write_event(
        {
            "event_id": "evt:rel:3003",
            "event_index": 3,
            "actor_id": "char_c",
            "event_type": "relational_belief_event",
            "producer_ts": 3003,
            "payload": {
                "entity_id": "char_a",
                "belief_type": "trust_level",
                "value": "guarded",
            },
        }
    )

    bundle = store.retrieval_bundle("char_c")

    assert bundle["social_memories"]
    assert bundle["social_memories"][0]["entity_id"] == "char_a"
    assert bundle["social_memories"][0]["trust_baseline"] == 0.25
    assert bundle["social_memories"][0]["suspicion_baseline"] == 0.75
    assert bundle["social_memories"][0]["source_event_id"] == "evt:rel:3003"
    assert "belief_type" not in bundle["social_memories"][0]
    assert "value" not in bundle["social_memories"][0]
