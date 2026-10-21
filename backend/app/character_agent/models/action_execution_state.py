from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.character_agent.models.projection_base import ActorPrivateProjection


class ActionExecutionState(ActorPrivateProjection):
    intent_ref: str | None = Field(default=None, min_length=1)
    request_ref: str | None = Field(default=None, min_length=1)
    execution_ref: str | None = Field(default=None, min_length=1)
    result_ref: str | None = Field(default=None, min_length=1)
    status: Literal["unknown", "intended", "requested", "executing", "succeeded", "failed", "cancelled"] = "unknown"
