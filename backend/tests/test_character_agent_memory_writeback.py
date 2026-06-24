from pathlib import Path

from app.character_agent.storage.memory_store import CharacterAgentMemoryStore


def test_memory_store_writes_timeline_event_into_working_and_episodic_layers() -> None:
    store = CharacterAgentMemoryStore()

    event = {
        "event_id": "evt:2001",
        "event_index": 1,
        "actor_id": "char_c",
        "event_type": "character_perceived_event",
        "producer_ts": 2001,
        "payload": {
            "summary": "char_a spoke nearby",
            "tags": ["auditory", "social"],
        },
    }

    store.write_event(event)
    bundle = store.retrieval_bundle("char_c")

    assert bundle["working_memory"]
    assert bundle["working_memory"][0]["event_id"] == "evt:2001"
    assert set(bundle.keys()) == {
        "working_memory",
        "event_memories",
        "observation_memories",
        "knowledge_memories",
        "social_memories",
        "episodic_memories",
        "relational_memories",
    }
    assert bundle["event_memories"]
    assert bundle["event_memories"][0]["summary"] == "char_a spoke nearby"
    assert bundle["observation_memories"]
    assert bundle["observation_memories"][0]["observation_summary"] == "char_a spoke nearby"
    assert bundle["episodic_memories"]
    assert bundle["episodic_memories"][0]["summary"] == "char_a spoke nearby"
    assert bundle["episodic_memories"][0]["source_event_id"] == "evt:2001"
    assert bundle["episodic_memories"][0]["producer_ts"] == 2001
    assert bundle["episodic_memories"][0]["tags"] == []


def test_memory_store_writes_relational_belief_events_into_relational_layer() -> None:
    store = CharacterAgentMemoryStore()

    event = {
        "event_id": "evt:2002",
        "event_index": 2,
        "actor_id": "char_c",
        "event_type": "relational_belief_event",
        "producer_ts": 2002,
        "payload": {
            "entity_id": "char_a",
            "belief_type": "trust_level",
            "value": "guarded",
        },
    }

    store.write_event(event)
    bundle = store.retrieval_bundle("char_c")

    assert bundle["social_memories"]
    assert bundle["social_memories"][0]["entity_id"] == "char_a"
    assert bundle["social_memories"][0]["trust_baseline"] == 0.25


def test_memory_store_preserves_relational_belief_type_and_source_lineage() -> None:
    store = CharacterAgentMemoryStore()

    event = {
        "event_id": "evt:2002b",
        "event_index": 2,
        "actor_id": "char_c",
        "event_type": "relational_belief_event",
        "producer_ts": 2003,
        "payload": {
            "entity_id": "char_a",
            "belief_type": "trust_level",
            "value": "guarded",
        },
    }

    store.write_event(event)
    bundle = store.retrieval_bundle("char_c")

    assert bundle["knowledge_memories"]
    assert bundle["knowledge_memories"][0]["proposition_key"] == "social:char_a:trust_level"
    assert bundle["knowledge_memories"][0]["proposition"] == "char_a:trust_level=guarded"
    assert bundle["knowledge_memories"][0]["source_event_id"] == "evt:2002b"


def test_memory_store_derives_legacy_relational_memories_from_stage2_knowledge_pool() -> None:
    store = CharacterAgentMemoryStore()

    event = {
        "event_id": "evt:2002d",
        "event_index": 4,
        "actor_id": "char_c",
        "event_type": "relational_belief_event",
        "producer_ts": 2005,
        "payload": {
            "entity_id": "char_a",
            "belief_type": "trust_level",
            "value": "guarded",
        },
    }

    store.write_event(event)
    bundle = store.retrieval_bundle("char_c")

    assert bundle["relational_memories"]
    assert bundle["relational_memories"][0]["entity_id"] == "char_a"
    assert bundle["relational_memories"][0]["belief_type"] == "trust_level"
    assert bundle["relational_memories"][0]["value"] == "guarded"
    assert bundle["relational_memories"][0]["source_event_id"] == "evt:2002d"
    assert bundle["relational_memories"][0]["producer_ts"] == 2005


