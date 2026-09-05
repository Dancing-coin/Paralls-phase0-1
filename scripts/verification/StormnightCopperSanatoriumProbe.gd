extends Node3D

const VIEW := preload("res://scripts/verification/StormnightCopperSanatoriumView.gd")
const ROOMS := ["arrival", "records", "treatment", "courtyard"]

var view: Node


func _ready() -> void:
	view = VIEW.new()
	add_child(view)
	_build_scene()
	call_deferred("_run_probe")


func _run_probe() -> void:
	view.apply_committed_projection({
		"phase_ref": "phase:stormnight:investigation@1",
		"committed_clue_refs": ["clue:stormnight:01@1", "clue:stormnight:02@1"],
		"private_fact_refs": ["fact:stormnight:02@1"],
		"pursuit": "none",
		"accusation_status": "eligible",
		"terminal_outcome": "none",
		"voice_state": "clue_found",
	})
	view.apply_speculative_projection({"phase_ref": "phase:stormnight:storm-night@1"})
	var rejection: Dictionary = view.reject_speculative_state("probe_rejected")
	var panel: Dictionary = view.read_only_panel_state()
	var ok: bool = ROOMS.size() == 4 and rejection.get("speculative_state_cleared", false) and panel.get("phase", "") == "phase:stormnight:investigation@1" and panel.get("voice_state", "") == "rejected"
	var report := {"status": "godot-runtime-stormnight-verified" if ok else "godot-runtime-stormnight-failed", "rooms": ROOMS, "panel": panel, "rejection": rejection}
	var path := ProjectSettings.globalize_path("res://.harness/verification/stormnight-copper-sanatorium-godot-runtime.json")
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(report, "\t"))
		file.close()
	print("stormnight_copper_sanatorium_probe:verified=%s" % str(ok).to_lower())
	get_tree().quit(0 if ok else 1)


func _build_scene() -> void:
	for index in range(ROOMS.size()):
		var room := Node3D.new()
		room.name = "Room_%s" % ROOMS[index]
		room.set_meta("room_ref", "location:stormnight:%s@1" % ROOMS[index])
		room.position = Vector3(float(index) * 8.0, 0.0, 0.0)
		add_child(room)
		_add_box(room, "Floor", Vector3(6.0, 0.2, 6.0), Vector3(0.0, -0.1, 0.0), Color(0.12, 0.14, 0.18))
		_add_box(room, "Occluder_%s" % index, Vector3(0.4, 2.2, 3.0), Vector3(0.0, 1.1, 0.0), Color(0.22, 0.28, 0.36))
		_add_box(room, "HideSpot_%s" % index, Vector3(1.4, 1.2, 1.4), Vector3(1.4, 0.6, 1.6), Color(0.18, 0.42, 0.28))
		_add_box(room, "Door_%s" % index, Vector3(0.5, 2.4, 1.8), Vector3(3.0, 1.2, 0.0), Color(0.45, 0.30, 0.16))
		_add_box(room, "EvidenceTable_%s" % index, Vector3(1.4, 0.8, 0.8), Vector3(-1.6, 0.4, -1.6), Color(0.65, 0.48, 0.25))
		room.set_meta("sound_zone_ref", "sound-zone:stormnight:%s@1" % ROOMS[index])


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
