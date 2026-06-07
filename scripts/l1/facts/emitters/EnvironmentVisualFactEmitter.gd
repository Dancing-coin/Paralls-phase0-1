extends Node

@export_node_path("Node") var visual_fact_emitter_path := NodePath("..")

var _last_emitted_state_by_environment: Dictionary = {}


func emit_environment_state_transition(environment_id: String, previous_state: String, next_state: String) -> bool:
	if environment_id == "":
		return false
	if previous_state == next_state:
		return false

	_last_emitted_state_by_environment[environment_id] = next_state

	if next_state != "alerted":
		return false

	var visual_fact_emitter := _get_visual_fact_emitter()
	if visual_fact_emitter == null or not visual_fact_emitter.has_method("emit_visual_fact"):
		return false

	var emitted: bool = visual_fact_emitter.emit_visual_fact(
		"light_level_drop",
		"environment_light_drop",
		"",
		"",
		environment_id,
		"set",
		"environment_state/%s" % environment_id
	)
	if not emitted:
		return false

	_bus_log("phase0_visual_fact:light_level_drop:%s" % environment_id)
	return true


func _get_visual_fact_emitter() -> Node:
	return get_node_or_null(visual_fact_emitter_path)


func _get_bus() -> Node:
	return get_node_or_null("/root/LocalPresentationBus")


func _bus_log(message: String) -> void:
	var bus := _get_bus()
	if bus and bus.has_method("log_debug"):
		bus.log_debug(message)
