from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExecutionConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True, allow_inf_nan=False)

    confirmation_id: str = Field(min_length=1)
    request_ref: str = Field(min_length=1)
    execution_state: Literal["confirmed", "partial", "aborted"]
    rollback_token: str | None = None
    producer_ts: int = Field(ge=0)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
