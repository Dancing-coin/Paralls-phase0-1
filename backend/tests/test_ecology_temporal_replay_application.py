"""Ecology expiry through the application cadence and Durable replay ingress."""
from __future__ import annotations

import asyncio
from copy import deepcopy

import pytest

from app.gameplay.ecology_runtime import EcologyDroughtProcessPolicy
from app.gameplay.event_store import DurableGameplayEventStore
from test_infra_ecology_drought_state_obligation import _apply, STREAM
from test_infra_ecology_process_lifecycle import _envelope, _record
from test_status_application_lifecycle import application
from test_world_batch_settlement_application import inputs, submit
from test_world_replay_checkpoint_application import capture, tail_call


async def _runtime(main, callback):
    return await asyncio.wrap_future(main.runtime_execution.submit(callback))


@pytest.mark.asyncio
async def test_ecology_application_cadence_checkpoint_tail_and_durable_new_authority(application):
    main, start, advance = application
    await start()
    await advance(86400)
    store = main.gameplay_event_store
    assert isinstance(store, DurableGameplayEventStore)
    old_consumer = main.ecology_temporal_consumer
    old_authority = old_consumer.authority
    assert old_authority.store is store
    plan, window = inputs(main)
    assert (await submit(main, plan=plan, window=window, budget=1)).stage == "pending_recovery"

    def seed_drought():
        _record(store)
        assert old_authority.advance_drought_process(
            envelope=_envelope(command_id="app:ecology:drought", key="app:ecology:drought",
                               expected_revision=5, tick=3),
            policy=EcologyDroughtProcessPolicy(), region_ref="region:process",
        ).committed
        source = next(event for event in reversed(store.read_events())
                      if event.event_type == "gameplay.ecology.drought_process_advanced")
        assert _apply(old_authority, expected_revision=store.get_stream_head(STREAM),
                      source_event_id=source.event_id, source_event_revision=source.stream_revision,
                      due_tick=172800).committed

    await _runtime(main, seed_drought)
    cut = await capture(main, ref="replay:ecology-application")
    assert cut.status == "consistent", cut.diagnostics
    participant = cut.checkpoint.state["participants"]["ecology_temporal"]
    assert participant["state"]["open"] and not participant["state"]["terminal"]
    await advance(172800)
    assert main.ecology_temporal_consumer.last_errors == ()
    assert len(main.ecology_temporal_consumer.last_results) == 1
    receipt = main.ecology_temporal_consumer.last_results[0]
    assert receipt.committed
    tail = await tail_call(main, checkpoint_ref="replay:ecology-application")
    assert tail.status == "verified", tail.diagnostics
    final_participant = tail.payload["participants"]["ecology_temporal"]
    assert final_participant["state"]["terminal"] and not final_participant["state"]["open"]
    assert set(cut.checkpoint.state["participants"]) == set(tail.payload["participants"])
    assert {item["event_type"] for item in final_participant["event_refs"]} >= {
        "gameplay.ecology.drought_state_expired", "gameplay.ecology.drought_state_obligation_settled"}

    await main._stop_population_runtime_on_shutdown()
    assert store._closed
    await start()
    assert main.gameplay_event_store is not store
    assert isinstance(main.gameplay_event_store, DurableGameplayEventStore)
    assert main.ecology_temporal_consumer is not old_consumer
    assert main.ecology_temporal_consumer.authority is not old_authority
    assert main.ecology_temporal_consumer.authority.store is main.gameplay_event_store
    before = await _runtime(main, lambda: main.gameplay_event_store.export_snapshot())
    replay = await tail_call(main, tail.payload, checkpoint_ref="replay:ecology-application")
    assert replay.status == "verified", replay.diagnostics
    assert replay.result["full_digest"] == replay.result["result_digest"]
    assert replay.result["participants"]["ecology_temporal"] == final_participant
    assert set(replay.result["participants"]) == set(tail.payload["participants"])
    assert (await _runtime(main, lambda: main.gameplay_event_store.export_snapshot())) == before

    damaged = deepcopy(tail.payload)
    damaged["participants"].pop("ecology_temporal")
    from app.world_runtime.replay_checkpoint import _tail_hash
    damaged["digest"] = _tail_hash(damaged)
    rejected = await tail_call(main, damaged, checkpoint_ref="replay:ecology-application")
    assert rejected.status == "divergent" and rejected.result is None
    assert rejected.diagnostics == ("replay_participant_scope_conflict",)
    assert (await _runtime(main, lambda: main.gameplay_event_store.export_snapshot())) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["missing", "digest", "expired", "revoked", "timeline"])
