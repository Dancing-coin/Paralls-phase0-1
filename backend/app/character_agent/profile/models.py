from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictProfileModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


ProfileScalar = Field(ge=0.0, le=1.0)


class IdentityCore(StrictProfileModel):
    character_id: str
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    occupation_role: str


class TraitVectorLayer(StrictProfileModel):
    courage: float = ProfileScalar
    scheming: float = ProfileScalar
    empathy: float = ProfileScalar
    rationality: float = ProfileScalar
    sociability: float = ProfileScalar


class ConversationPersonalityLayer(StrictProfileModel):
    social_openness: float = ProfileScalar
    privacy_sensitivity: float = ProfileScalar
    talk_initiative: float = ProfileScalar
    deception_control: float = ProfileScalar
    trust_threshold_for_private_talk: float = ProfileScalar


class OriginSeed(StrictProfileModel):
    homeland: str | None = None
    formative_context: str | None = None
    current_scene_function: str | None = None


class LifeMemoryBackbone(StrictProfileModel):
    defining_memories: list[str] = Field(default_factory=list)
    unresolved_knots: list[str] = Field(default_factory=list)


class VirtueValueLayer(StrictProfileModel):
    value_priorities: list[str] = Field(default_factory=list)
    red_lines: list[str] = Field(default_factory=list)
    forbidden_behaviors: list[str] = Field(default_factory=list)


class CapabilityConstraintLayer(StrictProfileModel):
    skills: list[str] = Field(default_factory=list)
    knowledge_domains: list[str] = Field(default_factory=list)
    physical_constraints: list[str] = Field(default_factory=list)
    psychological_constraints: list[str] = Field(default_factory=list)
    social_constraints: list[str] = Field(default_factory=list)


class StyleExpressionBiasLayer(StrictProfileModel):
    speech_style: str
    silence_pattern: str
    gesture_bias: str
    posture_bias: str


class RuntimeDefaults(StrictProfileModel):
    default_control_mode: Literal[
        "agent_full_auto",
        "player_priority_assisted",
        "away_conservative_takeover",
        "scripted_override",
    ] = "agent_full_auto"


class CharacterProfile(StrictProfileModel):
    identity_core: IdentityCore
    origin_seed: OriginSeed
    life_memory_backbone: LifeMemoryBackbone
    virtue_value_layer: VirtueValueLayer
    trait_vector_layer: TraitVectorLayer
    capability_constraint_layer: CapabilityConstraintLayer
    style_expression_bias_layer: StyleExpressionBiasLayer
    conversation_personality_layer: ConversationPersonalityLayer
    runtime_defaults: RuntimeDefaults = Field(default_factory=RuntimeDefaults)