def test_memory_store_does_not_project_unknown_relational_belief_types_into_social_memory() -> None:
    store = CharacterAgentMemoryStore()

    event = {
        "event_id": "evt:2002c",
        "event_index": 3,
        "actor_id": "char_c",
        "event_type": "relational_belief_event",
        "producer_ts": 2004,
        "payload": {
            "entity_id": "char_a",
            "belief_type": "secret_knowledge",
            "value": "knows_about_letter",
        },
    }

    store.write_event(event)
    bundle = store.retrieval_bundle("char_c")

    assert bundle["knowledge_memories"]
    assert bundle["knowledge_memories"][0]["proposition_key"] == "social:char_a:secret_knowledge"
    assert bundle["social_memories"] == []


def test_memory_store_persists_and_recovers_retrieval_bundle(tmp_path: Path) -> None:
    store = CharacterAgentMemoryStore(storage_root=tmp_path)

    event = {
        "event_id": "evt:2003",
        "event_index": 3,
        "actor_id": "char_c",
        "event_type": "character_agent_settlement_result",
        "producer_ts": 2003,
        "payload": {
            "result_type": "action_resolution_result",
        },
    }

    store.write_event(event)
    reloaded = CharacterAgentMemoryStore(storage_root=tmp_path)
    bundle = reloaded.retrieval_bundle("char_c")

    assert bundle["working_memory"]
    assert bundle["event_memories"]
    assert bundle["event_memories"][0]["summary"] == "action_resolution_result"
    assert (tmp_path / "character_agent_memory_store.json").exists()


def test_memory_store_uses_settlement_change_summary_for_episodic_memory_when_present() -> None:
    store = CharacterAgentMemoryStore()

    event = {
        "event_id": "evt:2003b",
        "event_index": 3,
        "actor_id": "char_c",
        "event_type": "character_agent_settlement_result",
        "producer_ts": 2003,
        "payload": {
            "result_type": "action_resolution_result",
            "change_summary": "moved closer to target",
        },
    }

    store.write_event(event)
    bundle = store.retrieval_bundle("char_c")

    assert bundle["event_memories"]
    assert bundle["event_memories"][0]["summary"] == "moved closer to target"


def test_memory_store_uses_dialogue_content_for_episodic_memory_when_present() -> None:
    store = CharacterAgentMemoryStore()

    event = {
        "event_id": "evt:2003c",
        "event_index": 4,
        "actor_id": "char_c",
        "event_type": "character_agent_dialogue_response",
        "producer_ts": 2004,
        "payload": {
            "output_type": "dialogue_response",
            "content": "I will keep watch.",
        },
    }

    store.write_event(event)
    bundle = store.retrieval_bundle("char_c")

    assert bundle["event_memories"]
    assert bundle["event_memories"][0]["summary"] == "dialogue_response:I will keep watch."


def test_memory_store_sanitizes_large_reasoning_request_before_working_memory_writeback() -> None:
    store = CharacterAgentMemoryStore()
    large_text = "auditory_fact/speaker_active|" * 4000

    event = {
        "event_id": "evt:2004",
        "event_index": 4,
        "actor_id": "char_c",
        "event_type": "l2_reasoning_request",
        "producer_ts": 2004,
        "payload": {
            "task_kind": "l2_reasoning",
            "context": {
                "actor_id": "char_c",
                "control_mode": "player_priority_assisted",
                "snapshot": {"visible_entities": [large_text]},
                "memory": {"working_memory": [{"summary": large_text}]},
                "event": {"perceived_summary": large_text},
            },
        },
    }

    store.write_event(event)
    bundle = store.retrieval_bundle("char_c")

    stored = bundle["working_memory"][0]
    assert stored["event_type"] == "l2_reasoning_request"
    assert "snapshot_summary" in stored["payload"]
    assert "memory_summary" in stored["payload"]
    assert "event_summary" in stored["payload"]
    assert "context" not in stored["payload"]


