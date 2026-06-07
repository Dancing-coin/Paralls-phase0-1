from pydantic import BaseModel, Field


class CandidatePerceptEvent(BaseModel):
    event_type: str = "candidate_percept_event"
    percept_channel: str
    source_fact_family: str
    source_fact_type: str
    producer_ts: int
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
