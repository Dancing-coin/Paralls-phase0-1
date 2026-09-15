extends RefCounted

class_name CharacterIntentFrame


static func build(physics_tick: int, admitted: Array[Dictionary], queued: Array[Dictionary], rejected: Array[Dictionary]) -> Dictionary:
	var admitted_copy := admitted.duplicate(true)
	var queued_copy := queued.duplicate(true)
	var rejected_copy := rejected.duplicate(true)
	return {
		"physics_tick": physics_tick,
		"admitted": admitted_copy,
		"queued": queued_copy,
		"rejected": rejected_copy,
		"admitted_ids": _ids(admitted_copy),
		"queued_ids": _ids(queued_copy),
		"rejected_ids": _ids(rejected_copy),
		"immutable": true,
	}


static func _ids(entries: Array[Dictionary]) -> Array[StringName]:
	var ids: Array[StringName] = []
	for entry in entries:
		ids.append(StringName(entry.get("request_id", entry.get("lease_id", entry.get("action_instance_id", "")))))
	return ids
