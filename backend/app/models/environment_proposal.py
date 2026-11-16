from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EnvironmentProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True, allow_inf_nan=False)

    proposal_id: str = Field(min_length=1)
    candidate_ref: str
    decision_ref: str
    room_id: str = Field(min_length=1)
    scene_id: str = Field(min_length=1)
    zone_id: str = Field(min_length=1)
    target_environment_id: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    requested_change_type: str = Field(min_length=1)
    requested_strength: Literal["weak", "medium", "strong"]
    constraints_known: list[str] = Field(default_factory=list)
    fallback_options: list[dict[str, object]] = Field(default_factory=list)
    producer_ts: int = Field(ge=0)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
