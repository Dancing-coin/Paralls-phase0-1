from app.contracts.l1.action_request import ActionRequest
from app.models.environment_request import EnvironmentRequest
from app.models.player_input import InteractIntent
from app.models.environment_field import EnvironmentFieldState
from app.models.state_machine_transition import StateMachineTransitionEvent
from app.models.world_result import (
    ActionResolutionResult,
    BodyStateResult,
    ConstraintStateResult,
    EnvironmentStateResult,
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
            "state_list": [
                {
                    "state_id": "idle",
                    "display_name": "Idle",
                    "is_terminal": False,
                    "is_stable": True,
                    "material_requirements": [],
                },
                {
                    "state_id": "heated",
                    "display_name": "Heated",
                    "is_terminal": False,
                    "is_stable": False,
                    "material_requirements": ["burnable"],
                },
                {
                    "state_id": "burning",
                    "display_name": "Burning",
                    "is_terminal": False,
                    "is_stable": False,
                    "material_requirements": ["burnable"],
                },
                {
                    "state_id": "charred",
                    "display_name": "Charred",
                    "is_terminal": False,
                    "is_stable": True,
                    "material_requirements": ["burnable"],
                },
                {
                    "state_id": "extinguished",
                    "display_name": "Extinguished",
                    "is_terminal": False,
                    "is_stable": True,
                    "material_requirements": ["burnable"],
                },
            ],
            "transition_list": [
                {
                    "from_state": "idle",
                    "to_state": "heated",
                    "trigger_type": "heat_applied",
                    "constraint_checks": ["material_constraint"],
                    "effect_profile": "temperature_rise",
                    "cooldown_ms": 0,
                },
                {
                    "from_state": "heated",
                    "to_state": "burning",
                    "trigger_type": "ignite",
                    "constraint_checks": ["material_constraint"],
                    "effect_profile": "smoke_and_flame",
                    "cooldown_ms": 0,
                },
            ],
            "entry_effects": ["smoke_density_delta"],
            "exit_effects": ["visibility_change"],
            "stable_state_tags": ["idle", "charred", "extinguished"],
        },
        "lock": {
            "machine_id": "lock",
            "entity_type": "object",
            "state_list": [
                {
                    "state_id": "locked",
                    "display_name": "Locked",
                    "is_terminal": False,
                    "is_stable": True,
                    "material_requirements": [],
                },
                {
                    "state_id": "unlocked",
                    "display_name": "Unlocked",
                    "is_terminal": False,
                    "is_stable": True,
                    "material_requirements": [],
                },
                {
                    "state_id": "jammed",
                    "display_name": "Jammed",
                    "is_terminal": False,
                    "is_stable": True,
                    "material_requirements": [],
                },
                {
                    "state_id": "broken",
                    "display_name": "Broken",
                    "is_terminal": True,
                    "is_stable": True,
                    "material_requirements": [],
                },
            ],
            "transition_list": [
                {
                    "from_state": "locked",
                    "to_state": "unlocked",
                    "trigger_type": "unlock",
                    "constraint_checks": ["lock_state_constraint"],
                    "effect_profile": "access_open",
                    "cooldown_ms": 0,
                }
            ],
            "entry_effects": ["lock_feedback"],
            "exit_effects": [],
            "stable_state_tags": ["locked", "unlocked", "jammed", "broken"],
        },
        "visibility": {
            "machine_id": "visibility",
            "entity_type": "object",
            "state_list": [
                {
                    "state_id": "hidden",
                    "display_name": "Hidden",
                    "is_terminal": False,
                    "is_stable": True,
                    "material_requirements": [],
                },
                {
                    "state_id": "partially_visible",
                    "display_name": "Partially Visible",
                    "is_terminal": False,
                    "is_stable": True,
                    "material_requirements": [],
                },
                {
                    "state_id": "visible",
                    "display_name": "Visible",
                    "is_terminal": False,
                    "is_stable": True,
                    "material_requirements": [],
                },
                {
                    "state_id": "removed_from_surface",
                    "display_name": "Removed From Surface",
                    "is_terminal": False,
                    "is_stable": True,
                    "material_requirements": [],
                },
            ],
            "transition_list": [
                {
                    "from_state": "hidden",
                    "to_state": "partially_visible",
                    "trigger_type": "light_level_change",
                    "constraint_checks": ["occlusion_constraint"],
                    "effect_profile": "visibility_raise",
                    "cooldown_ms": 0,
                }
            ],
            "entry_effects": ["visibility_change"],
            "exit_effects": [],
            "stable_state_tags": ["hidden", "partially_visible", "visible", "removed_from_surface"],
        },
        "integrity": {
            "machine_id": "integrity",
            "entity_type": "object",
            "state_list": [
                {
                    "state_id": "intact",
                    "display_name": "Intact",
                    "is_terminal": False,
                    "is_stable": True,
                    "material_requirements": [],
                },
                {
                    "state_id": "disturbed",
                    "display_name": "Disturbed",
                    "is_terminal": False,
                    "is_stable": True,
                    "material_requirements": [],
                },
                {
                    "state_id": "cracked",
                    "display_name": "Cracked",
                    "is_terminal": False,
                    "is_stable": True,
                    "material_requirements": [],
                },
                {
                    "state_id": "broken",
                    "display_name": "Broken",
                    "is_terminal": True,
                    "is_stable": True,
                    "material_requirements": [],
                },
            ],
            "transition_list": [
                {
                    "from_state": "intact",
                    "to_state": "disturbed",
                    "trigger_type": "apply_force",
                    "constraint_checks": ["material_constraint"],
                    "effect_profile": "integrity_loss",
                    "cooldown_ms": 0,
                }
            ],
            "entry_effects": ["integrity_feedback"],
            "exit_effects": [],
            "stable_state_tags": ["intact", "disturbed", "cracked", "broken"],
        },
        "moisture": {
            "machine_id": "moisture",
            "entity_type": "object",
            "state_list": [
                {
                    "state_id": "dry",
                    "display_name": "Dry",
                    "is_terminal": False,
                    "is_stable": True,
                    "material_requirements": [],
                },
                {
                    "state_id": "damp",
                    "display_name": "Damp",
                    "is_terminal": False,
                    "is_stable": False,
                    "material_requirements": ["absorbs_moisture"],
                },
                {
                    "state_id": "wet",
                    "display_name": "Wet",
                    "is_terminal": False,
                    "is_stable": False,
                    "material_requirements": ["absorbs_moisture"],
                },
                {
                    "state_id": "soaked",
                    "display_name": "Soaked",
                    "is_terminal": False,
                    "is_stable": True,
                    "material_requirements": ["absorbs_moisture"],
                },
                {
                    "state_id": "drying",
                    "display_name": "Drying",
                    "is_terminal": False,
                    "is_stable": False,
                    "material_requirements": ["absorbs_moisture"],
                },
            ],
            "transition_list": [
                {
                    "from_state": "dry",
                    "to_state": "damp",
                    "trigger_type": "humidity_rise",
                    "constraint_checks": ["material_constraint"],
                    "effect_profile": "moisture_gain",
                    "cooldown_ms": 0,
                }
            ],
            "entry_effects": ["moisture_feedback"],
            "exit_effects": [],
            "stable_state_tags": ["dry", "soaked"],
        },
    }
    MATERIAL_TEMPLATES: dict[str, dict[str, object]] = {
        "wood": {
            "material_id": "wood",
            "flammability": "medium",
            "charring_rate": "medium",
            "moisture_absorption": "medium",
            "break_resistance": "medium",
        },
        "fabric": {
            "material_id": "fabric",
            "flammability": "high",
            "smoke_factor": "high",
            "moisture_absorption": "high",
            "visibility_occlusion_factor": "medium",
        },
        "metal": {
            "material_id": "metal",
            "heat_transfer_rate": "high",
            "break_resistance": "high",
            "burnable": False,
        },
        "glass": {
            "material_id": "glass",
            "break_threshold": "low",
            "visibility_transparency": "high",
            "burnable": False,
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

    def build_environment_action_request(self, event: EnvironmentRequest) -> ActionRequest:
        target_environment_ids = event.target_entity_refs.get("environment_ids", [])
        target_environment_id = target_environment_ids[0] if target_environment_ids else ""
        return ActionRequest(
            request_id=event.request_id,
            request_type="environment_request",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            actor_id="",
            action_type="environment_request",
            source={
                "layer": str(event.source.get("layer", "L3") or "L3"),
                "system": str(event.source.get("system", "siming.orchestrator") or "siming.orchestrator"),
                "actor_id": str(event.source.get("actor_id", "") or ""),
                "object_id": str(event.source.get("object_id", "") or ""),
            },
            target_entity_refs={
                "actor_ids": list(event.target_entity_refs.get("actor_ids", [])),
                "object_ids": list(event.target_entity_refs.get("object_ids", [])),
                "environment_ids": list(target_environment_ids),
            },
            action_profile=event.requested_change_type,
            intent_strength=event.requested_strength,
            constraints_hint={
                "goal": event.goal,
                "reason_tag": event.reason_tag,
                "decision_ref": event.decision_ref,
                "candidate_ref": event.candidate_ref,
                "ttl": event.ttl,
            },
            producer_ts=event.producer_ts,
            causation_id=event.causation_id,
            correlation_id=event.correlation_id,
            target_environment_id=target_environment_id,
            payload={
                "goal": event.goal,
                "requested_change_type": event.requested_change_type,
                "requested_strength": event.requested_strength,
            },
        )

    def resolve_interaction(
        self,
        event: InteractIntent,
        *,
        is_in_range: bool | None = None,
        actor_position: tuple[float, float, float] | None = None,
    ) -> ActionResolutionResult | ConstraintStateResult:
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
                constraint_type="distance_constraint",
                constraint_code="out_of_range",
                constraint_summary="target is too far away",
                blocking_entity_refs=[event.target_object_id],
                settlement_status="rejected",
            )

        return ActionResolutionResult(
            request_ref=request.request_id,
            result_id=f"action_resolution:{request.request_id}",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            actor_id=event.actor_id,
            source_type="player",
            target_object_id=event.target_object_id,
            result_type="action_resolution_result",
            causation_id=f"interact:{event.producer_ts}",
            correlation_id=f"interact:{event.producer_ts}",
            producer_ts=event.producer_ts + 1,
            resolution_status="accepted",
            resolved_entities=[event.target_object_id],
            applied_state_changes=[
                "object_state_result",
                "body_state_result",
                "environment_state_result",
            ],
            stable_state_summary="interaction accepted",
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
        request_ref: str | None = None,
        causation_id: str | None = None,
        correlation_id: str | None = None,
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
            request_ref=request_ref or f"environment:{target_environment_id}:{producer_ts}",
            result_id=f"environment_result:{target_environment_id}:{producer_ts}",
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            actor_id=actor_id,
            source_type="system",
            target_environment_id=target_environment_id,
            result_type="environment_state_result",
            causation_id=causation_id or f"env:{target_environment_id}:{current_state}",
            correlation_id=correlation_id or f"env:{target_environment_id}:{current_state}",
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

    def resolve_environment_request(
        self,
        event: EnvironmentRequest,
    ) -> tuple[ActionResolutionResult, EnvironmentStateResult]:
        request = self.build_environment_action_request(event)
        target_environment_ids = request.target_entity_refs.get("environment_ids", [])
        target_environment_id = target_environment_ids[0] if target_environment_ids else "env_default"
        resolution = ActionResolutionResult(
            request_ref=request.request_id,
            result_id=f"action_resolution:{request.request_id}",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            actor_id="",
            source_type="system",
            target_environment_id=target_environment_id,
            result_type="action_resolution_result",
            causation_id=event.causation_id,
            correlation_id=event.correlation_id,
            producer_ts=event.producer_ts + 1,
            resolution_status="accepted",
            resolved_entities=[target_environment_id],
            applied_state_changes=["environment_state_result"],
            stable_state_summary="environment_request accepted",
            settlement_status="accepted",
        )
        environment_result = self.emit_environment_shift(
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            actor_id="",
            target_environment_id=target_environment_id,
            previous_state="stable",
            current_state="alerted",
            producer_ts=resolution.producer_ts + 1,
            request_ref=request.request_id,
            causation_id=event.causation_id,
            correlation_id=event.correlation_id,
        )
        return resolution, environment_result

    def emit_action_resolution_result(
        self,
        event: InteractIntent,
        interaction_result: ActionResolutionResult,
    ) -> ActionResolutionResult:
        return ActionResolutionResult(
            request_ref=interaction_result.request_ref,
            result_id=interaction_result.result_id,
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

    def emit_state_machine_transition(
        self,
        *,
        room_id: str,
        scene_id: str,
        zone_id: str,
        entity_id: str,
        machine_id: str,
        from_state: str,
        to_state: str,
        trigger_type: str,
        transition_reason: str,
        producer_ts: int,
        causation_id: str,
        correlation_id: str,
    ) -> StateMachineTransitionEvent:
        return StateMachineTransitionEvent(
            event_id=f"transition:{machine_id}:{entity_id}:{producer_ts}",
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            entity_id=entity_id,
            machine_id=machine_id,
            from_state=from_state,
            to_state=to_state,
            trigger_type=trigger_type,
            transition_reason=transition_reason,
            producer_ts=producer_ts,
            causation_id=causation_id,
            correlation_id=correlation_id,
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
            EnvironmentFieldState(
                field_id=f"field:{room_id}:scene_demo:{zone_id}",
                room_id=room_id,
                zone_id=zone_id,
            ),
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
                field_id=f"field:{room_id}:{scene_id}:{zone_id}",
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
                updated_at=producer_ts,
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
            field_id=f"field:{room_id}:{scene_id}:{zone_id}",
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
            updated_at=producer_ts,
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
