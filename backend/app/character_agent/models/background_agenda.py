from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CharacterBackgroundAgendaEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agenda_id: str
    agenda_kind: str
    title: str
    summary: str = ""
    target_ref: str = ""
    horizon: str = "mid"
    status: str = "active"
    priority: float = Field(default=0.5, ge=0.0, le=1.0)
    source: str = ""
    last_reinforced_ts: int = 0
    last_progress_ts: int = 0
    blocked_count: int = 0


class CharacterBackgroundAgendaState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str
    latent_tendency: str = ""
    watch_focus: str = ""
    agenda_summary: str = ""
    agenda_phase: str = ""
    supervision_level: str = "weak"
    dominant_agenda_id: str = ""
    agenda_entries: list[CharacterBackgroundAgendaEntry] = Field(default_factory=list)
    updated_at: int = 0


__all__ = ["CharacterBackgroundAgendaEntry", "CharacterBackgroundAgendaState"]
