extends SceneTree

const SOURCE_SCENE := "res://addons/JehenoThirdPersonController/PlayerCharacter/GodotPlush/godot_plush_skin.tscn"
const OUTPUT_BONEMAP := "res://addons/mixabridge/generated/bonemap_godot_plush.tres"
const PROFILE_BONES := [
	"Hips",
	"LeftUpperArm",
	"LeftLowerArm",
	"RightUpperArm",
	"RightLowerArm",
	"LeftUpperLeg",
	"LeftLowerLeg",
	"LeftFoot",
	"RightUpperLeg",
	"RightLowerLeg",
	"RightFoot",
]

func _initialize() -> void:
	var mapper = preload("res://addons/mixabridge/bone_mapper.gd").new()
	var bone_map: BoneMap = mapper.create_bone_map_for_scene(SOURCE_SCENE)
	if bone_map == null:
		push_error("mixabridge_inspect_plush_bonemap: failed to create BoneMap")
		quit(1)
		return

	var save_err := mapper.save_bone_map(bone_map, OUTPUT_BONEMAP)
	if save_err != OK:
		push_error("mixabridge_inspect_plush_bonemap: failed to save BoneMap: %s" % save_err)
		quit(2)
		return

	print("BONE_MAP_SAVED:%s" % OUTPUT_BONEMAP)
	print("BONE_COUNT:%s" % mapper.skeleton_bone_count)
	print("MAPPED_COUNT:%s" % mapper.mapped_bones.size())
	print("UNMAPPED_COUNT:%s" % mapper.unmapped_bones.size())

	for profile_bone in PROFILE_BONES:
		var assigned := bone_map.get_skeleton_bone_name(profile_bone)
		print("PROFILE_ASSIGNMENT:%s=%s" % [profile_bone, assigned])

	var reloaded := load(OUTPUT_BONEMAP) as BoneMap
	if reloaded == null:
		push_error("mixabridge_inspect_plush_bonemap: failed to reload saved BoneMap")
		quit(3)
		return

	for profile_bone in PROFILE_BONES:
		var assigned := reloaded.get_skeleton_bone_name(profile_bone)
		print("RELOADED_ASSIGNMENT:%s=%s" % [profile_bone, assigned])

	quit(0)
