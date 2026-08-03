"""Read-only gameplay state-group composition for the first runtime façade slice."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
import re
from types import MappingProxyType
from typing import Any, Iterable, Literal, Mapping

from pydantic import ConfigDict, Field

from app.gameplay.models import GameplayEvent, StrictGameplayModel


class StateGroupRegistryError(ValueError):
    """Raised when a requested state-group composition is not valid."""


class StateGroupLifecycleError(ValueError):
    """Raised when committed lifecycle events cannot form a valid read model."""


_LIFECYCLE_EVENT_TO_STATE = {
    "gameplay.state_group.materialized": "materialized",
    "gameplay.state_group.enabled": "enabled",
    "gameplay.state_group.dormant": "dormant",
    "gameplay.state_group.disabled": "disabled",
}
StateGroupLifecycleState = Literal["materialized", "enabled", "dormant", "disabled"]


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


@dataclass(frozen=True)
class StateGroupLifecycleRecord:
    group_id: str
    definition_version: str
    source_patch_revision: str
    lifecycle_state: StateGroupLifecycleState
    materialized_event_id: str
    lifecycle_event_id: str


@dataclass(frozen=True)
class StateGroupLifecycleProjection:
    """Authority-event-derived state-group lifecycle read model, not a command API."""

    actor_ref: str
    records: Mapping[str, StateGroupLifecycleRecord]
    enabled_group_ids: tuple[str, ...]
    source_revision_vector: Mapping[str, int]
    applied_event_ids: tuple[str, ...]
    lifecycle_revision: str


class StateGroupRegistry:
    """Immutable state-group definitions with explicit historical-version lookup.

    A group may have more than one registered definition because a committed
    lifecycle event must keep resolving the definition it originally named.
    Callers that compose more than one version must supply the selected version
    rather than silently receiving whichever definition was registered last.
    """

    def __init__(self) -> None:
        self._definitions: dict[str, dict[str, StateGroupDefinition]] = {}

    def register(self, definition: StateGroupDefinition) -> None:
        versions = self._definitions.setdefault(definition.group_id, {})
        if definition.definition_version in versions:
            raise StateGroupRegistryError("state_group_definition_duplicate")
        versions[definition.definition_version] = definition

    def resolve(self, group_id: str, definition_version: str | None = None) -> StateGroupDefinition:
        try:
            versions = self._definitions[group_id]
        except KeyError as exc:
            raise StateGroupRegistryError("state_group_definition_unknown") from exc
        if definition_version is None:
            if len(versions) != 1:
                raise StateGroupRegistryError("state_group_definition_version_required")
            return next(iter(versions.values()))
        try:
            return versions[definition_version]
        except KeyError as exc:
            raise StateGroupRegistryError("state_group_definition_version_unknown") from exc

    def list_group_ids(self) -> tuple[str, ...]:
        """Expose stable registry membership for backend policy compilation only."""
        return tuple(sorted(self._definitions))

    def resolve_load_order(
        self,
        requested_group_ids: Iterable[str],
        *,
        definition_versions: Mapping[str, str] | None = None,
    ) -> list[str]:
        """Resolve one explicit definition graph into stable dependency order.

        ``definition_versions`` pins lifecycle/assembly callers to historical
        definitions.  The compact single-version call remains valid only while
        a requested group (and every dependency) has exactly one definition.
        """

        ordered: list[str] = []
        permanent: set[str] = set()
        visiting: set[str] = set()

        def resolve_for_composition(group_id: str) -> StateGroupDefinition:
            version = definition_versions.get(group_id) if definition_versions is not None else None
            return self.resolve(group_id, version)

        def visit(group_id: str) -> None:
            if group_id in permanent:
                return
            if group_id in visiting:
                raise StateGroupRegistryError("state_group_dependency_cycle")
            try:
                definition = resolve_for_composition(group_id)
            except StateGroupRegistryError as exc:
                if str(exc) in {"state_group_definition_unknown", "state_group_definition_version_unknown"}:
                    raise StateGroupRegistryError("state_group_dependency_missing") from exc
                raise
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
            conflicts = active_group_ids.intersection(resolve_for_composition(group_id).conflicts)
            if conflicts:
                raise StateGroupRegistryError("state_group_conflict")
        return ordered


class StateGroupLifecycleProjector:
    """Rebuild enabled-group membership solely from committed Gameplay events."""

    def __init__(self, registry: StateGroupRegistry) -> None:
        self._registry = registry

    def rebuild(
        self,
        actor_ref: str,
        events: Iterable[GameplayEvent],
        *,
        checkpoint: StateGroupLifecycleProjection | None = None,
    ) -> StateGroupLifecycleProjection:
        if not actor_ref:
            raise StateGroupLifecycleError("actor_ref_required")
        if checkpoint is not None and checkpoint.actor_ref != actor_ref:
            raise StateGroupLifecycleError("actor_mismatch")
        records: dict[str, StateGroupLifecycleRecord] = dict(checkpoint.records) if checkpoint is not None else {}
        source_revision_vector: dict[str, int] = dict(checkpoint.source_revision_vector) if checkpoint is not None else {}
        applied_event_ids: list[str] = list(checkpoint.applied_event_ids) if checkpoint is not None else []
        seen_event_ids: set[str] = set(applied_event_ids)
        ordered_events = sorted(events, key=lambda event: (event.global_sequence, event.event_id))
        for event in ordered_events:
            if event.event_id in seen_event_ids:
                continue
            if event.event_type == "gameplay.state_group.rebound":
                self._apply_rebound(actor_ref, records, event)
                source_revision_vector[event.stream_id] = max(
                    source_revision_vector.get(event.stream_id, 0), event.stream_revision
                )
                seen_event_ids.add(event.event_id)
                applied_event_ids.append(event.event_id)
                continue
            if event.event_type == "gameplay.state_group.migrated":
                self._apply_migrated(actor_ref, records, event)
                source_revision_vector[event.stream_id] = max(
                    source_revision_vector.get(event.stream_id, 0), event.stream_revision
                )
                seen_event_ids.add(event.event_id)
                applied_event_ids.append(event.event_id)
                continue
            target_state = _LIFECYCLE_EVENT_TO_STATE.get(event.event_type)
            if target_state is None:
                continue
            seen_event_ids.add(event.event_id)
            payload = event.payload
            if str(payload.get("actor_ref", "")) != actor_ref:
                raise StateGroupLifecycleError("actor_mismatch")
            group_id = str(payload.get("group_id", ""))
            definition_version = str(payload.get("definition_version", ""))
            source_patch_revision = str(payload.get("source_patch_revision", ""))
            if not group_id or not definition_version or not source_patch_revision:
                raise StateGroupLifecycleError("lifecycle_event_payload_invalid")
            self._validate_definition(group_id, definition_version)
            current = records.get(group_id)
            if target_state == "materialized":
                if current is not None and current.lifecycle_state != "disabled":
                    raise StateGroupLifecycleError("duplicate_materialization")
                records[group_id] = StateGroupLifecycleRecord(
                    group_id=group_id,
                    definition_version=definition_version,
                    source_patch_revision=source_patch_revision,
                    lifecycle_state="materialized",
                    materialized_event_id=event.event_id,
                    lifecycle_event_id=event.event_id,
                )
            else:
                if current is None:
                    operation = {"enabled": "enable", "dormant": "dormancy", "disabled": "disable"}[target_state]
                    raise StateGroupLifecycleError(f"{operation}_before_materialization")
                self._validate_transition(current, target_state, definition_version, source_patch_revision)
                records[group_id] = StateGroupLifecycleRecord(
                    group_id=current.group_id,
                    definition_version=current.definition_version,
                    source_patch_revision=current.source_patch_revision,
                    lifecycle_state=target_state,
                    materialized_event_id=current.materialized_event_id,
                    lifecycle_event_id=event.event_id,
                )
            source_revision_vector[event.stream_id] = max(
                source_revision_vector.get(event.stream_id, 0), event.stream_revision
            )
            applied_event_ids.append(event.event_id)

        enabled_records = {
            record.group_id: record.definition_version
            for record in records.values()
            if record.lifecycle_state == "enabled"
        }
        enabled_group_ids = tuple(
            self._registry.resolve_load_order(
                enabled_records,
                definition_versions=enabled_records,
            )
        )
        normalized_revisions = _freeze_mapping(source_revision_vector)
        frozen_records = MappingProxyType(dict(sorted(records.items())))
        lifecycle_revision = _digest(
            {
                "actor_ref": actor_ref,
                "records": {
                    group_id: {
                        "definition_version": record.definition_version,
                        "source_patch_revision": record.source_patch_revision,
                        "lifecycle_state": record.lifecycle_state,
                        "lifecycle_event_id": record.lifecycle_event_id,
                    }
                    for group_id, record in frozen_records.items()
                },
                "source_revision_vector": dict(normalized_revisions),
                "applied_event_ids": applied_event_ids,
            }
        )
        return StateGroupLifecycleProjection(
            actor_ref=actor_ref,
            records=frozen_records,
            enabled_group_ids=enabled_group_ids,
            source_revision_vector=normalized_revisions,
            applied_event_ids=tuple(applied_event_ids),
            lifecycle_revision=f"lifecycle:{lifecycle_revision[:16]}",
        )

    def _validate_definition(self, group_id: str, definition_version: str) -> None:
        try:
            self._registry.resolve(group_id, definition_version)
        except StateGroupRegistryError:
            raise StateGroupLifecycleError("definition_version_mismatch")

    @staticmethod
    def _apply_rebound(
        actor_ref: str,
        records: dict[str, StateGroupLifecycleRecord],
        event: GameplayEvent,
    ) -> None:
        payload = event.payload
        if str(payload.get("actor_ref", "")) != actor_ref:
            raise StateGroupLifecycleError("actor_mismatch")
        group_id = str(payload.get("group_id", ""))
        definition_version = str(payload.get("definition_version", ""))
        previous_source = str(payload.get("previous_source_patch_revision", ""))
        next_source = str(payload.get("next_source_patch_revision", ""))
        migration_kind = str(payload.get("migration_kind", ""))
        migration_digest = str(payload.get("migration_digest", ""))
        if not all((group_id, definition_version, previous_source, next_source, migration_digest)):
            raise StateGroupLifecycleError("rebind_event_payload_invalid")
        if migration_kind != "identity_rebind" or not _is_sha256_digest(migration_digest):
            raise StateGroupLifecycleError("rebind_migration_invalid")
        current = records.get(group_id)
        if current is None or current.lifecycle_state == "disabled":
            raise StateGroupLifecycleError("rebind_before_active_materialization")
        if current.definition_version != definition_version:
            raise StateGroupLifecycleError("definition_version_mismatch")
        if current.source_patch_revision != previous_source or previous_source == next_source:
            raise StateGroupLifecycleError("source_patch_revision_mismatch")
        records[group_id] = StateGroupLifecycleRecord(
            group_id=current.group_id,
            definition_version=current.definition_version,
            source_patch_revision=next_source,
            lifecycle_state=current.lifecycle_state,
            materialized_event_id=current.materialized_event_id,
            lifecycle_event_id=event.event_id,
        )

    @staticmethod
    def _validate_transition(
        current: StateGroupLifecycleRecord,
        target_state: str,
        definition_version: str,
        source_patch_revision: str,
    ) -> None:
        if current.definition_version != definition_version:
            raise StateGroupLifecycleError("definition_version_mismatch")
        if current.source_patch_revision != source_patch_revision:
            raise StateGroupLifecycleError("source_patch_revision_mismatch")
        if target_state == "enabled" and current.lifecycle_state not in {"materialized", "dormant"}:
            raise StateGroupLifecycleError("enable_transition_invalid")
        if target_state == "dormant" and current.lifecycle_state != "enabled":
            raise StateGroupLifecycleError("dormant_transition_invalid")
        if target_state == "disabled" and current.lifecycle_state not in {"materialized", "enabled", "dormant"}:
            raise StateGroupLifecycleError("disable_transition_invalid")

    def _apply_migrated(
        self,
        actor_ref: str,
        records: dict[str, StateGroupLifecycleRecord],
        event: GameplayEvent,
    ) -> None:
        """Advance lifecycle metadata only after a domain-owned migration fact.

        The resource/body payload remains outside this projector.  Requiring
        the domain event identity merely preserves the cross-stream lineage
        that the Patch coordinator committed atomically.
        """

        payload = event.payload
        if str(payload.get("actor_ref", "")) != actor_ref:
            raise StateGroupLifecycleError("actor_mismatch")
        group_id = str(payload.get("group_id", ""))
        from_definition_version = str(payload.get("from_definition_version", ""))
        to_definition_version = str(payload.get("to_definition_version", ""))
        previous_source = str(payload.get("previous_source_patch_revision", ""))
        next_source = str(payload.get("next_source_patch_revision", ""))
        migration_kind = str(payload.get("migration_kind", ""))
        migration_digest = str(payload.get("migration_digest", ""))
        migrator_code_digest = str(payload.get("migrator_code_digest", ""))
        domain_event_id = str(payload.get("domain_event_id", ""))
        if not all(
            (
                group_id,
                from_definition_version,
                to_definition_version,
                previous_source,
                next_source,
                migration_kind,
                migration_digest,
                migrator_code_digest,
                domain_event_id,
            )
        ) or not _is_sha256_digest(migration_digest) or not _is_sha256_digest(migrator_code_digest):
            raise StateGroupLifecycleError("migration_event_payload_invalid")
        current = records.get(group_id)
        if current is None or current.lifecycle_state == "disabled":
            raise StateGroupLifecycleError("migration_before_active_materialization")
        if (
            current.definition_version != from_definition_version
            or current.source_patch_revision != previous_source
            or previous_source == next_source
        ):
            raise StateGroupLifecycleError("migration_source_mismatch")
        self._validate_definition(group_id, to_definition_version)
        records[group_id] = StateGroupLifecycleRecord(
            group_id=current.group_id,
            definition_version=to_definition_version,
            source_patch_revision=next_source,
            lifecycle_state=current.lifecycle_state,
            materialized_event_id=current.materialized_event_id,
            lifecycle_event_id=event.event_id,
        )


def _is_sha256_digest(value: str) -> bool:
    return re.fullmatch(r"sha256:[0-9a-f]{64}", value) is not None


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
        definition_versions: Mapping[str, str] | None = None,
    ) -> CharacterGameRuntimeState:
        if not actor_ref:
            raise ValueError("actor_ref is required")
        enabled_state_groups = tuple(
            self._registry.resolve_load_order(
                enabled_group_ids,
                definition_versions=definition_versions,
            )
        )
        normalized_revisions = _freeze_mapping({key: int(value) for key, value in sorted(source_revision_vector.items())})
        envelopes: dict[str, StateGroupProjectionEnvelope] = {}
        for group_id in enabled_state_groups:
            definition = self._registry.resolve(
                group_id,
                definition_versions.get(group_id) if definition_versions is not None else None,
            )
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

    def build_from_lifecycle(
        self,
        *,
        lifecycle: StateGroupLifecycleProjection,
        group_payloads: Mapping[str, Mapping[str, Any]],
        registry_revision: str,
        world_config_revision: str,
        active_patch_set_revision: str,
    ) -> CharacterGameRuntimeState:
        """Compose only event-enabled projections; lifecycle mutation stays with authority."""
        return self.build(
            actor_ref=lifecycle.actor_ref,
            enabled_group_ids=lifecycle.enabled_group_ids,
            group_payloads=group_payloads,
            source_revision_vector=lifecycle.source_revision_vector,
            registry_revision=registry_revision,
            world_config_revision=world_config_revision,
            active_patch_set_revision=active_patch_set_revision,
            definition_versions={
                group_id: lifecycle.records[group_id].definition_version
                for group_id in lifecycle.enabled_group_ids
                if group_id in lifecycle.records
            },
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
