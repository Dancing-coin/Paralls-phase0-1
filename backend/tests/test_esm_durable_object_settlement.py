"""Shared-store owner tests; these do not assert production source admission."""
import pytest

from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.models.player_input import InteractIntent
from app.services.esm_service import ESMService


def command(service, key="exec:1", action="use", target="obj_worktable", scene="scene_demo"):
    event = InteractIntent(player_id="character_agent", room_id="room_demo", scene_id=scene,
        zone_id="zone_focus", actor_id="char_a", intent_type="interact_intent", producer_ts=10,
        target_object_id=target, interaction_type=action, turn_id="turn:1", execution_contract_ref=key)
    return event, service.build_action_request(event)


def settle(service, event, request, **kwargs):
    return service.settle_object_interaction(event, action_request=request,
        actor_position=kwargs.pop("actor_position", (-0.9, 0.85, -2.0)), **kwargs)


def state(service, scene="scene_demo"):
    return service.interaction_state_for(room_id="room_demo", scene_id=scene,
        zone_id="zone_focus", target_object_id="obj_worktable")


def test_sqlite_commit_reopen_exact_receipt_and_next_transition(tmp_path):
    path = tmp_path / "world.db"
    store = DurableGameplayEventStore(path)
    try:
        service = ESMService(store=store)
        event, request = command(service)
        result, receipt = settle(service, event, request)
        assert result.settlement_status == "committed"
        assert result.settlement_id == receipt.transaction_id
        assert receipt.committed and state(service) == "engaged"
        assert store.get_event(receipt.committed_event_ids[0]).visibility_policy == "authority_only"
    finally:
        store.close()
    store = DurableGameplayEventStore(path)
    try:
        service = ESMService(store=store)
        assert state(service) == "engaged"
        assert settle(service, event, request, actor_position=None) == (result, receipt)
        assert store.get_last_global_sequence() == 1
        event2, request2 = command(service, key="exec:2", action="finish_use")
        assert settle(service, event2, request2)[1].committed
        assert state(service) == "ready"
    finally:
        store.close()


@pytest.mark.parametrize("changes", [dict(scene_id="elsewhere"), dict(payload={"different": True}),
    dict(actor_id="char_b"), dict(source={"system": "spoofed"})])
def test_changed_duplicate_zero_write(changes):
    store = GameplayEventStore()
    service = ESMService(store=store)
    event, request = command(service)
    settle(service, event, request)
    with pytest.raises(ValueError):
        settle(service, event, request.model_copy(update=changes))
    assert store.get_last_global_sequence() == 1


@pytest.mark.parametrize("position", [None, (float("nan"), 0, 0), (float("inf"), 0, 0),
    (0, 0), (True, 0, 0)])
def test_invalid_position_zero_write(position):
    store = GameplayEventStore()
    service = ESMService(store=store)
    event, request = command(service)
    with pytest.raises(ValueError, match="position"):
        settle(service, event, request, actor_position=position)
    assert store.get_last_global_sequence() == 0 and state(service) == "ready"


def test_out_of_range_then_retry_and_scope_isolation():
    store = GameplayEventStore()
    service = ESMService(store=store)
    event, request = command(service)
    result, receipt = settle(service, event, request, actor_position=(100, 0, 0))
    assert result.settlement_status == "rejected" and receipt is None
    assert state(service) == "ready" and store.get_last_global_sequence() == 0
    settle(service, event, request)
    assert state(service, "other") == "ready"
    event2, request2 = command(service, key="exec:2", scene="other")
    assert settle(service, event2, request2)[1].committed
    assert len(store.get_stream_heads()) == 2


@pytest.mark.parametrize("target,action", [("obj_letter", "inspect"), ("obj_lamp_switch", "press"),
    ("obj_archive_door", "open"), ("obj_observation_bench", "sit")])
def test_external_or_physical_effects_not_partially_committed(target, action):
    store = GameplayEventStore()
    service = ESMService(store=store)
    event, request = command(service, target=target, action=action)
    with pytest.raises(ValueError, match="object_only"):
        settle(service, event, request)
    assert store.get_last_global_sequence() == 0


