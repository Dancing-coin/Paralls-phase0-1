"""Unique driver arbitration per (subject, mechanism, window).

The runtime already had an ``ActivationLock`` for one activated profile, but
nothing prevented two drivers from advancing the *same* actor at once: a B0
continuity batch and an activated B3 agent could both settle the same window, and
neither knew about the other.  The spec forbids that — every covered unit must
have exactly one advancing source.

This module owns only the claim.  It grants no settlement rights and writes no
fact; releasing a claim never implies the work succeeded.
"""

from __future__ import annotations

from typing import Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# The dimensions along which an actor can be advanced.  They are separate because
# the spec allows coarse handling of one dimension while another is fine-grained —
# as long as each individual dimension has one driver.
MechanismDimension = Literal[
    "continuity",
    "local_event",
    "propagation",
    "resource",
]

MECHANISM_DIMENSIONS: tuple[str, ...] = (
    "continuity",
    "local_event",
    "propagation",
    "resource",
)


class DriverClaim(BaseModel):
    """A claim to advance one subject, in one dimension, over one window."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    subject_ref: str = Field(min_length=1)
    dimension: MechanismDimension
    # Which runtime is asking to advance.  Recorded so a conflict can name both
    # sides rather than only reporting "already claimed".
    driver_ref: str = Field(min_length=1)
    window_start: int = Field(ge=0)
    window_end: int = Field(ge=0)
    # Scope keeps distinct worlds or branches from colliding on the same ids.
    scope_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_window(self) -> "DriverClaim":
        if self.window_end <= self.window_start:
            raise ValueError("claim_window_invalid")
        return self

    def overlaps(self, other: "DriverClaim") -> bool:
        if self.scope_ref != other.scope_ref:
            return False
        if self.subject_ref != other.subject_ref or self.dimension != other.dimension:
            return False
        return self.window_start < other.window_end and other.window_start < self.window_end


class DriverDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    granted: bool
    claim: DriverClaim
    # Present when granted is False: who already holds the overlapping window.
    conflicting_driver_ref: str = ""
    reason: str = ""

    @model_validator(mode="after")
    def validate_reason(self) -> "DriverDecision":
        if self.granted and self.conflicting_driver_ref:
            raise ValueError("granted_claim_names_a_conflict")
        if not self.granted and not self.reason:
            raise ValueError("refused_claim_without_reason")
        return self


class DriverArbitrator:
    """Grants at most one driver per (subject, dimension, window) unit."""

    def __init__(self) -> None:
        self._claims: list[DriverClaim] = []

    def active_claims(self) -> tuple[DriverClaim, ...]:
        return tuple(self._claims)

    def request(self, claim: DriverClaim) -> DriverDecision:
        """Grant or refuse one claim.

        A refresh from the *same* driver over its own window is granted (it is not
        a second driver), so idempotent retries do not fight themselves.
        """
        for existing in self._claims:
            if not claim.overlaps(existing):
                continue
            if existing.driver_ref == claim.driver_ref:
                continue
            return DriverDecision(
                granted=False,
                claim=claim,
                conflicting_driver_ref=existing.driver_ref,
                reason="driver_conflict",
            )
        self._claims.append(claim)
        return DriverDecision(granted=True, claim=claim, reason="")

    def release(self, claim: DriverClaim) -> bool:
        """Release an identical claim.  Returns whether one was held.

        Release only ends the claim: it says nothing about whether the work
        succeeded, and must not be read as a receipt.
        """
        for index, existing in enumerate(self._claims):
            if (
                existing.subject_ref == claim.subject_ref
                and existing.dimension == claim.dimension
                and existing.driver_ref == claim.driver_ref
                and existing.scope_ref == claim.scope_ref
                and existing.window_start == claim.window_start
                and existing.window_end == claim.window_end
            ):
                del self._claims[index]
                return True
        return False

    def release_driver(self, driver_ref: str) -> int:
        """Drop every claim held by a driver; used on handoff or shutdown."""
        before = len(self._claims)
        self._claims = [c for c in self._claims if c.driver_ref != driver_ref]
        return before - len(self._claims)

    def claims_for(self, subject_ref: str) -> tuple[DriverClaim, ...]:
        return tuple(c for c in self._claims if c.subject_ref == subject_ref)

    def drivers_for(self, subject_ref: str) -> frozenset[str]:
        return frozenset(c.driver_ref for c in self._claims if c.subject_ref == subject_ref)
