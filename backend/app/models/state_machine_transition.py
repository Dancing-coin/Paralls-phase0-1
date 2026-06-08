from pydantic import BaseModel


class StateMachineTransitionEvent(BaseModel):
    event_id: str
    event_type: str = "state_machine_transition"
    room_id: str
    scene_id: str = "scene_demo"
    zone_id: str = "zone_focus"
    entity_id: str
    machine_id: str
    from_state: str
    to_state: str
    trigger_type: str
    transition_reason: str
    producer_ts: int
    causation_id: str
    correlation_id: str = ""
