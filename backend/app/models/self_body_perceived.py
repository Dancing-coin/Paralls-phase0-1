from pydantic import BaseModel


class SelfBodyPerceivedEvent(BaseModel):
    event_type: str = "self_body_perceived_event"
    actor_id: str
    body_state_class: str
    producer_ts: int
    room_id: str
    scene_id: str
    zone_id: str
    perceived_summary: str
    source_body_result_id: str

