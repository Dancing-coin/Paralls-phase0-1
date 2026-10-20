from pathlib import Path
import json
from hashlib import sha256
from dataclasses import replace

import pytest

from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.resource_body_runtime import (
    RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST,
    RESOURCE_V2_POLICY_MIGRATOR_CODE_DIGEST,
    ResourceBoundsMigrationAuthorityService,
    ResourceBoundsMigrationRequest,
    ResourceBodyRuntimeError,
    ResourceBodyRuntimeProjector,
    ResourceDefinition,
    ResourceDefinitionRegistry,
    ResourceStateProjection,
)


ACTOR = "actor:migration-v2"
STREAM = f"gameplay:resources:{ACTOR}"


def _append(store, command_id, event_type, payload):
    return store.append_batch({
        "transaction_id": f"tx:{command_id}", "command_id": command_id,
        "expected_stream_revisions": {STREAM: store.get_stream_head(STREAM)},
        "pinned_revisions": {},
        "events": [{"event_id": f"evt:{command_id}", "event_type": event_type,
                     "schema_version": 1, "stream_id": STREAM, "stream_revision": 0,
                     "global_sequence": 0, "transaction_id": f"tx:{command_id}",
                     "command_id": command_id, "causation_id": command_id,
                     "correlation_id": "migration-v2", "visibility_policy": "authority_only",
                     "payload": payload}],
        "idempotency_record": {"principal_ref": "migration-test", "idempotency_key": command_id,
                                "payload_digest": f"sha256:{command_id}"},
        "outbox_entries": [], "result_digest": f"sha256:{command_id}",
        "projection_refresh_hints": [],
    })


def _defs():
    registry = ResourceDefinitionRegistry()
    registry.register(ResourceDefinition(resource_id="core.stamina", definition_version="legacy", minimum=0, maximum=10))
    registry.register(ResourceDefinition(resource_id="core.stamina", definition_version="v2", minimum=0, maximum=6,
                                         resource_schema="resource.v2", capacity=8, base_capacity=8))
    return registry


def _legacy(store):
    _append(store, "materialize", "gameplay.resource.materialized", {
        "actor_ref": ACTOR, "resource_id": "core.stamina", "minimum": 0,
        "maximum": 10, "current": 9, "definition_version": "legacy",
    })


def _request(projection):
    return ResourceBoundsMigrationRequest(
        actor_ref=ACTOR, resource_id="core.stamina", from_definition_version="legacy",
        to_definition_version="v2", expected_projection_revision=projection.projection_revision,
        migration_digest="sha256:" + "a" * 64,
        migrator_code_digest=RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST,
    )


def test_v2_migration_emits_capacity_fields_and_replays_full_tail(tmp_path: Path):
    path = tmp_path / "migration.sqlite3"
    store = DurableGameplayEventStore(path)
    _legacy(store)
    projector = ResourceBodyRuntimeProjector(resource_definitions=_defs())
    before = projector.rebuild_resources(ACTOR, store.read_events())
    plan = ResourceBoundsMigrationAuthorityService(definitions=_defs()).plan(_request(before), before)
    assert plan.payload["target_resource_schema"] == "resource.v2"
    result = _append(store, "migrate", plan.event_type, dict(plan.payload))
    assert result.committed
    full = projector.rebuild_resources(ACTOR, store.read_events())
    entry = full.entries["core.stamina"]
    assert (entry.current, entry.capacity, entry.base_capacity, entry.locked, entry.debt) == (6, 8, 8, 0, 0)
    checkpoint = projector.rebuild_resources(ACTOR, store.read_events()[:1])
    assert projector.rebuild_resources(ACTOR, store.read_events()[1:], checkpoint=checkpoint) == full
    store.close()
    reopened = DurableGameplayEventStore(path)
    assert ResourceBodyRuntimeProjector(resource_definitions=_defs()).rebuild_resources(ACTOR, reopened.read_events()) == full
    reopened.close()


