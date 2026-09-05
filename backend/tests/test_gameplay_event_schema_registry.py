from __future__ import annotations

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
