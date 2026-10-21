from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MentalRegulationProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_id: str
    clarity: float | None = Field(default=None, ge=0, le=1)
    attention_stability: float | None = Field(default=None, ge=0, le=1)
    inhibitory_control: float | None = Field(default=None, ge=0, le=1)
    goal_continuity: float | None = Field(default=None, ge=0, le=1)
    masking_load: float | None = Field(default=None, ge=0, le=1)
    regulation_pressure: float | None = Field(default=None, ge=0, le=1)
    rationality_band: Literal["stable", "strained", "edge", "temporary_loss", "continuity_risk"] | None = None
    source_factors: tuple[tuple[str, float], ...] = ()
    goal_conflict_refs: tuple[str, ...] = ()
    mental_resource_summary: tuple[()] = ()
    source_revisions: tuple[tuple[str, str], ...] = ()
    diagnostics: tuple[str, ...] = ("regulation_policy_unregistered",)


def project_mental_regulation(*, actor_id: str, snapshot: dict, dynamic_state: dict) -> MentalRegulationProjection:
    for source in (snapshot, dynamic_state):
        if source.get("actor_id", actor_id) != actor_id:
            raise ValueError("mental regulation source actor mismatch")
    tension = dynamic_state.get("tension_state", {})
    tension = tension if isinstance(tension, dict) else {}
    factors = []
    for key in ("distraction_level", "stress_load", "social_pressure", "masking_pressure"):
        value = dynamic_state.get(key, tension.get(key))
        if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1:
            factors.append((key, float(value)))
    affect = dynamic_state.get("affect_state", {})
    if isinstance(affect, dict):
        factors.extend((f"affect.{key}", float(value)) for key, value in sorted(affect.items())
                       if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1)
    clarity = snapshot.get("clarity_score")
    clarity = float(clarity) if isinstance(clarity, (int, float)) and not isinstance(clarity, bool) and 0 <= clarity <= 1 else None
    revisions = tuple((name, hashlib.sha256(json.dumps(source, sort_keys=True, ensure_ascii=False).encode()).hexdigest())
                      for name, source in (("l1", snapshot), ("dynamic_state", dynamic_state)) if source)
    # Only aliases with an existing source meaning are projected. Derived control
    # factors and bands await an admitted policy; no thresholds are guessed here.
    return MentalRegulationProjection(
        actor_id=actor_id, clarity=clarity, masking_load=dict(factors).get("masking_pressure"),
        source_factors=tuple(factors), source_revisions=revisions,
        goal_conflict_refs=tuple(str(ref) for ref in dynamic_state.get("unresolved_conflicts", []) if isinstance(ref, str)),
    )
