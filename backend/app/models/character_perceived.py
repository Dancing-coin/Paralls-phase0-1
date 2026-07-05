from pydantic import BaseModel, Field


class CharacterPerceivedEvent(BaseModel):
    event_type: str = "character_perceived_event"
    actor_id: str
    percept_channel: str
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
    perceived_summary: str
    source_candidate_event_id: str
    source_actor_id: str = ""
    target_actor_id: str = ""
    target_object_id: str = ""
    target_environment_id: str = ""
    distance_m: float | None = None
    clarity_score: float = 1.0
    certainty_score: float = 1.0
