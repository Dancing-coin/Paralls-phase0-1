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
from app.world_runtime.fact_registry import WorldFactRegistry


_FACT_REGISTRY = WorldFactRegistry()


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


def build_raw_fact_authority_ack(event: RawFactEvent, *, source_type: str) -> Message:
    route_kind = _FACT_REGISTRY.route_for_family(event.fact_family)
    if route_kind == "visual":
        return {
            "message_type": "ack",
            "payload": {
                "accepted": True,
                "source_type": source_type,
                "route": "authority_visual_fact",
                "fact_family": event.fact_family,
                "fact_type": event.fact_type,
                "relation_type": event.relation_type,
                "fact_key": event.relation_type,
            },
        }
    if route_kind == "auditory":
        return _ack_known_raw_fact(event, source_type=source_type, route="authority_auditory_fact")[0]
    if route_kind == "spatial_access":
        return {
            "message_type": "ack",
            "payload": {
                "accepted": True,
                "source_type": source_type,
                "route": "authority_spatial_access_fact",
            },
        }
    if route_kind in {
        "authority_role_state_fact",
        "authority_physiology_fact",
        "authority_tactile_fact",
        "authority_thermal_fact",
        "authority_olfactory_fact",
    }:
        return _ack_known_raw_fact(event, source_type=source_type, route=route_kind)[0]
    return {
        "message_type": "ack",
        "payload": {
            "accepted": False,
            "source_type": source_type,
            "route": "unknown_raw_fact_family",
        },
    }


def route_raw_fact_event(
    event: RawFactEvent,
    *,
    source_type: str,
    context: VisualFactHandlerContext | None = None,
    visual_fact_handler: VisualFactHandler | None = None,
    spatial_access_fact_handler: SpatialAccessFactRouteHandler | None = None,
) -> list[Message]:
    route_kind = _FACT_REGISTRY.route_for_family(event.fact_family)

    if route_kind == "visual":
        if context is None:
            raise ValueError("visual_fact routing requires a handler context")
        handler = visual_fact_handler or handle_visual_fact_event
        return handler(
            VisualFactEvent(**event.model_dump()),
            source_type,
            context,
        )

    if route_kind == "spatial_access":
        handler = spatial_access_fact_handler or handle_spatial_access_fact_event
        return handler(event, source_type)

    if route_kind == "auditory":
        return handle_auditory_fact_event(event, source_type)

    if route_kind == "authority_role_state_fact":
        return _ack_known_raw_fact(event, source_type=source_type, route=route_kind)

    if route_kind == "authority_physiology_fact":
        return _ack_known_raw_fact(event, source_type=source_type, route=route_kind)

    if route_kind == "authority_tactile_fact":
        return _ack_known_raw_fact(event, source_type=source_type, route=route_kind)

    if route_kind == "authority_thermal_fact":
        return _ack_known_raw_fact(event, source_type=source_type, route=route_kind)

    if route_kind == "authority_olfactory_fact":
        return _ack_known_raw_fact(event, source_type=source_type, route=route_kind)

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
