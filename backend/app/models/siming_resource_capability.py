import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.siming_heavenly_graph import HeavenlyGraphScope


class StrictResourceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ResourceCapabilityPackage(StrictResourceModel):
    capability_id: str = Field(min_length=1)
    asset_bundle: str = Field(min_length=1)
    scene_refs: list[str] = Field(min_length=1)
    actor_ids: list[str] = Field(min_length=1)
    object_ids: list[str] = Field(default_factory=list)
    environment_ids: list[str] = Field(default_factory=list)
    realization_keys: list[str] = Field(default_factory=list)
    semantic_purposes: list[str] = Field(min_length=1)
    load_cost: float = Field(ge=0.0)
    loaded: bool
    cooldown_until: int = Field(ge=0)


class ResourceRealizationRequest(StrictResourceModel):
    node_id: str = Field(min_length=1)
    actor_bindings: dict[str, str] = Field(min_length=1)
    target_object_id: str | None = Field(default=None, min_length=1)
    target_environment_id: str | None = Field(default=None, min_length=1)
    required_realization_keys: list[str] = Field(min_length=1)
    camera_pattern: str = Field(min_length=1)
    semantic_purpose: str = Field(min_length=1)
    location_state: str = Field(min_length=1)

    def signature(self, asset_bundle: str) -> str:
        payload = [
            asset_bundle,
            sorted(self.actor_bindings.items()),
            self.camera_pattern,
            self.semantic_purpose,
            self.location_state,
        ]
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


class ResourceMatch(StrictResourceModel):
    accepted: bool
    reason: str = ""
    capability: ResourceCapabilityPackage | None = None
    realization_signature: str = ""
    fatigue_penalty: float = Field(default=0.0, ge=0.0)

    @model_validator(mode="after")
    def require_capability_for_accepted_match(self) -> "ResourceMatch":
        if self.accepted and (self.capability is None or not self.realization_signature):
            raise ValueError("accepted resource match requires capability and realization signature")
        return self


class StagingAck(StrictResourceModel):
    source: Literal["godot", "character", "esm"]
    correlation_id: str = Field(min_length=1)
    accepted: bool
    reason: str = ""


class StagingRequest(StrictResourceModel):
    scope: HeavenlyGraphScope
    node_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    obligation_id: str = Field(min_length=1)
    recorded_at: int = Field(ge=0)
    resource_match: ResourceMatch


class StagingResult(StrictResourceModel):
    node_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    status: Literal["staged", "aborted_before_activation", "cancelled"]
    story_node_lifecycle: Literal["staged", "aborted"]
    obligation_status: Literal["open", "pressured", "partially_satisfied"]
    realization_signature: str = Field(min_length=1)
    reason: str = ""

    @model_validator(mode="after")
    def validate_staging_lifecycle(self) -> "StagingResult":
        if self.status == "staged" and self.story_node_lifecycle != "staged":
            raise ValueError("staged result requires staged story node lifecycle")
        if self.status != "staged" and self.story_node_lifecycle != "aborted":
            raise ValueError("aborted or cancelled result requires aborted story node lifecycle")
        return self
