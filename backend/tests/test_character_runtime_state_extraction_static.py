from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]


def test_runtime_state_is_actor_owned_after_replica_retirement() -> None:
    actor = _read("scripts/character/CharacterActor.gd")
    assert "@onready var runtime_state = CharacterRuntimeStateRef.new()" in actor
    assert not (ROOT / ("scripts/character/Character" + "Replica.gd")).exists()
    assert "func apply_control_intent(" in actor
    assert "func apply_compatibility_pose_sync(" in actor


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_character_runtime_state_host_exists() -> None:
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")

    assert "class_name CharacterRuntimeState" in runtime_state_source
    assert "func apply_runtime_state_payload(payload: Dictionary) -> void:" in runtime_state_source
    assert "func build_player_presentation_input(" in runtime_state_source
    assert "func set_active_command(" in runtime_state_source
    assert "func clear_active_command() -> void:" in runtime_state_source


def test_character_replica_uses_runtime_state_host_for_extracted_state() -> None:
    actor_source = _read("scripts/character/CharacterActor.gd")

    assert "CharacterRuntimeState" in actor_source
    assert "@onready var runtime_state = CharacterRuntimeStateRef.new()" in actor_source
    assert "@onready var runtime_state: CharacterRuntimeState" not in actor_source
    assert "runtime_state.stage_player_shell_pose" in actor_source
    assert "runtime_state.build_player_presentation_input" in actor_source
    assert "runtime_state.apply_runtime_state_payload" in actor_source
    assert "runtime_state.set_active_command" in actor_source
    assert "runtime_state.clear_active_command" in actor_source


def test_character_actor_does_not_redeclare_runtime_state_owned_fields() -> None:
    actor_source = _read("scripts/character/CharacterActor.gd")
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")

    assert "@onready var runtime_state = CharacterRuntimeStateRef.new()" in actor_source
    assert "class_name CharacterRuntimeState" in runtime_state_source
    for field in (
        'var runtime_focus_target := ""', 'var runtime_attention_source := ""',
        'var runtime_nearby_actor_refs: Array[String] = []',
        'var runtime_nearby_object_refs: Array[String] = []',
        'var runtime_nearby_environment_refs: Array[String] = []',
        'var runtime_conversation_candidate_refs: Array[String] = []',
        'var runtime_engagement_pressure := ""', 'var runtime_privacy_risk_hint := ""',
        'var active_command_type := ""', 'var active_command_priority := 0',
        'var player_motion_state: Dictionary = {}',
        'var player_shell_velocity := Vector3.ZERO', 'var player_shell_grounded := true',
        'var player_stance := "stand"', 'var player_gait := "walk"',
        'var player_jump_type := "none"',
    ):
        assert field not in actor_source
    assert "var player_presentation_input: Dictionary = {}" not in actor_source
    assert "var player_presentation_input: Dictionary = {}" not in runtime_state_source


def test_runtime_state_host_stages_focus_and_attention_metadata() -> None:
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")
    actor_source = _read("scripts/character/CharacterActor.gd")

    assert "func should_apply_focus_attention(" in runtime_state_source
    assert "func resolve_attention_target_ref(" in runtime_state_source
    assert "func should_highlight_focus(" in runtime_state_source
    assert "runtime_state.should_apply_focus_attention" in actor_source
    assert "runtime_state.resolve_attention_target_ref" in actor_source
    assert "runtime_state.should_highlight_focus" in actor_source
    assert "runtime_state.get_runtime_nearby_actor_refs()" not in actor_source
    assert "runtime_state.get_runtime_nearby_object_refs()" not in actor_source
    assert "runtime_state.get_runtime_engagement_pressure()" not in actor_source
    assert "runtime_state.get_runtime_privacy_risk_hint()" not in actor_source


