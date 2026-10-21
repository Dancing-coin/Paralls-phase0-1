"""Private Economy random facts in the bounded replay participant cut."""

from copy import deepcopy
import asyncio
import json

import pytest

from app.gameplay.event_store import DurableGameplayEventStore
from app.gameplay.ecology_runtime import EcologyDroughtProcessPolicy
from app.world_runtime.replay_checkpoint import _manifest, _tail_hash
from app.world_runtime.replay_participants import (
    _ecology_temporal_participant, _economy_random_participant, _economy_temporal_participant,
    _validate_ecology_temporal_participant, _validate_economy_random_participant,
    _validate_economy_temporal_participant,
)
from test_economy_random_owner import _draw
from test_status_application_lifecycle import application
from test_world_batch_settlement_application import inputs, submit
from test_world_replay_checkpoint_application import capture, tail_call
from test_equipment_replay_participant import ACTOR as EQUIPMENT_ACTOR, _prepare_equipment, _unequip
from test_resource_replay_participant import _reservation, _run
from test_economy_temporal_replay_application import _open_temporal_obligation
from test_infra_ecology_drought_state_obligation import _apply as apply_drought_state, STREAM as ECOLOGY_STREAM
from test_infra_ecology_process_lifecycle import _envelope as ecology_envelope, _record as record_ecology_process
from test_population_activation_presence_service import _proposal as presence_proposal, _service_with_store as presence_service
from test_life_state_case_death_caller import _seed as seed_case_death
from app.gameplay.life_state_runtime import CaseDeathLifeStateCaller
from app.population_continuity.presence_runtime import CharacterDespawnRequest, PopulationPresenceAuthority


def _saved_manifest(random):
    value = {
        "schema_version": 1,
        "versions": {"participant_manifest": 1, "batch_input": 1, "batch_operation": 1,
                     "population_recovery": 1, "status_events": 1, "migration_events": 1,
                     "economy_random": 1},
        "batches": [], "population": {"schema_version": 1},
        "status": {"schema_version": 1}, "migration": {"schema_version": 1},
        "external_dependencies": {}, "random_context": {}, "economy_random": random,
    }
    return _manifest(value, ())


def test_empty_temporal_and_random_participants_preserve_legacy_absence(tmp_path):
    store = DurableGameplayEventStore(tmp_path / "empty-participants.sqlite3")
    participants = (
        (_economy_temporal_participant, _validate_economy_temporal_participant),
        (_ecology_temporal_participant, _validate_ecology_temporal_participant),
        (_economy_random_participant, _validate_economy_random_participant),
    )
    before = store.export_snapshot()
    for capture_participant, validate_participant in participants:
        saved = capture_participant(store)
        assert saved["event_refs"] == []
        validate_participant(store, None)
        validate_participant(store, saved)
        damaged = deepcopy(saved)
        damaged["view_digest"] = "sha256:tampered"
        with pytest.raises(ValueError):
            validate_participant(store, damaged)
    assert store.export_snapshot() == before
    store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("domain", ["economy_temporal", "ecology_temporal", "economy_random"])
