from app.models.raw_fact import RawFactEvent
from app.models.visual_fact import VisualFactEvent
from app.services.fact_handlers.auditory_fact_handler import handle_auditory_fact_event
from app.services.fact_handlers.spatial_access_fact_handler import (
    SpatialAccessFactRouteHandler,
    handle_spatial_access_fact_event,
)
from app.services.fact_handlers.visual_fact_handler import (
    Message,
    VisualFactHandler,
    VisualFactHandlerContext,
    handle_visual_fact_event,
)


def _ack_known_raw_fact(event: RawFactEvent, *, source_type: str, route: str) -> list[Message]:
    return [
        {
            "message_type": "ack",
            "payload": {
                "accepted": True,
                "source_type": source_type,
                "route": route,
                "fact_family": event.fact_family,
                "fact_type": event.fact_type,
                "relation_type": event.relation_type,
                "fact_key": event.fact_type,
            },
        }
    ]


def route_raw_fact_event(
    event: RawFactEvent,
    *,
    source_type: str,
    context: VisualFactHandlerContext | None = None,
    visual_fact_handler: VisualFactHandler | None = None,
    spatial_access_fact_handler: SpatialAccessFactRouteHandler | None = None,
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

    if event.fact_family == "spatial_access_fact":
        handler = spatial_access_fact_handler or handle_spatial_access_fact_event
        return handler(event, source_type)

    if event.fact_family == "auditory_fact":
        return handle_auditory_fact_event(event, source_type)

    if event.fact_family == "role_state_fact":
        return _ack_known_raw_fact(event, source_type=source_type, route="authority_role_state_fact")

    if event.fact_family == "physiology_state_fact":
        return _ack_known_raw_fact(event, source_type=source_type, route="authority_physiology_fact")

    if event.fact_family == "tactile_fact":
        return _ack_known_raw_fact(event, source_type=source_type, route="authority_tactile_fact")

    if event.fact_family == "thermal_fact":
        return _ack_known_raw_fact(event, source_type=source_type, route="authority_thermal_fact")

    if event.fact_family == "olfactory_fact":
        return _ack_known_raw_fact(event, source_type=source_type, route="authority_olfactory_fact")

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
