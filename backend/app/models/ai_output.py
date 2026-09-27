from pydantic import BaseModel, Field

from app.models.dialogue_audio import DialogueAudio


class AIOutputBase(BaseModel):
    actor_id: str
    room_id: str
    output_type: str
    causation_id: str
    correlation_id: str = ""
    producer_ts: int


class DialogueResponse(AIOutputBase):
    output_type: str = "dialogue_response"
    target_actor_id: str
    content: str
    tone: str
    tts_required: bool = True
    audio: DialogueAudio | None = None
    request_id: str | None = None
    turn_id: str = ""
    idempotency_key: str = ""
    expected_revision_vector: dict[str, int] = Field(default_factory=dict)
    expected_memory_revision_vector: dict[str, int] = Field(default_factory=dict)
    expected_snapshot_revision: int = 0


class AttentionShift(AIOutputBase):
    output_type: str = "attention_shift"
    target_actor_id: str | None = None
    target_object_id: str | None = None
    attention_reason: str


class InteractionReaction(AIOutputBase):
    output_type: str = "interaction_reaction"
    target_object_id: str | None = None
    target_environment_id: str | None = None
    reaction_type: str
    reaction_text: str | None = None


class SimingHookSignal(AIOutputBase):
    output_type: str = "siming_hook_signal"
    signal_type: str
    signal_strength: str
    summary: str
