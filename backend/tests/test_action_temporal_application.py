"""Application-bound Action admission and committed-request recovery evidence."""
from dataclasses import replace
from fractions import Fraction
from copy import deepcopy
import json
from threading import get_ident

import pytest

from app import main
from app.gameplay.event_schema_registry import create_stormnight_event_schema_registry
from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.p5 import stormnight_realtime_session as session_module
from app.services.runtime_execution import RuntimeExecution
from app.world_runtime.simulation_clock import SimulationClock
from app.world_runtime.temporal_contracts import ClockMapping, SimulationTimeline, TemporalProfile
from app.ws_protocol import Envelope


def _sample():
    from app.gameplay.action_window_runtime import ActionTemporalContext

    profile = TemporalProfile("test.action.seconds", "1", "test-only", "continuous", "fixed_step",
        "scheduled_event", "immediate_owner_action", "world", "best_effort", "disabled", "second",
        Fraction(1), ("test.action.source",), "exact", "step", ())
    timeline = SimulationTimeline("world:test-action", "world:test-action", "test-owner",
        profile.profile_id, "1", "test-epoch", 10, None, 0, "active")
    clock = SimulationClock(world_ref=timeline.world_scope_ref, initial_tick=10,
        temporal_profile=profile, timeline=timeline)
    mapping = ClockMapping("test.action.source", "1", "server:test-action", "sample", timeline.timeline_id,
        "1", 100, 10, Fraction(1), "exact", (0, 1000), 5, "test-only-admission")
    context = ActionTemporalContext(clock=clock, mapping=mapping, source_revision="source:1",
        sampled_at=100, received_at=100, cutoff_tick=101,
        late_input_policy_ref="test:reject-late", ordering_policy_ref="test:command-order")
    return session_module.StormnightActionTimeSample(context=context, window_start_tick=100,
        window_end_tick=101, submitted_at="2026-10-16T00:00:00Z")


def _route(execution, kind, request_id, **fields):
    envelope = Envelope(message_type="stormnight_player_intent",
        payload=dict(kind=kind, request_id=request_id, **fields))
    return execution.submit(lambda: main._handle_envelope(envelope)[0]["payload"]).result(timeout=10)


def _install(monkeypatch, store, provider=None):
    service = session_module.StormnightRealtimeSessionService(store=store, action_time_provider=provider)
    monkeypatch.setattr(main, "stormnight_realtime_session_service", service, raising=False)
    return service


def test_actual_application_rejects_unbound_action_without_writes(monkeypatch):
    store = GameplayEventStore(event_schema_registry=create_stormnight_event_schema_registry())
    _install(monkeypatch, store)
    execution = RuntimeExecution()
    try:
        assert _route(execution, "start", "unbound-start")["accepted"]
        before = len(store.read_events())
        result = _route(execution, "pursue", "unbound-action")
        assert not result["accepted"] and result["error_code"] == "action_time_binding_missing"
        assert len(store.read_events()) == before
    finally:
        assert execution.stop(timeout_seconds=2)


def test_actual_application_owner_commits_mapped_pins_and_replays_original_receipt(monkeypatch):
    sample = _sample()
    calls = []
    def provider(_intent):
        calls.append(get_ident())
        return sample
    store = GameplayEventStore(event_schema_registry=create_stormnight_event_schema_registry())
    _install(monkeypatch, store, provider)
    execution = RuntimeExecution()
    try:
        assert _route(execution, "start", "mapped-start")["accepted"]
        first = _route(execution, "pursue", "mapped-action")
        assert first["accepted"] and first["receipt_event_ids"]
        event = store.get_event(first["receipt_event_ids"][0])
        assert event.payload["time_binding"]["timeline_id"] == "world:test-action"
        assert event.payload["window_start_tick"] == 100  # Content ordinal is zero.
        receipt = store.get_by_idempotency("authority:p5:investigation-conflict", "stormnight:player:mapped-action:action")
        assert first["receipt_event_ids"] == receipt.committed_event_ids
        before = len(store.read_events())
        replay = _route(execution, "pursue", "mapped-action")
        assert replay["idempotency_status"] == "duplicate_replayed"
        assert replay["receipt_event_ids"] == first["receipt_event_ids"]
        assert len(store.read_events()) == before and len(calls) == 1
        assert calls[0] != get_ident()
        changed = _route(execution, "hide", "mapped-action")
        assert not changed["accepted"] and len(store.read_events()) == before
    finally:
        assert execution.stop(timeout_seconds=2)


