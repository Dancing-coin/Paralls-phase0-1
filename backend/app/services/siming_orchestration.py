"""Orchestration cadence for the Phase-1 Siming.

Three things were missing from the runtime and are defined here as data rather
than scattered constants: the five-level priority grading, the three degradation
modes, and the budget profile with its named defaults.  The orchestrator consumes
these; it does not invent them.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# P0 is the fatal path and must never be shed.  Lower levels are shed first, so
# the ordering *is* the degradation policy.
SimingPriority = Literal["P0", "P1", "P2", "P3", "P4"]

RUNTIME_PRIORITIES: tuple[SimingPriority, ...] = ("P0", "P1", "P2", "P3", "P4")

# Which priorities each mode keeps.  ``standard`` keeps everything; ``survival``
# keeps only the main judge chain, which the contract forbids shedding.
MODE_RETAINED_PRIORITIES: dict[str, frozenset[str]] = {
    "standard": frozenset({"P0", "P1", "P2", "P3", "P4"}),
    "pressure": frozenset({"P0", "P1", "P2", "P3"}),
    "survival": frozenset({"P0", "P1"}),
}

SimingRuntimeMode = Literal["standard", "pressure", "survival"]

# Path degradation ladder (contract 14 §8.2).  A path that cannot run degrades to
# the next entry, never sideways to something more forceful.
PATH_FALLBACK_LADDER: tuple[str, ...] = (
    "environment_change_path",
    "visual_fact_path",
    "character_input_path",
    "no_action",
)

# The auditor each fairness dimension belongs to.  Conversation access is called
# out separately because the contract forbids folding it into participation.
AUDITOR_FOR_DIMENSION: dict[str, str] = {
    "information_distribution": "information_auditor",
    "participation_distribution": "participation_auditor",
    "conversation_access_fairness": "conversation_access_auditor",
    "suspicion_heat_distribution": "suspicion_auditor",
    "evidence_visibility_distribution": "evidence_auditor",
}

AUDITORS: tuple[str, ...] = (
    "information_auditor",
    "participation_auditor",
    "conversation_access_auditor",
    "suspicion_auditor",
    "evidence_auditor",
)

# Auditors that may be downsampled under pressure.  Everything else keeps running
# so the main judge chain never loses an input.
PRESSURE_DOWNSAMPLED_AUDITORS: frozenset[str] = frozenset({"suspicion_auditor"})

# The exact seven budget names the contract freezes.  Defaults may be overridden
# by deployment, but the names must survive so budgets stay comparable.
DEFAULT_BUDGETS: dict[str, int] = {
    "tick_interval_ms": 1000,
    "max_event_window_age_ms": 3000,
    "auditor_fanout_budget_ms": 300,
    "decision_budget_ms": 200,
    "dispatch_deadline_ms": 500,
    "ack_timeout_ms": 5000,
    "audit_persist_budget_ms": 1000,
}

# What a budget overrun does.  Keeping the reaction next to the budget prevents a
# later reader from guessing whether an overrun is fatal or merely degrading.
BUDGET_OVERRUN_ACTION: dict[str, str] = {
    "tick_interval_ms": "merge_event_window",
    "max_event_window_age_ms": "mark_late_input_and_recompute",
    "auditor_fanout_budget_ms": "degrade_auditor_to_stale",
    "decision_budget_ms": "disable_l3_highlight_path",
    "dispatch_deadline_ms": "mark_ack_pending",
    "ack_timeout_ms": "mark_ack_timeout",
    "audit_persist_budget_ms": "queue_durable_and_mark_audit_pending",
}


class SimingBudgetProfile(BaseModel):
    """Named budget set; deployment may override values but not names."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tick_interval_ms: int = Field(default=1000, ge=0)
    max_event_window_age_ms: int = Field(default=3000, ge=0)
    auditor_fanout_budget_ms: int = Field(default=300, ge=0)
    decision_budget_ms: int = Field(default=200, ge=0)
    dispatch_deadline_ms: int = Field(default=500, ge=0)
    ack_timeout_ms: int = Field(default=5000, ge=0)
    audit_persist_budget_ms: int = Field(default=1000, ge=0)

    @classmethod
    def default(cls) -> "SimingBudgetProfile":
        return cls(**DEFAULT_BUDGETS)

    def as_dict(self) -> dict[str, int]:
        return self.model_dump()


def retained_priorities(mode: str) -> frozenset[str]:
    """Priorities still scheduled in ``mode``; unknown modes fail closed."""
    try:
        return MODE_RETAINED_PRIORITIES[mode]
    except KeyError:
        raise ValueError(f"unknown_runtime_mode:{mode}") from None


def is_priority_scheduled(priority: str, mode: str) -> bool:
    """Whether a task at ``priority`` still runs in ``mode``."""
    return priority in retained_priorities(mode)


def next_permitted_path(path: str) -> str:
    """Next rung of the degradation ladder.

    ``no_action`` is the floor: an unrunnable or unknown path degrades to it
    rather than to a more forceful intervention.
    """
    try:
        index = PATH_FALLBACK_LADDER.index(path)
    except ValueError:
        return "no_action"
    return PATH_FALLBACK_LADDER[min(index + 1, len(PATH_FALLBACK_LADDER) - 1)]


def select_runtime_mode(*, queued_events: int, pressure_threshold: int, survival_threshold: int) -> str:
    """Pick a mode from queue depth.

    Thresholds are caller-supplied so the policy stays policy; this function only
    keeps the ordering honest (survival is never chosen below pressure).
    """
    if survival_threshold < pressure_threshold:
        raise ValueError("survival_threshold_below_pressure_threshold")
    if queued_events >= survival_threshold:
        return "survival"
    if queued_events >= pressure_threshold:
        return "pressure"
    return "standard"
