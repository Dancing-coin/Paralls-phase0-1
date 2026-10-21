import pytest

from app.gameplay.event_schema_registry import EventSchemaRegistry, EventSchemaRegistration, register_social_delivery_event_schemas
from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.p5.social_delivery import SocialDeliveryAuthority, SocialDeliveryWindow, _PRINCIPAL
from app.gameplay.settlement_plan import build_atomic_event_batch


def _store():
    registry = EventSchemaRegistry()
    register_social_delivery_event_schemas(registry)
    registry.register(EventSchemaRegistration("gameplay.social.knowledge_observed", 1, "sha256:test:knowledge:v1"))
    return GameplayEventStore(event_schema_registry=registry), registry


def _source(store):
    batch = build_atomic_event_batch(
        command_id="source-1", principal_ref="authority:p5:social", stream_id="gameplay:source:1",
        expected_revision=0, event_specs=(("gameplay.social.knowledge_observed", {"fact_ref": "fact:1"}),),
        idempotency_key="source-key", causation_id="c:1", correlation_id="co:1",
    )
    batch = batch.model_copy(update={"events": [batch.events[0].model_copy(update={"visibility_policy": "public"})]}, deep=True)
    return store.append_batch(batch), "gameplay:source:1", batch.events[0].event_id


def _record(authority, **overrides):
    values = dict(
        delivery_ref="delivery:1", source_stream_id="gameplay:source:1", source_revision=1,
        source_event_id="event:source-1:1", recipient_ref="character:recipient",
        window=SocialDeliveryWindow(10, 20, 30), command_id="delivery-1", idempotency_key="delivery-key",
        causation_id="c:delivery", correlation_id="co:delivery", world_now=15, operational_now=10,
    )
    values.update(overrides)
    return authority.record_delivery(**values)


def test_delivery_rechecks_source_and_projects_recipient_scope():
    store, _ = _store()
    _, _, event_id = _source(store)
    authority = SocialDeliveryAuthority(store=store)
    result = _record(authority, source_event_id=event_id)
    assert result.committed
    assert authority.view_for(recipient_ref="character:recipient", world_now=15).deliveries
    assert store.list_outbox()[0].audience == "actor:character:recipient"
    duplicate = _record(authority, source_event_id=event_id)
    assert duplicate.committed and duplicate.error_code == "duplicate_replayed"
    changed = _record(authority, source_event_id=event_id, window=SocialDeliveryWindow(10, 21, 30))
    assert not changed.committed and changed.error_code == "idempotency_key_reused"


def test_delivery_changed_command_identity_is_rejected_without_write():
    store, _ = _store()
    _, _, event_id = _source(store)
    authority = SocialDeliveryAuthority(store=store)
    first = _record(authority, source_event_id=event_id)
    assert first.committed
    before = store.export_snapshot()
    changed = _record(authority, source_event_id=event_id, command_id="delivery-2")
    assert not changed.committed and changed.error_code == "idempotency_key_reused"
    assert store.export_snapshot() == before


def test_delivery_lost_response_recovery_after_window_closed_is_receipt_only():
    store, _ = _store()
    _, _, event_id = _source(store)
    authority = SocialDeliveryAuthority(store=store)
    first = _record(authority, source_event_id=event_id)
    assert first.committed
    before = store.export_snapshot()
    duplicate = _record(authority, source_event_id=event_id, world_now=25, operational_now=None)
    assert duplicate.committed and duplicate.error_code == "duplicate_replayed"
    assert duplicate.append_result == first.append_result
    changed = _record(authority, source_event_id=event_id, world_now=25,
                      operational_now=None, window=SocialDeliveryWindow(10, 21, 30))
    assert not changed.committed and changed.error_code == "idempotency_key_reused"
    assert store.export_snapshot() == before


def test_delivery_duplicate_rejects_corrupt_receipt_refs_without_write():
    store, _ = _store()
    _, _, event_id = _source(store)
    authority = SocialDeliveryAuthority(store=store)
    first = _record(authority, source_event_id=event_id)
    assert first.committed and first.append_result is not None
    key = (_PRINCIPAL, "delivery-key")
    store._idempotency_results[key] = first.append_result.model_copy(
        update={"committed_event_ids": [*first.append_result.committed_event_ids, "missing:event"]}, deep=True
    )
    before = store.export_snapshot()
    duplicate = _record(authority, source_event_id=event_id)
    assert not duplicate.committed and duplicate.error_code == "idempotency_key_reused"
    assert store.export_snapshot() == before


