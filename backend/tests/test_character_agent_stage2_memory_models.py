from app.character_agent.memory.event_memory import CharacterEventMemory
from app.character_agent.memory.higher_order_memory import CharacterHigherOrderMemory
from app.character_agent.memory.knowledge_memory import CharacterKnowledgeMemory
from app.character_agent.memory.observation_memory import CharacterObservationMemory
from app.character_agent.memory.social_memory import CharacterSocialMemory
from app.character_agent.models.event_memory import CharacterEventMemoryRecord
from app.character_agent.models.knowledge_memory import CharacterKnowledgeMemoryRecord
from app.character_agent.models.observation_memory import CharacterObservationMemoryRecord
from app.character_agent.models.social_memory import CharacterSocialMemoryRecord
from app.character_agent.models.knowledge_state import KnowledgeState


def test_knowledge_memory_upserts_proposition_record() -> None:
    memory = CharacterKnowledgeMemory()

    entry = memory.upsert_proposition(
        actor_id="char_c",
        proposition_key="prop:1",
        proposition="char_a may be nearby",
        state=KnowledgeState.SUSPECTED,
        confidence=0.35,
        source_event_id="evt:2001",
        producer_ts=2001,
    )

    assert entry["actor_id"] == "char_c"
    assert entry["proposition_key"] == "prop:1"
    assert entry["proposition"] == "char_a may be nearby"
    assert entry["state"] == "suspected"
    assert entry["confidence"] == 0.35
    assert memory.recall("char_c")[0]["state"] == "suspected"


def test_knowledge_memory_upsert_replaces_existing_slot() -> None:
    memory = CharacterKnowledgeMemory()

    memory.upsert_proposition(
        actor_id="char_c",
        proposition_key="prop:1",
        proposition="char_a may be nearby",
        state=KnowledgeState.SUSPECTED,
        confidence=0.35,
        source_event_id="evt:2001",
        producer_ts=2001,
    )
    memory.upsert_proposition(
        actor_id="char_c",
        proposition_key="prop:1",
        proposition="char_a is nearby",
        state=KnowledgeState.BELIEVED,
        confidence=0.8,
        source_event_id="evt:2005",
        producer_ts=2005,
    )

    recalled = memory.recall("char_c")
    assert len(recalled) == 1
    assert recalled[0]["proposition"] == "char_a is nearby"
    assert recalled[0]["state"] == "believed"


def test_event_memory_records_world_event_fields() -> None:
    memory = CharacterEventMemory()

    entry = memory.record_event(
        actor_id="char_c",
        source_event_id="evt:2002",
        world_ts=2002,
        event_type="door_opened",
        summary="the nearby door opened",
        clarity_score=0.8,
        certainty_score=0.9,
        refs=["door:1"],
    )

    assert entry["source_event_id"] == "evt:2002"
    assert entry["world_ts"] == 2002
    assert entry["summary"] == "the nearby door opened"
    assert entry["clarity_score"] == 0.8
    assert entry["certainty_score"] == 0.9
    assert entry["refs"] == ["door:1"]


def test_event_memory_generates_unique_memory_ids_for_same_source_event() -> None:
    memory = CharacterEventMemory()

    first = memory.record_event(
        actor_id="char_c",
        source_event_id="evt:2002",
        world_ts=2002,
        event_type="door_opened",
        summary="the nearby door opened",
        clarity_score=0.8,
        certainty_score=0.9,
        refs=["door:1"],
        event_id="evt:2002:a",
    )
    second = memory.record_event(
        actor_id="char_c",
        source_event_id="evt:2002",
        world_ts=2002,
        event_type="door_opened",
        summary="the nearby door opened again",
        clarity_score=0.7,
        certainty_score=0.85,
        refs=["door:1"],
        event_id="evt:2002:b",
    )

    assert first["memory_id"] != second["memory_id"]


