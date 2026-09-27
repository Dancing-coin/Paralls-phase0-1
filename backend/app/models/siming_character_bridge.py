import re
import re
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


BridgeBand = Literal["impulse", "opportunity", "fact_reveal"]
BridgeInputType = Literal["siming_high_level_message"]
LocomotionRelation = Literal[
    "coexist",
    "drive_locomotion",
    "replace_locomotion",
    "suspend",
]
DeliveryStatus = Literal[
    "accepted",
    "rejected",
    "deferred",
    "suggested_only",
    "rejected_by_filter",
    "blocked_by_world_constraint",
    "expired",
    "unroutable",
    "target_unavailable",
]

_TAG_NAMESPACES = frozenset(
    {
        "goal",
        "intent",
        "evidence",
        "capability",
        "affordance",
        "constraint",
        "state",
        "status",
        "action",
        "phase",
        "occupy",
        "event",
        "authority",
        "presentation",
        "expression",
    }
)
_FORBIDDEN_INTENT_FIELDS = frozenset(
    {
        "damage",
        "hit",
        "hit_result",
        "inventory",
        "inventory_mutation",
        "projectile",
        "ammo",
        "status_write",
        "transform",
        "velocity",
        "global_position",
        "linear_velocity",
        "animation",
        "animation_state",
        "raw_animation",
        "raw_pose",
        "pose",
        "clip",
        "clip_ref",
        "raw_clip_filename",
        "world_truth",
        "world_write",
        "authority_result",
    }
)


def _validate_namespaced_tags(value: object, field_name: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = [value]
    else:
        values = list(value)  # type: ignore[arg-type]
    normalized: list[str] = []
    for item in values:
        tag = str(item).strip()
        parts = tag.split(":", 1)
        if len(parts) != 2 or parts[0] not in _TAG_NAMESPACES or not parts[1]:
            raise ValueError(f"{field_name} contains unnamespaced tag: {tag}")
        normalized.append(tag)
    return normalized


def _reject_intent_fields(value: object) -> object:
    if not isinstance(value, Mapping):
        return value
    present = sorted(_FORBIDDEN_INTENT_FIELDS.intersection(str(key) for key in value))
    if present:
        raise ValueError(f"forbidden intent field(s): {', '.join(present)}")
    semantic_action_id = str(value.get("semantic_action_id", value.get("action_id", "")) or "")
    if semantic_action_id.casefold() in {"boxing", "short punch", "sword attack"}:
        raise ValueError("raw clip filename is not a semantic action id")
    if semantic_action_id and (
        re.search(r"\.(?:glb|fbx|anim|tres|res)$", semantic_action_id, re.IGNORECASE)
        or "/" in semantic_action_id
        or "\\" in semantic_action_id
    ):
        raise ValueError("raw clip filename is not a semantic action id")
    return value


class CharacterSemanticIntentProposal(BaseModel):
    """Authority-neutral semantic proposal shared by Agent, INF, and Siming."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_ref: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    intent_tags: list[str] = Field(default_factory=list)
    context_tags: list[str] = Field(default_factory=list)
    semantic_action_id: str | None = Field(default=None, min_length=1)
    target_ref: str | None = Field(default=None, min_length=1)
    move: tuple[float, float] | None = None
    facing: float | None = None
    claims: list[str] = Field(default_factory=list)
    locomotion_relation: LocomotionRelation = "coexist"
    presentation_cues: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    source: str = Field(min_length=1)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    provenance: Mapping[str, Any] = Field(default_factory=dict)
    privacy_scope: str = Field(min_length=1)
    authority_scope: str = Field(min_length=1)
    expected_revision_vector: Mapping[str, int] = Field(default_factory=dict)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def reject_unsafe_fields(cls, value: object) -> object:
        return _reject_intent_fields(value)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "CharacterSemanticIntentProposal":
        return cls.model_validate(payload)

    @classmethod
    def from_inf_payload(cls, payload: Mapping[str, Any]) -> "CharacterSemanticIntentProposal":
        """Normalize an INF fact/metadata proposal without granting authority."""
        normalized = dict(payload)
        normalized.setdefault("source", "inf")
        normalized.setdefault("source_id", "inf")
        normalized.setdefault("privacy_scope", "actor_private:unknown")
        normalized.setdefault("authority_scope", "world:default")
        normalized.setdefault("causation_id", "inf:causation:unknown")
        normalized.setdefault("correlation_id", "inf:correlation:unknown")
        return cls.model_validate(normalized)

    @classmethod
    def _normalize_tags(cls, value: object, info: Any) -> list[str]:
        return _validate_namespaced_tags(value, info.field_name)

    _normalize_intent_tags = field_validator(
        "intent_tags", "context_tags", "presentation_cues", mode="before"
    )(_normalize_tags)

    @model_validator(mode="after")
    def validate_metadata(self) -> "CharacterSemanticIntentProposal":
        if any(int(value) < 0 for value in self.expected_revision_vector.values()):
            raise ValueError("expected revision vector entries must be non-negative")
        return self


class SimingCharacterCompatibilityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    delivery_id: str
    actor_id: str
    input_type: BridgeInputType
    band: BridgeBand
    producer_ts: int
    room_id: str
    scene_id: str
    zone_id: str
    causation_id: str
    correlation_id: str
    presentation_hint: str | None = None
    pressure_hint: str | None = None
    salience_boost: float | None = None
    reason_scope: str | None = None
    target_actor_id: str | None = None
    target_object_id: str | None = None
    target_environment_id: str | None = None
    intent_tags: list[str] = Field(default_factory=list)
    context_tags: list[str] = Field(default_factory=list)
    semantic_action_id: str | None = Field(default=None, min_length=1)
    claims: list[str] = Field(default_factory=list)
    locomotion_relation: LocomotionRelation = "coexist"
    presentation_cues: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def reject_forbidden_low_level_fields(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value

        forbidden = {
            "go_to_position",
            "kill_target_now",
            "believe_X_now",
            "choose_Y_now",
            "physical_success",
        }
        present = sorted(forbidden.intersection(value.keys()))
        if present:
            raise ValueError(f"forbidden compatibility input field(s): {', '.join(present)}")
        _reject_intent_fields(value)
        return value

    @classmethod
    def _normalize_tags(cls, value: object, info: Any) -> list[str]:
        return _validate_namespaced_tags(value, info.field_name)

    _normalize_semantic_tags = field_validator(
        "intent_tags", "context_tags", "presentation_cues", mode="before"
    )(_normalize_tags)

    @model_validator(mode="after")
    def validate_semantic_action(self) -> "SimingCharacterCompatibilityInput":
        if self.semantic_action_id:
            _reject_intent_fields({"semantic_action_id": self.semantic_action_id})
        return self

    @model_validator(mode="after")
    def require_matching_target_actor_id_when_present(self) -> "SimingCharacterCompatibilityInput":
        if self.target_actor_id is not None and self.target_actor_id != self.actor_id:
            raise ValueError("target_actor_id must match actor_id when provided")
        return self


class CharacterDeliveryAuditSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    delivery_id: str
    actor_id: str
    status: DeliveryStatus
    producer_ts: int
    causation_id: str
    correlation_id: str
