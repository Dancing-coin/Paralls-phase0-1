"""Time coordinates for the existing caller-driven SimulationClock.

These values carry pins and owner references; they do not schedule or commit facts.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal


@dataclass(frozen=True)
class TemporalProfile:
    profile_id: str
    revision: str
    content_package_ref: str
    advancement_policy: str
    resolution_quantum: str
    scheduling_policy: str
    settlement_policy: str
    time_control_policy: str
    determinism_policy: str
    rewind_policy: str
    canonical_unit_ref: str
    step_duration: Fraction
    supported_clock_mappings: tuple[str, ...]
    rounding_policy: Literal["floor", "ceil", "exact"]
    activation_boundary: str
    compatibility_constraints: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.step_duration, Fraction) or self.step_duration <= 0:
            raise ValueError("temporal_profile_duration_invalid")
        if not all((self.profile_id, self.revision, self.canonical_unit_ref, self.activation_boundary)):
            raise ValueError("temporal_profile_identity_missing")
        if self.rounding_policy not in {"floor", "ceil", "exact"}:
            raise ValueError("temporal_rounding_invalid")


@dataclass(frozen=True)
class SimulationTimeline:
    timeline_id: str
    world_scope_ref: str
    advancement_owner_ref: str
    profile_ref: str
    profile_revision: str
    epoch_ref: str
    current_step: int
    current_phase: int | None
    authoritative_revision: int
    status: str
    parent_timeline_id: str | None = None


@dataclass(frozen=True)
class SimulationTime:
    timeline_id: str
    step_index: int
    canonical_time_value: Fraction
    substep_index: int = 0
    phase_index: int | None = None

    def __post_init__(self) -> None:
        if not self.timeline_id or self.step_index < 0 or self.substep_index < 0:
            raise ValueError("simulation_time_invalid")
        if not isinstance(self.canonical_time_value, Fraction):
            raise ValueError("simulation_time_requires_exact_value")


@dataclass(frozen=True)
class ClockMapping:
    mapping_id: str
    revision: str
    source_clock_ref: str
    source_unit_ref: str
    target_timeline_ref: str
    target_profile_revision: str
    source_origin: int
    target_origin: int
    ratio: Fraction
    rounding_policy: Literal["floor", "ceil", "exact"]
    valid_source_interval: tuple[int, int]
    max_lateness: int
    evidence_source_policy_ref: str

    def __post_init__(self) -> None:
        if not isinstance(self.ratio, Fraction) or self.ratio <= 0:
            raise ValueError("clock_mapping_ratio_invalid")
        if self.valid_source_interval[0] > self.valid_source_interval[1] or self.max_lateness < 0:
            raise ValueError("clock_mapping_interval_invalid")
        if self.rounding_policy not in {"floor", "ceil", "exact"}:
            raise ValueError("clock_mapping_rounding_invalid")
