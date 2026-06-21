from __future__ import annotations

from app.models.observatory import WorldOutcomeEvent


class WorldOutcomeDebugProjection:
    def project(self, *, message_type: str, payload: dict[str, object]) -> WorldOutcomeEvent:
        target_ref = self._target_ref(payload)
        request_type = str(
            payload.get("source_action_request_type", "")
            or payload.get("interaction_type", "")
            or payload.get("request_type", "")
            or ""
        )
        settlement_status = str(payload.get("settlement_status", "") or payload.get("resolution_status", "") or "")
        constraint_summary = str(payload.get("constraint_summary", "") or "")
        world_change_summary = str(
            payload.get("change_summary", "") or payload.get("stable_state_summary", "") or payload.get("result_type", "")
        )
        dramatic_consequence = world_change_summary
        if settlement_status == "rejected":
            dramatic_consequence = "request rejected: %s" % (constraint_summary or payload.get("result_type", "constraint"))
        elif payload.get("stable_state_summary"):
            dramatic_consequence = "%s | %s" % (world_change_summary, str(payload.get("stable_state_summary", "")))
        return WorldOutcomeEvent(
            producer_ts=int(payload.get("producer_ts", 0) or 0),
            causation_id=str(payload.get("causation_id", "") or ""),
            correlation_id=str(payload.get("correlation_id", "") or ""),
            participants=[value for value in [str(payload.get("actor_id", "") or ""), target_ref] if value != ""],
            actor_id=str(payload.get("actor_id", "") or ""),
            target_ref=target_ref,
            request_type=request_type,
            settlement_status=settlement_status,
            constraint_summary=constraint_summary,
            world_change_summary=world_change_summary,
            dramatic_consequence_summary=dramatic_consequence,
            source_message_type=message_type,
            detail=dict(payload),
        )

    def _target_ref(self, payload: dict[str, object]) -> str:
        for key in ("target_object_id", "target_environment_id", "target_actor_id", "entity_id"):
            value = str(payload.get(key, "") or "")
            if value != "":
                return value
        return ""