@pytest.mark.parametrize("operational_now", [None, True, "10", -1])
def test_delivery_with_cutoff_requires_valid_operational_sample_without_write(operational_now):
    store, _ = _store()
    _, _, event_id = _source(store)
    before = store.export_snapshot()
    result = _record(SocialDeliveryAuthority(store=store), source_event_id=event_id,
                     operational_now=operational_now)
    assert not result.committed
    assert result.error_code == "social_delivery_operational_time_invalid"
    assert store.export_snapshot() == before


@pytest.mark.parametrize("operational_now", [None, True, "10", -1])
def test_expiry_with_cutoff_requires_valid_operational_sample_without_write(operational_now):
    store, _ = _store()
    _, _, event_id = _source(store)
    authority = SocialDeliveryAuthority(store=store)
    assert _record(authority, source_event_id=event_id).committed
    before = store.export_snapshot()
    result = authority.expire_delivery(
        delivery_ref="delivery:1", recipient_ref="character:recipient", world_now=20,
        operational_now=operational_now, command_id="expiry-invalid-time",
        idempotency_key="expiry-invalid-time", causation_id="c:e", correlation_id="co:e",
    )
    assert not result.committed
    assert result.error_code == "social_delivery_operational_time_invalid"
    assert store.export_snapshot() == before


def test_delivery_rejects_stale_source_and_expiry_respects_operational_cutoff():
    store, _ = _store()
    _, stream, event_id = _source(store)
    authority = SocialDeliveryAuthority(store=store)
    assert _record(authority, source_event_id=event_id).committed
    assert not authority.expire_delivery(
        delivery_ref="delivery:1", recipient_ref="character:recipient", world_now=20, operational_now=31,
        command_id="expiry-late", idempotency_key="expiry-late-key", causation_id="c:e", correlation_id="co:e",
    ).committed
    expired = authority.expire_delivery(
        delivery_ref="delivery:1", recipient_ref="character:recipient", world_now=20, operational_now=30,
        command_id="expiry-1", idempotency_key="expiry-key", causation_id="c:e", correlation_id="co:e",
    )
    assert expired.committed
    assert not authority.view_for(recipient_ref="character:recipient", world_now=15).deliveries


def test_expiry_rejects_changed_source_revision_without_write():
    store, _ = _store()
    _, stream, event_id = _source(store)
    authority = SocialDeliveryAuthority(store=store)
    assert _record(authority, source_event_id=event_id).committed
    before = store.export_snapshot()
    store._stream_heads[stream] = store.get_stream_head(stream) + 1
    rejected = authority.expire_delivery(
        delivery_ref="delivery:1", recipient_ref="character:recipient", world_now=20, operational_now=30,
        command_id="expiry-stale", idempotency_key="expiry-stale-key", causation_id="c:e", correlation_id="co:e",
    )
    assert not rejected.committed and rejected.error_code == "social_delivery_source_revision_stale"
    store._stream_heads[stream] -= 1
    assert store.export_snapshot() == before


def test_delivery_rejects_changed_source_payload_without_write():
    store, _ = _store()
    _, stream, event_id = _source(store)
    authority = SocialDeliveryAuthority(store=store)
    assert _record(authority, source_event_id=event_id).committed
    source = store._events_by_id[event_id]
    source.payload["fact_ref"] = "fact:tampered"
    before = store.export_snapshot()
    rejected = authority.expire_delivery(
        delivery_ref="delivery:1", recipient_ref="character:recipient", world_now=20, operational_now=30,
        command_id="expiry-payload-stale", idempotency_key="expiry-payload-stale-key",
        causation_id="c:e", correlation_id="co:e",
    )
    assert not rejected.committed and rejected.error_code == "social_delivery_source_revision_stale"
    assert store.export_snapshot() == before
    assert not authority.view_for(recipient_ref="character:recipient", world_now=15).deliveries


def test_durable_reopen_preserves_delivery_and_replay(tmp_path):
    path = tmp_path / "social.db"
    registry = EventSchemaRegistry()
    register_social_delivery_event_schemas(registry)
    registry.register(EventSchemaRegistration("gameplay.social.knowledge_observed", 1, "sha256:test:knowledge:v1"))
    store = DurableGameplayEventStore(path, event_schema_registry=registry)
    _, _, event_id = _source(store)
    authority = SocialDeliveryAuthority(store=store)
    assert _record(authority, source_event_id=event_id).committed
    store.close()
    reopened_registry = EventSchemaRegistry.from_snapshot(registry.export_snapshot())
    reopened = DurableGameplayEventStore(path, event_schema_registry=reopened_registry)
    reopened_authority = SocialDeliveryAuthority(store=reopened)
    assert reopened_authority.view_for(recipient_ref="character:recipient", world_now=15).deliveries
    duplicate = _record(reopened_authority, source_event_id=event_id)
    assert duplicate.committed and duplicate.error_code == "duplicate_replayed"
    reopened.close()


