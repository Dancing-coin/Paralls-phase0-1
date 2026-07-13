from pydantic import BaseModel, ConfigDict, Field


class KimodoSelectedSkillPathHint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    binding_id: str = ""
    skill_id: str = ""
    action_id: str = ""
    skill_path_tags: list[str] = Field(default_factory=list)


class KimodoSettlementOutcomeHint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome_band: str = ""
    failure_domains: list[str] = Field(default_factory=list)
    primary_failure_domain: str = ""
    realization_hints: list[str] = Field(default_factory=list)


class KimodoActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str
    semantic_keys: list[str] = Field(default_factory=list)
    target_actor_id: str | None = None
    target_object_id: str | None = None
    execution_mode: str
    selected_skill_path: KimodoSelectedSkillPathHint = Field(default_factory=KimodoSelectedSkillPathHint)
    primitive_action_tags: list[str] = Field(default_factory=list)
    settlement_outcome: KimodoSettlementOutcomeHint = Field(default_factory=KimodoSettlementOutcomeHint)


class KimodoRealizationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str
    semantic_keys: list[str] = Field(default_factory=list)
    execution_mode: str
    selected_skill_path: KimodoSelectedSkillPathHint = Field(default_factory=KimodoSelectedSkillPathHint)
    primitive_action_tags: list[str] = Field(default_factory=list)
    settlement_outcome: KimodoSettlementOutcomeHint = Field(default_factory=KimodoSettlementOutcomeHint)
    generated_motion_allowed: bool = False
    local_fallback_asset_refs: list[str] = Field(default_factory=list)
    missing_semantic_keys: list[str] = Field(default_factory=list)
