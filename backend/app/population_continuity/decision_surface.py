from __future__ import annotations

import math
import hashlib
import json
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, Mapping

from pydantic import Field, model_validator

from app.population_continuity.models import ContinuityModel

if TYPE_CHECKING:
    from app.population_continuity.siming_contracts import PopulationReadSet

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


class PopulationDecisionPolicy(ContinuityModel):
    policy_revision: str = Field(min_length=1)
    default_fidelity_tier: Literal["B0", "B1", "B2", "B3"]
    budget: int = Field(ge=0)
    max_candidates: int = Field(ge=0)
    player_proximity_weight: float = 1.0
    owner_consequence_weight: float = 1.0
    propagation_weight: float = 1.0
    narrative_obligation_weight: float = 1.0
    starvation_weight: float = 1.0

    @model_validator(mode="after")
    def validate_weights(self) -> "PopulationDecisionPolicy":
        weights = (
            self.player_proximity_weight,
            self.owner_consequence_weight,
            self.propagation_weight,
            self.narrative_obligation_weight,
            self.starvation_weight,
        )
        if any(not math.isfinite(value) or value < 0 for value in weights):
            raise ValueError("decision_weight_invalid")
        return self


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class PopulationDecisionPlanner:
    """Pure candidate evaluator and deterministic selector."""

    _BEHAVIOR_OUTPUTS: dict[str, tuple[PopulationOutputKind, ...]] = {
        "schedule_gated_supply": ("owner_bound_intent", "character_core_command"),
        "routine_work": ("presentation_seed",),
        "relationship_negotiation": ("activation_candidate",),
    }

    def evaluate(
        self,
        read_set: "PopulationReadSet",
        capabilities: tuple[PopulationCapabilityDescriptor, ...],
        policy: PopulationDecisionPolicy,
    ) -> tuple[PopulationDecisionCandidate, ...]:
        candidates: list[PopulationDecisionCandidate] = []
        for projection in read_set.projections:
            payload = projection.payload
            actor_ref = str(
                payload.get("actor_ref")
                or payload.get("profile_ref")
                or payload.get("character_ref")
                or ""
            )
            behavior = str(payload.get("candidate_kind") or payload.get("kind") or payload.get("behavior_kind") or "")
            if not actor_ref or not behavior:
                continue
            descriptor = next(
                (
                    item
                    for item in capabilities
                    if item.enabled
                    and behavior in item.accepted_behavior_kinds
                    and item.policy_revision == policy.policy_revision
                    and self._scope_matches(projection.scope, item.required_scopes)
                    and self._source_matches(payload, item.required_source_domains)
                ),
                None,
            )
            if descriptor is None or behavior not in self._BEHAVIOR_OUTPUTS:
                continue
            outputs = self._BEHAVIOR_OUTPUTS[behavior]
            if not set(outputs).issubset(set(descriptor.allowed_output_kinds)):
                continue
            cohort_ref = str(payload.get("cohort_ref") or self._cohort_ref(read_set))
            candidates.append(
                PopulationDecisionCandidate(
                    candidate_ref=f"candidate:{projection.ref}",
                    actor_ref=actor_ref,
                    cohort_ref=cohort_ref,
                    behavior_kind=behavior,
                    fidelity_tier=str(payload.get("fidelity_tier") or policy.default_fidelity_tier),
                    source_projection_refs=(projection.ref,),
                    source_revision_vector=dict(projection.revision_vector),
                    evidence_refs=tuple(str(item) for item in (payload.get("evidence_refs") or ())),
                    estimated_cost=max(0, int(payload.get("budget_cost", 1) or 1)),
                    objective_risk=str(payload.get("objective_risk") or ("low" if "owner_bound_intent" in outputs else "none")),
                    player_proximity=float(payload.get("player_proximity", 0.0) or 0.0),
                    narrative_obligation_pressure=float(payload.get("narrative_obligation_pressure", 0.0) or 0.0),
                    unresolved_owner_consequence=float(payload.get("unresolved_owner_consequence", 0.0) or 0.0),
                    propagation_pressure=float(payload.get("propagation_pressure", 0.0) or 0.0),
                    starvation_credit=float(payload.get("starvation_credit", 0.0) or 0.0),
                    allowed_outputs=outputs,
                    policy_revision=policy.policy_revision,
                    selector_revision=read_set.cadence.selector_revision,
                    ruleset_revision=read_set.cadence.ruleset_revision,
                    idempotency_key=f"candidate:{projection.ref}",
                )
            )
        return tuple(candidates)

    def filter_registered(
        self,
        candidates: tuple[PopulationDecisionCandidate, ...],
        capabilities: tuple[PopulationCapabilityDescriptor, ...],
    ) -> tuple[PopulationDecisionCandidate, ...]:
        return tuple(
            candidate
            for candidate in candidates
            if any(
                descriptor.enabled
                and candidate.behavior_kind in descriptor.accepted_behavior_kinds
                and set(candidate.allowed_outputs).issubset(set(descriptor.allowed_output_kinds))
                for descriptor in capabilities
            )
        )

    def select(
        self,
        candidates: tuple[PopulationDecisionCandidate, ...],
        policy: PopulationDecisionPolicy,
    ) -> PopulationDecision:
        def score(candidate: PopulationDecisionCandidate) -> float:
            return (
                candidate.player_proximity * policy.player_proximity_weight
                + candidate.unresolved_owner_consequence * policy.owner_consequence_weight
                + candidate.propagation_pressure * policy.propagation_weight
                + candidate.narrative_obligation_pressure * policy.narrative_obligation_weight
                + candidate.starvation_credit * policy.starvation_weight
            )

        ordered = sorted(candidates, key=lambda item: (-score(item), item.candidate_ref, item.source_projection_refs))
        selected: list[PopulationDecisionCandidate] = []
        deferred: list[PopulationDecisionCandidate] = []
        budget_used = 0
        for candidate in ordered:
            if len(selected) >= policy.max_candidates or budget_used + candidate.estimated_cost > policy.budget:
                deferred.append(candidate)
                continue
            selected.append(candidate)
            budget_used += candidate.estimated_cost
        counts: dict[str, int] = {}
        for candidate in selected:
            counts[candidate.fidelity_tier] = counts.get(candidate.fidelity_tier, 0) + 1
        result_digest = _digest({"selected": [item.candidate_ref for item in selected], "deferred": [item.candidate_ref for item in deferred], "budget_used": budget_used})
        return PopulationDecision(
            selected_candidates=tuple(selected),
            deferred_candidates=tuple(deferred),
            budget_used=budget_used,
            budget_remaining=max(0, policy.budget - budget_used),
            fidelity_counts=counts,
            decision_reason_codes=("weighted_selection",) if selected else ("no_candidate_selected",),
            read_set_digest="sha256:unbound",
            result_digest=result_digest,
        )

    @staticmethod
    def _cohort_ref(read_set: PopulationReadSet) -> str:
        value = read_set.cadence.cadence_id
        return value.removeprefix("cadence:") if value.startswith("cadence:") else value

    @staticmethod
    def _scope_matches(scope: str, required: tuple[str, ...]) -> bool:
        return not required or scope in required

    @staticmethod
    def _source_matches(payload: dict[str, object], required: tuple[str, ...]) -> bool:
        if not required:
            return True
        source = str(payload.get("source_domain") or payload.get("domain") or "")
        return source in required
