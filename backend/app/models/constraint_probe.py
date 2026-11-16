from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ConstraintProbe(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True, allow_inf_nan=False)

    probe_id: str = Field(min_length=1)
    target_environment_id: str = Field(min_length=1)
    constraint_type: Literal["cooldown", "material", "spatial", "resource", "all"]
    producer_ts: int = Field(ge=0)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)


class ConstraintStateResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True, allow_inf_nan=False)

    state_id: str = Field(min_length=1)
    probe_ref: str = Field(min_length=1)
    active_constraints: dict[str, object] = Field(default_factory=dict)
    cooldown_remaining: int = Field(ge=0)
    producer_ts: int = Field(ge=0)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
