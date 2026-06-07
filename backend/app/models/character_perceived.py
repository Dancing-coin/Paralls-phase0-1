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