@pytest.mark.parametrize("change", ["timeline", "profile", "late", "source", "mapping"])
def test_actual_application_rejects_bad_temporal_admission(monkeypatch, change):
    sample = _sample()
    if change == "timeline":
        sample = replace(sample, context=replace(sample.context,
            mapping=replace(sample.context.mapping, target_timeline_ref="world:other")))
    elif change == "profile":
        sample = replace(sample, context=replace(sample.context,
            mapping=replace(sample.context.mapping, target_profile_revision="stale")))
    elif change == "late":
        sample = replace(sample, context=replace(sample.context, received_at=102))
    else:
        # Corrupt the frozen request during caller-to-owner transit. Admission
        # context remains trusted and the real owner must reject the old pin.
        freeze = session_module.freeze_action_time_binding
        field = "source_revision" if change == "source" else "mapping_revision"
        def corrupt(*args, **kwargs):
            return freeze(*args, **kwargs).model_copy(update={field: "stale"})
        monkeypatch.setattr(session_module, "freeze_action_time_binding", corrupt)
    store = GameplayEventStore(event_schema_registry=create_stormnight_event_schema_registry())
    _install(monkeypatch, store, lambda _intent: sample)
    execution = RuntimeExecution()
    try:
        assert _route(execution, "start", "bad-time-start")["accepted"]
        before = len(store.read_events())
        result = _route(execution, "hide", "bad-time-action")
        assert not result["accepted"] and result["error_code"]
        assert len(store.read_events()) == before
    finally:
        assert execution.stop(timeout_seconds=2)


def test_durable_application_restart_replays_pins_receipt_without_sampling(monkeypatch, tmp_path, record_property):
    path = tmp_path / "action.sqlite"
    schema = create_stormnight_event_schema_registry()
    store = DurableGameplayEventStore(path, event_schema_registry=schema)
    _install(monkeypatch, store, lambda _intent: _sample())
    execution = RuntimeExecution()
    try:
        assert _route(execution, "start", "durable-start")["accepted"]
        first = _route(execution, "pursue", "durable-action")
        assert first["accepted"]
        pins = store.get_event(first["receipt_event_ids"][0]).payload["time_binding"]
        receipt = store.get_by_idempotency("authority:p5:investigation-conflict", "stormnight:player:durable-action:action").model_dump(mode="json")
        count = len(store.read_events())
    finally:
        assert execution.stop(timeout_seconds=2)
        store.close()
    restored = DurableGameplayEventStore(path, event_schema_registry=schema)
    def forbidden_resample(_intent):
        pytest.fail("Committed retry must not sample current time or select the next content node")
    restored_service = _install(monkeypatch, restored, forbidden_resample)
    execution = RuntimeExecution()
    try:
        replay = _route(execution, "pursue", "durable-action")
        assert replay["accepted"] and replay["idempotency_status"] == "duplicate_replayed"
        assert replay["receipt_event_ids"] == first["receipt_event_ids"]
        assert restored.get_event(replay["receipt_event_ids"][0]).payload["time_binding"] == pins
        assert len(restored.read_events()) == count
        assert restored.get_by_idempotency("authority:p5:investigation-conflict", "stormnight:player:durable-action:action").model_dump(mode="json") == receipt
        record_property("action_temporal_pins", json.dumps(pins, sort_keys=True))
        record_property("actual_owner_receipt", json.dumps(receipt, sort_keys=True))
        record_property("boundary", "RuntimeExecution -> main._handle_envelope -> Stormnight session -> existing InvestigationConflictAuthority -> DurableGameplayEventStore")
        record_property("recovery", "closed first store; new instance; original receipt/pins; zero resampling; zero additional commits")
        changed = _route(execution, "hide", "durable-action")
        assert not changed["accepted"] and len(restored.read_events()) == count
        changed_kind = _route(execution, "inspect", "durable-action")
        assert not changed_kind["accepted"] and len(restored.read_events()) == count
        incompatible = _sample()
        incompatible = replace(incompatible, context=replace(incompatible.context, source_revision="source:2"))
        restored_service.action_time_provider = lambda _intent: incompatible
        new_request = _route(execution, "hide", "durable-new-incompatible")
        assert not new_request["accepted"] and new_request["error_code"] == "action_time_consumer_migration_required"
        assert len(restored.read_events()) == count
    finally:
        assert execution.stop(timeout_seconds=2)
        restored.close()


