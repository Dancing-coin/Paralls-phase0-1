"""Resource domain reconstruction inside the existing application replay cut."""
import asyncio
from copy import deepcopy
from pathlib import Path

import pytest

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.resource_body_runtime import (
    ResourceBodyRuntimeProjector, ResourceReservationAuthorityService, ResourceReservationCommand,
)
from app.gameplay.resource_materialization import (
    CharacterResourceMaterializationCaller, ResourceMaterializationAuthorityService,
)
from app.world_runtime.replay_checkpoint import _tail_hash
from test_status_application_lifecycle import application
from test_world_batch_settlement_application import inputs, submit
from test_world_replay_checkpoint_application import capture, tail_call


async def _run(main, callback):
    return await asyncio.wrap_future(main.runtime_execution.submit(callback))


async def _prepare(application):
    main, start, advance = application
    await start()
    await advance(86400)
    plan, window = inputs(main)
    await submit(main, plan=plan, window=window, budget=0)

    def materialize():
        registry = CharacterProfileRegistry.from_directory(
            Path(__file__).resolve().parents[2] / "assets/characters/profiles")
        caller = CharacterResourceMaterializationCaller(
            authority=ResourceMaterializationAuthorityService(store=main.gameplay_event_store, registry=registry))
        driver = main._population_runtime_driver
        return caller.materialize(actor_ref="char_a", world_ref=driver.world_runtime.mode.world_ref,
            timeline_ref=driver.clock.timeline.timeline_id, world_tick=driver.current_tick,
            idempotency_key="resource-replay:materialize", expected_revision=0)

    assert (await _run(main, materialize)).committed
    assert (await _reservation(main, "reserve")).committed
    return main, start, advance


async def _reservation(main, operation):
    def apply():
        store = main.gameplay_event_store
        projection = ResourceBodyRuntimeProjector().rebuild_resources(
            "char_a", store.read_stream("gameplay:resources:char_a"))
        return ResourceReservationAuthorityService(store=store).apply(
            ResourceReservationCommand(command_id=f"resource-replay:{operation}", actor_ref="char_a",
                authority_principal="gameplay_authority", idempotency_key=f"resource-replay:{operation}",
                payload_digest=f"sha256:{operation}", causation_id="resource-replay", correlation_id="resource-replay",
                operation=operation, resource_id="core.stamina", reservation_ref="reservation:replay",
                amount=3 if operation == "reserve" else None, lock_ref="lock:replay"), projection)
    return await _run(main, apply)


@pytest.mark.asyncio
async def test_resource_participant_durable_reopen_consume_recovery_and_domain_parity(application, monkeypatch):
    main, start, advance = await _prepare(application)
    cut = await capture(main)
    assert cut.status == "consistent", cut.diagnostics
    saved = cut.checkpoint.state["participants"]
    assert saved["versions"]["resource"] == 1
    row = saved["resource"]["actors"]["char_a"]
    assert row["entries"]["core.stamina"]["reserved"] == 3
    assert row["entries"]["core.stamina"]["locked"] == 3
    assert (await _reservation(main, "consume")).committed
    await advance(172800)
    tail = await tail_call(main)
    assert tail.status == "verified", tail.diagnostics
    old_store = main.gameplay_event_store
    await main._stop_population_runtime_on_shutdown()
    await start()
    assert main.gameplay_event_store is not old_store
    domain_checkpoints = []
    original = ResourceBodyRuntimeProjector.rebuild_resources
    def observe(self, actor, events, *, checkpoint=None):
        if checkpoint is not None:
            domain_checkpoints.append(checkpoint)
        return original(self, actor, events, checkpoint=checkpoint)
    monkeypatch.setattr(ResourceBodyRuntimeProjector, "rebuild_resources", observe)
    before = await _run(main, lambda: main.gameplay_event_store.export_snapshot())
    result = await tail_call(main, tail.payload)
    assert result.status == "verified", result.diagnostics
    assert result.result["full_digest"] == result.result["result_digest"]
    assert domain_checkpoints and domain_checkpoints[0].reservations["reservation:replay"] == ("core.stamina", 3)
    state = result.result["participants"]["resource"]["actors"]["char_a"]
    assert state["reservations"] == {}
    assert state["locks"]["lock:replay"][-1] == "consumed"
    assert state["entries"]["core.stamina"]["current"] == 100
    assert await _run(main, lambda: main.gameplay_event_store.export_snapshot()) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["state", "event_ref", "digest", "decoder", "omit", "version_omitted"])
