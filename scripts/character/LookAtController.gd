extends Node3D

func look_at_target(target_position: Vector3) -> void:
    look_at(target_position, Vector3.UP)
