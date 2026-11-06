"""Matter-to-actor eligibility for the Siming scheduler.

The spec fixes eligibility as a six-way conjunction: scope, role/relationship
relevance, location/access, capability/authority, privacy/admission, and the
absence of a conflicting lock.  Each of those is owned by another authority, so
this module does not evaluate them — it requires them to be supplied and fails
closed when one is absent.

That distinction matters: treating a missing evidence item as "allowed" is how a
scheduler silently grants access nobody approved.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

EligibilityCheck = Literal[
    "scope_match",
    "role_relevance",
    "location_access",
    "capability_authority",
    "privacy_admission",
    "no_conflicting_lock",
]

# The six conjunction terms, in the order the spec states them.
ELIGIBILITY_CHECKS: tuple[str, ...] = (
    "scope_match",
    "role_relevance",
    "location_access",
    "capability_authority",
    "privacy_admission",
    "no_conflicting_lock",
)


class EligibilityEvidence(BaseModel):
    """Evidence for one conjunction term, supplied by its owning authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    check: EligibilityCheck
    passed: bool
    # Which authority answered.  Required because "allowed" is only meaningful
    # when we know who allowed it.
    authority_ref: str = Field(min_length=1)
    reason: str = ""


class MatterEligibility(BaseModel):
    """The result of the six-way conjunction for one (actor, matter) pair."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_ref: str = Field(min_length=1)
    matter_ref: str = Field(min_length=1)
    eligible: bool
    failed_checks: tuple[str, ...] = ()
    missing_checks: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_consistency(self) -> "MatterEligibility":
        if self.eligible and (self.failed_checks or self.missing_checks):
            raise ValueError("eligible_with_failed_or_missing_check")
        if not self.eligible and not (self.failed_checks or self.missing_checks):
            raise ValueError("ineligible_without_failure_reason")
        return self


class MatterActorSelector:
    """Ranks actors for a matter without ever making the world decision.

    Scoring here is policy, not fact: it orders candidates that already passed the
    conjunction and never turns a score into an actor's decision.
    """

    def evaluate(
        self,
        *,
        actor_ref: str,
        matter_ref: str,
        evidence: tuple[EligibilityEvidence, ...],
    ) -> MatterEligibility:
        by_check = {item.check: item for item in evidence}
        failed: list[str] = []
        missing: list[str] = []
        for check in ELIGIBILITY_CHECKS:
            item = by_check.get(check)
            if item is None:
                missing.append(check)
            elif not item.passed:
                failed.append(check)
        reasons: list[str] = []
        if failed:
            reasons.append("eligibility_check_failed")
        if missing:
            # Absent evidence is not permission.
            reasons.append("eligibility_evidence_missing")
        return MatterEligibility(
            actor_ref=actor_ref,
            matter_ref=matter_ref,
            eligible=not failed and not missing,
            failed_checks=tuple(failed),
            missing_checks=tuple(missing),
            reason_codes=tuple(reasons),
        )

    def rank(
        self,
        eligibilities: tuple[MatterEligibility, ...],
        *,
        fairness_credit: dict[str, float] | None = None,
        matter_urgency: dict[str, float] | None = None,
    ) -> tuple[MatterEligibility, ...]:
        """Order eligible actors: urgency, then fairness, then a stable tie-break.

        Ineligible actors are dropped rather than ranked low, so a caller cannot
        accidentally treat a near-miss as a weak candidate.
        """
        credit = fairness_credit or {}
        urgency = matter_urgency or {}
        eligible = [item for item in eligibilities if item.eligible]
        return tuple(
            sorted(
                eligible,
                key=lambda item: (
                    -urgency.get(item.matter_ref, 0.0),
                    -credit.get(item.actor_ref, 0.0),
                    item.actor_ref,
                    item.matter_ref,
                ),
            )
        )
