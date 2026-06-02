extends Node

@export var dialogue_action := "phase0_submit_dialogue"
@export var interact_action := "phase0_interact"
@export var character_c_sync_enabled := true
@export var hide_player_visual_shell := true

@onready var embodiment: Node = $"../Phase0Embodiment"
@onready var player: CharacterBody3D = get_parent() as CharacterBody3D

# This bridge still drives the Player locomotion shell directly.
# In Phase 0.5 the scene also contains CharacterC as the first in-world
# player-driven role shell, but focus and interaction authority remain unchanged.

func _ready() -> void:
	if hide_player_visual_shell:
		_set_player_visual_shell_visible(false)

func _physics_process(_delta: float) -> void:
	if not character_c_sync_enabled:
		_clear_character_c_sync()
		return
	_sync_character_c_from_player()

func _unhandled_input(event: InputEvent) -> void:
	var main_demo := _get_main_demo()
	if main_demo == null:
		return

	if event.is_action_pressed(dialogue_action) and main_demo.has_method("submit_dialogue"):
		if embodiment and embodiment.has_method("trigger_dialogue_feedback"):
			embodiment.trigger_dialogue_feedback()
		main_demo.submit_dialogue()

	if event.is_action_pressed(interact_action) and main_demo.has_method("submit_interaction"):
		if embodiment and embodiment.has_method("trigger_interact_feedback"):
			embodiment.trigger_interact_feedback()
		main_demo.submit_interaction()

func trigger_dialogue() -> void:
	var main_demo := _get_main_demo()
	if embodiment and embodiment.has_method("trigger_dialogue_feedback"):
		embodiment.trigger_dialogue_feedback()
	if main_demo and main_demo.has_method("submit_dialogue"):
		main_demo.submit_dialogue()

func trigger_interaction() -> void:
	var main_demo := _get_main_demo()
	if embodiment and embodiment.has_method("trigger_interact_feedback"):
		embodiment.trigger_interact_feedback()
	if main_demo and main_demo.has_method("submit_interaction"):
		main_demo.submit_interaction()

func _get_main_demo() -> Node:
	return get_tree().current_scene

func set_character_c_sync_enabled(enabled: bool) -> void:
	character_c_sync_enabled = enabled
	if not enabled:
		_clear_character_c_sync()

func _sync_character_c_from_player() -> void:
	var main_demo := _get_main_demo()
	if main_demo == null:
		return
	var character_c := main_demo.get_node_or_null("CharacterC")
	if character_c == null or not character_c.has_method("apply_player_shell_frame"):
		return

	var planar_velocity := Vector3(player.velocity.x, 0.0, player.velocity.z)
	var look_target := _resolve_player_look_target()
	character_c.apply_player_shell_frame(player.global_position, planar_velocity, look_target, player.is_on_floor())

func _clear_character_c_sync() -> void:
	var main_demo := _get_main_demo()
	if main_demo == null:
		return
	var character_c := main_demo.get_node_or_null("CharacterC")
	if character_c and character_c.has_method("clear_player_shell_frame"):
		character_c.clear_player_shell_frame()

func get_control_anchor_position() -> Vector3:
	var character_c := _get_character_c()
	if character_c and character_c.has_method("is_player_shell_active") and character_c.is_player_shell_active():
		if character_c.has_method("get_role_anchor_position"):
			return character_c.get_role_anchor_position()
		if character_c is Node3D:
			return (character_c as Node3D).global_position
	return player.global_position

func get_control_forward() -> Vector3:
	var character_c := _get_character_c()
	if character_c and character_c.has_method("is_player_shell_active") and character_c.is_player_shell_active():
		var look_target := _resolve_player_look_target()
		var forward := look_target - get_control_anchor_position()
		forward.y = 0.0
		if forward.length() > 0.001:
			return forward.normalized()
		if character_c is Node3D:
			return -((character_c as Node3D).global_basis.z).normalized()
	return _resolve_player_forward()

func get_camera() -> Camera3D:
	return _find_camera()

func _resolve_player_look_target() -> Vector3:
	var visual_root := player.find_child("VisualRoot", true, false)
	if visual_root is Node3D:
		return player.global_position - (visual_root as Node3D).global_basis.z
	var camera := _find_camera()
	if camera is Camera3D:
		return player.global_position - (camera as Camera3D).global_basis.z
	return player.global_position - player.global_basis.z

func _resolve_player_forward() -> Vector3:
	var camera := _find_camera()
	if camera:
		return -(camera.global_basis.z).normalized()
	var visual_root := player.find_child("VisualRoot", true, false)
	if visual_root is Node3D:
		return -((visual_root as Node3D).global_basis.z).normalized()
	return -(player.global_basis.z).normalized()

func _set_player_visual_shell_visible(is_visible: bool) -> void:
	var visual_root := player.find_child("VisualRoot", true, false)
	if visual_root is Node3D:
		(visual_root as Node3D).visible = is_visible

func _get_character_c() -> Node:
	var main_demo := _get_main_demo()
	if main_demo == null:
		return null
	return main_demo.get_node_or_null("CharacterC")

func _find_camera() -> Camera3D:
	var found := player.find_child("Camera3D", true, false)
	if found is Camera3D:
		return found as Camera3D
	return null
