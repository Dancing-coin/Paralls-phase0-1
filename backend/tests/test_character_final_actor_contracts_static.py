from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_character_intent_frame_ingress_runs_through_stage2_adapter_seams() -> None:
    player_shell_source = _read("scripts/player/PlayerShell.gd")
    player_bridge_source = _read("scripts/player/Phase0PlayerBridge.gd")
    replica_source = _read("scripts/character/CharacterReplica.gd")

    assert "HumanControllerAdapterRef.build_intent_frame" in player_shell_source
    assert "ProgramControllerAdapterRef.build_intent_frame" in player_bridge_source
    assert "AgentControllerAdapterRef.build_intent_frame" in replica_source


def test_character_presentation_input_egress_runs_through_runtime_state_host() -> None:
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")
    replica_source = _read("scripts/character/CharacterReplica.gd")
    contract_source = _read("scripts/character/CharacterPresentationInput.gd")

    assert "CharacterPresentationInput" in runtime_state_source
    assert "func from_agent_execution_plan(" in contract_source
    assert "func from_player_runtime_state(" in contract_source
    assert '\"focus_state\"' in contract_source
    assert '\"action_state\"' in contract_source
    assert '\"speech_state\"' in contract_source
    assert "runtime_state.build_player_presentation_input" in replica_source
    assert "runtime_state.stage_player_shell_pose" in replica_source
    assert "_normalize_presentation_input(_build_player_presentation_input())" not in replica_source


def test_character_controller_port_keeps_the_final_intent_shape_explicit() -> None:
    port_source = _read("scripts/character/CharacterControllerPort.gd")

    assert "normalize_intent_frame" in port_source
    assert '\"controller_source\"' in port_source
    assert '\"control_mode\"' in port_source
    assert '\"move_local\"' in port_source
    assert '\"desired_facing_yaw\"' in port_source
    assert '\"look_pitch\"' in port_source
    assert '\"gait\"' in port_source
    assert '\"action\"' in port_source


def test_character_agent_execution_path_uses_stage2_shared_actor_contracts() -> None:
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")
    replica_source = _read("scripts/character/CharacterReplica.gd")
    contract_source = _read("scripts/character/CharacterPresentationInput.gd")

    assert "CharacterPresentationInputRef.from_player_runtime_state(" in runtime_state_source
    assert "CharacterPresentationInputRef.from_agent_execution_plan(" in runtime_state_source
    assert "func from_agent_execution_plan(" in contract_source
    assert "AgentControllerAdapterRef.build_intent_frame" in replica_source
    assert "runtime_state.stage_agent_execution" in replica_source
    assert "runtime_state.get_agent_presentation_input" in replica_source
    assert "const CharacterPresentationInputRef" not in replica_source
    assert "_normalize_presentation_input(\n\t\truntime_state.stage_agent_execution" not in replica_source


def test_knight_role_skin_consumes_character_presentation_input_contract_directly() -> None:
    role_skin_source = _read("scripts/character/KnightRoleSkin.gd")
    contract_source = _read("scripts/character/CharacterPresentationInput.gd")

    assert "CharacterPresentationInputRef.normalize(next_input)" in role_skin_source
    assert "func get_focus_target_id(" in contract_source
    assert "func get_requested_action(" in contract_source
    assert "func get_equipment_gait_hint(" in contract_source
    assert "func get_active_command_type(" in contract_source
    assert "func get_motion_move_local_actual(" in contract_source
    assert "func get_motion_velocity_world(" in contract_source
    assert "func get_motion_gait_actual(" in contract_source
    assert "func get_focus_state(" in contract_source
    assert "func get_action_state(" in contract_source
    assert "func get_equipment_state(" in contract_source
    assert "func get_speech_state(" in contract_source
    assert "CharacterPresentationInputRef.get_motion_move_local_actual(current_presentation_contract)" in role_skin_source
    assert "CharacterPresentationInputRef.get_motion_velocity_world(current_presentation_contract)" in role_skin_source
    assert "CharacterPresentationInputRef.get_motion_gait_actual(current_presentation_contract)" in role_skin_source
    assert "CharacterPresentationInputRef.get_focus_target_id(current_presentation_contract)" in role_skin_source
    assert "CharacterPresentationInputRef.get_requested_action(current_presentation_contract)" in role_skin_source
    assert "CharacterPresentationInputRef.get_equipment_gait_hint(current_presentation_contract)" in role_skin_source
    assert "CharacterPresentationInputRef.get_active_command_type(current_presentation_contract)" in role_skin_source
    assert 'current_presentation_contract.get("motion_state", {})' not in role_skin_source
    assert 'current_presentation_contract.get("focus_state", {})' not in role_skin_source
    assert 'current_presentation_contract.get("action_state", {})' not in role_skin_source
    assert 'current_presentation_contract.get("equipment_state", {})' not in role_skin_source
    assert 'current_presentation_contract.get("speech_state", {})' not in role_skin_source
    assert 'focus_state.get("target_id", "")' not in role_skin_source
    assert 'action_state.get("requested_action", "")' not in role_skin_source
    assert 'equipment_state.get("gait_hint", "")' not in role_skin_source
    assert 'speech_state.get("active_command_type", "")' not in role_skin_source
    assert 'motion_state.get("move_local_actual", Vector2.ZERO)' not in role_skin_source
    assert 'motion_state.get("velocity_world", Vector3.ZERO)' not in role_skin_source
    assert 'motion_state.get("gait_actual", "walk")' not in role_skin_source
    assert "_normalize_presentation_input(next_input)" not in role_skin_source
    assert "CharacterActorSchemaRef.normalize_presentation_input(candidate)" not in role_skin_source


