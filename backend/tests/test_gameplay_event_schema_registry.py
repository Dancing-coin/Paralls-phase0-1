from __future__ import annotations

import sqlite3

import pytest

from app.gameplay.event_schema_registry import EventSchemaRegistration, EventSchemaRegistry, EventSchemaRegistryError, create_stormnight_event_schema_registry
from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore

from test_gameplay_event_store_contract import _batch, _event, _outbox


def test_optional_registry_rejects_unregistered_event_without_mutation() -> None:
    registry = EventSchemaRegistry()
    store = GameplayEventStore(event_schema_registry=registry)
    result = store.append_batch(_batch(events=[_event("evt:registry", stream_id="stream:registry")], outbox_entries=[_outbox("evt:registry")], expected={"stream:registry": 0}))
    assert not result.committed
    assert result.failure is not None and result.failure.error_code == "event_schema_unregistered"
    assert store.read_events() == []


def test_registered_event_version_commits_while_default_store_remains_compatible() -> None:
    registry = EventSchemaRegistry()
    registry.register(EventSchemaRegistration("gameplay.session_reserved", 1, "sha256:fixture-v1"))
    guarded = GameplayEventStore(event_schema_registry=registry)
    assert guarded.append_batch(_batch(events=[_event("evt:registered", stream_id="stream:registered")], outbox_entries=[_outbox("evt:registered")], expected={"stream:registered": 0})).committed
    assert GameplayEventStore().append_batch(_batch(events=[_event("evt:default", stream_id="stream:default")], outbox_entries=[_outbox("evt:default")], expected={"stream:default": 0})).committed


def test_schema_registration_identity_is_immutable_and_snapshot_round_trips() -> None:
    registry = EventSchemaRegistry()
    registration = EventSchemaRegistration("gameplay.session_reserved", 1, "sha256:fixture-v1")
    registry.register(registration)

    with pytest.raises(EventSchemaRegistryError, match="event_schema_registration_duplicate"):
        registry.register(registration)
    with pytest.raises(EventSchemaRegistryError, match="event_schema_digest_conflict"):
        registry.register(EventSchemaRegistration("gameplay.session_reserved", 1, "sha256:changed"))

    restored = EventSchemaRegistry.from_snapshot(registry.export_snapshot())
    assert restored.get("gameplay.session_reserved", 1) == registration


def test_stormnight_case_schema_bundle_is_registered() -> None:
    registry = create_stormnight_event_schema_registry()
    for event_type in (
        "gameplay.p5.mystery.case_opened@1",
        "gameplay.p5.mystery.statement_recorded@1",
        "gameplay.p5.mystery.accusation_submitted@1",
        "gameplay.p5.mystery.case_outcome_resolved@1",
    ):
        registry.require(event_type, 1)


def test_durable_snapshot_restores_opt_in_write_gate(tmp_path) -> None:
    path = tmp_path / "guarded-store.json"
    registry = EventSchemaRegistry()
    registry.register(EventSchemaRegistration("gameplay.session_reserved", 1, "sha256:fixture-v1"))
    store = DurableGameplayEventStore(path, event_schema_registry=registry)
    assert store.append_batch(
        _batch(
            events=[_event("evt:guarded", stream_id="stream:guarded")],
            outbox_entries=[_outbox("evt:guarded")],
            expected={"stream:guarded": 0},
        )
    ).committed

    restored = DurableGameplayEventStore(path)
    unregistered_event = _event(
        "evt:unregistered",
        stream_id="stream:unregistered",
        tx="tx:unregistered",
        command_id="cmd:unregistered",
    )
    unregistered_event["schema_version"] = 2
    rejected = restored.append_batch(
        _batch(
            tx="tx:unregistered",
            command_id="cmd:unregistered",
            key="key:unregistered",
            digest="digest:unregistered",
            events=[unregistered_event],
            outbox_entries=[_outbox("evt:unregistered", tx="tx:unregistered")],
            expected={"stream:unregistered": 0},
        )
    )
    assert not rejected.committed
    assert rejected.failure is not None and rejected.failure.error_code == "event_schema_unregistered"


