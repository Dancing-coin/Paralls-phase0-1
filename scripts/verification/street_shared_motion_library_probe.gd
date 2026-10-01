extends SceneTree

const DEMO_SCENE := "res://scenes/phase0/StreetCombatActorDemo.tscn"
const EXPECTED_LIBRARY_ID := "motionlib:humanoid.v1.core@1"
const EXPECTED_STATES := ["idle", "walk", "run", "jump", "boxing", "sword_attack"]
const SKIN_PATHS := [
	"PlayerCharacter/VisualRoot/AssetMount/RotationOffset/ScaleOffset/ImportedModel/RoleAssetRoot/StreetCharacterSkin",
	"AgentCharacterJK/VisualRoot/AssetMount/RotationOffset/ScaleOffset/ImportedModel/RoleAssetRoot/StreetCharacterSkin",
	"AgentCharacterT/VisualRoot/AssetMount/RotationOffset/ScaleOffset/ImportedModel/RoleAssetRoot/StreetCharacterSkin",
]

func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	var scene: Node = load(DEMO_SCENE).instantiate()
	get_root().add_child(scene)
	await process_frame
	await process_frame
	var skins: Array[Node] = []
	for path in SKIN_PATHS:
		var skin := scene.get_node_or_null(path)
		if skin != null:
			skins.append(skin)
	var shared_library_identity := _shared_library_identity(skins)
	var six_states := _six_states(skins)
	var animation_tree_active := _animation_tree_active(skins)
	var motor_motion_owner := _motor_motion_owner()
	var root_motion_single_consume := _root_motion_single_consume(skins)
	var fallback_reason := _fallback_reason(skins)
	print("shared_library_identity=%s" % str(shared_library_identity).to_lower())
	print("six_states=%s" % str(six_states).to_lower())
	print("animation_tree_active=%s" % str(animation_tree_active).to_lower())
	print("motor_motion_owner=%s" % str(motor_motion_owner).to_lower())
	print("root_motion_single_consume=%s" % str(root_motion_single_consume).to_lower())
	print("fallback_reason=%s" % fallback_reason)
	print("fallback_applied=%s" % str(not fallback_reason.is_empty()).to_lower())
	scene.queue_free()
	quit(0 if shared_library_identity and six_states and animation_tree_active and motor_motion_owner and root_motion_single_consume else 1)


func _shared_library_identity(skins: Array[Node]) -> bool:
	if skins.size() != SKIN_PATHS.size():
		return false
	var observed := ""
	for skin in skins:
		if not skin.has_method("uses_shared_motion_library") or not bool(skin.uses_shared_motion_library()):
			return false
		var library_id := str(skin.get_mounted_motion_library_id()) if skin.has_method("get_mounted_motion_library_id") else ""
		if library_id != EXPECTED_LIBRARY_ID:
			return false
		if observed.is_empty():
			observed = library_id
		elif observed != library_id:
			return false
	return true


func _six_states(skins: Array[Node]) -> bool:
	for skin in skins:
		if not skin.has_method("get_source_animation_states"):
			return false
		var states := Array(skin.get_source_animation_states())
		for expected in EXPECTED_STATES:
			if not states.has(expected):
				return false
		if states.size() != EXPECTED_STATES.size():
			return false
	return skins.size() == SKIN_PATHS.size()


func _animation_tree_active(skins: Array[Node]) -> bool:
	for skin in skins:
		if not skin.has_method("is_animation_tree_active") or not bool(skin.is_animation_tree_active()):
			return false
	return skins.size() == SKIN_PATHS.size()


func _motor_motion_owner() -> bool:
	var actor_source := FileAccess.get_file_as_string("res://scripts/character/CharacterActor.gd")
	var skin_source := FileAccess.get_file_as_string("res://scripts/street_combat/StreetCharacterSkin.gd")
	return not actor_source.contains("move_and_" + "slide(") and not skin_source.contains("velocity")


func _root_motion_single_consume(skins: Array[Node]) -> bool:
	if skins.is_empty():
		return false
	var skin := skins[0]
	if not skin.has_method("reset_root_motion") or not skin.has_method("consume_root_motion_delta") or not skin.has_method("get_root_motion_consume_count"):
		return false
	skin.reset_root_motion()
	skin.consume_root_motion_delta()
	skin.consume_root_motion_delta()
	return int(skin.get_root_motion_consume_count()) == 1


func _fallback_reason(skins: Array[Node]) -> String:
	for skin in skins:
		if skin.has_method("get_fallback_reason"):
			var reason := str(skin.get_fallback_reason())
			if not reason.is_empty():
				return reason
	return ""

