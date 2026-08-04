"""Configured, backend-owned Phase 3 sources for the Godot gameplay mirror."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from pydantic import ConfigDict, Field, model_validator

from app.gameplay.effective_stats import EffectiveStatResolver, StatBaseline
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.godot_mirror_delivery import GameplayGodotProjectionPublisher
from app.gameplay.models import StrictGameplayModel
from app.gameplay.phase3_state_composer import Phase3StateComposer
from app.gameplay.resource_body_runtime import (
    ResourceBodyRuntimeProjector,
    ResourceDefinition,
    ResourceDefinitionRegistry,
)
from app.gameplay.runtime_state import CharacterGameRuntimeStateBuilder, StateGroupDefinition, StateGroupLifecycleProjector, StateGroupRegistry
from app.gameplay.state_group_views import StateGroupConsumerViewPolicy, StateGroupViewProjector
from app.gameplay.status_tags import StatusTagDefinition, StatusTagProjector, StatusTagRegistry, active_status_tag_modifiers


class Phase3MirrorSourceError(ValueError):
    """Raised when a backend mirror source configuration cannot compose safely."""


_SUPPORTED_GROUP_IDS = frozenset(
    {
        "core.resources",
        "core.body_runtime",
        "core.status_tags",
        "core.effective_stats",
    }
)


class Phase3MirrorActorConfiguration(StrictGameplayModel):
    """Explicit backend configuration for one read-only Phase 3 actor source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_ref: str = Field(min_length=1)
    state_group_definitions: tuple[StateGroupDefinition, ...] = Field(min_length=1)
    godot_view_policies: tuple[StateGroupConsumerViewPolicy, ...] = ()
    godot_allowed_group_ids: tuple[str, ...] = ()
    resource_definitions: tuple[ResourceDefinition, ...] = ()
    status_tag_definitions: tuple[StatusTagDefinition, ...] = ()
    stat_baselines: tuple[StatBaseline, ...] = ()
    registry_revision: str = Field(min_length=1)
    world_config_revision: str = Field(min_length=1)
    active_patch_set_revision: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_mirror_source_scope(self) -> "Phase3MirrorActorConfiguration":
        group_ids = tuple(item.group_id for item in self.state_group_definitions)
        definition_keys = tuple(
            (item.group_id, item.definition_version)
            for item in self.state_group_definitions
        )
        if len(set(definition_keys)) != len(definition_keys):
            raise ValueError("phase3_mirror_state_group_definition_duplicate")
        unsupported = set(group_ids).difference(_SUPPORTED_GROUP_IDS)
        if unsupported:
            raise ValueError("phase3_mirror_state_group_unsupported")
        allowed = self.godot_allowed_group_ids or group_ids
        if set(allowed).difference(group_ids):
            raise ValueError("phase3_mirror_godot_group_unknown")
        policy_ids = tuple(item.group_id for item in self.godot_view_policies)
        if len(set(policy_ids)) != len(policy_ids) or set(policy_ids).difference(group_ids):
            raise ValueError("phase3_mirror_godot_policy_invalid")
        if set(allowed).difference(policy_ids):
            raise ValueError("phase3_mirror_godot_policy_required")
        resource_definition_keys = tuple(
            (item.resource_id, item.definition_version)
            for item in self.resource_definitions
        )
        if len(set(resource_definition_keys)) != len(resource_definition_keys):
            raise ValueError("phase3_mirror_resource_definition_duplicate")
        if len({item.tag_id for item in self.status_tag_definitions}) != len(self.status_tag_definitions):
            raise ValueError("phase3_mirror_status_tag_duplicate")
        if len({item.stat_id for item in self.stat_baselines}) != len(self.stat_baselines):
            raise ValueError("phase3_mirror_stat_baseline_duplicate")
        return self