async def test_first_owner_fact_after_empty_cut_replays_after_durable_reopen(application, domain):
    main, start, advance = application
    await start()
    await advance(86400)
    plan, window = inputs(main)
    assert (await submit(main, plan=plan, window=window, budget=1)).receipts
    cut = await capture(main, ref=f"replay:first:{domain}")
    assert cut.status == "consistent", cut.diagnostics

    def first_write():
        if domain == "economy_temporal":
            _open_temporal_obligation(main)
        elif domain == "ecology_temporal":
            authority = main.ecology_temporal_consumer.authority
            record_ecology_process(main.gameplay_event_store)
            assert authority.advance_drought_process(
                envelope=ecology_envelope(command_id="first:drought", key="first:drought",
                    expected_revision=5, tick=3),
                policy=EcologyDroughtProcessPolicy(), region_ref="region:process",
            ).committed
        else:
            assert _draw(main.gameplay_event_store, "first-after-cut").committed

    await asyncio.wrap_future(main.runtime_execution.submit(first_write))
    tail = await tail_call(main, checkpoint_ref=f"replay:first:{domain}")
    assert tail.status == "verified", tail.diagnostics

    await main._stop_population_runtime_on_shutdown()
    await start()
    before = await asyncio.wrap_future(main.runtime_execution.submit(
        lambda: main.gameplay_event_store.export_snapshot()))
    replay = await tail_call(main, tail.payload, checkpoint_ref=f"replay:first:{domain}")
    assert replay.status == "verified", replay.diagnostics
    assert cut.checkpoint.state["participants"][domain]["event_refs"] == []
    assert tail.payload["participants"][domain]["event_refs"]
    if domain == "economy_random":
        assert cut.checkpoint.state["participants"]["random_context"]["status"] == "not_applicable"
        assert tail.payload["participants"]["random_context"]["status"] == "bounded_owner_result"
        assert tail.payload["participants"]["random_context"]["t07"] == "not_verified"
        assert "seed" not in json.dumps(tail.payload["participants"][domain])
    assert replay.result["full_digest"] == replay.result["result_digest"]
    assert await asyncio.wrap_future(main.runtime_execution.submit(
        lambda: main.gameplay_event_store.export_snapshot())) == before


def test_random_owner_scoped_projection_is_private_and_survives_durable_reopen(tmp_path):
    path = tmp_path / "random-replay.sqlite3"
    store = DurableGameplayEventStore(path)
    assert _draw(store, "first").committed
    cut = store.get_last_global_sequence()
    saved = _economy_random_participant(store, boundary_sequence=cut)
    assert saved is not None
    assert saved["scope"] == "project:economy-random-private"
    assert saved["result_count"] == 1
    assert "seed" not in json.dumps(saved)
    _saved_manifest(saved)
    assert _draw(store, "second").committed
    current = _economy_random_participant(store)
    assert current["result_count"] == 2
    _validate_economy_random_participant(store, saved, boundary_sequence=cut)
    _validate_economy_random_participant(store, current)
    before = store.export_snapshot()
    store.close()
    reopened = DurableGameplayEventStore(path)
    assert _economy_random_participant(reopened) == current
    _validate_economy_random_participant(reopened, saved, boundary_sequence=cut)
    assert reopened.export_snapshot() == before
    reopened.close()


@pytest.mark.parametrize("fault", ["refs", "state", "missing", "version"])
def test_random_scoped_projection_rejects_changed_manifest_without_write(tmp_path, fault):
    store = DurableGameplayEventStore(tmp_path / "random-invalid.sqlite3")
    assert _draw(store, "first").committed
    saved = _economy_random_participant(store)
    bad = deepcopy(saved)
    if fault == "refs":
        bad["event_refs"][0]["event_digest"] = "changed"
    elif fault == "state":
        bad["result_digests"]["first"] = "changed"
    elif fault == "missing":
        bad = None
    else:
        value = _saved_manifest(saved)
        del value["versions"]["economy_random"]
        with pytest.raises(ValueError):
            _manifest(value, ())
        store.close()
        return
    before = store.export_snapshot()
    with pytest.raises(ValueError):
        _validate_economy_random_participant(store, bad)
    assert store.export_snapshot() == before
    store.close()


def test_random_scoped_projection_accepts_cut_between_anchor_and_result(tmp_path):
    store = DurableGameplayEventStore(tmp_path / "anchor-cut.sqlite3")
    assert _draw(store, "first").committed
    anchor = next(event for event in store.read_events()
                  if event.event_type.endswith("random_entropy_anchor_created@1"))
    saved = _economy_random_participant(store, boundary_sequence=anchor.global_sequence)
    assert saved["result_count"] == 0
    assert len(saved["event_refs"]) == 1
    _validate_economy_random_participant(store, saved, boundary_sequence=anchor.global_sequence)
    store.close()


