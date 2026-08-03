from __future__ import annotations

import pytest

from app.gameplay.runtime_state import (
    CharacterGameRuntimeStateBuilder,
    StateGroupLifecycleError,
    StateGroupLifecycleProjector,
    StateGroupDefinition,
    StateGroupRegistry,
    StateGroupRegistryError,
)
from app.gameplay.models import GameplayEvent


def _definition(
    group_id: str,
    *,
    dependencies: tuple[str, ...] = (),
    conflicts: tuple[str, ...] = (),
) -> StateGroupDefinition:
    return StateGroupDefinition(
        group_id=group_id,
        definition_version="1.0.0",
        projection_schema_version=1,
        dependencies=dependencies,
        conflicts=conflicts,
    )


def _lifecycle_event(
    event_id: str,
    event_type: str,
    *,
    sequence: int,
    group_id: str = "core.resources",
    definition_version: str = "1.0.0",
    source_patch_revision: str = "patch:demo:v1",
    actor_ref: str = "actor:char_a",
) -> GameplayEvent:
    return GameplayEvent(
        event_id=event_id,
        event_type=event_type,
        schema_version=1,
        stream_id="gameplay:state-groups:actor:char_a",
        stream_revision=sequence,
        global_sequence=sequence,
        transaction_id=f"tx:{event_id}",
        command_id=f"cmd:{event_id}",
        causation_id=f"cause:{event_id}",
        correlation_id=f"corr:{event_id}",
        visibility_policy="authority_only",
        payload={
            "actor_ref": actor_ref,
            "group_id": group_id,
            "definition_version": definition_version,
            "source_patch_revision": source_patch_revision,
        },
    )


def test_registry_resolves_dependencies_in_deterministic_order() -> None:
    registry = StateGroupRegistry()
    registry.register(_definition("core.status_tags"))
    registry.register(_definition("core.resources"))
    registry.register(_definition("adventure.body_runtime", dependencies=("core.resources", "core.status_tags")))

    assert registry.resolve_load_order(["adventure.body_runtime"]) == [
        "core.resources",
        "core.status_tags",
        "adventure.body_runtime",
    ]


def test_registry_rejects_unknown_dependencies_and_enabled_conflicts() -> None:
    registry = StateGroupRegistry()
    registry.register(_definition("core.resources", dependencies=("core.absent",)))

    with pytest.raises(StateGroupRegistryError, match="dependency_missing"):
        registry.resolve_load_order(["core.resources"])

    registry = StateGroupRegistry()
    registry.register(_definition("core.resources", conflicts=("core.status_tags",)))
    registry.register(_definition("core.status_tags"))

    with pytest.raises(StateGroupRegistryError, match="state_group_conflict"):
        registry.resolve_load_order(["core.resources", "core.status_tags"])


def test_registry_keeps_historical_definitions_and_requires_explicit_selection() -> None:
    registry = StateGroupRegistry()
    registry.register(_definition("core.resources"))
    registry.register(
        StateGroupDefinition(
            group_id="core.resources",
            definition_version="2.0.0",
            projection_schema_version=2,
        )
    )

    assert registry.resolve("core.resources", "1.0.0").projection_schema_version == 1
    assert registry.resolve("core.resources", "2.0.0").projection_schema_version == 2
    with pytest.raises(StateGroupRegistryError, match="definition_version_required"):
        registry.resolve("core.resources")
    with pytest.raises(StateGroupRegistryError, match="definition_version_required"):
        registry.resolve_load_order(["core.resources"])
    assert registry.resolve_load_order(
        ["core.resources"],
        definition_versions={"core.resources": "1.0.0"},
    ) == ["core.resources"]


def test_lifecycle_replay_resolves_the_version_committed_by_each_historical_event() -> None:
    registry = StateGroupRegistry()
    registry.register(_definition("core.resources"))
    registry.register(
        StateGroupDefinition(
            group_id="core.resources",
            definition_version="2.0.0",
            projection_schema_version=2,
        )
    )

    lifecycle = StateGroupLifecycleProjector(registry).rebuild(
        "actor:char_a",
        [
            _lifecycle_event("event:materialized", "gameplay.state_group.materialized", sequence=1),
            _lifecycle_event("event:enabled", "gameplay.state_group.enabled", sequence=2),
        ],
    )

    assert lifecycle.records["core.resources"].definition_version == "1.0.0"
    state = CharacterGameRuntimeStateBuilder(registry).build_from_lifecycle(
        lifecycle=lifecycle,
        group_payloads={"core.resources": {"stamina": 7}},
        registry_revision="registry:core:v1",
        world_config_revision="world:demo:v1",
        active_patch_set_revision="patches:demo:v1",
    )
    assert state.groups["core.resources"].definition_version == "1.0.0"


