from app.character_agent.memory.relational_memory import CharacterRelationalMemory


def test_relational_memory_upserts_belief_by_actor_and_entity() -> None:
    memory = CharacterRelationalMemory()

    entry = memory.upsert_belief(
        actor_id="char_c",
        entity_id="char_a",
        belief_type="trust_level",
        value="uncertain",
        source_event_id="evt:1002",
        producer_ts=1002,
    )

    assert entry["actor_id"] == "char_c"
    assert entry["entity_id"] == "char_a"
    assert entry["belief_type"] == "trust_level"
    assert entry["value"] == "uncertain"

    beliefs = memory.recall("char_c")

    assert len(beliefs) == 1
    assert beliefs[0]["entity_id"] == "char_a"


def test_relational_memory_replaces_matching_belief_slot() -> None:
    memory = CharacterRelationalMemory()

    memory.upsert_belief("char_c", "char_a", "trust_level", "uncertain", "evt:1002", 1002)
    memory.upsert_belief("char_c", "char_a", "trust_level", "guarded", "evt:1003", 1003)

    beliefs = memory.recall("char_c")

    assert len(beliefs) == 1
    assert beliefs[0]["value"] == "guarded"
    assert beliefs[0]["source_event_id"] == "evt:1003"
