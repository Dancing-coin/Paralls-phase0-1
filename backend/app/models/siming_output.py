from pydantic import BaseModel


class SimingOutputBase(BaseModel):
    room_id: str
    output_type: str
    causation_id: str
    producer_ts: int
    target_actor_id: str | None = None
    target_environment_id: str | None = None


class NarrativeNudge(SimingOutputBase):
    output_type: str = "narrative_nudge"
    nudge_summary: str
    nudge_intensity: str


class AttentionPrompt(SimingOutputBase):
    output_type: str = "attention_prompt"
    target_object_id: str | None = None
    prompt_summary: str


class SituationShift(SimingOutputBase):
    output_type: str = "situation_shift"
    shift_summary: str
    expected_effect: str
