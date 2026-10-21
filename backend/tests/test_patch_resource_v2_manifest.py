import pytest

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.patch_lifecycle_authority import (
    GameplayPatchLifecycleAuthorityError,
    GameplayPatchLifecycleAuthorityService,
    ResourceBoundsMigrationContext,
)
from app.gameplay.patch_runtime import ResourceMigrationTargetDefinition, GameplayPatchRegistry
from app.gameplay.resource_body_runtime import ResourceBodyRuntimeProjector, ResourceDefinition, ResourceDefinitionRegistry
from app.gameplay.runtime_state import StateGroupDefinition, StateGroupRegistry

from test_gameplay_patch_lifecycle_authority import (
    _active_set_command, _context, _install_command, _manifest,
    _materialize_versioned_resource, _resource_bounds_clamp, _state_group_context,
)


def test_resource_migration_manifest_pins_v2_target_policy_in_digest():
    migration = _resource_bounds_clamp()
    pinned = migration.model_copy(update={
        "target_resource_definition": ResourceMigrationTargetDefinition(
            resource_schema="resource.v2", capacity=8, base_capacity=8, debt_ceiling=0
        )
    })
    assert pinned.target_resource_definition is not None
    assert pinned.expected_migration_digest() != migration.expected_migration_digest()
    assert pinned.model_dump(mode="json")["target_resource_definition"] == {
        "resource_schema": "resource.v2", "capacity": 8,
        "base_capacity": 8, "debt_ceiling": 0,
    }


def _setup_v2_migration(*, target_policy: ResourceMigrationTargetDefinition):
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    state_groups = StateGroupRegistry()
    state_groups.register(StateGroupDefinition(group_id="core.resources", definition_version="1.0.0", projection_schema_version=1))
    state_groups.register(StateGroupDefinition(group_id="core.resources", definition_version="2.0.0", projection_schema_version=2))
    resource_definitions = ResourceDefinitionRegistry()
    resource_definitions.register(ResourceDefinition(resource_id="core.stamina", definition_version="1.0.0", minimum=0, maximum=10))
    resource_definitions.register(ResourceDefinition(resource_id="core.stamina", definition_version="2.0.0", minimum=0, maximum=6,
                                                     resource_schema="resource.v2", capacity=8, base_capacity=8))
    store = GameplayEventStore()
    service = GameplayPatchLifecycleAuthorityService(store=store, registry=registry,
                                                     state_group_registry=state_groups,
                                                     resource_definition_registry=resource_definitions)
    v1 = _manifest(revision="patch:v2@1.0.0", version="1.0.0", state_group_ids=("core.resources",))
    migration = _resource_bounds_clamp().model_copy(update={"target_resource_definition": target_policy})
    migration = migration.model_copy(update={"migration_digest": migration.expected_migration_digest()})
    v2 = _manifest(revision="patch:v2@2.0.0", version="2.0.0", state_group_ids=("core.resources",),
                   state_group_migrations=(migration,), event_schemas=(migration.input_event_schema, migration.output_event_schema))
    service.install_candidate(_install_command(v1, command_id="install-v1"), _context(registry))
    service.install_candidate(_install_command(v2, command_id="install-v2"), _context(registry))
    v1_target = registry.compose_active_set((v1.patch_revision_id,))
    enabled = service.apply_active_set(_active_set_command(operation="enable", patch_revision_ids=(v1.patch_revision_id,), command_id="enable-v1", state_group_actor_refs=("actor:char_a",)),
                                      _context(registry, state_group_contexts=(_state_group_context(actor_ref="actor:char_a", active_patch_set_revision=v1_target.active_patch_set_revision, definition_version="1.0.0"),)))
    _materialize_versioned_resource(store)
    projection = ResourceBodyRuntimeProjector(resource_definitions=resource_definitions).rebuild_resources("actor:char_a", store.read_events())
    return registry, service, store, resource_definitions, projection, enabled, v1, v2


def test_apply_active_set_v2_migration_commits_target_policy():
    policy = ResourceMigrationTargetDefinition(resource_schema="resource.v2", capacity=8, base_capacity=8, debt_ceiling=0)
    registry, service, store, definitions, projection, enabled, _, v2 = _setup_v2_migration(target_policy=policy)
    target = registry.compose_active_set((v2.patch_revision_id,))
    result = service.apply_active_set(
        _active_set_command(operation="upgrade", patch_revision_ids=(v2.patch_revision_id,), command_id="upgrade-v2", state_group_actor_refs=("actor:char_a",)),
        _context(registry, active_revision=enabled.active_patch_set.active_patch_set_revision,
                 state_group_contexts=(_state_group_context(actor_ref="actor:char_a", active_patch_set_revision=enabled.active_patch_set.active_patch_set_revision, definition_version="1.0.0"),),
                 resource_bounds_migration_contexts=(ResourceBoundsMigrationContext(actor_ref="actor:char_a", resource_id="core.stamina", expected_projection_revision=projection.projection_revision),)),
    )
    assert result.changed and result.active_patch_set == target
    entry = ResourceBodyRuntimeProjector(resource_definitions=definitions).rebuild_resources("actor:char_a", store.read_events()).entries["core.stamina"]
    assert (entry.definition_version, entry.capacity, entry.base_capacity) == ("2.0.0", 8, 8)


def test_apply_active_set_v2_target_mismatch_is_zero_write():
    policy = ResourceMigrationTargetDefinition(resource_schema="resource.v2", capacity=7, base_capacity=7, debt_ceiling=0)
    registry, service, store, _, projection, enabled, _, v2 = _setup_v2_migration(target_policy=policy)
    before = list(store.read_events())
    with pytest.raises(GameplayPatchLifecycleAuthorityError, match="target_definition_mismatch"):
        service.apply_active_set(_active_set_command(operation="upgrade", patch_revision_ids=(v2.patch_revision_id,), command_id="upgrade-bad", state_group_actor_refs=("actor:char_a",)),
                                _context(registry, active_revision=enabled.active_patch_set.active_patch_set_revision,
                                         state_group_contexts=(_state_group_context(actor_ref="actor:char_a", active_patch_set_revision=enabled.active_patch_set.active_patch_set_revision, definition_version="1.0.0"),),
                                         resource_bounds_migration_contexts=(ResourceBoundsMigrationContext(actor_ref="actor:char_a", resource_id="core.stamina", expected_projection_revision=projection.projection_revision),)))
    assert store.read_events() == before
