from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


NarrativePhase = Literal["setup", "rising", "pressure", "resolution"]
PressureLevel = Literal["low", "normal", "elevated", "critical"]
ObligationStatus = Literal["open", "closed"]
QualitySeverity = Literal["ok", "low", "medium", "high", "unavailable", "partial"]


class NarrativeMarker(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marker_id: str
    marker_type: str
    source_event_id: str
    target_refs: list[str] = Field(default_factory=list)
    reason: str


class NarrativeThread(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thread_id: str
    thread_type: str
    status: str
    target_refs: list[str] = Field(default_factory=list)


class NarrativeStateSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    schema_version: int = 1
    producer_system: str = "siming.narrative_core"
    room_id: str
    scene_id: str
    zone_id: str
    world_ts: int
    sim_tick_ts: int
    active_phase: NarrativePhase
    pressure_level: PressureLevel
    open_threads: list[NarrativeThread] = Field(default_factory=list)
    active_markers: list[NarrativeMarker] = Field(default_factory=list)
    causation_id: str
    correlation_id: str


class NarrativeObligation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    obligation_id: str
    obligation_type: str
    source_event_id: str
    target_refs: list[str] = Field(default_factory=list)
    pressure: PressureLevel
    status: ObligationStatus = "open"
    reason: str


class NarrativeObligationLedger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ledger_id: str
    schema_version: int = 1
    producer_system: str = "siming.narrative_core"
    room_id: str
    world_ts: int
    sim_tick_ts: int
    obligations: list[NarrativeObligation] = Field(default_factory=list)
    causation_id: str
    correlation_id: str


class InterventionSeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seed_id: str
    seed_type: str
    basis_snapshot_ref: str
    basis_obligation_refs: list[str] = Field(default_factory=list)
    target_refs: list[str] = Field(default_factory=list)
    suggested_band: str
    risk_tags: list[str] = Field(default_factory=list)
    explanation: str
    source: str = "narrative_core"


class QualitySignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal_id: str
    dimension: str
    severity: QualitySeverity
    target_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    suggested_action_band: str
    reason: str


class NarrativeCoreResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: NarrativeStateSnapshot
    ledger: NarrativeObligationLedger
    seeds: list[InterventionSeed] = Field(default_factory=list)
