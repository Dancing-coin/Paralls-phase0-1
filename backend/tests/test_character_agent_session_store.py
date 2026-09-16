import json
import shutil
from pathlib import Path

import pytest

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


def test_independent_runtime_session_stores_generate_distinct_event_ids() -> None:
    first_runtime = CharacterAgentSessionStore()
    second_runtime = CharacterAgentSessionStore()

    first = first_runtime.append_event(
        "char_b", "character_perceived_event", 1005, {"summary": "first"}
    )
    second = second_runtime.append_event(
        "char_b", "character_perceived_event", 1005, {"summary": "second"}
    )

    assert first["event_id"] != second["event_id"]


def test_session_store_recovers_from_empty_interrupted_file(tmp_path: Path) -> None:
    path = tmp_path / "character_agent_session_store.json"
    path.write_text("", encoding="utf-8")

    store = CharacterAgentSessionStore(storage_root=tmp_path)
    event = store.append_event("char_b", "character_perceived_event", 1006, {"summary": "recovered"})
    reloaded = CharacterAgentSessionStore(storage_root=tmp_path)

    assert event["event_index"] == 1
    assert reloaded.list_events("char_b")[0]["payload"]["summary"] == "recovered"


def test_session_store_appends_actor_scoped_history_without_rewriting_other_actor(
    tmp_path: Path,
) -> None:
    store = CharacterAgentSessionStore(storage_root=tmp_path)
    store.append_event("char_a", "character_perceived_event", 1007, {"summary": "a"})

    actor_a_path = store._actor_storage_path("char_a")
    before = actor_a_path.read_bytes()

    store.append_event("char_b", "character_perceived_event", 1008, {"summary": "b"})

    assert actor_a_path.read_bytes() == before
    assert store.list_events("char_a")[0]["payload"]["summary"] == "a"
    assert store.list_events("char_b")[0]["payload"]["summary"] == "b"


def test_session_store_migrates_legacy_snapshot_once_without_duplicate_events(
    tmp_path: Path,
) -> None:
    legacy_event = {
        "event_id": "char_a:legacy:1",
        "event_index": 1,
        "actor_id": "char_a",
        "event_type": "legacy",
        "producer_ts": 1,
        "payload": {"summary": "legacy"},
    }
    (tmp_path / "character_agent_session_store.json").write_text(
        '{"char_a": [' + json.dumps(legacy_event) + ']}',
        encoding="utf-8",
    )

    store = CharacterAgentSessionStore(storage_root=tmp_path)
    store.append_event("char_a", "new", 2, {"summary": "new"})
    reloaded = CharacterAgentSessionStore(storage_root=tmp_path)

    assert [item["event_type"] for item in reloaded.list_events("char_a")] == ["legacy", "new"]


def test_session_store_resumes_interrupted_legacy_migration_without_duplicates(
    tmp_path: Path,
) -> None:
    legacy_events = [
        {
            "event_id": f"char_a:legacy:{index}",
            "event_index": index,
            "actor_id": "char_a",
            "event_type": "legacy",
            "producer_ts": index,
            "payload": {"index": index},
        }
        for index in (1, 2)
    ]
    (tmp_path / "character_agent_session_store.json").write_text(
        json.dumps({"char_a": legacy_events}),
        encoding="utf-8",
    )
    actor_path = (
        CharacterAgentSessionStore(storage_root=tmp_path)._actor_storage_path("char_a")
    )
    actor_path.parent.mkdir(parents=True, exist_ok=True)
    actor_path.write_text(json.dumps(legacy_events[0]) + "\n", encoding="utf-8")

    store = CharacterAgentSessionStore(storage_root=tmp_path)
    store.append_event("char_a", "new", 3, {"index": 3})
    reloaded = CharacterAgentSessionStore(storage_root=tmp_path)

    assert [event["event_id"] for event in reloaded.list_events("char_a")[:2]] == [
        "char_a:legacy:1",
        "char_a:legacy:2",
    ]
    assert [event["event_type"] for event in reloaded.list_events("char_a")] == [
        "legacy",
        "legacy",
        "new",
    ]


