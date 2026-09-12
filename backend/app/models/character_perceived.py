from pydantic import BaseModel, Field, model_validator

from app.character_agent.models.memory_consistency import MemoryFactClaim


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
    fact_claim: MemoryFactClaim | None = None

    @model_validator(mode="after")
    def validate_memory_evidence(self):
        if self.fact_claim is not None:
            if self.fact_claim.source_ref not in {self.source_candidate_event_id, *self.source_ref_lineage}:
                raise ValueError("fact claim must reference the received evidence")
            if self.fact_claim.valid_at > self.producer_ts:
                raise ValueError("future fact cannot be received evidence")
            if self.fact_claim.subject_ref not in {self.target_ref, self.target_object_id, self.target_actor_id, self.target_environment_id}:
                raise ValueError("fact claim must match the perceived target")
        return self