def test_v2_migration_rejects_open_lock_and_tampered_target(tmp_path: Path):
    store = DurableGameplayEventStore(tmp_path / "reject.sqlite3")
    _legacy(store)
    projector = ResourceBodyRuntimeProjector(resource_definitions=_defs())
    projection = projector.rebuild_resources(ACTOR, store.read_events())
    locked = ResourceStateProjection(projection.actor_ref, projection.entries, projection.reservations,
                                     projection.source_revision_vector, projection.projection_revision,
                                     {"lock": ("reservation", "core.stamina", 1, "open")})
    with pytest.raises(ResourceBodyRuntimeError, match="active_locks"):
        ResourceBoundsMigrationAuthorityService(definitions=_defs()).plan(_request(locked), locked)
    assert len(store.read_stream(STREAM)) == 1
    stale = _request(projection).model_copy(update={"expected_projection_revision": "stale"})
    with pytest.raises(ResourceBodyRuntimeError, match="projection_revision_conflict"):
        ResourceBoundsMigrationAuthorityService(definitions=_defs()).plan(stale, projection)
    assert len(store.read_stream(STREAM)) == 1
    plan = ResourceBoundsMigrationAuthorityService(definitions=_defs()).plan(_request(projection), projection)
    bad = dict(plan.payload, target_capacity=999)
    _append(store, "bad-migrate", plan.event_type, bad)
    with pytest.raises(ResourceBodyRuntimeError, match="v2_policy"):
        projector.rebuild_resources(ACTOR, store.read_events())
    assert len(store.read_stream(STREAM)) == 2
    store.close()


@pytest.mark.parametrize("maximum,current", [(10, 5), (6, 5), (4, 4)])
def test_v2_to_v2_migration_preserves_current_and_applies_versioned_bounds(tmp_path, maximum, current):
    registry = ResourceDefinitionRegistry()
    registry.register(ResourceDefinition(resource_id="core.stamina", definition_version="v2", minimum=0,
                                         maximum=6, resource_schema="resource.v2", capacity=8, base_capacity=8))
    registry.register(ResourceDefinition(resource_id="core.stamina", definition_version="v3", minimum=0,
                                         maximum=maximum, resource_schema="resource.v2", capacity=12, base_capacity=10))
    path = tmp_path / "v2-rebind.sqlite3"
    store = DurableGameplayEventStore(path)
    _append(store, "materialize-v2", "gameplay.resource.materialized", {
        "actor_ref": ACTOR, "resource_id": "core.stamina", "minimum": 0, "maximum": 6,
        "current": 5, "definition_version": "v2", "resource_schema": "resource.v2",
        "capacity": 8, "base_capacity": 8, "locked": 0, "debt": 0,
        "debt_ceiling": 0, "modifier_ledger": [],
        "modifier_ledger_digest": "sha256:" + sha256(b"[]").hexdigest(),
    })
    projector = ResourceBodyRuntimeProjector(resource_definitions=registry)
    before = projector.rebuild_resources(ACTOR, store.read_events())
    request = ResourceBoundsMigrationRequest(
        actor_ref=ACTOR, resource_id="core.stamina", from_definition_version="v2",
        to_definition_version="v3", expected_projection_revision=before.projection_revision,
        migration_digest="sha256:" + "b" * 64,
        migrator_code_digest=RESOURCE_V2_POLICY_MIGRATOR_CODE_DIGEST,
    )
    plan = ResourceBoundsMigrationAuthorityService(definitions=registry).plan(request, before)
    assert _append(store, "rebind", plan.event_type, dict(plan.payload)).committed
    full = projector.rebuild_resources(ACTOR, store.read_events())
    entry = full.entries["core.stamina"]
    assert (entry.current, entry.maximum, entry.capacity, entry.base_capacity) == (current, maximum, 12, 10)
    assert full == projector.rebuild_resources(ACTOR, store.read_events()[1:], checkpoint=before)
    store.close()
    reopened = DurableGameplayEventStore(path)
    try:
        assert ResourceBodyRuntimeProjector(resource_definitions=registry).rebuild_resources(ACTOR, reopened.read_events()) == full
    finally:
        reopened.close()


