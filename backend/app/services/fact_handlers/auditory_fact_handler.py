from app.models.raw_fact import RawFactEvent
from app.services.fact_handlers.visual_fact_handler import Message


def handle_auditory_fact_event(event: RawFactEvent, source_type: str) -> list[Message]:
    _ = event
    return [
        {
            "message_type": "ack",
            "payload": {
                "accepted": True,
                "source_type": source_type,
                "route": "authority_auditory_fact",
                "fact_family": event.fact_family,
                "fact_type": event.fact_type,
                "relation_type": event.relation_type,
                "fact_key": event.fact_type,
            },
        }
    ]