def test_character_agent_execution_metadata_is_staged_through_runtime_state() -> None:
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")
    replica_source = _read("scripts/character/CharacterReplica.gd")
    contract_source = _read("scripts/character/CharacterPresentationInput.gd")
    execution_slice = replica_source.split("func _on_character_agent_execution_received(payload: Dictionary) -> void:")[1].split(
        "func _handle_interact_goal_command(payload: Dictionary) -> void:"
    )[0]

    assert "func stage_agent_execution(" in runtime_state_source
    assert "func from_agent_execution_plan(" in contract_source
    assert "func get_expression_hint(" in contract_source
    assert "func get_physiology_hint(" in contract_source
    assert "func resolve_focus_target_lookup(" in runtime_state_source
    assert "func build_agent_role_state_effects(" in runtime_state_source
    assert "func build_agent_execution_side_effect_plan(" in runtime_state_source
    assert "func get_execution_side_effect_focus_target_lookup(" in runtime_state_source
    assert "func get_execution_side_effect_physiology_hint(" in runtime_state_source
    assert "func get_execution_side_effect_role_state_effects(" in runtime_state_source
    assert "func get_role_state_effect_name(" in runtime_state_source
    assert "func get_target_lookup_property_name(" in runtime_state_source
    assert "func get_target_lookup_expected(" in runtime_state_source
    assert "func execution_payload_targets_actor(" in runtime_state_source
    assert "func get_execution_payload_actor_control_frames(" in runtime_state_source
    assert "func get_execution_payload_presentation_plan(" in runtime_state_source
    assert "func get_execution_payload_first_frame(" in runtime_state_source
    assert "func map_requested_action_to_role_state(" in runtime_state_source
    assert "var agent_focus_target_id" not in runtime_state_source
    assert "var agent_expression_hint" not in runtime_state_source
    assert "var agent_physiology_hint" not in runtime_state_source
    assert "func get_agent_focus_target_id()" not in runtime_state_source
    assert "func get_agent_expression_hint()" not in runtime_state_source
    assert "func get_agent_physiology_hint()" not in runtime_state_source
    assert "dialogue_role_state" in replica_source
    assert "interaction_role_state" in replica_source
    assert "focus_role_state" in replica_source
    assert "attention_role_state" in replica_source
    assert "CharacterPresentationInputRef.get_requested_action(agent_presentation_input)" in runtime_state_source

    assert "runtime_state.stage_agent_execution" in replica_source
    assert "runtime_state.build_agent_execution_side_effect_plan(" in replica_source
    assert "runtime_state.get_execution_side_effect_focus_target_lookup(execution_side_effect_plan)" in replica_source
    assert "runtime_state.get_execution_side_effect_physiology_hint(execution_side_effect_plan)" in replica_source
    assert "runtime_state.get_execution_side_effect_role_state_effects(execution_side_effect_plan)" in replica_source
    assert "runtime_state.get_role_state_effect_name(effect)" in replica_source
    assert "runtime_state.get_target_lookup_property_name(lookup)" in replica_source
    assert "runtime_state.get_target_lookup_expected(lookup)" in replica_source
    assert "runtime_state.execution_payload_targets_actor(payload, actor_id)" in replica_source
    assert "runtime_state.get_execution_payload_actor_control_frames(payload)" in replica_source
    assert "runtime_state.get_execution_payload_presentation_plan(payload)" in replica_source
    assert "runtime_state.get_execution_payload_first_frame(actor_control_frames)" in replica_source
    assert "CharacterControllerPortRef.get_action_name(frame)" in replica_source
    assert "_push_presentation_input(runtime_state.get_agent_presentation_input())" in replica_source
    assert "dialogue_role_state," in replica_source
    assert "interaction_role_state," in replica_source
    assert "focus_role_state," in replica_source
    assert "attention_role_state," in replica_source
    assert 'presentation_plan.get("expression_hint"' not in replica_source
    assert 'presentation_plan.get("physiology_hint"' not in replica_source
    assert 'role_asset_scene.apply_presentation_input(runtime_state.get_agent_presentation_input())' not in execution_slice
    assert "var normalized_presentation_input" not in execution_slice
    assert "var execution_metadata" not in execution_slice
    assert "var role_state_effects" not in execution_slice
    assert "var property_name :=" not in execution_slice
    assert "var expected :=" not in execution_slice
    assert 'normalized_presentation_input.get("focus_state", {})' not in execution_slice
    assert 'normalized_presentation_input.get("action_state", {})' not in execution_slice
    assert "var expression_hint :=" not in execution_slice
    assert "var action_name :=" not in execution_slice
    assert "var requested_action_name :=" not in execution_slice
    assert '_payload_string(effect, "state_name", "")' not in execution_slice
    assert '_payload_string(frame, "action", "idle")' not in execution_slice
    assert 'payload.get("actor_control_frames", [])' not in execution_slice
    assert 'payload.get("presentation_plan", {})' not in execution_slice
    assert 'actor_control_frames[0]' not in execution_slice
    assert '_find_node_by_property("actor_id", target_ref)' not in execution_slice
    assert '_find_node_by_property("object_id", target_ref)' not in execution_slice
    assert '_find_node_by_property("environment_id", target_ref)' not in execution_slice
    assert "runtime_state.resolve_focus_target_lookup(" not in execution_slice
    assert "runtime_state.build_agent_role_state_effects()" not in execution_slice
    assert "map_requested_action_to_role_state(" not in execution_slice
    assert "var physiology_hint := runtime_state.get_execution_side_effect_physiology_hint(execution_side_effect_plan)" in execution_slice
    assert 'execution_side_effect_plan.get("focus_target_lookup", {})' not in execution_slice
    assert 'execution_side_effect_plan.get("physiology_hint", "")' not in execution_slice
    assert 'execution_side_effect_plan.get("role_state_effects", [])' not in execution_slice
    assert "runtime_state.get_agent_focus_target_id()" not in replica_source
    assert "runtime_state.get_agent_expression_hint()" not in replica_source
    assert "runtime_state.get_agent_physiology_hint()" not in replica_source
    assert "build_agent_execution_metadata" not in runtime_state_source
    assert "build_agent_role_state_requests" not in runtime_state_source


