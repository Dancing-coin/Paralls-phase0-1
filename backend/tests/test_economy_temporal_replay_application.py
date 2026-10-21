"""Application-level Economy temporal participant replay proof."""

from __future__ import annotations

import asyncio
from copy import deepcopy

import pytest

from app.gameplay.event_store import DurableGameplayEventStore
from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.inventory_runtime import InventoryAuthorityService
from app.gameplay.ecology_runtime import EcologyDroughtProcessPolicy
from app.world_runtime.replay_checkpoint import replay_scoped_tail
from test_infra_ecology_drought_state_obligation import _apply as apply_drought_state, STREAM as ECOLOGY_STREAM
from test_infra_ecology_process_lifecycle import _envelope as ecology_envelope, _record as record_ecology_process
from test_world_batch_settlement_application import inputs, submit
from test_world_replay_checkpoint_application import capture, tail_call
from test_status_application_lifecycle import application


async def _submit_runtime(main, callback):
    return await asyncio.wrap_future(main.runtime_execution.submit(callback))


def _open_temporal_obligation(main):
    authority = main.economy_temporal_consumer.authority
    assert authority._store is main.gameplay_event_store
    assert authority.open_account(
        command_id="app:replay:economy:alice",
        account_id="account:app-replay:alice",
        owner_ref="actor:app-replay:alice",
        currency_ref="currency:coin",
        initial_balance=10,
        idempotency_key="app:replay:economy:alice",
        causation_id="cause:app:replay:economy:alice",
        correlation_id="corr:app:replay:economy:alice",
        expected_revision=0,
    ).committed
    assert authority.open_account(
        command_id="app:replay:economy:bob",
        account_id="account:app-replay:bob",
        owner_ref="actor:app-replay:bob",
        currency_ref="currency:coin",
        initial_balance=0,
        idempotency_key="app:replay:economy:bob",
        causation_id="cause:app:replay:economy:bob",
        correlation_id="corr:app:replay:economy:bob",
        expected_revision=1,
    ).committed
    opened = authority.open_scheduled_account_transfer_obligation(
        command_id="app:replay:economy:open",
        transfer_ref="scheduled-transfer:app-replay:1",
        debit_account_id="account:app-replay:alice",
        credit_account_id="account:app-replay:bob",
        amount=3,
        due_tick=main._population_runtime_driver.current_tick,
        idempotency_key="app:replay:economy:open",
        causation_id="cause:app:replay:economy:open",
        correlation_id="corr:app:replay:economy:open",
        expected_revision=2,
    )
    assert opened.committed


@pytest.mark.asyncio
async def test_economy_temporal_application_checkpoint_tail_survives_durable_reopen(application):
    main, start, advance = application
    await start()
    await advance(86400)
    store = main.gameplay_event_store
    assert isinstance(store, DurableGameplayEventStore)
    path = store._snapshot_path

    plan, window = inputs(main)
    partial = await submit(main, plan=plan, window=window, budget=1)
    assert partial.stage == "pending_recovery"

    await _submit_runtime(main, lambda: _open_temporal_obligation(main))
    checkpoint = await capture(main, ref="replay:economy-temporal")
    assert checkpoint.status == "consistent", checkpoint.diagnostics
    saved_participant = checkpoint.checkpoint.state["participants"]["economy_temporal"]
    assert saved_participant["scope"] == "project:economy-temporal"

    # Advance through the application-owned cadence callback so the evidence
    # covers PopulationCadenceDriver -> temporal consumers -> Economy owner.
    await advance(main._population_runtime_driver.current_tick + 1)
    assert main.economy_temporal_consumer.last_errors == ()
    tail = await tail_call(main, checkpoint_ref="replay:economy-temporal")
    assert tail.status == "verified", tail.diagnostics
    assert tail.payload["participants"]["economy_temporal"] != saved_participant
    assert tail.payload["participants"]["economy_temporal"]["state"]["terminal"]

    await main._stop_population_runtime_on_shutdown()
    assert store._closed
    reopened = DurableGameplayEventStore(path)
    restored_authority = EconomyAuthorityService(store=reopened)
    inventory = main.inventory_authority_service
    restored_inventory = InventoryAuthorityService(
        store=reopened, registry=inventory._registry, package_registry=inventory._package_registry)
    try:
        restored = replay_scoped_tail(
            store=reopened,
            checkpoint_ref="replay:economy-temporal",
            tail=tail.payload,
            expected_result_digest=tail.payload["result_digest"],
            inventory_authority=restored_inventory,
        )
        assert restored.status == "verified", restored.diagnostics
        assert restored.result["result_digest"] == restored.result["full_digest"]
        assert restored.result["participants"]["economy_temporal"] == tail.payload["participants"]["economy_temporal"]
        assert restored_authority._store is reopened
    finally:
        reopened.close()


