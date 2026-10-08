extends SceneTree

const AdapterRef = preload("res://scripts/character/CharacterPackagePresentationAdapter.gd")

class AlignmentFixture:
	extends "res://scripts/character/CharacterPackagePresentationAdapter.gd"
	func _ready() -> void:
		pass

var failures: Array[String] = []

func _initialize() -> void:
	call_deferred("_run")

func _check(condition: bool, label: String) -> void:
	if not condition:
		failures.append(label)
		push_error(label)

func _run() -> void:
	var adapter = AdapterRef.new()
	if not adapter.has_method("apply_visual_alignment"):
		_check(false, "package adapter must apply declared visual alignment")
	else:
		for entry: Array in [["-z", Vector3.FORWARD], ["+z", Vector3.BACK], ["+x", Vector3.RIGHT], ["-x", Vector3.LEFT]]:
			var result: Dictionary = adapter.apply_visual_alignment({"forward_axis": entry[0], "up_axis": "+y"})
			_check(bool(result.get("accepted", false)), "valid source axis: " + str(entry[0]))
			_check((adapter.basis * entry[1]).is_equal_approx(Vector3.FORWARD), "source forward becomes actor -Z: " + str(entry[0]))
		var calibration := {"forward_axis": "-z", "presentation_alignment": {"visual_yaw_degrees": 180.0}}
		adapter.rotation.y = PI
		adapter.apply_visual_alignment(calibration)
		adapter.apply_visual_alignment(calibration)
		_check((adapter.basis * Vector3.BACK).is_equal_approx(Vector3.FORWARD), "legacy scene yaw and repeated application do not double rotate")
		var prior: Basis = adapter.basis
		for invalid: Dictionary in [{"forward_axis": "unknown"}, {"up_axis": "+z"}, {"presentation_alignment": "bad"}, {"presentation_alignment": {"visual_yaw_degrees": "180"}}, {"presentation_alignment": {"visual_yaw_degrees": NAN}}]:
			_check(not bool(adapter.apply_visual_alignment(invalid).get("accepted", false)), "malformed alignment rejected")
			_check(adapter.basis.is_equal_approx(prior), "rejection does not change transform")
	adapter.free()
	# Independently specified geometry checks that actor yaw is not applied twice.
	var body := CharacterBody3D.new()
	body.rotation.y = PI / 2.0
	root.add_child(body)
	var calibrated := AlignmentFixture.new()
	body.add_child(calibrated)
	calibrated.apply_visual_alignment({"presentation_alignment": {"visual_yaw_degrees": 180.0}})
	var skeleton := Skeleton3D.new()
	skeleton.scale = Vector3(2, 2, 2)
	calibrated.add_child(skeleton)
	calibrated._skeleton = skeleton
	var local_delta: Vector3 = calibrated.root_motion_to_actor_local(Vector3(0, 0, 0.2))
	_check(local_delta.is_equal_approx(Vector3(0, 0, -0.4)), "model +Z becomes actor -Z with imported scale")
	_check((body.global_basis * local_delta).is_equal_approx(Vector3(-0.4, 0, 0)), "actor yaw maps corrected root displacement once")
	body.queue_free()
	await process_frame
	var packed := load("res://scenes/phase0/StreetCombatActorControlDemo.tscn") as PackedScene
	var scene := packed.instantiate()
	root.add_child(scene)
	await process_frame
	for actor_name: String in ["PlayerCharacter", "AgentCharacterJK", "AgentCharacterT", "KnightCharacter"]:
		var actor := scene.get_node(actor_name) as CharacterBody3D
		var presenter: Node3D = actor.get("role_asset_scene")
		_check((presenter.basis * Vector3.BACK).normalized().is_equal_approx(Vector3.FORWARD), "package alignment applied: " + actor_name)
		if presenter.has_method("root_motion_to_actor_local"):
			var model: Node3D = presenter._skeleton
			var original_rotation := actor.rotation
			actor.rotation.y = 0.73
			var converted: Vector3 = presenter.root_motion_to_actor_local(Vector3(0, 0, 0.2))
			var expected: Vector3 = actor.global_basis.inverse() * model.global_basis * Vector3(0, 0, 0.2)
			_check(converted.is_equal_approx(expected), "root delta shares model orientation and scale: " + actor_name)
			actor.rotation = original_rotation
		else:
			_check(false, "root delta must be converted into actor coordinates")
	scene.queue_free()
	await process_frame
	print("character_visual_alignment failures=", failures)
	quit(0 if failures.is_empty() else 1)
