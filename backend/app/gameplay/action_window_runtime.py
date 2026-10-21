"""Read-only admission for one logical action window.

This module validates a client/agent action sample against an admitted action
graph and frozen spatial revisions.  It intentionally does not append events;
the Conflict owner consumes its result later.
"""

from __future__ import annotations

from hashlib import sha256
import json
from dataclasses import asdict, dataclass
from fractions import Fraction
from typing import Mapping

from pydantic import ConfigDict, Field, model_validator

from app.gameplay.action_graph_content import ActionGraphDefinition
from app.gameplay.models import StrictGameplayModel
from app.world_runtime.simulation_clock import SimulationClock
from app.world_runtime.temporal_contracts import ClockMapping, SettlementWindow


class ActionTimeBinding(StrictGameplayModel):
    """Historical source coordinates and exact, domain-neutral settlement pins."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    timeline_id: str
    profile_ref: str
    profile_revision: str
    mapping_id: str
    mapping_revision: str
    source_clock_ref: str
    source_unit_ref: str
    source_revision: str
    sampled_at: int
    received_at: int
    cutoff_tick: int
    temporal_profile: dict[str, object]
    clock_mapping: dict[str, object]
    sampled_time: dict[str, object]
    received_time: dict[str, object]
    settlement_window: dict[str, object]


@dataclass(frozen=True)
class ActionTemporalContext:
    """Trusted caller binding; never constructed from the action's claimed pins."""

    clock: SimulationClock
    mapping: ClockMapping
    source_revision: str
    sampled_at: int
    received_at: int
    cutoff_tick: int
    late_input_policy_ref: str
    ordering_policy_ref: str


def _temporal_json(value: object) -> object:
    if isinstance(value, Fraction):
        return {"numerator": value.numerator, "denominator": value.denominator}
    if isinstance(value, dict):
        return {key: _temporal_json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_temporal_json(item) for item in value]
    return value


def freeze_action_time_binding(
    intent: "ActionWindowIntent", context: ActionTemporalContext, *,
    idempotency_key: str, expected_authority_revisions: Mapping[str, int],
) -> ActionTimeBinding:
    """Map source coordinates without advancing time or writing domain facts."""
    clock, mapping = context.clock, context.mapping
    if clock.timeline is None or clock.temporal_profile is None:
        raise ValueError("action_window_temporal_context_missing")
    if not all((context.source_revision, context.late_input_policy_ref, context.ordering_policy_ref, idempotency_key)):
        raise ValueError("action_window_temporal_policy_missing")

    def mapped(source: int, received: int | None = None):
        return clock.map_source_time(
            mapping=mapping, source_clock_ref=mapping.source_clock_ref,
            source_unit_ref=mapping.source_unit_ref, source_revision=context.source_revision,
            expected_source_revision=context.source_revision, mapping_revision=mapping.revision,
            sampled_at=source, received_at=source if received is None else received,
        )

    start, end = mapped(intent.window_start_tick), mapped(intent.window_end_tick)
    sample = mapped(context.sampled_at, context.received_at)
    received, cutoff = mapped(context.received_at), mapped(context.cutoff_tick)
    if not intent.window_start_tick <= context.sampled_at <= intent.window_end_tick:
        raise ValueError("action_window_sample_outside_window")
    if not start.canonical_time_value <= sample.canonical_time_value <= end.canonical_time_value:
        raise ValueError("action_window_sample_outside_window")
    if (context.received_at > context.cutoff_tick or received.canonical_time_value > cutoff.canonical_time_value
            or clock.tick > cutoff.step_index or clock.timeline.current_step > cutoff.step_index):
        raise ValueError("action_window_cutoff_exceeded")
    if cutoff.canonical_time_value < end.canonical_time_value:
        raise ValueError("action_window_cutoff_before_window_end")
    window = SettlementWindow(
        window_ref=f"action-window:{intent.attempt_ref}:{intent.window_index}",
        timeline_id=clock.timeline.timeline_id, from_time=start, to_time=end,
        participant_scope=(intent.actor_ref, *intent.target_refs), phase_ref=None,
        input_cutoff=cutoff, late_input_policy_ref=context.late_input_policy_ref,
        confirmation_boundary=cutoff, frozen_read_set=tuple(sorted(intent.expected_revision_vector.items())),
        evidence_refs=intent.evidence_refs, ordering_policy_ref=context.ordering_policy_ref,
        expected_authority_revisions=tuple(sorted(expected_authority_revisions.items())),
        settlement_idempotency_key=idempotency_key,
    )
    return ActionTimeBinding(
        timeline_id=clock.timeline.timeline_id, profile_ref=clock.temporal_profile.profile_id,
        profile_revision=clock.temporal_profile.revision, mapping_id=mapping.mapping_id,
        mapping_revision=mapping.revision, source_clock_ref=mapping.source_clock_ref,
        source_unit_ref=mapping.source_unit_ref, source_revision=context.source_revision,
        sampled_at=context.sampled_at, received_at=context.received_at, cutoff_tick=context.cutoff_tick,
        temporal_profile=_temporal_json(asdict(clock.temporal_profile)),
        clock_mapping=_temporal_json(asdict(mapping)), sampled_time=_temporal_json(asdict(sample)),
        received_time=_temporal_json(asdict(received)), settlement_window=_temporal_json(asdict(window)),
    )


