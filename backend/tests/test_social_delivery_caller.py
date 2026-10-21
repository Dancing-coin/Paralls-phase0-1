import pytest
import asyncio

from app.gameplay.p5.social_delivery_caller import GovernmentPublicMillingSocialDeliveryCaller
from app.gameplay.event_store import DurableGameplayEventStore
from app.gameplay.p5.social_delivery import SocialDeliveryAuthority
from app.world_runtime.replay_participants import _social_delivery_participant
from app.world_runtime.temporal_contracts import TemporalAuthorization
from test_inf4ao_public_milling_social_ack import _notice
from test_status_application_lifecycle import application


def _pins(tick: int = 10) -> dict[str, object]:
    grant = TemporalAuthorization(
        authorization_ref="authorization:population-social@1",
        revision="authorization:population-temporal@1",
        issuer_ref="world_runtime.population_cadence:bakery",
        timeline_id="timeline:bakery",
        participant_scope=("authority:p5:social-delivery",),
        input_cutoff=tick,
        confirmation_boundary=tick,
        late_input_policy_ref="reject_after_cutoff",
        ordering_policy_ref="source_revision_then_event_ref",
        valid_until=tick,
    )
    return {
        "timeline_id": "timeline:bakery",
        "sampled_at": tick,
        "received_at": tick,
        "temporal_authorization_issuer_ref": grant.issuer_ref,
        "confirmation_boundary": tick,
        "input_cutoff": tick,
        "temporal_authorizations": {
            "social": {**grant.payload(), "digest": grant.digest},
        },
    }


def _explicit_window_adapter(caller, **request):
    """Owner/adapter fixture only; this is not admitted production window policy."""
    request.setdefault("operational_now", None)
    return caller._deliver_notice(
        **request, recipient_ref=caller._bound_receiver(caller.store.get_event(request["notice_event_id"])),
        world_now=5, effective_from=5, effective_to=10, operational_cutoff=None,
    )


def test_government_notice_without_authored_validity_is_rejected_without_write():
    store, notice = _notice()
    caller = GovernmentPublicMillingSocialDeliveryCaller(store=store)
    forged = notice.model_copy(update={"payload": {key: value for key, value in notice.payload.items() if key not in {"effective_from", "effective_to", "validity_policy_revision"}}}, deep=True)
    store._events_by_id[notice.event_id] = forged
    store._events = [forged if item.event_id == notice.event_id else item for item in store._events]
    before = store.export_snapshot()
    result = caller.deliver_bound_receiver_notice(
        notice_event_id=notice.event_id, temporal_pins=_pins(5),
        command_id="missing-policy", idempotency_key="missing-policy",
        causation_id=notice.event_id, correlation_id="missing-policy",
    )
    assert not result.result.committed
    assert result.result.error_code == "social_delivery_temporal_policy_missing"
    assert store.export_snapshot() == before


def test_government_notice_with_authored_validity_commits_through_production_caller():
    store, notice = _notice()
    caller = GovernmentPublicMillingSocialDeliveryCaller(store=store)
    result = caller.deliver_bound_receiver_notice(
        notice_event_id=notice.event_id, temporal_pins=_pins(5),
        command_id="social-production:valid", idempotency_key="social-production:valid",
        causation_id=notice.event_id, correlation_id="social-production:valid",
    )
    assert result.result.committed
    assert result.result.append_result is not None
    assert len(result.result.append_result.committed_event_ids) == 1


def test_government_notice_production_caller_recovers_after_lost_append_response(monkeypatch):
    store, notice = _notice()
    caller = GovernmentPublicMillingSocialDeliveryCaller(store=store)
    original_append = store.append_batch
    calls = {"count": 0}

    def append_then_lose_response(batch):
        calls["count"] += 1
        result = original_append(batch)
        if calls["count"] == 1:
            raise TimeoutError("response lost after commit")
        return result

    monkeypatch.setattr(store, "append_batch", append_then_lose_response)
    with pytest.raises(TimeoutError, match="response lost after commit"):
        caller.deliver_bound_receiver_notice(
            notice_event_id=notice.event_id, temporal_pins=_pins(5),
            command_id="social-production:lost", idempotency_key="social-production:lost",
            causation_id=notice.event_id, correlation_id="social-production:lost",
        )
    monkeypatch.setattr(store, "append_batch", original_append)
    retry = caller.deliver_bound_receiver_notice(
        notice_event_id=notice.event_id, temporal_pins=_pins(5),
        command_id="social-production:lost", idempotency_key="social-production:lost",
        causation_id=notice.event_id, correlation_id="social-production:lost",
    )
    assert retry.result.committed and retry.result.error_code == "duplicate_replayed"
    assert len(store.read_events(event_type="gameplay.social.delivery_recorded@1")) == 1