def test_memory_store_can_build_objectized_working_memory_state() -> None:
    store = CharacterAgentMemoryStore()

    store.write_event(
        {
            "event_id": "evt:2101",
            "event_index": 1,
            "actor_id": "char_c",
            "event_type": "character_perceived_event",
            "producer_ts": 2101,
            "payload": {"summary": "char_a spoke nearby"},
        }
    )
    store.write_event(
        {
            "event_id": "evt:2102",
            "event_index": 2,
            "actor_id": "char_c",
            "event_type": "character_agent_settlement_result",
            "producer_ts": 2102,
            "payload": {"result_type": "action_resolution_result"},
        }
    )
    store.write_event(
        {
            "event_id": "evt:2103",
            "event_index": 3,
            "actor_id": "char_c",
            "event_type": "siming_output_event",
            "producer_ts": 2103,
            "payload": {"summary": "watch obj_letter"},
        }
    )

    state = store.working_memory_state("char_c", private_snapshot={"actor_id": "char_c"})

    assert state.recent_perceived_events
    assert state.recent_perceived_events[0]["event_type"] == "character_perceived_event"
    assert state.recent_esm_results
    assert state.recent_esm_results[0]["event_type"] == "character_agent_settlement_result"
    assert state.recent_siming_catalysts
    assert state.recent_siming_catalysts[0]["event_type"] == "siming_output_event"
    assert state.private_snapshot["actor_id"] == "char_c"
    state_dict = state.model_dump()
    assert "event_memories" not in state_dict
    assert "observation_memories" not in state_dict
    assert "knowledge_memories" not in state_dict
    assert "social_memories" not in state_dict


def test_memory_store_working_memory_recall_returns_deep_copied_payloads() -> None:
    store = CharacterAgentMemoryStore()
    store.write_event(
        {
            "event_id": "evt:2201",
            "event_index": 1,
            "actor_id": "char_c",
            "event_type": "character_perceived_event",
            "producer_ts": 2201,
            "payload": {"summary": "char_a spoke nearby", "nested": {"tone": "guarded"}},
        }
    )

    bundle = store.retrieval_bundle("char_c")
    bundle["working_memory"][0]["payload"]["nested"]["tone"] = "mutated"

    fresh_bundle = store.retrieval_bundle("char_c")

    assert fresh_bundle["working_memory"][0]["payload"]["nested"]["tone"] == "guarded"


def test_memory_store_working_memory_state_returns_deep_copied_private_snapshot() -> None:
    store = CharacterAgentMemoryStore()
    snapshot = {"actor_id": "char_c", "nested": {"focus": "obj_letter"}}

    state = store.working_memory_state("char_c", private_snapshot=snapshot)
    state.private_snapshot["nested"]["focus"] = "mutated"
    state_dump = state.model_dump()
    state_dump["private_snapshot"]["nested"]["focus"] = "mutated-again"

    fresh_state = store.working_memory_state("char_c", private_snapshot=snapshot)

    assert snapshot["nested"]["focus"] == "obj_letter"
    assert fresh_state.private_snapshot["nested"]["focus"] == "obj_letter"


def test_memory_store_write_event_deep_copies_input_event_payload() -> None:
    store = CharacterAgentMemoryStore()
    event = {
        "event_id": "evt:2301",
        "event_index": 1,
        "actor_id": "char_c",
        "event_type": "character_perceived_event",
        "producer_ts": 2301,
        "payload": {
            "summary": "char_a spoke nearby",
            "nested": {"tone": "guarded"},
        },
    }

    store.write_event(event)
    event["payload"]["nested"]["tone"] = "mutated-after-write"

    bundle = store.retrieval_bundle("char_c")

    assert bundle["working_memory"][0]["payload"]["nested"]["tone"] == "guarded"