def test_delivery_view_checkpoint_cut_and_tail_exclude_future_events():
    store, _ = _store()
    _, _, event_id = _source(store)
    authority = SocialDeliveryAuthority(store=store)
    assert _record(authority, source_event_id=event_id).committed
    checkpoint = store.read_events()[-1].global_sequence

    second = _record(
        authority,
        delivery_ref="delivery:2",
        command_id="delivery-2",
        idempotency_key="delivery-key-2",
        source_event_id=event_id,
    )
    assert second.committed

    cut = authority.view_for(recipient_ref="character:recipient", world_now=15, checkpoint_at=checkpoint)
    full = authority.view_for(recipient_ref="character:recipient", world_now=15)
    assert len(cut.deliveries) == 1
    assert len(full.deliveries) == 2
    assert full.deliveries[:1] == cut.deliveries
    assert cut.projection_hash != full.projection_hash

    # A boundary beyond the durable tail is rejected as a future cut by
    # yielding the same historical state, never by reading speculative rows.
    with pytest.raises(ValueError, match="social_delivery_checkpoint_future"):
        authority.view_for(
            recipient_ref="character:recipient", world_now=15,
            checkpoint_at=store.read_events()[-1].global_sequence + 100,
        )


def test_delivery_participant_capture_is_scoped_to_real_recipient_events():
    from app.world_runtime.replay_participants import _social_delivery_participant

    store, _ = _store()
    _, _, event_id = _source(store)
    authority = SocialDeliveryAuthority(store=store)
    assert _record(authority, source_event_id=event_id).committed
    checkpoint = store.read_events()[-1].global_sequence
    assert _record(
        authority,
        delivery_ref="delivery:2",
        command_id="delivery-2",
        idempotency_key="delivery-key-2",
        source_event_id=event_id,
    ).committed

    cut = _social_delivery_participant(
        store, authority, recipient_ref="character:recipient", now=15,
        boundary_sequence=checkpoint,
    )
    full = _social_delivery_participant(
        store, authority, recipient_ref="character:recipient", now=15,
    )
    assert cut is not None and full is not None
    assert len(cut["event_refs"]) == 1
    assert len(full["event_refs"]) == 2
    assert cut["scope"] == "project:social-delivery"


def test_unbound_delivery_participant_only_represents_an_empty_cut():
    from app.world_runtime.replay_participants import _social_delivery_participant

    store, _ = _store()
    _, _, event_id = _source(store)
    authority = SocialDeliveryAuthority(store=store)
    empty = _social_delivery_participant(
        store, authority, recipient_ref=None, now=15,
    )
    assert empty["scope"] == "project:social-delivery-unbound"
    assert empty["recipient_ref"] is None
    assert empty["event_refs"] == [] and empty["projection"] is None

    assert _record(authority, source_event_id=event_id).committed
    with pytest.raises(ValueError, match="replay_social_delivery_scope_unbound"):
        _social_delivery_participant(store, authority, recipient_ref=None, now=15)


@pytest.mark.parametrize("fault", ["stream", "visibility", "schema", "unknown_type", "principal", "persisted"])
def test_delivery_participant_rejects_corrupt_owner_fact_without_write(monkeypatch, fault):
    from app.world_runtime.replay_participants import _social_delivery_participant

    store, _ = _store()
    _, _, source_id = _source(store)
    authority = SocialDeliveryAuthority(store=store)
    assert _record(authority, source_event_id=source_id).committed
    delivery = next(event for event in store.read_events()
                    if event.event_type == "gameplay.social.delivery_recorded@1")
    before = store.export_snapshot()

    if fault == "principal":
        monkeypatch.setattr(store, "transaction_owns_event", lambda **kwargs: False)
    elif fault == "persisted":
        original = store.get_event
        monkeypatch.setattr(store, "get_event", lambda event_id: (
            delivery.model_copy(update={"visibility_policy": "public"})
            if event_id == delivery.event_id else original(event_id)))
    else:
        update = {
            "stream": {"stream_id": "gameplay:social:delivery:wrong"},
            "visibility": {"visibility_policy": "public"},
            "schema": {"schema_version": 2},
            "unknown_type": {"event_type": "gameplay.social.delivery_recalled@2"},
        }[fault]
        original = store.read_events
        monkeypatch.setattr(store, "read_events", lambda *args, **kwargs: [
            event.model_copy(update=update) if event.event_id == delivery.event_id else event
            for event in original(*args, **kwargs)])

    with pytest.raises(ValueError, match="replay_social_delivery_event_provenance_invalid"):
        _social_delivery_participant(
            store, authority, recipient_ref="character:recipient", now=15)
    assert store.export_snapshot() == before
