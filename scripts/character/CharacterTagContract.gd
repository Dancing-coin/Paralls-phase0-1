extends RefCounted

class_name CharacterTagContract

const ALLOWED_NAMESPACES := [
	"goal", "intent", "evidence", "capability", "affordance", "constraint",
	"state", "status", "action", "phase", "occupy", "event", "authority",
	"presentation", "expression",
]


static func normalize_ingress_tags(
	tags: Array[StringName],
	authority_committed: bool = false,
	authority_route: StringName = &""
) -> Dictionary:
	var accepted: Array[StringName] = []
	var rejected: Array[StringName] = []
	for tag in tags:
		var value := str(tag)
		var parts := value.split(":", false, 1)
		if parts.size() != 2 or parts[0] not in ALLOWED_NAMESPACES or str(parts[1]).is_empty():
			rejected.append(tag)
			continue
		if parts[0] == "authority" and (not authority_committed or str(authority_route) not in ["esm", "gameplay", "composite"]):
			rejected.append(tag)
			continue
		accepted.append(StringName(value))
	return {"accepted": accepted, "rejected": rejected}


static func read_legacy_demo_tags(raw: Dictionary) -> Array[StringName]:
	var tags: Array[StringName] = []
	for key in ["active_goal_tags", "evidence_tags", "status_tags", "primitive_action_tags"]:
		for value in raw.get(key, []):
			if str(value).contains(":"):
				tags.append(StringName(value))
	return tags