def test_observation_memory_records_perceived_version_with_distortion_fields() -> None:
    memory = CharacterObservationMemory()

    entry = memory.record_observation(
        actor_id="char_c",
        source_event_id="evt:2003",
        world_ts=2003,
        observed_entity_id="char_a",
        observation_type="character_perceived_event",
        observation_summary="saw char_a speaking",
        clarity_score=0.4,
        certainty_score=0.55,
        distortion_tags=["occluded", "noisy"],
        refs=["char_a", "scene:main"],
    )

    assert entry["observed_entity_id"] == "char_a"
    assert entry["observation_type"] == "character_perceived_event"
    assert entry["observation_summary"] == "saw char_a speaking"
    assert entry["clarity_score"] == 0.4
    assert entry["distortion_tags"] == ["occluded", "noisy"]
    assert entry["refs"] == ["char_a", "scene:main"]
    assert "distortion_tags" in memory.recall("char_c")[0]


def test_observation_memory_generates_unique_memory_ids_for_same_source_event() -> None:
    memory = CharacterObservationMemory()

    first = memory.record_observation(
        actor_id="char_c",
        source_event_id="evt:2003",
        world_ts=2003,
        observed_entity_id="char_a",
        observation_type="character_perceived_event",
        observation_summary="saw char_a speaking",
        clarity_score=0.4,
        certainty_score=0.55,
        distortion_tags=["occluded", "noisy"],
        refs=["char_a", "scene:main"],
    )
    second = memory.record_observation(
        actor_id="char_c",
        source_event_id="evt:2003",
        world_ts=2003,
        observed_entity_id="char_a",
        observation_type="character_perceived_event",
        observation_summary="saw char_a speaking again",
        clarity_score=0.45,
        certainty_score=0.6,
        distortion_tags=["occluded"],
        refs=["char_a", "scene:main"],
    )

    assert first["memory_id"] != second["memory_id"]


def test_social_memory_records_stage2_semantics_with_entity_id() -> None:
    memory = CharacterSocialMemory()

    entry = memory.upsert_relation(
        actor_id="char_c",
        entity_id="char_a",
        trust_baseline=0.7,
        suspicion_baseline=0.2,
        intimacy=0.4,
        dependency=0.1,
        unresolved_tension=0.0,
        shared_secret_refs=["secret:1"],
        source_event_id="evt:2004",
        producer_ts=2004,
    )

    assert entry["entity_id"] == "char_a"
    assert entry["trust_baseline"] == 0.7
    assert entry["shared_secret_refs"] == ["secret:1"]
    assert memory.recall("char_c")[0]["entity_id"] == "char_a"


def test_stage2_memory_components_expose_typed_record_views() -> None:
    event_memory = CharacterEventMemory()
    observation_memory = CharacterObservationMemory()
    knowledge_memory = CharacterKnowledgeMemory()
    social_memory = CharacterSocialMemory()

    event_memory.record_event(
        actor_id="char_c",
        source_event_id="evt:2002",
        world_ts=2002,
        event_type="door_opened",
        summary="the nearby door opened",
        clarity_score=0.8,
        certainty_score=0.9,
        refs=["door:1"],
    )
    observation_memory.record_observation(
        actor_id="char_c",
        source_event_id="evt:2003",
        world_ts=2003,
        observed_entity_id="char_a",
        observation_type="character_perceived_event",
        observation_summary="saw char_a speaking",
        clarity_score=0.4,
        certainty_score=0.55,
        distortion_tags=["occluded"],
        refs=["char_a"],
    )
    knowledge_memory.upsert_proposition(
        actor_id="char_c",
        proposition_key="prop:1",
        proposition="char_a may be nearby",
        state=KnowledgeState.SUSPECTED,
        confidence=0.35,
        source_event_id="evt:2001",
        producer_ts=2001,
    )
    social_memory.upsert_relation(
        actor_id="char_c",
        entity_id="char_a",
        trust_baseline=0.7,
        suspicion_baseline=0.2,
        intimacy=0.4,
        dependency=0.1,
        unresolved_tension=0.0,
        shared_secret_refs=["secret:1"],
        source_event_id="evt:2004",
        producer_ts=2004,
    )

    event_record = event_memory.recall_records("char_c")[0]
    observation_record = observation_memory.recall_records("char_c")[0]
    knowledge_record = knowledge_memory.recall_records("char_c")[0]
    social_record = social_memory.recall_records("char_c")[0]

    assert isinstance(event_record, CharacterEventMemoryRecord)
    assert isinstance(observation_record, CharacterObservationMemoryRecord)
    assert isinstance(knowledge_record, CharacterKnowledgeMemoryRecord)
    assert isinstance(social_record, CharacterSocialMemoryRecord)


