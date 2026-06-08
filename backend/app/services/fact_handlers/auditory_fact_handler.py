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
            },
        }
    ]