def test_legacy_source_rejects_v2_migrator_without_writing():
    store = GameplayEventStore()
    _legacy(store)
    before = ResourceBodyRuntimeProjector(resource_definitions=_defs()).rebuild_resources(ACTOR, store.read_events())
    request = _request(before).model_copy(update={"migrator_code_digest": RESOURCE_V2_POLICY_MIGRATOR_CODE_DIGEST})
    with pytest.raises(ResourceBodyRuntimeError, match="legacy_migrator"):
        ResourceBoundsMigrationAuthorityService(definitions=_defs()).plan(request, before)
    assert len(store.read_events()) == 1


def test_v2_migration_rejects_modifier_ledger_substitution():
    registry = ResourceDefinitionRegistry()
    registry.register(ResourceDefinition(resource_id="core.stamina", definition_version="v2", minimum=0,
                                         maximum=6, resource_schema="resource.v2", capacity=8, base_capacity=8))
    registry.register(ResourceDefinition(resource_id="core.stamina", definition_version="v3", minimum=0,
                                         maximum=6, resource_schema="resource.v2", capacity=9, base_capacity=8))
    store = GameplayEventStore()
    _append(store, "materialize-modifier", "gameplay.resource.materialized", {
        "actor_ref": ACTOR, "resource_id": "core.stamina", "minimum": 0, "maximum": 6,
        "current": 5, "definition_version": "v2", "resource_schema": "resource.v2",
        "capacity": 8, "base_capacity": 8, "locked": 0, "debt": 0, "debt_ceiling": 0,
        "modifier_ledger": [{"modifier_ref": "mod:a", "operation": "capacity_delta", "amount": 1,
                              "source_event_id": "evt:mod:a", "template_id": "resource-capacity:a@1"}],
        "modifier_ledger_digest": "sha256:" + sha256(json.dumps([{"modifier_ref": "mod:a", "operation": "capacity_delta", "amount": 1,
                              "source_event_id": "evt:mod:a", "template_id": "resource-capacity:a@1"}], sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
    })
    before = ResourceBodyRuntimeProjector(resource_definitions=registry).rebuild_resources(ACTOR, store.read_events())
    request = ResourceBoundsMigrationRequest(actor_ref=ACTOR, resource_id="core.stamina", from_definition_version="v2",
        to_definition_version="v3", expected_projection_revision=before.projection_revision,
        migration_digest="sha256:" + "c" * 64, migrator_code_digest=RESOURCE_V2_POLICY_MIGRATOR_CODE_DIGEST)
    plan = ResourceBoundsMigrationAuthorityService(definitions=registry).plan(request, before)
    bad_ledger = [{"modifier_ref": "mod:substitute", "operation": "capacity_delta", "amount": 99,
                   "source_event_id": "evt:substitute", "template_id": "resource-capacity:substitute@1"}]
    bad = dict(plan.payload, target_modifier_ledger=bad_ledger,
               target_modifier_ledger_digest="sha256:" + sha256(json.dumps(bad_ledger, sort_keys=True, separators=(",", ":")).encode()).hexdigest())
    _append(store, "bad-ledger-substitution", plan.event_type, bad)
    with pytest.raises(ResourceBodyRuntimeError, match="v2_policy"):
        ResourceBodyRuntimeProjector(resource_definitions=registry).rebuild_resources(ACTOR, store.read_events())


@pytest.mark.parametrize("change", [
    {"migration_kind": "resource.v2.policy.rebind.v1"},
    {"migrator_code_digest": RESOURCE_V2_POLICY_MIGRATOR_CODE_DIGEST},
])
def test_replay_rejects_migrator_identity_not_bound_to_source(change):
    store = GameplayEventStore()
    _legacy(store)
    projector = ResourceBodyRuntimeProjector(resource_definitions=_defs())
    before = projector.rebuild_resources(ACTOR, store.read_events())
    plan = ResourceBoundsMigrationAuthorityService(definitions=_defs()).plan(_request(before), before)
    _append(store, "tampered-migrator", plan.event_type, {**plan.payload, **change})
    with pytest.raises(ResourceBodyRuntimeError, match="legacy_policy"):
        projector.rebuild_resources(ACTOR, store.read_events())
