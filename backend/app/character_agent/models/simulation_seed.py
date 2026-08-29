from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from app.population_continuity.models import ContinuityModel


MemoryCandidateKind = Literal[
    "event_experience", "perceptual_observation", "factual_knowledge", "social_impression", "higher_order_belief"
]


class CharacterMemoryCandidate(ContinuityModel):
    candidate_id: str = Field(min_length=1)
    actor_ref: str = Field(min_length=1)
    candidate_kind: MemoryCandidateKind
    source_event_refs: tuple[str, ...] = Field(min_length=1)
    event_valid_at: int = Field(ge=0)
    event_recorded_at: int = Field(default=0, ge=0)
    knowledge_available_at: int = Field(ge=0)
    exposure_basis: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    salience: float = Field(ge=0.0, le=1.0)
    visibility_scope: str = Field(min_length=1)
    privacy_disposition: str = Field(min_length=1)
    materialization_policy: str = Field(min_length=1)
    dedup_key: str = Field(min_length=1)
    source_revision_vector: dict[str, int] = Field(default_factory=dict)


class CharacterSimulationSeedCandidate(ContinuityModel):
    seed_id: str = Field(min_length=1)
    actor_ref: str = Field(min_length=1)
    world_ref: str = Field(min_length=1)
    from_tick: int = Field(ge=0)
    to_tick: int = Field(ge=0)
    source_event_refs: tuple[str, ...] = ()
    source_owner_receipt_refs: tuple[str, ...] = ()
    state_deltas: dict[str, Any] = Field(default_factory=dict)
    memory_candidates: tuple[CharacterMemoryCandidate, ...] = ()
    drift_candidates: tuple[dict[str, Any], ...] = ()
    activation_hints: tuple[str, ...] = ()
    presentation_seed: dict[str, Any] = Field(default_factory=dict)
    visibility_scope: str = Field(min_length=1)
    privacy_disposition: str = Field(min_length=1)
    source_revision_vector: dict[str, int] = Field(default_factory=dict)
    ruleset_revision: str = Field(min_length=1)
    selector_revision: str = Field(min_length=1)
    deterministic_seed: str = Field(min_length=1)
    owner_effect_status: Literal["not_required", "owner_settlement_required", "settled", "rejected"]
    materialization_status: Literal["pending", "committed", "rejected"] = "pending"
    idempotency_key: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_seed(self) -> "CharacterSimulationSeedCandidate":
        if self.to_tick < self.from_tick:
            raise ValueError("seed_tick_range_invalid")
        if len(set(self.source_owner_receipt_refs)) != len(self.source_owner_receipt_refs):
            raise ValueError("seed_owner_receipt_duplicate")
        return self


class CharacterContinuityCommand(ContinuityModel):
    command_id: str = Field(min_length=1)
    actor_ref: str = Field(min_length=1)
    source_owner_receipt_refs: tuple[str, ...] = ()
    expected_character_revision: int = Field(ge=0)
    source_revision_vector: dict[str, int] = Field(default_factory=dict)
    state_delta: dict[str, Any] = Field(default_factory=dict)
    memory_candidate_refs: tuple[str, ...] = ()
    exposure_evidence: dict[str, Any] = Field(default_factory=dict)
    policy_revision: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    world_effect_required: bool = False

    @model_validator(mode="after")
    def validate_command(self) -> "CharacterContinuityCommand":
        if len(set(self.source_owner_receipt_refs)) != len(self.source_owner_receipt_refs):
            raise ValueError("command_owner_receipt_duplicate")
        if len(set(self.memory_candidate_refs)) != len(self.memory_candidate_refs):
            raise ValueError("command_memory_candidate_duplicate")
        if self.world_effect_required and not self.source_owner_receipt_refs:
            raise ValueError("owner_settlement_required")
        return self


class CharacterContinuityReceipt(ContinuityModel):
    receipt_ref: str = Field(min_length=1)
    command_id: str = Field(min_length=1)
    actor_ref: str = Field(min_length=1)
    status: Literal["committed", "rejected", "requeued", "idempotent_replay"]
    character_revision_before: int = Field(ge=0)
    character_revision_after: int = Field(ge=0)
    applied_state_digest: str = ""
    seed_delta_refs: tuple[str, ...] = ()
    materialization_status: str = "pending"
    cursor_vector: dict[str, int] = Field(default_factory=dict)
    refusal_reason: str | None = None
    source_owner_receipt_refs: tuple[str, ...] = ()
    recorded_at: int = Field(default=0, ge=0)


class CharacterMemoryMaterializationReceipt(ContinuityModel):
    candidate_id: str = Field(min_length=1)
    actor_ref: str = Field(min_length=1)
    status: Literal["committed", "rejected", "idempotent_replay"]
    selected_pool: str | None = None
    memory_cursor: int = Field(default=0, ge=0)
    refusal_reason: str | None = None

