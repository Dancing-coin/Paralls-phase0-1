extends SceneTree

const CharacterAssetQualificationRef = preload("res://scripts/character/CharacterAssetQualification.gd")

const BONE_NAMES := [
	"Root", "Hips", "Spine", "Chest", "Head",
	"LeftUpperArm", "LeftLowerArm", "LeftHand",
	"RightUpperArm", "RightLowerArm", "RightHand",
	"LeftUpperLeg", "LeftLowerLeg", "LeftFoot",
	"RightUpperLeg", "RightLowerLeg", "RightFoot",
]

const CANONICAL_BONES := [
	"root", "pelvis", "spine", "chest", "head",
	"left_upper_arm", "left_lower_arm", "left_hand",
	"right_upper_arm", "right_lower_arm", "right_hand",
	"left_upper_leg", "left_lower_leg", "left_foot",
	"right_upper_leg", "right_lower_leg", "right_foot",
]


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	var qualification := CharacterAssetQualificationRef.new()
	var valid := qualification.qualify(_manifest())
	var invalid_rest := qualification.qualify(_manifest({"invalid_rest_pose": true}))
	var missing_root := qualification.qualify(_manifest({"remove_mapping": "root"}))
	var missing_tag_manifest := _manifest().duplicate(true)
	var missing_tag_map: Dictionary = missing_tag_manifest["locomotion_map"]
	missing_tag_map.erase("turn_right")
	missing_tag_manifest["locomotion_map"] = missing_tag_map
	var missing_tag := qualification.qualify(missing_tag_manifest)
	var missing_clip := qualification.qualify(_manifest({"missing_clip": true}))
	var full_body := qualification.qualify(_manifest({"full_body_as_upper_body": true}))
	var bad_slot := qualification.qualify(_manifest({"bad_slot": true}))
	var optional_missing := qualification.qualify(_manifest({"optional_missing": true}))
	var fallback := qualification.qualify(_manifest({"full_body_as_upper_body": true, "fallback": true}))
	var rejected := qualification.qualify(_manifest({"full_body_as_upper_body": true, "fallback": false}))
	print(JSON.stringify({
		"valid_humanoid": valid.get("status"),
		"invalid_rest_pose": invalid_rest.get("status"),
		"missing_root_bone": missing_root.get("status"),
		"unmapped_required_locomotion_tag": missing_tag.get("status"),
		"missing_required_clip": missing_clip.get("status"),
		"full_body_as_upper_body": full_body.get("status"),
		"required_slot_incompatible": bad_slot.get("status"),
		"missing_optional_finger_facial": optional_missing.get("status"),
		"explicit_fallback": fallback.get("status"),
		"rejected_without_fallback": rejected.get("status"),
		"valid_wave_audit": valid.get("clip_audits", {}).get("wave", {}),
		"full_body_wave_audit": full_body.get("clip_audits", {}).get("wave", {}),
		"optional_bones": optional_missing.get("optional"),
		"missing_root_reasons": missing_root.get("reasons"),
		"full_body_reasons": full_body.get("reasons"),
		"slot_reasons": bad_slot.get("reasons"),
	}))
	quit(0 if valid.get("status") == "qualified" else 1)


func _manifest(options: Dictionary = {}) -> Dictionary:
	var skeleton := _skeleton(bool(options.get("invalid_rest_pose", false)))
	var mapping: Dictionary = {}
	for index in BONE_NAMES.size():
		mapping[CANONICAL_BONES[index]] = BONE_NAMES[index]
	if options.has("remove_mapping"):
		mapping.erase(str(options["remove_mapping"]))
	var locomotion := {
		"idle": "idle",
		"walk_forward": "walk_forward",
		"run_forward": "run_forward",
		"jump_start": "jump_start",
		"jump_loop": "jump_loop",
		"jump_land": "jump_land",
		"turn_left": "turn_left",
		"turn_right": "turn_right",
	}
	if options.has("remove_locomotion_tag"):
		var filtered_locomotion := {}
		for tag in locomotion:
			if tag != str(options["remove_locomotion_tag"]):
				filtered_locomotion[tag] = locomotion[tag]
		locomotion = filtered_locomotion
	if bool(options.get("missing_clip", false)):
		locomotion["idle"] = "missing_idle"
	var clips := {}
	for clip_name in locomotion.values():
		if str(clip_name) != "missing_idle":
			clips[str(clip_name)] = _clip(str(clip_name), "", Vector3.ZERO)
	clips["wave"] = _clip("wave", "LeftHand", Vector3(0.05, 0.0, 0.0))
	if bool(options.get("full_body_as_upper_body", false)):
		clips["wave"] = _clip("wave", "LeftUpperLeg", Vector3(0.2, 0.0, 0.0))
	var slot_bone := "right_hand"
	if bool(options.get("bad_slot", false)):
		slot_bone = "head"
	var action := {
		"semantic_action_id": "action:wave",
		"clip_ref": "wave",
		"mode": "native_upper_body",
		"locomotion_compatibility": "coexist",
		"required_slots": ["weapon_hand"],
		"root_motion_policy": "hold",
		"root_motion_required": false,
		"markers": [{"marker_id": "hand_reach", "time_seconds": 0.35, "marker_kind": "hand_reach_candidate", "emits_attempt": false, "evidence_requirement": "none"}],
		"cancel_windows": [{"start_seconds": 0.1, "end_seconds": 0.8}],
		"resource_claims": ["upper_body"],
		"physics_claims": [],
		"authority_route_ref": "gameplay",
		"fallback_policy": "reject",
	}
	if bool(options.get("fallback", false)):
		action["fallback"] = {"mode": "full_body_exclusive", "locomotion_compatibility": "replace_locomotion"}
	return {
		"package_id": "fixture_humanoid",
		"source_frame_rate": 30.0,
		"unit_scale": 1.0,
		"forward_axis": "-z",
		"up_axis": "+y",
		"canonical_mapping": {"profile_id": "humanoid.v1", "bones": mapping},
		"required_slots": ["weapon_hand"],
		"slots": {"weapon_hand": {"canonical_bone": slot_bone, "anchor_ref": "Rig:RightHand"}},
		"locomotion_map": locomotion,
		"clips": clips,
		"actions": [action],
		"_skeleton": skeleton,
		"optional_bones": {"left_finger_1": "LeftFinger1", "facial_jaw": "Jaw"},
	}


func _skeleton(invalid_rest_pose: bool) -> Skeleton3D:
	var skeleton := Skeleton3D.new()
	skeleton.name = "Rig"
	for index in BONE_NAMES.size():
		skeleton.add_bone(BONE_NAMES[index])
		skeleton.set_bone_rest(index, Transform3D.IDENTITY)
		if index > 0:
			skeleton.set_bone_parent(index, 0)
	if invalid_rest_pose:
		skeleton.set_bone_rest(0, Transform3D(Basis(Vector3.ZERO, Vector3.ZERO, Vector3.ZERO), Vector3.ZERO))
	return skeleton


func _clip(_name: String, bone_name: String, movement: Vector3) -> Animation:
	var clip := Animation.new()
	clip.length = 1.0
	clip.step = 1.0 / 30.0
	if not bone_name.is_empty():
		var track := clip.add_track(Animation.TYPE_POSITION_3D)
		clip.track_set_path(track, NodePath("Rig:%s" % bone_name))
		clip.track_insert_key(track, 0.0, Vector3.ZERO)
		clip.track_insert_key(track, 0.5, movement)
	return clip
