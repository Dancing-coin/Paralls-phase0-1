from decimal import Decimal
from types import MappingProxyType

import pytest

from app.gameplay.effective_stats import EffectiveStatResolver, StatBaseline
from app.gameplay.inventory_runtime import EncumbranceProjection, InventoryItem, InventoryProjection
from app.gameplay.models import GameplayEvent
from app.gameplay.phase3_state_composer import Phase3CheckpointReplay, Phase3StateComposer, Phase3StateComposerError
from app.gameplay.resource_body_runtime import (
    RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST,
    RESOURCE_BOUNDS_CLAMP_MIGRATOR_ID,
    BodyRuntimeProjection,
    ResourceBodyRuntimeProjector,
    ResourceDefinition,
    ResourceDefinitionRegistry,
    ResourceEntry,
    ResourceStateProjection,
)
from app.gameplay.runtime_state import CharacterGameRuntimeStateBuilder, StateGroupDefinition, StateGroupLifecycleProjection, StateGroupLifecycleProjector, StateGroupRegistry
from app.gameplay.status_tags import StatusTagDefinition, StatusTagModifierTemplate, StatusTagProjector, StatusTagRegistry, StatusTagStateProjection


def _registry() -> StateGroupRegistry:
    registry = StateGroupRegistry()
    for group_id in ("core.resources", "core.body_runtime", "core.status_tags", "core.effective_stats", "core.inventory", "core.encumbrance"):
        registry.register(StateGroupDefinition(group_id=group_id, definition_version="1", projection_schema_version=1))
    return registry


def _lifecycle(*groups: str) -> StateGroupLifecycleProjection:
    return StateGroupLifecycleProjection(actor_ref="actor:a", records=MappingProxyType({}), enabled_group_ids=groups, source_revision_vector=MappingProxyType({"gameplay:state_groups:actor:a": 4}), applied_event_ids=(), lifecycle_revision="lifecycle:test")


def _resources(actor_ref: str = "actor:a") -> ResourceStateProjection:
    return ResourceStateProjection(actor_ref=actor_ref, entries=MappingProxyType({"core.stamina": ResourceEntry("core.stamina", "legacy-v0", 7, 0, 10, "evt:stamina")}), reservations=MappingProxyType({}), source_revision_vector=MappingProxyType({"gameplay:resources:actor:a": 1}), projection_revision="projection:resources")


def _body() -> BodyRuntimeProjection:
    return BodyRuntimeProjection(actor_ref="actor:a", injuries=MappingProxyType({}), functions=MappingProxyType({}), source_revision_vector=MappingProxyType({}), projection_revision="projection:body")


def _tags() -> StatusTagStateProjection:
    return StatusTagStateProjection(actor_ref="actor:a", active_instances=MappingProxyType({}), source_revision_vector=MappingProxyType({}), projection_revision="projection:tags")


def test_composer_includes_only_lifecycle_enabled_groups_without_write_api() -> None:
    stat = EffectiveStatResolver().resolve(StatBaseline(stat_id="combat.power", value=Decimal("10"), source_ref="profile"), [])
    state = Phase3StateComposer(facade_builder=CharacterGameRuntimeStateBuilder(_registry())).compose(
        lifecycle=_lifecycle("core.resources", "core.effective_stats"),
        resources=_resources(), body=_body(), tags=_tags(), effective_stats={"combat.power": stat},
        registry_revision="registry:v1", world_config_revision="world:v1", active_patch_set_revision="patch:v1",
    )

    assert state.enabled_state_groups == ("core.effective_stats", "core.resources")
    assert set(state.groups) == {"core.resources", "core.effective_stats"}
    assert state.groups["core.resources"].payload["entries"]["core.stamina"]["available"] == 7
    assert not hasattr(state, "update")


def test_composer_rejects_cross_actor_projection() -> None:
    composer = Phase3StateComposer(facade_builder=CharacterGameRuntimeStateBuilder(_registry()))
    with pytest.raises(Phase3StateComposerError, match="actor_ref_mismatch"):
        composer.compose(lifecycle=_lifecycle("core.resources"), resources=_resources("actor:other"), body=_body(), tags=_tags(), effective_stats={}, registry_revision="registry:v1", world_config_revision="world:v1", active_patch_set_revision="patch:v1")


