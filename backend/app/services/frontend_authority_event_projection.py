from app.models.authority_event import AuthorityEvent
from app.models.siming_catalyst import InnerPrompt


FRONTEND_AUTHORITY_EVENT_TYPES = {
    "siming.staging_request",
    "siming.visual_observability_request",
    "siming.fact_reveal",
    "siming.impulse",
    "siming.opportunity",
    "siming.inner_prompt",
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


def project_authority_event_as_social_spatial_runtime_result(event: AuthorityEvent) -> dict[str, object] | None:
    if event.event_type not in {"esm_result_event", "constraint_state_event"}:
        return None

    payload = dict(event.payload)
    if str(payload.get("result_type", "") or "") != "action_resolution_result":
        return None
    if str(payload.get("action_profile", "") or "") not in {
        "approach",
        "follow_target",
        "seek_private_distance",
        "withdraw",
        "break_contact",
    }:
        return None

    return {
        "message_type": "social_spatial_runtime_result",
        "payload": {
            "actor_id": str(payload.get("actor_id", "") or ""),
            "target_actor_id": str(payload.get("target_actor_id", "") or ""),
            "action_profile": str(payload.get("action_profile", "") or ""),
            "settlement_status": str(payload.get("settlement_status", "") or ""),
            "producer_ts": int(payload.get("producer_ts", 0) or 0),
        },
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


def project_authority_event_as_inner_prompt(event: AuthorityEvent) -> dict[str, object] | None:
    if event.event_type != "siming.inner_prompt":
        return None

    prompt = InnerPrompt.from_authority_event(event)
    return {
        "message_type": "siming_inner_prompt",
        "type": "siming_inner_prompt",
        "prompt_id": prompt.prompt_id,
        "target_actor_id": prompt.target_actor_id,
        "prompt_text": prompt.prompt_text,
        "intensity": prompt.intensity,
        "presentation_effects": list(prompt.presentation_effects),
        "player_facing": prompt.player_facing,
        "non_authoritative": prompt.non_authoritative,
        "evidence_refs": list(prompt.evidence_refs),
        "situation_snapshot_id": prompt.situation_snapshot_id,
        "authority_event_id": event.event_id,
        "causation_id": event.causation_id,
        "correlation_id": event.correlation_id,
        "producer_ts": event.producer_ts,
    }


def project_authority_event_as_siming_output(event: AuthorityEvent) -> dict[str, object] | None:
    if event.event_type not in FRONTEND_AUTHORITY_EVENT_TYPES or event.event_type == "siming.inner_prompt":
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

    def handle_event(self, event: AuthorityEvent) -> dict[str, object] | None:
        envelope = project_authority_event_as_conversation_candidate(event)
        if envelope is not None:
            self._pending.append(envelope)
            return envelope

        envelope = project_authority_event_as_world_result(event)
        if envelope is not None:
            self._pending.append(envelope)
            social_spatial = project_authority_event_as_social_spatial_runtime_result(event)
            if social_spatial is not None:
                self._pending.append(social_spatial)
            return envelope

        envelope = project_authority_event_as_state_machine_transition(event)
        if envelope is not None:
            self._pending.append(envelope)
            return envelope

        envelope = project_authority_event_as_inner_prompt(event)
        if envelope is not None:
            self._pending.append(envelope)
            return envelope

        envelope = project_authority_event_as_siming_output(event)
        if envelope is not None:
            self._pending.append(envelope)
            authority_event = project_authority_event_for_frontend(event)
            if authority_event is not None:
                self._pending.append(authority_event)
            return envelope
        return None

    def drain(self) -> list[dict[str, object]]:
        pending = self._pending
        self._pending = []
        return pending

    def clear(self) -> None:
        self._pending = []
