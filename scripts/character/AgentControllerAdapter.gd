extends RefCounted

class_name AgentControllerAdapter

const CharacterControllerPortRef = preload("res://scripts/character/CharacterControllerPort.gd")
const CharacterControlModeRef = preload("res://scripts/character/CharacterControlMode.gd")


static func build_intent_frame(actor_id: String, candidate: Dictionary) -> Dictionary:
	var next_frame := {
		"actor_id": actor_id,
		"controller_source": "agent",
		"control_mode": CharacterControlModeRef.AGENT_CONTROLLED,
	}
	for key in candidate.keys():
		next_frame[key] = candidate[key]
	next_frame["actor_id"] = actor_id
	next_frame["controller_source"] = "agent"
	next_frame["control_mode"] = CharacterControlModeRef.AGENT_CONTROLLED
	return CharacterControllerPortRef.normalize_intent_frame(next_frame)


static func build_intent_proposal(message: Dictionary) -> Dictionary:
	var forbidden_fields := [
		"transform", "velocity", "global_position", "linear_velocity",
		"animation", "animation_state", "clip", "clip_ref", "raw_clip_filename",
		"damage", "hit", "inventory", "inventory_mutation", "projectile", "ammo",
		"status_write", "world_truth", "world_write",
	]
	for field in forbidden_fields:
		if message.has(field):
			return {"accepted": false, "reason": "forbidden_intent_field:%s" % field}
	var semantic_action_id := str(message.get("semantic_action_id", message.get("action_id", "")))
	if semantic_action_id.to_lower() in ["boxing", "short punch", "sword attack"] or semantic_action_id.ends_with(".glb") or semantic_action_id.ends_with(".fbx") or semantic_action_id.contains("/") or semantic_action_id.contains("\\"):
		return {"accepted": false, "reason": "raw_clip_filename_forbidden"}
	var raw := message.duplicate(true)
	raw["action_id"] = semantic_action_id
	raw["intent_tags"] = message.get("intent_tags", []).duplicate()
	raw["context_tags"] = message.get("context_tags", []).duplicate()
	var proposal := CharacterControllerPortRef.submit_intent_proposal(
		raw,
		StringName(message.get("source_id", "agent")),
		CharacterControlModeRef.AGENT_CONTROLLED,
	)
	if not bool(proposal.get("accepted", false)):
		return proposal
	proposal["semantic_action_id"] = semantic_action_id
	proposal["claims"] = message.get("claims", []).duplicate()
	proposal["locomotion_relation"] = str(message.get("locomotion_relation", "coexist"))
	proposal["presentation_cues"] = message.get("presentation_cues", []).duplicate()
	proposal["reason_codes"] = message.get("reason_codes", []).duplicate()
	return proposal