def test_runtime_state_host_stages_player_shell_pose_metadata() -> None:
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")
    actor_source = _read("scripts/character/CharacterActor.gd")
    sync_helper_source = _read("scripts/player/Phase0CharacterShellSync.gd")

    assert "func stage_player_shell_pose(" in runtime_state_source
    assert "func clear_player_shell_pose() -> void:" in runtime_state_source
    assert "func get_player_shell_velocity() -> Vector3:" in runtime_state_source
    assert "func is_player_shell_grounded() -> bool:" in runtime_state_source
    assert "func get_player_stance() -> String:" in runtime_state_source
    assert "func get_player_gait() -> String:" in runtime_state_source
    assert "func get_player_jump_type() -> String:" in runtime_state_source
    assert "runtime_state.stage_player_shell_pose" in actor_source
    assert "runtime_state.clear_player_shell_pose" in actor_source
    assert "runtime_state.get_player_shell_velocity" in actor_source
    assert "runtime_state.is_player_shell_grounded" in actor_source
    assert "runtime_state.get_player_stance" in actor_source
    assert "runtime_state.get_player_jump_type" in actor_source
    assert "player_motion_state: Dictionary" in sync_helper_source
    assert 'character_c.apply_embodied_pose_sync(world_position, planar_velocity, look_target, is_grounded, player_motion_state)' in sync_helper_source
    assert "runtime_state.accept_player_motion_state" not in actor_source
    assert "runtime_state.clear_player_motion_state" not in actor_source
    assert "runtime_state.get_player_motion_state()" not in actor_source
    assert "runtime_state.set_player_presentation_input" not in actor_source
    assert "runtime_state.get_player_presentation_input()" not in actor_source
    assert "var player_shell_velocity := Vector3.ZERO" not in actor_source
    assert "var player_shell_grounded := true" not in actor_source
    assert "var player_stance := \"stand\"" not in actor_source
    assert "var player_jump_type := \"none\"" not in actor_source
    assert 'next_motion_state.get("velocity_world", Vector3.ZERO)' not in runtime_state_source
    assert 'next_motion_state.get("grounded", true)' not in runtime_state_source


def test_runtime_state_no_longer_keeps_internal_player_motion_helper_layers() -> None:
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")
    stage_slice = runtime_state_source.split("func stage_player_shell_pose(", 1)[1].split(
        "func clear_player_shell_pose()", 1
    )[0]
    clear_slice = runtime_state_source.split("func clear_player_shell_pose() -> void:", 1)[1].split(
        "func get_player_shell_velocity()", 1
    )[0]

    assert "func accept_player_motion_state(" not in runtime_state_source
    assert "func clear_player_motion_state() -> void:" not in runtime_state_source
    assert "accept_player_motion_state(next_motion_state)" not in stage_slice
    assert "player_motion_state = next_motion_state.duplicate(true)" in stage_slice
    assert "clear_player_motion_state()" not in clear_slice
    assert "player_motion_state = {}" in clear_slice
    assert "player_shell_velocity = Vector3.ZERO" in clear_slice


def test_runtime_state_host_exposes_player_locomotion_interpretation_helper() -> None:
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")
    actor_source = _read("scripts/character/CharacterActor.gd")

    assert "func resolve_player_locomotion_state(" in runtime_state_source
    assert '"motion_profile"' in runtime_state_source
    assert '"locomotion_state"' in runtime_state_source
    assert "runtime_state.resolve_player_locomotion_state" in actor_source


def test_runtime_state_builds_agent_execution_side_effect_plan_from_presentation_input() -> None:
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")
    side_effect_slice = runtime_state_source.split("func build_agent_execution_side_effect_plan(", 1)[1].split(
        "func get_execution_side_effect_focus_target_lookup(", 1
    )[0]

    assert '"focus_target_lookup": resolve_focus_target_lookup(' in side_effect_slice
    assert "CharacterPresentationInputRef.get_focus_target_id(agent_presentation_input)" in side_effect_slice
    assert '"physiology_hint": CharacterPresentationInputRef.get_physiology_hint(agent_presentation_input)' in side_effect_slice
    assert '"active_command_type": CharacterPresentationInputRef.get_active_command_type(agent_presentation_input)' in side_effect_slice
    assert '"role_state_effects": build_agent_role_state_effects(' in side_effect_slice
    assert "func get_execution_side_effect_active_command_type(" in runtime_state_source
    assert "func get_execution_side_effect_active_command_type_payload(" in runtime_state_source


