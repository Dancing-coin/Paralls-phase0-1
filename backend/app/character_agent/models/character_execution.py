"""Canonical, authority-neutral L4 execution contract.

The character runtime may describe a semantic action and presentation-safe
realization hints, but it never sends body control or world mutation data as
part of this contract.  World/ESM authorities decide whether the semantic
request settles and Godot only realizes the accepted result locally.
"""

from __future__ import annotations

import re
from types import MappingProxyType
from typing import Literal, Mapping

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_serializer,
    field_validator,
    model_validator,
)


# These names are rejected recursively, including when an adapter accidentally
# nests a forbidden payload under an observation or realization hint.  Keeping
# the deny-list here makes the boundary explicit and gives callers a stable
# validation error instead of silently dropping unsafe fields.
_FORBIDDEN_EXECUTION_FIELDS = frozenset(
    {
        "body",
        "body_authority",
        "body_state",
        "bone_pose",
        "bone_poses",
        "damage",
        "global_position",
        "target_position",
        "move_local",
        "look_local",
        "facing",
        "gait",
        "stance",
        "action_frame",
        "impulse",
        "inventory",
        "linear_velocity",
        "local_position",
        "motor",
        "motor_command",
        "physics",
        "pose",
        "position",
        "raw_animation",
        "raw_pose",
        "rotation",
        "status",
        "transform",
        "translation",
        "velocity",
        "vla",
        "vla_candidate",
        "controller_source",
        "control_mode",
        "world_mutation",
        "world_state",
        "world_write",
        "world_effect",
        "authority_result",
        "settlement_result",
        "result",
        "animation",
        "animation_state",
        "clip",
    }
)


def _freeze_json(value: JsonValue) -> JsonValue:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _freeze_json(nested) for key, nested in value.items()}
        )  # type: ignore[return-value]
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(nested) for nested in value)  # type: ignore[return-value]
    return value


def _scan_forbidden(value: object, *, path: str = "") -> str | None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key)
            normalized_key = re.sub(r"(?<!^)([A-Z])", r"_\1", key_text)
            normalized_key = normalized_key.replace("-", "_").lower()
            if normalized_key in _FORBIDDEN_EXECUTION_FIELDS:
                return f"{path}.{key_text}" if path else key_text
            found = _scan_forbidden(nested, path=f"{path}.{key_text}" if path else key_text)
            if found is not None:
                return found
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            found = _scan_forbidden(nested, path=f"{path}[{index}]")
            if found is not None:
                return found
    return None


def _thaw_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _thaw_json(nested) for key, nested in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw_json(nested) for nested in value]
    return value