def test_runtime_state_no_longer_reads_agent_presentation_plan_fields_directly_in_multiple_places() -> None:
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")
    contract_source = _read("scripts/character/CharacterPresentationInput.gd")

    assert "CharacterPresentationInputRef.from_player_runtime_state(" in runtime_state_source
    assert "CharacterPresentationInputRef.from_agent_execution_plan(" in runtime_state_source
    assert "CharacterPresentationInputRef.get_focus_target_id(agent_presentation_input)" in runtime_state_source
    assert "CharacterPresentationInputRef.get_requested_action(agent_presentation_input)" in runtime_state_source
    assert "CharacterPresentationInputRef.get_expression_hint(agent_presentation_input)" in runtime_state_source
    assert "CharacterPresentationInputRef.get_physiology_hint(agent_presentation_input)" in runtime_state_source
    assert '"focus_state": {' not in runtime_state_source
    assert '"action_state": {' not in runtime_state_source
    assert '"speech_state": {' not in runtime_state_source
    assert 'presentation_plan.get("target_ref", "")' not in runtime_state_source
    assert 'presentation_plan.get("focus_state", {})' not in runtime_state_source
    assert 'presentation_plan.get("action_state", {})' not in runtime_state_source
    assert 'presentation_plan.get("speech_state", {})' not in runtime_state_source
    assert 'presentation_plan.get("motion_state", {})' not in runtime_state_source
    assert 'presentation_plan.get("equipment_state", {})' not in runtime_state_source
    assert 'presentation_plan.get("expression_hint", "")' not in runtime_state_source
    assert 'presentation_plan.get("physiology_hint", "")' not in runtime_state_source
    assert 'player_motion_state.duplicate(true)' not in runtime_state_source
    assert 'presentation_plan.get("target_ref", "")' in contract_source
    assert 'presentation_plan.get("focus_state", {})' in contract_source
    assert 'presentation_plan.get("action_state", {})' in contract_source
    assert 'presentation_plan.get("speech_state", {})' in contract_source
    assert 'agent_presentation_input.get("focus_state", {})' not in runtime_state_source
    assert 'agent_presentation_input.get("action_state", {})' not in runtime_state_source
    assert 'focus_state.get("target_id", "")' not in runtime_state_source
    assert 'action_state.get("requested_action", "idle")' not in runtime_state_source
    assert 'agent_presentation_input.get("expression_hint", "")' not in runtime_state_source
    assert 'agent_presentation_input.get("physiology_hint", "")' not in runtime_state_source