def test_government_notice_expiry_uses_bound_source_and_replays_changed_duplicates():
    store, notice = _notice(effective_from=5, effective_to=10)
    caller = GovernmentPublicMillingSocialDeliveryCaller(store=store)
    delivered = caller.deliver_bound_receiver_notice(
        notice_event_id=notice.event_id, temporal_pins=_pins(5),
        command_id="social-expiry:deliver", idempotency_key="social-expiry:deliver",
        causation_id=notice.event_id, correlation_id="social-expiry",
    )
    assert delivered.result.committed
    first = caller.expire_bound_receiver_notice(
        notice_event_id=notice.event_id, temporal_pins=_pins(10),
        command_id="social-expiry:expire", idempotency_key="social-expiry:expire",
        causation_id=notice.event_id, correlation_id="social-expiry",
    )
    assert first.result.committed
    duplicate = caller.expire_bound_receiver_notice(
        notice_event_id=notice.event_id, temporal_pins=_pins(10),
        command_id="social-expiry:expire", idempotency_key="social-expiry:expire",
        causation_id=notice.event_id, correlation_id="social-expiry",
    )
    assert duplicate.result.committed and duplicate.result.error_code == "duplicate_replayed"
    changed = caller.expire_bound_receiver_notice(
        notice_event_id=notice.event_id, temporal_pins=_pins(10),
        command_id="social-expiry:changed", idempotency_key="social-expiry:expire",
        causation_id=notice.event_id, correlation_id="social-expiry",
    )
    assert not changed.result.committed and changed.result.error_code == "idempotency_key_reused"


def test_government_notice_expiry_rejects_before_world_window_closes_without_write():
    store, notice = _notice(effective_from=5, effective_to=10)
    caller = GovernmentPublicMillingSocialDeliveryCaller(store=store)
    caller.deliver_bound_receiver_notice(
        notice_event_id=notice.event_id, temporal_pins=_pins(5),
        command_id="social-expiry:early-deliver", idempotency_key="social-expiry:early-deliver",
        causation_id=notice.event_id, correlation_id="social-expiry:early",
    )
    before = store.export_snapshot()
    rejected = caller.expire_bound_receiver_notice(
        notice_event_id=notice.event_id, temporal_pins=_pins(9),
        command_id="social-expiry:early", idempotency_key="social-expiry:early",
        causation_id=notice.event_id, correlation_id="social-expiry:early",
    )
    assert not rejected.result.committed
    assert rejected.result.error_code == "social_delivery_world_window_open"
    assert store.export_snapshot() == before


def test_government_notice_expiry_recovers_lost_response(monkeypatch):
    store, notice = _notice(effective_from=5, effective_to=10)
    caller = GovernmentPublicMillingSocialDeliveryCaller(store=store)
    caller.deliver_bound_receiver_notice(
        notice_event_id=notice.event_id, temporal_pins=_pins(5),
        command_id="social-expiry:lost-deliver", idempotency_key="social-expiry:lost-deliver",
        causation_id=notice.event_id, correlation_id="social-expiry:lost",
    )
    original_append = store.append_batch
    calls = {"count": 0}
    def append_then_lose(batch):
        calls["count"] += 1
        result = original_append(batch)
        if calls["count"] == 1:
            raise TimeoutError("response lost after commit")
        return result
    monkeypatch.setattr(store, "append_batch", append_then_lose)
    with pytest.raises(TimeoutError):
        caller.expire_bound_receiver_notice(
            notice_event_id=notice.event_id, temporal_pins=_pins(10),
            command_id="social-expiry:lost", idempotency_key="social-expiry:lost",
            causation_id=notice.event_id, correlation_id="social-expiry:lost",
        )
    monkeypatch.setattr(store, "append_batch", original_append)
    retry = caller.expire_bound_receiver_notice(
        notice_event_id=notice.event_id, temporal_pins=_pins(10),
        command_id="social-expiry:lost", idempotency_key="social-expiry:lost",
        causation_id=notice.event_id, correlation_id="social-expiry:lost",
    )
    assert retry.result.committed and retry.result.error_code == "duplicate_replayed"


