from collections.abc import Callable
from dataclasses import dataclass

from app.models.visual_fact import VisualFactEvent
from app.services.conversation_relation_service import ConversationRelationService
from app.services.event_trace_service import EventTraceService

Message = dict[str, object]
VisualFactHandler = Callable[[VisualFactEvent, str, "VisualFactHandlerContext"], list[Message]]


@dataclass(frozen=True, slots=True)
class VisualFactHandlerContext:
    conversation_relation_service: ConversationRelationService
    event_trace: EventTraceService
    ensure_runtime_snapshot_for_event: Callable[[VisualFactEvent], list[Message]]
    project_runtime_delta: Callable[[str, int], Message | None]
    candidate_messages: Callable[[object], list[Message]]
    publish_visual_fact: Callable[[VisualFactEvent], list[Message]]


def handle_visual_fact_event(
    event: VisualFactEvent,
    source_type: str,
    context: VisualFactHandlerContext,
) -> list[Message]:
    context.conversation_relation_service.apply_visual_fact(event)
    context.event_trace.record(event.fact_type)
    context.event_trace.record(event.relation_type)

    messages: list[Message] = [
        {
            "message_type": "ack",
            "payload": {
                "accepted": True,
                "source_type": source_type,
                "route": "authority_visual_fact",
            },
        }
    ]
    messages.extend(context.ensure_runtime_snapshot_for_event(event))
    visual_delta = context.project_runtime_delta(event.actor_id, event.producer_ts)
    if visual_delta is not None:
        messages.append(visual_delta)

    messages.extend(context.publish_visual_fact(event))

    candidate = context.conversation_relation_service.build_candidate_event(
        actor_id=event.actor_id,
        causation_id=f"visual_fact:{event.producer_ts}",
        correlation_id=f"visual_fact:{event.producer_ts}",
    )
    messages.extend(context.candidate_messages(candidate))
    return messages
