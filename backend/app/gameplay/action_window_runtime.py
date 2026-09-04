"""Read-only admission for one logical action window.

This module validates a client/agent action sample against an admitted action
graph and frozen spatial revisions.  It intentionally does not append events;
the Conflict owner consumes its result later.
"""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Mapping

from pydantic import ConfigDict, Field, model_validator

from app.gameplay.action_graph_content import ActionGraphDefinition
from app.gameplay.models import StrictGameplayModel


class SpatialSnapshotRef(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_ref: str = Field(min_length=1)
    navigation_revision: str = Field(min_length=1)
    collision_revision: str = Field(min_length=1)
    occlusion_revision: str = Field(min_length=1)
    sound_zone_revision: str = Field(min_length=1)


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
    evidence_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_window(self) -> "ActionWindowIntent":
        if self.window_end_tick <= self.window_start_tick:
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
    ) -> ActionWindowResult:
        digest = _digest(intent.model_dump(mode="json"))
        if intent.graph_ref != graph.graph_ref or intent.graph_revision != graph.graph_revision:
            return cls._reject(intent, digest, "action_window_graph_revision_conflict")
        if previous_window_index is not None and intent.window_index != previous_window_index + 1:
            return cls._reject(intent, digest, "action_window_order_conflict")
        if prior_intent_digest is not None:
            if prior_intent_digest == digest:
                return ActionWindowResult(
                    accepted=True,
                    attempt_ref=intent.attempt_ref,
                    window_index=intent.window_index,
                    intent_digest=digest,
                    perception=PerceptionResolution(
                        snapshot_ref=spatial_snapshot.snapshot_ref,
                        distance_band="duplicate",
                        reason_ref="action_window_duplicate_replay",
                    ),
                )
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
        if _private_evidence_leaked(intent.actor_ref, intent.visibility_sample, intent.sound_sample, intent.contact_sample):
            return cls._reject(intent, digest, "action_window_private_evidence_leaked")
        if _sample_conflicts(intent):
            return cls._reject(intent, digest, "action_window_measurement_conflict")
        perception = PerceptionResolution(
            visible=bool(intent.visibility_sample.get("visible", False)),
            heard=bool(intent.sound_sample.get("heard", False)),
            in_contact=bool(intent.contact_sample.get("in_contact", False)),
            distance_band=str(intent.visibility_sample.get("distance_band", "unknown")),
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
    "ActionWindowIntent",
    "ActionWindowResult",
    "ActionWindowValidator",
    "PerceptionResolution",
    "SpatialSnapshotRef",
]