def test_composer_includes_lifecycle_enabled_inventory_read_models_only() -> None:
    inventory = InventoryProjection("actor:a", MappingProxyType({"item:stone": InventoryItem("item:stone", "stone", 1, "evt:item")}), MappingProxyType({}), MappingProxyType({"item:stone": "container:bag"}), MappingProxyType({"gameplay:inventory:actor:a": 2}), "inventory:test")
    encumbrance = EncumbranceProjection("actor:a", 2, 1, MappingProxyType({"item:stone": 2}), inventory.source_revision_vector, "encumbrance:test")
    state = Phase3StateComposer(facade_builder=CharacterGameRuntimeStateBuilder(_registry())).compose(lifecycle=_lifecycle("core.inventory", "core.encumbrance"), resources=_resources(), body=_body(), tags=_tags(), effective_stats={}, inventory=inventory, encumbrance=encumbrance, registry_revision="registry:v1", world_config_revision="world:v1", active_patch_set_revision="patch:v1")
    assert state.groups["core.inventory"].payload["locations"] == {"item:stone": "container:bag"}
    assert state.groups["core.encumbrance"].payload["carried_weight"] == 2


def _event(event_id: str, event_type: str, stream_id: str, stream_revision: int, sequence: int, payload: dict[str, object]) -> GameplayEvent:
    return GameplayEvent(event_id=event_id, event_type=event_type, schema_version=1, stream_id=stream_id, stream_revision=stream_revision, global_sequence=sequence, transaction_id=f"tx:{event_id}", command_id=f"cmd:{event_id}", causation_id=event_id, correlation_id="corr:phase3", visibility_policy="authority_only", payload=payload)


def test_phase3_checkpoint_plus_tail_matches_full_domain_facade_rebuild() -> None:
    groups = _registry()
    tag_registry = StatusTagRegistry()
    tag_registry.register(StatusTagDefinition(tag_id="blessed", definition_version="1", modifier_templates=(StatusTagModifierTemplate(template_id="power", stat_id="combat.power", operation="additive", value="2", stacking_key="blessed"),)))
    lifecycle_stream = "gameplay:state_groups:actor:a"
    events = []
    for index, group_id in enumerate(("core.resources", "core.body_runtime", "core.status_tags", "core.effective_stats"), start=1):
        events.append(_event(f"materialize:{group_id}", "gameplay.state_group.materialized", lifecycle_stream, index * 2 - 1, index * 2 - 1, {"actor_ref": "actor:a", "group_id": group_id, "definition_version": "1", "source_patch_revision": "patch:v1"}))
        events.append(_event(f"enable:{group_id}", "gameplay.state_group.enabled", lifecycle_stream, index * 2, index * 2, {"actor_ref": "actor:a", "group_id": group_id, "definition_version": "1", "source_patch_revision": "patch:v1"}))
    events.extend([
        _event("resource", "gameplay.resource.materialized", "gameplay:resources:actor:a", 1, 9, {"actor_ref": "actor:a", "resource_id": "core.stamina", "minimum": 0, "maximum": 10, "current": 7}),
        _event("injury", "gameplay.body.injury_applied", "gameplay:body:actor:a", 1, 10, {"actor_ref": "actor:a", "injury_id": "injury:right", "function_id": "grip.right", "capacity_ratio": 0}),
        _event("tag", "gameplay.status_tag.applied", "gameplay:status_tags:actor:a", 1, 11, {"actor_ref": "actor:a", "tag_id": "blessed", "instance_id": "tag:blessed", "source_ref": "source:blessed", "stack_count": 1}),
        _event("recover", "gameplay.body.injury_recovered", "gameplay:body:actor:a", 2, 12, {"actor_ref": "actor:a", "injury_id": "injury:right"}),
        _event("remove", "gameplay.status_tag.removed", "gameplay:status_tags:actor:a", 2, 13, {"actor_ref": "actor:a", "tag_id": "blessed", "instance_id": "tag:blessed"}),
    ])
    composer = Phase3StateComposer(facade_builder=CharacterGameRuntimeStateBuilder(groups))
    replay = Phase3CheckpointReplay(lifecycle_projector=StateGroupLifecycleProjector(groups), resource_body_projector=ResourceBodyRuntimeProjector(), status_tag_projector=StatusTagProjector(tag_registry), composer=composer, baselines={"combat.power": StatBaseline(stat_id="combat.power", value=Decimal("10"), source_ref="profile")})

    full = replay.checkpoint_plus_tail(replay.checkpoint("actor:a", events), [], registry_revision="registry:v1", world_config_revision="world:v1", active_patch_set_revision="patch:v1")
    checkpointed = replay.checkpoint_plus_tail(replay.checkpoint("actor:a", events[:11]), events[11:], registry_revision="registry:v1", world_config_revision="world:v1", active_patch_set_revision="patch:v1")

    assert checkpointed.snapshot_checksum == full.snapshot_checksum
    assert checkpointed.groups["core.resources"].payload["entries"]["core.stamina"]["available"] == 7
    assert checkpointed.groups["core.body_runtime"].payload["functions"] == {}
    assert checkpointed.groups["core.status_tags"].payload["active_instances"] == {}
    assert checkpointed.groups["core.effective_stats"].payload["entries"]["combat.power"]["effective_value"] == "10"


