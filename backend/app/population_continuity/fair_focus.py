"""Fair focus selection for the Siming scheduler.

The spec requires that every candidate focus be traceable to a declared source,
and that fairness be a *coverage* mechanism rather than a plot dice roll.  The
runtime already accumulated ``starvation_credit`` but never spent it down, so an
actor could stay unserved forever while looking "credited" — coverage had no
feedback loop.

This module supplies the missing loop: it ranks by accumulated credit, resets the
credit of whoever was actually served, and exposes coverage/starvation metrics so
"nobody starved" is a measurable claim instead of an assumption.
"""

from __future__ import annotations

from typing import Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# The eight admissible focus sources.  A candidate that cannot name one of these
# is not eligible: the spec forbids untraceable focus.
FocusSource = Literal[
    "world_event",
    "actor_due",
    "relationship_spread",
    "region_pressure",
    "organization_duty",
    "player_interaction",
    "fairness_seed",
    "narrative_obligation",
]

FOCUS_SOURCES: tuple[str, ...] = (
    "world_event",
    "actor_due",
    "relationship_spread",
    "region_pressure",
    "organization_duty",
    "player_interaction",
    "fairness_seed",
    "narrative_obligation",
)

# Sources that may nominate an actor purely for coverage.  Story pressure must not
# pretend to be fairness, and fairness must not invent conflict.
COVERAGE_SOURCES: frozenset[str] = frozenset({"fairness_seed", "actor_due"})

# Credit added per cycle an actor goes unserved, and the ceiling that keeps one
# long-neglected actor from monopolising every future window.
CREDIT_PER_CYCLE = 0.1
CREDIT_CEILING = 1.0
# Credit is reset to this after being served, not to zero: a served actor should
# not immediately out-rank everyone, but should be eligible again soon.
CREDIT_ON_SERVE = 0.0


class FocusCandidate(BaseModel):
    """One nominated focus, with the source that justifies it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_ref: str = Field(min_length=1)
    source: FocusSource
    matter_ref: str = ""
    # Set by the caller after roster/permission admission.  A candidate is never
    # admitted here on the strength of this module alone.
    eligible: bool = True
    priority: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = ""


class FocusSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected: tuple[FocusCandidate, ...] = ()
    deferred: tuple[FocusCandidate, ...] = ()
    # Actors in the roster that were never served, longest-waiting first.
    starved_actors: tuple[str, ...] = ()
    coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    served_this_cycle: int = Field(default=0, ge=0)
    reason_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_counts(self) -> "FocusSelection":
        if self.served_this_cycle != len(self.selected):
            raise ValueError("served_count_mismatch")
        return self


class FairFocusQueue:
    """Accumulates per-actor coverage credit and spends it deterministically.

    The queue owns *no* world state and grants no permission: it only decides which
    already-admitted actor should be considered next, which is why it can be a
    pure scheduler input.
    """

    def __init__(self, *, ceiling: float = CREDIT_CEILING) -> None:
        self._credit: dict[str, float] = {}
        self._ceiling = ceiling
        self._served_total: dict[str, int] = {}

    def credit_for(self, actor_ref: str) -> float:
        return self._credit.get(actor_ref, 0.0)

    def accrue(self, actor_refs: Iterable[str], *, amount: float = CREDIT_PER_CYCLE) -> None:
        """Advance credit for actors that were not served this cycle."""
        for actor_ref in actor_refs:
            current = self._credit.get(actor_ref, 0.0)
            self._credit[actor_ref] = min(self._ceiling, current + amount)

    def observe_service(self, actor_refs: Iterable[str]) -> None:
        """Spend down credit for actors that were actually served."""
        for actor_ref in actor_refs:
            self._credit[actor_ref] = CREDIT_ON_SERVE
            self._served_total[actor_ref] = self._served_total.get(actor_ref, 0) + 1

    def select(
        self,
        candidates: Iterable[FocusCandidate],
        *,
        limit: int,
        roster: Iterable[str] | None = None,
    ) -> FocusSelection:
        """Pick up to ``limit`` eligible candidates, fairest first.

        Ordering is: ineligible never selected; declared priority first; then
        accumulated credit; then a stable tie-break on the actor ref so a replay
        over the same inputs produces the same order.
        """
        if limit < 0:
            raise ValueError("focus_limit_negative")
        eligible = [c for c in candidates if c.eligible]
        ordered = sorted(
            eligible,
            key=lambda c: (-c.priority, -self.credit_for(c.actor_ref), c.actor_ref, c.source),
        )
        selected = tuple(ordered[:limit])
        deferred = tuple(ordered[limit:])
        served = {c.actor_ref for c in selected}

        roster_set = set(roster) if roster is not None else set(self._credit)
        starved = sorted(
            (actor for actor in roster_set if self.credit_for(actor) > 0.0 and actor not in served),
            key=lambda actor: (-self.credit_for(actor), actor),
        )
        # Coverage is the share of the roster carrying no outstanding credit: a
        # roster where everyone has been reached recently reports 1.0.
        if roster_set:
            unreached = sum(1 for actor in roster_set if self.credit_for(actor) > 0.0)
            coverage = (len(roster_set) - unreached) / len(roster_set)
        else:
            coverage = 1.0
        reasons: list[str] = []
        if deferred:
            reasons.append("focus_budget_exhausted")
        if starved:
            reasons.append("actors_still_waiting")
        if not eligible:
            reasons.append("no_eligible_focus")
        return FocusSelection(
            selected=selected,
            deferred=deferred,
            starved_actors=tuple(starved),
            coverage=min(1.0, max(0.0, coverage)),
            served_this_cycle=len(selected),
            reason_codes=tuple(reasons),
        )
