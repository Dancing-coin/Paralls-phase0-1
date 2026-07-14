from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


MindFactorLayer = Literal[
    "enduring_truth",
    "memory_evidence",
    "runtime_state",
    "affordance",
    "cognition_process",
    "writeback_learning",
]

_FACTOR_LAYER_OWNERSHIP: dict[str, str] = {
    "effective_profile": "enduring_truth",
    "authored_constraint": "enduring_truth",
    "personality_bias": "enduring_truth",
    "identity_context": "enduring_truth",
    "embodiment_context": "enduring_truth",
    "authority_context": "enduring_truth",
    "private_truth_context": "enduring_truth",
    "dossier_hot_reload": "enduring_truth",
    "memory_activation": "memory_evidence",
    "cognitive_anchor": "memory_evidence",
    "relationship": "memory_evidence",
    "relationship_context": "memory_evidence",
    "knowledge_context": "memory_evidence",
    "higher_order_belief": "memory_evidence",
    "relationship_seed_context": "memory_evidence",
    "perception_context": "runtime_state",
    "need_pressure": "runtime_state",
    "affective_body_state": "runtime_state",
    "goal_context": "runtime_state",
    "unresolved_tension": "runtime_state",
    "supervision": "runtime_state",
    "skill_affordance": "affordance",
    "action_affordance": "affordance",
    "relationship_affordance": "affordance",
    "environment_affordance": "affordance",
    "equipment_affordance": "affordance",
    "physical_feasibility": "affordance",
    "capability_seed_affordance": "affordance",
}


class StrictMindFrameModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MentalFactorProjectionCard(StrictMindFrameModel):
    factor_type: str
    layer: MindFactorLayer
    scope: Literal["actor_private", "public", "system", "scenario"] = "actor_private"
    horizon: Literal["instant", "scene", "arc", "long_term"] = "scene"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    freshness: Literal["current", "recent", "stale", "unknown"] = "unknown"
    summary: str
    payload: dict[str, object] = Field(default_factory=dict)
    source_refs: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_factor_layer(self) -> MentalFactorProjectionCard:
        expected_layer = _FACTOR_LAYER_OWNERSHIP.get(self.factor_type)
        if expected_layer is None:
            raise ValueError(f"Unsupported factor_type {self.factor_type!r}")
        if self.layer != expected_layer:
            raise ValueError(
                f"factor_type {self.factor_type!r} must use layer {expected_layer!r}"
            )
        return self


class MindFrameLayer(StrictMindFrameModel):
    cards: list[MentalFactorProjectionCard] = Field(default_factory=list)
    summary: dict[str, object] = Field(default_factory=dict)


class CharacterMindFrameTrigger(StrictMindFrameModel):
    event_id: str = ""
    event_type: str = ""
    source_stage: str = ""


class MindFrameProvenance(StrictMindFrameModel):
    source_refs: list[str] = Field(default_factory=list)
    builder_version: str = "mind_frame_builder.v1"


class CognitionWorkspace(StrictMindFrameModel):
    active_anchors: list[str] = Field(default_factory=list)
    dominant_drivers: list[str] = Field(default_factory=list)
    active_conflicts: list[str] = Field(default_factory=list)
    decision_biases: list[str] = Field(default_factory=list)
    hard_constraints: list[str] = Field(default_factory=list)
    candidate_questions: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class CharacterMindFrame(StrictMindFrameModel):
    actor_id: str
    mind_turn_id: str
    producer_ts: int = 0
    trigger: CharacterMindFrameTrigger = Field(default_factory=CharacterMindFrameTrigger)
    enduring_truth: MindFrameLayer = Field(default_factory=MindFrameLayer)
    memory_evidence: MindFrameLayer = Field(default_factory=MindFrameLayer)
    runtime_state: MindFrameLayer = Field(default_factory=MindFrameLayer)
    affordances: MindFrameLayer = Field(default_factory=MindFrameLayer)
    cognition_workspace: CognitionWorkspace = Field(default_factory=CognitionWorkspace)
    provenance: MindFrameProvenance = Field(default_factory=MindFrameProvenance)

    @model_validator(mode="after")
    def validate_layer_buckets(self) -> CharacterMindFrame:
        bucket_layers = {
            "enduring_truth": "enduring_truth",
            "memory_evidence": "memory_evidence",
            "runtime_state": "runtime_state",
            "affordances": "affordance",
        }
        for bucket_name, expected_layer in bucket_layers.items():
            bucket = getattr(self, bucket_name)
            for card in bucket.cards:
                if card.layer != expected_layer:
                    raise ValueError(
                        f"{bucket_name} accepts only {expected_layer!r} cards; "
                        f"got {card.factor_type!r} on {card.layer!r}"
                    )
        return self


