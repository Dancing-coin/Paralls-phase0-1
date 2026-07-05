from pydantic import BaseModel, Field


class CandidatePerceptEvent(BaseModel):
    event_type: str = "candidate_percept_event"
    percept_channel: str
    source_fact_family: str
    source_fact_type: str
    producer_ts: int
    capture_root_id: str = ""
    capture_id: str = ""
    clock_domain: str = ""
    monotonic_tick: int | None = None
    source_frame_index: int | None = None
    wall_clock_ts: int | None = None
    sample_ref_id: str = ""
    world_anchor_id: str = ""
    subject_ref: str = ""
    target_ref: str = ""
    source_ref_lineage: list[str] = Field(default_factory=list)
    room_id: str
    scene_id: str
    zone_id: str
    source_actor_id: str = ""
    source_object_id: str = ""
    source_environment_id: str = ""
    target_actor_id: str = ""
    target_object_id: str = ""
    target_environment_id: str = ""
    audience_scope: str = "candidate"
    observability: dict[str, object] = Field(default_factory=dict)
    causation_id: str = ""
    correlation_id: str = ""
