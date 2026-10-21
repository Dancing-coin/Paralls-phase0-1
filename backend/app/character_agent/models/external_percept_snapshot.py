from __future__ import annotations

from pydantic import Field

from app.character_agent.models.projection_base import ActorPrivateProjection


class ExternalPerceptSnapshot(ActorPrivateProjection):
    subject_ref: str = Field(min_length=1)
    summary: str = ""
    conflict_refs: tuple[str, ...] = ()
    visibility: str = "actor_private"
