extends Node


func _ready() -> void:
	var payload_path := OS.get_environment("BAKERY_MIRROR_PAYLOAD")
	if payload_path == "":
		push_error("bakery_mirror_probe:payload_missing")
		get_tree().quit(1)
		return
	var file := FileAccess.open(payload_path, FileAccess.READ)
	if file == null:
		push_error("bakery_mirror_probe:payload_unreadable")
		get_tree().quit(1)
		return
	var parsed = JSON.parse_string(file.get_as_text())
	if not (parsed is Dictionary):
		push_error("bakery_mirror_probe:payload_invalid")
		get_tree().quit(1)
		return
	var group = parsed.get("groups", {}).get("bakery.gameplay", {})
	var mirror_payload = group.get("payload", {})
	var valid := (
		str(parsed.get("consumer", "")) == "godot"
		and str(mirror_payload.get("facility_state", "")) == "acquired"
		and str(mirror_payload.get("output_state", "")) == "sold"
		and int(mirror_payload.get("output_count", 0)) >= 1
		and str(parsed.get("view_checksum", "")) != ""
	)
	if not valid:
		push_error("bakery_mirror_probe:committed_view_invalid")
		get_tree().quit(1)
		return
	print("bakery_committed_mirror_probe:proved:facility=acquired:output=sold")
	get_tree().quit(0)
