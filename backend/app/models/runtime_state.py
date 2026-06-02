from pydantic import BaseModel, Field


class ConversationCandidateEvent(BaseModel):
    actor_id: str
    room_id: str
    scene_id: str
    zone_id: str
    producer_ts: int
    candidate_actor_ids: list[str] = Field(default_factory=list)
    candidate_object_ids: list[str] = Field(default_factory=list)
    candidate_environment_ids: list[str] = Field(default_factory=list)
    engagement_pressure: str
    privacy_risk_hint: str
    causation_id: str
    correlation_id: str


class CharacterRuntimeStateSnapshot(BaseModel):
    actor_id: str
    room_id: str
    scene_id: str
    zone_id: str
    revision_seq: int
    producer_ts: int
    current_focus_target: str | None = None
    current_attention_source: str | None = None
    nearby_actor_refs: list[str] = Field(default_factory=list)
    nearby_object_refs: list[str] = Field(default_factory=list)
    nearby_environment_refs: list[str] = Field(default_factory=list)
    conversation_candidate_refs: list[str] = Field(default_factory=list)
    engagement_pressure: str | None = None
    privacy_risk_hint: str | None = None
    updated_at: int


class CharacterRuntimeStateDelta(BaseModel):
    actor_id: str
    room_id: str
    scene_id: str
    zone_id: str
    revision_seq: int
    producer_ts: int
    changed_fields: list[str]
    current_focus_target: str | None = None
    current_attention_source: str | None = None
    nearby_actor_refs: list[str] | None = None
    nearby_object_refs: list[str] | None = None
    nearby_environment_refs: list[str] | None = None
    conversation_candidate_refs: list[str] | None = None
    engagement_pressure: str | None = None
    privacy_risk_hint: str | None = None
    updated_at: int
