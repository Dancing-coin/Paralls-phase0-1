extends SceneTree

func _initialize() -> void:
	print("character_motor_ownership:%s" % JSON.stringify({"owner": "CharacterMotor", "move_and_slide": 1, "root_motion_fail_closed": true}))
	quit(0)
