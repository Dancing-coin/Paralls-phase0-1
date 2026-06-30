from __future__ import annotations

from app.world_runtime.models import WorldEntityRef, WorldStateDelta


def project_world_result_delta(payload: dict[str, object]) -> WorldStateDelta | None:
    target_environment_id = str(payload.get("target_environment_id", "") or "")
    if target_environment_id:
        return WorldStateDelta(
            entity=WorldEntityRef(entity_type="environment", entity_id=target_environment_id),
            changed_fields={"current_state": payload.get("current_state", "")},
            producer_ts=int(payload.get("producer_ts", 0) or 0),
        )

    target_object_id = str(payload.get("target_object_id", "") or "")
    if target_object_id:
        return WorldStateDelta(
            entity=WorldEntityRef(entity_type="object", entity_id=target_object_id),
            changed_fields={"current_state": payload.get("current_state", "")},
            producer_ts=int(payload.get("producer_ts", 0) or 0),
        )

    return None
