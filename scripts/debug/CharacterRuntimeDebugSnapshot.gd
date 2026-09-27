class_name CharacterRuntimeDebugSnapshot
extends RefCounted

static func capture(runtime: Dictionary, frame: Dictionary, command: Dictionary, motor_state: Dictionary) -> Dictionary:
	var snapshot := {
		"runtime": runtime.duplicate(true), "frame": frame.duplicate(true),
		"command": command.duplicate(true), "motor_state": motor_state.duplicate(true),
	}
	return _freeze(snapshot)

static func _freeze(value: Variant) -> Variant:
	if value is Dictionary:
		var out := {}
		for key in value:
			out[key] = _freeze(value[key])
		return out
	if value is Array:
		var out_array: Array = []
		for item in value:
			out_array.append(_freeze(item))
		return out_array
	return value
