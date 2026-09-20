extends SceneTree

# 外机执行：不依赖模型资产，检查真实 Motor 输出；本地静态检查不代表此 probe 已通过。
const Motor = preload("res://scripts/character/CharacterMotor.gd")
var failures: Array[String] = []
var checks := 0

func _initialize() -> void:
	_run.call_deferred()

func _check(condition: bool, label: String) -> void:
	checks += 1
	if not condition:
		failures.append(label)

func _run() -> void:
	var body := CharacterBody3D.new()
	var collider := CollisionShape3D.new()
	var shape := SphereShape3D.new()
	shape.radius = 0.2
	collider.shape = shape
	body.add_child(collider)
	root.add_child(body)
	var motor := Motor.new()
	body.add_child(motor)
	for yaw in [0.0, PI / 2.0, PI]:
		for move in [Vector2(0, 1), Vector2(0, -1), Vector2(1, 0), Vector2(-1, 0)]:
			body.position = Vector3.ZERO
			body.rotation.y = yaw
			body.velocity = Vector3.ZERO
			await physics_frame
			var result: Dictionary = motor.apply_intent_frame(body, {"actor_id": "probe", "move_local": move, "desired_facing_yaw": yaw, "action": "locomotion"}, 1.0 / 60.0)
			var local: Vector2 = result["move_local_actual"]
			var expected: Vector3 = body.global_basis.x * move.x - body.global_basis.z * move.y
			_check(local.normalized().dot(move) > 0.99, "local_direction:%s:%s" % [yaw, move])
			_check(body.velocity.dot(expected) > 0.0, "world_direction:%s:%s" % [yaw, move])
	for vertical_speed in [0.0, -3.0]:
		body.velocity = Vector3(0, vertical_speed, 0)
		await physics_frame
		var result: Dictionary = motor.apply_physics_command(body, {"desired_velocity": Vector3.ZERO, "facing_yaw": body.rotation.y}, 1.0 / 60.0)
		_check((result["move_local_actual"] as Vector2).is_zero_approx(), "stationary_or_falling:%s" % vertical_speed)
	# 墙面阻挡时仍有前进请求，但实际本地运动必须归零。
	var wall := StaticBody3D.new()
	var wall_collider := CollisionShape3D.new()
	var wall_shape := BoxShape3D.new()
	wall_shape.size = Vector3(10, 10, 0.2)
	wall_collider.shape = wall_shape
	wall.add_child(wall_collider)
	wall.position = Vector3(0, 0, -0.4)
	root.add_child(wall)
	body.position = Vector3.ZERO
	body.rotation = Vector3.ZERO
	body.velocity = Vector3.ZERO
	var hit_wall := false
	for tick in range(60):
		await physics_frame
		var result: Dictionary = motor.apply_intent_frame(body, {"actor_id": "probe", "move_local": Vector2(0, 1), "desired_facing_yaw": 0.0}, 1.0 / 60.0)
		if body.get_slide_collision_count() > 0:
			hit_wall = true
			_check((result["move_local_actual"] as Vector2).length() < 0.01, "blocked_actual_velocity")
			break
	_check(hit_wall, "wall_contact_observed")
	print("character_motor_coordinates_probe:" + JSON.stringify({"passed": failures.is_empty(), "checks": checks, "failures": failures}))
	quit(0 if failures.is_empty() else 1)