class L2InterpretationView(StrictMindFrameModel):
    actor_id: str
    mind_turn_id: str
    perception_context: dict[str, object] = Field(default_factory=dict)
    effective_profile_summary: dict[str, object] = Field(default_factory=dict)
    personality_bias_summary: dict[str, object] = Field(default_factory=dict)
    memory_activation_summary: dict[str, object] = Field(default_factory=dict)
    cognitive_anchor_summary: dict[str, object] = Field(default_factory=dict)
    relationship_context_summary: dict[str, object] = Field(default_factory=dict)
    need_pressure_summary: dict[str, object] = Field(default_factory=dict)
    affective_body_summary: dict[str, object] = Field(default_factory=dict)
    goal_context_summary: dict[str, object] = Field(default_factory=dict)
    unresolved_tension_summary: dict[str, object] = Field(default_factory=dict)
    supervision_summary: dict[str, object] = Field(default_factory=dict)
    dossier_context_summary: dict[str, object] = Field(default_factory=dict)


class L3PlanningView(StrictMindFrameModel):
    actor_id: str
    mind_turn_id: str
    interpretation_summary: dict[str, object] = Field(default_factory=dict)
    cognition_workspace: CognitionWorkspace = Field(default_factory=CognitionWorkspace)
    goal_context_summary: dict[str, object] = Field(default_factory=dict)
    need_pressure_summary: dict[str, object] = Field(default_factory=dict)
    affective_body_summary: dict[str, object] = Field(default_factory=dict)
    skill_affordance_summary: dict[str, object] = Field(default_factory=dict)
    action_affordance_summary: dict[str, object] = Field(default_factory=dict)
    relationship_affordance_summary: dict[str, object] = Field(default_factory=dict)
    hard_constraints: list[str] = Field(default_factory=list)
    unresolved_tension_summary: dict[str, object] = Field(default_factory=dict)
    supervision_summary: dict[str, object] = Field(default_factory=dict)
    dossier_planning_summary: dict[str, object] = Field(default_factory=dict)


class L4ExecutionView(StrictMindFrameModel):
    actor_id: str
    mind_turn_id: str
    selected_intent: str = ""
    selected_skill_path: dict[str, object] = Field(default_factory=dict)
    target_refs: dict[str, str] = Field(default_factory=dict)
    affective_body_summary: dict[str, object] = Field(default_factory=dict)
    presentation_constraints: list[str] = Field(default_factory=list)
    realization_hints: list[str] = Field(default_factory=list)
    physical_feasibility_summary: dict[str, object] = Field(default_factory=dict)
    dossier_execution_constraints: dict[str, object] = Field(default_factory=dict)


class WritebackView(StrictMindFrameModel):
    actor_id: str
    mind_turn_id: str
    l2_deltas: dict[str, object] = Field(default_factory=dict)
    l3_decision: dict[str, object] = Field(default_factory=dict)
    l4_execution_proposal: dict[str, object] = Field(default_factory=dict)
    settlement_result: dict[str, object] = Field(default_factory=dict)
    dialogue_or_action_outcome: dict[str, object] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)


class MindDeltaLedger(StrictMindFrameModel):
    actor_id: str
    mind_turn_id: str
    belief_deltas: list[dict[str, object]] = Field(default_factory=list)
    social_deltas: list[dict[str, object]] = Field(default_factory=list)
    higher_order_deltas: list[dict[str, object]] = Field(default_factory=list)
    dynamic_state_deltas: dict[str, object] = Field(default_factory=dict)
    need_tension_deltas: dict[str, object] = Field(default_factory=dict)
    goal_deltas: list[dict[str, object]] = Field(default_factory=list)
    skill_evidence_deltas: list[dict[str, object]] = Field(default_factory=list)
    memory_write_candidates: list[dict[str, object]] = Field(default_factory=list)
    relationship_update_candidates: list[dict[str, object]] = Field(default_factory=list)
    drift_candidates: list[dict[str, object]] = Field(default_factory=list)
