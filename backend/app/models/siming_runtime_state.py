from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.authority_event import AuthorityEvent


StateAuthority = Literal["mirror", "editable", "read_only"]
NodeStatus = Literal["fresh", "partial", "stale", "unavailable"]
MarkerStatus = Literal["active", "stalled", "overheated", "resolved"]
ObligationStatus = Literal["open", "closed", "reopened"]
CheckpointType = Literal[
    "fairness_before",
    "fairness_after",
    "pre_decision",
    "post_decision",
    "post_dispatch",
]


class ObservedSimingEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_event_id: str
    event_type: str
    room_id: str
    scene_id: str
    zone_id: str
    producer_ts: int
    causation_id: str
    correlation_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    authority_event: AuthorityEvent

    @classmethod
    def from_authority_event(cls, event: AuthorityEvent) -> "ObservedSimingEvent":
        return cls(
            source_event_id=event.event_id,
            event_type=event.event_type,
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            producer_ts=event.producer_ts,
            causation_id=event.causation_id,
            correlation_id=event.correlation_id,
            payload=event.payload,
            authority_event=event,
        )


class StateTreeNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    owner_system: str
    authority: StateAuthority
    status: NodeStatus
    summary: dict[str, Any] = Field(default_factory=dict)


class GroupSimulationBranchSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: NodeStatus
    summary: dict[str, Any] = Field(default_factory=dict)


class StateTreeSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    schema_version: int
    producer_system: str
    room_id: str
    scene_id: str
    zone_id: str
    world_ts: int
    sim_tick_ts: int
    causation_id: str
    correlation_id: str
    environment: StateTreeNode
    character: StateTreeNode
    storyline: StateTreeNode
    group_simulation: GroupSimulationBranchSnapshot

    @model_validator(mode="after")
    def validate_mirror_authority_branches(self) -> "StateTreeSnapshot":
        if self.environment.authority != "mirror" or self.character.authority != "mirror":
            raise ValueError("environment and character branches must be mirror authority")
        return self


class StorylineMarker(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marker_id: str
    marker_type: str
    status: MarkerStatus
    entity_refs: list[str] = Field(default_factory=list)
    reason: str


class StorylineStateSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    schema_version: int
    producer_system: str
    room_id: str
    world_ts: int
    sim_tick_ts: int
    causation_id: str
    correlation_id: str
    active_phase: str
    markers: list[StorylineMarker] = Field(default_factory=list)


class NarrativeObligation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    obligation_id: str
    source_ref: str
    obligation_type: str
    status: ObligationStatus
    reason: str


class NarrativeObligationLedgerSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ledger_id: str
    schema_version: int
    producer_system: str
    room_id: str
    world_ts: int
    sim_tick_ts: int
    causation_id: str
    correlation_id: str
    obligations: list[NarrativeObligation] = Field(default_factory=list)


class FairnessDimensionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension_id: str
    status: NodeStatus
    score: float
    reason: str
    mapped_to_policy: bool


class ProjectionRunSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projection_id: str
    schema_version: int
    producer_system: str
    room_id: str
    world_ts: int
    sim_tick_ts: int
    causation_id: str
    correlation_id: str
    status: NodeStatus | None = None
    branch_status: NodeStatus | None = None
    basis_state_tree_ref: str | None = None
    basis_fairness_snapshot_ref: str | None = None
    candidate_hints: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_projection_status(self) -> "ProjectionRunSnapshot":
        if self.status is None and self.branch_status is None:
            raise ValueError("status or branch_status is required")
        if (
            self.status is not None
            and self.branch_status is not None
            and self.status != self.branch_status
        ):
            raise ValueError("status and branch_status must match when both are provided")
        resolved_status = self.status or self.branch_status
        self.status = resolved_status
        self.branch_status = resolved_status
        return self


class SimingCheckpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checkpoint_id: str
    schema_version: int
    room_id: str
    world_ts: int
    sim_tick_ts: int
    checkpoint_type: CheckpointType
    fairness_snapshot_ref: str | None = None
    state_tree_snapshot_ref: str | None = None
    storyline_snapshot_ref: str | None = None
    causation_id: str
    correlation_id: str


class NarrativeReadModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    read_model_id: str
    schema_version: int
    producer_system: str
    room_id: str
    scene_scope: str
    world_ts: int
    sim_tick_ts: int
    current_state: dict[str, Any] = Field(default_factory=dict)
    focus_entities: list[str] = Field(default_factory=list)
    intervention_surface: dict[str, Any] = Field(default_factory=dict)
    narrative_surface: dict[str, Any] = Field(default_factory=dict)
    derived_from_snapshot_ref: str | None = None
