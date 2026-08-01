"""Read-only gameplay state-group composition for the first runtime façade slice."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from pydantic import ConfigDict, Field

from app.gameplay.models import StrictGameplayModel


class StateGroupRegistryError(ValueError):
    """Raised when a requested state-group composition is not valid."""


class StateGroupDefinition(StrictGameplayModel):
    """Immutable metadata for one independently owned gameplay projection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    group_id: str = Field(min_length=1)
    definition_version: str = Field(min_length=1)
    projection_schema_version: int = Field(ge=1)
    dependencies: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()


@dataclass(frozen=True)
class StateGroupProjectionEnvelope:
    group_id: str
    definition_version: str
    projection_schema_version: int
    projection_revision: str
    source_revision_vector: Mapping[str, int]
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class CharacterGameRuntimeState:
    """A composed read model; it is deliberately not an event-store write API."""

    actor_ref: str
    facade_schema_version: int
    facade_revision: str
    source_revision_vector: Mapping[str, int]
    registry_revision: str
    world_config_revision: str
    active_patch_set_revision: str
    enabled_state_groups: tuple[str, ...]
    groups: Mapping[str, StateGroupProjectionEnvelope]
    snapshot_checksum: str


class StateGroupRegistry:
    """Minimal immutable-definition registry with deterministic dependency resolution."""

    def __init__(self) -> None:
        self._definitions: dict[str, StateGroupDefinition] = {}

    def register(self, definition: StateGroupDefinition) -> None:
        if definition.group_id in self._definitions:
            raise StateGroupRegistryError("state_group_definition_duplicate")
        self._definitions[definition.group_id] = definition

    def resolve(self, group_id: str) -> StateGroupDefinition:
        try:
            return self._definitions[group_id]
        except KeyError as exc:
            raise StateGroupRegistryError("state_group_definition_unknown") from exc

    def resolve_load_order(self, requested_group_ids: Iterable[str]) -> list[str]:
        ordered: list[str] = []
        permanent: set[str] = set()
        visiting: set[str] = set()

        def visit(group_id: str) -> None:
            if group_id in permanent:
                return
            if group_id in visiting:
                raise StateGroupRegistryError("state_group_dependency_cycle")
            definition = self._definitions.get(group_id)
            if definition is None:
                raise StateGroupRegistryError("state_group_dependency_missing")
            visiting.add(group_id)
            for dependency_id in sorted(definition.dependencies):
                visit(dependency_id)
            visiting.remove(group_id)
            permanent.add(group_id)
            ordered.append(group_id)

        for group_id in sorted(set(requested_group_ids)):
            visit(group_id)

        active_group_ids = set(ordered)
        for group_id in ordered:
            conflicts = active_group_ids.intersection(self._definitions[group_id].conflicts)
            if conflicts:
                raise StateGroupRegistryError("state_group_conflict")
        return ordered


class CharacterGameRuntimeStateBuilder:
    """Build deterministic read-only snapshots from independently owned projections."""

    def __init__(self, registry: StateGroupRegistry) -> None:
        self._registry = registry

    def build(
        self,
        *,
        actor_ref: str,
        enabled_group_ids: Iterable[str],
        group_payloads: Mapping[str, Mapping[str, Any]],
        source_revision_vector: Mapping[str, int],
        registry_revision: str,
        world_config_revision: str,
        active_patch_set_revision: str,
    ) -> CharacterGameRuntimeState:
        if not actor_ref:
            raise ValueError("actor_ref is required")
        enabled_state_groups = tuple(self._registry.resolve_load_order(enabled_group_ids))
        normalized_revisions = _freeze_mapping({key: int(value) for key, value in sorted(source_revision_vector.items())})
        envelopes: dict[str, StateGroupProjectionEnvelope] = {}
        for group_id in enabled_state_groups:
            definition = self._registry.resolve(group_id)
            payload = _freeze_mapping(deepcopy(dict(group_payloads.get(group_id, {}))))
            projection_revision = _digest(
                {
                    "group_id": group_id,
                    "definition_version": definition.definition_version,
                    "source_revision_vector": dict(normalized_revisions),
                    "payload": _thaw(payload),
                }
            )
            envelopes[group_id] = StateGroupProjectionEnvelope(
                group_id=group_id,
                definition_version=definition.definition_version,
                projection_schema_version=definition.projection_schema_version,
                projection_revision=f"projection:{projection_revision}",
                source_revision_vector=normalized_revisions,
                payload=payload,
            )

        snapshot_body = {
            "actor_ref": actor_ref,
            "facade_schema_version": 1,
            "source_revision_vector": dict(normalized_revisions),
            "registry_revision": registry_revision,
            "world_config_revision": world_config_revision,
            "active_patch_set_revision": active_patch_set_revision,
            "enabled_state_groups": enabled_state_groups,
            "groups": {
                group_id: {
                    "definition_version": envelope.definition_version,
                    "projection_schema_version": envelope.projection_schema_version,
                    "projection_revision": envelope.projection_revision,
                    "payload": _thaw(envelope.payload),
                }
                for group_id, envelope in envelopes.items()
            },
        }
        checksum = _digest(snapshot_body)
        return CharacterGameRuntimeState(
            actor_ref=actor_ref,
            facade_schema_version=1,
            facade_revision=f"facade:{checksum[:16]}",
            source_revision_vector=normalized_revisions,
            registry_revision=registry_revision,
            world_config_revision=world_config_revision,
            active_patch_set_revision=active_patch_set_revision,
            enabled_state_groups=enabled_state_groups,
            groups=MappingProxyType(envelopes),
            snapshot_checksum=f"sha256:{checksum}",
        )


def _digest(value: Mapping[str, Any]) -> str:
    return sha256(json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType({key: _freeze(value[key]) for key in sorted(value)})


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value
