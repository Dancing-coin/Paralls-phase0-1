from __future__ import annotations

from dataclasses import dataclass, replace
from math import ceil, floor
from fractions import Fraction

from app.gameplay.shared_contracts import ScheduledObligation
from .temporal_contracts import ClockMapping, SimulationTime, SimulationTimeline, TemporalProfile


def population_clock_profile(name: str) -> dict[str, str | int]:
    """启动时固定的时间语义；生产兼容窗口不伪装成一秒benchmark。"""
    if name not in ("production", "benchmark_1x", "benchmark_10x"):
        raise ValueError("population_clock_profile_unknown")
    window = 86400 if name == "production" else 1
    return dict(simulation_tick_unit="second", window_ticks=window,
                wall_period_seconds=window, speed=10 if name == "benchmark_10x" else 1)


def calculate_window_bounds(
    previous_tick: int, target_tick: int, window_size: int
) -> tuple[tuple[int, int], ...]:
    if previous_tick < 0 or target_tick < 0 or window_size <= 0:
        raise ValueError("simulation_clock_invalid_window")
    if target_tick < previous_tick:
        raise ValueError("simulation_clock_cannot_rewind")
    return tuple(
        (window_start, window_start + window_size)
        for window_start in range(previous_tick, target_tick - window_size + 1, window_size)
    )


@dataclass(frozen=True)
class ClockAdvance:
    previous_tick: int
    current_tick: int
    due: tuple[ScheduledObligation, ...]
    deferred: tuple[ScheduledObligation, ...]


class SimulationClock:
    """Caller-driven clock facade; it never starts a background loop or writes truth."""

    def __init__(self, *, world_ref: str, initial_tick: int = 0, catch_up_budget: int = 100,
                 temporal_profile: TemporalProfile | None = None,
                 timeline: SimulationTimeline | None = None) -> None:
        if not world_ref or initial_tick < 0 or catch_up_budget < 0:
            raise ValueError("simulation_clock_invalid")
        self.world_ref = world_ref
        self.tick = initial_tick
        self.catch_up_budget = catch_up_budget
        if (temporal_profile is None) != (timeline is None):
            raise ValueError("simulation_clock_temporal_pins_missing")
        if temporal_profile is not None:
            self._check_profile_admission(temporal_profile)
        if timeline is not None and (
            timeline.world_scope_ref != world_ref or timeline.current_step != initial_tick
            or timeline.profile_ref != temporal_profile.profile_id
            or timeline.profile_revision != temporal_profile.revision
            or not timeline.advancement_owner_ref or timeline.status != "active"
        ):
            raise ValueError("simulation_clock_temporal_pins_mismatch")
        self.temporal_profile = temporal_profile
        self.timeline = timeline

    @staticmethod
    def _check_profile_admission(profile: TemporalProfile) -> None:
        if profile.determinism_policy != "best_effort" or profile.rewind_policy != "disabled":
            raise ValueError("temporal_adapter_admission_required")

    def _check_mapping(self, mapping: ClockMapping) -> None:
        if self.timeline is None or self.temporal_profile is None:
            raise ValueError("simulation_clock_temporal_pins_missing")
        if mapping.target_timeline_ref != self.timeline.timeline_id:
            raise ValueError("clock_mapping_timeline_mismatch")
        if mapping.target_profile_revision != self.temporal_profile.revision:
            raise ValueError("clock_mapping_profile_revision_mismatch")
        if mapping.mapping_id not in self.temporal_profile.supported_clock_mappings:
            raise ValueError("clock_mapping_not_admitted")

    def map_source_time(self, *, mapping: ClockMapping, source_clock_ref: str,
                        source_unit_ref: str, source_revision: str,
                        expected_source_revision: str, mapping_revision: str,
                        sampled_at: int, received_at: int) -> SimulationTime:
        self._check_mapping(mapping)
        if mapping_revision != mapping.revision:
            raise ValueError("clock_mapping_revision_mismatch")
        if type(sampled_at) is not int or type(received_at) is not int:
            raise ValueError("clock_mapping_source_coordinate_invalid")
        if (source_clock_ref != mapping.source_clock_ref or source_unit_ref != mapping.source_unit_ref
                or not source_revision or source_revision != expected_source_revision):
            raise ValueError("clock_mapping_source_mismatch")
        if not mapping.valid_source_interval[0] <= sampled_at <= mapping.valid_source_interval[1]:
            raise ValueError("clock_mapping_source_outside_interval")
        if not 0 <= received_at - sampled_at <= mapping.max_lateness:
            raise ValueError("clock_mapping_source_stale")
        value = mapping.target_origin + (sampled_at - mapping.source_origin) * mapping.ratio
        if mapping.rounding_policy == "exact" and value.denominator != 1:
            raise ValueError("clock_mapping_rounding_required")
        step = ceil(value) if mapping.rounding_policy == "ceil" else floor(value)
        return SimulationTime(timeline_id=self.timeline.timeline_id, step_index=step,
                              canonical_time_value=step * self.temporal_profile.step_duration)

    def advance_mapped(self, time: SimulationTime, *, advancement_owner_ref: str,
                       source_mapping: ClockMapping,
                       obligations: tuple[ScheduledObligation, ...] = ()) -> ClockAdvance:
        if self.timeline is None or advancement_owner_ref != self.timeline.advancement_owner_ref:
            raise ValueError("simulation_clock_advancement_owner_mismatch")
        self._check_mapping(source_mapping)
        if source_mapping.source_clock_ref in {"render", "render_frame"}:
            raise ValueError("simulation_clock_render_projection_only")
        if time.timeline_id != self.timeline.timeline_id:
            raise ValueError("simulation_clock_timeline_mismatch")
        if time.canonical_time_value != time.step_index * self.temporal_profile.step_duration:
            raise ValueError("simulation_clock_time_unit_mismatch")
        result = self._advance(time.step_index, obligations)
        self.timeline = replace(self.timeline, current_step=result.current_tick,
                                authoritative_revision=self.timeline.authoritative_revision + 1)
        return result

    def advance(self, target_tick: int, obligations: tuple[ScheduledObligation, ...] = ()) -> ClockAdvance:
        if self.timeline is not None:
            raise ValueError("simulation_clock_mapped_advance_required")
        return self._advance(target_tick, obligations)

    def _advance(self, target_tick: int, obligations: tuple[ScheduledObligation, ...]) -> ClockAdvance:
        if target_tick < self.tick:
            raise ValueError("simulation_clock_cannot_rewind")
        due = tuple(sorted((item for item in obligations if item.due_tick <= target_tick and item.status in {"open", "due", "retry", "retryable"}), key=lambda item: (item.due_tick, item.obligation_id)))
        selected = due[: self.catch_up_budget]
        deferred = due[self.catch_up_budget :]
        previous = self.tick
        self.tick = target_tick
        return ClockAdvance(previous_tick=previous, current_tick=target_tick, due=selected, deferred=deferred)


__all__ = ["ClockAdvance", "SimulationClock", "calculate_window_bounds"]
