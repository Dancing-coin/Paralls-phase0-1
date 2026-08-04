"""Backend-safe envelope for the read-only Godot gameplay-state mirror."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.gameplay.state_group_views import CharacterGameRuntimeStateView


class GodotGameplayMirrorProjectionError(ValueError):
    """Raised when a non-Godot or unsafe view would cross the presentation boundary."""


_FORBIDDEN_FIELDS = {
    "world_truth_claim",
    "authority_command",
    "private_mind_state",
    "bone_transforms",
    "rigid_body_velocity",
    "migration_kind",
    "migration_digest",
    "migrator_code_digest",
    "rollback_mode",
    "input_event_schema",
    "output_event_schema",
}


def project_godot_runtime_state(view: CharacterGameRuntimeStateView) -> dict[str, Any]:
    """Serialize only a previously policy-filtered Godot view; it owns no delivery or writes."""

    if view.consumer != "godot":
        raise GodotGameplayMirrorProjectionError("godot_view_required")
    groups: dict[str, dict[str, Any]] = {}
    for group_id, envelope in view.groups.items():
        payload = _json_ready(envelope.payload)
        if _contains_forbidden_field(payload):
            raise GodotGameplayMirrorProjectionError("forbidden_projection_field")
        groups[group_id] = {
            "projection_revision": envelope.projection_revision,
            "payload": payload,
        }
    return {
        "message_type": "gameplay_runtime_state_projection",
        "projection_kind": "gameplay_runtime_state.godot.v1",
        "actor_ref": view.actor_ref,
        "facade_revision": view.source_facade_revision,
        "source_revision_vector": dict(view.source_revision_vector),
        "groups": groups,
    }


def _contains_forbidden_field(value: object) -> bool:
    """Reject prohibited fields at every depth before presentation serialization."""

    if isinstance(value, Mapping):
        return any(
            str(key) in _FORBIDDEN_FIELDS or _contains_forbidden_field(nested)
            for key, nested in value.items()
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_contains_forbidden_field(item) for item in value)
    return False


def _json_ready(value: object) -> Any:
    """Convert immutable read-model containers before they cross the JSON boundary."""

    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_ready(item) for item in value]
    return value