@dataclass(frozen=True)
class Phase3MirrorSource:
    """Rebuilds one actor's configured façade from committed backend events only."""

    configuration: Phase3MirrorActorConfiguration
    store: GameplayEventStore
    _lifecycle_projector: StateGroupLifecycleProjector
    _resource_body_projector: ResourceBodyRuntimeProjector
    _status_tag_projector: StatusTagProjector
    _composer: Phase3StateComposer
    _view_projector: StateGroupViewProjector

    @classmethod
    def create(
        cls,
        *,
        configuration: Phase3MirrorActorConfiguration,
        store: GameplayEventStore,
    ) -> "Phase3MirrorSource":
        state_groups = StateGroupRegistry()
        for definition in configuration.state_group_definitions:
            state_groups.register(definition)
        resource_definitions = ResourceDefinitionRegistry()
        for definition in configuration.resource_definitions:
            resource_definitions.register(definition)
        tag_registry = StatusTagRegistry()
        for definition in configuration.status_tag_definitions:
            tag_registry.register(definition)
        return cls(
            configuration=configuration,
            store=store,
            _lifecycle_projector=StateGroupLifecycleProjector(state_groups),
            _resource_body_projector=ResourceBodyRuntimeProjector(
                resource_definitions=resource_definitions if configuration.resource_definitions else None,
            ),
            _status_tag_projector=StatusTagProjector(tag_registry),
            _composer=Phase3StateComposer(facade_builder=CharacterGameRuntimeStateBuilder(state_groups)),
            _view_projector=StateGroupViewProjector(list(configuration.godot_view_policies)),
        )

    def godot_view(self):
        actor_ref = self.configuration.actor_ref
        # Each configured source rebuilds only its own committed actor stream.
        events = tuple(
            event
            for event in self.store.read_events()
            if str(event.payload.get("actor_ref", "")) == actor_ref
        )
        lifecycle = self._lifecycle_projector.rebuild(actor_ref, events)
        unsupported_enabled = set(lifecycle.enabled_group_ids).difference(_SUPPORTED_GROUP_IDS)
        if unsupported_enabled:
            raise Phase3MirrorSourceError("phase3_mirror_enabled_group_unsupported")
        resources = self._resource_body_projector.rebuild_resources(actor_ref, events)
        body = self._resource_body_projector.rebuild_body(actor_ref, events)
        tags = self._status_tag_projector.rebuild(actor_ref, events)
        modifiers = active_status_tag_modifiers(tags, self._status_tag_projector.registry)
        resolver = EffectiveStatResolver()
        effective_stats = {
            baseline.stat_id: resolver.resolve(
                baseline,
                [item for item in modifiers if item.stat_id == baseline.stat_id],
            )
            for baseline in self.configuration.stat_baselines
        }
        state = self._composer.compose(
            lifecycle=lifecycle,
            resources=resources,
            body=body,
            tags=tags,
            effective_stats=effective_stats,
            registry_revision=self.configuration.registry_revision,
            world_config_revision=self.configuration.world_config_revision,
            active_patch_set_revision=self.configuration.active_patch_set_revision,
        )
        return self._view_projector.godot_view(
            state,
            allowed_group_ids=self.configuration.godot_allowed_group_ids
            or tuple(item.group_id for item in self.configuration.state_group_definitions),
        )


def install_phase3_mirror_sources(
    *,
    configurations: Iterable[Phase3MirrorActorConfiguration],
    store: GameplayEventStore,
    publisher: GameplayGodotProjectionPublisher,
) -> tuple[str, ...]:
    """Install only explicit backend configurations; no scene or client data participates."""

    installed: list[str] = []
    for configuration in configurations:
        if configuration.actor_ref in installed:
            raise Phase3MirrorSourceError("phase3_mirror_actor_duplicate")
        source = Phase3MirrorSource.create(configuration=configuration, store=store)
        publisher.register_actor_source(actor_ref=configuration.actor_ref, source=source.godot_view)
        installed.append(configuration.actor_ref)
    return tuple(installed)


__all__ = [
    "Phase3MirrorActorConfiguration",
    "Phase3MirrorSource",
    "Phase3MirrorSourceError",
    "install_phase3_mirror_sources",
]
