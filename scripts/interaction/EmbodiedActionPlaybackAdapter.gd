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


func restore_local_ownership() -> void:
	if playback_host != null and playback_host.has_method("restore_reviewed_action_playback"):
		playback_host.call("restore_reviewed_action_playback")
	local_ownership_restored = true
