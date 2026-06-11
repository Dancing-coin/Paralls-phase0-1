from pydantic import BaseModel, Field


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
    short_horizon_social_presence: list[str] = Field(default_factory=list)
    local_spatial_confidence_map: dict[str, float] = Field(default_factory=dict)
    recent_world_changes: list[str] = Field(default_factory=list)
    recent_constraint_results: list[str] = Field(default_factory=list)
    body_state_hints: list[str] = Field(default_factory=list)
    last_siming_catalyst: str | None = None
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


class CharacterPresentationCommand(BaseModel):
    actor_id: str
    output_type: str
    producer_ts: int
    causation_id: str
    correlation_id: str
    target_actor_id: str | None = None
    target_object_id: str | None = None
    target_environment_id: str | None = None
    dialogue_text: str | None = None
    move_target: list[float] | None = None
    role_state_hint: str | None = None
    physiology_hint: str | None = None
