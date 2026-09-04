extends Node3D

const ROOMS := ["entry", "archive", "safe_room"]
const VOICE_TEMPLATES := {
	"preparing": "准备进入行动窗口。",
	"detected": "你已暴露，立即改变策略。",
	"captured": "控制权已被对手取得。",
	"escaped": "你已脱离当前追捕窗口。",
	"rejected": "行动被权威状态拒绝，已回到上次确认位置。",
	"returned": "已恢复到最近一次可回放的确认状态。",
}

var committed_projection: Dictionary = {
	"encounter_ref": "encounter:scripted-mystery-probe",
	"phase": "idle",
	"exposure": 0,
	"control": "none",
	"terminal_outcome": "none",
	"source_revision_vector": {},
}
var speculative_projection: Dictionary = {}
var voice_state := "returned"


func _ready() -> void:
	_build_greybox_reference_scene()
	_apply_voice_state("returned")


func apply_committed_projection(projection: Dictionary) -> void:
	# Only backend committed/read-only mirror data may update this state.
	committed_projection = projection.duplicate(true)
	speculative_projection.clear()
	_apply_voice_state(str(committed_projection.get("phase", "returned")))


func set_speculative_projection(projection: Dictionary) -> void:
	# Speculation is local presentation only and never treated as truth.
	speculative_projection = projection.duplicate(true)


func reject_speculative_state(reason: String = "authority_rejected") -> Dictionary:
	speculative_projection.clear()
	_apply_voice_state("rejected")
	return {"accepted": false, "reason": reason, "speculative_state_cleared": true}


func _apply_voice_state(state: String) -> void:
	voice_state = state if VOICE_TEMPLATES.has(state) else "returned"


func get_read_only_projection() -> Dictionary:
	return {
		"committed": committed_projection.duplicate(true),
		"speculative": speculative_projection.duplicate(true),
		"voice_state": voice_state,
		"voice_template": VOICE_TEMPLATES.get(voice_state, ""),
	}


func _build_greybox_reference_scene() -> void:
	for index in range(ROOMS.size()):
		var room := Node3D.new()
		room.name = "Room_%s" % ROOMS[index]
		room.set_meta("room_ref", "room:%s@1" % ROOMS[index])
		room.position = Vector3(float(index) * 8.0, 0.0, 0.0)
		add_child(room)
		_add_box(room, "Floor", Vector3(6.0, 0.2, 6.0), Vector3(0.0, -0.1, 0.0), Color(0.12, 0.14, 0.18))
		_add_box(room, "Occluder", Vector3(0.4, 2.2, 3.0), Vector3(0.0, 1.1, 0.0), Color(0.22, 0.28, 0.36))
		_add_box(room, "Door", Vector3(0.5, 2.4, 1.8), Vector3(3.0, 1.2, 0.0), Color(0.45, 0.30, 0.16))
		_add_box(room, "Clue", Vector3(0.6, 0.6, 0.6), Vector3(-1.8, 0.3, -1.8), Color(0.85, 0.72, 0.22))
		_add_box(room, "HideSpot", Vector3(1.4, 1.2, 1.4), Vector3(1.4, 0.6, 1.6), Color(0.18, 0.42, 0.28))
		room.set_meta("sound_zone_ref", "sound-zone:%s@1" % ROOMS[index])


func _add_box(parent: Node3D, node_name: String, size: Vector3, position: Vector3, color: Color) -> void:
	var mesh_instance := MeshInstance3D.new()
	mesh_instance.name = node_name
	var mesh := BoxMesh.new()
	mesh.size = size
	mesh_instance.mesh = mesh
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	mesh_instance.material_override = material
	mesh_instance.position = position
	parent.add_child(mesh_instance)

