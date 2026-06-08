from app.models.candidate_percept import CandidatePerceptEvent
from app.models.raw_fact import RawFactEvent

AUDITORY_CANDIDATE_POLICY = "l1_only"


def compile_candidate_percepts(event: RawFactEvent) -> list[CandidatePerceptEvent]:
    if event.fact_family == "auditory_fact":
        return []

    if event.fact_family == "visual_fact":
        return [
            CandidatePerceptEvent(
                percept_channel="visual",
                source_fact_family=event.fact_family,
                source_fact_type=event.fact_type,
                producer_ts=event.producer_ts,
                room_id=event.room_id,
                scene_id=event.scene_id,
                zone_id=event.zone_id,
                source_actor_id=event.source.actor_id,
                source_object_id=event.source.object_id,
                source_environment_id=event.source.environment_id,
                target_actor_id=event.targets.actor_id,
                target_object_id=event.targets.object_id,
                target_environment_id=event.targets.environment_id,
                audience_scope="candidate",
                observability=event.observability.model_dump(),
                causation_id=event.causation_id,
                correlation_id=event.correlation_id,
            )
        ]

    if event.fact_family == "spatial_access_fact":
        return [
            CandidatePerceptEvent(
                percept_channel="spatial",
                source_fact_family=event.fact_family,
                source_fact_type=event.fact_type,
                producer_ts=event.producer_ts,
                room_id=event.room_id,
                scene_id=event.scene_id,
                zone_id=event.zone_id,
                source_actor_id=event.source.actor_id,
                source_object_id=event.source.object_id,
                source_environment_id=event.source.environment_id,
                target_actor_id=event.targets.actor_id,
                target_object_id=event.targets.object_id,
                target_environment_id=event.targets.environment_id,
                audience_scope="candidate",
                observability=event.observability.model_dump(),
                causation_id=event.causation_id,
                correlation_id=event.correlation_id,
            )
        ]

    return []