def test_character_replica_applies_agent_execution_side_effects_through_runtime_state_helpers() -> None:
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")
    actor_source = _read("scripts/character/CharacterActor.gd")
    handler_slice = actor_source.split("func _on_character_agent_execution_received(payload: Dictionary) -> void:", 1)[1].split(
        "func _handle_interact_goal_command(", 1
    )[0]

    assert "func get_execution_side_effect_active_command_type(" in runtime_state_source
    assert "func get_execution_side_effect_focus_target_lookup(" in runtime_state_source
    assert "func get_execution_side_effect_physiology_hint(" in runtime_state_source
    assert "func get_execution_side_effect_role_state_effects(" in runtime_state_source
    assert "runtime_state.build_agent_execution_side_effect_plan(" in handler_slice
    assert "runtime_state.get_execution_side_effect_active_command_type(execution_side_effect_plan)" in handler_slice
    assert "runtime_state.set_active_command(active_command_type, _command_priority(active_command_type))" in handler_slice
    assert "runtime_state.get_execution_side_effect_focus_target_lookup(execution_side_effect_plan)" in handler_slice
    assert "runtime_state.get_execution_side_effect_physiology_hint(execution_side_effect_plan)" in handler_slice
    assert "runtime_state.get_execution_side_effect_role_state_effects(execution_side_effect_plan)" in handler_slice
    assert 'presentation_plan.get("focus_target_id"' not in handler_slice
    assert 'presentation_plan.get("physiology_hint"' not in handler_slice
    assert 'presentation_plan.get("expression_hint"' not in handler_slice
    assert 'presentation_plan.get("active_command_type"' not in handler_slice
    assert "CharacterPresentationInputRef." not in handler_slice


def test_runtime_state_host_builds_player_presentation_payload_fields() -> None:
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")
    actor_source = _read("scripts/character/CharacterActor.gd")

    assert "func resolve_player_presentation_motion_fields(" in runtime_state_source
    assert "runtime_state.resolve_player_presentation_motion_fields" in actor_source
    assert 'player_motion_state.get("move_local_actual", Vector2.ZERO)' not in runtime_state_source
    assert 'player_motion_state.get("velocity_world", player_shell_velocity)' not in runtime_state_source


def test_runtime_state_player_presentation_builder_no_longer_keeps_unused_transitional_args() -> None:
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")
    actor_source = _read("scripts/character/CharacterActor.gd")
    build_slice = runtime_state_source.split("func build_player_presentation_input(", 1)[1].split(
        "func resolve_player_presentation_motion_fields(", 1
    )[0]
    replica_build_slice = actor_source.split("func _build_player_presentation_input() -> Dictionary:", 1)[1].split(
        "func _push_presentation_input(", 1
    )[0]

    assert "func build_player_presentation_input(" in runtime_state_source
    assert "player_shell_velocity: Vector3" not in build_slice
    assert "player_gait: String" not in build_slice
    assert "runtime_state.get_player_shell_velocity()," not in replica_build_slice
    assert "runtime_state.get_player_gait()" not in replica_build_slice
    assert "var presentation_contract :=" not in build_slice
    assert "return CharacterPresentationInputRef.from_player_runtime_state(" in build_slice


def test_runtime_state_no_longer_keeps_player_presentation_setter_layer() -> None:
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")
    stage_slice = runtime_state_source.split("func stage_player_shell_pose(", 1)[1].split(
        "func clear_player_shell_pose()", 1
    )[0]

    assert "func set_player_presentation_input(" not in runtime_state_source
    assert "set_player_presentation_input(next_presentation_input)" not in stage_slice
    assert "player_presentation_input = next_presentation_input.duplicate(true)" not in stage_slice
    assert "return next_presentation_input.duplicate(true)" in stage_slice


def test_runtime_state_no_longer_keeps_player_presentation_cache_field_or_getter() -> None:
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")
    actor_source = _read("scripts/character/CharacterActor.gd")

    assert "var player_presentation_input: Dictionary = {}" not in runtime_state_source
    assert "func get_player_presentation_input() -> Dictionary:" not in runtime_state_source
    assert "_push_presentation_input(runtime_state.get_player_presentation_input())" not in actor_source


def test_runtime_state_no_longer_keeps_zero_consumer_getters() -> None:
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")

    assert "func get_player_motion_state() -> Dictionary:" not in runtime_state_source
    assert "func get_runtime_nearby_actor_refs() -> Array[String]:" not in runtime_state_source
    assert "func get_runtime_nearby_object_refs() -> Array[String]:" not in runtime_state_source
    assert "func get_runtime_engagement_pressure() -> String:" not in runtime_state_source
    assert "func get_runtime_privacy_risk_hint() -> String:" not in runtime_state_source