async def test_ecology_application_strict_grant_rejection_is_zero_write(application, monkeypatch, fault):
    """Application cadence pins are the only temporal authorization input."""
    import json

    main, start, advance = application
    await start()
    await advance(86400)
    driver = main._population_runtime_driver
    assert driver.require_temporal_authorization is True

    def seed_drought():
        store = main.gameplay_event_store
        _record(store)
        assert main.ecology_temporal_consumer.authority.advance_drought_process(
            envelope=_envelope(command_id="app:ecology:drought", key="app:ecology:drought",
                               expected_revision=5, tick=3),
            policy=EcologyDroughtProcessPolicy(), region_ref="region:process",
        ).committed
        source = next(event for event in reversed(store.read_events())
                      if event.event_type == "gameplay.ecology.drought_process_advanced")
        assert _apply(main.ecology_temporal_consumer.authority,
                      expected_revision=store.get_stream_head(STREAM),
                      source_event_id=source.event_id, source_event_revision=source.stream_revision,
                      due_tick=driver.current_tick).committed

    await _runtime(main, seed_drought)
    pins = await _runtime(main, driver.publish_window.confirmed_time_pins)
    bad = deepcopy(pins)
    grants = bad["temporal_authorizations"]
    if isinstance(grants, str):
        grants = json.loads(grants)
    if fault == "missing":
        grants.pop("ecology")
    elif fault == "digest":
        grants["ecology"]["digest"] = "sha256:tampered"
    elif fault == "expired":
        grants["ecology"]["valid_until"] = driver.current_tick - 1
    elif fault == "revoked":
        grants["ecology"]["revoked"] = True
    else:
        grants["ecology"]["timeline_id"] = "timeline:other"
    bad["temporal_authorizations"] = grants
    monkeypatch.setattr(driver.publish_window, "confirmed_time_pins", lambda: bad)
    before = await _runtime(main, lambda: main.gameplay_event_store.export_snapshot())
    await _runtime(main, lambda: main.ecology_temporal_consumer.advance(driver))
    assert main.ecology_temporal_consumer.last_errors == (("temporal", "ecology_temporal_authorization_rejected"),)
    assert main.ecology_temporal_consumer.last_results == ()
    assert await _runtime(main, lambda: main.gameplay_event_store.export_snapshot()) == before

    monkeypatch.undo()
    await _runtime(main, lambda: main.ecology_temporal_consumer.advance(driver))
    assert main.ecology_temporal_consumer.last_errors == ()
    assert main.ecology_temporal_consumer.last_results[0].committed

    assert await _runtime(main, lambda: main.gameplay_event_store.export_snapshot()) != before


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["issuer", "boundary", "missing_issuer", "missing_sample"])
async def test_ecology_application_rejects_rebound_grant_even_with_recomputed_digest(application, monkeypatch, fault):
    """A grant must remain bound to the cadence record that issued its window."""
    import json
    from app.world_runtime.temporal_contracts import TemporalAuthorization

    main, start, advance = application
    await start()
    await advance(86400)
    driver = main._population_runtime_driver
    pins = await _runtime(main, driver.publish_window.confirmed_time_pins)
    bad = deepcopy(pins)
    grants = json.loads(bad["temporal_authorizations"])
    grant = dict(grants["ecology"])
    if fault == "issuer":
        grant["issuer_ref"] = "world_runtime.population_cadence:forged"
    elif fault == "missing_issuer":
        bad.pop("temporal_authorization_issuer_ref")
    elif fault == "missing_sample":
        bad.pop("sampled_at")
    else:
        bad["sampled_at"] = driver.current_tick + 1
        bad["confirmation_boundary"] = driver.current_tick + 1
    auth = TemporalAuthorization(
        authorization_ref=grant["authorization_ref"], revision=grant["revision"],
        issuer_ref=grant["issuer_ref"], timeline_id=grant["timeline_id"],
        participant_scope=tuple(grant["participant_scope"]), input_cutoff=grant["input_cutoff"],
        confirmation_boundary=grant["confirmation_boundary"],
        late_input_policy_ref=grant["late_input_policy_ref"],
        ordering_policy_ref=grant["ordering_policy_ref"], valid_until=grant["valid_until"],
    )
    grant["digest"] = auth.digest
    grants["ecology"] = grant
    bad["temporal_authorizations"] = grants
    monkeypatch.setattr(driver.publish_window, "confirmed_time_pins", lambda: bad)
    before = await _runtime(main, lambda: main.gameplay_event_store.export_snapshot())
    await _runtime(main, lambda: main.ecology_temporal_consumer.advance(driver))
    assert main.ecology_temporal_consumer.last_errors == (("temporal", "ecology_temporal_authorization_rejected"),)
    assert main.ecology_temporal_consumer.last_results == ()
    assert await _runtime(main, lambda: main.gameplay_event_store.export_snapshot()) == before
