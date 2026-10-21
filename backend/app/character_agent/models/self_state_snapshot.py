from __future__ import annotations

from typing import Mapping

from pydantic import Field, field_validator

from app.character_agent.models.projection_base import ActorPrivateProjection, frozen_map


class SelfStateSnapshot(ActorPrivateProjection):
    body_state_class: str = "unknown"
    combat_influences: Mapping[str, object] = Field(default_factory=dict)

    @field_validator("combat_influences", mode="after")
    @classmethod
    def freeze_influences(cls, value: Mapping[str, object]) -> Mapping[str, object]:
        return frozen_map(value)