def test_application_rejects_revision_race_with_real_competing_store_write(monkeypatch):
    store = GameplayEventStore(event_schema_registry=create_stormnight_event_schema_registry())
    _install(monkeypatch, store, lambda _intent: _sample())
    execution = RuntimeExecution()
    original_append = store.append_batch
    raced = []
    def race(batch):
        value = batch.model_dump(mode="json") if hasattr(batch, "model_dump") else batch
        if not raced and value["events"][0]["stream_id"] == "gameplay:conflict:encounter:stormnight":
            competing = deepcopy(value)
            competing["transaction_id"] += ":competing"
            competing["command_id"] += ":competing"
            competing["idempotency_record"]["idempotency_key"] += ":competing"
            for event in competing["events"]:
                event["event_id"] += ":competing"
                event["transaction_id"] = competing["transaction_id"]
                event["command_id"] = competing["command_id"]
            raced.append(original_append(competing))
            assert raced[0].committed
        return original_append(batch)
    try:
        assert _route(execution, "start", "race-start")["accepted"]
        monkeypatch.setattr(store, "append_batch", race)
        result = _route(execution, "hide", "race-action")
        assert not result["accepted"] and result["error_code"]
        assert raced and store.get_by_idempotency("authority:p5:investigation-conflict",
            "stormnight:player:race-action:action") is None
    finally:
        assert execution.stop(timeout_seconds=2)


def test_caller_activation_refuses_provider_switch_without_migration(monkeypatch):
    provider = lambda _intent: _sample()
    store = GameplayEventStore(event_schema_registry=create_stormnight_event_schema_registry())
    service = _install(monkeypatch, store, provider)
    service.activate_action_time_provider(provider)
    with pytest.raises(ValueError, match="migration_required"):
        service.activate_action_time_provider(lambda _intent: _sample())
    assert service.action_time_provider is provider


def test_actual_caller_same_provider_mutation_requires_migration_and_old_replay_works(monkeypatch):
    sample = [_sample()]
    store = GameplayEventStore(event_schema_registry=create_stormnight_event_schema_registry())
    _install(monkeypatch, store, lambda _intent: sample[0])
    execution = RuntimeExecution()
    try:
        assert _route(execution, "start", "activation-start")["accepted"]
        first = _route(execution, "hide", "activation-first")
        assert first["accepted"]
        sample[0] = replace(sample[0], context=replace(sample[0].context, source_revision="source:2"))
        before = len(store.read_events())
        rejected = _route(execution, "hide", "activation-new")
        assert not rejected["accepted"] and rejected["error_code"] == "action_time_consumer_migration_required"
        replay = _route(execution, "hide", "activation-first")
        assert replay["accepted"] and replay["receipt_event_ids"] == first["receipt_event_ids"]
        assert len(store.read_events()) == before
    finally:
        assert execution.stop(timeout_seconds=2)
