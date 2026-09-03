"""Read-only Inventory projection for Godot/Population consumers."""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from typing import Any
from app.gameplay.inventory_platform_runtime import InventoryPlatformProjection

class InventoryPresentationError(ValueError):
    pass

def project_inventory_for_godot(projection: InventoryPlatformProjection, *, consumer: str = "godot") -> dict[str, Any]:
    if consumer != "godot":
        raise InventoryPresentationError("inventory_presentation_consumer_invalid")
    state = projection.to_state()
    if _forbidden(state):
        raise InventoryPresentationError("inventory_presentation_forbidden_field")
    return {"message_type": "inventory_runtime_projection", "projection_kind": "inventory.generic.godot.v1", "projection_schema_version": 1, "state": state, "source_revision_vector": dict(projection.source_revision_vector), "last_global_sequence": projection.last_global_sequence}

def _forbidden(value: object) -> bool:
    if isinstance(value, Mapping):
        return any(str(k) in {"authority_command", "arbitrary_code", "script", "caller_proof"} or _forbidden(v) for k, v in value.items())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_forbidden(v) for v in value)
    return False

__all__ = ["InventoryPresentationError", "project_inventory_for_godot"]