@pytest.mark.asyncio
async def test_application_social_ingress_uses_current_driver_boundary(application):
    main, start, advance = application
    await start()
    await advance(86400)
    driver = main._population_runtime_driver
    caller = main.social_delivery_caller
    original = driver.publish_window.confirmed_time_pins
    current = original()
    current["sampled_at"] = driver.current_tick + 1
    current["confirmation_boundary"] = driver.current_tick + 1
    driver.publish_window.confirmed_time_pins = lambda: current
    before = await asyncio.wrap_future(main.runtime_execution.submit(
        lambda: main.gameplay_event_store.export_snapshot()))
    try:
        result = await asyncio.wrap_future(main.submit_social_delivery(
            notice_event_id="missing-notice", command_id="stale-ingress",
            idempotency_key="stale-ingress", causation_id="stale-ingress",
            correlation_id="stale-ingress"))
        assert result is None
    except ValueError as exc:
        assert str(exc) == "social_delivery_temporal_pins_stale"
    after = await asyncio.wrap_future(main.runtime_execution.submit(
        lambda: main.gameplay_event_store.export_snapshot()))
    assert after == before
    assert main.social_delivery_caller is caller
    driver.publish_window.confirmed_time_pins = original


@pytest.mark.asyncio
async def test_application_social_ingress_commits_bound_delivery_from_durable_source(application):
    """The application ingress must consume an authored Government source in its own store."""
    main, start, advance = application
    await start()
    await advance(86400)
    source_store, notice = _notice(effective_from=86400, effective_to=172800)

    def import_source_transactions():
        for transaction in source_store.read_transactions():
            result = main.gameplay_event_store.append_batch(transaction)
            assert result.committed, result.failure

    await asyncio.wrap_future(main.runtime_execution.submit(import_source_transactions))
    result = await asyncio.wrap_future(main.submit_social_delivery(
        notice_event_id=notice.event_id,
        command_id="social-application:bound-delivery",
        idempotency_key="social-application:bound-delivery",
        causation_id=notice.event_id,
        correlation_id="social-application:bound-delivery",
    ))
    assert result is not None and result.result.committed
    assert result.source_event_id == notice.event_id
    recipient = main.social_delivery_caller._bound_receiver(
        main.gameplay_event_store.get_event(notice.event_id)
    )
    assert recipient == "org:mill:1"
    events = main.gameplay_event_store.read_events(
        event_type="gameplay.social.delivery_recorded@1"
    )
    assert len(events) == 1
    assert events[0].payload["recipient_ref"] == recipient
    await advance(172800)
    expired = await asyncio.wrap_future(main.submit_social_delivery_expiry(
        notice_event_id=notice.event_id,
        command_id="social-application:bound-expiry",
        idempotency_key="social-application:bound-expiry",
        causation_id=notice.event_id,
        correlation_id="social-application:bound-expiry",
    ))
    assert expired.result.committed
    expiry_events = main.gameplay_event_store.read_events(
        event_type="gameplay.social.delivery_expired@1"
    )
    assert len(expiry_events) == 1
    assert expiry_events[0].payload["world_now"] == 172800


def test_private_source_adapter_receipt_with_explicit_test_window():
    store, notice = _notice()
    caller = GovernmentPublicMillingSocialDeliveryCaller(store=store)
    forged = notice.model_copy(update={"payload": {key: value for key, value in notice.payload.items() if key not in {"effective_from", "effective_to", "validity_policy_revision"}}}, deep=True)
    store._events_by_id[notice.event_id] = forged
    store._events = [forged if item.event_id == notice.event_id else item for item in store._events]
    assert not hasattr(caller, "deliver_notice")
    request = dict(
        notice_event_id=notice.event_id,
        operational_now=None,
        temporal_pins=_pins(5),
        command_id="social-caller:1",
        idempotency_key="social-caller:key",
        causation_id=notice.event_id,
        correlation_id="social-caller:corr",
    )
    first = _explicit_window_adapter(caller, **request)
    assert first.result.committed
    before = store.export_snapshot()
    duplicate = _explicit_window_adapter(caller, **request)
    assert duplicate.result.committed and duplicate.result.error_code == "duplicate_replayed"
    assert store.export_snapshot() == before