def _registry_batch(suffix: str, *, schema_version: int = 1):
    tx = f"tx:registry:{suffix}"
    command = f"cmd:registry:{suffix}"
    stream = f"stream:registry:{suffix}"
    event = _event(f"evt:registry:{suffix}", stream_id=stream, tx=tx, command_id=command)
    event["schema_version"] = schema_version
    return _batch(
        tx=tx,
        command_id=command,
        key=f"key:registry:{suffix}",
        digest=f"digest:registry:{suffix}",
        events=[event],
        outbox_entries=[_outbox(event["event_id"], tx=tx)],
        expected={stream: 0},
    )


def test_durable_writes_reuse_unchanged_registry_serialization(tmp_path, monkeypatch) -> None:
    registry = EventSchemaRegistry()
    registry.register(EventSchemaRegistration("gameplay.session_reserved", 1, "sha256:fixture-v1"))
    store = DurableGameplayEventStore(tmp_path / "registry-reuse.db", event_schema_registry=registry)
    exports = []
    export_snapshot = registry.export_snapshot

    def export():
        value = export_snapshot()
        exports.append(value)
        return value

    monkeypatch.setattr(registry, "export_snapshot", export)
    try:
        for suffix in ("first", "second", "third"):
            assert store.append_batch(_registry_batch(suffix)).committed
        assert exports == []
        reopened = DurableGameplayEventStore(store._snapshot_path)
        try:
            assert [event.event_id for event in reopened.read_events()] == [
                "evt:registry:first", "evt:registry:second", "evt:registry:third",
            ]
            assert reopened.export_snapshot()["event_schema_registry"] == {
                "registry_schema_version": 1,
                "registrations": [{"event_type": "gameplay.session_reserved", "schema_version": 1,
                                   "schema_digest": "sha256:fixture-v1"}],
            }
        finally:
            reopened.close()
    finally:
        store.close()


def test_durable_registry_rebuilds_only_after_successful_registration(tmp_path, monkeypatch) -> None:
    registry = EventSchemaRegistry()
    v1 = EventSchemaRegistration("gameplay.session_reserved", 1, "sha256:fixture-v1")
    registry.register(v1)
    store = DurableGameplayEventStore(tmp_path / "registry-change.db", event_schema_registry=registry)
    exports = []
    export_snapshot = registry.export_snapshot

    def export():
        value = export_snapshot()
        exports.append(value)
        return value

    monkeypatch.setattr(registry, "export_snapshot", export)
    try:
        with pytest.raises(EventSchemaRegistryError, match="event_schema_registration_duplicate"):
            registry.register(v1)
        with pytest.raises(EventSchemaRegistryError, match="event_schema_digest_conflict"):
            registry.register(EventSchemaRegistration("gameplay.session_reserved", 1, "sha256:conflict"))
        assert store.append_batch(_registry_batch("unchanged")).committed
        assert exports == []
        registry.register(EventSchemaRegistration("gameplay.session_reserved", 2, "sha256:fixture-v2"))
        assert store.append_batch(_registry_batch("changed", schema_version=2)).committed
        assert store.append_batch(_registry_batch("changed-again", schema_version=2)).committed
        assert len(exports) == 1
        # 对外导出的可变副本不能污染后续持久化身份。
        snapshot = export_snapshot()
        snapshot["registrations"][0]["schema_digest"] = "sha256:tampered"
        assert store.append_batch(_registry_batch("isolated", schema_version=2)).committed
        assert len(exports) == 1
        reopened = DurableGameplayEventStore(store._snapshot_path)
        try:
            assert reopened.export_snapshot()["event_schema_registry"] == {
                "registry_schema_version": 1,
                "registrations": [
                    {"event_type": "gameplay.session_reserved", "schema_version": 1,
                     "schema_digest": "sha256:fixture-v1"},
                    {"event_type": "gameplay.session_reserved", "schema_version": 2,
                     "schema_digest": "sha256:fixture-v2"},
                ],
            }
        finally:
            reopened.close()
    finally:
        store.close()


