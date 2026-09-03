"""Read-only public/Godot projection for Ecology state."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.gameplay.ecology_platform_runtime import EcologyPlatformProjection


class EcologyPresentationError(ValueError):
    pass


_FORBIDDEN = frozenset({"authority_command", "owner_ref", "private_evidence", "arbitrary_code", "script"})


def project_ecology_for_godot(projection: EcologyPlatformProjection, *, consumer: str = "godot") -> dict[str, Any]:
    if consumer != "godot":
        raise EcologyPresentationError("ecology_presentation_consumer_invalid")
    state = projection.to_state()
    if _contains_forbidden(state):
        raise EcologyPresentationError("ecology_presentation_forbidden_field")
    return {
        "message_type": "ecology_runtime_projection",
        "projection_kind": "ecology.generic.godot.v1",
        "projection_schema_version": 1,
        "state": state,
        "source_revision_vector": dict(projection.source_revision_vector),
        "last_global_sequence": projection.last_global_sequence,
    }


def _contains_forbidden(value: object) -> bool:
    if isinstance(value, Mapping):
        return any(str(key) in _FORBIDDEN or _contains_forbidden(nested) for key, nested in value.items())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_contains_forbidden(item) for item in value)
    return False


__all__ = ["EcologyPresentationError", "project_ecology_for_godot"]
