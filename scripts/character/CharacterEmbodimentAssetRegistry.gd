extends RefCounted

class_name CharacterEmbodimentAssetRegistry

var _motion_assets: Dictionary = {}


func register_motion_asset(semantic_key: String, asset_ref: String) -> void:
	if semantic_key.is_empty() or asset_ref.is_empty():
		return
	_motion_assets[semantic_key] = asset_ref


func preload_assets_for_semantics(semantic_keys: Array[String]) -> Array[String]:
	var queued: Array[String] = []
	for semantic_key: String in semantic_keys:
		if not _motion_assets.has(semantic_key):
			continue
		queued.append(str(_motion_assets[semantic_key]))
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
