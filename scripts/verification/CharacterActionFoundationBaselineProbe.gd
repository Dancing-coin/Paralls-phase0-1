extends RefCounted
class_name CharacterActionFoundationBaselineProbe

const REQUIRED_FIELDS := [
	"actor_id",
	"source_kind",
	"state",
	"clip",
	"velocity_world",
	"position",
	"action_locked",
	"root_policy",
	"caller_path",
]

static func capture_actor(actor: Node, source_kind: StringName, caller_path: String) -> Dictionary:
	var skin := actor.get_node_or_null("VisualRoot/AssetMount/RotationOffset/ScaleOffset/ImportedModel/RoleAssetRoot/StreetCharacterSkin")
	var controller: Node = skin.get("animation_controller") if skin != null else null
	var state := str(controller.get("current_state")) if controller != null else "unknown"
	var clip := str(skin.call("get_current_clip_name")) if skin != null and skin.has_method("get_current_clip_name") else ""
	var locked := bool(controller.call("is_locked")) if controller != null and controller.has_method("is_locked") else false
	var root_policy := "hold"
	if skin != null and skin.has_meta("root_motion_policy"):
		root_policy = str(skin.get_meta("root_motion_policy"))
	return {
		"actor_id": str(actor.get("actor_id")),
		"source_kind": str(source_kind),
		"state": state,
		"clip": clip,
		"velocity_world": _vector_payload(actor.get("velocity")),
		"position": _vector_payload(actor.get("global_position")),
		"action_locked": locked,
		"root_policy": root_policy,
		"caller_path": caller_path,
	}

static func capture_scene(root: Node) -> Array[Dictionary]:
	var snapshots: Array[Dictionary] = []
	for actor_name in ["PlayerCharacter", "AgentCharacterJK", "AgentCharacterT"]:
		var actor := root.get_node_or_null(actor_name)
		if actor == null:
			continue
		var source_kind: StringName = &"player" if actor_name == "PlayerCharacter" else &"agent"
		snapshots.append(capture_actor(actor, source_kind, "scenes/phase0/StreetCombatDemo.tscn:%s" % actor_name))
	return snapshots

static func emit_scene(root: Node) -> void:
	for snapshot in capture_scene(root):
		print("character_action_foundation_baseline:%s" % JSON.stringify(snapshot))

static func _vector_payload(value: Variant) -> Array[float]:
	if value is Vector3:
		return [float(value.x), float(value.y), float(value.z)]
	return [0.0, 0.0, 0.0]