async def test_resource_participant_rejects_corruption_without_write(application, fault):
    main, _, _ = await _prepare(application)
    cut = await capture(main)
    assert cut.status == "consistent", cut.diagnostics
    tail = await tail_call(main)
    bad = deepcopy(tail.payload)
    resource = bad["participants"]["resource"]
    if fault == "state":
        resource["actors"]["char_a"]["entries"]["core.stamina"]["current"] -= 1
    elif fault == "event_ref":
        resource["event_refs"][0]["event_digest"] = "changed"
    elif fault == "digest":
        resource["view_digest"] = "changed"
    elif fault == "decoder":
        bad["participants"]["versions"]["resource"] = 99
    elif fault == "omit":
        del bad["participants"]["resource"]
    else:
        del bad["participants"]["versions"]["resource"]
    bad["digest"] = _tail_hash(bad)
    before = await _run(main, lambda: main.gameplay_event_store.export_snapshot())
    result = await tail_call(main, bad)
    assert result.status in {"incomplete", "divergent"}
    assert result.result is None
    assert await _run(main, lambda: main.gameplay_event_store.export_snapshot()) == before


def test_resource_migration_without_historical_definitions_rejects_instead_of_omitting():
    from app.gameplay.event_store import GameplayEventStore
    from app.gameplay.resource_body_runtime import ResourceBoundsMigrationAuthorityService
    from app.world_runtime.replay_participants import _resource_participant
    from test_resource_v2_migration import ACTOR, _append, _defs, _legacy, _request

    store = GameplayEventStore()
    _legacy(store)
    boundary = store.get_last_global_sequence()
    projector = ResourceBodyRuntimeProjector(resource_definitions=_defs())
    prior = projector.rebuild_resources(ACTOR, store.read_events())
    plan = ResourceBoundsMigrationAuthorityService(definitions=_defs()).plan(_request(prior), prior)
    legacy_payload = {key: value for key, value in plan.payload.items()
                      if key not in {"definition_snapshots", "definition_snapshots_digest"}}
    assert _append(store, "migrate", plan.event_type, legacy_payload).committed
    before = store.export_snapshot()
    with pytest.raises(ValueError, match="resource_definition_registry_required"):
        _resource_participant(store)
    # Future migration must not invalidate reconstruction at the earlier cut.
    historical = _resource_participant(store, boundary_sequence=boundary)
    assert historical["actors"][ACTOR]["entries"]["core.stamina"]["current"] == 9
    assert store.export_snapshot() == before


def _d06_owner_store(tmp_path):
    from app.gameplay.event_store import DurableGameplayEventStore
    from app.gameplay.resource_migration_control import ResourceMigrationControlAuthority, ResourceMigrationOwner
    from app.gameplay.resource_body_runtime import RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST
    from app.world_runtime.replay_participants import _resource_participant
    from test_resource_migration_control import _legacy_resources, _migration_definitions, _pause

    path = tmp_path / "d06-replay.sqlite3"
    store = DurableGameplayEventStore(path)
    _legacy_resources(store)
    cut = store.get_last_global_sequence()
    saved = _resource_participant(store, boundary_sequence=cut)
    assert _pause(ResourceMigrationControlAuthority(store=store), expected_resource_revision=3).committed
    owner = ResourceMigrationOwner(store=store, definitions=_migration_definitions())
    result = owner.apply(actor_ref="char_a", migration_id="migration:1",
        from_definition_version="v1", to_definition_version="v2",
        migration_digest="sha256:" + "a" * 64,
        migrator_code_digest=RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST,
        authority_principal="resource-migration-caller", idempotency_key="apply:replay")
    assert result.committed
    return path, store, saved, cut, result


def test_d06_owner_pins_historical_definitions_for_durable_scoped_replay(tmp_path):
    from app.gameplay.event_store import DurableGameplayEventStore
    from app.world_runtime.replay_participants import _resource_participant, validate_resource_checkpoint_tail

    path, store, saved, cut, result = _d06_owner_store(tmp_path)
    event = next(event for event in store.get_transaction(result.transaction_id).events
                 if event.event_type == "gameplay.resource.bounds_migrated")
    assert event.payload["definition_snapshots"]["source"]["definition_version"] == "v1"
    assert event.payload["definition_snapshots"]["target"]["definition_version"] == "v2"
    current = _resource_participant(store)
    validate_resource_checkpoint_tail(store, saved, current, cut, store.get_last_global_sequence())
    before = store.export_snapshot()
    store.close()
    reopened = DurableGameplayEventStore(path)
    assert _resource_participant(reopened) == current
    validate_resource_checkpoint_tail(reopened, saved, current, cut, reopened.get_last_global_sequence())
    assert reopened.export_snapshot() == before
    reopened.close()


