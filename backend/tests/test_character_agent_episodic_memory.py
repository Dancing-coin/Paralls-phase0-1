from app.character_agent.memory.episodic_memory import CharacterEpisodicMemory


def test_episodic_memory_remembers_structured_episode() -> None:
    memory = CharacterEpisodicMemory()

    entry = memory.remember(
        actor_id="char_c",
        summary="char_a spoke nearby",
        tags=["auditory", "social"],
        source_event_id="evt:1001",
        producer_ts=1001,
    )

    assert entry["actor_id"] == "char_c"
    assert entry["summary"] == "char_a spoke nearby"
    assert entry["tags"] == ["auditory", "social"]
    assert entry["source_event_id"] == "evt:1001"

    entries = memory.recall("char_c")

    assert len(entries) == 1
    assert entries[0]["summary"] == "char_a spoke nearby"
