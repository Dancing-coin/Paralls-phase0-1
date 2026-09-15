extends RefCounted

class_name ResourceClaimScheduler

const CANONICAL_CLAIMS := [
	"full_body_pose", "pelvis", "upper_body", "left_arm", "right_arm", "left_hand", "right_hand",
	"left_leg", "right_leg", "head", "root_translation", "world_motion", "facing", "physics_body",
	"support_contact", "interaction_reach", "weapon_slot:{slot_id}", "weapon_hit_volume:{weapon_id}",
	"target_occupancy:{target_id}", "voice_channel", "ragdoll_body",
]
const PARENT_CLAIMS := {
	"full_body_pose": ["pelvis", "upper_body", "left_leg", "right_leg"],
	"upper_body": ["left_arm", "right_arm", "left_hand", "right_hand"],
	"left_arm": ["left_hand"],
	"right_arm": ["right_hand"],
}


static func decide(request: Dictionary, occupancy: Dictionary, tick: int) -> Dictionary:
	var conflicts: Array[StringName] = []
	var owners: Array[StringName] = []
	for claim_value in request.get("claims", []):
		var claim := StringName(claim_value)
		for occupied_value in occupancy:
			var occupied := StringName(occupied_value)
			if _claims_conflict(claim, occupied):
				conflicts.append(claim)
				owners.append(StringName(occupancy[occupied_value]))
	if conflicts.is_empty():
		return {"decision": &"accept_now", "claims": request.get("claims", []), "conflicting_owner_ids": [], "reason": &"available", "tick": tick}
	var wants_queue := StringName(request.get("cancellation_policy", "queue")) == &"queue"
	return {
		"decision": &"queue" if wants_queue else &"reject",
		"claims": request.get("claims", []),
		"conflicting_owner_ids": owners,
		"reason": &"claim_conflict",
		"tick": tick,
	}


static func _claims_conflict(left: StringName, right: StringName) -> bool:
	if left == right:
		return true
	return _is_parent_of(left, right) or _is_parent_of(right, left)


static func _is_parent_of(parent: StringName, child: StringName) -> bool:
	for child_name in PARENT_CLAIMS.get(str(parent), []):
		if StringName(child_name) == child or _is_parent_of(StringName(child_name), child):
			return true
	return false