def action_intent_payload(intent: "ActionWindowIntent") -> dict[str, object]:
    """Keep historical unbound intent digests byte-compatible."""
    payload = intent.model_dump(mode="json")
    if intent.time_binding is None:
        payload.pop("time_binding", None)
    return payload


class SpatialSnapshotRef(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_ref: str = Field(min_length=1)
    navigation_revision: str = Field(min_length=1)
    collision_revision: str = Field(min_length=1)
    occlusion_revision: str = Field(min_length=1)
    sound_zone_revision: str = Field(min_length=1)
    source_revision_vector: dict[str, int] = Field(default_factory=dict)
    visibility_by_target: dict[str, bool] = Field(default_factory=dict)
    sound_by_target: dict[str, bool] = Field(default_factory=dict)
    contact_by_target: dict[str, bool] = Field(default_factory=dict)
    distance_band_by_target: dict[str, str] = Field(default_factory=dict)


class ActionWindowIntent(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    attempt_ref: str = Field(min_length=1)
    encounter_ref: str = Field(min_length=1)
    actor_ref: str = Field(pattern=r"^character:")
    window_index: int = Field(ge=0)
    window_start_tick: int = Field(ge=0)
    window_end_tick: int = Field(ge=1)
    graph_ref: str = Field(min_length=1)
    graph_revision: str = Field(min_length=1)
    node_ref: str = Field(min_length=1)
    target_refs: tuple[str, ...] = ()
    expected_revision_vector: dict[str, int] = Field(default_factory=dict)
    local_position_sample: tuple[float, float, float]
    facing_sample: tuple[float, float, float]
    visibility_sample: dict[str, object] = Field(default_factory=dict)
    sound_sample: dict[str, object] = Field(default_factory=dict)
    contact_sample: dict[str, object] = Field(default_factory=dict)
    navigation_revision: str = Field(min_length=1)
    collision_revision: str = Field(min_length=1)
    occlusion_revision: str = Field(min_length=1)
    sound_zone_revision: str = Field(min_length=1)
    deterministic_seed: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    time_binding: ActionTimeBinding | None = None

    @model_validator(mode="after")
    def validate_window(self) -> "ActionWindowIntent":
        if self.window_end_tick - self.window_start_tick != 1:
            raise ValueError("action_window_duration_invalid")
        if len(self.local_position_sample) != 3 or len(self.facing_sample) != 3:
            raise ValueError("action_window_sample_invalid")
        if any(value < 0 for value in self.expected_revision_vector.values()):
            raise ValueError("action_window_revision_invalid")
        if len(set(self.target_refs)) != len(self.target_refs) or len(set(self.evidence_refs)) != len(self.evidence_refs):
            raise ValueError("action_window_array_duplicate")
        return self


class PerceptionResolution(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    visible: bool = False
    heard: bool = False
    in_contact: bool = False
    distance_band: str = Field(min_length=1)
    reason_ref: str = Field(min_length=1)
    snapshot_ref: str = Field(min_length=1)


class ActionWindowResult(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted: bool
    attempt_ref: str = Field(min_length=1)
    window_index: int = Field(ge=0)
    intent_digest: str = Field(min_length=1)
    error_code: str | None = None
    perception: PerceptionResolution | None = None


class ActionWindowValidator:
    """Validate action windows without touching any persistence or authority store."""

    @classmethod
    def validate(
        cls,
        intent: ActionWindowIntent,
        *,
        graph: ActionGraphDefinition,
        spatial_snapshot: SpatialSnapshotRef,
        previous_window_index: int | None = None,
        prior_intent_digest: str | None = None,
        prior_result: ActionWindowResult | None = None,
    ) -> ActionWindowResult:
        digest = _digest(action_intent_payload(intent))
        if intent.graph_ref != graph.graph_ref or intent.graph_revision != graph.graph_revision:
            return cls._reject(intent, digest, "action_window_graph_revision_conflict")
        if previous_window_index is not None and intent.window_index != previous_window_index + 1:
            return cls._reject(intent, digest, "action_window_order_conflict")
        if prior_intent_digest is not None:
            if prior_intent_digest == digest:
                if prior_result is None:
                    return cls._reject(intent, digest, "action_window_duplicate_result_missing")
                return prior_result.model_copy(deep=True)
            return cls._reject(intent, digest, "action_window_idempotency_reused")
        node = next((candidate for candidate in graph.nodes if candidate.node_ref == intent.node_ref), None)
        if node is None:
            return cls._reject(intent, digest, "action_window_node_unknown")
        if any(value not in {target.node_ref for target in graph.nodes} for value in node.cancel_targets):
            return cls._reject(intent, digest, "action_window_cancel_target_invalid")
        expected = {
            "navigation_revision": spatial_snapshot.navigation_revision,
            "collision_revision": spatial_snapshot.collision_revision,
            "occlusion_revision": spatial_snapshot.occlusion_revision,
            "sound_zone_revision": spatial_snapshot.sound_zone_revision,
        }
        actual = {
            "navigation_revision": intent.navigation_revision,
            "collision_revision": intent.collision_revision,
            "occlusion_revision": intent.occlusion_revision,
            "sound_zone_revision": intent.sound_zone_revision,
        }
        if actual != expected:
            return cls._reject(intent, digest, "action_window_spatial_revision_conflict")
        if dict(intent.expected_revision_vector) != dict(spatial_snapshot.source_revision_vector):
            return cls._reject(intent, digest, "action_window_source_revision_conflict")
        if _private_evidence_leaked(intent.actor_ref, intent.visibility_sample, intent.sound_sample, intent.contact_sample):
            return cls._reject(intent, digest, "action_window_private_evidence_leaked")
        if _sample_conflicts(intent):
            return cls._reject(intent, digest, "action_window_measurement_conflict")
        target_ref = intent.target_refs[0] if intent.target_refs else ""
        if target_ref and target_ref not in spatial_snapshot.distance_band_by_target:
            return cls._reject(intent, digest, "action_window_spatial_evidence_missing")
        authoritative_visible = spatial_snapshot.visibility_by_target.get(target_ref, False)
        authoritative_heard = spatial_snapshot.sound_by_target.get(target_ref, False)
        authoritative_contact = spatial_snapshot.contact_by_target.get(target_ref, False)
        claimed_visible = bool(intent.visibility_sample.get("visible", False))
        claimed_heard = bool(intent.sound_sample.get("heard", False))
        claimed_contact = bool(intent.contact_sample.get("in_contact", False))
        if (claimed_visible, claimed_heard, claimed_contact) != (authoritative_visible, authoritative_heard, authoritative_contact):
            return cls._reject(intent, digest, "action_window_measurement_conflict")
        perception = PerceptionResolution(
            visible=authoritative_visible,
            heard=authoritative_heard,
            in_contact=authoritative_contact,
            distance_band=spatial_snapshot.distance_band_by_target.get(target_ref, "movement"),
            reason_ref="action_window_spatial_snapshot_recomputed",
            snapshot_ref=spatial_snapshot.snapshot_ref,
        )
        return ActionWindowResult(
            accepted=True,
            attempt_ref=intent.attempt_ref,
            window_index=intent.window_index,
            intent_digest=digest,
            perception=perception,
        )

    @staticmethod
    def _reject(intent: ActionWindowIntent, digest: str, error_code: str) -> ActionWindowResult:
        return ActionWindowResult(
            accepted=False,
            attempt_ref=intent.attempt_ref,
            window_index=intent.window_index,
            intent_digest=digest,
            error_code=error_code,
        )


def _private_evidence_leaked(actor_ref: str, *samples: Mapping[str, object]) -> bool:
    for sample in samples:
        scope = sample.get("visibility_scope", sample.get("scope"))
        if isinstance(scope, str) and scope.startswith("actor:") and scope != f"actor:{actor_ref}":
            return True
    return False


def _sample_conflicts(intent: ActionWindowIntent) -> bool:
    for sample in (intent.visibility_sample, intent.sound_sample, intent.contact_sample):
        if sample.get("measurement_conflict") is True or sample.get("tampered") is True:
            return True
    return False


def _digest(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


__all__ = [
    "ActionTimeBinding",
    "ActionTemporalContext",
    "freeze_action_time_binding",
    "ActionWindowIntent",
    "ActionWindowResult",
    "ActionWindowValidator",
    "PerceptionResolution",
    "SpatialSnapshotRef",
]