def test_d06_scoped_replay_accepts_second_v2_migration_from_owner(tmp_path):
    from app.gameplay.resource_body_runtime import RESOURCE_V2_POLICY_MIGRATOR_CODE_DIGEST
    from app.gameplay.resource_migration_control import ResourceMigrationControlAuthority, ResourceMigrationOwner
    from app.world_runtime.replay_participants import _resource_participant, validate_resource_checkpoint_tail
    from test_resource_migration_control import _two_stage_migration_definitions

    _, store, saved, cut, _ = _d06_owner_store(tmp_path)
    definitions = _two_stage_migration_definitions()
    control = ResourceMigrationControlAuthority(store=store, definitions=definitions)
    assert control.pause(actor_ref="char_a", migration_id="migration:2", source_definition_revision="v2",
        target_definition_revision="v3", schema_digest="schema:resource-v2", codec_digest="codec:resource-v2",
        migrator_digest=RESOURCE_V2_POLICY_MIGRATOR_CODE_DIGEST,
        expected_resource_revision=store.get_stream_head("gameplay:resources:char_a"),
        expected_control_revision=store.get_stream_head("gameplay:resource-migration-control:char_a"),
        idempotency_key="pause:second", authority_principal="trusted-migration-caller").committed
    assert ResourceMigrationOwner(store=store, definitions=definitions).apply(
        actor_ref="char_a", migration_id="migration:2", from_definition_version="v2",
        to_definition_version="v3", migration_digest="sha256:" + "b" * 64,
        migrator_code_digest=RESOURCE_V2_POLICY_MIGRATOR_CODE_DIGEST,
        authority_principal="resource-migration-caller", idempotency_key="apply:second").committed
    current = _resource_participant(store)
    assert {entry["definition_version"] for entry in current["actors"]["char_a"]["entries"].values()} == {"v3"}
    validate_resource_checkpoint_tail(store, saved, current, cut, store.get_last_global_sequence())
    store.close()


def test_d06_scoped_replay_rejects_conflicting_owner_definition_for_same_version(tmp_path):
    from app.gameplay.resource_body_runtime import ResourceDefinition, ResourceDefinitionRegistry
    from app.gameplay.resource_migration_control import ResourceMigrationControlAuthority, ResourceMigrationOwner
    from app.gameplay.resource_body_runtime import RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST
    from app.gameplay.settlement_plan import build_atomic_event_batch
    from app.world_runtime.replay_participants import _resource_participant
    from test_resource_migration_control import _migration_definitions

    _, store, _, _, _ = _d06_owner_store(tmp_path)
    first_cut = store.get_last_global_sequence()
    for index, (resource_id, maximum) in enumerate((
            ("core.stamina", 10), ("core.mana", 8), ("core.action_points", 4))):
        assert store.append_batch(build_atomic_event_batch(
            command_id=f"legacy:char_b:{resource_id}", principal_ref="legacy-test",
            stream_id="gameplay:resources:char_b", expected_revision=index,
            event_specs=[("gameplay.resource.materialized", {
                "actor_ref": "char_b", "resource_id": resource_id, "minimum": 0,
                "maximum": maximum, "current": maximum, "definition_version": "v1"})],
            idempotency_key=f"legacy:char_b:{resource_id}", causation_id="cause", correlation_id="corr")).committed
    definitions = ResourceDefinitionRegistry()
    baseline = _migration_definitions()
    for resource_id in ("core.stamina", "core.mana", "core.action_points"):
        for version in ("v1", "v2"):
            original = baseline.resolve(resource_id, version)
            definitions.register(ResourceDefinition.model_validate({
                **original.model_dump(mode="json"),
                "maximum": 8 if (resource_id, version) == ("core.stamina", "v2") else original.maximum}))
    control = ResourceMigrationControlAuthority(store=store)
    assert control.pause(actor_ref="char_b", migration_id="migration:b", source_definition_revision="v1",
        target_definition_revision="v2", schema_digest="schema:resource-v2", codec_digest="codec:resource-v2",
        migrator_digest="migrator:resource-v2", expected_resource_revision=3,
        expected_control_revision=0, idempotency_key="pause:b",
        authority_principal="trusted-migration-caller").committed
    assert ResourceMigrationOwner(store=store, definitions=definitions).apply(
        actor_ref="char_b", migration_id="migration:b", from_definition_version="v1",
        to_definition_version="v2", migration_digest="sha256:" + "c" * 64,
        migrator_code_digest=RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST,
        authority_principal="resource-migration-caller", idempotency_key="apply:b").committed
    before = store.export_snapshot()
    with pytest.raises(ValueError, match="resource_migration_definition_conflict"):
        _resource_participant(store)
    assert _resource_participant(store, boundary_sequence=first_cut) is not None
    assert store.export_snapshot() == before
    store.close()