@pytest.mark.parametrize("fault", ["stream", "schema", "visibility", "payload", "persisted"])
def test_random_scoped_projection_rejects_corrupt_owner_event_without_write(tmp_path, monkeypatch, fault):
    store = DurableGameplayEventStore(tmp_path / "random-corrupt.sqlite3")
    assert _draw(store, "first").committed
    result = next(event for event in store.read_events()
                  if event.event_type.endswith("random_result_committed@1"))
    before = store.export_snapshot()
    if fault == "persisted":
        original = store.get_event
        monkeypatch.setattr(store, "get_event", lambda event_id: (
            result.model_copy(update={"visibility_policy": "public"})
            if event_id == result.event_id else original(event_id)))
    else:
        updates = {"stream": {"stream_id": "gameplay:wrong"},
                   "schema": {"schema_version": 99},
                   "visibility": {"visibility_policy": "public"},
                   "payload": {"payload": {**result.payload, "anchor_ref": "missing-anchor"}}}[fault]
        original = store.read_events
        monkeypatch.setattr(store, "read_events", lambda *args, **kwargs: [
            event.model_copy(update=updates) if event.event_id == result.event_id else event
            for event in original(*args, **kwargs)])
    with pytest.raises(ValueError):
        _economy_random_participant(store)
    assert store.export_snapshot() == before
    store.close()


@pytest.mark.parametrize("unknown_type", ["gameplay.economy.random_result_committed@2",
                                          "gameplay.economy.random_entropy_anchor_created@2"])
def test_random_scoped_projection_rejects_unknown_random_event_without_write(tmp_path, monkeypatch, unknown_type):
    store = DurableGameplayEventStore(tmp_path / "random-unknown.sqlite3")
    assert _draw(store, "first").committed
    original = store.read_events
    event = next(row for row in original() if row.event_type.endswith("random_result_committed@1"))
    before = store.export_snapshot()
    monkeypatch.setattr(store, "read_events", lambda *args, **kwargs: [
        row.model_copy(update={"event_type": unknown_type}) if row.event_id == event.event_id else row
        for row in original(*args, **kwargs)])
    with pytest.raises(ValueError, match="replay_economy_random_event_scope_invalid"):
        _economy_random_participant(store)
    assert store.export_snapshot() == before
    store.close()


@pytest.mark.asyncio
async def test_application_random_owner_participates_in_durable_cut_and_tail(application):
    main, start, advance = application
    await start()
    await advance(86400)
    plan, window = inputs(main)
    assert (await submit(main, plan=plan, window=window, budget=0)).receipts
    first = await asyncio.wrap_future(main.runtime_execution.submit(
        lambda: _draw(main.gameplay_event_store, "application-first")))
    assert first.committed
    cut = await capture(main)
    assert cut.status == "consistent", cut.diagnostics
    random = cut.checkpoint.state["participants"]["economy_random"]
    assert random["result_count"] == 1
    assert cut.checkpoint.state["participants"]["versions"]["economy_random"] == 1
    assert cut.checkpoint.state["participants"]["random_context"]["status"] == "bounded_owner_result"
    assert "seed" not in json.dumps(random)
    second = await asyncio.wrap_future(main.runtime_execution.submit(
        lambda: _draw(main.gameplay_event_store, "application-second")))
    assert second.committed
    tail = await tail_call(main)
    assert tail.status == "verified", tail.diagnostics
    assert tail.payload["participants"]["economy_random"]["result_count"] == 2
    await main._stop_population_runtime_on_shutdown()
    await start()
    before = await asyncio.wrap_future(main.runtime_execution.submit(
        lambda: main.gameplay_event_store.export_snapshot()))
    resumed = await tail_call(main, tail.payload)
    assert resumed.status == "verified", resumed.diagnostics
    assert await asyncio.wrap_future(main.runtime_execution.submit(
        lambda: main.gameplay_event_store.export_snapshot())) == before


