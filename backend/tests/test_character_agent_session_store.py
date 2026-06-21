from pathlib import Path

from app.character_agent.storage.session_store import CharacterAgentSessionStore


def test_session_store_appends_and_lists_events_per_actor() -> None:
    store = CharacterAgentSessionStore()

    event = store.append_event(
        actor_id="char_c",
        event_type="character_perceived_event",
        producer_ts=1001,
        payload={"percept_channel": "auditory", "summary": "speaker_active"},
    )

    assert event["actor_id"] == "char_c"
    assert event["event_type"] == "character_perceived_event"
    assert event["producer_ts"] == 1001
    assert event["payload"]["percept_channel"] == "auditory"
    assert event["event_index"] == 1

    events = store.list_events("char_c")

    assert len(events) == 1
    assert events[0]["event_index"] == 1
    assert store.list_events("char_a") == []


def test_session_store_keeps_actor_timelines_isolated() -> None:
    store = CharacterAgentSessionStore()

    store.append_event("char_a", "character_perceived_event", 1002, {"summary": "a"})
    store.append_event("char_b", "character_perceived_event", 1003, {"summary": "b"})

    assert [event["actor_id"] for event in store.list_events("char_a")] == ["char_a"]
    assert [event["actor_id"] for event in store.list_events("char_b")] == ["char_b"]


def test_session_store_persists_and_recovers_actor_timelines(tmp_path: Path) -> None:
    store = CharacterAgentSessionStore(storage_root=tmp_path)

    store.append_event("char_c", "character_perceived_event", 1004, {"summary": "persisted"})
    reloaded = CharacterAgentSessionStore(storage_root=tmp_path)

    events = reloaded.list_events("char_c")

    assert events
    assert events[0]["payload"]["summary"] == "persisted"
    assert (tmp_path / "character_agent_session_store.json").exists()