def test_government_notice_caller_rejects_world_tick_not_bound_to_cadence_grant():
    store, notice = _notice()
    caller = GovernmentPublicMillingSocialDeliveryCaller(store=store)
    before = store.export_snapshot()
    stale_pins = _pins(5)
    stale_pins["sampled_at"] = 4
    rejected = caller.deliver_bound_receiver_notice(
        notice_event_id=notice.event_id,
        operational_now=None,
        temporal_pins=stale_pins,
        command_id="social-caller:stale-world-tick",
        idempotency_key="social-caller:stale-world-tick-key",
        causation_id=notice.event_id,
        correlation_id="social-caller:stale-world-tick-corr",
    )
    assert not rejected.result.committed
    assert rejected.result.error_code == "social_delivery_temporal_source_invalid"
    assert store.export_snapshot() == before


def test_government_notice_caller_rejects_stale_or_invalid_source_before_owner():
    store, notice = _notice()
    caller = GovernmentPublicMillingSocialDeliveryCaller(store=store)
    request = dict(
        notice_event_id=notice.event_id,
        operational_now=None,
        temporal_pins=_pins(5),
        command_id="social-caller:2",
        idempotency_key="social-caller:key-2",
        causation_id=notice.event_id,
        correlation_id="social-caller:corr-2",
    )
    store._stream_heads[notice.stream_id] = notice.stream_revision + 1
    before = store.export_snapshot()
    rejected = caller.deliver_bound_receiver_notice(**request)
    assert not rejected.result.committed
    assert rejected.result.error_code == "social_delivery_notice_source_stale"
    assert store.export_snapshot() == before


def test_bound_receiver_does_not_supply_missing_notice_validity():
    store, notice = _notice()
    caller = GovernmentPublicMillingSocialDeliveryCaller(store=store)
    forged = notice.model_copy(update={"payload": {key: value for key, value in notice.payload.items() if key not in {"effective_from", "effective_to", "validity_policy_revision"}}}, deep=True)
    store._events_by_id[notice.event_id] = forged
    store._events = [forged if item.event_id == notice.event_id else item for item in store._events]
    request = dict(
        notice_event_id=notice.event_id,
        temporal_pins=_pins(5),
        command_id="social-bound:1",
        idempotency_key="social-bound:key",
        causation_id=notice.event_id,
        correlation_id="social-bound:corr",
    )
    selected = caller._bound_receiver(notice)
    assert selected is not None and selected.startswith(("organization:", "org:"))
    before = store.export_snapshot()
    result = caller.deliver_bound_receiver_notice(**request)
    assert not result.result.committed
    assert result.result.error_code == "social_delivery_temporal_policy_missing"
    assert store.export_snapshot() == before


def test_government_notice_bounded_delivery_rejects_a_caller_selected_world_window():
    store, notice = _notice()
    caller = GovernmentPublicMillingSocialDeliveryCaller(store=store)

    with pytest.raises(TypeError):
        caller.deliver_bound_receiver_notice(
            notice_event_id=notice.event_id,
            world_now=5,
            operational_now=10,
            effective_from=1,
            effective_to=100,
            operational_cutoff=10,
            temporal_pins=_pins(5),
            command_id="social-bound:untrusted-window",
            idempotency_key="social-bound:untrusted-window-key",
            causation_id=notice.event_id,
            correlation_id="social-bound:untrusted-window-corr",
        )