def test_registry_change_survives_group_rollback_and_retry(tmp_path) -> None:
    path = tmp_path / "registry-group-rollback.db"
    registry = EventSchemaRegistry()
    registry.register(EventSchemaRegistration("gameplay.session_reserved", 1, "sha256:fixture-v1"))
    store = DurableGameplayEventStore(path, event_schema_registry=registry)
    try:
        with pytest.raises(RuntimeError, match="interrupt registry group"):
            with store.group_commit():
                assert store.append_batch(_registry_batch("first")).committed
                registry.register(EventSchemaRegistration("gameplay.session_reserved", 2, "sha256:fixture-v2"))
                assert store.append_batch(_registry_batch("second", schema_version=2)).committed
                raise RuntimeError("interrupt registry group")
        reopened = DurableGameplayEventStore(path)
        try:
            assert reopened.read_events() == []
            rejected = reopened.append_batch(_registry_batch("second", schema_version=2))
            assert rejected.failure.error_code == "event_schema_unregistered"
        finally:
            reopened.close()
        with store.group_commit():
            assert store.append_batch(_registry_batch("second", schema_version=2)).committed
            assert store.append_batch(_registry_batch("third", schema_version=2)).committed
        store.close()
        reopened = DurableGameplayEventStore(path)
        try:
            assert [event.event_id for event in reopened.read_events()] == [
                "evt:registry:second", "evt:registry:third",
            ]
            assert reopened.append_batch(_registry_batch("second", schema_version=2)).idempotency_status == "duplicate_replayed"
            assert reopened.export_snapshot()["event_schema_registry"]["registrations"][1] == {
                "event_type": "gameplay.session_reserved", "schema_version": 2,
                "schema_digest": "sha256:fixture-v2",
            }
        finally:
            reopened.close()
    finally:
        store.close()


def test_registry_change_retries_after_later_sql_write_failure(tmp_path) -> None:
    path = tmp_path / "registry-sql-rollback.db"
    registry = EventSchemaRegistry()
    registry.register(EventSchemaRegistration("gameplay.session_reserved", 1, "sha256:fixture-v1"))
    store = DurableGameplayEventStore(path, event_schema_registry=registry)
    try:
        registry.register(EventSchemaRegistration("gameplay.session_reserved", 2, "sha256:fixture-v2"))
        batch = _registry_batch("retry", schema_version=2)
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TRIGGER reject_outbox BEFORE INSERT ON outbox BEGIN SELECT RAISE(ABORT, 'injected'); END")
        assert store.append_batch(batch).failure.error_code == "durable_persistence_failed"
        reopened = DurableGameplayEventStore(path)
        try:
            assert reopened.read_events() == []
            assert reopened.append_batch(batch).failure.error_code == "event_schema_unregistered"
        finally:
            reopened.close()
        with sqlite3.connect(path) as connection:
            connection.execute("DROP TRIGGER reject_outbox")
        assert store.append_batch(batch).committed
        reopened = DurableGameplayEventStore(path)
        try:
            assert reopened.append_batch(batch).idempotency_status == "duplicate_replayed"
            assert reopened.export_snapshot()["event_schema_registry"]["registrations"][1] == {
                "event_type": "gameplay.session_reserved", "schema_version": 2,
                "schema_digest": "sha256:fixture-v2",
            }
        finally:
            reopened.close()
    finally:
        store.close()


def test_registration_during_snapshot_export_is_not_cached_as_current(tmp_path, monkeypatch) -> None:
    registry = EventSchemaRegistry()
    registry.register(EventSchemaRegistration("gameplay.session_reserved", 1, "sha256:fixture-v1"))
    export_snapshot = registry.export_snapshot

    def register_after_export():
        value = export_snapshot()
        registry.register(EventSchemaRegistration("gameplay.session_reserved", 2, "sha256:fixture-v2"))
        monkeypatch.setattr(registry, "export_snapshot", export_snapshot)
        return value

    monkeypatch.setattr(registry, "export_snapshot", register_after_export)
    path = tmp_path / "registry-export-change.db"
    store = DurableGameplayEventStore(path, event_schema_registry=registry)
    try:
        assert store.append_batch(_registry_batch("changed", schema_version=2)).committed
        reopened = DurableGameplayEventStore(path)
        try:
            assert reopened.append_batch(_registry_batch("next", schema_version=2)).committed
        finally:
            reopened.close()
    finally:
        store.close()
