"""Consumer-filtered, immutable views over CharacterGameRuntimeState."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Literal, Mapping

from pydantic import ConfigDict, Field

from app.gameplay.models import StrictGameplayModel
from app.gameplay.runtime_state import CharacterGameRuntimeState, StateGroupProjectionEnvelope


ConsumerKind = Literal["authority", "godot", "mind_frame", "debug"]


class StateGroupViewError(ValueError):
    """Raised when a consumer view cannot be safely projected."""


class StateGroupConsumerViewPolicy(StrictGameplayModel):
    """Field allowlists can only remove data from authoritative group payloads."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    group_id: str = Field(min_length=1)
    godot_allowed_fields: tuple[str, ...] = ()
    mind_allowed_fields: tuple[str, ...] = ()
    debug_allowed_fields: tuple[str, ...] = ()
    debug_principal_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class StateGroupRuntimeViewEnvelope:
    group_id: str
    definition_version: str
    projection_schema_version: int
    projection_revision: str
    source_revision_vector: Mapping[str, int]
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class CharacterGameRuntimeStateView:
    actor_ref: str
    consumer: ConsumerKind
    source_facade_revision: str
    source_revision_vector: Mapping[str, int]
    groups: Mapping[str, StateGroupRuntimeViewEnvelope]
    view_checksum: str


class StateGroupViewProjector:
    """Creates presentation/read views without changing state, lifecycle, or authority."""

    def __init__(self, policies: list[StateGroupConsumerViewPolicy]) -> None:
        self._policies = {policy.group_id: policy for policy in policies}
        if len(self._policies) != len(policies):
            raise StateGroupViewError("view_policy_duplicate_group")

    def authority_view(
        self,
        state: CharacterGameRuntimeState,
        *,
        allowed_group_ids: tuple[str, ...],
    ) -> CharacterGameRuntimeStateView:
        return self._project(state, consumer="authority", allowed_group_ids=allowed_group_ids)

    def godot_view(
        self,
        state: CharacterGameRuntimeState,
        *,
        allowed_group_ids: tuple[str, ...],
    ) -> CharacterGameRuntimeStateView:
        return self._project(state, consumer="godot", allowed_group_ids=allowed_group_ids)

    def mind_frame_view(
        self,
        state: CharacterGameRuntimeState,
        *,
        allowed_group_ids: tuple[str, ...],
    ) -> CharacterGameRuntimeStateView:
        return self._project(state, consumer="mind_frame", allowed_group_ids=allowed_group_ids)

    def debug_view(
        self,
        state: CharacterGameRuntimeState,
        *,
        allowed_group_ids: tuple[str, ...],
        principal_ref: str,
    ) -> CharacterGameRuntimeStateView:
        return self._project(
            state,
            consumer="debug",
            allowed_group_ids=allowed_group_ids,
            principal_ref=principal_ref,
        )

    def _project(
        self,
        state: CharacterGameRuntimeState,
        *,
        consumer: ConsumerKind,
        allowed_group_ids: tuple[str, ...],
        principal_ref: str | None = None,
    ) -> CharacterGameRuntimeStateView:
        allowed = set(allowed_group_ids)
        groups: dict[str, StateGroupRuntimeViewEnvelope] = {}
        for group_id in state.enabled_state_groups:
            if group_id not in allowed:
                continue
            envelope = state.groups[group_id]
            if consumer == "authority":
                payload = _freeze_mapping(_thaw(envelope.payload))
            else:
                policy = self._policies.get(group_id)
                if policy is None:
                    raise StateGroupViewError("view_policy_missing")
                allowed_fields = self._allowed_fields(policy, consumer, principal_ref)
                if allowed_fields is None:
                    continue
                payload = _freeze_mapping(
                    {field: _thaw(envelope.payload[field]) for field in allowed_fields if field in envelope.payload}
                )
            groups[group_id] = StateGroupRuntimeViewEnvelope(
                group_id=envelope.group_id,
                definition_version=envelope.definition_version,
                projection_schema_version=envelope.projection_schema_version,
                projection_revision=envelope.projection_revision,
                source_revision_vector=_freeze_mapping(_thaw(envelope.source_revision_vector)),
                payload=payload,
            )
        frozen_groups = MappingProxyType(groups)
        checksum = _digest(
            {
                "actor_ref": state.actor_ref,
                "consumer": consumer,
                "source_facade_revision": state.facade_revision,
                "groups": {
                    group_id: {
                        "projection_revision": envelope.projection_revision,
                        "payload": _thaw(envelope.payload),
                    }
                    for group_id, envelope in frozen_groups.items()
                },
            }
        )
        return CharacterGameRuntimeStateView(
            actor_ref=state.actor_ref,
            consumer=consumer,
            source_facade_revision=state.facade_revision,
            source_revision_vector=_freeze_mapping(_thaw(state.source_revision_vector)),
            groups=frozen_groups,
            view_checksum=f"sha256:{checksum}",
        )

    @staticmethod
    def _allowed_fields(
        policy: StateGroupConsumerViewPolicy,
        consumer: ConsumerKind,
        principal_ref: str | None,
    ) -> tuple[str, ...] | None:
        if consumer == "godot":
            return policy.godot_allowed_fields or None
        if consumer == "mind_frame":
            return policy.mind_allowed_fields or None
        if consumer == "debug":
            if principal_ref not in policy.debug_principal_refs:
                return None
            return policy.debug_allowed_fields or None
        raise StateGroupViewError("consumer_kind_invalid")


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


__all__ = [
    "CharacterGameRuntimeStateView",
    "StateGroupConsumerViewPolicy",
    "StateGroupRuntimeViewEnvelope",
    "StateGroupViewError",
    "StateGroupViewProjector",
]
