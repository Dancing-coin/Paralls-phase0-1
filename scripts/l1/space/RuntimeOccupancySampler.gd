extends RefCounted

class_name RuntimeOccupancySampler

var field_id := "occupancy:runtime"
var static_model_ref := ""
var zone_states: Dictionary = {}
var object_states: Dictionary = {}
var dirty_events: Array[Dictionary] = []
var full_scene_rescan_count := 0


func initialize_from_space_model(model: Dictionary) -> void:
	static_model_ref = str(model.get("model_id", ""))
	for element: Dictionary in model.get("elements", []):
		if str(element.get("element_type", "")) == "zone":
			_ensure_zone(str(element.get("element_id", "zone_focus")))


func apply_actor_zone(actor_id: String, zone_id: String, source_ref: String) -> void:
	var zone := _ensure_zone(zone_id)
	var actor_ids: Array = zone.get("actor_ids", [])
	if not actor_ids.has(actor_id):
		actor_ids.append(actor_id)
	zone["actor_ids"] = actor_ids
	_mark_dirty(zone_id, "actor_entered_zone", source_ref)


func apply_environment_field(zone_id: String, visibility_level: String, smoke_density: String, source_ref: String) -> void:
	var zone := _ensure_zone(zone_id)
	zone["visibility"] = visibility_level
	zone["passability"] = "requires_detour" if visibility_level != "clear" or smoke_density in ["dense", "heavy"] else "passable"
	zone["environment_field_ref"] = source_ref
	_mark_dirty(zone_id, "environment_field_changed", source_ref)


func apply_object_state(object_id: String, zone_id: String, state: String, affordances: Array[String], occludes: bool, source_ref: String) -> void:
	var updated_at := Time.get_ticks_msec()
	object_states[object_id] = {
		"object_id": object_id,
		"zone_id": zone_id,
		"state": state,
		"affordances": affordances,
		"occludes": occludes,
		"source_refs": [source_ref],
		"updated_at": updated_at,
	}
	var zone := _ensure_zone(zone_id)
	var object_ids: Array = zone.get("object_ids", [])
	if not object_ids.has(object_id):
		object_ids.append(object_id)
	zone["object_ids"] = object_ids
	_mark_dirty(zone_id, "object_state_changed", source_ref)


func snapshot() -> Dictionary:
	return {
		"field_id": field_id,
		"static_model_ref": static_model_ref,
		"zone_states": zone_states,
		"object_states": object_states,
		"dirty_zone_ids": zone_states.keys(),
		"dirty_events": dirty_events,
		"full_scene_rescan_count": full_scene_rescan_count,
		"update_strategy": "dirty_zone_event_driven_incremental",
	}


func write_artifact(relative_path: String = ".harness/verification/l1-occupancy-runtime.json") -> String:
	var path := ProjectSettings.globalize_path("res://" + relative_path)
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return ""
	file.store_string(JSON.stringify(snapshot(), "\t"))
	file.close()
	return path


func _ensure_zone(zone_id: String) -> Dictionary:
	if not zone_states.has(zone_id):
		zone_states[zone_id] = {
			"zone_id": zone_id,
			"actor_ids": [],
			"object_ids": [],
			"visibility": "clear",
			"passability": "passable",
			"environment_field_ref": "",
		}
	return zone_states[zone_id]


func _mark_dirty(zone_id: String, update_kind: String, source_ref: String) -> void:
	dirty_events.append({
		"update_kind": update_kind,
		"zone_id": zone_id,
		"producer_ts": Time.get_ticks_msec(),
		"source_refs": [source_ref],
	})
