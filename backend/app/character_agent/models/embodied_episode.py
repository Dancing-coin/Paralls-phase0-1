"""Actor-private evidence for one advisory-nominated embodied attempt.

This module deliberately has no authority or presentation dependency.  It
records evidence already produced by those owners so the actor can evaluate
the attempt without promoting a provider claim into world truth.
"""

from __future__ import annotations

import re
from types import MappingProxyType
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_serializer, field_validator, model_validator


EpisodeFailureClass = Literal[
    "perception", "localization", "precondition", "unreachable", "contact",
    "wrong_target", "stale_scene", "timeout", "authority_rejected",
    "observation_mismatch", "strategy",
]
EmbodiedEpisodeOutcome = Literal["in_progress", "confirmed_success", "recovery_required"]

_FORBIDDEN_CANDIDATE_FIELDS = frozenset({
    "body", "body_authority", "body_state", "bone_pose", "bone_poses",
    "global_position", "local_position", "position", "transform", "translation",
    "rotation", "velocity", "linear_velocity", "impulse", "motor", "motor_command",
    "physics", "raw_pose", "raw_animation", "animation", "world_state",
    "world_write", "world_mutation", "world_effect", "authority_result",
    "settlement_result", "godot", "controller_source",
})


def _forbidden_path(value: object, *, path: str = "") -> str | None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key)
            normalized = re.sub(r"(?<!^)([A-Z])", r"_\1", key_text).replace("-", "_").lower()
            if normalized in _FORBIDDEN_CANDIDATE_FIELDS:
                return f"{path}.{key_text}" if path else key_text
            found = _forbidden_path(nested, path=f"{path}.{key_text}" if path else key_text)
            if found:
                return found
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            found = _forbidden_path(nested, path=f"{path}[{index}]")
            if found:
                return found
    return None


def forbidden_candidate_field(value: object) -> str | None:
    """Return a prohibited body/control/world field without mutating input."""
    return _forbidden_path(value)


def _freeze(value: JsonValue) -> JsonValue:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(nested) for key, nested in value.items()})  # type: ignore[return-value]
    if isinstance(value, list):
        return tuple(_freeze(nested) for nested in value)  # type: ignore[return-value]
    return value


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _thaw(nested) for key, nested in value.items()}
    if isinstance(value, tuple):
        return [_thaw(nested) for nested in value]
    return value


class CandidateActionObservation(BaseModel):
    """A reviewed semantic candidate, never an actuator or authority request."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)

    candidate_id: str = Field(min_length=1)
    target_ref: str = Field(min_length=1)
    semantic_action_id: str = Field(min_length=1)
    reviewed_target_ref: str = Field(min_length=1)
    reviewed_action_ref: str = Field(min_length=1)
    preconditions: tuple[str, ...] = ()
    expected_observation: Mapping[str, JsonValue] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    uncertainty: Mapping[str, JsonValue] = Field(default_factory=dict)
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    reobserve_required: bool = False
    source_kind: Literal["provider_advisory", "structured_percept", "model_inference"] = "provider_advisory"

    @model_validator(mode="before")
    @classmethod
    def reject_control_or_world_fields(cls, value: object) -> object:
        forbidden = _forbidden_path(value)
        if forbidden:
            raise ValueError(f"forbidden candidate field: {forbidden}")
        return value

    @field_validator("preconditions", "evidence_refs", mode="after")
    @classmethod
    def validate_refs(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() for value in values):
            raise ValueError("candidate references must be non-empty")
        return values

    @field_validator("expected_observation", "uncertainty", mode="after")
    @classmethod
    def freeze_maps(cls, value: Mapping[str, JsonValue]) -> Mapping[str, JsonValue]:
        return MappingProxyType({str(key): _freeze(nested) for key, nested in value.items()})

    @field_serializer("expected_observation", "uncertainty", when_used="always")
    def serialize_maps(self, value: object) -> object:
        return _thaw(value)

    @model_validator(mode="after")
    def validate_reviewed_identity(self) -> "CandidateActionObservation":
        if self.target_ref != self.reviewed_target_ref:
            raise ValueError("candidate target must match its reviewed target")
        return self


class EmbodiedEpisodeRecord(BaseModel):
    """Immutable actor-private join of candidate, authority, and observation evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)

    episode_ref: str = Field(min_length=1)
    turn_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    candidate: CandidateActionObservation
    pre_capture_ref: str = Field(min_length=1)
    post_capture_ref: str = ""
    authority_result_ref: str = ""
    authority_status: str = ""
    observed_state: str = ""
    outcome: EmbodiedEpisodeOutcome = "in_progress"
    failure_class: EpisodeFailureClass | None = None
    recovery_candidate: Mapping[str, JsonValue] = Field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()
    reobserve_required: bool = False

    @field_validator("recovery_candidate", mode="after")
    @classmethod
    def freeze_recovery_candidate(cls, value: Mapping[str, JsonValue]) -> Mapping[str, JsonValue]:
        return MappingProxyType({str(key): _freeze(nested) for key, nested in value.items()})

    @field_serializer("recovery_candidate", when_used="always")
    def serialize_recovery_candidate(self, value: object) -> object:
        return _thaw(value)

    @model_validator(mode="after")
    def validate_outcome_evidence(self) -> "EmbodiedEpisodeRecord":
        if self.outcome == "confirmed_success":
            if not self.authority_result_ref or not self.post_capture_ref:
                raise ValueError("confirmed episode success requires authority and post-capture evidence")
            if self.failure_class is not None:
                raise ValueError("confirmed episode success cannot have a failure class")
        if self.outcome == "recovery_required" and self.failure_class is None:
            raise ValueError("recovery-required episode needs a typed failure")
        return self


__all__ = [
    "CandidateActionObservation", "EmbodiedEpisodeOutcome", "EmbodiedEpisodeRecord",
    "EpisodeFailureClass", "forbidden_candidate_field",
]
