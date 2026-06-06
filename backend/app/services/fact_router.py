from app.models.raw_fact import RawFactEvent
from app.models.visual_fact import VisualFactEvent
from app.services.fact_handlers.visual_fact_handler import (
    Message,
    VisualFactHandler,
    VisualFactHandlerContext,
    handle_visual_fact_event,
)


def route_raw_fact_event(
    event: RawFactEvent,
    *,
    source_type: str,
    context: VisualFactHandlerContext | None = None,
    visual_fact_handler: VisualFactHandler | None = None,
) -> list[Message]:
    if event.fact_family == "visual_fact":
        if context is None:
            raise ValueError("visual_fact routing requires a handler context")
        handler = visual_fact_handler or handle_visual_fact_event
        return handler(
            VisualFactEvent(**event.model_dump()),
            source_type,
            context,
        )

    return [
        {
            "message_type": "ack",
            "payload": {
                "accepted": False,
                "source_type": source_type,
                "route": "unknown_raw_fact_family",
            },
        }
    ]
