extends SceneTree

const DEMO_SCENE := "res://scenes/phase0/StreetCombatActorDemo.tscn"
const EXPECTED_LIBRARY_ID := "motionlib:humanoid.v1.core@1"
const SKIN_PATHS := [
	"PlayerCharacter/VisualRoot/AssetMount/RotationOffset/ScaleOffset/ImportedModel/RoleAssetRoot/StreetCharacterSkin",
	"AgentCharacterJK/VisualRoot/AssetMount/RotationOffset/ScaleOffset/ImportedModel/RoleAssetRoot/StreetCharacterSkin",
	"AgentCharacterT/VisualRoot/AssetMount/RotationOffset/ScaleOffset/ImportedModel/RoleAssetRoot/StreetCharacterSkin",
]
const EXPECTED_STATES := ["idle", "walk", "run", "jump", "boxing", "sword_attack"]

var _failures: Array[String] = []

func _initialize() -> void:
	call_deferred("_run")

func _run() -> void:
	var scene: Node = load(DEMO_SCENE).instantiate()
	get_root().add_child(scene)
	await process_frame
	await process_frame
	_test_three_street_skins_mount_same_library(scene)
	_test_six_states_and_lock_compatibility(scene)
	scene.queue_free()
	if _failures.is_empty():
		print("PASS test_shared_animation_library_runtime")
		quit(0)
		return
	print("FAILURES count=%d values=%s" % [_failures.size(), str(_failures)])
	quit(1)

func _test_three_street_skins_mount_same_library(scene: Node) -> void:
	var library_ids: Array[String] = []
	for path in SKIN_PATHS:
		var skin := scene.get_node_or_null(path)
		_assert_true(skin != null, "street skin exists: %s" % path)
		if skin == null:
			continue
		_assert_true(skin.has_method("uses_shared_motion_library"), "skin exposes shared library query")
		_assert_true(skin.has_method("get_mounted_motion_library_id"), "skin exposes mounted library id")
		if not skin.has_method("uses_shared_motion_library"):
			continue
		_assert_true(bool(skin.uses_shared_motion_library()), "skin uses shared motion library: %s" % path)
		var library_id := str(skin.get_mounted_motion_library_id())
		library_ids.append(library_id)
		_assert_eq(library_id, EXPECTED_LIBRARY_ID, "mounted library id: %s" % path)
	_assert_eq(library_ids.size(), 3, "three street skins mounted")
	_assert_true(library_ids.size() == 3 and library_ids[0] == library_ids[1] and library_ids[1] == library_ids[2], "all skins share one library id")

func _test_six_states_and_lock_compatibility(scene: Node) -> void:
	for path in SKIN_PATHS:
		var skin := scene.get_node_or_null(path)
		if skin == null:
			continue
		for state_name in EXPECTED_STATES:
			_assert_true(bool(skin.has_clip(state_name)), "%s resolves state %s" % [path, state_name])
		_assert_true(bool(skin.is_animation_tree_active()), "%s animation tree active" % path)
		var animation_player := skin.find_child("AnimationPlayer", true, false) as AnimationPlayer
		_assert_true(animation_player != null, "%s animation player exists" % path)
		if animation_player != null:
			_assert_true(animation_player.has_animation_library(&"central"), "%s central namespace mounted" % path)
			_assert_true(animation_player.get_animation_library_list().size() >= 2, "%s local GLB library retained as fallback" % path)
		_assert_true(bool(skin.play_locomotion_state("walk")), "%s walk state accepted" % path)
		_assert_true(str(skin.get_current_clip_name()).begins_with("central/"), "%s walk resolves from central namespace" % path)
		_assert_true(bool(skin.play_locomotion_state("run")), "%s run state accepted" % path)
		_assert_true(str(skin.get_current_clip_name()).begins_with("central/"), "%s run resolves from central namespace" % path)
		_assert_true(bool(skin.play_action_state("boxing")), "%s boxing action accepted" % path)
		_assert_true(str(skin.get_current_clip_name()).begins_with("central/"), "%s boxing resolves from central namespace" % path)
		_assert_true(bool(skin.animation_controller.is_locked()), "%s boxing action locks" % path)
		skin.animation_controller.cancel_action()
		_assert_true(not bool(skin.animation_controller.is_locked()), "%s boxing cancel unlocks" % path)
		_assert_true(bool(skin.play_action_state("sword_attack")), "%s sword action accepted" % path)
		_assert_true(str(skin.get_current_clip_name()).begins_with("central/"), "%s sword resolves from central namespace (%s)" % [path, str(skin.get_current_clip_name())])
		_assert_true(bool(skin.animation_controller.is_locked()), "%s sword action locks" % path)
		skin.restore_reviewed_action_playback()
		_assert_true(not bool(skin.animation_controller.is_locked()), "%s restore unlocks" % path)

func _assert_true(value: bool, label: String) -> void:
	if not value:
		_failures.append(label)

func _assert_eq(actual: Variant, expected: Variant, label: String) -> void:
	if actual != expected:
		_failures.append("%s: %s != %s" % [label, str(actual), str(expected)])
