from typing import Literal

from pydantic import BaseModel, Field

CHARACTER_ACTOR_AUTONOMY_MODES = (
    "human_controlled",
    "agent_controlled",
    "idle_autonomous",
    "away_conservative_takeover",
    "scripted_test",
)

CHARACTER_AGENT_CONTROL_MODES = (
    "agent_full_auto",
    "player_priority_assisted",
    "away_conservative_takeover",
    "scripted_override",
)

SHARED_CHARACTER_COMMANDS = (
    "look_at",
    "go_to",
    "approach",
    "observe",
    "interact",
    "speak",
)


class CharacterPrivateWorldSnapshot(BaseModel):
    actor_id: str
    room_id: str
    scene_id: str
    zone_id: str
    producer_ts: int
    visible_entities: list[str] = Field(default_factory=list)
    audible_entities: list[str] = Field(default_factory=list)
    unresolved_signals: list[str] = Field(default_factory=list)
    active_anomalies: list[str] = Field(default_factory=list)
    attention_targets: list[str] = Field(default_factory=list)
    current_attention_targets: list[str] = Field(default_factory=list)
    short_horizon_social_presence: list[str] = Field(default_factory=list)
    local_spatial_confidence_map: dict[str, float] = Field(default_factory=dict)
    recent_world_changes: list[str] = Field(default_factory=list)
    recent_constraint_results: list[str] = Field(default_factory=list)
    body_state_hints: list[str] = Field(default_factory=list)
    last_siming_catalyst: str | None = None
    vigilance_level: str = "baseline"
    distraction_level: str = "baseline"
    bias_tags: list[str] = Field(default_factory=list)
    clarity_score: float = 1.0
    certainty_score: float = 1.0
    updated_at: int


class CharacterInterpretation(BaseModel):
    actor_id: str
    interpreted_summary: str
    interpretation_type: str
    salience_score: float
    ambiguity_level: str
    risk_level: str
    opportunity_level: str
    attention_target: str | None = None
    inner_prompt_candidate: str | None = None


class CharacterIntentDecision(BaseModel):
    actor_id: str
    selected_intent: str
    persona_passed: bool
    logic_passed: bool
    gain_loss_passed: bool
    rationale: str


class CharacterSuggestionPacket(BaseModel):
    actor_id: str
    control_mode: Literal["player_priority_assisted"]
    producer_ts: int
    causation_id: str
    correlation_id: str
    recommended_intents: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    urge_vector: str = ""
    social_read: str = ""
    why_this_now: str = ""
    role_consistency_hint: str = ""


class CharacterGoalCommand(BaseModel):
    actor_id: str
    command_type: Literal["look_at", "go_to", "approach", "observe", "interact", "speak"]
    ttl_ms: int
    causation_id: str
    correlation_id: str
    producer_ts: int | None = None
    target_actor_id: str | None = None
    target_object_id: str | None = None
    target_environment_id: str | None = None
    target_position: list[float] | None = None
    dialogue_text: str | None = None
    role_state_hint: str | None = None
    physiology_hint: str | None = None


class CharacterIntentFrame(BaseModel):
    actor_id: str
    controller_source: Literal["human", "agent", "scripted"]
    ttl_ms: int
    causation_id: str
    correlation_id: str
    move_local: list[float] | None = None
    look_local: list[float] | None = None
    gait: str | None = None
    stance: str | None = None
    action: str | None = None
