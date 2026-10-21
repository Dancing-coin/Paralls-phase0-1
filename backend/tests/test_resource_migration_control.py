from pathlib import Path

import pytest

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.resource_body_runtime import ResourceBodyRuntimeProjector, ResourceDefinition, ResourceDefinitionRegistry, RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST, RESOURCE_V2_POLICY_MIGRATOR_CODE_DIGEST
from app.gameplay.resource_body_runtime import ResourceReservationAuthorityService, ResourceReservationCommand
from app.gameplay.resource_materialization import ResourceMaterializationAuthorityService
from app.gameplay.resource_migration_control import ResourceMigrationControlAuthority, ResourceMigrationOwner
from app.gameplay.settlement_plan import build_atomic_event_batch


PROFILE_DIR = Path(__file__).resolve().parents[2] / "assets" / "characters" / "profiles"
RESOURCE_STREAM = "gameplay:resources:char_a"
CONTROL_STREAM = "gameplay:resource-migration-control:char_a"


def _materialized(store):
    owner = ResourceMaterializationAuthorityService(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    return owner.materialize(actor_ref="char_a", world_ref="world:bakery", timeline_ref="timeline:main", world_tick=0,
                             idempotency_key="materialize", expected_revision=0)


def _pause(owner, **changes):
    values = dict(actor_ref="char_a", migration_id="migration:1", source_definition_revision="v1",
                  target_definition_revision="v2", schema_digest="schema:resource-v2",
                  codec_digest="codec:resource-v2", migrator_digest="migrator:resource-v2",
                  expected_resource_revision=3, expected_control_revision=0, idempotency_key="pause:1",
                  authority_principal="trusted-migration-caller")
    values.update(changes)
    return owner.pause(**values)


def _legacy_resources(store):
    for index, (resource_id, maximum) in enumerate((("core.stamina", 10), ("core.mana", 8), ("core.action_points", 4))):
        assert store.append_batch(build_atomic_event_batch(
            command_id=f"legacy:{resource_id}", principal_ref="legacy-test", stream_id=RESOURCE_STREAM,
            expected_revision=index, event_specs=[("gameplay.resource.materialized", {
                "actor_ref": "char_a", "resource_id": resource_id, "minimum": 0,
                "maximum": maximum, "current": maximum, "definition_version": "v1",
            })], idempotency_key=f"legacy:{resource_id}", causation_id="cause", correlation_id="corr",
        )).committed


def _migration_definitions():
    definitions = ResourceDefinitionRegistry()
    for resource_id, maximum, capacity in (("core.stamina", 10, 12), ("core.mana", 8, 10), ("core.action_points", 4, 6)):
        definitions.register(ResourceDefinition(resource_id=resource_id, definition_version="v1", minimum=0, maximum=maximum))
        definitions.register(ResourceDefinition(resource_id=resource_id, definition_version="v2", minimum=0, maximum=maximum - 1,
                                                resource_schema="resource.v2", capacity=capacity, base_capacity=capacity))
    return definitions


def _two_stage_migration_definitions():
    definitions = _migration_definitions()
    for resource_id, maximum, capacity in (("core.stamina", 11, 14), ("core.mana", 9, 12), ("core.action_points", 5, 8)):
        definitions.register(ResourceDefinition(resource_id=resource_id, definition_version="v3", minimum=0,
                                                maximum=maximum, resource_schema="resource.v2",
                                                capacity=capacity, base_capacity=capacity))
    return definitions


def test_pause_is_authority_only_persistent_and_drain_is_read_only():
    store = GameplayEventStore()
    _materialized(store)
    owner = ResourceMigrationControlAuthority(store=store)
    result = _pause(owner)
    assert result.committed
    assert store.read_stream(CONTROL_STREAM)[0].visibility_policy == "authority_only"
    observation = owner.observe_drain(actor_ref="char_a", migration_id="migration:1", expected_resource_revision=3)
    assert observation.status == "drained"
    assert len(store.read_stream(RESOURCE_STREAM)) == 3


@pytest.mark.parametrize("damage", ["command", "revision", "sequence", "event", "missing_event"])
def test_pause_replay_rejects_damaged_durable_receipt_without_write(tmp_path, monkeypatch, damage):
    path = tmp_path / "pause-receipt.sqlite3"
    store = DurableGameplayEventStore(path)
    _materialized(store)
    first = _pause(ResourceMigrationControlAuthority(store=store))
    assert first.committed
    store.close()
    store = DurableGameplayEventStore(path)
    try:
        before = store.get_last_global_sequence()
        lookup = store.get_by_idempotency
        get_event = store.get_event
        if damage in {"event", "missing_event"}:
            def altered_event(event_id):
                if damage == "missing_event":
                    raise KeyError(event_id)
                event = get_event(event_id)
                return event.model_copy(update={"visibility_policy": "public"}, deep=True)
            monkeypatch.setattr(store, "get_event", altered_event)
        else:
            changes = {
                "command": {"command_id": "wrong-command"},
                "revision": {"resulting_stream_revisions": {CONTROL_STREAM: 99}},
                "sequence": {"global_sequence_range": (99, 99)},
            }[damage]
            def altered_receipt(principal, key):
                receipt = lookup(principal, key)
                return receipt.model_copy(update=changes, deep=True) if receipt is not None else None
            monkeypatch.setattr(store, "get_by_idempotency", altered_receipt)
        with pytest.raises(ValueError, match="resource_migration_receipt_incomplete"):
            _pause(ResourceMigrationControlAuthority(store=store))
        assert store.get_last_global_sequence() == before
    finally:
        store.close()


def test_drain_reports_pending_until_original_reservation_is_released():
    store = GameplayEventStore()
    _materialized(store)
    reservation = ResourceReservationAuthorityService(store=store).apply(ResourceReservationCommand(
        command_id="reserve", actor_ref="char_a", authority_principal="gameplay_authority",
        idempotency_key="reserve", payload_digest="sha256:reserve", causation_id="cause:reserve",
        correlation_id="corr:reserve", operation="reserve", resource_id="core.stamina",
        reservation_ref="reservation:1", lock_ref="lock:1", amount=2), ResourceBodyRuntimeProjector().rebuild_resources("char_a", store.read_events()))
    assert reservation.committed
    owner = ResourceMigrationControlAuthority(store=store)
    assert _pause(owner, expected_resource_revision=store.get_stream_head(RESOURCE_STREAM)).committed
    assert owner.observe_drain(actor_ref="char_a", migration_id="migration:1", expected_resource_revision=store.get_stream_head(RESOURCE_STREAM)).status == "pending"


def test_pause_rejects_new_reservation_but_allows_existing_consume_and_release():
    store = GameplayEventStore()
    _materialized(store)
    reservations = ResourceReservationAuthorityService(store=store)
    projection = ResourceBodyRuntimeProjector().rebuild_resources("char_a", store.read_events())
    first = reservations.apply(ResourceReservationCommand(
        command_id="reserve-before-pause", actor_ref="char_a", authority_principal="gameplay_authority",
        idempotency_key="reserve-before-pause", payload_digest="sha256:reserve-before-pause",
        causation_id="cause:reserve-before-pause", correlation_id="corr:reservation",
        operation="reserve", resource_id="core.stamina", reservation_ref="reservation:existing", lock_ref="lock:existing", amount=2), projection)
    assert first.committed
    second = reservations.apply(ResourceReservationCommand(
        command_id="reserve-second", actor_ref="char_a", authority_principal="gameplay_authority",
        idempotency_key="reserve-second", payload_digest="sha256:reserve-second",
        causation_id="cause:reserve-second", correlation_id="corr:reservation",
        operation="reserve", resource_id="core.stamina", reservation_ref="reservation:second", lock_ref="lock:second", amount=1),
        ResourceBodyRuntimeProjector().rebuild_resources("char_a", store.read_events()))
    assert second.committed
    owner = ResourceMigrationControlAuthority(store=store)
    assert _pause(owner, expected_resource_revision=store.get_stream_head(RESOURCE_STREAM)).committed
    paused_projection = ResourceBodyRuntimeProjector().rebuild_resources("char_a", store.read_events())
    with pytest.raises(ValueError, match="paused_for_migration"):
        reservations.apply(ResourceReservationCommand(
            command_id="reserve-after-pause", actor_ref="char_a", authority_principal="gameplay_authority",
            idempotency_key="reserve-after-pause", payload_digest="sha256:reserve-after-pause",
            causation_id="cause:reserve-after-pause", correlation_id="corr:reservation",
            operation="reserve", resource_id="core.stamina", reservation_ref="reservation:new", lock_ref="lock:new", amount=1), paused_projection)
    assert len(store.read_stream(RESOURCE_STREAM)) == 7
    consumed = reservations.apply(ResourceReservationCommand(
        command_id="consume-after-pause", actor_ref="char_a", authority_principal="gameplay_authority",
        idempotency_key="consume-after-pause", payload_digest="sha256:consume-after-pause",
        causation_id="cause:consume-after-pause", correlation_id="corr:reservation",
        operation="consume", resource_id="core.stamina", reservation_ref="reservation:existing", lock_ref="lock:existing"), paused_projection)
    assert consumed.committed
    released_projection = ResourceBodyRuntimeProjector().rebuild_resources("char_a", store.read_events())
    assert set(released_projection.reservations) == {"reservation:second"}

    # Release is an allowed drain operation while the migration is paused.
    released = reservations.apply(ResourceReservationCommand(
        command_id="release-second", actor_ref="char_a", authority_principal="gameplay_authority",
        idempotency_key="release-second", payload_digest="sha256:release-second",
        causation_id="cause:release-second", correlation_id="corr:reservation",
        operation="release", resource_id="core.stamina", reservation_ref="reservation:second", lock_ref="lock:second"),
        ResourceBodyRuntimeProjector().rebuild_resources("char_a", store.read_events()))
    assert released.committed
    assert not ResourceBodyRuntimeProjector().rebuild_resources("char_a", store.read_events()).reservations


def test_reservation_rejects_resource_write_after_validation_without_own_write():
    class InterleavingStore(GameplayEventStore):
        injected = False

        def read_stream(self, stream_id):
            if not self.injected and stream_id == CONTROL_STREAM:
                self.injected = True
                revision = self.get_stream_head(RESOURCE_STREAM)
                super().append_batch({
                    "transaction_id": "tx:concurrent-resource-write",
                    "command_id": "concurrent-resource-write",
                    "expected_stream_revisions": {RESOURCE_STREAM: revision},
                    "read_stream_revisions": {RESOURCE_STREAM: revision},
                    "pinned_revisions": {},
                    "events": [{
                        "event_id": "evt:concurrent-resource-write",
                        "event_type": "gameplay.resource.concurrent_write",
                        "schema_version": 1,
                        "stream_id": RESOURCE_STREAM,
                        "stream_revision": 0,
                        "global_sequence": 0,
                        "transaction_id": "tx:concurrent-resource-write",
                        "command_id": "concurrent-resource-write",
                        "causation_id": "cause:concurrent-resource-write",
                        "correlation_id": "corr:concurrent-resource-write",
                        "visibility_policy": "authority_only",
                        "payload": {"actor_ref": "char_a"},
                    }],
                    "idempotency_record": {"principal_ref": "race", "idempotency_key": "concurrent", "payload_digest": "sha256:concurrent"},
                    "outbox_entries": [], "result_digest": "sha256:concurrent", "projection_refresh_hints": [],
                })
            return super().read_stream(stream_id)

    store = InterleavingStore()
    _materialized(store)
    resources = ResourceBodyRuntimeProjector().rebuild_resources("char_a", store.read_events())
    result = ResourceReservationAuthorityService(store=store).apply(ResourceReservationCommand(
            command_id="reserve-race", actor_ref="char_a", authority_principal="gameplay_authority",
            idempotency_key="reserve-race", payload_digest="sha256:reserve-race",
            causation_id="cause:reserve-race", correlation_id="corr:race",
            operation="reserve", resource_id="core.stamina", reservation_ref="reservation:race", lock_ref="lock:race", amount=1), resources)
    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "revision_conflict"
    assert not any(event.command_id == "reserve-race" for event in store.read_stream(RESOURCE_STREAM))


def test_pause_exact_replay_changed_duplicate_and_conflict_are_zero_write(tmp_path):
    path = tmp_path / "migration-control.sqlite3"
    store = DurableGameplayEventStore(path)
    _materialized(store)
    owner = ResourceMigrationControlAuthority(store=store)
    first = _pause(owner)
    replay = _pause(owner)
    assert replay.idempotency_status == "duplicate_replayed"
    assert replay.committed_event_ids == first.committed_event_ids
    with pytest.raises(ValueError, match="idempotency_reused"):
        _pause(owner, schema_digest="schema:changed")
    store.close()
    reopened = DurableGameplayEventStore(path)
    new_owner = ResourceMigrationControlAuthority(store=reopened)
    recovered = _pause(new_owner)
    assert recovered.idempotency_status == "duplicate_replayed"
    assert len(reopened.read_stream(CONTROL_STREAM)) == 1
    reopened.close()


def test_durable_reopen_drains_existing_consume_and_release(tmp_path):
    path = tmp_path / "migration-drain.sqlite3"
    store = DurableGameplayEventStore(path)
    _materialized(store)
    reservations = ResourceReservationAuthorityService(store=store)
    first = reservations.apply(ResourceReservationCommand(
        command_id="durable-reserve-consume", actor_ref="char_a", authority_principal="gameplay_authority",
        idempotency_key="durable-reserve-consume", payload_digest="sha256:durable-reserve-consume",
        causation_id="cause:durable-reserve-consume", correlation_id="corr:durable",
        operation="reserve", resource_id="core.stamina", reservation_ref="reservation:consume", lock_ref="lock:consume", amount=1),
        ResourceBodyRuntimeProjector().rebuild_resources("char_a", store.read_events()))
    assert first.committed
    second = reservations.apply(ResourceReservationCommand(
        command_id="durable-reserve-release", actor_ref="char_a", authority_principal="gameplay_authority",
        idempotency_key="durable-reserve-release", payload_digest="sha256:durable-reserve-release",
        causation_id="cause:durable-reserve-release", correlation_id="corr:durable",
        operation="reserve", resource_id="core.stamina", reservation_ref="reservation:release", lock_ref="lock:release", amount=1),
        ResourceBodyRuntimeProjector().rebuild_resources("char_a", store.read_events()))
    assert second.committed
    assert _pause(ResourceMigrationControlAuthority(store=store), expected_resource_revision=store.get_stream_head(RESOURCE_STREAM)).committed
    store.close()

    reopened = DurableGameplayEventStore(path)
    owner = ResourceReservationAuthorityService(store=reopened)
    projection = ResourceBodyRuntimeProjector().rebuild_resources("char_a", reopened.read_events())
    consumed = owner.apply(ResourceReservationCommand(
        command_id="durable-consume-after-reopen", actor_ref="char_a", authority_principal="gameplay_authority",
        idempotency_key="durable-consume-after-reopen", payload_digest="sha256:durable-consume-after-reopen",
        causation_id="cause:durable-consume-after-reopen", correlation_id="corr:durable",
        operation="consume", resource_id="core.stamina", reservation_ref="reservation:consume", lock_ref="lock:consume"), projection)
    assert consumed.committed
    released = owner.apply(ResourceReservationCommand(
        command_id="durable-release-after-reopen", actor_ref="char_a", authority_principal="gameplay_authority",
        idempotency_key="durable-release-after-reopen", payload_digest="sha256:durable-release-after-reopen",
        causation_id="cause:durable-release-after-reopen", correlation_id="corr:durable",
        operation="release", resource_id="core.stamina", reservation_ref="reservation:release", lock_ref="lock:release"),
        ResourceBodyRuntimeProjector().rebuild_resources("char_a", reopened.read_events()))
    assert released.committed
    assert not ResourceBodyRuntimeProjector().rebuild_resources("char_a", reopened.read_events()).reservations
    reopened.close()


def test_pause_stale_read_set_rejects_without_write():
    store = GameplayEventStore()
    _materialized(store)
    owner = ResourceMigrationControlAuthority(store=store)
    with pytest.raises(ValueError, match="resource_migration_resource_revision_conflict"):
        _pause(owner, expected_resource_revision=2)
    assert not store.read_stream(CONTROL_STREAM)


def test_pause_rejects_overlapping_migration_and_read_set_override():
    store = GameplayEventStore()
    _materialized(store)
    owner = ResourceMigrationControlAuthority(store=store)
    with pytest.raises(ValueError, match="read_set_conflict"):
        _pause(owner, read_stream_revisions={RESOURCE_STREAM: 2})
    assert _pause(owner).committed
    with pytest.raises(ValueError, match="migration_overlap"):
        _pause(owner, migration_id="migration:2", idempotency_key="pause:2", expected_control_revision=1)


def test_drain_unknown_without_pause_is_read_only():
    store = GameplayEventStore()
    _materialized(store)
    observation = ResourceMigrationControlAuthority(store=store).observe_drain(
        actor_ref="char_a", migration_id="missing", expected_resource_revision=3
    )
    assert observation.status == "unknown"
    assert not store.read_stream(CONTROL_STREAM)


def test_d06_owner_applies_all_registered_resources_and_replays_durable(tmp_path):
    path = tmp_path / "resource-d06.sqlite3"
    store = DurableGameplayEventStore(path)
    _legacy_resources(store)
    control = ResourceMigrationControlAuthority(store=store)
    assert _pause(control, expected_resource_revision=3).committed
    definitions = _migration_definitions()
    owner = ResourceMigrationOwner(store=store, definitions=definitions)
    kwargs = dict(actor_ref="char_a", migration_id="migration:1", from_definition_version="v1",
                  to_definition_version="v2", migration_digest="sha256:" + "a" * 64,
                  migrator_code_digest=RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST,
                  authority_principal="resource-migration-caller", idempotency_key="apply:1")
    first = owner.apply(**kwargs)
    assert first.committed
    assert len(first.committed_event_ids) == 4
    projection = ResourceBodyRuntimeProjector(resource_definitions=definitions).rebuild_resources("char_a", store.read_stream(RESOURCE_STREAM))
    assert all(entry.capacity is not None and entry.debt == 0 for entry in projection.entries.values())
    checkpoint = ResourceBodyRuntimeProjector(resource_definitions=definitions).rebuild_resources("char_a", store.read_stream(RESOURCE_STREAM)[:3])
    full = ResourceBodyRuntimeProjector(resource_definitions=definitions).rebuild_resources("char_a", store.read_stream(RESOURCE_STREAM))
    tail = ResourceBodyRuntimeProjector(resource_definitions=definitions).rebuild_resources("char_a", store.read_stream(RESOURCE_STREAM)[3:], checkpoint=checkpoint)
    assert tail == full
    resumed = ResourceReservationAuthorityService(store=store).apply(ResourceReservationCommand(
        command_id="reserve-after-migration", actor_ref="char_a", authority_principal="gameplay_authority",
        idempotency_key="reserve-after-migration", payload_digest="sha256:reserve-after-migration",
        causation_id="cause:reserve-after-migration", correlation_id="corr:after-migration",
        operation="reserve", resource_id="core.stamina", reservation_ref="reservation:after-migration",
        lock_ref="lock:after-migration", amount=1), full)
    assert resumed.committed
    store.close()
    reopened = DurableGameplayEventStore(path)
    replay = ResourceMigrationOwner(store=reopened, definitions=definitions).apply(**kwargs)
    assert replay.idempotency_status == "duplicate_replayed"
    with pytest.raises(ValueError, match="idempotency_reused"):
        ResourceMigrationOwner(store=reopened, definitions=definitions).apply(**{**kwargs, "migration_digest": "sha256:" + "b" * 64})
    reopened.close()


def test_d06_duplicate_requires_persisted_transaction_and_complete_receipt(tmp_path, monkeypatch):
    path = tmp_path / "resource-d06-incomplete.sqlite3"
    store = DurableGameplayEventStore(path)
    _legacy_resources(store)
    assert _pause(ResourceMigrationControlAuthority(store=store), expected_resource_revision=3).committed
    definitions = _migration_definitions()
    owner = ResourceMigrationOwner(store=store, definitions=definitions)
    kwargs = dict(actor_ref="char_a", migration_id="migration:1", from_definition_version="v1",
                  to_definition_version="v2", migration_digest="sha256:" + "a" * 64,
                  migrator_code_digest=RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST,
                  authority_principal="resource-migration-caller", idempotency_key="apply:1")
    first = owner.apply(**kwargs)
    assert first.committed
    monkeypatch.setattr(store, "get_transaction", lambda transaction_id: None)
    with pytest.raises(ValueError, match="receipt_incomplete"):
        owner.apply(**kwargs)
    store.close()


def test_d06_duplicate_missing_persisted_event_is_rejected_as_incomplete(tmp_path, monkeypatch):
    store = DurableGameplayEventStore(tmp_path / "missing-migration-event.sqlite3")
    _legacy_resources(store)
    assert _pause(ResourceMigrationControlAuthority(store=store)).committed
    owner = ResourceMigrationOwner(store=store, definitions=_migration_definitions())
    kwargs = dict(actor_ref="char_a", migration_id="migration:1", from_definition_version="v1",
                  to_definition_version="v2", migration_digest="sha256:" + "a" * 64,
                  migrator_code_digest=RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST,
                  authority_principal="resource-migration-caller", idempotency_key="apply:missing")
    first = owner.apply(**kwargs)
    assert first.committed
    before = store.get_last_global_sequence()
    def missing_event(event_id):
        raise KeyError(event_id)
    monkeypatch.setattr(store, "get_event", missing_event)
    with pytest.raises(ValueError, match="resource_migration_receipt_incomplete"):
        owner.apply(**kwargs)
    assert store.get_last_global_sequence() == before


def test_d06_equipment_recovery_modifier_survives_durable_migration_and_recovery(tmp_path, monkeypatch):
    import test_resource_modifier_admission as equipment_fixture
    from test_resource_recovery import _cadence
    from app.gameplay.resource_recovery import ResourceRecoveryAuthorityService

    # The existing public Equipment service consumes the authored focus charm;
    # only actor identity is changed to this migration owner's admitted syntax.
    actor = "mana_migration"
    monkeypatch.setattr(equipment_fixture, "ACTOR", actor)
    path = tmp_path / "equipment-migration.sqlite3"
    store = DurableGameplayEventStore(path)
    equipment_fixture._equip(store)
    stream = f"gameplay:resources:{actor}"
    definitions = ResourceDefinitionRegistry()
    for version, maximum in (("mana@1", 10), ("mana@2", 12)):
        definitions.register(ResourceDefinition(resource_id="core.mana", definition_version=version,
            minimum=0, maximum=maximum, resource_schema="resource.v2", capacity=maximum, base_capacity=maximum))
    projector = ResourceBodyRuntimeProjector(resource_definitions=definitions)
    before = projector.rebuild_resources(actor, store.read_stream(stream))
    assert len(before.entries["core.mana"].modifier_ledger) == 1
    control = ResourceMigrationControlAuthority(store=store, definitions=definitions)
    assert control.pause(actor_ref=actor, migration_id="focus-policy-rebind",
        source_definition_revision="mana@1", target_definition_revision="mana@2",
        schema_digest="schema:resource-v2", codec_digest="codec:resource-v2",
        migrator_digest=RESOURCE_V2_POLICY_MIGRATOR_CODE_DIGEST,
        expected_resource_revision=2, expected_control_revision=0,
        idempotency_key="pause:focus", authority_principal="trusted-migration-caller").committed
    kwargs = dict(actor_ref=actor, migration_id="focus-policy-rebind", from_definition_version="mana@1",
        to_definition_version="mana@2", migration_digest="sha256:" + "f" * 64,
        migrator_code_digest=RESOURCE_V2_POLICY_MIGRATOR_CODE_DIGEST,
        authority_principal="resource-migration-caller", idempotency_key="apply:focus")
    result = ResourceMigrationOwner(store=store, definitions=definitions).apply(**kwargs)
    assert result.committed
    migrated = projector.rebuild_resources(actor, store.read_stream(stream))
    assert migrated.entries["core.mana"].modifier_ledger == before.entries["core.mana"].modifier_ledger
    assert migrated.entries["core.mana"].modifier_ledger_digest == before.entries["core.mana"].modifier_ledger_digest
    assert migrated == projector.rebuild_resources(actor, store.read_stream(stream)[2:], checkpoint=before)
    store.close()
    store = DurableGameplayEventStore(path)
    try:
        assert ResourceMigrationOwner(store=store, definitions=definitions).apply(**kwargs).idempotency_status == "duplicate_replayed"
        _cadence(store)
        recovery = ResourceRecoveryAuthorityService(store=store, definitions=definitions).recover(
            actor_ref=actor, world_ref="world", timeline_ref="timeline", confirmed_world_tick=20,
            idempotency_key="recover:migrated-focus", expected_revision=3)
        assert recovery.committed
        final = projector.rebuild_resources(actor, store.read_stream(stream))
        assert final.entries["core.mana"].current == 9
        assert final.entries["core.mana"].definition_version == "mana@2"
        assert final.entries["core.mana"].modifier_ledger == before.entries["core.mana"].modifier_ledger
        assert final == projector.rebuild_resources(actor, store.read_stream(stream)[2:], checkpoint=before)
        with pytest.raises(ValueError, match="resource_migration_already_completed"):
            ResourceMigrationOwner(store=store, definitions=definitions).apply(**{**kwargs, "idempotency_key": "apply:again"})
    finally:
        store.close()
    store.close()


def test_d06_receipt_replay_supports_variable_resource_batch_size(tmp_path):
    path = tmp_path / "resource-d06-single.sqlite3"
    store = DurableGameplayEventStore(path)
    assert store.append_batch(build_atomic_event_batch(
        command_id="legacy:single", principal_ref="legacy-test", stream_id=RESOURCE_STREAM,
        expected_revision=0, event_specs=[("gameplay.resource.materialized", {
            "actor_ref": "char_a", "resource_id": "core.stamina", "minimum": 0,
            "maximum": 10, "current": 10, "definition_version": "v1",
        })], idempotency_key="legacy:single", causation_id="cause", correlation_id="corr",
    )).committed
    assert _pause(ResourceMigrationControlAuthority(store=store), expected_resource_revision=1).committed
    definitions = _migration_definitions()
    kwargs = dict(actor_ref="char_a", migration_id="migration:1", from_definition_version="v1",
                  to_definition_version="v2", migration_digest="sha256:" + "a" * 64,
                  migrator_code_digest=RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST,
                  authority_principal="resource-migration-caller", idempotency_key="apply:single")
    owner = ResourceMigrationOwner(store=store, definitions=definitions)
    first = owner.apply(**kwargs)
    assert first.committed and len(first.committed_event_ids) == 2
    assert owner.apply(**kwargs).idempotency_status == "duplicate_replayed"
    store.close()


def test_d06_apply_must_match_paused_source_and_target_revisions():
    store = GameplayEventStore()
    _legacy_resources(store)
    assert _pause(ResourceMigrationControlAuthority(store=store), expected_resource_revision=3).committed
    owner = ResourceMigrationOwner(store=store, definitions=_migration_definitions())
    before = len(store.read_events())
    with pytest.raises(ValueError, match="migration_revision_pin_mismatch"):
        owner.apply(actor_ref="char_a", migration_id="migration:1", from_definition_version="v1",
                    to_definition_version="v3", migration_digest="sha256:" + "a" * 64,
                    migrator_code_digest=RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST,
                    authority_principal="resource-migration-caller", idempotency_key="apply:wrong-target")
    assert len(store.read_events()) == before


def test_d06_second_v2_migration_rebuilds_after_durable_reopen_and_replays(tmp_path):
    path = tmp_path / "resource-d06-second.sqlite3"
    store = DurableGameplayEventStore(path)
    _legacy_resources(store)
    definitions = _two_stage_migration_definitions()
    control = ResourceMigrationControlAuthority(store=store, definitions=definitions)
    assert _pause(control, expected_resource_revision=3).committed
    first_kwargs = dict(actor_ref="char_a", migration_id="migration:1", from_definition_version="v1",
                        to_definition_version="v2", migration_digest="sha256:" + "a" * 64,
                        migrator_code_digest=RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST,
                        authority_principal="resource-migration-caller", idempotency_key="apply:first")
    owner = ResourceMigrationOwner(store=store, definitions=definitions)
    assert owner.apply(**first_kwargs).committed
    assert control.observe_drain(actor_ref="char_a", migration_id="migration:1",
                                 expected_resource_revision=store.get_stream_head(RESOURCE_STREAM)).status == "drained"
    assert control.pause(actor_ref="char_a", migration_id="migration:2", source_definition_revision="v2",
                         target_definition_revision="v3", schema_digest="schema:resource-v2",
                         codec_digest="codec:resource-v2", migrator_digest=RESOURCE_V2_POLICY_MIGRATOR_CODE_DIGEST,
                         expected_resource_revision=store.get_stream_head(RESOURCE_STREAM),
                         expected_control_revision=store.get_stream_head(CONTROL_STREAM), idempotency_key="pause:2",
                         authority_principal="trusted-migration-caller").committed
    second_kwargs = dict(actor_ref="char_a", migration_id="migration:2", from_definition_version="v2",
                         to_definition_version="v3", migration_digest="sha256:" + "b" * 64,
                         migrator_code_digest=RESOURCE_V2_POLICY_MIGRATOR_CODE_DIGEST,
                         authority_principal="resource-migration-caller", idempotency_key="apply:second")
    assert owner.apply(**second_kwargs).committed
    store.close()
    reopened = DurableGameplayEventStore(path)
    projector = ResourceBodyRuntimeProjector(resource_definitions=definitions)
    events = reopened.read_stream(RESOURCE_STREAM)
    full = projector.rebuild_resources("char_a", events)
    checkpoint = projector.rebuild_resources("char_a", events[:6])
    assert projector.rebuild_resources("char_a", events[6:], checkpoint=checkpoint) == full
    assert {entry.definition_version for entry in full.entries.values()} == {"v3"}
    before = reopened.get_last_global_sequence()
    reopened_owner = ResourceMigrationOwner(store=reopened, definitions=definitions)
    assert reopened_owner.apply(**second_kwargs).idempotency_status == "duplicate_replayed"
    with pytest.raises(ValueError, match="idempotency_reused"):
        reopened_owner.apply(**{**second_kwargs, "migration_digest": "sha256:" + "c" * 64})
    assert reopened_owner.apply(**first_kwargs).idempotency_status == "duplicate_replayed"
    assert ResourceMigrationControlAuthority(store=reopened, definitions=definitions).observe_drain(
        actor_ref="char_a", migration_id="migration:2", expected_resource_revision=reopened.get_stream_head(RESOURCE_STREAM)
    ).status == "drained"
    assert reopened.get_last_global_sequence() == before
    reopened.close()


def test_d06_apply_rejects_migrator_digest_different_from_pause_without_write():
    store = GameplayEventStore()
    _legacy_resources(store)
    assert _pause(ResourceMigrationControlAuthority(store=store),
                  migrator_digest=RESOURCE_V2_POLICY_MIGRATOR_CODE_DIGEST).committed
    before = store.get_last_global_sequence()
    with pytest.raises(ValueError, match="migration_code_digest_pin_mismatch"):
        ResourceMigrationOwner(store=store, definitions=_migration_definitions()).apply(
            actor_ref="char_a", migration_id="migration:1", from_definition_version="v1",
            to_definition_version="v2", migration_digest="sha256:" + "a" * 64,
            migrator_code_digest=RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST,
            authority_principal="resource-migration-caller", idempotency_key="apply:wrong-code")
    assert store.get_last_global_sequence() == before


def test_d06_target_policy_missing_for_one_resource_is_zero_write():
    store = GameplayEventStore()
    _legacy_resources(store)
    assert _pause(ResourceMigrationControlAuthority(store=store)).committed
    definitions = ResourceDefinitionRegistry()
    for resource_id, maximum, capacity in (("core.stamina", 10, 12), ("core.mana", 8, 10), ("core.action_points", 4, 6)):
        definitions.register(ResourceDefinition(resource_id=resource_id, definition_version="v1", minimum=0, maximum=maximum))
        if resource_id != "core.action_points":
            definitions.register(ResourceDefinition(resource_id=resource_id, definition_version="v2", minimum=0,
                                                    maximum=maximum - 1, resource_schema="resource.v2",
                                                    capacity=capacity, base_capacity=capacity))
    before = len(store.read_events())
    with pytest.raises(ValueError, match="resource_definition_unknown"):
        ResourceMigrationOwner(store=store, definitions=definitions).apply(
            actor_ref="char_a", migration_id="migration:1", from_definition_version="v1",
            to_definition_version="v2", migration_digest="sha256:" + "a" * 64,
            migrator_code_digest=RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST,
            authority_principal="resource-migration-caller", idempotency_key="apply:missing-policy")
    assert len(store.read_events()) == before


def test_d06_rejects_resource_write_after_frozen_projection(monkeypatch):
    store = GameplayEventStore()
    _legacy_resources(store)
    assert _pause(ResourceMigrationControlAuthority(store=store)).committed
    definitions = _migration_definitions()
    from app.gameplay.resource_body_runtime import ResourceBoundsMigrationAuthorityService
    original = ResourceBoundsMigrationAuthorityService.plan
    injected = False

    def plan_then_write(self, request, projection):
        nonlocal injected
        plan = original(self, request, projection)
        if not injected:
            injected = True
            assert store.append_batch(build_atomic_event_batch(
                command_id="concurrent:resource", principal_ref="race", stream_id=RESOURCE_STREAM,
                expected_revision=3, event_specs=[("gameplay.resource.concurrent_write", {"actor_ref": "char_a"})],
                idempotency_key="concurrent:resource", causation_id="race", correlation_id="race",
            )).committed
        return plan

    monkeypatch.setattr(ResourceBoundsMigrationAuthorityService, "plan", plan_then_write)
    result = ResourceMigrationOwner(store=store, definitions=definitions).apply(
        actor_ref="char_a", migration_id="migration:1", from_definition_version="v1",
        to_definition_version="v2", migration_digest="sha256:" + "a" * 64,
        migrator_code_digest=RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST,
        authority_principal="resource-migration-caller", idempotency_key="apply:race",
    )
    assert not result.committed
    assert result.failure.error_code == "revision_conflict"
    assert not store.read_events(event_type="gameplay.resource_migration.completed")


def test_d17_completed_migration_id_cannot_be_reopened():
    store = GameplayEventStore()
    _legacy_resources(store)
    control = ResourceMigrationControlAuthority(store=store)
    assert _pause(control).committed
    assert ResourceMigrationOwner(store=store, definitions=_migration_definitions()).apply(
        actor_ref="char_a", migration_id="migration:1", from_definition_version="v1",
        to_definition_version="v2", migration_digest="sha256:" + "a" * 64,
        migrator_code_digest=RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST,
        authority_principal="resource-migration-caller", idempotency_key="apply:1").committed
    before = store.get_last_global_sequence()
    with pytest.raises(ValueError, match="resource_migration_id_already_used"):
        _pause(control, source_definition_revision="v2", target_definition_revision="v3",
               expected_resource_revision=6, expected_control_revision=2,
               idempotency_key="pause:reopen")
    assert store.get_last_global_sequence() == before


def test_d17_active_migration_id_cannot_replace_frozen_contract():
    store = GameplayEventStore()
    _legacy_resources(store)
    control = ResourceMigrationControlAuthority(store=store)
    assert _pause(control).committed
    before = store.get_last_global_sequence()
    with pytest.raises(ValueError, match="resource_migration_id_already_used"):
        _pause(control, target_definition_revision="other-version",
               expected_control_revision=1, idempotency_key="pause:replace")
    assert store.get_last_global_sequence() == before
