from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SettlementCategory = Literal["cognitive", "social", "physical", "tool", "authority", "special"]
ActionKind = Literal["composite", "primitive"]
Learnability = Literal["natural", "trained", "granted", "locked"]
SkillSource = Literal["authored", "learned", "temporary", "equipment", "authority", "scripted", "constrained"]
SkillRank = Literal["none", "novice", "basic", "trained", "expert", "master", "blocked"]
OutcomeBand = Literal["blocked", "failed", "partial", "success_with_cost", "clean_success", "misfire"]
FailureDomain = Literal[
    "none",
    "skill_failure",
    "missing_requirement",
    "world_constraint",
    "physical_failure",
    "authority_policy_failure",
    "social_resistance",
    "state_interference",
    "tool_failure",
    "knowledge_mismatch",
    "realization_failure",
]


class StrictSkillModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SkillDefinition(StrictSkillModel):
    skill_id: str
    display_name: str = ""
    settlement_categories: list[SettlementCategory] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    role_tags: list[str] = Field(default_factory=list)
    learnability: Learnability = "natural"
    risk_tags: list[str] = Field(default_factory=list)
    visibility_default: dict[str, object] = Field(default_factory=dict)


class ActionDefinition(StrictSkillModel):
    action_id: str
    kind: ActionKind
    target_types: list[str] = Field(default_factory=list)
    settlement_categories: list[SettlementCategory] = Field(default_factory=list)
    primitive_sequence_templates: dict[str, list[str]] = Field(default_factory=dict)
    variant_rules: list[dict[str, object]] = Field(default_factory=list)
    realization_keys: list[str] = Field(default_factory=list)


class SkillActionBinding(StrictSkillModel):
    binding_id: str
    skill_id: str
    action_id: str
    skill_path_tags: list[str] = Field(default_factory=list)
    eligibility: dict[str, object] = Field(default_factory=dict)
    quality: dict[str, object] = Field(default_factory=dict)
    learning: dict[str, object] = Field(default_factory=dict)


class CharacterSkillState(StrictSkillModel):
    actor_id: str
    skill_id: str
    source: SkillSource
    rank: SkillRank = "none"
    proficiency: float = Field(default=0.0, ge=0.0, le=1.0, strict=True)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, strict=True)
    familiarity: dict[str, float] = Field(default_factory=dict)
    restrictions: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    visibility: dict[str, object] = Field(default_factory=dict)


class SkillAffordanceSummary(StrictSkillModel):
    actor_id: str
    available_action_families: dict[str, dict[str, object]] = Field(default_factory=dict)
    blocked_action_families: dict[str, dict[str, object]] = Field(default_factory=dict)
    notable_constraints: list[str] = Field(default_factory=list)
    recent_skill_feedback: list[str] = Field(default_factory=list)


class CompositeActionProposal(StrictSkillModel):
    proposal_id: str
    actor_id: str
    source_intent: str
    action_id: str
    target_refs: dict[str, str] = Field(default_factory=dict)
    preferred_strategy_tags: list[str] = Field(default_factory=list)
    forbidden_strategy_tags: list[str] = Field(default_factory=list)
    desired_outcomes: list[str] = Field(default_factory=list)


class SkillEvaluationRequest(StrictSkillModel):
    actor_id: str
    action_id: str
    target_refs: dict[str, str] = Field(default_factory=dict)
    preferred_strategy_tags: list[str] = Field(default_factory=list)
    forbidden_strategy_tags: list[str] = Field(default_factory=list)
    dynamic_state: dict[str, object] = Field(default_factory=dict)
    equipment_refs: list[str] = Field(default_factory=list)


class SkillEvaluationResult(StrictSkillModel):
    actor_id: str
    action_id: str
    selected_path: dict[str, object] = Field(default_factory=dict)
    viable_paths: list[dict[str, object]] = Field(default_factory=list)
    blocked_paths: list[dict[str, object]] = Field(default_factory=list)
    recommendation_reason: list[str] = Field(default_factory=list)
    learning_policy_snapshot: dict[str, object] = Field(default_factory=dict)


class PrimitiveActionPlan(StrictSkillModel):
    composite_action_id: str
    skill_path_id: str
    primitive_actions: list[str] = Field(default_factory=list)
    realization_keys: list[str] = Field(default_factory=list)


class ActionSettlementResult(StrictSkillModel):
    outcome_band: OutcomeBand
    failure_domains: list[FailureDomain] = Field(default_factory=list)
    primary_failure_domain: FailureDomain = "none"
    semantic_effects: list[str] = Field(default_factory=list)
    physical_effects: list[str] = Field(default_factory=list)
    social_effects: list[str] = Field(default_factory=list)
    costs: list[str] = Field(default_factory=list)
    realization_hints: list[str] = Field(default_factory=list)


class SkillLearningPolicy(StrictSkillModel):
    evidence_collection_enabled: bool = True
    candidate_generation_enabled: bool = True
    promotion_enabled: bool = False
    auto_promotion_enabled: bool = False
    allowed_domains: list[str] = Field(default_factory=list)
    blocked_domains: list[str] = Field(default_factory=lambda: ["authority", "special"])


class SkillEvidence(StrictSkillModel):
    evidence_id: str
    actor_id: str
    skill_id: str
    action_id: str
    binding_id: str = ""
    source_settlement_id: str
    outcome_band: OutcomeBand
    primary_failure_domain: FailureDomain
    failure_domains: list[FailureDomain] = Field(default_factory=list)
    evidence_channels: dict[str, object] = Field(default_factory=dict)
    eligible_for_candidate: bool = False
    eligible_for_promotion: bool = False