def test_higher_order_memory_upsert_replaces_existing_subject_and_proposition_slot() -> None:
    memory = CharacterHigherOrderMemory()

    memory.upsert_meta_belief(
        actor_id="char_c",
        subject_actor_id="char_a",
        proposition_key="obj_letter:is_sensitive",
        meta_belief="char_a suspects char_c knows more",
        confidence=0.55,
        source_event_id="evt:3001",
        producer_ts=3001,
    )
    memory.upsert_meta_belief(
        actor_id="char_c",
        subject_actor_id="char_a",
        proposition_key="obj_letter:is_sensitive",
        meta_belief="char_a is nearly certain char_c knows more",
        confidence=0.82,
        source_event_id="evt:3002",
        producer_ts=3002,
    )

    recalled = memory.recall("char_c")

    assert len(recalled) == 1
    assert recalled[0]["meta_belief"] == "char_a is nearly certain char_c knows more"
    assert recalled[0]["confidence"] == 0.82


def test_recall_returns_isolated_copies() -> None:
    event_memory = CharacterEventMemory()
    event_memory.record_event(
        actor_id="char_c",
        source_event_id="evt:2002",
        world_ts=2002,
        event_type="door_opened",
        summary="the nearby door opened",
        clarity_score=0.8,
        certainty_score=0.9,
        refs=["door:1"],
    )
    event_recalled = event_memory.recall("char_c")
    event_recalled[0]["refs"].append("mutated")
    assert event_memory.recall("char_c")[0]["refs"] == ["door:1"]

    observation_memory = CharacterObservationMemory()
    observation_memory.record_observation(
        actor_id="char_c",
        source_event_id="evt:2003",
        world_ts=2003,
        observed_entity_id="char_a",
        observation_type="character_perceived_event",
        observation_summary="saw char_a speaking",
        clarity_score=0.4,
        certainty_score=0.55,
        distortion_tags=["occluded", "noisy"],
        refs=["char_a", "scene:main"],
    )
    observation_recalled = observation_memory.recall("char_c")
    observation_recalled[0]["distortion_tags"].append("mutated")
    assert observation_memory.recall("char_c")[0]["distortion_tags"] == ["occluded", "noisy"]

    knowledge_memory = CharacterKnowledgeMemory()
    knowledge_memory.upsert_proposition(
        actor_id="char_c",
        proposition_key="prop:1",
        proposition="char_a may be nearby",
        state=KnowledgeState.SUSPECTED,
        confidence=0.35,
        source_event_id="evt:2001",
        producer_ts=2001,
    )
    knowledge_recalled = knowledge_memory.recall("char_c")
    knowledge_recalled[0]["proposition"] = "mutated"
    assert knowledge_memory.recall("char_c")[0]["proposition"] == "char_a may be nearby"

    social_memory = CharacterSocialMemory()
    social_memory.upsert_relation(
        actor_id="char_c",
        entity_id="char_a",
        trust_baseline=0.7,
        suspicion_baseline=0.2,
        intimacy=0.4,
        dependency=0.1,
        unresolved_tension=0.0,
        shared_secret_refs=["secret:1"],
        source_event_id="evt:2004",
        producer_ts=2004,
    )
    social_recalled = social_memory.recall("char_c")
    social_recalled[0]["shared_secret_refs"].append("mutated")
    assert social_memory.recall("char_c")[0]["shared_secret_refs"] == ["secret:1"]
