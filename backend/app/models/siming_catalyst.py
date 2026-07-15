from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.authority_event import AuthorityEvent


CatalystType = Literal[
    "fact_reveal",
    "attention_prompt",
    "opportunity_hint",
    "pressure_hint",
    "impulse_hint",
]
ImpulseAxis = Literal["narrative", "relation", "action"]
PresentationEffect = Literal[
    "narration_text",
    "subtle_audio_cue",
    "screen_vignette",
    "controller_rumble",
    "short_ui_hint",
]

FORBIDDEN_CATALYST_PAYLOAD_FIELDS = {
    "actor_control_frames",
    "action_request_bundle",
    "character_agent_execution",
    "physical_success",
    "world_mutation",
    "private_memory_patch",
    "selected_intent",
    "command_type",
    "low_level_motion",
}

FORBIDDEN_INNER_PROMPT_PAYLOAD_FIELDS = FORBIDDEN_CATALYST_PAYLOAD_FIELDS | {
    "focus_target_id",
    "movement_input",
    "interact_input",
    "backend_action_request",
    "object_state_patch",
    "environment_state_patch",
}

PRIVATE_REF_NAMESPACE_PREFIXES = (
    "character_private_cache",
    "character_private_context",
    "character_private",
    "character_mm",
    "private_cache",
    "private_patch",
    "patch_session",
    "patch_context",
    "inference_history",
)

_PRIVATE_REF_NAMESPACE_PATTERN = re.compile(
    r"(^|[:/])("
    + "|".join(re.escape(prefix) for prefix in PRIVATE_REF_NAMESPACE_PREFIXES)
    + r")(?=[:_]|$)"
)

_CATALYST_EVENT_TYPES = {
    "siming.fact_reveal",
    "siming.impulse",
    "siming.opportunity",
    "siming.attention_prompt",
    "siming.pressure_hint",
}

_REF_FIELD_NAMES = {
    "catalyst_id",
    "prompt_id",
    "target_actor_id",
    "target_object_id",
    "target_environment_id",
    "source_authority_event_id",
    "situation_snapshot_id",
    "evidence_refs",
    "conflict_refs",
    "causation_id",
    "correlation_id",
}


def _required_str(value: object, fallback: str = "") -> str:
    rendered = str(value or fallback or "").strip()
    if not rendered:
        raise ValueError("required string field is empty")
    return rendered


def _contains_private_ref_marker(value: str) -> bool:
    return bool(_PRIVATE_REF_NAMESPACE_PATTERN.search(value.strip()))


def _iter_ref_like_values(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if isinstance(value, list):
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]
    return []


def _reject_private_ref_fields(model: BaseModel, field_names: set[str]) -> None:
    for field_name in field_names:
        field_value = getattr(model, field_name, None)
        if any(_contains_private_ref_marker(value) for value in _iter_ref_like_values(field_value)):
            raise ValueError(f"private refs are forbidden in {field_name}")


def _reject_forbidden_payload_fields(payload: dict[str, Any], forbidden_fields: set[str]) -> None:
    present = sorted(forbidden_fields.intersection(payload.keys()))
    if present:
        raise ValueError(f"forbidden Siming payload field(s): {', '.join(present)}")


def _reject_private_payload_refs(payload: dict[str, Any]) -> None:
    for key, value in payload.items():
        key_parts = key.lower().split("_")
        if not any(part in {"ref", "refs", "id", "ids", "lineage", "context", "source", "conflict", "conflicts"} for part in key_parts):
            continue
        if any(_contains_private_ref_marker(item) for item in _iter_ref_like_values(value)):
            raise ValueError(f"private refs are forbidden in {key}")


class SimingCatalystInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalyst_id: str
    catalyst_type: CatalystType
    impulse_axis: ImpulseAxis | None = None
    impulse_label: str | None = None
    room_id: str
    scene_id: str
    zone_id: str
    target_actor_id: str | None = None
    target_object_id: str | None = None
    target_environment_id: str | None = None
    source_authority_event_id: str
    situation_snapshot_id: str | None = None
    presentation_hint: str | None = None
    pressure_hint: str | None = None
    salience_boost: float | None = None
    intensity: float = 0.0
    reason_scope: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    conflict_refs: list[str] = Field(default_factory=list)
    causation_id: str
    correlation_id: str
    producer_ts: int

    @field_validator("evidence_refs", "conflict_refs", mode="before")
    @classmethod
    def normalize_string_list(cls, value: object) -> list[str]:
        return _iter_ref_like_values(value)

    @model_validator(mode="after")
    def validate_boundary(self) -> "SimingCatalystInput":
        _reject_private_ref_fields(self, _REF_FIELD_NAMES)
        if self.intensity > 0.35:
            raise ValueError("catalyst intensity exceeds 0.35")
        if self.catalyst_type == "impulse_hint":
            if self.impulse_axis is None:
                raise ValueError("impulse_hint requires impulse_axis")
            if not any([self.target_actor_id, self.target_object_id, self.target_environment_id, self.situation_snapshot_id]):
                raise ValueError("impulse_hint requires target or situation_snapshot_id")
            if not self.evidence_refs:
                raise ValueError("impulse_hint requires evidence_refs")
        return self

    @classmethod
    def from_authority_event(cls, event: AuthorityEvent) -> "SimingCatalystInput":
        payload = dict(event.payload)
        _reject_forbidden_payload_fields(payload, FORBIDDEN_CATALYST_PAYLOAD_FIELDS)
        _reject_private_payload_refs(payload)
        if _is_player_controlled_target(payload):
            raise ValueError("player-controlled actor must receive inner_prompt, not impulse_hint")

        raw_type = event.event_type.removeprefix("siming.")
        catalyst_type = {
            "impulse": "impulse_hint",
            "opportunity": "opportunity_hint",
            "attention": "attention_prompt",
            "attention_prompt": "attention_prompt",
            "pressure": "pressure_hint",
            "pressure_hint": "pressure_hint",
            "fact_reveal": "fact_reveal",
        }.get(raw_type, raw_type)

        return cls(
            catalyst_id=_required_str(payload.get("message_id"), event.event_id),
            catalyst_type=catalyst_type,
            impulse_axis=_optional_str(payload.get("impulse_axis")),
            impulse_label=_optional_str(payload.get("impulse_label")),
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            target_actor_id=_optional_str(payload.get("target_actor_id")),
            target_object_id=_optional_str(payload.get("target_object_id")),
            target_environment_id=_optional_str(payload.get("target_environment_id")),
            source_authority_event_id=event.event_id,
            situation_snapshot_id=_optional_str(payload.get("situation_snapshot_id")),
            presentation_hint=_optional_str(payload.get("presentation_hint")),
            pressure_hint=_optional_str(payload.get("pressure_hint")),
            salience_boost=_optional_float(payload.get("salience_boost")),
            intensity=float(payload.get("intensity", 0.0) or 0.0),
            reason_scope=_optional_str(payload.get("reason_scope")),
            evidence_refs=payload.get("evidence_refs", []),
            conflict_refs=payload.get("conflict_refs", []),
            causation_id=event.causation_id,
            correlation_id=event.correlation_id,
            producer_ts=event.producer_ts,
        )


class InnerPrompt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_id: str
    prompt_type: Literal["inner_prompt"] = "inner_prompt"
    room_id: str
    scene_id: str
    zone_id: str
    target_actor_id: str
    source_authority_event_id: str
    situation_snapshot_id: str | None = None
    prompt_text: str
    intensity: float = 0.0
    evidence_refs: list[str] = Field(default_factory=list)
    player_facing: bool = True
    non_authoritative: bool = True
    presentation_effects: list[PresentationEffect] = Field(default_factory=list)
    causation_id: str
    correlation_id: str
    producer_ts: int

    @field_validator("evidence_refs", mode="before")
    @classmethod
    def normalize_evidence_refs(cls, value: object) -> list[str]:
        return _iter_ref_like_values(value)

    @model_validator(mode="after")
    def validate_boundary(self) -> "InnerPrompt":
        _reject_private_ref_fields(self, _REF_FIELD_NAMES)
        if self.intensity > 0.35:
            raise ValueError("inner_prompt intensity exceeds 0.35")
        if not self.player_facing:
            raise ValueError("inner_prompt must be player_facing")
        if not self.non_authoritative:
            raise ValueError("inner_prompt must be non_authoritative")
        if not self.evidence_refs and self.situation_snapshot_id is None:
            raise ValueError("inner_prompt requires evidence_refs or situation_snapshot_id")
        return self

    @classmethod
    def from_authority_event(cls, event: AuthorityEvent) -> "InnerPrompt":
        payload = dict(event.payload)
        _reject_forbidden_payload_fields(payload, FORBIDDEN_INNER_PROMPT_PAYLOAD_FIELDS)
        _reject_private_payload_refs(payload)
        return cls(
            prompt_id=_required_str(payload.get("message_id"), event.event_id),
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            target_actor_id=_required_str(payload.get("target_actor_id")),
            source_authority_event_id=event.event_id,
            situation_snapshot_id=_optional_str(payload.get("situation_snapshot_id")),
            prompt_text=_required_str(payload.get("prompt_text"), str(payload.get("presentation_hint", "") or "")),
            intensity=float(payload.get("intensity", 0.0) or 0.0),
            evidence_refs=payload.get("evidence_refs", []),
            player_facing=bool(payload.get("player_facing", True)),
            non_authoritative=bool(payload.get("non_authoritative", True)),
            presentation_effects=list(payload.get("presentation_effects", []) or []),
            causation_id=event.causation_id,
            correlation_id=event.correlation_id,
            producer_ts=event.producer_ts,
        )


def validate_siming_authority_event(event: AuthorityEvent) -> None:
    if not event.event_type.startswith("siming."):
        return
    if event.event_type == "siming.inner_prompt":
        InnerPrompt.from_authority_event(event)
        return
    _reject_forbidden_payload_fields(dict(event.payload), FORBIDDEN_CATALYST_PAYLOAD_FIELDS)
    _reject_private_payload_refs(dict(event.payload))
    if event.event_type in _CATALYST_EVENT_TYPES:
        SimingCatalystInput.from_authority_event(event)


def _optional_str(value: object) -> str | None:
    rendered = str(value or "").strip()
    return rendered or None


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _is_player_controlled_target(payload: dict[str, Any]) -> bool:
    target_actor_id = str(payload.get("target_actor_id", "") or "").strip().lower()
    target_control = str(payload.get("target_actor_control", "") or payload.get("actor_control", "") or "").strip().lower()
    return target_actor_id == "player" or target_control in {"player", "player_controlled", "human"}
