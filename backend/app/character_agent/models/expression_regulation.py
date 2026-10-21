from __future__ import annotations

from types import MappingProxyType
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

ExpressionChannel = Literal["speech", "face", "body", "social_spatial", "physiology"]
_CHANNELS = ("speech", "face", "body", "social_spatial", "physiology")


class ExpressionRegulationFrame(BaseModel):
    """Read-only translation inputs; missing control policy remains unknown."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)

    intent: str = Field(min_length=1)
    social_context: tuple[str, ...] = ()
    rationality_band: str | None = None
    affect_pressure: float | None = Field(default=None, ge=0, le=1)
    masking_pressure: float | None = Field(default=None, ge=0, le=1)
    regulation_load: float | None = Field(default=None, ge=0, le=1)
    channel_control: Mapping[ExpressionChannel, float | None] = Field(default_factory=lambda: dict.fromkeys(_CHANNELS))
    leakage_channels: tuple[ExpressionChannel, ...] = ()
    recovery_state: str | None = None
    body_constraints: tuple[str, ...] = ()
    mental_resource_summary: tuple[str, ...] = ()
    soul_rule_summary: tuple[str, ...] = ()
    source_revisions: tuple[tuple[str, str], ...] = ()

    @field_validator("channel_control", mode="before")
    @classmethod
    def decode_channels(cls, value):
        if isinstance(value, (list, tuple)):
            if len({entry[0] for entry in value}) != len(value):
                raise ValueError("duplicate expression channel")
            return dict(value)
        return value

    @field_validator("channel_control")
    @classmethod
    def freeze_channels(cls, value):
        if any(control is not None and not 0 <= control <= 1 for control in value.values()):
            raise ValueError("channel controls must be bounded")
        return MappingProxyType(dict.fromkeys(_CHANNELS) | dict(value))

    @field_serializer("channel_control")
    def serialize_channels(self, value):
        # Channel names are semantic values, not body-control payload keys.
        return list(value.items())


class DeviationEpisode(BaseModel):
    """Observed expression timing, never a policy that triggers an episode."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    onset: int = Field(ge=0)
    peak: int | None = Field(default=None, ge=0)
    duration: int | None = Field(default=None, ge=0)
    recovery: int | None = Field(default=None, ge=0)
    channels: tuple[ExpressionChannel, ...] = ()
    source_refs: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def check_observed_order(self):
        if self.peak is not None and self.peak < self.onset:
            raise ValueError("deviation peak precedes onset")
        if self.recovery is not None and self.recovery < max(self.onset, self.peak or self.onset):
            raise ValueError("deviation recovery precedes observation")
        if self.recovery is not None and self.duration is not None and self.duration != self.recovery - self.onset:
            raise ValueError("deviation duration conflicts with recovery")
        return self
