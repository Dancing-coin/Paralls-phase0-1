from __future__ import annotations

import pytest

from app.gameplay.runtime_state import (
    CharacterGameRuntimeStateBuilder,
    StateGroupDefinition,
    StateGroupRegistry,
    StateGroupRegistryError,
)


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
