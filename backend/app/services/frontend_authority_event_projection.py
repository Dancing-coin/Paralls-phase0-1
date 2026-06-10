from app.models.authority_event import AuthorityEvent


FRONTEND_AUTHORITY_EVENT_TYPES = {
    "siming.visual_observability_request",
    "siming.fact_reveal",
}


def project_authority_event_as_conversation_candidate(event: AuthorityEvent) -> dict[str, object] | None:
    if event.event_type != "conversation_resolution_event":
        return None
    return {
        "message_type": "conversation_candidate_event",
        "payload": dict(event.payload),
    }


def project_authority_event_as_world_result(event: AuthorityEvent) -> dict[str, object] | None:
    if event.event_type not in {"esm_result_event", "constraint_state_event"}:
        return None

    payload = dict(event.payload)
    target_object_id = str(payload.get("target_object_id", "") or "")
    target_environment_id = str(payload.get("target_environment_id", "") or "")
    entity_id = str(payload.get("entity_id", "") or "")
    object_id = entity_id or target_object_id or target_environment_id or None
    return {
        "message_type": "world_result",
        "event_id": str(payload.get("result_id", "") or ""),
        "event_type": str(payload.get("result_type", "world_result") or "world_result"),
        "producer_ts": event.producer_ts,
        "room_id": event.room_id,
        "scene_id": event.scene_id,
        "zone_id": event.zone_id,
        "entity_id": entity_id,
        "source": {
            "layer": "L1",
            "system": "esm",
            "actor_id": str(payload.get("actor_id", "") or ""),
            "object_id": object_id,
        },
        "routing": {
            "audience_mode": "authority_broadcast",
            "routing_mode": "authoritative_event_bus",
            "dialog_group_id": None,
            "target_ids": [],
        },
        "priority": "p1",
        "ttl": None,
        "durability": "replayable",
        "causation_id": event.causation_id,
        "correlation_id": event.correlation_id,
        "payload": payload,
    }


def project_authority_event_as_state_machine_transition(event: AuthorityEvent) -> dict[str, object] | None:
    if event.event_type != "state_machine_transition_event":
        return None

    payload = dict(event.payload)
    return {
        "message_type": "state_machine_transition",
        "event_id": str(payload.get("event_id", "") or ""),
        "event_type": str(payload.get("event_type", "state_machine_transition") or "state_machine_transition"),
        "room_id": event.room_id,
        "scene_id": event.scene_id,
        "zone_id": event.zone_id,
        "entity_id": str(payload.get("entity_id", "") or ""),
        "machine_id": str(payload.get("machine_id", "") or ""),
        "from_state": str(payload.get("from_state", "") or ""),
        "to_state": str(payload.get("to_state", "") or ""),
        "trigger_type": str(payload.get("trigger_type", "") or ""),
        "transition_reason": str(payload.get("transition_reason", "") or ""),
        "producer_ts": event.producer_ts,
        "causation_id": event.causation_id,
        "correlation_id": event.correlation_id,
        "payload": payload,
    }


def project_authority_event_for_frontend(event: AuthorityEvent) -> dict[str, object] | None:
    candidate = project_authority_event_as_conversation_candidate(event)
    if candidate is not None:
        return candidate
    world_result = project_authority_event_as_world_result(event)
    if world_result is not None:
        return world_result
    transition = project_authority_event_as_state_machine_transition(event)
    if transition is not None:
        return transition
    if event.event_type in FRONTEND_AUTHORITY_EVENT_TYPES:
        return {
            "message_type": "authority_event",
            "payload": event.model_dump(exclude_none=True),
        }
    return None


def project_authority_event_as_siming_output(event: AuthorityEvent) -> dict[str, object] | None:
    if event.event_type not in FRONTEND_AUTHORITY_EVENT_TYPES:
        return None

    payload = {
        "room_id": event.room_id,
        "output_type": "attention_prompt",
        "causation_id": event.causation_id,
        "correlation_id": event.correlation_id,
        "producer_ts": event.producer_ts,
        "target_actor_id": event.payload.get("target_actor_id"),
        "target_environment_id": event.payload.get("target_environment_id"),
        "target_object_id": event.payload.get("target_object_id"),
        "prompt_summary": str(event.payload.get("presentation_hint", "notice established visual fact")),
        "authority_event_id": event.event_id,
        "authority_event_type": event.event_type,
    }
    return {
        "message_type": "siming_output",
        "payload": payload,
    }


class FrontendAuthorityEventProjector:
    def __init__(self) -> None:
        self._pending: list[dict[str, object]] = []

    def handle_event(self, event: AuthorityEvent) -> None:
        envelope = project_authority_event_as_conversation_candidate(event)
        if envelope is not None:
            self._pending.append(envelope)
            return

        envelope = project_authority_event_as_world_result(event)
        if envelope is not None:
            self._pending.append(envelope)
            return

        envelope = project_authority_event_as_state_machine_transition(event)
        if envelope is not None:
            self._pending.append(envelope)
            return

        envelope = project_authority_event_as_siming_output(event)
        if envelope is not None:
            self._pending.append(envelope)

    def drain(self) -> list[dict[str, object]]:
        pending = self._pending
        self._pending = []
        return pending

    def clear(self) -> None:
        self._pending = []
