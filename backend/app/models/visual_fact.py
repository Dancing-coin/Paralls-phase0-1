from pydantic import BaseModel


class VisualFactEvent(BaseModel):
    actor_id: str
    room_id: str
    scene_id: str
    zone_id: str
    producer_ts: int
    fact_type: str
    relation_type: str
    target_actor_id: str | None = None
    target_object_id: str | None = None
    target_environment_id: str | None = None
