extends RefCounted

class_name CharacterEmbodimentAssetRegistry

var _motion_assets: Dictionary = {}


func register_motion_asset(semantic_key: String, asset_ref: String) -> void:
	if semantic_key.is_empty() or asset_ref.is_empty():
		return
	_motion_assets[semantic_key] = {
		"asset_ref": asset_ref,
		"descriptor": CharacterActionAssetDescriptor.normalize({
			"action_tag": semantic_key,
			"animation_clip_ref": asset_ref,
		}),
	}


func register_action_asset(action_tag: String, candidate: Dictionary) -> void:
	if action_tag.is_empty():
		return
	var descriptor := CharacterActionAssetDescriptor.normalize(candidate)
	if str(descriptor.get("action_tag", "")).is_empty():
		descriptor["action_tag"] = action_tag
	var asset_ref := str(descriptor.get("animation_clip_ref", ""))
	if asset_ref.is_empty():
		return
	_motion_assets[action_tag] = {
		"asset_ref": asset_ref,
		"descriptor": descriptor,
	}


func preload_assets_for_semantics(semantic_keys: Array[String]) -> Array[String]:
	var queued: Array[String] = []
	for semantic_key: String in semantic_keys:
		if not _motion_assets.has(semantic_key):
			continue
		var entry: Variant = _motion_assets[semantic_key]
		if entry is Dictionary:
			queued.append(str(entry.get("asset_ref", "")))
		else:
			queued.append(str(entry))
	return queued


func compose_realization_plan(semantic_keys: Array[String], generated_motion_allowed: bool) -> Dictionary:
	var local_fallback_asset_refs := preload_assets_for_semantics(semantic_keys)
	var missing_semantic_keys: Array[String] = []
	for semantic_key: String in semantic_keys:
		if _motion_assets.has(semantic_key):
			continue
		missing_semantic_keys.append(semantic_key)
	return {
		"semantic_keys": semantic_keys,
		"generated_motion_allowed": generated_motion_allowed,
		"local_fallback_asset_refs": local_fallback_asset_refs,
		"missing_semantic_keys": missing_semantic_keys,
	}


func resolve_action_atoms(primitive_action_tags: Array, primitive_realization_keys: Array) -> Dictionary:
	var requested_keys: Array[String] = []
	for value: Variant in primitive_action_tags:
		var action_tag := str(value)
		if not action_tag.is_empty() and not requested_keys.has(action_tag):
			requested_keys.append(action_tag)
	for value: Variant in primitive_realization_keys:
		var realization_key := str(value)
		if not realization_key.is_empty() and not requested_keys.has(realization_key):
			requested_keys.append(realization_key)

	var selected_action_atoms: Array[Dictionary] = []
	var missing_action_keys: Array[String] = []
	for semantic_key: String in requested_keys:
		if not _motion_assets.has(semantic_key):
			missing_action_keys.append(semantic_key)
			continue
		var entry: Variant = _motion_assets[semantic_key]
		var descriptor: Dictionary = {}
		if entry is Dictionary:
			descriptor = entry.get("descriptor", {}).duplicate(true)
		if descriptor.is_empty():
			missing_action_keys.append(semantic_key)
			continue
		selected_action_atoms.append(descriptor)

	return {
		"status": "available" if missing_action_keys.is_empty() else "action_assets_unavailable",
		"selected_action_atoms": selected_action_atoms,
		"missing_action_keys": missing_action_keys,
	}
