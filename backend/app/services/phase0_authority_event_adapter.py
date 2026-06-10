from app.models.authority_event import AuthorityEvent, AuthorityEventRouting, AuthorityEventSource
from app.models.player_input import DialogueSubmit, FocusTargetChange, InteractIntent, MoveIntent
from app.models.runtime_state import ConversationCandidateEvent
from app.models.visual_fact import VisualFactEvent
from app.models.world_result import (
    ActionResolutionResult,
    BodyStateResult,
    ConstraintStateResult,
    EnvironmentStateResult,
    ObjectStateResult,
    VisibleFeedbackResult,
)


PlayerInputEvent = MoveIntent | DialogueSubmit | InteractIntent | FocusTargetChange
WorldResultEvent = (
    ActionResolutionResult
    | ObjectStateResult
    | BodyStateResult
    | EnvironmentStateResult
    | VisibleFeedbackResult
    | ConstraintStateResult
)


class Phase0AuthorityEventAdapter:
    def visual_fact_event(self, event: VisualFactEvent) -> AuthorityEvent:
        event_id = f"visual_fact:{event.producer_ts}:{event.actor_id}:{event.fact_type}"
        payload = event.model_dump(exclude_none=True)
        payload["established_fact_id"] = event_id
        payload["target_actor_id"] = event.target_actor_id
        payload["target_object_id"] = event.target_object_id
        payload["target_environment_id"] = event.target_environment_id
        return AuthorityEvent(
            event_id=event_id,
            event_type="visual_fact_event",
            producer_ts=event.producer_ts,
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            source=AuthorityEventSource(layer="L1", system="visual_fact", actor_id=event.actor_id),
            routing=AuthorityEventRouting(audience_mode="room", routing_mode="event_type", target_ids=["siming"]),
            priority="p2",
            ttl=5000,
            durability="replayable",
            causation_id=event.causation_id or f"visual_fact:{event.producer_ts}",
            correlation_id=event.correlation_id or f"visual_fact:{event.producer_ts}",
            payload=payload,
        )

    def world_result_event(self, result: WorldResultEvent, *, source_event: object) -> AuthorityEvent:
        event_type = "constraint_state_event" if isinstance(result, ConstraintStateResult) else "esm_result_event"
        return AuthorityEvent(
            event_id=f"{event_type}:{result.producer_ts}:{result.causation_id}",
            event_type=event_type,
            producer_ts=result.producer_ts,
            room_id=result.room_id,
            scene_id=result.scene_id or getattr(source_event, "scene_id", "scene_demo"),
            zone_id=result.zone_id or getattr(source_event, "zone_id", "zone_focus"),
            source=AuthorityEventSource(layer="L1", system="esm", actor_id=result.actor_id or getattr(source_event, "actor_id", None)),
            routing=AuthorityEventRouting(audience_mode="room", routing_mode="event_type", target_ids=["siming"]),
            priority="p1" if isinstance(result, ConstraintStateResult) else "p2",
            ttl=5000,
            durability="replayable",
            causation_id=result.causation_id,
            correlation_id=result.correlation_id or result.causation_id,
            payload=result.model_dump(exclude_none=True),
        )

    def conversation_candidate_event(self, event: ConversationCandidateEvent) -> AuthorityEvent:
        return AuthorityEvent(
            event_id=f"conversation_candidate:{event.producer_ts}:{event.actor_id}",
            event_type="conversation_resolution_event",
            producer_ts=event.producer_ts,
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            source=AuthorityEventSource(layer="L2", system="conversation_relation", actor_id=event.actor_id),
            routing=AuthorityEventRouting(audience_mode="room", routing_mode="event_type", target_ids=["siming"]),
            priority="p2",
            ttl=5000,
            durability="replayable",
            causation_id=event.causation_id,
            correlation_id=event.correlation_id,
            payload=event.model_dump(exclude_none=True),
        )
