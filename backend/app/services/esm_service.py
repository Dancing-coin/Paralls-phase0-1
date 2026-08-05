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
    WORKBENCH_HISTORY_LIMIT = 2
    SUPPORTED_ENVIRONMENT_CHANGE_TYPES = {"light_level_drop", "light_level_restore", "thermal_level_rise", "smoke_density_rise", "noise_level_rise"}
    UNSUPPORTED_ENVIRONMENT_CHANGE_TYPES = {"thermal_spike"}
    OBJECT_POSITIONS: dict[str, tuple[float, float, float]] = {
        "obj_letter": (0.0, 0.95, -2.0),
        "obj_plaque": (-2.2, 1.2, -2.0),
        "obj_lamp_switch": (2.2, 1.2, -2.0),
        "obj_archive_door": (0.0, 1.2, -4.0),
        "obj_worktable": (-0.9, 0.85, -2.0),
        "obj_observation_bench": (15.4, 0.7, -6.6),
    }
    # An interaction target is not authoritative merely because a Godot node
    # names it. The main demo's small policy catalog keeps the authority
    # boundary explicit while broader object-family ownership is still pending.
    INTERACTION_POLICIES: dict[str, dict[str, object]] = {
        "obj_letter": {
            "allowed_interactions": {"inspect", "read", "destroy"},
            "machine_id": "visibility",
            "affordances": ["inspect", "read"],
            "occludes": False,
            "environment_transition": "alert_lamp",
            "initial_state": "partially_visible",
            "stateful": True,
            "transitions": {
                "inspect": {
                    "previous_state": "partially_visible",
                    "current_state": "visible",
                },
                "read": {
                    "previous_state": "partially_visible",
                    "current_state": "visible",
                },
                "destroy": {
                    "previous_state": "visible",
                    "current_state": "removed_from_surface",
                },
            },
        },
        "obj_plaque": {
            "allowed_interactions": {"inspect", "read"},
            "machine_id": "visibility",
            "previous_state": "partially_visible",
            "current_state": "visible",
            "affordances": ["inspect", "read"],
            "occludes": False,
            "environment_transition": "none",
        },
        "obj_lamp_switch": {
            "allowed_interactions": {"press"},
            "machine_id": "switch",
            "previous_state": "idle",
            "current_state": "activated",
            "affordances": ["press"],
            "occludes": False,
            "environment_transition": "alert_lamp",
        },
        "obj_archive_door": {
            "allowed_interactions": {"open", "close"},
            "machine_id": "door",
            "affordances": ["open", "close"],
            "occludes": False,
            "environment_transition": "none",
            "initial_state": "closed",
            "stateful": True,
            "transitions": {
                "open": {"previous_state": "closed", "current_state": "open"},
                "close": {"previous_state": "open", "current_state": "closed"},
            },
        },
        "obj_worktable": {
            "allowed_interactions": {"use", "finish_use"},
            "machine_id": "work_surface",
            "affordances": ["use", "finish_use"],
            "occludes": False,
            "environment_transition": "none",
            "initial_state": "ready",
            "stateful": True,
            "transitions": {
                "use": {"previous_state": "ready", "current_state": "engaged"},
                "finish_use": {"previous_state": "engaged", "current_state": "ready"},
            },
        },
        "obj_observation_bench": {
            "allowed_interactions": {"sit", "stand"},
            "machine_id": "seat_occupancy",
            "affordances": ["sit", "stand"],
            "occludes": False,
            "environment_transition": "none",
            "initial_state": "available",
            "stateful": True,
            "actor_scoped": True,
            "transitions": {
                "sit": {
                    "previous_state": "available",
                    "current_state": "occupied",
                    "owner_requirement": "unclaimed",
                    "owner_effect": "claim",
                    "body_state_class": "posture",
                    "body_previous_state": "standing",
                    "body_current_state": "seated",
                },
                "stand": {
                    "previous_state": "occupied",
                    "current_state": "available",
                    "owner_requirement": "actor_is_owner",
                    "owner_effect": "release",
                    "body_state_class": "posture",
                    "body_previous_state": "seated",
                    "body_current_state": "standing",
                },
            },
        },
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
        "light_source": {
            "machine_id": "light_source",
            "entity_type": "environment",
            "state_list": [
                {
                    "state_id": "stable",
                    "display_name": "Stable",
                    "is_terminal": False,
                    "is_stable": True,
                    "material_requirements": [],
                },
                {
                    "state_id": "alerted",
                    "display_name": "Alerted",
                    "is_terminal": False,
                    "is_stable": False,
                    "material_requirements": [],
                },
            ],
            "transition_list": [
                {
                    "from_state": "stable",
                    "to_state": "alerted",
                    "trigger_type": "environment_request.light_level_drop",
                    "constraint_checks": [],
                    "effect_profile": "visibility_reduction",
                    "cooldown_ms": 0,
                },
                {
                    "from_state": "alerted",
                    "to_state": "stable",
                    "trigger_type": "environment_request.light_level_restore",
                    "constraint_checks": [],
                    "effect_profile": "visibility_restore",
                    "cooldown_ms": 0,
                }
            ],
            "entry_effects": ["light_level_delta", "visibility_change"],
            "exit_effects": [],
            "stable_state_tags": ["stable"],
        },
        "heat_source": {
            "machine_id": "heat_source",
            "entity_type": "environment",
            "state_list": [
                {
                    "state_id": "stable",
                    "display_name": "Stable",
                    "is_terminal": False,
                    "is_stable": True,
                    "material_requirements": [],
                },
                {
                    "state_id": "heated",
                    "display_name": "Heated",
                    "is_terminal": False,
                    "is_stable": False,
                    "material_requirements": [],
                },
            ],
            "transition_list": [
                {
                    "from_state": "stable",
                    "to_state": "heated",
                    "trigger_type": "environment_request.thermal_level_rise",
                    "constraint_checks": [],
                    "effect_profile": "thermal_rise",
                    "cooldown_ms": 0,
                }
            ],
            "entry_effects": ["thermal_level_delta"],
            "exit_effects": [],
            "stable_state_tags": ["stable"],
        },
        "smoke_source": {
            "machine_id": "smoke_source",
            "entity_type": "environment",
            "state_list": [
                {
                    "state_id": "stable",
                    "display_name": "Stable",
                    "is_terminal": False,
                    "is_stable": True,
                    "material_requirements": [],
                },
                {
                    "state_id": "smoke_rising",
                    "display_name": "Smoke Rising",
                    "is_terminal": False,
                    "is_stable": False,
                    "material_requirements": [],
                },
            ],
            "transition_list": [
                {
                    "from_state": "stable",
                    "to_state": "smoke_rising",
                    "trigger_type": "environment_request.smoke_density_rise",
                    "constraint_checks": [],
                    "effect_profile": "smoke_density_rise",
                    "cooldown_ms": 0,
                }
            ],
            "entry_effects": ["smoke_density_delta", "visibility_change"],
            "exit_effects": [],
            "stable_state_tags": ["stable"],
        },
        "noise_source": {
            "machine_id": "noise_source",
            "entity_type": "environment",
            "state_list": [
                {
                    "state_id": "stable",
                    "display_name": "Stable",
                    "is_terminal": False,
                    "is_stable": True,
                    "material_requirements": [],
                },
                {
                    "state_id": "noisy",
                    "display_name": "Noisy",
                    "is_terminal": False,
                    "is_stable": False,
                    "material_requirements": [],
                },
            ],
            "transition_list": [
                {
                    "from_state": "stable",
                    "to_state": "noisy",
                    "trigger_type": "environment_request.noise_level_rise",
                    "constraint_checks": [],
                    "effect_profile": "noise_rise",
                    "cooldown_ms": 0,
                }
            ],
            "entry_effects": ["noise_level_delta"],
            "exit_effects": [],
            "stable_state_tags": ["stable"],
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
        self._latest_environment_result: EnvironmentStateResult | None = None
        self._latest_state_machine_transition: StateMachineTransitionEvent | None = None
        self._latest_environment_request: ActionRequest | None = None
        self._latest_environment_resolution: ActionResolutionResult | ConstraintStateResult | None = None
        self._recent_environment_requests: list[ActionRequest] = []
        self._recent_environment_resolutions: list[ActionResolutionResult | ConstraintStateResult] = []
        self._recent_environment_results: list[EnvironmentStateResult] = []
        self._recent_state_machine_transitions: list[StateMachineTransitionEvent] = []
        self._registered_interaction_states: dict[tuple[str, str, str, str], str] = {}
        self._registered_interaction_owners: dict[tuple[str, str, str, str], str] = {}

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
                entity_id=event.target_object_id,
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
            entity_id=event.target_object_id,
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

    def interaction_policy_for(
        self,
        target_object_id: str,
        interaction_type: str,
        *,
        room_id: str = "",
        scene_id: str = "",
        zone_id: str = "",
        actor_id: str = "",
    ) -> dict[str, object] | None:
        policy = self.INTERACTION_POLICIES.get(target_object_id)
        if policy is None:
            return None
        allowed_interactions = policy.get("allowed_interactions", set())
        if interaction_type not in allowed_interactions:
            return None
        if not bool(policy.get("stateful", False)):
            return policy
        transitions = policy.get("transitions", {})
        transition = transitions.get(interaction_type) if isinstance(transitions, dict) else None
        if not isinstance(transition, dict):
            return None
        initial_state = str(policy.get("initial_state", ""))
        actual_state = self.interaction_state_for(
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            target_object_id=target_object_id,
            initial_state=initial_state,
        )
        resolved_policy = {key: value for key, value in policy.items() if key != "transitions"}
        resolved_policy.update(transition)
        resolved_policy["state_match"] = actual_state == str(transition["previous_state"])
        owner_requirement = str(transition.get("owner_requirement", ""))
        if owner_requirement:
            actual_owner = self.interaction_owner_for(
                room_id=room_id,
                scene_id=scene_id,
                zone_id=zone_id,
                target_object_id=target_object_id,
            )
            resolved_policy["owner_match"] = (
                actual_owner == ""
                if owner_requirement == "unclaimed"
                else bool(actor_id) and actual_owner == actor_id
                if owner_requirement == "actor_is_owner"
                else False
            )
        return resolved_policy

    def interaction_state_for(
        self,
        *,
        room_id: str,
        scene_id: str,
        zone_id: str,
        target_object_id: str,
        initial_state: str | None = None,
    ) -> str:
        policy = self.INTERACTION_POLICIES.get(target_object_id, {})
        fallback = initial_state if initial_state is not None else str(policy.get("initial_state", ""))
        return self._registered_interaction_states.get(
            (room_id, scene_id, zone_id, target_object_id),
            fallback,
        )

    def interaction_owner_for(
        self,
        *,
        room_id: str,
        scene_id: str,
        zone_id: str,
        target_object_id: str,
    ) -> str:
        return self._registered_interaction_owners.get(
            (room_id, scene_id, zone_id, target_object_id),
            "",
        )

    def commit_interaction_state(
        self,
        *,
        room_id: str,
        scene_id: str,
        zone_id: str,
        target_object_id: str,
        current_state: str,
        actor_id: str = "",
        interaction_type: str = "",
    ) -> None:
        policy = self.INTERACTION_POLICIES.get(target_object_id)
        if policy is None or not bool(policy.get("stateful", False)):
            return
        state_key = (room_id, scene_id, zone_id, target_object_id)
        self._registered_interaction_states[state_key] = current_state
        if not bool(policy.get("actor_scoped", False)):
            return
        transitions = policy.get("transitions", {})
        transition = transitions.get(interaction_type) if isinstance(transitions, dict) else None
        owner_effect = str(transition.get("owner_effect", "")) if isinstance(transition, dict) else ""
        if owner_effect == "claim" and actor_id:
            self._registered_interaction_owners[state_key] = actor_id
        elif owner_effect == "release":
            self._registered_interaction_owners.pop(state_key, None)

    def reject_unsupported_interaction(self, event: InteractIntent) -> ConstraintStateResult:
        request = self.build_action_request(event)
        object_known = event.target_object_id in self.INTERACTION_POLICIES
        return ConstraintStateResult(
            request_ref=request.request_id,
            result_id=f"constraint:{request.request_id}",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            actor_id=event.actor_id,
            source_type="player",
            entity_id=event.target_object_id,
            target_object_id=event.target_object_id,
            result_type="constraint_state_result",
            causation_id=f"interact:{event.producer_ts}",
            correlation_id=f"interact:{event.producer_ts}",
            producer_ts=event.producer_ts + 1,
            constraint_type="interaction_policy_constraint",
            constraint_code="unsupported_interaction" if object_known else "unsupported_object",
            constraint_summary=(
                "interaction is not allowed for this target"
                if object_known
                else "target is not registered by the authority interaction policy"
            ),
            blocking_entity_refs=[event.target_object_id],
            settlement_status="rejected",
        )

    def reject_interaction_state(
        self,
        event: InteractIntent,
        *,
        expected_state: str,
        actual_state: str,
    ) -> ConstraintStateResult:
        request = self.build_action_request(event)
        return ConstraintStateResult(
            request_ref=request.request_id,
            result_id=f"constraint:{request.request_id}",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            actor_id=event.actor_id,
            source_type="player",
            entity_id=event.target_object_id,
            target_object_id=event.target_object_id,
            result_type="constraint_state_result",
            causation_id=f"interact:{event.producer_ts}",
            correlation_id=f"interact:{event.producer_ts}",
            producer_ts=event.producer_ts + 1,
            constraint_type="interaction_state_constraint",
            constraint_code="invalid_interaction_state",
            constraint_summary=f"interaction requires {expected_state}; current state is {actual_state}",
            blocking_entity_refs=[event.target_object_id],
            settlement_status="rejected",
        )

    def reject_interaction_owner(
        self,
        event: InteractIntent,
        *,
        expected_owner: str,
        actual_owner: str,
    ) -> ConstraintStateResult:
        request = self.build_action_request(event)
        return ConstraintStateResult(
            request_ref=request.request_id,
            result_id=f"constraint:{request.request_id}",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            actor_id=event.actor_id,
            source_type="player",
            entity_id=event.target_object_id,
            target_object_id=event.target_object_id,
            result_type="constraint_state_result",
            causation_id=f"interact:{event.producer_ts}",
            correlation_id=f"interact:{event.producer_ts}",
            producer_ts=event.producer_ts + 1,
            constraint_type="interaction_owner_constraint",
            constraint_code="interaction_owner_mismatch",
            constraint_summary=f"interaction requires owner {expected_owner}; current owner is {actual_owner or 'none'}",
            blocking_entity_refs=[event.target_object_id],
            settlement_status="rejected",
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
        machine_id: str = "light_source",
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
        result = EnvironmentStateResult(
            request_ref=request_ref or f"environment:{target_environment_id}:{producer_ts}",
            result_id=f"environment_result:{target_environment_id}:{producer_ts}",
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            actor_id=actor_id,
            source_type="system",
            entity_id=target_environment_id,
            target_environment_id=target_environment_id,
            result_type="environment_state_result",
            machine_id=machine_id,
            causation_id=causation_id or f"env:{target_environment_id}:{current_state}",
            correlation_id=correlation_id or f"env:{target_environment_id}:{current_state}",
            producer_ts=producer_ts,
            previous_state=previous_state,
            current_state=current_state,
            change_summary=f"{target_environment_id} changed from {previous_state} to {current_state}",
            field_id=field_state.field_id,
            source_environment_id=field_state.source_environment_id,
            affected_zone_ids=[zone_id],
            field_delta_summary=["light_level", "noise_level", "thermal_level", "smoke_density", "visibility_level"],
            temperature=field_state.temperature,
            humidity=field_state.humidity,
            smoke_density=field_state.smoke_density,
            light_level=field_state.light_level,
            noise_level=field_state.noise_level,
            thermal_level=field_state.thermal_level,
            visibility_level=field_state.visibility_level,
            updated_at=field_state.updated_at,
            settlement_status="applied",
        )
        self._latest_environment_result = result
        self._push_history(self._recent_environment_results, result)
        return result

    def resolve_environment_request(
        self,
        event: EnvironmentRequest,
    ) -> tuple[ActionResolutionResult | ConstraintStateResult, EnvironmentStateResult | None]:
        request = self.build_environment_action_request(event)
        self._latest_environment_request = request
        self._push_history(self._recent_environment_requests, request)
        target_environment_ids = request.target_entity_refs.get("environment_ids", [])
        target_environment_id = target_environment_ids[0] if target_environment_ids else "env_default"
        if event.requested_change_type not in self.SUPPORTED_ENVIRONMENT_CHANGE_TYPES:
            resolution = ConstraintStateResult(
                    request_ref=request.request_id,
                    result_id=f"constraint:{request.request_id}",
                    room_id=event.room_id,
                    scene_id=event.scene_id,
                    zone_id=event.zone_id,
                    actor_id="",
                    source_type="system",
                    entity_id=target_environment_id,
                    target_environment_id=target_environment_id,
                    result_type="constraint_state_result",
                    causation_id=event.causation_id,
                    correlation_id=event.correlation_id,
                    producer_ts=event.producer_ts + 1,
                    constraint_type="unsupported_environment_request",
                    constraint_code="unsupported_change_type",
                    constraint_summary=f"unsupported environment change type: {event.requested_change_type}",
                    blocking_entity_refs=[target_environment_id],
                    settlement_status="rejected",
            )
            self._latest_environment_resolution = resolution
            self._push_history(self._recent_environment_resolutions, resolution)
            return resolution, None
        resolved_state = "alerted"
        machine_id = "light_source"
        previous_state = "stable"
        if event.requested_change_type == "light_level_restore":
            resolved_state = "stable"
            machine_id = "light_source"
            previous_state = "alerted"
        elif event.requested_change_type == "thermal_level_rise":
            resolved_state = "heated"
            machine_id = "heat_source"
        elif event.requested_change_type == "smoke_density_rise":
            resolved_state = "smoke_rising"
            machine_id = "smoke_source"
        elif event.requested_change_type == "noise_level_rise":
            resolved_state = "noisy"
            machine_id = "noise_source"

        resolution = ActionResolutionResult(
            request_ref=request.request_id,
            result_id=f"action_resolution:{request.request_id}",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            actor_id="",
            source_type="system",
            entity_id=target_environment_id,
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
        self._latest_environment_resolution = resolution
        self._push_history(self._recent_environment_resolutions, resolution)
        environment_result = self.emit_environment_shift(
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            actor_id="",
            target_environment_id=target_environment_id,
            previous_state=previous_state,
            current_state=resolved_state,
            machine_id=machine_id,
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
            entity_id=event.target_object_id,
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
        transition = StateMachineTransitionEvent(
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
        self._latest_state_machine_transition = transition
        self._push_history(self._recent_state_machine_transitions, transition)
        return transition

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
        machine_id: str = "visibility",
        producer_ts: int,
        request_ref: str | None = None,
        causation_id: str | None = None,
        correlation_id: str | None = None,
    ) -> ObjectStateResult:
        return ObjectStateResult(
            request_ref=request_ref or f"object:{target_object_id}:{producer_ts}",
            result_id=f"object_result:{target_object_id}:{producer_ts}",
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            actor_id=actor_id,
            source_type="system",
            entity_id=target_object_id,
            target_object_id=target_object_id,
            machine_id=machine_id,
            causation_id=causation_id or f"object:{target_object_id}:{producer_ts}",
            correlation_id=correlation_id or f"object:{target_object_id}:{producer_ts}",
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
        request_ref: str | None = None,
        causation_id: str | None = None,
        correlation_id: str | None = None,
    ) -> BodyStateResult:
        return BodyStateResult(
            request_ref=request_ref or f"body:{actor_id}:{producer_ts}",
            result_id=f"body_result:{actor_id}:{producer_ts}",
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            actor_id=actor_id,
            source_type="system",
            causation_id=causation_id or f"body:{actor_id}:{producer_ts}",
            correlation_id=correlation_id or f"body:{actor_id}:{producer_ts}",
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

    def get_repo_local_capabilities(self) -> dict[str, object]:
        return {
            "supported_settlement_classes": [
                "interaction_success",
                "interaction_rejection_by_constraint",
                "environment_state_shift",
            ],
            "supported_constraint_classes": [
                "distance_constraint",
                "unsupported_environment_request",
            ],
            "supported_environment_change_types": sorted(self.SUPPORTED_ENVIRONMENT_CHANGE_TYPES),
            "unsupported_environment_change_types": sorted(self.UNSUPPORTED_ENVIRONMENT_CHANGE_TYPES),
            "supported_environment_fields": [
                "light_level",
                "noise_level",
                "thermal_level",
                "smoke_density",
                "visibility_level",
            ],
            "environment_machine_ids": ["heat_source", "light_source", "noise_source", "smoke_source"],
            "environment_field_semantics": {
                "light_level": "real_but_coarse",
                "noise_level": "real_but_coarse",
                "thermal_level": "real_but_coarse",
                "smoke_density": "real_but_coarse",
                "visibility_level": "real_but_coarse",
            },
            "environment_request_policy": {
                "supported_change_type_behavior": "accept_and_emit_environment_state_result",
                "unsupported_change_type_behavior": "reject_constraint_state_result",
            },
            "environment_request_variant_policy": {
                "supported_families": [
                    "visibility_change",
                    "thermal_change",
                    "smoke_change",
                ],
                "unsupported_families": [
                    "humidity_change",
                    "integrity_change",
                    "material_change",
                ],
                "current_supported_change_types": sorted(self.SUPPORTED_ENVIRONMENT_CHANGE_TYPES),
            },
        }

    def get_repo_local_workbench_snapshot(
        self,
        *,
        room_id: str,
        scene_id: str,
        zone_id: str,
    ) -> dict[str, object]:
        field_state = self.get_environment_field(room_id, zone_id)
        capabilities = self.get_repo_local_capabilities()
        return {
            "room_id": room_id,
            "scene_id": scene_id,
            "zone_id": zone_id,
            "state_machine_template_ids": sorted(self.STATE_MACHINE_TEMPLATES.keys()),
            "material_template_ids": sorted(self.MATERIAL_TEMPLATES.keys()),
            "environment_machine_ids": capabilities["environment_machine_ids"],
            "supported_environment_change_types": capabilities["supported_environment_change_types"],
            "unsupported_environment_change_types": capabilities["unsupported_environment_change_types"],
            "current_environment_field": field_state.model_dump(),
            "latest_environment_request": self._latest_environment_request.model_dump() if self._latest_environment_request is not None else None,
            "latest_environment_resolution": self._latest_environment_resolution.model_dump() if self._latest_environment_resolution is not None else None,
            "latest_environment_result": self._latest_environment_result.model_dump() if self._latest_environment_result is not None else None,
            "latest_state_machine_transition": self._latest_state_machine_transition.model_dump() if self._latest_state_machine_transition is not None else None,
            "recent_environment_requests": [entry.model_dump() for entry in self._recent_environment_requests],
            "recent_environment_resolutions": [entry.model_dump() for entry in self._recent_environment_resolutions],
            "recent_environment_results": [entry.model_dump() for entry in self._recent_environment_results],
            "recent_state_machine_transitions": [entry.model_dump() for entry in self._recent_state_machine_transitions],
        }

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
                thermal_level=self._propagate_thermal_level(source.thermal_level),
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
        thermal_level = "neutral"
        humidity = "stable"
        smoke_density = "clear"
        light_level = "normal"
        noise_level = "quiet"
        visibility_level = "clear"
        if current_state == "alerted":
            light_level = "low"
            noise_level = "elevated"
            thermal_level = "warm"
            smoke_density = "light"
            visibility_level = "reduced"
        elif current_state == "heated":
            thermal_level = "hot"
        elif current_state == "smoke_rising":
            smoke_density = "dense"
            visibility_level = "reduced"
        elif current_state == "noisy":
            noise_level = "loud"

        field_state = EnvironmentFieldState(
            field_id=f"field:{room_id}:{scene_id}:{zone_id}",
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            temperature=temperature,
            thermal_level=thermal_level,
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

    def _propagate_thermal_level(self, level: str) -> str:
        if level == "warm":
            return "mild_warm"
        return level

    def _propagate_visibility_level(self, level: str) -> str:
        if level == "reduced":
            return "soft_reduced"
        return level

    def _push_history(self, entries: list[object], entry: object) -> None:
        entries.append(entry)
        if len(entries) > self.WORKBENCH_HISTORY_LIMIT:
            del entries[0 : len(entries) - self.WORKBENCH_HISTORY_LIMIT]
