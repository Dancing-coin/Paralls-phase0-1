from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.authority_event import AuthorityEvent
from app.models.siming_runtime_state import (
    FairnessDimensionSnapshot,
    NarrativeReadModel,
    SimingCheckpoint,
)


SimingInputType = Literal[
    "world_fact_event",
    "visual_fact_event",
    "esm_result_event",
    "character_behavior_event",
    "conversation_resolution_event",
    "constraint_state_event",
    "siming_staging_ack",
    "population_cadence_input",
]

SimingOutputType = Literal[
    "fairness_snapshot",
    "intervention_candidate",
    "intervention_decision",
    "staging_request",
    "dispatch_intent",
    "audit_record",
    "no_action",
]

SelectedPath = Literal[
    "character_input_path",
    "environment_change_path",
    "visual_fact_path",
    "l3_highlight_path",
    "no_action",
]

InterventionBand = Literal[
    "impulse",
    "opportunity",
    "fact_reveal",
    "environment_request",
    "none",
]

CandidateSource = Literal["rule", "llm", "fallback"]

AuditStatus = Literal[
    "recorded",
    "no_action",
    "duplicate_suppressed",
    "stale_candidate",
    "dispatch_timeout",
    "partial_target_delivery",
    "esm_rejected",
    "expired_ttl",
    "late_input",
    "late_result_correction",
    "degraded",
    "llm_timeout",
    "llm_invalid_output",
    "policy_rejected",
    "feasibility_rejected",
    "unknown_effect",
    "ack_timeout",
]


class FairnessStateSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    room_id: str
    scene_id: str
    zone_id: str
    causation_id: str
    correlation_id: str
    known_fact_ids: list[str] = Field(default_factory=list)
    eligible_actor_ids: list[str] = Field(default_factory=list)
    blocked_actor_ids: list[str] = Field(default_factory=list)
    recent_intervention_ids: list[str] = Field(default_factory=list)
    dimensions: dict[str, FairnessDimensionSnapshot] = Field(default_factory=dict)


class InterventionCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    room_id: str
    scene_id: str
    zone_id: str
    causation_id: str
    correlation_id: str
    proposed_band: InterventionBand
    target_actor_id: str | None = None
    target_object_id: str | None = None
    target_environment_id: str | None = None
    established_fact_ids: list[str] = Field(default_factory=list)
    explanation: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason_tags: list[str] = Field(default_factory=list)
    source: CandidateSource = "rule"

    @model_validator(mode="before")
    @classmethod
    def reject_forbidden_candidate_fields(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        forbidden = {
            "authority_event",
            "event_type",
            "intervention_decision",
            "selected_path",
            "physical_success",
            "role_belief_truth",
            "esm_state_mutation",
            "character_low_level_command",
        }
        present = sorted(forbidden.intersection(value.keys()))
        if present:
            raise ValueError(
                f"forbidden Siming candidate field(s): {', '.join(present)}"
            )
        return value


class InterventionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_id: str
    candidate_id: str
    room_id: str
    scene_id: str
    zone_id: str
    causation_id: str
    correlation_id: str
    selected_path: SelectedPath
    intervention_band: InterventionBand
    accepted: bool
    policy_reasons: list[str] = Field(default_factory=list)
    feasibility_reasons: list[str] = Field(default_factory=list)


class SimingInput(BaseModel):
    input_type: SimingInputType
    source_event: AuthorityEvent


class SimingOutput(BaseModel):
    output_type: SimingOutputType
    room_id: str
    scene_id: str
    zone_id: str
    causation_id: str
    correlation_id: str
    producer_ts: int
    selected_path: SelectedPath | None = None
    intervention_band: InterventionBand | None = None
    priority: str = "p2"
    ttl: int | None = 5000
    durability: str = "replayable"
    payload: dict[str, Any] = Field(default_factory=dict)


class SimingAuditCorrection(BaseModel):
    correction_id: str
    status: AuditStatus
    reason: str
    causation_id: str
    producer_ts: int


class SimingAuditRecord(BaseModel):
    audit_id: str
    room_id: str
    correlation_id: str
    causation_id: str
    source_event_id: str
    status: AuditStatus
    reason: str
    dispatch_event_id: str | None = None
    correction_records: list[SimingAuditCorrection] = Field(default_factory=list)


class SimingTickResult(BaseModel):
    outputs: list[SimingOutput] = Field(default_factory=list)
    audit_records: list[SimingAuditRecord] = Field(default_factory=list)
    checkpoints: list[SimingCheckpoint] = Field(default_factory=list)
    read_model: NarrativeReadModel | None = None
