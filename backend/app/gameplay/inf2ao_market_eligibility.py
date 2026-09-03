"""INF-2AO: account-neutral Economy marker for certified output listing eligibility."""

from __future__ import annotations

from pydantic import ConfigDict, Field

from app.gameplay.models import StrictGameplayModel


class ProductionOutputMarketEligibilityIntent(StrictGameplayModel):
    """Caller supplies only the committed custody source and concurrency pins."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_event_id: str = Field(min_length=1)
    expected_source_revision: int = Field(ge=1)
    expected_economy_stream_revision: int = Field(ge=0)
    command_id: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    submitted_at: str = Field(min_length=1)


__all__ = ["ProductionOutputMarketEligibilityIntent"]
