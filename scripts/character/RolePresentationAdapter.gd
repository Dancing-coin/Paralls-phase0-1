extends RefCounted

class_name RolePresentationAdapter


const FORBIDDEN_TRUTH_FIELDS := [&"transform", &"global_position", &"velocity", &"damage", &"hit", &"inventory", &"status", &"action_attempt", &"authority_result"]

var _registry: CharacterEmbodimentAssetRegistry
var _presentation_target: Node


func _init(registry: CharacterEmbodimentAssetRegistry, presentation_target: Node = null) -> void:
	_registry = registry
	_presentation_target = presentation_target


func apply_input(input: Dictionary) -> Dictionary:
	for field in FORBIDDEN_TRUTH_FIELDS:
		if input.has(String(field)):
			return {"accepted": false, "reason": StringName("world_truth_input_forbidden:%s" % field), "playback_observations": []}
	var package_id := StringName(str(input.get("package_id", "")))
	var semantic_action_id := StringName(str(input.get("semantic_action_id", "")))
	var claims := _normalize_claims(input.get("claims", []))
	if String(package_id).is_empty() or String(semantic_action_id).is_empty():
		return {"accepted": false, "reason": &"semantic_presentation_request_required", "playback_observations": []}
	var resolved := _registry.resolve(package_id, semantic_action_id, claims)
	if not bool(resolved.get("accepted", false)):
		return {"accepted": false, "reason": resolved.get("reason", &"profile_unavailable"), "playback_observations": []}
	var observation := {
		"semantic_action_id": semantic_action_id,
		"package_id": package_id,
		"profile_id": resolved.get("profile", {}).get("profile_id", ""),
		"markers": resolved.get("profile", {}).get("timing_markers", []),
		"status": resolved.get("status", "available"),
	}
	if _presentation_target != null and _presentation_target.has_method("play_qualified_profile"):
		var target_observation: Variant = _presentation_target.call("play_qualified_profile", resolved.get("profile", {}))
		if target_observation is Dictionary:
			observation["target_observation"] = target_observation
	return {"accepted": true, "selected_profile": resolved.get("profile", {}).duplicate(true), "playback_observations": [observation]}


func _normalize_claims(raw_claims: Variant) -> Array[StringName]:
	var claims: Array[StringName] = []
	if raw_claims is Array:
		for raw_claim in raw_claims:
			var claim := StringName(str(raw_claim))
			if not String(claim).is_empty() and not claims.has(claim):
				claims.append(claim)
	return claims
