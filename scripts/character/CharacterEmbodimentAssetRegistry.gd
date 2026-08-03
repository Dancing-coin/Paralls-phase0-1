extends RefCounted

class_name CharacterEmbodimentAssetRegistry

var _motion_assets: Dictionary = {}
var _reviewed_action_catalog: Dictionary = {}


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


func register_reviewed_action_catalog(entries: Array[Dictionary]) -> Dictionary:
	var registered_action_tags: Array[String] = []
	var rejected_action_tags: Array[String] = []
	for entry: Dictionary in entries:
		if not bool(entry.get("reviewed", false)):
			rejected_action_tags.append(str(entry.get("descriptor", {}).get("action_tag", "")))
			continue
		var descriptor_candidate: Variant = entry.get("descriptor", {})
		if not (descriptor_candidate is Dictionary):
			rejected_action_tags.append("")
			continue
		var descriptor := CharacterActionAssetDescriptor.normalize(descriptor_candidate)
		var action_tag := str(descriptor.get("action_tag", ""))
		var clip_ref := str(descriptor.get("animation_clip_ref", ""))
		var controller_phase := str(entry.get("controller_phase", ""))
		var registration_keys: Variant = entry.get("registration_keys", [])
		if action_tag.is_empty() or clip_ref.is_empty() or controller_phase.is_empty() or not (registration_keys is Array):
			rejected_action_tags.append(action_tag)
			continue
		var normalized_keys: Array[String] = []
		for value: Variant in registration_keys:
			var key := str(value)
			if not key.is_empty() and not normalized_keys.has(key):
				normalized_keys.append(key)
		if normalized_keys.is_empty() or not normalized_keys.has(action_tag):
			rejected_action_tags.append(action_tag)
			continue
		for key: String in normalized_keys:
			register_action_asset(key, descriptor)
		_reviewed_action_catalog[action_tag] = {
			"action_tag": action_tag,
			"controller_phase": controller_phase,
			"registration_keys": normalized_keys,
			"descriptor": descriptor.duplicate(true),
		}
		registered_action_tags.append(action_tag)
	return {
		"status": "available" if rejected_action_tags.is_empty() else "action_assets_unavailable",
		"registered_action_tags": registered_action_tags,
		"rejected_action_tags": rejected_action_tags,
	}


func inventory_reviewed_action_assets() -> Array[Dictionary]:
	var inventory: Array[Dictionary] = []
	for action_tag: String in _reviewed_action_catalog:
		inventory.append(_reviewed_action_catalog[action_tag].duplicate(true))
	return inventory


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
	var selected_action_tags: Array[String] = []
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
		var action_tag := str(descriptor.get("action_tag", ""))
		if action_tag.is_empty():
			missing_action_keys.append(semantic_key)
			continue
		if selected_action_tags.has(action_tag):
			continue
		selected_action_atoms.append(descriptor)
		selected_action_tags.append(action_tag)

	return {
		"status": "available" if missing_action_keys.is_empty() else "action_assets_unavailable",
		"selected_action_atoms": selected_action_atoms,
		"selected_action_tags": selected_action_tags,
		"missing_action_keys": missing_action_keys,
	}
