from __future__ import annotations

import math
import hashlib
import json
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, Mapping

from pydantic import Field, field_serializer, model_validator

from app.population_continuity.fair_focus import FairFocusQueue
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
    capability_id: str = ""
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

    @field_serializer("source_revision_vector")
    def serialize_source_revision_vector(self, value: Mapping[str, int]) -> dict[str, int]:
        return dict(value)


GovernanceOutcome = Literal[
    "accept",
    "no_op",
    "requeue",
    "defer",
    "upgrade",
]


class PopulationDeferralRecord(ContinuityModel):
    """Auditable record for a candidate the governor deliberately postponed.

    Budget exhaustion and fidelity deferral are governance decisions, not silent
    drops: without a record the candidate is indistinguishable from one that was
    never proposed.
    """

    candidate_ref: str = Field(min_length=1)
    actor_ref: str = Field(min_length=1)
    behavior_kind: str = Field(min_length=1)
    reason: Literal["budget_exhausted", "max_candidates_reached", "fidelity_deferred"]
    budget_used: int = Field(ge=0)
    budget_remaining: int = Field(ge=0)
    estimated_cost: int = Field(ge=0)
    fidelity_tier: str = Field(min_length=1)


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

    @field_serializer("fidelity_counts")
    def serialize_fidelity_counts(self, value: Mapping[str, int]) -> dict[str, int]:
        return dict(value)

    decision_reason_codes: tuple[str, ...] = ()
    # ``None`` means the caller did not classify the outcome; only an explicit
    # classification is validated, so legacy construction stays valid.
    governance_outcome: GovernanceOutcome | None = None
    deferrals: tuple[PopulationDeferralRecord, ...] = ()
    read_set_digest: str = Field(min_length=1)
    result_digest: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_governance_outcome(self) -> "PopulationDecision":
        """Keep an explicit outcome consistent with what was decided."""
        if self.governance_outcome is None:
            return self
        if self.governance_outcome == "accept":
            if not self.selected_candidates:
                raise ValueError("governance_outcome_accept_requires_selection")
        elif self.governance_outcome == "no_op":
            if self.selected_candidates:
                raise ValueError("governance_outcome_no_op_requires_empty_selection")
        elif self.governance_outcome == "upgrade":
            # An upgrade promotes fidelity instead of settling a fact, so it must
            # never carry an owner-bound selection in the same decision.
            if any(
                "owner_bound_intent" in candidate.allowed_outputs
                for candidate in self.selected_candidates
            ):
                raise ValueError("governance_outcome_upgrade_cannot_settle_owner_fact")
        return self


class PopulationCapabilityDescriptor(ContinuityModel):
    capability_id: str = Field(min_length=1)
    accepted_behavior_kinds: tuple[str, ...] = Field(min_length=1)
    required_scopes: tuple[str, ...] = ()
    # Where a candidate of this behavior can legitimately originate.  A
    # capability registered here but reachable only from fixtures must say so,
    # otherwise "enabled" reads as "production-drivable".
    production_source: Literal["owner_event", "baseline_projection", "fixture_only"] = (
        "owner_event"
    )
    required_source_domains: tuple[str, ...] = ()
    target_owner: str = Field(min_length=1)
    allowed_output_kinds: tuple[PopulationOutputKind, ...] = Field(min_length=1)
    capability_revision: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    enabled: bool
    owner_contract_ref: str | None = None

    def validate_owner_contract(self) -> bool:
        """Non-raising owner-contract check used by the admission gate.

        Returns ``False`` for any malformed descriptor so the caller can fail
        closed.  Use :meth:`require_owner_contract` when the caller must
        distinguish "not required" from "misconfigured".
        """
        try:
            self.require_owner_contract()
        except ValueError:
            return False
        return True

    def require_owner_contract(self) -> None:
        """Raise when an owner-bound descriptor is misconfigured.

        A descriptor that produces ``owner_bound_intent`` must resolve to a
        governed contract whose owner is exactly ``target_owner``.  Silently
        disabling such a capability would hide a configuration error, so this
        rejects loudly instead.
        """
        if "owner_bound_intent" not in self.allowed_output_kinds:
            return
        if not self.owner_contract_ref:
            raise ValueError(
                f"population_capability_owner_contract_missing:{self.capability_id}"
            )
        from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog

        try:
            contract = GovernedAuthorityContractCatalog.require(
                contract_ref=self.owner_contract_ref
            )
        except Exception as exc:  # noqa: BLE001 - re-raised with capability context
            raise ValueError(
                f"population_capability_owner_contract_unknown:{self.capability_id}"
            ) from exc
        if contract.owner_ref != self.target_owner:
            raise ValueError(
                f"population_capability_owner_contract_mismatch:{self.capability_id}"
            )


