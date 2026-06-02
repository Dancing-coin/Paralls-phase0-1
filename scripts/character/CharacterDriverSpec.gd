extends Resource

class_name CharacterDriverSpec

enum DriverMode {
	AI,
	PLAYER,
}

@export var driver_mode: DriverMode = DriverMode.AI
@export var move_target: Vector3 = Vector3.ZERO
@export var has_move_target := false
@export var look_target: Vector3 = Vector3.ZERO
@export var has_look_target := false
@export var requested_action := ""
