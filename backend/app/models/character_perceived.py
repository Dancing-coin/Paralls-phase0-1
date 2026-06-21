from pydantic import BaseModel


class CharacterPerceivedEvent(BaseModel):
    event_type: str = "character_perceived_event"
    actor_id: str
    percept_channel: str
    producer_ts: int
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
