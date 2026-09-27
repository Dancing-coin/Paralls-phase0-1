from pydantic import BaseModel, Field


class ActionRequest(BaseModel):
    request_id: str
    request_type: str
    room_id: str
    scene_id: str
    zone_id: str
    actor_id: str
    action_type: str
    source: dict[str, object] = Field(default_factory=dict)
    target_entity_refs: dict[str, list[str]] = Field(default_factory=dict)
    action_profile: str = ""
    intent_strength: str = "normal"
    constraints_hint: dict[str, object] = Field(default_factory=dict)
    producer_ts: int = 0
    causation_id: str = ""
    correlation_id: str = ""
    turn_id: str = ""
    idempotency_key: str = ""
    expected_revision_vector: dict[str, int] = Field(default_factory=dict)
    expected_memory_revision_vector: dict[str, int] = Field(default_factory=dict)
    expected_snapshot_revision: int = 0
    target_actor_id: str = ""
    target_object_id: str = ""
    target_environment_id: str = ""
    payload: dict[str, object] = Field(default_factory=dict)
