from app.models.runtime_state import ConversationCandidateEvent
from app.models.siming_output import AttentionPrompt
from app.models.visual_fact import VisualFactEvent


class SimingService:
    def evaluate_world_event(self, *, room_id: str, actor_id: str, object_id: str, event_type: str) -> AttentionPrompt:
        summary = f"notice change around {object_id}"
        return AttentionPrompt(
            room_id=room_id,
            output_type="attention_prompt",
            target_actor_id=actor_id,
            target_object_id=object_id,
            causation_id=f"siming:{event_type}:{object_id}",
            producer_ts=1,
            prompt_summary=summary,
        )

    def evaluate_candidate_relationship(self, event: ConversationCandidateEvent) -> AttentionPrompt:
        target_actor_id = event.candidate_actor_ids[0] if event.candidate_actor_ids else None
        target_object_id = event.candidate_object_ids[0] if event.candidate_object_ids else None
        target_environment_id = event.candidate_environment_ids[0] if event.candidate_environment_ids else None
        target_label = target_actor_id or target_object_id or target_environment_id or event.actor_id
        return AttentionPrompt(
            room_id=event.room_id,
            output_type="attention_prompt",
            causation_id=f"siming:{event.causation_id}",
            producer_ts=event.producer_ts + 1,
            target_actor_id=target_actor_id,
            target_environment_id=target_environment_id,
            target_object_id=target_object_id,
            prompt_summary="watch %s" % target_label,
        )

    def evaluate_visual_fact(self, event: VisualFactEvent) -> AttentionPrompt | None:
        if event.fact_type != "light_level_drop":
            return None
        return AttentionPrompt(
            room_id=event.room_id,
            output_type="attention_prompt",
            causation_id=f"siming:{event.fact_type}:{event.target_environment_id or 'env'}",
            producer_ts=event.producer_ts + 1,
            target_actor_id="char_b",
            target_environment_id=event.target_environment_id,
            prompt_summary="notice light drop around %s" % (event.target_environment_id or "environment"),
        )