def test_runtime_state_uses_thin_helpers_for_payload_actor_and_target_fields() -> None:
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")

    assert "func get_payload_actor_id(" in runtime_state_source
    assert "func get_payload_target_actor_id(" in runtime_state_source
    assert "func get_payload_target_object_id(" in runtime_state_source
    assert "func get_payload_target_environment_id(" in runtime_state_source
    assert "return get_payload_actor_id(payload) == current_actor_id" in runtime_state_source
    assert "return get_payload_target_actor_id(payload) == current_actor_id" in runtime_state_source
    assert "var target_environment_id := get_payload_target_environment_id(payload)" in runtime_state_source
    assert "var target_object_id := get_payload_target_object_id(payload)" in runtime_state_source
    assert 'str(payload.get("actor_id", "")) == current_actor_id' not in runtime_state_source
    assert 'str(payload.get("target_actor_id", "")) == current_actor_id' not in runtime_state_source
    assert 'str(payload.get("actor_id", "")) != "char_c"' not in runtime_state_source
    assert 'var target_environment_id := str(payload.get("target_environment_id", "") or "")' not in runtime_state_source
    assert 'var target_object_id := str(payload.get("target_object_id", "") or "")' not in runtime_state_source
    assert "func get_payload_target_actor_id(payload: Dictionary) -> String:" in runtime_state_source


def test_runtime_state_uses_helpers_for_runtime_state_payload_reference_lists() -> None:
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")

    assert "func get_runtime_nearby_actor_refs_payload(" in runtime_state_source
    assert "func get_runtime_nearby_object_refs_payload(" in runtime_state_source
    assert "func get_runtime_nearby_environment_refs_payload(" in runtime_state_source
    assert "func get_runtime_conversation_candidate_refs_payload(" in runtime_state_source
    assert 'runtime_nearby_actor_refs = _read_runtime_string_array(get_runtime_nearby_actor_refs_payload(payload))' in runtime_state_source
    assert 'runtime_nearby_object_refs = _read_runtime_string_array(get_runtime_nearby_object_refs_payload(payload))' in runtime_state_source
    assert 'runtime_nearby_environment_refs = _read_runtime_string_array(get_runtime_nearby_environment_refs_payload(payload))' in runtime_state_source
    assert 'runtime_conversation_candidate_refs = _read_runtime_string_array(get_runtime_conversation_candidate_refs_payload(payload))' in runtime_state_source
    assert 'runtime_nearby_actor_refs = _read_runtime_string_array(payload.get("nearby_actor_refs", []))' not in runtime_state_source
    assert 'runtime_nearby_object_refs = _read_runtime_string_array(payload.get("nearby_object_refs", []))' not in runtime_state_source
    assert 'runtime_nearby_environment_refs = _read_runtime_string_array(payload.get("nearby_environment_refs", []))' not in runtime_state_source
    assert 'runtime_conversation_candidate_refs = _read_runtime_string_array(payload.get("conversation_candidate_refs", []))' not in runtime_state_source