class PopulationCapabilityCatalog:
    """Source-controlled, read-only capability descriptors for population decisions."""

    @staticmethod
    def validate_owner_contracts(policy_revision: str = "policy:registry:v1") -> None:
        """Fail closed when any registered owner-bound capability is misconfigured.

        The admission gate only ever sees the descriptors a caller passes in, so
        a bad catalog entry could stay invisible until that capability happens to
        be requested.  Validating the whole catalog once makes the error appear
        at composition time instead.
        """
        for descriptor in PopulationCapabilityCatalog.default(policy_revision):
            descriptor.require_owner_contract()

    @staticmethod
    def registered_behavior_kinds(policy_revision: str = "policy:registry:v1") -> frozenset[str]:
        """Return every behavior kind registered by the source-controlled catalog.

        This is the single source of truth for population behavior vocabulary.
        Other modules must derive their admitted sets from here instead of
        hardcoding private copies; ``policy_revision`` does not affect the set.
        """
        return frozenset(
            kind
            for descriptor in PopulationCapabilityCatalog.default(policy_revision)
            for kind in descriptor.accepted_behavior_kinds
        )

    @staticmethod
    def default(policy_revision: str) -> tuple[PopulationCapabilityDescriptor, ...]:
        return (
            PopulationCapabilityDescriptor(
                capability_id="population:schedule-gated-supply:v1",
                accepted_behavior_kinds=("schedule_gated_supply",),
                target_owner="actor_gameplay.organization_domain",
                allowed_output_kinds=("owner_bound_intent", "character_core_command"),
                capability_revision="population:schedule-gated-supply:v1",
                policy_revision=policy_revision,
                enabled=True,
                owner_contract_ref="inf:weather-front-organization-supply@1",
            ),
            PopulationCapabilityDescriptor(
                capability_id="population:organization-production-work-contribution:v1",
                accepted_behavior_kinds=("organization_production_work_contribution",),
                required_scopes=("organization:summary", "public"),
                required_source_domains=("production",),
                target_owner="actor_gameplay.organization_domain",
                allowed_output_kinds=("owner_bound_intent", "character_core_command"),
                capability_revision="population:organization-production-work-contribution:v1",
                policy_revision=policy_revision,
                enabled=True,
                owner_contract_ref="inf:organization-production-work-contribution-acceptance@1",
            ),
            PopulationCapabilityDescriptor(
                capability_id="population:inventory-output-custody:v1",
                accepted_behavior_kinds=("inventory_output_custody",),
                required_scopes=("organization:summary", "public"),
                required_source_domains=("inventory",),
                target_owner="actor_gameplay.inventory_domain",
                allowed_output_kinds=("owner_bound_intent", "character_core_command"),
                capability_revision="population:inventory-output-custody:v1",
                policy_revision=policy_revision,
                enabled=True,
                owner_contract_ref="inf:inventory-production-output-custody@1",
            ),
            PopulationCapabilityDescriptor(
                capability_id="population:social-population-signal:v1",
                accepted_behavior_kinds=("social_population_signal",),
                required_scopes=("public",),
                required_source_domains=("social",),
                target_owner="authority:p5:social",
                allowed_output_kinds=("owner_bound_intent",),
                capability_revision="population:social-population-signal:v1",
                policy_revision=policy_revision,
                enabled=True,
                owner_contract_ref="inf:population-signal-materialization@1",
            ),
            PopulationCapabilityDescriptor(
                capability_id="population:organization-window-due:v1",
                accepted_behavior_kinds=("organization_operating_window_due",),
                target_owner="actor_gameplay.organization_domain",
                allowed_output_kinds=("owner_bound_intent",),
                capability_revision="population:organization-window-due:v1",
                policy_revision=policy_revision,
                enabled=True,
                owner_contract_ref="inf:organization-operating-window@1",
            ),
            PopulationCapabilityDescriptor(
                capability_id="population:routine-presentation:v1",
                accepted_behavior_kinds=("routine_work",),
                target_owner="character_core",
                allowed_output_kinds=("presentation_seed", "character_core_command"),
                capability_revision="population:routine-presentation:v1",
                policy_revision=policy_revision,
                enabled=True,
                production_source="baseline_projection",
            ),
            PopulationCapabilityDescriptor(
                capability_id="population:activation-candidate:v1",
                accepted_behavior_kinds=("relationship_negotiation",),
                target_owner="character_activation",
                allowed_output_kinds=("activation_candidate",),
                capability_revision="population:activation-candidate:v1",
                policy_revision=policy_revision,
                enabled=True,
                # No committed owner event produces this behavior yet, so only
                # fixtures can drive it.  Recording that keeps "enabled" from
                # being read as "production-drivable".
                production_source="fixture_only",
            ),
            PopulationCapabilityDescriptor(
                capability_id="population:tax-pressure:v1",
                accepted_behavior_kinds=("tax_pressure",),
                required_scopes=("public",),
                required_source_domains=("economy",),
                target_owner="character_core",
                allowed_output_kinds=("presentation_seed", "activation_candidate", "defer"),
                capability_revision="population:tax-pressure:v1",
                policy_revision=policy_revision,
                enabled=True,
            ),
        )


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
            if descriptor is None:
                continue
            outputs = descriptor.allowed_output_kinds
            if not outputs:
                continue
            try:
                estimated_cost = max(0, int(payload.get("budget_cost", 1) or 1))
                objective_risk = str(payload.get("objective_risk") or ("low" if "owner_bound_intent" in outputs else "none"))
                signals = {
                    "player_proximity": float(payload.get("player_proximity", 0.0) or 0.0),
                    "narrative_obligation_pressure": float(payload.get("narrative_obligation_pressure", 0.0) or 0.0),
                    "unresolved_owner_consequence": float(payload.get("unresolved_owner_consequence", 0.0) or 0.0),
                    "propagation_pressure": float(payload.get("propagation_pressure", 0.0) or 0.0),
                    "starvation_credit": float(payload.get("starvation_credit", 0.0) or 0.0),
                }
            except (TypeError, ValueError):
                continue
            cohort_ref = str(payload.get("cohort_ref") or self._cohort_ref(read_set))
            candidates.append(
                PopulationDecisionCandidate(
                    candidate_ref=f"candidate:{projection.ref}",
                    capability_id=descriptor.capability_id,
                    actor_ref=actor_ref,
                    cohort_ref=cohort_ref,
                    behavior_kind=behavior,
                    fidelity_tier=str(payload.get("fidelity_tier") or policy.default_fidelity_tier),
                    source_projection_refs=(projection.ref,),
                    source_revision_vector=dict(projection.revision_vector),
                    evidence_refs=tuple(str(item) for item in (payload.get("evidence_refs") or ())),
                    estimated_cost=estimated_cost,
                    objective_risk=objective_risk,
                    **signals,
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
        *,
        focus_queue: "FairFocusQueue | None" = None,
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
        deferrals: list[PopulationDeferralRecord] = []
        # 按角色限制昂贵层级，同角色的不同义务仍保留原成本和候选身份。
        tier_actor_limits = {"B1": 32, "B2": 4}
        selected_actors: dict[str, set[str]] = {tier: set() for tier in tier_actor_limits}
        budget_used = 0
        for candidate in ordered:
            actors = selected_actors.get(candidate.fidelity_tier)
            tier_full = (actors is not None and candidate.actor_ref not in actors
                         and len(actors) >= tier_actor_limits[candidate.fidelity_tier])
            defer_reason: str | None = None
            if tier_full:
                defer_reason = "fidelity_deferred"
            elif len(selected) >= policy.max_candidates:
                defer_reason = "max_candidates_reached"
            elif budget_used + candidate.estimated_cost > policy.budget:
                defer_reason = "budget_exhausted"
            if defer_reason is not None:
                deferred.append(candidate)
                # Deferral is a governance decision and must stay auditable;
                # otherwise a starved candidate is indistinguishable from one
                # that was never proposed.
                deferrals.append(
                    PopulationDeferralRecord(
                        candidate_ref=candidate.candidate_ref,
                        actor_ref=candidate.actor_ref,
                        behavior_kind=candidate.behavior_kind,
                        reason=defer_reason,
                        budget_used=budget_used,
                        budget_remaining=max(0, policy.budget - budget_used),
                        estimated_cost=candidate.estimated_cost,
                        fidelity_tier=candidate.fidelity_tier,
                    )
                )
                continue
            selected.append(candidate)
            budget_used += candidate.estimated_cost
            if actors is not None:
                actors.add(candidate.actor_ref)
        if focus_queue is not None:
            # Spend the credit of whoever was actually served.  Without this the
            # queue only ever accumulates, so the same actor keeps out-ranking
            # everyone and coverage never improves.
            focus_queue.observe_service({c.actor_ref for c in selected})
            focus_queue.accrue(
                {c.actor_ref for c in deferred} - {c.actor_ref for c in selected}
            )
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
            governance_outcome="accept" if selected else "no_op",
            deferrals=tuple(deferrals),
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
