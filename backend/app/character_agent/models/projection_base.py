from __future__ import annotations

from types import MappingProxyType
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator


ProjectionFreshness = Literal["current", "recent", "stale", "expired", "unknown"]
ProjectionUncertainty = Literal["known", "unknown", "stale", "conflicting"]


class ActorPrivateProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    captured_at: int = Field(ge=0)
    producer_ts: int = Field(ge=0)
    revision: str = Field(min_length=1)
    freshness: ProjectionFreshness = "unknown"
    visibility: str = Field(min_length=1)
    uncertainty: ProjectionUncertainty = "unknown"

    @field_validator("producer_ts")
    @classmethod
    def producer_not_before_capture(cls, value: int, info):
        captured_at = info.data.get("captured_at")
        if captured_at is not None and value < captured_at:
            raise ValueError("producer_ts must not precede captured_at")
        return value


def frozen_map(value: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType({str(key): nested for key, nested in value.items()})