class CharacterExecutionContract(BaseModel):
    """The sole production-shaped output of character-agent L4."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_default=True,
        populate_by_name=True,
    )

    turn_id: str = Field(min_length=1)
    actor_ref: str = Field(
        min_length=1,
        validation_alias=AliasChoices("actor_ref", "actor_id"),
    )
    source_ref: str = Field(
        min_length=1,
        validation_alias=AliasChoices("source_ref", "source_event_ref"),
    )
    producer_ts: int = Field(ge=0)
    target_refs: tuple[str, ...] = Field(default_factory=tuple)
    # `target_ref` is retained as a convenience for single-target consumers;
    # `target_refs` remains the canonical serialized representation.
    target_ref: str | None = Field(default=None, min_length=1)
    semantic_intent_id: str = Field(
        min_length=1,
        validation_alias=AliasChoices(
            "semantic_intent_id", "semantic_intent", "intent_id"
        ),
    )
    semantic_action_id: str = Field(
        min_length=1,
        validation_alias=AliasChoices("semantic_action_id", "action_id", "action"),
    )
    source_id: str = Field(default="character_agent_l4", min_length=1)
    expected_target_revision_vector: Mapping[str, int] = Field(
        default_factory=dict,
        validation_alias=AliasChoices(
            "expected_target_revision_vector", "target_revision_vector", "target_revisions"
        ),
    )
    intent_tags: tuple[str, ...] = Field(default_factory=tuple)
    context_tags: tuple[str, ...] = Field(default_factory=tuple)
    claims: tuple[str, ...] = Field(default_factory=tuple)
    locomotion_relation: Literal[
        "coexist", "drive_locomotion", "replace_locomotion", "suspend"
    ] = "coexist"
    allowed_realization_hints: Mapping[str, JsonValue] = Field(
        default_factory=dict,
        validation_alias=AliasChoices(
            "allowed_realization_hints", "realization_hints"
        ),
    )
    expected_revision_vector: Mapping[str, int] = Field(
        validation_alias=AliasChoices(
            "expected_revision_vector", "expected_revisions"
        )
    )
    # The memory and snapshot pins are retained separately so an authority
    # adapter cannot mistake cognition revisions for world truth revisions.
    expected_memory_revision_vector: Mapping[str, int] = Field(default_factory=dict)
    expected_snapshot_revision: int = Field(default=0, ge=0)
    idempotency_key: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    privacy_scope: str = Field(min_length=1)
    authority_scope: str = Field(min_length=1)
    expected_observation: Mapping[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def reject_forbidden_payloads(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        forbidden = _scan_forbidden(value)
        if forbidden is not None:
            raise ValueError(f"forbidden execution field: {forbidden}")
        return value

    @field_validator("target_refs", mode="before")
    @classmethod
    def normalize_target_refs(cls, value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, str):
            return (value,)
        return tuple(str(ref) for ref in value)  # type: ignore[arg-type]

    @field_validator("target_refs", mode="after")
    @classmethod
    def validate_target_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not ref.strip() for ref in value):
            raise ValueError("target refs must be non-empty")
        if len(set(value)) != len(value):
            raise ValueError("target refs must be unique")
        return value

    @field_validator("allowed_realization_hints", "expected_observation", mode="after")
    @classmethod
    def freeze_json_maps(
        cls, value: Mapping[str, JsonValue]
    ) -> Mapping[str, JsonValue]:
        return MappingProxyType(
            {str(key): _freeze_json(nested) for key, nested in value.items()}
        )

    @field_validator("expected_revision_vector", mode="after")
    @classmethod
    def freeze_revision_maps(cls, value: Mapping[str, int]) -> Mapping[str, int]:
        if not value:
            raise ValueError("expected revision vector is required")
        if any(int(revision) < 0 for revision in value.values()):
            raise ValueError("execution revision vector entries must be non-negative")
        return MappingProxyType({str(key): int(revision) for key, revision in value.items()})

    @field_validator("expected_memory_revision_vector", mode="after")
    @classmethod
    def freeze_memory_revision_map(cls, value: Mapping[str, int]) -> Mapping[str, int]:
        if any(int(revision) < 0 for revision in value.values()):
            raise ValueError("execution memory revision vector entries must be non-negative")
        return MappingProxyType({str(key): int(revision) for key, revision in value.items()})

    @field_validator("expected_target_revision_vector", mode="after")
    @classmethod
    def freeze_target_revision_map(cls, value: Mapping[str, int]) -> Mapping[str, int]:
        if any(int(revision) < 0 for revision in value.values()):
            raise ValueError("execution target revision entries must be non-negative")
        return MappingProxyType({str(key): int(revision) for key, revision in value.items()})

    @field_serializer(
        "allowed_realization_hints",
        "expected_observation",
        "expected_revision_vector",
        "expected_memory_revision_vector",
        "expected_target_revision_vector",
        when_used="always",
    )
    def serialize_frozen_maps(self, value: object) -> object:
        return _thaw_json(value)

    @model_validator(mode="after")
    def validate_identity(self) -> "CharacterExecutionContract":
        if self.target_ref is not None and not self.target_refs:
            object.__setattr__(self, "target_refs", (self.target_ref,))
        elif self.target_ref is not None and self.target_ref not in self.target_refs:
            raise ValueError("target_ref must be included in target_refs")
        if self.target_ref is None and len(self.target_refs) == 1:
            object.__setattr__(self, "target_ref", self.target_refs[0])
        if self.semantic_intent_id == "" or self.semantic_action_id == "":
            raise ValueError("semantic intent and action are required")
        allowed_namespaces = {
            "goal", "intent", "evidence", "capability", "affordance", "constraint",
            "state", "status", "action", "phase", "occupy", "event", "authority",
            "presentation", "expression",
        }
        if any(
            len(str(tag).split(":", 1)) != 2
            or str(tag).split(":", 1)[0] not in allowed_namespaces
            or not str(tag).split(":", 1)[1]
            for tag in (*self.intent_tags, *self.context_tags)
        ):
            raise ValueError("execution tags must be namespaced")
        return self

    @property
    def actor_id(self) -> str:
        """Compatibility projection for local presentation consumers."""
        return self.actor_ref.removeprefix("character:")

    @property
    def semantic_intent(self) -> str:
        return self.semantic_intent_id

    @property
    def action_id(self) -> str:
        return self.semantic_action_id


__all__ = ["CharacterExecutionContract"]
