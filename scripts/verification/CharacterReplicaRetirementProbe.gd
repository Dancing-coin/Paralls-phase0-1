extends RefCounted
class_name CharacterReplicaRetirementProbe

const MATRIX_PATH := "res://docs/character/character-replica-retirement-matrix-2026-09-29.md"
const ROOTS := ["scenes", "scripts", "backend"]


static func inspect() -> Dictionary:
	var matrix_source := FileAccess.get_file_as_string(MATRIX_PATH)
	var rows: Variant = _matrix_rows(matrix_source)
	if not rows is Array:
		return {"passed": false, "error": "missing_or_invalid_matrix", "source_digest": ""}
	var registered := {}
	for row in rows:
		if not row is Dictionary or not row.has("caller_path"):
			return {"passed": false, "error": "invalid_matrix_row", "source_digest": ""}
		registered[str(row["caller_path"])] = row
	var paths: Array[String] = []
	for root in ROOTS:
		_scan_paths("res://%s" % root, paths)
	paths.sort()
	var digest := HashingContext.new()
	digest.start(HashingContext.HASH_SHA256)
	var unregistered: Array[String] = []
	var scene_instances := 0
	var script_references := 0
	var provider_lookups := 0
	var runtime_lookups := 0
	var movement_writers: Array[Dictionary] = []
	var animation_writers: Array[Dictionary] = []
	var compatibility_sites: Array[Dictionary] = []
	for path in paths:
		var source := FileAccess.get_file_as_string("res://%s" % path)
		if not source.contains("CharacterReplica") and not source.contains("legacy_character_replica"):
			continue
		digest.update((path + "\n").to_utf8_buffer())
		digest.update(source.to_utf8_buffer())
		digest.update(PackedByteArray([0]))
		if not registered.has(path):
			unregistered.append(path)
		if path.ends_with(".tscn") and path != "scenes/phase0/CharacterReplica.tscn" and path != "scenes/phase0/ValidationCharacterReplica.tscn":
			scene_instances += source.count("CharacterReplica.tscn") + source.count("ValidationCharacterReplica.tscn")
		var category := str(registered[path].get("category", "")) if registered.has(path) else ""
		if path.ends_with(".gd") and not category in ["compatibility", "migration_test", "verification", "comment_only"]:
			script_references += source.count("CharacterReplica")
			provider_lookups += source.count('get_node_or_null("CharacterReplica")') + source.count('get_node_or_null("PlayerCharacter/CharacterReplica")')
			runtime_lookups += source.count('get_node_or_null("CharacterReplica")') + source.count('get_node_or_null("PlayerCharacter/CharacterReplica")') + source.count('NodePath("../CharacterReplica")')
			_collect_compatibility_calls(path, source, compatibility_sites)
	for path in paths:
		if not path.ends_with(".gd") or path.begins_with("scripts/verification/"):
			continue
		var source := FileAccess.get_file_as_string("res://%s" % path)
		_collect_forbidden_calls(path, source, movement_writers, animation_writers)
	return {
		"source_digest": digest.finish().hex_encode(),
		"matrix_digest": matrix_source.sha256_text(),
		"active_scene_instances": scene_instances,
		"runtime_script_references": script_references,
		"runtime_replica_lookups": runtime_lookups,
		"provider_lookups": provider_lookups,
		"direct_body_writers_outside_motor": movement_writers.size(),
		"direct_body_writer_sites": movement_writers,
		"direct_animation_writers_outside_controller": animation_writers.size(),
		"direct_animation_writer_sites": animation_writers,
		"compatibility_call_count": compatibility_sites.size(),
		"compatibility_call_sites": compatibility_sites,
		"unregistered_callers": unregistered,
		"inventory_passed": unregistered.is_empty(),
		"passed": unregistered.is_empty() and scene_instances == 0 and script_references == 0 and runtime_lookups == 0 and compatibility_sites.is_empty() and movement_writers.is_empty() and animation_writers.is_empty(),
	}


static func _matrix_rows(source: String) -> Variant:
	var chunks := source.split("```json", false, 1)
	if chunks.size() != 2:
		return null
	var json_chunks := chunks[1].split("```", false, 1)
	if json_chunks.size() != 2:
		return null
	return JSON.parse_string(json_chunks[0].strip_edges())


static func _scan_paths(directory: String, paths: Array[String]) -> void:
	var access := DirAccess.open(directory)
	if access == null:
		return
	access.list_dir_begin()
	var name := access.get_next()
	while name != "":
		if access.current_is_dir():
			_scan_paths(directory.path_join(name), paths)
		elif name.ends_with(".gd") or name.ends_with(".tscn") or name.ends_with(".py"):
			paths.append(directory.path_join(name).trim_prefix("res://"))
		name = access.get_next()
	access.list_dir_end()


static func _collect_forbidden_calls(path: String, source: String, movement: Array[Dictionary], animation: Array[Dictionary]) -> void:
	var body_pattern := RegEx.new()
	body_pattern.compile("\\b(?:body|actor|replica|player)\\.(?:global_position|position|velocity(?:\\.[xyz])?)\\s*[+\\-]?=(?!=)|\\bvelocity\\.[xyz]\\s*[+\\-]?=(?!=)|\\.move_and_" + "slide\\s*\\(")
	var animation_pattern := RegEx.new()
	animation_pattern.compile("\\b(?:animation_player|animation_state_playback|playback)\\.(?:play|travel|seek)\\s*\\(")
	var lines := source.split("\n")
	for index in lines.size():
		var line := lines[index].strip_edges()
		if line.begins_with("#"):
			continue
		if path != "scripts/character/CharacterMotor.gd" and body_pattern.search(line) != null:
			movement.append({"path": path, "line": index + 1, "source": line})
		if path != "scripts/character/RoleAnimationController.gd" and animation_pattern.search(line) != null:
			animation.append({"path": path, "line": index + 1, "source": line})


static func _collect_compatibility_calls(path: String, source: String, sites: Array[Dictionary]) -> void:
	var pattern := RegEx.new()
	pattern.compile("\\b(?:replica|player_replica|character_replica)\\.[A-Za-z_][A-Za-z_0-9]*\\s*\\(")
	var lines := source.split("\n")
	for index in lines.size():
		var line := lines[index].strip_edges()
		if not line.begins_with("#") and pattern.search(line) != null:
			sites.append({"path": path, "line": index + 1, "source": line})
