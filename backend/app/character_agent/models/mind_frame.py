from __future__ import annotations

import hashlib
import json
from types import MappingProxyType
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator


from app.character_agent.models.turn_context import CharacterTurnContext


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
    turn_id: str = ""
    branch_id: str | None = None
    input_revision_vector: Mapping[str, int] = Field(default_factory=dict)
    memory_revision_vector: Mapping[str, int] = Field(default_factory=dict)
    policy_revision: str = ""
    snapshot_revision: int = 0
    frame_digest: str = ""
    source_refs: tuple[str, ...] = ()

    @field_validator("input_revision_vector", "memory_revision_vector", mode="after")
    @classmethod
    def freeze_frame_revision_vectors(cls, value: Mapping[str, int]) -> Mapping[str, int]:
        if any(revision < 0 for revision in value.values()):
            raise ValueError("mind frame revisions must be non-negative")
        return MappingProxyType(dict(value))

    @field_serializer("input_revision_vector", "memory_revision_vector")
    def serialize_frame_revision_vectors(self, value: Mapping[str, int]) -> dict[str, int]:
        return dict(value)

    @field_validator("source_refs", mode="before")
    @classmethod
    def normalize_source_refs(cls, value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        return tuple(str(ref) for ref in value)  # type: ignore[arg-type]


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

    def _content_digest(self) -> str:
        payload = self.model_dump(mode="json", exclude={"frame_digest"})
        return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()

    def bind_to_turn(self, turn: CharacterTurnContext) -> "CharacterMindFrame":
        """Bind once; later consumers must validate the original content and pins."""
        if self.actor_id != turn.actor_id:
            raise ValueError("mind frame actor mismatch")
        if self.turn_id:
            self.validate_turn(turn)
            return self
        bound = self.model_copy(update={
            "turn_id": turn.turn_id,
            "branch_id": turn.branch_id,
            "input_revision_vector": MappingProxyType(dict(turn.input_revision_vector)),
            "memory_revision_vector": MappingProxyType(dict(turn.memory_revision_vector)),
            "policy_revision": turn.policy_revision,
            "snapshot_revision": turn.snapshot_revision,
            "source_refs": tuple(sorted(set(self.provenance.source_refs))),
        })
        return bound.model_copy(update={"frame_digest": bound._content_digest()})

    def validate_turn(self, turn: CharacterTurnContext) -> None:
        if not self.turn_id:
            raise ValueError("mind frame is not bound to a turn")
        if self.actor_id != turn.actor_id:
            raise ValueError("mind frame actor mismatch")
        if self.turn_id != turn.turn_id:
            raise ValueError("mind frame turn mismatch")
        if self.branch_id != turn.branch_id:
            raise ValueError("mind frame branch mismatch")
        if dict(self.input_revision_vector) != dict(turn.input_revision_vector):
            raise ValueError("mind frame input revision mismatch")
        if dict(self.memory_revision_vector) != dict(turn.memory_revision_vector):
            raise ValueError("mind frame memory revision mismatch")
        if self.policy_revision != turn.policy_revision or self.snapshot_revision != turn.snapshot_revision:
            raise ValueError("mind frame revision mismatch")
        if not self.frame_digest or self.frame_digest != self._content_digest():
            raise ValueError("mind frame digest mismatch")


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
