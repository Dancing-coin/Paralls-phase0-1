extends Node

@export var idle_sway_amount := 0.03
@export var idle_sway_speed := 2.2
@export var dialogue_lean_amount := 0.16
@export var interact_lean_amount := 0.1
@export var posture_recover_speed := 5.2
@export var action_hold_duration := 0.55

@onready var visual_root: Node3D = $"../VisualRoot"

var sway_time := 0.0
var posture_offset := Vector3.ZERO
var posture_target := Vector3.ZERO
var hold_timer := 0.0

func _process(delta: float) -> void:
	sway_time += delta * idle_sway_speed
	if hold_timer > 0.0:
		hold_timer = max(hold_timer - delta, 0.0)
	elif posture_target.length() > 0.001:
		posture_target = Vector3.ZERO

	posture_offset = posture_offset.lerp(posture_target, clamp(posture_recover_speed * delta, 0.0, 1.0))
	_apply_visual_offset()

func trigger_dialogue_feedback() -> void:
	posture_target = Vector3(0.0, 0.0, -dialogue_lean_amount)
	hold_timer = action_hold_duration

func trigger_interact_feedback() -> void:
	posture_target = Vector3(0.0, -interact_lean_amount * 0.35, -interact_lean_amount)
	hold_timer = action_hold_duration

func _apply_visual_offset() -> void:
	if visual_root == null:
		return
	var offset_y := sin(sway_time) * idle_sway_amount
	visual_root.position = Vector3(posture_offset.x, posture_offset.y + offset_y, posture_offset.z)
