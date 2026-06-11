extends Node

class_name CharacterMotor


func apply_intent_frame(body: CharacterBody3D, frame: Dictionary, _delta: float) -> Dictionary:
	body.move_and_slide()
	return {"frame": frame}