@pytest.mark.asyncio
async def test_shared_cut_replays_ten_domain_participants_after_cadence_and_restart(application):
    from app.gameplay.inventory_runtime import ItemDefinition
    from app.gameplay.p5.social_delivery import SocialDeliveryWindow
    from app.population_continuity.social_owner_adapter import SocialPopulationSignalOwnerExecutor
    from app.services.siming_population_capability import PopulationSimulationCapability
    from test_siming_population_social_signal_vertical import _read_set

    main, start, advance = await _prepare_equipment(application)
    def seed_temporal():
        _open_temporal_obligation(main)
        store = main.gameplay_event_store
        authority = main.ecology_temporal_consumer.authority
        record_ecology_process(store)
        assert authority.advance_drought_process(
            envelope=ecology_envelope(command_id="joint:drought", key="joint:drought",
                expected_revision=5, tick=3),
            policy=EcologyDroughtProcessPolicy(), region_ref="region:process").committed
        source = next(event for event in reversed(store.read_events())
                      if event.event_type == "gameplay.ecology.drought_process_advanced")
        assert apply_drought_state(authority, expected_revision=store.get_stream_head(ECOLOGY_STREAM),
            source_event_id=source.event_id, source_event_revision=source.stream_revision,
            due_tick=172800).committed
    await _run(main, seed_temporal)
    def seed_presence():
        store = main.gameplay_event_store
        _, service = presence_service(store)
        result = service.commit_and_spawn(presence_proposal(),
            presence_idempotency_key="presence:joint", presence_expected_revision=0)
        assert result.activation.committed and result.presence.committed
    await _run(main, seed_presence)
    read_set = _read_set()
    social_result = await _run(main, lambda: PopulationSimulationCapability(owner_executors={
        "population:social-population-signal:v1": SocialPopulationSignalOwnerExecutor(
            authority=main.social_fact_authority_service)
    }).run_default_decision_cycle(read_set.cadence, read_set))
    assert social_result.status == "accepted"
    social_source = await _run(main, lambda: next(event for event in main.gameplay_event_store.read_events()
        if event.event_type == "gameplay.social.population_signal_recorded@1"))
    delivered = await _run(main, lambda: main.social_delivery_caller.authority.record_delivery(
        delivery_ref="delivery:joint", source_stream_id=social_source.stream_id,
        source_revision=social_source.stream_revision, source_event_id=social_source.event_id,
        recipient_ref="character:char_a", window=SocialDeliveryWindow(86400, 172800, None),
        world_now=86400, command_id="social:joint-delivery",
        idempotency_key="social:joint-delivery", causation_id=social_source.event_id,
        correlation_id="social:joint-delivery"))
    assert delivered.committed
    assert (await _run(main, lambda: _draw(main.gameplay_event_store, "joint-first"))).committed
    cut = await capture(main)
    assert cut.status == "consistent", cut.diagnostics
    saved = cut.checkpoint.state["participants"]
    domains = {"resource", "inventory_domain", "equipment", "economy_random",
               "economy_temporal", "ecology_temporal", "presence", "life_state",
               "social", "social_delivery"}
    assert domains <= set(saved)
    assert saved["resource"]["actors"]["char_a"]["reservations"]
    assert saved["equipment"]["actors"][EQUIPMENT_ACTOR]["active_by_slot"]
    assert saved["inventory_domain"]["actors"][EQUIPMENT_ACTOR]["items"]
    assert saved["economy_random"]["result_count"] == 1
    assert saved["economy_temporal"]["state"]["open"]
    assert saved["ecology_temporal"]["state"]["open"]
    assert saved["presence"]["rows"] == [{
        "world_ref": "world:bakery", "character_ref": "character:char_a",
        "incarnation": 1, "status": "present"}]
    assert saved["life_state"]["actors"]["character:char_a"]["state"] == "alive"
    assert saved["social"]["event_refs"]
    assert saved["social_delivery"]["event_refs"]
    assert (await _reservation(main, "consume")).committed
    assert (await _unequip(main)).committed
    assert (await _run(main, lambda: _draw(main.gameplay_event_store, "joint-second"))).committed
    def settle_death():
        store, confirmation_id = seed_case_death(main.gameplay_event_store, "character:char_a")
        assert store is main.gameplay_event_store
        result = CaseDeathLifeStateCaller(store=store).record_confirmed_case_death(
            confirmation_event_id=confirmation_id, expected_source_revision=2,
            command_id="death:joint", idempotency_key="death:joint",
            causation_id=confirmation_id, correlation_id="death:joint")
        assert result.result.committed
    await _run(main, settle_death)
    assert (await _run(main, lambda: PopulationPresenceAuthority(store=main.gameplay_event_store).despawn(
        CharacterDespawnRequest(world_ref="world:bakery", character_ref="character:char_a",
            incarnation=1, idempotency_key="despawn:joint", expected_revision=1,
            reason="explicit_departure")))).committed
    await advance(172800)
    assert main.economy_temporal_consumer.last_errors == ()
    assert main.ecology_temporal_consumer.last_errors == ()
    assert main.economy_temporal_consumer.last_results[0].committed
    assert main.ecology_temporal_consumer.last_results[0].committed
    expired = await _run(main, lambda: main.social_delivery_caller.authority.expire_delivery(
        delivery_ref="delivery:joint", recipient_ref="character:char_a", world_now=172800,
        command_id="social:joint-expiry", idempotency_key="social:joint-expiry",
        causation_id=social_source.event_id, correlation_id="social:joint-expiry"))
    assert expired.committed
    tail = await tail_call(main)
    assert tail.status == "verified", tail.diagnostics
    old_store = main.gameplay_event_store
    await main._stop_population_runtime_on_shutdown()
    await start()
    assert main.gameplay_event_store is not old_store
    main.inventory_authority_service._registry.register_item(ItemDefinition("item:sword", "1", 3, 2))
    before = await _run(main, lambda: main.gameplay_event_store.export_snapshot())
    resumed = await tail_call(main, tail.payload)
    assert resumed.status == "verified", resumed.diagnostics
    assert resumed.result["full_digest"] == resumed.result["result_digest"]
    current = resumed.result["participants"]
    assert current["resource"]["actors"]["char_a"]["reservations"] == {}
    assert current["equipment"]["actors"][EQUIPMENT_ACTOR]["active_by_slot"] == {}
    assert current["economy_random"]["result_count"] == 2
    assert current["economy_temporal"]["state"]["terminal"]
    assert current["ecology_temporal"]["state"]["terminal"]
    assert current["presence"]["rows"] == []
    assert current["life_state"]["actors"]["character:char_a"]["state"] == "dead"
    assert current["life_state"]["actors"]["character:char_a"]["incarnation"] == 1
    assert current["social"]["event_refs"] == saved["social"]["event_refs"]
    assert len(current["social_delivery"]["event_refs"]) == len(saved["social_delivery"]["event_refs"]) + 1
    for domain in domains:
        damaged = deepcopy(tail.payload)
        participant = damaged["participants"][domain]
        participant["projection_hash" if domain in {"social", "social_delivery"} else "view_digest"] = "changed"
        damaged["digest"] = _tail_hash(damaged)
        rejected = await tail_call(main, damaged)
        assert rejected.status in {"incomplete", "divergent"}, domain
        assert rejected.result is None
        if domain in {"social", "social_delivery"}:
            assert "social" in " ".join(rejected.diagnostics), rejected.diagnostics
    assert await _run(main, lambda: main.gameplay_event_store.export_snapshot()) == before
