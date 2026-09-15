extends RefCounted

class_name LayerControlProposal


static func from_intent(proposal: Dictionary) -> Dictionary:
	if not bool(proposal.get("accepted", false)):
		return proposal.duplicate(true)
	var requested_claims: Array[StringName] = []
	if (proposal.get("move_local", Vector2.ZERO) as Vector2).length() > 0.001:
		requested_claims.append(&"world_motion")
		requested_claims.append(&"facing")
	var action_id := StringName(proposal.get("action_id", ""))
	return {
		"accepted": true,
		"proposal": proposal.duplicate(true),
		"desired_channels": [&"locomotion"] if action_id.is_empty() else [&"locomotion", &"action"],
		"add_projection_tags": proposal.get("intent_tags", []).duplicate(),
		"remove_projection_tags": [],
		"requested_claims": requested_claims,
		"cancellation_policy": StringName(proposal.get("cancellation_policy", "queue")),
		"root_motion_policy": StringName(proposal.get("root_motion_policy", "hold")),
	}
