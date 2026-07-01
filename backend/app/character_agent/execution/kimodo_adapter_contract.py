from pydantic import BaseModel, ConfigDict, Field


class KimodoActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str
    semantic_keys: list[str] = Field(default_factory=list)
    target_actor_id: str | None = None
    target_object_id: str | None = None
    execution_mode: str


class KimodoRealizationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str
    semantic_keys: list[str] = Field(default_factory=list)
    execution_mode: str
    generated_motion_allowed: bool = False
    local_fallback_asset_refs: list[str] = Field(default_factory=list)
    missing_semantic_keys: list[str] = Field(default_factory=list)
