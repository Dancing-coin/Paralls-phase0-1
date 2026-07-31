extends Node

class_name CharacterPresentationAssetResolver


const MANIFEST_CONTRACT := "character_presentation_bindings.v1"

@export_file("*.json") var binding_manifest_path := "res://assets/characters/asset_manifests/character_presentation_bindings.json"
@export var apply_on_ready := true

var _bindings_by_actor_id: Dictionary = {}


func _ready() -> void:
	if apply_on_ready:
		call_deferred("load_and_apply")


func load_and_apply() -> Dictionary:
	var manifest := _load_manifest()
	if manifest.is_empty():
		return {"loaded": false, "applied_actor_ids": []}
	_bindings_by_actor_id = _index_approved_bindings(manifest)
	var applied_actor_ids: Array[String] = []
	var scene := get_tree().current_scene
	if scene == null:
		return {"loaded": true, "applied_actor_ids": applied_actor_ids}
	for actor_node in _find_actor_nodes(scene):
		var actor_id := str(actor_node.get("actor_id"))
		var binding: Dictionary = _bindings_by_actor_id.get(actor_id, {})
		if binding.is_empty() or not actor_node.has_method("apply_presentation_asset_binding"):
			continue
		if bool(actor_node.apply_presentation_asset_binding(binding)):
			applied_actor_ids.append(actor_id)
	return {"loaded": true, "applied_actor_ids": applied_actor_ids}


func _load_manifest() -> Dictionary:
	if binding_manifest_path.is_empty() or not FileAccess.file_exists(binding_manifest_path):
		return {}
	var source := FileAccess.get_file_as_string(binding_manifest_path)
	var parsed: Variant = JSON.parse_string(source)
	if not (parsed is Dictionary):
		push_warning("Character presentation asset manifest must be a JSON object")
		return {}
	var manifest: Dictionary = parsed
	if str(manifest.get("contract", "")) != MANIFEST_CONTRACT:
		push_warning("Character presentation asset manifest contract is unsupported")
		return {}
	if not (manifest.get("bindings", []) is Array):
		push_warning("Character presentation asset manifest bindings must be an array")
		return {}
	return manifest


func _index_approved_bindings(manifest: Dictionary) -> Dictionary:
	var indexed: Dictionary = {}
	for candidate in manifest.get("bindings", []):
		if not (candidate is Dictionary):
			continue
		var binding: Dictionary = candidate
		var actor_id := str(binding.get("actor_id", ""))
		var binding_status := str(binding.get("binding_status", "candidate"))
		if actor_id.is_empty():
			continue
		if binding_status != "approved":
			continue
		if indexed.has(actor_id):
			push_warning("Character presentation asset manifest contains duplicate approved actor binding: %s" % actor_id)
			continue
		indexed[actor_id] = binding
	return indexed


func _find_actor_nodes(root: Node) -> Array[Node]:
	var matches: Array[Node] = []
	_find_actor_nodes_recursive(root, matches)
	return matches


func _find_actor_nodes_recursive(node: Node, matches: Array[Node]) -> void:
	if node.has_method("apply_presentation_asset_binding") and not str(node.get("actor_id")).is_empty():
		matches.append(node)
	for child in node.get_children():
		_find_actor_nodes_recursive(child, matches)
