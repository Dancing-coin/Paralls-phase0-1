from app.models.player_input import InteractIntent
from app.models.environment_field import EnvironmentFieldState
from app.models.world_result import ConstraintStateResult, EnvironmentStateResult, ObjectInteractionResult


class ESMService:
    INTERACTION_RANGE = 3.0
    OBJECT_POSITIONS: dict[str, tuple[float, float, float]] = {
        "obj_letter": (0.0, 0.95, -2.0),
    }

    def __init__(self) -> None:
        self._environment_fields: dict[tuple[str, str], EnvironmentFieldState] = {}

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
                scene_id=event.scene_id,
                zone_id=event.zone_id,
                actor_id=event.actor_id,
                source_type="player",
                target_object_id=event.target_object_id,
                result_type="constraint_state_result",
                causation_id=f"interact:{event.producer_ts}",
                correlation_id=f"interact:{event.producer_ts}",
                producer_ts=event.producer_ts + 1,
                constraint_type="distance",
                constraint_summary="target is too far away",
                settlement_status="rejected",
            )

        return ObjectInteractionResult(
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            actor_id=event.actor_id,
            source_type="player",
            target_object_id=event.target_object_id,
            result_type="object_interaction_result",
            causation_id=f"interact:{event.producer_ts}",
            correlation_id=f"interact:{event.producer_ts}",
            producer_ts=event.producer_ts + 1,
            interaction_type=event.interaction_type,
            result_summary="object interaction accepted",
            state_changed=True,
            settlement_status="accepted",
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

    def emit_environment_shift(
        self,
        room_id: str,
        target_environment_id: str,
        previous_state: str,
        current_state: str,
        *,
        scene_id: str = "scene_demo",
        zone_id: str = "zone_focus",
        actor_id: str = "",
        producer_ts: int = 1,
    ) -> EnvironmentStateResult:
        field_state = self._update_environment_field(
            room_id=room_id,
            zone_id=zone_id,
            target_environment_id=target_environment_id,
            current_state=current_state,
            producer_ts=producer_ts,
        )
        return EnvironmentStateResult(
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            actor_id=actor_id,
            source_type="system",
            target_environment_id=target_environment_id,
            result_type="environment_state_result",
            causation_id=f"env:{target_environment_id}:{current_state}",
            correlation_id=f"env:{target_environment_id}:{current_state}",
            producer_ts=producer_ts,
            previous_state=previous_state,
            current_state=current_state,
            change_summary=f"{target_environment_id} changed from {previous_state} to {current_state}",
            light_level=field_state.light_level,
            noise_level=field_state.noise_level,
            settlement_status="applied",
        )

    def get_environment_field(self, room_id: str, zone_id: str) -> EnvironmentFieldState:
        return self._environment_fields.get(
            (room_id, zone_id),
            EnvironmentFieldState(room_id=room_id, zone_id=zone_id),
        )

    def _update_environment_field(
        self,
        *,
        room_id: str,
        zone_id: str,
        target_environment_id: str,
        current_state: str,
        producer_ts: int,
    ) -> EnvironmentFieldState:
        light_level = "normal"
        noise_level = "quiet"
        if current_state == "alerted":
            light_level = "low"
            noise_level = "elevated"

        field_state = EnvironmentFieldState(
            room_id=room_id,
            zone_id=zone_id,
            light_level=light_level,
            noise_level=noise_level,
            producer_ts=producer_ts,
            source_environment_id=target_environment_id,
        )
        self._environment_fields[(room_id, zone_id)] = field_state
        return field_state
