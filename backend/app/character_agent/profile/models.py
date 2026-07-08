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


class NeedWeightMap(StrictProfileModel):
    physiological: float = ProfileScalar
    safety: float = ProfileScalar
    belonging: float = ProfileScalar
    esteem: float = ProfileScalar
    self_actualization: float = ProfileScalar


class NeedChannelMap(StrictProfileModel):
    physiological: list[str] = Field(default_factory=list)
    safety: list[str] = Field(default_factory=list)
    belonging: list[str] = Field(default_factory=list)
    esteem: list[str] = Field(default_factory=list)
    self_actualization: list[str] = Field(default_factory=list)


class NeedHierarchyLayer(StrictProfileModel):
    base_weights: NeedWeightMap
    deprivation_sensitivity: NeedWeightMap
    satisfaction_sensitivity: NeedWeightMap
    dominant_drives: list[str] = Field(default_factory=list)
    satisfaction_channels: NeedChannelMap = Field(default_factory=NeedChannelMap)
    frustration_channels: NeedChannelMap = Field(default_factory=NeedChannelMap)


class BaselineTemperament(StrictProfileModel):
    caution: float = ProfileScalar
    dominance: float = ProfileScalar
    attachment: float = ProfileScalar
    emotional_reactivity: float = ProfileScalar
    recovery_speed: float = ProfileScalar
    impulse_control: float = ProfileScalar


class ConflictStyle(StrictProfileModel):
    confrontation_tendency: float = ProfileScalar
    avoidance_tendency: float = ProfileScalar
    mediation_tendency: float = ProfileScalar
    escalation_threshold: float = ProfileScalar


class DefensePatterns(StrictProfileModel):
    under_pressure: list[str]
    under_shame: list[str]
    under_threat: list[str]
    under_loss: list[str]


class TrustDynamics(StrictProfileModel):
    initial_trust_bias: float = ProfileScalar
    betrayal_memory_weight: float = ProfileScalar
    forgiveness_threshold: float = ProfileScalar
    loyalty_lock_in: float = ProfileScalar


class ExpressionBias(StrictProfileModel):
    outward_warmth: float = ProfileScalar
    emotional_transparency: float = ProfileScalar
    facial_control: float = ProfileScalar
    verbal_indirection: float = ProfileScalar


class TemperamentResponseLayer(StrictProfileModel):
    baseline_temperament: BaselineTemperament
    conflict_style: ConflictStyle
    defense_patterns: DefensePatterns
    trust_dynamics: TrustDynamics
    expression_bias: ExpressionBias


class DriftPolicy(StrictProfileModel):
    minimum_cross_scene_count: int = Field(default=3, ge=1)
    minimum_confirming_events: int = Field(default=6, ge=1)
    minimum_time_span: Literal["long_arc"] = "long_arc"
    require_non_transient_evidence: bool = True


class LongTermPersonalityDriftLayer(StrictProfileModel):
    stable_shifts: list[str] = Field(default_factory=list)
    reinforced_patterns: list[str] = Field(default_factory=list)
    weakened_patterns: list[str] = Field(default_factory=list)
    need_reweights: dict[str, float] = Field(default_factory=dict)
    trust_reweights: dict[str, float] = Field(default_factory=dict)
    expression_reweights: dict[str, float] = Field(default_factory=dict)
    drift_policy: DriftPolicy = Field(default_factory=DriftPolicy)


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
    need_hierarchy_layer: NeedHierarchyLayer
    temperament_response_layer: TemperamentResponseLayer
    long_term_personality_drift_layer: LongTermPersonalityDriftLayer = Field(
        default_factory=LongTermPersonalityDriftLayer
    )
    runtime_defaults: RuntimeDefaults = Field(default_factory=RuntimeDefaults)
