extends Node

@export var dialogue_action := "phase0_submit_dialogue"
@export var interact_action := "phase0_interact"
@export var gait_cycle_action := "phase0_cycle_walk_mode"
@export var crouch_toggle_action := "phase0_toggle_crouch"
@export var guard_pose_action := "phase0_knight_guard_pose"
@export var observe_pose_action := "phase0_knight_observe_pose"
@export var speak_pose_action := "phase0_knight_speak_pose"
@export var inspect_pose_action := "phase0_knight_inspect_pose"
@export var alert_pose_action := "phase0_knight_alert_pose"
@export var ambient_pose_action := "phase0_knight_ambient_pose"
@export var sword_swing_action := "phase0_sword_swing"
@export var shield_block_action := "phase0_shield_block"

@onready var player_bridge: Node = $"../Phase0InputBridge"

var sword_swing_pressed := false
var shield_block_pressed := false

func handle_shell_action_event(event: InputEvent) -> void:
	if player_bridge == null:
		return
	if event.is_action_pressed(gait_cycle_action) and player_bridge.has_method("cycle_gait_mode"):
		player_bridge.cycle_gait_mode()
	if event.is_action_pressed(crouch_toggle_action) and player_bridge.has_method("toggle_crouch_mode"):
		player_bridge.toggle_crouch_mode()
	if event.is_action_pressed(dialogue_action):
		_call_bridge_role_action("speak")
		if player_bridge.has_method("trigger_dialogue"):
			player_bridge.trigger_dialogue()
	if event.is_action_pressed(interact_action):
		_call_bridge_role_action("inspect")
		if player_bridge.has_method("trigger_interaction"):
			player_bridge.trigger_interaction()
	if event.is_action_pressed(guard_pose_action):
		_call_bridge_role_action("guard")
	if event.is_action_pressed(observe_pose_action):
		_call_bridge_role_action("observe")
	if event.is_action_pressed(speak_pose_action):
		_call_bridge_role_action("speak")
	if event.is_action_pressed(inspect_pose_action):
		_call_bridge_role_action("inspect")
	if event.is_action_pressed(alert_pose_action):
		_call_bridge_role_action("alert")
	if event.is_action_pressed(ambient_pose_action):
		_call_bridge_role_action("ambient")
	if event.is_action_pressed(sword_swing_action):
		if not sword_swing_pressed:
			_call_bridge_combat_action("sword_swing")
		sword_swing_pressed = true
	elif event.is_action_released(sword_swing_action):
		sword_swing_pressed = false
	if event.is_action_pressed(shield_block_action):
		if not shield_block_pressed:
			_call_bridge_combat_action("shield_block")
		shield_block_pressed = true
	elif event.is_action_released(shield_block_action):
		shield_block_pressed = false

func _call_bridge_role_action(action_tag: String) -> void:
	if player_bridge and player_bridge.has_method("trigger_role_action"):
		player_bridge.trigger_role_action(action_tag)

func _call_bridge_combat_action(action_tag: String) -> void:
	if player_bridge and player_bridge.has_method("trigger_combat_action"):
		player_bridge.trigger_combat_action(action_tag)