@pytest.mark.parametrize("commit_first", [False, True])
def test_append_failure_and_lost_response_do_not_install_volatile_state(monkeypatch, commit_first):
    store = GameplayEventStore()
    service = ESMService(store=store)
    event, request = command(service)
    original = store.append_batch
    def fail(batch):
        if commit_first:
            original(batch)
        raise OSError("response lost" if commit_first else "disk unavailable")
    monkeypatch.setattr(store, "append_batch", fail)
    with pytest.raises(OSError):
        settle(service, event, request)
    assert state(service) == "ready" and not service._canonical_interaction_settlements
    monkeypatch.setattr(store, "append_batch", original)
    assert settle(service, event, request)[1].committed
    assert state(service) == "engaged" and store.get_last_global_sequence() == 1


def test_read_revision_cas_failure_zero_write():
    store = GameplayEventStore()
    service = ESMService(store=store)
    event, request = command(service)
    with pytest.raises(ValueError, match="commit"):
        settle(service, event, request, read_stream_revisions={"source:missing": 1})
    assert store.get_last_global_sequence() == 0 and state(service) == "ready"


def test_corrupt_receipt_recovery_fails_closed(monkeypatch):
    store = GameplayEventStore()
    service = ESMService(store=store)
    event, request = command(service)
    settle(service, event, request)
    original = store.get_transaction
    def corrupt(ref):
        return original(ref).model_copy(update={"result_digest": "sha256:corrupt"}, deep=True)
    monkeypatch.setattr(store, "get_transaction", corrupt)
    with pytest.raises(ValueError, match="recovery"):
        ESMService(store=store)
    assert store.get_last_global_sequence() == 1


@pytest.mark.parametrize("changes", [dict(actor_id="char_b"), dict(turn_id="turn:other"),
    dict(execution_contract_ref="exec:other"), dict(scene_id="other"),
    dict(target_object_id="obj_plaque"), dict(interaction_type="finish_use")])
def test_exact_request_with_mismatched_event_is_rejected(changes):
    store = GameplayEventStore()
    service = ESMService(store=store)
    event, request = command(service)
    settle(service, event, request)
    with pytest.raises(ValueError, match="match"):
        settle(service, event.model_copy(update=changes), request)
    assert store.get_last_global_sequence() == 1


def test_concurrent_object_commit_cannot_be_overwritten(monkeypatch):
    store = GameplayEventStore()
    service = ESMService(store=store)
    other = ESMService(store=store)
    event, request = command(service)
    original = store.append_batch
    def race(batch):
        monkeypatch.setattr(store, "append_batch", original)
        other_event, other_request = command(other, key="exec:other")
        settle(other, other_event, other_request)
        return original(batch)
    monkeypatch.setattr(store, "append_batch", race)
    with pytest.raises(ValueError, match="commit"):
        settle(service, event, request)
    assert store.get_last_global_sequence() == 1
    assert state(service) == "ready"
    assert state(ESMService(store=store)) == "engaged"


def test_explicit_schema_registration_with_strict_durable_store(tmp_path):
    from app.gameplay.event_schema_registry import EventSchemaRegistry
    from app.services.esm_service import ESM_OBJECT_SETTLEMENT_SCHEMA
    registry = EventSchemaRegistry()
    registry.register(ESM_OBJECT_SETTLEMENT_SCHEMA)
    path = tmp_path / "strict.db"
    store = DurableGameplayEventStore(path, event_schema_registry=registry)
    try:
        service = ESMService(store=store)
        event, request = command(service)
        result, receipt = settle(service, event, request)
    finally:
        store.close()
    store = DurableGameplayEventStore(path, event_schema_registry=registry)
    try:
        assert settle(ESMService(store=store), event, request) == (result, receipt)
    finally:
        store.close()


@pytest.mark.parametrize("committed", [False, True])
def test_legacy_commit_cannot_mutate_durable_object_state(committed):
    store = GameplayEventStore()
    service = ESMService(store=store)
    event, request = command(service)
    if committed:
        settle(service, event, request)
    with pytest.raises(ValueError, match="durable"):
        service.commit_interaction_state(room_id=event.room_id, scene_id=event.scene_id,
            zone_id=event.zone_id, target_object_id=event.target_object_id,
            current_state="ready" if committed else "engaged")
    assert state(service) == ("engaged" if committed else "ready")
    assert state(ESMService(store=store)) == state(service)


@pytest.mark.parametrize("field", ["room_id", "scene_id", "zone_id", "actor_id"])
def test_missing_canonical_identity_cannot_create_durable_truth(field):
    store = GameplayEventStore()
    service = ESMService(store=store)
    event, _ = command(service)
    event = event.model_copy(update={field: ""})
    request = service.build_action_request(event)
    with pytest.raises(ValueError, match="canonical"):
        settle(service, event, request)
    assert store.get_last_global_sequence() == 0
