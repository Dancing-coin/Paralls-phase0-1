from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CharacterBackgroundAgendaState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str
    latent_tendency: str = ""
    watch_focus: str = ""
    agenda_summary: str = ""
    agenda_phase: str = ""
    supervision_level: str = "weak"
    updated_at: int = 0


__all__ = ["CharacterBackgroundAgendaState"]

