from app.models.player_input import InteractIntent
from app.models.world_result import ConstraintStateResult, EnvironmentStateResult, ObjectInteractionResult


class ESMService:
    INTERACTION_RANGE = 3.0
    OBJECT_POSITIONS: dict[str, tuple[float, float, float]] = {
        "obj_letter": (0.0, 0.95, -2.0),
    }

    def resolve_interaction(
        self,
        event: InteractIntent,
        *,
        is_in_range: bool | None = None,
        actor_position: tuple[float, float, float] | None = None,
    ) -> ObjectInteractionResult | ConstraintStateResult:
        next_is_in_range = is_in_range if is_in_range is not None else self._is_in_range(event.target_object_id, actor_position)
        if not next_is_in_range:
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

    def _is_in_range(self, target_object_id: str, actor_position: tuple[float, float, float] | None) -> bool:
        if actor_position is None:
            return True
        target_position = self.OBJECT_POSITIONS.get(target_object_id)
        if target_position is None:
            return True
        dx = actor_position[0] - target_position[0]
        dy = actor_position[1] - target_position[1]
        dz = actor_position[2] - target_position[2]
        return (dx * dx + dy * dy + dz * dz) ** 0.5 <= self.INTERACTION_RANGE

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
