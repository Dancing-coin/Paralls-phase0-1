extends Node

class_name EmbodiedActionPlaybackAdapter


var playback_host: Node
var phase_playback_trace: Array[Dictionary] = []
var local_ownership_restored := true


func configure_playback_host(host: Node) -> void:
	playback_host = host


func begin_phase(phase: String, action_atoms: Array[Dictionary]) -> Dictionary:
	if action_atoms.is_empty():
		phase_playback_trace.append({
			"phase": phase,
			"action_tags": [],
			"local_execution_only": true,
		})
		return {"accepted": true, "status": "no_local_atom"}
	if playback_host == null or not playback_host.has_method("play_reviewed_action_atom"):
		return {"accepted": false, "status": "local_playback_unavailable"}
	local_ownership_restored = false
	var action_tags: Array[String] = []
	var played_clips: Array[String] = []
	for atom: Dictionary in action_atoms:
		var result: Variant = playback_host.call(
			"play_reviewed_action_atom",
			str(atom.get("action_tag", "")),
			str(atom.get("animation_clip_ref", "")),
			phase
		)
		if not (result is Dictionary) or not bool(result.get("accepted", false)):
			return {"accepted": false, "status": "local_playback_unavailable"}
		action_tags.append(str(atom.get("action_tag", "")))
		played_clips.append(str(result.get("played_clip", "")))
	phase_playback_trace.append({
		"phase": phase,
		"action_tags": action_tags,
		"played_clips": played_clips,
		"local_execution_only": true,
	})
	return {"accepted": true, "status": "played", "played_clips": played_clips}


func begin_qualified_phase(phase: String, qualified_profiles: Array[Dictionary]) -> Dictionary:
	if qualified_profiles.is_empty():
		phase_playback_trace.append({
			"phase": phase,
			"semantic_action_ids": [],
			"profile_ids": [],
			"local_execution_only": true,
		})
		return {"accepted": true, "status": "no_qualified_profile"}
	if playback_host == null or not playback_host.has_method("play_qualified_profile"):
		return {"accepted": false, "status": "qualified_profile_playback_unavailable"}
	local_ownership_restored = false
	var semantic_action_ids: Array[String] = []
	var profile_ids: Array[String] = []
	var observations: Array[Dictionary] = []
	for profile: Dictionary in qualified_profiles:
		var semantic_action_id := str(profile.get("semantic_action_id", ""))
		var profile_id := str(profile.get("profile_id", ""))
		if semantic_action_id.is_empty() or profile_id.is_empty() or str(profile.get("qualification_status", "rejected")) == "rejected":
			return {"accepted": false, "status": "qualified_profile_invalid"}
		var result: Variant = playback_host.call("play_qualified_profile", profile.duplicate(true))
		if not (result is Dictionary) or not bool(result.get("accepted", false)):
			return {"accepted": false, "status": "qualified_profile_playback_unavailable"}
		semantic_action_ids.append(semantic_action_id)
		profile_ids.append(profile_id)
		observations.append(result.duplicate(true))
	phase_playback_trace.append({
		"phase": phase,
		"semantic_action_ids": semantic_action_ids,
		"profile_ids": profile_ids,
		"observations": observations,
		"local_execution_only": true,
	})
	return {"accepted": true, "status": "played", "semantic_action_ids": semantic_action_ids, "profile_ids": profile_ids, "observations": observations}


func restore_local_ownership() -> void:
	if playback_host != null and playback_host.has_method("restore_reviewed_action_playback"):
		playback_host.call("restore_reviewed_action_playback")
	local_ownership_restored = true
