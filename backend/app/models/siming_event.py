from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.authority_event import AuthorityEvent


SimingInputType = Literal[
    "world_fact_event",
    "visual_fact_event",
    "esm_result_event",
    "character_behavior_event",
    "conversation_resolution_event",
    "constraint_state_event",
]

SimingOutputType = Literal[
    "fairness_snapshot",
    "intervention_candidate",
    "intervention_decision",
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
]


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
