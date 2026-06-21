from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ObservatoryRecord(BaseModel):
    producer_ts: int
    causation_id: str
    correlation_id: str
    participants: list[str] = Field(default_factory=list)


class ActorDramaticState(ObservatoryRecord):
    actor_id: str
    current_intent: str
    focus_target: str
    state_label: str
    why_now_summary: str
    perception_summary: str
    memory_summary: str
    interpretation_summary: str
    decision_summary: str
    execution_summary: str
    latest_outcome_summary: str
    latest_siming_summary: str


class ActorDramaticEvent(ObservatoryRecord):
    actor_id: str
    stage: str
    summary: str
    focus_target: str
    intent_label: str
    detail: dict[str, Any] = Field(default_factory=dict)

    @property
    def event_ref(self) -> str:
        return f"{self.actor_id}:{self.stage}:{self.producer_ts}"


class SimingDramaticState(ObservatoryRecord):
    fairness_summary: str
    intervention_candidate: str
    intervention_decision: str
    selected_path: str
    intervention_band: str
    target_ref: str
    reason_summary: str
    downstream_status: str
    no_action_reason: str


class SimingDramaticEvent(ObservatoryRecord):
    stage: str
    summary: str
    selected_path: str
    intervention_band: str
    target_ref: str
    reason_summary: str
    downstream_status: str
    no_action_reason: str

    @property
    def event_ref(self) -> str:
        return f"siming:{self.stage}:{self.producer_ts}"


class WorldOutcomeEvent(ObservatoryRecord):
    actor_id: str
    target_ref: str
    request_type: str
    settlement_status: str
    constraint_summary: str
    world_change_summary: str
    dramatic_consequence_summary: str
    source_message_type: str
    detail: dict[str, Any] = Field(default_factory=dict)

    @property
    def event_ref(self) -> str:
        return f"world:{self.target_ref}:{self.producer_ts}"


class ScriptBeat(ObservatoryRecord):
    beat_id: str
    dramatic_summary: str
    actor_event_refs: list[str] = Field(default_factory=list)
    siming_event_refs: list[str] = Field(default_factory=list)
    world_event_refs: list[str] = Field(default_factory=list)