def test_session_store_recovers_actor_log_when_schema_marker_is_missing(
    tmp_path: Path,
) -> None:
    store = CharacterAgentSessionStore(storage_root=tmp_path)
    store.append_event("char_b", "committed", 4, {"summary": "durable"})
    (tmp_path / "character_agent_session_store.json").unlink()

    reloaded = CharacterAgentSessionStore(storage_root=tmp_path)

    assert [event["event_type"] for event in reloaded.list_events("char_b")] == [
        "committed"
    ]


def test_session_store_ignores_only_an_incomplete_jsonl_tail(tmp_path: Path) -> None:
    store = CharacterAgentSessionStore(storage_root=tmp_path)
    store.append_event("char_c", "committed", 5, {"summary": "complete"})
    actor_path = store._actor_storage_path("char_c")
    with actor_path.open("ab") as stream:
        stream.write(b'{"event_id":"interrupted"')

    reloaded = CharacterAgentSessionStore(storage_root=tmp_path)

    assert [event["event_type"] for event in reloaded.list_events("char_c")] == [
        "committed"
    ]


def test_session_store_truncates_incomplete_tail_before_next_append(
    tmp_path: Path,
) -> None:
    first = CharacterAgentSessionStore(storage_root=tmp_path)
    first.append_event("char_c", "first", 6, {})
    actor_path = first._actor_storage_path("char_c")
    with actor_path.open("ab") as stream:
        stream.write(b'{"event_id":"interrupted"')

    recovered = CharacterAgentSessionStore(storage_root=tmp_path)
    recovered.append_event("char_c", "second", 7, {})
    reloaded = CharacterAgentSessionStore(storage_root=tmp_path)

    assert [event["event_type"] for event in reloaded.list_events("char_c")] == [
        "first",
        "second",
    ]


def test_session_store_recovers_utf8_codepoint_cut_in_jsonl_tail(
    tmp_path: Path,
) -> None:
    store = CharacterAgentSessionStore(storage_root=tmp_path)
    store.append_event("char_c", "committed", 8, {})
    actor_path = store._actor_storage_path("char_c")
    with actor_path.open("ab") as stream:
        stream.write(b'{"summary":"\xe4\xb8')

    recovered = CharacterAgentSessionStore(storage_root=tmp_path)

    assert [event["event_type"] for event in recovered.list_events("char_c")] == [
        "committed"
    ]


def test_session_store_rejects_non_event_json_before_the_tail(tmp_path: Path) -> None:
    store = CharacterAgentSessionStore(storage_root=tmp_path)
    store.append_event("char_a", "committed", 9, {})
    actor_path = store._actor_storage_path("char_a")
    with actor_path.open("ab") as stream:
        stream.write(b"[]\n")

    with pytest.raises(ValueError, match="session_event_invalid"):
        CharacterAgentSessionStore(storage_root=tmp_path)


def test_session_store_rejects_conflicting_duplicate_event_id(tmp_path: Path) -> None:
    legacy_event = {
        "event_id": "char_a:conflict:1",
        "event_index": 1,
        "actor_id": "char_a",
        "event_type": "legacy",
        "producer_ts": 1,
        "payload": {"value": "legacy"},
    }
    (tmp_path / "character_agent_session_store.json").write_text(
        json.dumps({"char_a": [legacy_event]}),
        encoding="utf-8",
    )
    store = CharacterAgentSessionStore(storage_root=tmp_path)
    actor_path = store._actor_storage_path("char_a")
    actor_path.parent.mkdir(parents=True, exist_ok=True)
    actor_path.write_text(
        json.dumps({**legacy_event, "payload": {"value": "conflict"}}) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="session_event_id_conflict"):
        CharacterAgentSessionStore(storage_root=tmp_path)


def test_session_store_repairs_complete_jsonl_tail_without_newline(
    tmp_path: Path,
) -> None:
    first = CharacterAgentSessionStore(storage_root=tmp_path)
    first.append_event("char_b", "first", 10, {})
    actor_path = first._actor_storage_path("char_b")
    actor_path.write_bytes(actor_path.read_bytes().removesuffix(b"\n"))

    recovered = CharacterAgentSessionStore(storage_root=tmp_path)
    recovered.append_event("char_b", "second", 11, {})
    reloaded = CharacterAgentSessionStore(storage_root=tmp_path)

    assert [event["event_type"] for event in reloaded.list_events("char_b")] == [
        "first",
        "second",
    ]


