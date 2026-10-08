extends Node

class_name CharacterCameraController

@export var offset := Vector3(4.8, 3.1, 6.6)
@export var follow_speed := 4.0

var camera: Camera3D

func setup(value: Camera3D) -> void:
	camera = value

func follow(actor: Node3D, delta: float) -> void:
	if camera == null or actor == null:
		return
	var target := actor.global_position + Vector3(0.0, 1.0, 0.0)
	var desired := actor.global_position + offset
	camera.global_position = camera.global_position.lerp(desired, minf(1.0, follow_speed * delta))
	camera.look_at(target, Vector3.UP)
