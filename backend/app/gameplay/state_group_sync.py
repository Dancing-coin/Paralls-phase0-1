"""Immutable backend snapshot/delta contracts for gameplay state-group reads."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Mapping

from app.gameplay.runtime_state import CharacterGameRuntimeState, StateGroupProjectionEnvelope


class StateGroupSyncError(ValueError):
    """Raised when a snapshot or delta cannot be safely synchronized."""


@dataclass(frozen=True)
class CharacterGameRuntimeSnapshot:
    actor_ref: str
    facade_revision: str
    source_revision_vector: Mapping[str, int]
    schema_capabilities: tuple[str, ...]
    enabled_state_groups: tuple[str, ...]
    groups: Mapping[str, StateGroupProjectionEnvelope]
    snapshot_checksum: str


@dataclass(frozen=True)
class CharacterGameRuntimeDelta:
    actor_ref: str
    base_facade_revision: str
    target_facade_revision: str
    target_source_revision_vector: Mapping[str, int]
    target_schema_capabilities: tuple[str, ...]
    target_enabled_state_groups: tuple[str, ...]
    changed_group_envelopes: Mapping[str, StateGroupProjectionEnvelope]
    removed_group_ids: tuple[str, ...]
    confirmed_prediction_ids: tuple[str, ...]
    rejected_predictions: tuple[str, ...]
    target_snapshot_checksum: str


class StateGroupSyncService:
    """Builds and applies backend read-model deltas; it owns no transport or writes."""

    def snapshot(
        self,
        state: CharacterGameRuntimeState,
        *,
        schema_capabilities: tuple[str, ...],
    ) -> CharacterGameRuntimeSnapshot:
        capabilities = tuple(sorted(set(schema_capabilities)))
        snapshot = CharacterGameRuntimeSnapshot(
            actor_ref=state.actor_ref,
            facade_revision=state.facade_revision,
            source_revision_vector=_freeze_revisions(state.source_revision_vector),
            schema_capabilities=capabilities,
            enabled_state_groups=tuple(state.enabled_state_groups),
            groups=MappingProxyType(dict(state.groups)),
            snapshot_checksum="",
        )
        return _with_checksum(snapshot)

    def delta(
        self,
        base: CharacterGameRuntimeSnapshot,
        target: CharacterGameRuntimeSnapshot,
        *,
        confirmed_prediction_ids: tuple[str, ...] = (),
        rejected_predictions: tuple[str, ...] = (),
    ) -> CharacterGameRuntimeDelta:
        self._validate_snapshot(base)
        self._validate_snapshot(target)
        if base.actor_ref != target.actor_ref:
            raise StateGroupSyncError("actor_mismatch")
        changed = {
            group_id: envelope
            for group_id, envelope in target.groups.items()
            if group_id not in base.groups or base.groups[group_id].projection_revision != envelope.projection_revision
        }
        return CharacterGameRuntimeDelta(
            actor_ref=target.actor_ref,
            base_facade_revision=base.facade_revision,
            target_facade_revision=target.facade_revision,
            target_source_revision_vector=_freeze_revisions(target.source_revision_vector),
            target_schema_capabilities=target.schema_capabilities,
            target_enabled_state_groups=target.enabled_state_groups,
            changed_group_envelopes=MappingProxyType(dict(changed)),
            removed_group_ids=tuple(sorted(set(base.groups).difference(target.groups))),
            confirmed_prediction_ids=tuple(confirmed_prediction_ids),
            rejected_predictions=tuple(rejected_predictions),
            target_snapshot_checksum=target.snapshot_checksum,
        )

    def apply_delta(
        self,
        base: CharacterGameRuntimeSnapshot,
        delta: CharacterGameRuntimeDelta,
        *,
        supported_schema_capabilities: tuple[str, ...],
    ) -> CharacterGameRuntimeSnapshot:
        self._validate_snapshot(base)
        if base.actor_ref != delta.actor_ref:
            raise StateGroupSyncError("actor_mismatch")
        if base.facade_revision != delta.base_facade_revision:
            raise StateGroupSyncError("facade_revision_conflict")
        if not set(delta.target_schema_capabilities).issubset(supported_schema_capabilities):
            raise StateGroupSyncError("projection_schema_unsupported")
        if set(delta.changed_group_envelopes).intersection(delta.removed_group_ids):
            raise StateGroupSyncError("delta_group_overlap")
        groups = dict(base.groups)
        for group_id in delta.removed_group_ids:
            groups.pop(group_id, None)
        groups.update(delta.changed_group_envelopes)
        if set(delta.target_enabled_state_groups) != set(groups):
            raise StateGroupSyncError("delta_enabled_groups_invalid")
        candidate = CharacterGameRuntimeSnapshot(
            actor_ref=delta.actor_ref,
            facade_revision=delta.target_facade_revision,
            source_revision_vector=_freeze_revisions(delta.target_source_revision_vector),
            schema_capabilities=tuple(delta.target_schema_capabilities),
            enabled_state_groups=tuple(delta.target_enabled_state_groups),
            groups=MappingProxyType(groups),
            snapshot_checksum="",
        )
        rebuilt = _with_checksum(candidate)
        if rebuilt.snapshot_checksum != delta.target_snapshot_checksum:
            raise StateGroupSyncError("snapshot_checksum_invalid")
        return rebuilt

    @staticmethod
    def _validate_snapshot(snapshot: CharacterGameRuntimeSnapshot) -> None:
        if _snapshot_checksum(snapshot) != snapshot.snapshot_checksum:
            raise StateGroupSyncError("snapshot_checksum_invalid")
        if set(snapshot.enabled_state_groups) != set(snapshot.groups):
            raise StateGroupSyncError("snapshot_enabled_groups_invalid")


def _with_checksum(snapshot: CharacterGameRuntimeSnapshot) -> CharacterGameRuntimeSnapshot:
    return CharacterGameRuntimeSnapshot(
        actor_ref=snapshot.actor_ref,
        facade_revision=snapshot.facade_revision,
        source_revision_vector=snapshot.source_revision_vector,
        schema_capabilities=snapshot.schema_capabilities,
        enabled_state_groups=snapshot.enabled_state_groups,
        groups=snapshot.groups,
        snapshot_checksum=_snapshot_checksum(snapshot),
    )


def _snapshot_checksum(snapshot: CharacterGameRuntimeSnapshot) -> str:
    return "sha256:" + sha256(
        json.dumps(
            {
                "actor_ref": snapshot.actor_ref,
                "facade_revision": snapshot.facade_revision,
                "source_revision_vector": dict(snapshot.source_revision_vector),
                "schema_capabilities": snapshot.schema_capabilities,
                "enabled_state_groups": snapshot.enabled_state_groups,
                "groups": {
                    group_id: {
                        "definition_version": envelope.definition_version,
                        "projection_schema_version": envelope.projection_schema_version,
                        "projection_revision": envelope.projection_revision,
                        "source_revision_vector": dict(envelope.source_revision_vector),
                        "payload": _thaw(envelope.payload),
                    }
                    for group_id, envelope in snapshot.groups.items()
                },
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _freeze_revisions(revisions: Mapping[str, int]) -> Mapping[str, int]:
    return MappingProxyType({key: int(revisions[key]) for key in sorted(revisions)})


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


__all__ = [
    "CharacterGameRuntimeDelta",
    "CharacterGameRuntimeSnapshot",
    "StateGroupSyncError",
    "StateGroupSyncService",
]
