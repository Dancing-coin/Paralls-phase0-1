from app.models.candidate_percept import CandidatePerceptEvent
from app.models.character_perceived import CharacterPerceivedEvent


def filter_candidate_for_actor(
    candidate: CandidatePerceptEvent,
    *,
    actor_id: str,
    context: dict[str, object] | None = None,
) -> CharacterPerceivedEvent | None:
    if candidate.target_actor_id != "" and candidate.target_actor_id != actor_id:
        return None

    ctx = context or {}
    is_facing_target = bool(ctx.get("is_facing_target", True))
    distance_m = float(ctx.get("distance_m", 0.0) or 0.0)

    if candidate.percept_channel == "visual" and not is_facing_target:
        return None

    clarity_score = 1.0
    certainty_score = 1.0 if distance_m <= 3.0 else 0.6

    return CharacterPerceivedEvent(
        actor_id=actor_id,
        percept_channel=candidate.percept_channel,
        producer_ts=candidate.producer_ts,
        room_id=candidate.room_id,
        scene_id=candidate.scene_id,
        zone_id=candidate.zone_id,
        perceived_summary=f"{candidate.source_fact_family}/{candidate.source_fact_type}",
        source_candidate_event_id=f"{candidate.source_fact_family}:{candidate.producer_ts}:{actor_id}",
        source_actor_id=candidate.source_actor_id,
        target_actor_id=candidate.target_actor_id,
        target_object_id=candidate.target_object_id,
        target_environment_id=candidate.target_environment_id,
        distance_m=distance_m,
        clarity_score=clarity_score,
        certainty_score=certainty_score,
    )
