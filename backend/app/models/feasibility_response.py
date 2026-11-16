from pydantic import BaseModel, ConfigDict, Field


class FeasibilityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True, allow_inf_nan=False)

    response_id: str = Field(min_length=1)
    proposal_ref: str = Field(min_length=1)
    feasible: bool
    constraints: list[str] = Field(default_factory=list)
    estimated_effect: dict[str, object] = Field(default_factory=dict)
    alternative_suggestions: list[dict[str, object]] = Field(default_factory=list)
    producer_ts: int = Field(ge=0)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