def test_runtime_state_host_no_longer_keeps_finalize_player_presentation_input_bridge() -> None:
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")
    actor_source = _read("scripts/character/CharacterActor.gd")

    assert "func finalize_player_presentation_input(" not in runtime_state_source
    assert "runtime_state.finalize_player_presentation_input" not in actor_source


def test_runtime_state_host_no_longer_writes_flat_motion_fields_into_presentation_contract() -> None:
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")

    assert 'presentation_contract["move_x"]' not in runtime_state_source
    assert 'presentation_contract["move_y"]' not in runtime_state_source
    assert 'presentation_contract["speed"]' not in runtime_state_source
    assert 'presentation_contract["gait"]' not in runtime_state_source
    assert 'finalized["move_x"]' not in runtime_state_source
    assert 'finalized["move_y"]' not in runtime_state_source
    assert 'finalized["speed"]' not in runtime_state_source
    assert 'finalized["gait"]' not in runtime_state_source


def test_character_replica_player_locomotion_no_longer_reads_flat_presentation_motion_keys() -> None:
    actor_source = _read("scripts/character/CharacterActor.gd")

    locomotion_slice = actor_source.split("func _update_player_shell_locomotion() -> void:")[1].split(
        "func _resolve_player_motion_state(", 1
    )[0]

    assert 'player_presentation_input.get("move_x"' not in locomotion_slice
    assert 'player_presentation_input.get("move_y"' not in locomotion_slice
    assert 'player_presentation_input.get("speed"' not in locomotion_slice
    assert "runtime_state.resolve_player_presentation_motion_fields()" in locomotion_slice


def test_character_replica_player_locomotion_reads_runtime_state_intermediate_fields_through_helpers() -> None:
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")
    actor_source = _read("scripts/character/CharacterActor.gd")

    locomotion_slice = actor_source.split("func _update_player_shell_locomotion() -> void:")[1].split(
        "func _resolve_player_motion_state(", 1
    )[0]

    assert "func get_motion_fields_move_local(" in runtime_state_source
    assert "func get_motion_fields_velocity_world(" in runtime_state_source
    assert "func get_locomotion_decision_state(" in runtime_state_source
    assert "func should_clear_root_motion(" in runtime_state_source
    assert "func should_reset_posture(" in runtime_state_source
    assert "func get_locomotion_decision_motion_profile(" in runtime_state_source
    assert "func get_locomotion_decision_role_state(" in runtime_state_source
    assert "func get_locomotion_decision_role_state_duration(" in runtime_state_source
    assert "func get_locomotion_decision_physiology_hint(" in runtime_state_source
    assert "runtime_state.get_motion_fields_move_local(motion_fields)" in locomotion_slice
    assert "runtime_state.get_motion_fields_velocity_world(motion_fields)" in locomotion_slice
    assert "runtime_state.get_locomotion_decision_state(locomotion_decision)" in locomotion_slice
    assert "runtime_state.should_clear_root_motion(locomotion_decision)" in locomotion_slice
    assert "runtime_state.should_reset_posture(locomotion_decision)" in locomotion_slice
    assert "runtime_state.get_locomotion_decision_motion_profile(locomotion_decision)" in locomotion_slice
    assert "runtime_state.get_locomotion_decision_role_state(locomotion_decision)" in locomotion_slice
    assert "runtime_state.get_locomotion_decision_role_state_duration(locomotion_decision)" in locomotion_slice
    assert "runtime_state.get_locomotion_decision_physiology_hint(locomotion_decision)" in locomotion_slice
    assert 'motion_fields.get("move_local", Vector2.ZERO)' not in locomotion_slice
    assert 'motion_fields.get("velocity_world", runtime_state.get_player_shell_velocity())' not in locomotion_slice
    assert 'locomotion_decision.get("locomotion_state", "idle")' not in locomotion_slice
    assert 'locomotion_decision.get("clear_root_motion", false)' not in locomotion_slice
    assert 'locomotion_decision.get("reset_posture", false)' not in locomotion_slice
    assert 'locomotion_decision.get("motion_profile", "default")' not in locomotion_slice
    assert 'locomotion_decision.get("role_state", "")' not in locomotion_slice
    assert 'locomotion_decision.get("role_state_duration", 0.0)' not in locomotion_slice
    assert 'locomotion_decision.get("physiology_hint", "")' not in locomotion_slice