def test_runtime_state_uses_thin_helpers_for_execution_side_effect_and_lookup_fields() -> None:
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")

    assert "func get_execution_side_effect_focus_target_lookup(" in runtime_state_source
    assert "func get_execution_side_effect_physiology_hint(" in runtime_state_source
    assert "func get_execution_side_effect_role_state_effects(" in runtime_state_source
    assert "func get_target_lookup_property_name(" in runtime_state_source
    assert "func get_target_lookup_expected(" in runtime_state_source
    assert "func get_execution_side_effect_role_state_effects_payload(" in runtime_state_source
    assert "func get_execution_side_effect_focus_target_lookup_payload(" in runtime_state_source
    assert "func get_execution_side_effect_physiology_hint_payload(" in runtime_state_source
    assert "return get_execution_side_effect_focus_target_lookup_payload(execution_side_effect_plan)" in runtime_state_source
    assert "return str(get_execution_side_effect_physiology_hint_payload(execution_side_effect_plan))" in runtime_state_source
    assert "var value: Variant = get_execution_side_effect_role_state_effects_payload(execution_side_effect_plan)" in runtime_state_source
    assert "func get_target_lookup_property_name_payload(" in runtime_state_source
    assert "func get_target_lookup_expected_payload(" in runtime_state_source
    assert "return str(get_target_lookup_property_name_payload(lookup))" in runtime_state_source
    assert "return str(get_target_lookup_expected_payload(lookup))" in runtime_state_source


def test_character_replica_reuses_runtime_state_role_state_mapping() -> None:
    replica_source = _read("scripts/character/CharacterReplica.gd")

    assert "func perform_action(action_name: String) -> void:" in replica_source
    assert "runtime_state.map_requested_action_to_role_state(" in replica_source
    assert "dialogue_role_state," in replica_source
    assert "interaction_role_state," in replica_source
    assert "focus_role_state," in replica_source
    assert "attention_role_state," in replica_source
    assert "func _map_requested_action_to_role_state(" not in replica_source
    assert "var next_state := _map_requested_action_to_role_state(action_name)" not in replica_source


def test_actor_side_intent_frame_consumers_normalize_through_controller_port() -> None:
    motor_source = _read("scripts/character/CharacterMotor.gd")
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")
    player_bridge_source = _read("scripts/player/Phase0PlayerBridge.gd")
    replica_source = _read("scripts/character/CharacterReplica.gd")

    assert "CharacterControllerPortRef.normalize_intent_frame(frame)" in motor_source
    assert "CharacterControllerPortRef.normalize_intent_frame(intent_frame)" in runtime_state_source
    assert "CharacterControllerPortRef.normalize_intent_frame(current_intent_frame)" in player_bridge_source
    assert "CharacterControllerPortRef.normalize_intent_frame(" in replica_source


def test_phase0_player_bridge_reads_normalized_intent_fields_through_controller_port_helpers() -> None:
    port_source = _read("scripts/character/CharacterControllerPort.gd")
    player_bridge_source = _read("scripts/player/Phase0PlayerBridge.gd")

    assert "static func get_move_local(" in port_source
    assert "static func get_gait_name(" in port_source
    assert "static func get_action_name(" in port_source
    assert "static func get_desired_facing_yaw(" in port_source
    assert "CharacterControllerPortRef.get_move_local(normalized_frame)" in player_bridge_source
    assert "CharacterControllerPortRef.get_gait_name(normalized_frame)" in player_bridge_source
    assert "CharacterControllerPortRef.get_action_name(normalized_frame)" in player_bridge_source
    assert "CharacterControllerPortRef.get_desired_facing_yaw(normalized_frame, player.global_rotation.y)" in player_bridge_source
    assert 'normalized_frame.get("move_local", Vector2.ZERO)' not in player_bridge_source
    assert 'normalized_frame.get("gait", "")' not in player_bridge_source
    assert 'normalized_frame.get("action", "")' not in player_bridge_source
    assert 'normalized_frame.get("desired_facing_yaw", player.global_rotation.y)' not in player_bridge_source


def test_character_motor_reads_normalized_intent_fields_through_controller_port_helpers() -> None:
    port_source = _read("scripts/character/CharacterControllerPort.gd")
    motor_source = _read("scripts/character/CharacterMotor.gd")

    assert "static func get_move_local(" in port_source
    assert "static func get_gait_name(" in port_source
    assert "static func get_action_name(" in port_source
    assert "CharacterControllerPortRef.get_move_local(normalized_frame)" in motor_source
    assert "CharacterControllerPortRef.get_gait_name(normalized_frame)" in motor_source
    assert "CharacterControllerPortRef.get_action_name(normalized_frame)" in motor_source
    assert 'normalized_frame.get("move_local", Vector2.ZERO)' not in motor_source
    assert 'normalized_frame.get("gait", "walk")' not in motor_source
    assert 'normalized_frame.get("action", "idle")' not in motor_source


