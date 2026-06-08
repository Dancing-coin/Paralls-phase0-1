from pydantic import BaseModel, Field


class EnvironmentRequest(BaseModel):
    request_id: str
    candidate_ref: str = ""
    decision_ref: str = ""
    room_id: str
    scene_id: str = "scene_demo"
    zone_id: str = "zone_focus"
    source: dict[str, object] = Field(default_factory=dict)
    target_entity_refs: dict[str, list[str]] = Field(default_factory=dict)
    goal: str
    requested_change_type: str
    requested_strength: str = "medium"
    ttl: int | None = None
    reason_tag: str = ""
    producer_ts: int
    causation_id: str = ""
    correlation_id: str = ""
