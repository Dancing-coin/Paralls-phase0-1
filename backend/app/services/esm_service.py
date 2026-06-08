from app.contracts.l1.action_request import ActionRequest
from app.models.player_input import InteractIntent
from app.models.environment_field import EnvironmentFieldState
from app.models.world_result import (
    ActionResolutionResult,
    BodyStateResult,
    ConstraintStateResult,
    EnvironmentStateResult,
    ObjectInteractionResult,
    ObjectStateResult,
)


class ESMService:
    INTERACTION_RANGE = 3.0
    OBJECT_POSITIONS: dict[str, tuple[float, float, float]] = {
        "obj_letter": (0.0, 0.95, -2.0),
    }
    STATE_MACHINE_TEMPLATES: dict[str, dict[str, object]] = {
        "burning": {
            "machine_id": "burning",
            "entity_type": "object",
            "state_list": ["idle", "heated", "burning", "charred", "extinguished"],
        },
        "lock": {
            "machine_id": "lock",
            "entity_type": "object",
            "state_list": ["locked", "unlocked", "jammed", "broken"],
        },
    }
    MATERIAL_TEMPLATES: dict[str, dict[str, object]] = {
        "wood": {
            "material_id": "wood",
            "flammability": "medium",
            "break_resistance": "medium",
        },
        "fabric": {
            "material_id": "fabric",
            "flammability": "high",
            "smoke_factor": "high",
        },
    }

    def __init__(self) -> None:
        self._environment_fields: dict[tuple[str, str], EnvironmentFieldState] = {}

    def build_action_request(self, event: InteractIntent, *, source_system: str = "player_input_bridge") -> ActionRequest:
        request_id = f"interact:{event.producer_ts}:{event.target_object_id}"
        return ActionRequest(
            request_id=request_id,
            request_type="interact",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            actor_id=event.actor_id,
            action_type=event.intent_type,
            source={
                "layer": "L1",
                "system": source_system,
                "actor_id": event.actor_id,
            },
            target_entity_refs={
                "actor_ids": [],
                "object_ids": [event.target_object_id],
                "environment_ids": [],
            },
            action_profile=event.interaction_type,
            intent_strength="normal",
            constraints_hint={},
            producer_ts=event.producer_ts,
            causation_id=f"interact:{event.producer_ts}",
            correlation_id=f"interact:{event.producer_ts}",
            target_object_id=event.target_object_id,
            payload={"interaction_type": event.interaction_type},
        )

    def resolve_interaction(
        self,
        event: InteractIntent,
        *,
        is_in_range: bool | None = None,
        actor_position: tuple[float, float, float] | None = None,
    ) -> ObjectInteractionResult | ConstraintStateResult:
        request = self.build_action_request(event)
        next_is_in_range = is_in_range if is_in_range is not None else self._is_in_range(event.target_object_id, actor_position)
        if not next_is_in_range:
            return ConstraintStateResult(
                request_ref=request.request_id,
                result_id=f"constraint:{request.request_id}",
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
                constraint_code="distance_constraint",
                constraint_summary="target is too far away",
                blocking_entity_refs=[event.target_object_id],
                settlement_status="rejected",
            )

        return ObjectInteractionResult(
            request_ref=request.request_id,
            result_id=f"resolution:{request.request_id}",
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
            resolved_entities=[event.target_object_id],
            applied_state_changes=["object_interaction_result"],
            stable_state_summary="object_interaction accepted",
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
            scene_id=scene_id,
            zone_id=zone_id,
            target_environment_id=target_environment_id,
            current_state=current_state,
            producer_ts=producer_ts,
        )
        return EnvironmentStateResult(
            request_ref=f"environment:{target_environment_id}:{producer_ts}",
            result_id=f"environment_result:{target_environment_id}:{producer_ts}",
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
            affected_zone_ids=[zone_id],
            field_delta_summary=["light_level", "noise_level", "smoke_density", "visibility_level"],
            temperature=field_state.temperature,
            humidity=field_state.humidity,
            smoke_density=field_state.smoke_density,
            light_level=field_state.light_level,
            noise_level=field_state.noise_level,
            visibility_level=field_state.visibility_level,
            settlement_status="applied",
        )

    def emit_action_resolution_result(
        self,
        event: InteractIntent,
        interaction_result: ObjectInteractionResult,
    ) -> ActionResolutionResult:
        return ActionResolutionResult(
            request_ref=interaction_result.request_ref,
            result_id=f"action_resolution:{interaction_result.request_ref}",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            actor_id=event.actor_id,
            source_type="system",
            target_object_id=event.target_object_id,
            causation_id=interaction_result.causation_id,
            correlation_id=interaction_result.correlation_id,
            producer_ts=interaction_result.producer_ts,
            settlement_status=interaction_result.settlement_status,
            resolution_status=interaction_result.resolution_status,
            resolved_entities=list(interaction_result.resolved_entities),
            applied_state_changes=list(interaction_result.applied_state_changes),
            stable_state_summary=interaction_result.stable_state_summary,
        )

    def emit_object_state_result(
        self,
        *,
        room_id: str,
        scene_id: str,
        zone_id: str,
        actor_id: str,
        target_object_id: str,
        previous_state: str,
        current_state: str,
        producer_ts: int,
    ) -> ObjectStateResult:
        return ObjectStateResult(
            request_ref=f"object:{target_object_id}:{producer_ts}",
            result_id=f"object_result:{target_object_id}:{producer_ts}",
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            actor_id=actor_id,
            source_type="system",
            target_object_id=target_object_id,
            causation_id=f"object:{target_object_id}:{producer_ts}",
            correlation_id=f"object:{target_object_id}:{producer_ts}",
            producer_ts=producer_ts,
            previous_state=previous_state,
            current_state=current_state,
            change_summary=f"{target_object_id} changed from {previous_state} to {current_state}",
            settlement_status="applied",
        )

    def emit_body_state_result(
        self,
        *,
        room_id: str,
        scene_id: str,
        zone_id: str,
        actor_id: str,
        body_state_class: str,
        previous_state: str,
        current_state: str,
        producer_ts: int,
    ) -> BodyStateResult:
        return BodyStateResult(
            request_ref=f"body:{actor_id}:{producer_ts}",
            result_id=f"body_result:{actor_id}:{producer_ts}",
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            actor_id=actor_id,
            source_type="system",
            causation_id=f"body:{actor_id}:{producer_ts}",
            correlation_id=f"body:{actor_id}:{producer_ts}",
            producer_ts=producer_ts,
            body_state_class=body_state_class,
            previous_state=previous_state,
            current_state=current_state,
            change_summary=f"{body_state_class} changed from {previous_state} to {current_state}",
            settlement_status="applied",
        )

    def get_environment_field(self, room_id: str, zone_id: str) -> EnvironmentFieldState:
        return self._environment_fields.get(
            (room_id, zone_id),
            EnvironmentFieldState(room_id=room_id, zone_id=zone_id),
        )

    def get_state_machine_template(self, machine_id: str) -> dict[str, object]:
        return self.STATE_MACHINE_TEMPLATES[machine_id]

    def get_material_template(self, material_id: str) -> dict[str, object]:
        return self.MATERIAL_TEMPLATES[material_id]

    def propagate_environment_field_to_adjacent_zones(
        self,
        *,
        room_id: str,
        scene_id: str,
        source_zone_id: str,
        adjacent_zone_ids: list[str],
        producer_ts: int,
    ) -> dict[str, EnvironmentFieldState]:
        source = self.get_environment_field(room_id, source_zone_id)
        propagated: dict[str, EnvironmentFieldState] = {}
        for zone_id in adjacent_zone_ids:
            field = EnvironmentFieldState(
                room_id=room_id,
                scene_id=scene_id,
                zone_id=zone_id,
                temperature=source.temperature,
                humidity=source.humidity,
                smoke_density=self._propagate_smoke_density(source.smoke_density),
                light_level=source.light_level,
                noise_level=self._propagate_noise_level(source.noise_level),
                visibility_level=self._propagate_visibility_level(source.visibility_level),
                producer_ts=producer_ts,
                source_environment_id=source.source_environment_id,
            )
            self._environment_fields[(room_id, zone_id)] = field
            propagated[zone_id] = field
        return propagated

    def _update_environment_field(
        self,
        *,
        room_id: str,
        scene_id: str,
        zone_id: str,
        target_environment_id: str,
        current_state: str,
        producer_ts: int,
    ) -> EnvironmentFieldState:
        temperature = "ambient"
        humidity = "stable"
        smoke_density = "clear"
        light_level = "normal"
        noise_level = "quiet"
        visibility_level = "clear"
        if current_state == "alerted":
            light_level = "low"
            noise_level = "elevated"
            smoke_density = "light"
            visibility_level = "reduced"

        field_state = EnvironmentFieldState(
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            temperature=temperature,
            humidity=humidity,
            smoke_density=smoke_density,
            light_level=light_level,
            noise_level=noise_level,
            visibility_level=visibility_level,
            producer_ts=producer_ts,
            source_environment_id=target_environment_id,
        )
        self._environment_fields[(room_id, zone_id)] = field_state
        return field_state

    def _propagate_noise_level(self, level: str) -> str:
        if level == "elevated":
            return "moderate"
        return level

    def _propagate_smoke_density(self, density: str) -> str:
        if density == "light":
            return "trace"
        return density

    def _propagate_visibility_level(self, level: str) -> str:
        if level == "reduced":
            return "soft_reduced"
        return level