def test_read_only_facade_has_only_enabled_groups_and_stable_checksum() -> None:
    registry = StateGroupRegistry()
    registry.register(_definition("core.resources"))
    registry.register(_definition("core.status_tags"))
    builder = CharacterGameRuntimeStateBuilder(registry)

    state = builder.build(
        actor_ref="actor:char_a",
        enabled_group_ids=["core.status_tags", "core.resources"],
        group_payloads={
            "core.resources": {"stamina": 7},
            "core.status_tags": {"tags": ["steady"]},
            "unenabled.internal": {"must_not_leak": True},
        },
        source_revision_vector={"stream:char_a:resources": 3, "stream:char_a:status": 2},
        registry_revision="registry:core:v1",
        world_config_revision="world:demo:v1",
        active_patch_set_revision="patches:demo:v1",
    )

    assert state.enabled_state_groups == ("core.resources", "core.status_tags")
    assert set(state.groups) == {"core.resources", "core.status_tags"}
    assert state.groups["core.resources"].payload == {"stamina": 7}
    assert state.source_revision_vector == {
        "stream:char_a:resources": 3,
        "stream:char_a:status": 2,
    }
    assert state.snapshot_checksum == builder.build(
        actor_ref="actor:char_a",
        enabled_group_ids=["core.resources", "core.status_tags"],
        group_payloads={"core.resources": {"stamina": 7}, "core.status_tags": {"tags": ["steady"]}},
        source_revision_vector={"stream:char_a:resources": 3, "stream:char_a:status": 2},
        registry_revision="registry:core:v1",
        world_config_revision="world:demo:v1",
        active_patch_set_revision="patches:demo:v1",
    ).snapshot_checksum


def test_lifecycle_projector_rebuilds_enabled_groups_from_committed_events() -> None:
    registry = StateGroupRegistry()
    registry.register(_definition("core.resources"))
    lifecycle = StateGroupLifecycleProjector(registry).rebuild(
        "actor:char_a",
        [
            _lifecycle_event("event:materialized", "gameplay.state_group.materialized", sequence=1),
            _lifecycle_event("event:enabled", "gameplay.state_group.enabled", sequence=2),
        ],
    )

    state = CharacterGameRuntimeStateBuilder(registry).build_from_lifecycle(
        lifecycle=lifecycle,
        group_payloads={"core.resources": {"stamina": 7}},
        registry_revision="registry:core:v1",
        world_config_revision="world:demo:v1",
        active_patch_set_revision="patches:demo:v1",
    )

    assert lifecycle.enabled_group_ids == ("core.resources",)
    assert lifecycle.records["core.resources"].lifecycle_state == "enabled"
    assert state.enabled_state_groups == ("core.resources",)
    assert state.groups["core.resources"].payload == {"stamina": 7}


def test_lifecycle_projector_rejects_enable_before_materialization_or_wrong_actor() -> None:
    registry = StateGroupRegistry()
    registry.register(_definition("core.resources"))
    projector = StateGroupLifecycleProjector(registry)

    with pytest.raises(StateGroupLifecycleError, match="enable_before_materialization"):
        projector.rebuild(
            "actor:char_a",
            [_lifecycle_event("event:enabled", "gameplay.state_group.enabled", sequence=1)],
        )
    with pytest.raises(StateGroupLifecycleError, match="actor_mismatch"):
        projector.rebuild(
            "actor:char_a",
            [_lifecycle_event("event:materialized", "gameplay.state_group.materialized", sequence=1, actor_ref="actor:char_b")],
        )


def test_lifecycle_projector_excludes_dormant_and_disabled_groups_from_facade() -> None:
    registry = StateGroupRegistry()
    registry.register(_definition("core.resources"))
    lifecycle = StateGroupLifecycleProjector(registry).rebuild(
        "actor:char_a",
        [
            _lifecycle_event("event:materialized", "gameplay.state_group.materialized", sequence=1),
            _lifecycle_event("event:enabled", "gameplay.state_group.enabled", sequence=2),
            _lifecycle_event("event:dormant", "gameplay.state_group.dormant", sequence=3),
            _lifecycle_event("event:disabled", "gameplay.state_group.disabled", sequence=4),
        ],
    )

    state = CharacterGameRuntimeStateBuilder(registry).build_from_lifecycle(
        lifecycle=lifecycle,
        group_payloads={"core.resources": {"stamina": 7}},
        registry_revision="registry:core:v1",
        world_config_revision="world:demo:v1",
        active_patch_set_revision="patches:demo:v1",
    )

    assert lifecycle.enabled_group_ids == ()
    assert lifecycle.records["core.resources"].lifecycle_state == "disabled"
    assert state.groups == {}


def test_lifecycle_projector_ignores_duplicate_event_delivery_and_rejects_definition_drift() -> None:
    registry = StateGroupRegistry()
    registry.register(_definition("core.resources"))
    materialized = _lifecycle_event("event:materialized", "gameplay.state_group.materialized", sequence=1)
    enabled = _lifecycle_event("event:enabled", "gameplay.state_group.enabled", sequence=2)

    lifecycle = StateGroupLifecycleProjector(registry).rebuild("actor:char_a", [materialized, materialized, enabled])

    assert lifecycle.applied_event_ids == ("event:materialized", "event:enabled")
    with pytest.raises(StateGroupLifecycleError, match="definition_version_mismatch"):
        StateGroupLifecycleProjector(registry).rebuild(
            "actor:char_a",
            [
                materialized,
                _lifecycle_event(
                    "event:enabled:drift",
                    "gameplay.state_group.enabled",
                    sequence=2,
                    definition_version="2.0.0",
                ),
            ],
        )
