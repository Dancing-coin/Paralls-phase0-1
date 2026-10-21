"""Time coordinates for the existing caller-driven SimulationClock.

These values carry pins and owner references; they do not schedule or commit facts.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
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


@dataclass(frozen=True)
class ScheduledWork:
    work_ref: str
    domain_ref: str
    due_time: SimulationTime
    trigger_ref: str
    ordering_key: tuple[str, ...]
    expected_revision_vector: tuple[tuple[str, int], ...]
    owner_contract_ref: str
    time_pins: tuple[tuple[str, str | int], ...] = ()


@dataclass(frozen=True)
class SettlementWindow:
    window_ref: str
    timeline_id: str
    from_time: SimulationTime
    to_time: SimulationTime
    participant_scope: tuple[str, ...]
    phase_ref: str | None
    input_cutoff: SimulationTime
    late_input_policy_ref: str
    confirmation_boundary: SimulationTime
    frozen_read_set: tuple[tuple[str, int], ...]
    evidence_refs: tuple[str, ...]
    ordering_policy_ref: str
    expected_authority_revisions: tuple[tuple[str, int], ...]
    settlement_idempotency_key: str

    def __post_init__(self) -> None:
        times = (self.from_time, self.to_time, self.input_cutoff, self.confirmation_boundary)
        if any(time.timeline_id != self.timeline_id for time in times):
            raise ValueError("settlement_window_timeline_mismatch")
        if self.from_time.canonical_time_value > self.to_time.canonical_time_value:
            raise ValueError("settlement_window_bounds_invalid")
        if not (self.from_time.canonical_time_value <= self.input_cutoff.canonical_time_value
                <= self.to_time.canonical_time_value):
            raise ValueError("settlement_window_cutoff_out_of_bounds")
        if not (self.from_time.canonical_time_value <= self.confirmation_boundary.canonical_time_value
                <= self.to_time.canonical_time_value):
            raise ValueError("settlement_window_confirmation_out_of_bounds")


@dataclass(frozen=True)
class TemporalAuthorization:
    """A bounded grant carried by an existing cadence authority record.

    This is the stage-three temporal grant designed and implemented in this
    change. It is a read-only admission artifact; the existing event store
    remains the source of persistence and revocation (a missing or stale
    cadence record revokes the grant by failing verification).
    """

    authorization_ref: str
    revision: str
    issuer_ref: str
    timeline_id: str
    participant_scope: tuple[str, ...]
    input_cutoff: int
    confirmation_boundary: int
    late_input_policy_ref: str
    ordering_policy_ref: str
    valid_until: int
    revoked: bool = False

    def __post_init__(self) -> None:
        if (not self.authorization_ref or not self.revision or not self.issuer_ref
                or not self.timeline_id or not self.participant_scope
                or self.input_cutoff != self.confirmation_boundary
                or self.valid_until < self.confirmation_boundary
                or self.revoked):
            raise ValueError("temporal_authorization_invalid")

    def payload(self) -> dict[str, object]:
        return {
            "authorization_ref": self.authorization_ref,
            "revision": self.revision,
            "issuer_ref": self.issuer_ref,
            "timeline_id": self.timeline_id,
            "participant_scope": list(self.participant_scope),
            "input_cutoff": self.input_cutoff,
            "confirmation_boundary": self.confirmation_boundary,
            "late_input_policy_ref": self.late_input_policy_ref,
            "ordering_policy_ref": self.ordering_policy_ref,
            "valid_until": self.valid_until,
            "revoked": self.revoked,
        }

    @property
    def digest(self) -> str:
        encoded = json.dumps(self.payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return "sha256:" + hashlib.sha256(encoded.encode()).hexdigest()


def verify_temporal_authorization(*, pins: dict[str, object], expected_participant: str,
                                  expected_cutoff: int, expected_timeline: str,
                                  grant_key: str | None = None) -> bool:
    """Verify the grant digest and its scope against a persisted cadence pin set."""
    try:
        source = pins
        if grant_key is not None:
            grants = pins["temporal_authorizations"]
            if isinstance(grants, str):
                grants = json.loads(grants)
            source = dict(grants)[grant_key]
        raw_scope = source["participant_scope"] if grant_key else source["settlement_participant_scope"]
        if isinstance(raw_scope, str):
            participant_scope = (raw_scope,)
        elif isinstance(raw_scope, (list, tuple)):
            participant_scope = tuple(str(item) for item in raw_scope)
        else:
            return False
        # JSON and loosely typed callers must not be allowed to coerce a
        # string, float, or bool into an authoritative world-time value.
        # ``bool`` is an ``int`` subclass, hence the exact type check.
        input_cutoff_key = "input_cutoff"
        confirmation_key = "confirmation_boundary"
        valid_until_key = "valid_until" if grant_key else "temporal_authorization_valid_until"
        if any(type(source[key]) is not int for key in (input_cutoff_key, confirmation_key, valid_until_key)):
            return False
        authorization = TemporalAuthorization(
            authorization_ref=str(source["authorization_ref"] if grant_key else source["temporal_authorization_ref"]),
            revision=str(source["revision"] if grant_key else source["temporal_authorization_revision"]),
            issuer_ref=str(source["issuer_ref"] if grant_key else source["temporal_authorization_issuer_ref"]),
            timeline_id=str(source.get("timeline_id", pins["timeline_id"])),
            participant_scope=participant_scope,
            input_cutoff=source["input_cutoff"],
            confirmation_boundary=source["confirmation_boundary"],
            late_input_policy_ref=str(source["late_input_policy_ref"] if grant_key else source["late_input_policy_ref"]),
            ordering_policy_ref=str(source["ordering_policy_ref"] if grant_key else source["ordering_policy_ref"]),
            valid_until=source["valid_until"] if grant_key else source["temporal_authorization_valid_until"],
            revoked=bool(source.get("revoked", False)),
        )
        digest = source.get("digest") if grant_key else pins.get("temporal_authorization_digest")
        # A valid grant digest is insufficient on its own: the grant must be
        # issued by the same persisted cadence authority and confirmed window
        # that the caller is currently consuming. This prevents a caller from
        # rebinding a freshly re-digested grant to another issuer or boundary.
        if grant_key is not None:
            if authorization.issuer_ref != pins["temporal_authorization_issuer_ref"]:
                return False
            for key in ("sampled_at", "received_at", "input_cutoff", "confirmation_boundary"):
                if type(pins.get(key)) is not int or pins[key] != expected_cutoff:
                    return False
        return (authorization.digest == digest
                and authorization.timeline_id == expected_timeline
                and expected_participant in authorization.participant_scope
                and authorization.input_cutoff == expected_cutoff
                and authorization.valid_until >= expected_cutoff)
    except (KeyError, TypeError, ValueError):
        return False