def test_session_store_deduplicates_exact_legacy_event_ids(tmp_path: Path) -> None:
    event = {
        "event_id": "char_a:legacy:duplicate",
        "event_index": 1,
        "actor_id": "char_a",
        "event_type": "legacy",
        "producer_ts": 1,
        "payload": {},
    }
    (tmp_path / "character_agent_session_store.json").write_text(
        json.dumps({"char_a": [event, event]}),
        encoding="utf-8",
    )

    store = CharacterAgentSessionStore(storage_root=tmp_path)

    assert store.list_events("char_a") == [event]


def test_session_store_rejects_conflicting_legacy_event_ids(tmp_path: Path) -> None:
    event = {
        "event_id": "char_a:legacy:conflict",
        "event_index": 1,
        "actor_id": "char_a",
        "event_type": "legacy",
        "producer_ts": 1,
        "payload": {},
    }
    (tmp_path / "character_agent_session_store.json").write_text(
        json.dumps({"char_a": [event, {**event, "payload": {"conflict": True}}]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="session_event_id_conflict"):
        CharacterAgentSessionStore(storage_root=tmp_path)


def test_session_store_rejects_actor_log_in_wrong_hashed_path(tmp_path: Path) -> None:
    store = CharacterAgentSessionStore(storage_root=tmp_path)
    event = store.append_event("char_a", "committed", 12, {})
    correct_path = store._actor_storage_path("char_a")
    wrong_path = correct_path.with_name("wrong.jsonl")
    correct_path.replace(wrong_path)

    with pytest.raises(ValueError, match="session_event_actor_path_mismatch"):
        CharacterAgentSessionStore(storage_root=tmp_path)


def test_session_store_rejects_non_contiguous_event_index(tmp_path: Path) -> None:
    store = CharacterAgentSessionStore(storage_root=tmp_path)
    first = store.append_event("char_a", "first", 13, {})
    actor_path = store._actor_storage_path("char_a")
    second = {
        **first,
        "event_id": "char_a:gap:99",
        "event_index": 99,
        "event_type": "gap",
    }
    with actor_path.open("ab") as stream:
        stream.write((json.dumps(second) + "\n").encode("utf-8"))

    with pytest.raises(ValueError, match="session_event_index_gap"):
        CharacterAgentSessionStore(storage_root=tmp_path)


def test_session_store_preserves_history_when_actor_directory_disappears(
    tmp_path: Path, monkeypatch
) -> None:
    store = CharacterAgentSessionStore(storage_root=tmp_path)
    store.append_event("char_a", "first", 14, {})
    actor_path = store._actor_storage_path("char_a")
    original_open = Path.open
    deleted = False

    def delete_directory_before_append(path: Path, mode: str = "r", *args, **kwargs):
        nonlocal deleted
        if path == actor_path and mode == "ab" and not deleted:
            deleted = True
            shutil.rmtree(actor_path.parent)
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", delete_directory_before_append)
    store.append_event("char_a", "second", 15, {})
    monkeypatch.setattr(Path, "open", original_open)

    reloaded = CharacterAgentSessionStore(storage_root=tmp_path)

    assert [event["event_type"] for event in reloaded.list_events("char_a")] == [
        "first",
        "second",
    ]


def test_legacy_migration_uses_short_same_directory_temporary_path(
    tmp_path: Path, monkeypatch
) -> None:
    legacy_event = {
        "event_id": "char_a:first:14:legacy:1",
        "event_index": 1,
        "actor_id": "char_a",
        "event_type": "first",
        "producer_ts": 14,
        "payload": {},
    }
    (tmp_path / "character_agent_session_store.json").write_text(
        json.dumps({"char_a": [legacy_event]}),
        encoding="utf-8",
    )
    store = CharacterAgentSessionStore(storage_root=tmp_path)
    actor_path = store._actor_storage_path("char_a")
    maximum_path_length = len(str(actor_path)) + 10
    original_open = Path.open

    def reject_overlong_path(path: Path, *args, **kwargs):
        if len(str(path)) > maximum_path_length:
            raise FileNotFoundError(str(path))
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", reject_overlong_path)

    store.append_event("char_a", "second", 15, {})
    reloaded = CharacterAgentSessionStore(storage_root=tmp_path)

    assert [event["event_type"] for event in reloaded.list_events("char_a")] == [
        "first",
        "second",
    ]
