"""The four-position model and per-region fidelity budgeting.

Two independent problems motivated this module.  First, "where an actor is" was
being collapsed into a single spatial answer, but the spec requires four distinct
positions because they can legitimately disagree: the world may place an actor in
a region while Godot has not spawned a body, and perception may lag both.

Second, fidelity was chosen per candidate without any region-level ceiling, so
every actor near the player could be upgraded at once.  A region budget makes
"too many visible actors" a refused upgrade rather than a silent cost spike.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

FidelityTier = Literal["B0", "B1", "B2", "B3"]

FIDELITY_ORDER: tuple[str, ...] = ("B0", "B1", "B2", "B3")

# Downgrade order used when a region is over budget.  B3 is shed first because it
# is the expensive tier; B0 is the floor and is never shed.
FIDELITY_SHED_ORDER: tuple[str, ...] = ("B3", "B2", "B1")

FIDELITY_RANK: dict[str, int] = {tier: index for index, tier in enumerate(FIDELITY_ORDER)}

# Explicit one-step downgrade, so the ladder is readable at a glance rather than
# derived from tuple ordering.
FIDELITY_ONE_STEP_DOWN: dict[str, str] = {
    "B3": "B2",
    "B2": "B1",
    "B1": "B0",
}


class SpatialPosition(BaseModel):
    """One of the four position views.  Each is owned by a different system."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["truth", "body", "perception", "presentation"]
    region_ref: str = Field(min_length=1)
    # Which system produced this view; a position without an owner is unverifiable.
    source_ref: str = Field(min_length=1)
    revision: int = Field(ge=0)


class ActorPositionSet(BaseModel):
    """The four positions for one actor, kept separate on purpose.

    Disagreement between them is normal and meaningful; collapsing them would
    hide the case where the world has moved an actor but Godot has not.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_ref: str = Field(min_length=1)
    positions: tuple[SpatialPosition, ...] = ()

    @model_validator(mode="after")
    def validate_unique_kinds(self) -> "ActorPositionSet":
        kinds = [position.kind for position in self.positions]
        if len(kinds) != len(set(kinds)):
            raise ValueError("duplicate_position_kind")
        return self

    def for_kind(self, kind: str) -> SpatialPosition | None:
        for position in self.positions:
            if position.kind == kind:
                return position
        return None

    def is_aligned(self) -> bool:
        """True when every present view names the same region.

        A missing view is not alignment: absent evidence must not read as agreement.
        """
        regions = {position.region_ref for position in self.positions}
        return len(self.positions) == 4 and len(regions) == 1


class RegionFidelityBudget(BaseModel):
    """Per-tier actor allowance for one region."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    region_ref: str = Field(min_length=1)
    allowance: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_allowance(self) -> "RegionFidelityBudget":
        unknown = set(self.allowance) - set(FIDELITY_ORDER)
        if unknown:
            raise ValueError(f"unknown_fidelity_tier:{','.join(sorted(unknown))}")
        if any(value < 0 for value in self.allowance.values()):
            raise ValueError("negative_fidelity_allowance")
        return self

    def limit_for(self, tier: str) -> int:
        return self.allowance.get(tier, 0)


class FidelityAdmission(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_ref: str = Field(min_length=1)
    granted_tier: FidelityTier
    requested_tier: FidelityTier
    downgraded: bool
    reason: str = ""


class RegionFidelitySelector:
    """Grants fidelity within a region budget, downgrading rather than refusing.

    Refusing outright would strand an actor at B0; the spec instead allows a lower
    tier so the actor still advances cheaply.
    """

    def admit(
        self,
        *,
        actor_ref: str,
        requested_tier: str,
        budget: RegionFidelityBudget,
        occupancy: dict[str, int],
    ) -> FidelityAdmission:
        if requested_tier not in FIDELITY_RANK:
            raise ValueError(f"unknown_fidelity_tier:{requested_tier}")
        tier = requested_tier
        while True:
            if occupancy.get(tier, 0) < budget.limit_for(tier):
                return FidelityAdmission(
                    actor_ref=actor_ref,
                    granted_tier=tier,
                    requested_tier=requested_tier,
                    downgraded=tier != requested_tier,
                    reason="" if tier == requested_tier else "region_budget_downgrade",
                )
            lower = FIDELITY_ONE_STEP_DOWN.get(tier)
            if lower is None:
                # B0 is the floor: it is granted even at its cap, because refusing
                # would mean an actor stops advancing entirely.
                return FidelityAdmission(
                    actor_ref=actor_ref,
                    granted_tier="B0",
                    requested_tier=requested_tier,
                    downgraded=tier != "B0",
                    reason="b0_floor_reached",
                )
            tier = lower
