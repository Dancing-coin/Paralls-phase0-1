from app.models.player_input import InteractIntent
from app.models.world_result import ConstraintStateResult, EnvironmentStateResult, ObjectInteractionResult


class ESMService:
    def resolve_interaction(self, event: InteractIntent, *, is_in_range: bool) -> ObjectInteractionResult | ConstraintStateResult:
        if not is_in_range:
            return ConstraintStateResult(
                room_id=event.room_id,
                source_type="player",
                target_object_id=event.target_object_id,
                result_type="constraint_state_result",
                causation_id=f"interact:{event.producer_ts}",
                producer_ts=event.producer_ts + 1,
                constraint_type="distance",
                constraint_summary="target is too far away",
            )

        return ObjectInteractionResult(
            room_id=event.room_id,
            source_type="player",
            target_object_id=event.target_object_id,
            result_type="object_interaction_result",
            causation_id=f"interact:{event.producer_ts}",
            producer_ts=event.producer_ts + 1,
            interaction_type=event.interaction_type,
            result_summary="object interaction accepted",
            state_changed=True,
        )

    def emit_environment_shift(self, room_id: str, target_environment_id: str, previous_state: str, current_state: str) -> EnvironmentStateResult:
        return EnvironmentStateResult(
            room_id=room_id,
            source_type="system",
            target_environment_id=target_environment_id,
            result_type="environment_state_result",
            causation_id=f"env:{target_environment_id}:{current_state}",
            producer_ts=1,
            previous_state=previous_state,
            current_state=current_state,
            change_summary=f"{target_environment_id} changed from {previous_state} to {current_state}",
        )