def test_government_notice_bound_receiver_rejects_changed_party_binding_without_write():
    store, notice = _notice()
    caller = GovernmentPublicMillingSocialDeliveryCaller(store=store)
    created_id = notice.payload["source_contract_created_event_id"]
    created = store._events_by_id[created_id]
    created.payload["party_refs"] = [notice.payload["organization_ref"], "org:tampered"]
    before = store.export_snapshot()
    rejected = caller.deliver_bound_receiver_notice(
        notice_event_id=notice.event_id, temporal_pins=_pins(5), command_id="social-bound:tampered",
        idempotency_key="social-bound:tampered-key", causation_id=notice.event_id,
        correlation_id="social-bound:tampered-corr",
    )
    assert not rejected.result.committed
    assert rejected.result.error_code == "social_delivery_recipient_binding_invalid"
    assert store.export_snapshot() == before


def test_government_production_caller_checkpoint_tail_survives_durable_new_authority(tmp_path):
    source_store, notice = _notice()
    path = tmp_path / "government-social-delivery.db"
    durable = DurableGameplayEventStore(path)
    # Copy committed source transactions through the supported append API so
    # Government, contract and facility facts are present in the Durable store.
    for batch in source_store.read_transactions():
        assert durable.append_batch(batch).committed
    durable_caller = GovernmentPublicMillingSocialDeliveryCaller(store=durable)
    delivered = durable_caller.deliver_bound_receiver_notice(
        notice_event_id=notice.event_id, temporal_pins=_pins(5), command_id="social-durable:deliver",
        idempotency_key="social-durable:deliver:key", causation_id=notice.event_id,
        correlation_id="social-durable:deliver:corr",
    )
    assert delivered.result.committed
    recipient = durable_caller._bound_receiver(durable.get_event(notice.event_id))
    assert recipient
    checkpoint = durable.get_last_global_sequence()
    authority = durable_caller.authority
    captured = _social_delivery_participant(
        durable, authority, recipient_ref=recipient, now=5,
        boundary_sequence=checkpoint,
    )
    assert captured is not None and len(captured["event_refs"]) == 1

    expiry = authority.expire_delivery(
        delivery_ref=f"social-delivery:{notice.event_id}:{recipient}",
        recipient_ref=recipient, world_now=10, operational_now=10,
        command_id="social-durable:expire", idempotency_key="social-durable:expire:key",
        causation_id=notice.event_id, correlation_id="social-durable:expire:corr",
    )
    assert expiry.committed
    tail_view = authority.view_for(recipient_ref=recipient, world_now=5, checkpoint_at=checkpoint)
    full_view = authority.view_for(recipient_ref=recipient, world_now=5)
    assert len(tail_view.deliveries) == 1
    assert full_view.deliveries == ()

    durable.close()
    reopened = DurableGameplayEventStore(path)
    reopened_authority = SocialDeliveryAuthority(store=reopened)
    reopened_caller = GovernmentPublicMillingSocialDeliveryCaller(store=reopened, authority=reopened_authority)
    # Recovery uses the persisted source and delivery facts after a real
    # Durable close/reopen. This test does not manufacture a stream head by
    # mutating private in-memory state.
    before_retry = reopened.export_snapshot()
    retry = reopened_caller.deliver_bound_receiver_notice(
        notice_event_id=notice.event_id, temporal_pins=_pins(10), command_id="social-durable:deliver",
        idempotency_key="social-durable:deliver:key", causation_id=notice.event_id,
        correlation_id="social-durable:deliver:corr",
    )
    assert retry.result.committed and retry.result.error_code == "duplicate_replayed"
    changed = reopened_caller.deliver_bound_receiver_notice(
        notice_event_id=notice.event_id, temporal_pins=_pins(10), command_id="social-durable:changed",
        idempotency_key="social-durable:deliver:key", causation_id=notice.event_id,
        correlation_id="social-durable:deliver:corr",
    )
    assert not changed.result.committed and changed.result.error_code == "idempotency_key_reused"
    assert reopened.export_snapshot() == before_retry
    reopened_cut = reopened_authority.view_for(
        recipient_ref=recipient, world_now=5, checkpoint_at=checkpoint,
    )
    reopened_full = reopened_authority.view_for(recipient_ref=recipient, world_now=5)
    replayed = _social_delivery_participant(
        reopened, reopened_authority, recipient_ref=recipient, now=5,
    )
    assert reopened_cut == tail_view
    assert reopened_full == full_view
    assert replayed is not None and len(replayed["event_refs"]) == 2
    reopened.close()
