from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    ValidationInfo,
    field_validator,
    model_validator,
)

from app.models.siming_heavenly_graph import HeavenlyGraphScope
from app.models.siming_adaptive_bridge import AdaptiveBridgeNodeProposal
from app.models.siming_resource_capability import StagingAck, StagingRequest


_NORMALIZED_PUBLIC_REF = re.compile(r"^[a-z][a-z0-9_]*(?::[A-Za-z0-9_.-]+)+$")


class StrictMemoryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("*", check_fields=False)
    @classmethod
    def require_normalized_public_refs(
        cls,
        value: Any,
        info: ValidationInfo,
    ) -> Any:
        if not info.field_name.endswith("_refs"):
            return value

        for ref in value:
            if not _NORMALIZED_PUBLIC_REF.fullmatch(ref) or ref.startswith(
                "actor_private:"
            ):
                raise ValueError("references must be normalized public reference IDs")
        return value


class WorldFactMemoryEntry(StrictMemoryModel):
    domain: Literal["world_fact"] = "world_fact"
    entry_id: str
    world_anchor_id: str
    state_key: str
    state_value: JsonValue
    authority_result_ref: str
    evidence_refs: list[str] = Field(default_factory=list)


class CausalTimelineMemoryEntry(StrictMemoryModel):
    domain: Literal["causal_timeline"] = "causal_timeline"
    entry_id: str
    cause_ref: str
    effect_ref: str
    relation_type: Literal["CAUSED_BY", "ENABLED_BY", "PREVENTED_BY"]
    closes_path_refs: list[str] = Field(default_factory=list)


class ActorCognitionMemoryEntry(StrictMemoryModel):
    domain: Literal["actor_cognition"] = "actor_cognition"
    entry_id: str
    actor_id: str
    revision_vector: dict[str, str]
    completeness: Literal["complete", "memory_surface_incomplete"]
    supporting_memory_refs: list[str] = Field(default_factory=list)


class StorylineObligationMemoryEntry(StrictMemoryModel):
    domain: Literal["storyline_obligation"] = "storyline_obligation"
    entry_id: str
    record_type: Literal[
        "storyline",
        "story_node",
        "outcome_port",
        "obligation",
        "attractor",
        "constraint",
    ]
    lifecycle: str
    supporting_fact_refs: list[str] = Field(default_factory=list)


class InterventionOutcomeMemoryEntry(StrictMemoryModel):
    domain: Literal["intervention_outcome"] = "intervention_outcome"
    entry_id: str
    stage: Literal[
        "proposal",
        "selection",
        "staging_ack",
        "staging",
        "dispatch",
        "authority_result",
    ]
    correlation_id: str
    selected_node_ref: str | None = None
    realization_signature: str | None = None
    authority_result_ref: str | None = None
    dispatch_event_id: str | None = None
    dispatch_state: Literal[
        "sent_unconfirmed",
        "authority_confirmed",
        "authority_unknown",
    ] | None = None
    obligation_id: str | None = None
    staging_status: (
        Literal["staged", "aborted_before_activation", "cancelled"] | None
    ) = None
    story_node_lifecycle: Literal["staged", "aborted"] | None = None
    obligation_status: Literal["open", "pressured", "partially_satisfied"] | None = None
    staging_recorded_at: int | None = Field(default=None, ge=0)
    staging_ack: StagingAck | None = None
    staging_request: StagingRequest | None = None
    proposal: AdaptiveBridgeNodeProposal | None = None
    reason: str = ""

    @model_validator(mode="after")
    def require_staging_result_fields(self) -> "InterventionOutcomeMemoryEntry":
        if self.stage == "staging" and (
            self.selected_node_ref is None
            or self.realization_signature is None
            or self.obligation_id is None
            or self.staging_status is None
            or self.story_node_lifecycle is None
            or self.obligation_status is None
            or self.staging_recorded_at is None
        ):
            raise ValueError(
                "staging intervention outcome requires its complete result"
            )
        if self.stage == "dispatch" and (
            (self.dispatch_event_id is None) != (self.dispatch_state is None)
        ):
            raise ValueError("dispatch intervention outcome requires identity and state")
        return self


class ConvergenceStrategyMemoryEntry(StrictMemoryModel):
    domain: Literal["convergence_strategy"] = "convergence_strategy"
    entry_id: str
    reachable_attractor_refs: list[str] = Field(default_factory=list)
    open_obligation_refs: list[str] = Field(default_factory=list)
    permanently_closed_node_refs: list[str] = Field(default_factory=list)
    next_minimal_intervention: str = ""


SimingHeavenlyMemoryEntry = Annotated[
    WorldFactMemoryEntry
    | CausalTimelineMemoryEntry
    | ActorCognitionMemoryEntry
    | StorylineObligationMemoryEntry
    | InterventionOutcomeMemoryEntry
    | ConvergenceStrategyMemoryEntry,
    Field(discriminator="domain"),
]


class SimingContextRequest(StrictMemoryModel):
    scope: HeavenlyGraphScope
    valid_at: int = Field(ge=0)
    recorded_at: int | None = Field(default=None, ge=0)
    seed_node_ids: list[str]
    relevant_actor_ids: list[str] = Field(default_factory=list)
    relation_types: list[str] = Field(default_factory=list)
    node_limit: int = Field(default=200, ge=1, le=1000)
    relation_limit: int = Field(default=400, ge=1, le=2000)

    @model_validator(mode="after")
    def require_heavenly_scope(self) -> "SimingContextRequest":
        if (
            self.scope.graph_namespace != "siming_heavenly"
            or self.scope.owner_actor_id is not None
        ):
            raise ValueError("Siming context requires siming_heavenly scope")
        return self


class SimingCompiledContext(StrictMemoryModel):
    request: SimingContextRequest
    world_facts: list[WorldFactMemoryEntry] = Field(default_factory=list)
    causal_timeline: list[CausalTimelineMemoryEntry] = Field(default_factory=list)
    actor_cognition: list[ActorCognitionMemoryEntry] = Field(default_factory=list)
    storyline_obligations: list[StorylineObligationMemoryEntry] = Field(
        default_factory=list
    )
    intervention_outcomes: list[InterventionOutcomeMemoryEntry] = Field(
        default_factory=list
    )
    convergence_strategies: list[ConvergenceStrategyMemoryEntry] = Field(
        default_factory=list
    )
    selected_node_refs: list[str] = Field(default_factory=list)
    selected_relation_refs: list[str] = Field(default_factory=list)
    truncated: bool
    context_hash: str