def test_character_replica_no_longer_backreads_parent_motion_state_for_player_pose() -> None:
    actor_source = _read("scripts/character/CharacterActor.gd")

    player_pose_slice = actor_source.split("func apply_embodied_pose_sync(", 1)[1].split(
        "func clear_embodied_control_frame()", 1
    )[0]

    assert 'parent_node.get("motion_state")' not in player_pose_slice


def test_character_replica_clears_player_shell_pose_only_once_per_embodied_clear() -> None:
    actor_source = _read("scripts/character/CharacterActor.gd")

    clear_slice = actor_source.split("func clear_embodied_control_frame() -> void:", 1)[1].split(
        "func is_embodied_control_active()", 1
    )[0]

    assert clear_slice.count("runtime_state.clear_player_shell_pose()") == 1


def test_runtime_state_host_exposes_player_gait_motion_profile_helper() -> None:
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")
    actor_source = _read("scripts/character/CharacterActor.gd")

    assert "func resolve_player_gait_motion_profile() -> String:" in runtime_state_source
    assert 'return "amble"' in runtime_state_source
    assert 'return "brisk_walk"' in runtime_state_source
    assert 'return "run"' in runtime_state_source
    assert 'return "walk"' in runtime_state_source
    assert "runtime_state.resolve_player_gait_motion_profile()" in actor_source
    assert "match runtime_state.get_player_gait():" not in actor_source


def test_character_replica_reads_player_gait_back_through_runtime_state() -> None:
    actor_source = _read("scripts/character/CharacterActor.gd")

    assert "runtime_state.get_player_gait()" in actor_source
    assert '"gait": player_gait' not in actor_source
    assert "match player_gait:" not in actor_source
    assert re.search(r"(?m)^\s*player_gait\s*=", actor_source) is None


def test_character_replica_reads_player_stance_and_jump_back_through_runtime_state() -> None:
    actor_source = _read("scripts/character/CharacterActor.gd")

    assert "runtime_state.get_player_stance()" in actor_source
    assert "runtime_state.get_player_jump_type()" in actor_source
    assert '"stance": player_stance' not in actor_source
    assert '"jump_type": player_jump_type' not in actor_source


def test_runtime_state_owns_remaining_player_presentation_request_and_physiology_fields() -> None:
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")
    actor_source = _read("scripts/character/CharacterActor.gd")
    build_slice = runtime_state_source.split("func build_player_presentation_input(", 1)[1].split(
        "func resolve_player_presentation_motion_fields(", 1
    )[0]
    replica_build_slice = actor_source.split("func _build_player_presentation_input() -> Dictionary:", 1)[1].split(
        "func _push_presentation_input(", 1
    )[0]

    assert 'var requested_action := ""' in runtime_state_source
    assert 'var last_physiology_state_fact := ""' in runtime_state_source
    assert "func set_requested_action(action_name: String) -> void:" in runtime_state_source
    assert "func get_requested_action() -> String:" in runtime_state_source
    assert "func set_last_physiology_state_fact(strain_band: String) -> void:" in runtime_state_source
    assert "func get_last_physiology_state_fact() -> String:" in runtime_state_source
    assert 'var requested_action := ""' not in actor_source
    assert 'var last_physiology_state_fact := ""' not in actor_source
    assert "runtime_state.set_requested_action(action_name)" in actor_source
    assert "runtime_state.get_last_physiology_state_fact()" in actor_source
    assert "runtime_state.set_last_physiology_state_fact(strain_band)" in actor_source
    assert "requested_action: String" not in build_slice
    assert "last_physiology_state_fact: String" not in build_slice
    assert "return CharacterPresentationInputRef.from_player_runtime_state(" in build_slice
    assert "runtime_state.get_requested_action()," not in replica_build_slice
    assert "runtime_state.get_last_physiology_state_fact()," not in replica_build_slice
