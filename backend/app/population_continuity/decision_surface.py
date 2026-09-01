from __future__ import annotations

import math
from types import MappingProxyType
from typing import Literal, Mapping

from pydantic import Field, model_validator

from app.population_continuity.models import ContinuityModel

PopulationOutputKind = Literal[
    "presentation_seed",
    "activation_candidate",
    "owner_bound_intent",
    "character_core_command",
    "defer",
]


class PopulationDecisionCandidate(ContinuityModel):
    candidate_ref: str = Field(min_length=1)
    actor_ref: str = Field(min_length=1)
    cohort_ref: str = Field(min_length=1)
    behavior_kind: str = Field(min_length=1)
    fidelity_tier: Literal["B0", "B1", "B2", "B3"]
    source_projection_refs: tuple[str, ...] = ()
    source_revision_vector: Mapping[str, int] = Field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()
    estimated_cost: int = Field(ge=0)
    objective_risk: Literal["none", "low", "medium", "high"]
    player_proximity: float = Field(ge=0, le=1)
    narrative_obligation_pressure: float = Field(ge=0, le=1)
    unresolved_owner_consequence: float = Field(ge=0, le=1)
    propagation_pressure: float = Field(ge=0, le=1)
    starvation_credit: float = Field(ge=0, le=1)
    allowed_outputs: tuple[PopulationOutputKind, ...] = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    selector_revision: str = Field(min_length=1)
    ruleset_revision: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_numeric_signals(self) -> "PopulationDecisionCandidate":
        if any(
            not math.isfinite(value)
            for value in (
                self.player_proximity,
                self.narrative_obligation_pressure,
                self.unresolved_owner_consequence,
                self.propagation_pressure,
                self.starvation_credit,
            )
        ):
            raise ValueError("decision_signal_not_finite")
        if any(not key or isinstance(value, bool) or value < 0 for key, value in self.source_revision_vector.items()):
            raise ValueError("revision_vector_invalid")
        object.__setattr__(self, "source_revision_vector", MappingProxyType(dict(self.source_revision_vector)))
        return self


class PopulationDecision(ContinuityModel):
    selected_candidates: tuple[PopulationDecisionCandidate, ...] = ()
    deferred_candidates: tuple[PopulationDecisionCandidate, ...] = ()
    rejected_candidates: tuple[PopulationDecisionCandidate, ...] = ()
    unprocessed_refs: tuple[str, ...] = ()
    budget_used: int = Field(ge=0)
    budget_remaining: int = Field(ge=0)
    fidelity_counts: Mapping[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def freeze_fidelity_counts(self) -> "PopulationDecision":
        object.__setattr__(self, "fidelity_counts", MappingProxyType(dict(self.fidelity_counts)))
        return self

    decision_reason_codes: tuple[str, ...] = ()
    read_set_digest: str = Field(min_length=1)
    result_digest: str = Field(min_length=1)


class PopulationCapabilityDescriptor(ContinuityModel):
    capability_id: str = Field(min_length=1)
    accepted_behavior_kinds: tuple[str, ...] = Field(min_length=1)
    required_scopes: tuple[str, ...] = ()
    required_source_domains: tuple[str, ...] = ()
    target_owner: str = Field(min_length=1)
    allowed_output_kinds: tuple[PopulationOutputKind, ...] = Field(min_length=1)
    capability_revision: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    enabled: bool
