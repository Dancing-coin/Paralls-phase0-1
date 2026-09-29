extends SceneTree

func _initialize() -> void:
	var result := {"qualified": false, "rejection_reason": "root_motion_not_calibrated", "policy": "hold", "max_distance": 0.0, "max_duration_ticks": 0}
	print("root_motion_qualification:%s" % JSON.stringify(result))
	quit(0)