@pytest.mark.asyncio
async def test_economy_and_ecology_share_application_checkpoint_tail_after_durable_restart(application):
    main, start, advance = application
    await start()
    await advance(86400)
    store = main.gameplay_event_store
    assert isinstance(store, DurableGameplayEventStore)
    old_store = store
    old_economy = main.economy_temporal_consumer
    old_ecology = main.ecology_temporal_consumer
    plan, window = inputs(main)
    assert (await submit(main, plan=plan, window=window, budget=1)).stage == "pending_recovery"

    def seed_obligations():
        _open_temporal_obligation(main)
        authority = old_ecology.authority
        record_ecology_process(store)
        assert authority.advance_drought_process(
            envelope=ecology_envelope(command_id="app:replay:joint:drought",
                key="app:replay:joint:drought", expected_revision=5, tick=3),
            policy=EcologyDroughtProcessPolicy(), region_ref="region:process",
        ).committed
        source = next(event for event in reversed(store.read_events())
                      if event.event_type == "gameplay.ecology.drought_process_advanced")
        assert apply_drought_state(authority, expected_revision=store.get_stream_head(ECOLOGY_STREAM),
            source_event_id=source.event_id, source_event_revision=source.stream_revision,
            due_tick=172800).committed

    await _submit_runtime(main, seed_obligations)
    checkpoint = await capture(main, ref="replay:economy-ecology-joint")
    assert checkpoint.status == "consistent", checkpoint.diagnostics
    saved = checkpoint.checkpoint.state["participants"]
    assert {"economy_temporal", "ecology_temporal"} <= set(saved)
    assert saved["economy_temporal"]["state"]["open"]
    assert saved["ecology_temporal"]["state"]["open"]

    await advance(172800)
    assert old_economy.last_errors == () and old_economy.last_results[0].committed
    assert old_ecology.last_errors == () and old_ecology.last_results[0].committed
    tail = await tail_call(main, checkpoint_ref="replay:economy-ecology-joint")
    assert tail.status == "verified", tail.diagnostics
    final = tail.payload["participants"]
    assert {"economy_temporal", "ecology_temporal"} <= set(final)
    assert final["economy_temporal"]["state"]["terminal"]
    assert final["ecology_temporal"]["state"]["terminal"]

    await main._stop_population_runtime_on_shutdown()
    assert old_store._closed
    await start()
    assert main.gameplay_event_store is not old_store
    assert isinstance(main.gameplay_event_store, DurableGameplayEventStore)
    assert main.economy_temporal_consumer is not old_economy
    assert main.ecology_temporal_consumer is not old_ecology
    result = await tail_call(main, tail.payload, checkpoint_ref="replay:economy-ecology-joint")
    assert result.status == "verified", result.diagnostics
    assert result.result["full_digest"] == result.result["result_digest"]
    assert result.result["participants"] == final

    damaged = deepcopy(tail.payload)
    damaged["participants"].pop("ecology_temporal")
    from app.world_runtime.replay_checkpoint import _tail_hash
    damaged["digest"] = _tail_hash(damaged)
    rejected = await tail_call(main, damaged, checkpoint_ref="replay:economy-ecology-joint")
    assert rejected.status == "divergent"
    assert rejected.diagnostics == ("replay_participant_scope_conflict",)


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["missing", "digest", "expired", "revoked", "timeline"])
async def test_economy_application_strict_grant_rejection_is_zero_write(application, monkeypatch, fault):
    from copy import deepcopy
    import json

    main, start, advance = application
    await start()
    await advance(86400)
    driver = main._population_runtime_driver
    assert driver.require_temporal_authorization is True
    await _submit_runtime(main, lambda: _open_temporal_obligation(main))
    pins = await _submit_runtime(main, driver.publish_window.confirmed_time_pins)
    assert pins and pins["temporal_authorizations"]
    bad = deepcopy(pins)
    grants = bad["temporal_authorizations"]
    if isinstance(grants, str):
        grants = json.loads(grants)
    if fault == "missing":
        grants.pop("economy")
    elif fault == "digest":
        grants["economy"]["digest"] = "sha256:tampered"
    elif fault == "expired":
        grants["economy"]["valid_until"] = driver.current_tick - 1
    elif fault == "revoked":
        grants["economy"]["revoked"] = True
    else:
        grants["economy"]["timeline_id"] = "timeline:other"
    bad["temporal_authorizations"] = grants
    monkeypatch.setattr(driver.publish_window, "confirmed_time_pins", lambda: bad)
    before = await _submit_runtime(main, lambda: main.gameplay_event_store.export_snapshot())
    await _submit_runtime(main, lambda: main.economy_temporal_consumer.advance(driver))
    assert main.economy_temporal_consumer.last_errors == (("temporal", "economy_temporal_authorization_rejected"),)
    assert main.economy_temporal_consumer.last_results == ()
    assert await _submit_runtime(main, lambda: main.gameplay_event_store.export_snapshot()) == before
    monkeypatch.undo()
    await _submit_runtime(main, lambda: main.economy_temporal_consumer.advance(driver))
    assert main.economy_temporal_consumer.last_errors == ()
    assert main.economy_temporal_consumer.last_results[0].committed
    assert await _submit_runtime(main, lambda: main.gameplay_event_store.export_snapshot()) != before
