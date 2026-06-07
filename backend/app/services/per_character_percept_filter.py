from app.models.candidate_percept import CandidatePerceptEvent
from app.models.character_perceived import CharacterPerceivedEvent


def filter_candidate_for_actor(
    candidate: CandidatePerceptEvent, *, actor_id: str
) -> CharacterPerceivedEvent | None:
    if candidate.target_actor_id != "" and candidate.target_actor_id != actor_id:
        return None

    return CharacterPerceivedEvent(
        actor_id=actor_id,
        percept_channel=candidate.percept_channel,
        producer_ts=candidate.producer_ts,
        room_id=candidate.room_id,
        scene_id=candidate.scene_id,
        zone_id=candidate.zone_id,
        perceived_summary=f"{candidate.source_fact_family}/{candidate.source_fact_type}",
        source_candidate_event_id=f"{candidate.source_fact_family}:{candidate.producer_ts}:{actor_id}",
    )