def test_phase3_replay_composes_a_versioned_resource_migration_from_checkpoint_plus_tail() -> None:
    groups = StateGroupRegistry()
    groups.register(StateGroupDefinition(group_id="core.resources", definition_version="1.0.0", projection_schema_version=1))
    groups.register(StateGroupDefinition(group_id="core.resources", definition_version="2.0.0", projection_schema_version=2))
    resource_definitions = ResourceDefinitionRegistry()
    resource_definitions.register(ResourceDefinition(resource_id="core.stamina", definition_version="1.0.0", minimum=0, maximum=10))
    resource_definitions.register(ResourceDefinition(resource_id="core.stamina", definition_version="2.0.0", minimum=0, maximum=6))
    migration_digest = "sha256:" + "a" * 64
    lifecycle_stream = "gameplay:state_groups:actor:a"
    resource_stream = "gameplay:resources:actor:a"
    events = [
        _event("group:materialize", "gameplay.state_group.materialized", lifecycle_stream, 1, 1, {"actor_ref": "actor:a", "group_id": "core.resources", "definition_version": "1.0.0", "source_patch_revision": "patch:v1"}),
        _event("group:enable", "gameplay.state_group.enabled", lifecycle_stream, 2, 2, {"actor_ref": "actor:a", "group_id": "core.resources", "definition_version": "1.0.0", "source_patch_revision": "patch:v1"}),
        _event("resource:materialize", "gameplay.resource.materialized", resource_stream, 1, 3, {"actor_ref": "actor:a", "resource_id": "core.stamina", "definition_version": "1.0.0", "minimum": 0, "maximum": 10, "current": 8}),
        _event("resource:migrated", "gameplay.resource.bounds_migrated", resource_stream, 2, 4, {"actor_ref": "actor:a", "resource_id": "core.stamina", "from_definition_version": "1.0.0", "to_definition_version": "2.0.0", "source_minimum": 0, "source_maximum": 10, "target_minimum": 0, "target_maximum": 6, "previous_current": 8, "next_current": 6, "lost_amount": 2, "migration_kind": RESOURCE_BOUNDS_CLAMP_MIGRATOR_ID, "migration_digest": migration_digest, "migrator_code_digest": RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST}),
        _event("group:migrated", "gameplay.state_group.migrated", lifecycle_stream, 3, 5, {"actor_ref": "actor:a", "group_id": "core.resources", "from_definition_version": "1.0.0", "to_definition_version": "2.0.0", "previous_source_patch_revision": "patch:v1", "next_source_patch_revision": "patch:v2", "migration_kind": "resource_bounds_clamp", "migration_digest": migration_digest, "migrator_code_digest": RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST, "domain_event_id": "resource:migrated"}),
    ]
    replay = Phase3CheckpointReplay(
        lifecycle_projector=StateGroupLifecycleProjector(groups),
        resource_body_projector=ResourceBodyRuntimeProjector(resource_definitions=resource_definitions),
        status_tag_projector=StatusTagProjector(StatusTagRegistry()),
        composer=Phase3StateComposer(facade_builder=CharacterGameRuntimeStateBuilder(groups)),
        baselines={},
    )

    full = replay.checkpoint_plus_tail(
        replay.checkpoint("actor:a", events),
        [],
        registry_revision="registry:v2",
        world_config_revision="world:v1",
        active_patch_set_revision="patch:v2",
    )
    checkpointed = replay.checkpoint_plus_tail(
        replay.checkpoint("actor:a", events[:3]),
        events[3:],
        registry_revision="registry:v2",
        world_config_revision="world:v1",
        active_patch_set_revision="patch:v2",
    )

    assert checkpointed.snapshot_checksum == full.snapshot_checksum
    assert checkpointed.groups["core.resources"].definition_version == "2.0.0"
    assert checkpointed.groups["core.resources"].payload["entries"]["core.stamina"]["current"] == 6
    assert checkpointed.groups["core.resources"].payload["entries"]["core.stamina"]["maximum"] == 6