@pytest.mark.parametrize("fault", ["digest", "definition", "missing_completion", "wrong_principal", "missing_event", "changed_completion"])
def test_d06_scoped_replay_rejects_unproven_definition_pin_without_write(tmp_path, monkeypatch, fault):
    from app.world_runtime.replay_participants import _resource_participant

    _, store, _, _, result = _d06_owner_store(tmp_path)
    transaction = store.get_transaction(result.transaction_id)
    migration = next(event for event in transaction.events
                     if event.event_type == "gameplay.resource.bounds_migrated")
    if fault in {"digest", "definition"}:
        payload = deepcopy(migration.payload)
        if fault == "digest":
            payload["definition_snapshots_digest"] = "sha256:" + "0" * 64
        else:
            payload["definition_snapshots"]["target"]["maximum"] -= 1
        real_read = store.read_events
        monkeypatch.setattr(store, "read_events", lambda *args, **kwargs: [
            event.model_copy(update={"payload": payload}) if event.event_id == migration.event_id else event
            for event in real_read(*args, **kwargs)])
    elif fault in {"missing_event", "changed_completion"}:
        real_get = store.get_event
        completion = next(event for event in transaction.events
                          if event.event_type == "gameplay.resource_migration.completed")
        def changed(event_id):
            if fault == "missing_event" and event_id == migration.event_id:
                raise KeyError(event_id)
            if fault == "changed_completion" and event_id == completion.event_id:
                return completion.model_copy(update={"payload": {**completion.payload, "migration_id": "changed"}})
            return real_get(event_id)
        monkeypatch.setattr(store, "get_event", changed)
    else:
        original = store.get_transaction
        def altered(transaction_id):
            batch = original(transaction_id)
            if transaction_id != result.transaction_id:
                return batch
            if fault == "missing_completion":
                return batch.model_copy(update={"events": [event for event in batch.events
                    if event.event_type != "gameplay.resource_migration.completed"]})
            return batch.model_copy(update={"idempotency_record": batch.idempotency_record.model_copy(
                update={"principal_ref": "another_principal"})})
        monkeypatch.setattr(store, "get_transaction", altered)
    before = store.export_snapshot()
    with pytest.raises(ValueError, match="resource_(definition_registry_required|migration_definition_provenance_invalid)"):
        _resource_participant(store)
    assert store.export_snapshot() == before
    store.close()


@pytest.mark.parametrize("fault", ["schema", "unknown_type", "wrong_stream", "wrong_actor"])
def test_resource_event_scope_cannot_be_silently_dropped(monkeypatch, fault):
    from app.gameplay.event_store import GameplayEventStore
    from app.world_runtime.replay_participants import _resource_participant
    from test_resource_v2_migration import _legacy

    store = GameplayEventStore()
    _legacy(store)
    event = store.read_events()[0]
    updates = {"schema": {"schema_version": 99},
        "unknown_type": {"event_type": "gameplay.resource.unknown"},
        "wrong_stream": {"stream_id": "gameplay:other:actor"},
        "wrong_actor": {"payload": dict(event.payload, actor_ref="actor:wrong")}}[fault]
    monkeypatch.setattr(store, "read_events", lambda: [event.model_copy(update=updates)])
    with pytest.raises(ValueError, match="replay_resource_event_scope_unsupported"):
        _resource_participant(store)


@pytest.mark.parametrize("event_type,version,readable", [
    ("gameplay.character.life_state_changed", 2, True),
    ("gameplay.character.life_state_changed", 3, False),
    ("gameplay.resource.materialized", 2, False),
])
def test_replay_allows_only_registered_presence_v2_decoder(event_type, version, readable):
    from types import SimpleNamespace
    from app.world_runtime.replay_checkpoint import _replay_readable_event
    assert _replay_readable_event(SimpleNamespace(event_type=event_type, schema_version=version)) is readable