def test_character_replica_uses_shared_presentation_push_helper() -> None:
    replica_source = _read("scripts/character/CharacterReplica.gd")

    assert "func _push_presentation_input(presentation_input: Dictionary) -> void:" in replica_source
    assert "_push_presentation_input(runtime_state.get_agent_presentation_input())" in replica_source
    assert "var player_presentation_input := runtime_state.stage_player_shell_pose(" in replica_source
    assert "_push_presentation_input(player_presentation_input)" in replica_source
    assert "func _push_agent_presentation_input() -> void:" not in replica_source
    assert "func _push_player_presentation_input() -> void:" not in replica_source


def test_runtime_state_reads_agent_requested_action_through_shared_helpers() -> None:
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")
    controller_port_source = _read("scripts/character/CharacterControllerPort.gd")

    assert "CharacterControllerPortRef.get_action_name(normalized_intent_frame)" in runtime_state_source
    assert "CharacterPresentationInputRef.get_requested_action(agent_presentation_input)" in runtime_state_source
    assert "CharacterPresentationInputRef.get_focus_target_id(agent_presentation_input)" in runtime_state_source
    assert "static func get_action_name(" in controller_port_source
    assert 'normalized_intent_frame.get("action", "idle")' not in runtime_state_source


def test_character_replica_reads_target_lookup_fields_through_runtime_state_helpers() -> None:
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")
    replica_source = _read("scripts/character/CharacterReplica.gd")

    assert "func get_target_lookup_property_name(" in runtime_state_source
    assert "func get_target_lookup_expected(" in runtime_state_source
    assert "runtime_state.get_target_lookup_property_name(lookup)" in replica_source
    assert "runtime_state.get_target_lookup_expected(lookup)" in replica_source
    assert 'lookup.get("property_name", "")' not in replica_source
    assert 'lookup.get("expected", "")' not in replica_source


def test_character_replica_reads_command_target_position_through_runtime_state_helper() -> None:
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")
    replica_source = _read("scripts/character/CharacterReplica.gd")

    assert "func get_command_target_position(" in runtime_state_source
    assert "runtime_state.get_command_target_position(payload)" in replica_source
    assert 'payload.get("target_position", null)' not in replica_source


def test_character_replica_uses_runtime_state_helpers_for_runtime_state_payload_targeting() -> None:
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")
    replica_source = _read("scripts/character/CharacterReplica.gd")

    assert "func is_runtime_state_payload_for_actor(" in runtime_state_source
    assert "runtime_state.is_runtime_state_payload_for_actor(payload, actor_id)" in replica_source
    assert 'payload.get("actor_id", "") != actor_id' not in replica_source


def test_character_replica_uses_runtime_state_helpers_for_dialogue_and_siming_payload_targeting() -> None:
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")
    replica_source = _read("scripts/character/CharacterReplica.gd")

    assert "func is_dialogue_payload_for_actor(" in runtime_state_source
    assert "func is_siming_output_for_actor(" in runtime_state_source
    assert "runtime_state.is_dialogue_payload_for_actor(payload, actor_id)" in replica_source
    assert "runtime_state.is_siming_output_for_actor(payload, actor_id)" in replica_source
    assert 'payload.get("actor_id", "") == actor_id' not in replica_source
    assert 'payload.get("target_actor_id", "") == actor_id' not in replica_source


def test_character_replica_uses_runtime_state_helpers_for_fact_emitter_actor_id_sync() -> None:
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")
    replica_source = _read("scripts/character/CharacterReplica.gd")

    assert "func should_sync_emitter_actor_id(" in runtime_state_source
    assert "runtime_state.should_sync_emitter_actor_id(role_state_fact_emitter, actor_id)" in replica_source
    assert "runtime_state.should_sync_emitter_actor_id(physiology_state_fact_emitter, actor_id)" in replica_source
    assert 'role_state_fact_emitter.get("actor_id") != actor_id' not in replica_source
    assert 'physiology_state_fact_emitter.get("actor_id") != actor_id' not in replica_source


def test_character_replica_reads_line_of_sight_hit_collider_through_runtime_state_helper() -> None:
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")
    replica_source = _read("scripts/character/CharacterReplica.gd")

    assert "func get_line_of_sight_hit_collider(" in runtime_state_source
    assert "runtime_state.get_line_of_sight_hit_collider(hit)" in replica_source
    assert 'hit.get("collider", null)' not in replica_source
