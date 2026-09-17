extends SceneTree

const HumanControllerAdapterRef = preload("res://scripts/character/HumanControllerAdapter.gd")
const AgentControllerAdapterRef = preload("res://scripts/character/AgentControllerAdapter.gd")
const CharacterControllerPortRef = preload("res://scripts/character/CharacterControllerPort.gd")
const ActorActionArbiterRef = preload("res://scripts/character/ActorActionArbiter.gd")
const MotionContributionComposerRef = preload("res://scripts/character/MotionContributionComposer.gd")
const PhysicsContactEvidenceRef = preload("res://scripts/character/PhysicsContactEvidence.gd")
const EmbodiedActionControllerRef = preload("res://scripts/interaction/EmbodiedActionController.gd")
const CharacterReplicaSceneRef = preload("res://scenes/phase0/CharacterReplica.tscn")
const CharacterMotorRef = preload("res://scripts/character/CharacterMotor.gd")
const CharacterActionAssetDescriptorRef = preload("res://scripts/character/CharacterActionAssetDescriptor.gd")

func _initialize() -> void:
	call_deferred("_run")

func _run() -> void:
	var shared_command := _check_shared_command()
	var policy_contract := _check_policy_contract()
	var evidence_contract := await _check_evidence_contract()
	var recovery_contract := _check_recovery_contract()
	var stale_correction_contract := _check_stale_correction_contract()
	var surface_constraints := await _check_surface_constraints()
	var replica_runtime := await _check_replica_runtime()
	print(JSON.stringify({
		"shared_command": shared_command,
		"policy_contract": policy_contract,
		"evidence_contract": evidence_contract,
		"recovery_contract": recovery_contract,
		"stale_correction_contract": stale_correction_contract,
		"surface_constraints": surface_constraints,
		"replica_runtime": replica_runtime,
	}))
	quit(0 if shared_command and policy_contract and evidence_contract and recovery_contract and stale_correction_contract and surface_constraints and replica_runtime else 1)

func _check_shared_command() -> bool:
	var candidate := {
		"move_local": Vector2(0.5, -0.75),
		"desired_facing_yaw": 0.4,
		"gait": "run",
		"action": "locomotion",
	}
	var human := HumanControllerAdapterRef.build_intent_frame("player", candidate)
	var agent := AgentControllerAdapterRef.build_intent_frame("npc", candidate)
	var human_lease := {
		"request_id": "lease:shared",
		"lease_id": "lease:shared",
		"kind": "lease",
		"source_id": "human",
		"expires_at_tick": 10,
		"move_local": CharacterControllerPortRef.get_move_local(human),
		"desired_facing_yaw": CharacterControllerPortRef.get_desired_facing_yaw(human),
		"claims": [&"world_motion", &"facing"],
	}
	var agent_lease := human_lease.duplicate(true)
	agent_lease["source_id"] = "agent"
	agent_lease["move_local"] = CharacterControllerPortRef.get_move_local(agent)
	agent_lease["desired_facing_yaw"] = CharacterControllerPortRef.get_desired_facing_yaw(agent)
	var human_frame := ActorActionArbiterRef.resolve(1, [human_lease], [], {"occupancy": {}})
	var agent_frame := ActorActionArbiterRef.resolve(1, [agent_lease], [], {"occupancy": {}})
	var profile := {"speed": 6.0, "actor_ref": "shared"}
	var human_command := MotionContributionComposerRef.compose(human_frame, profile, 1.0 / 60.0)
	var agent_command := MotionContributionComposerRef.compose(agent_frame, profile, 1.0 / 60.0)
	return human_command.get("desired_velocity") == agent_command.get("desired_velocity") and human_command.get("facing_yaw") == agent_command.get("facing_yaw")

func _check_policy_contract() -> bool:
	var pending := MotionContributionComposerRef.apply_root_motion_policy({"root_delta": Vector3(0.8, 0.0, 0.0), "root_motion_policy": "hold"}, &"pending")
	var missing := MotionContributionComposerRef.apply_root_motion_policy({"root_delta": Vector3.ONE, "root_motion_policy": "bounded_continue"}, &"pending")
	var valid := MotionContributionComposerRef.apply_root_motion_policy({"root_delta": Vector3(0.8, 0.0, 0.0), "root_motion_policy": "reversible_continue", "root_motion_envelope": {"max_distance": 1.0, "max_duration_ticks": 2}}, &"pending")
	var unknown := MotionContributionComposerRef.apply_root_motion_policy({"root_delta": Vector3(0.8, 0.0, 0.0), "root_motion_policy": "bounded_continue", "root_motion_envelope": {"max_distance": 1.0, "max_duration_ticks": 2}}, &"unknown")
	var descriptor_rejected := CharacterActionAssetDescriptorRef.validate_root_motion_descriptor({"root_motion_policy": "bounded_continue"})
	return pending.get("root_delta", Vector3.ONE) == Vector3.ZERO and not bool(missing.get("accepted", true)) and bool(valid.get("accepted", false)) and unknown.get("root_delta", Vector3.ONE) == Vector3.ZERO and bool(unknown.get("unsafe_frozen", false)) and not bool(descriptor_rejected.get("accepted", true))

func _check_evidence_contract() -> bool:
	var body := CharacterBody3D.new()
	var shape := CollisionShape3D.new()
	var capsule := CapsuleShape3D.new()
	capsule.height = 1.0
	capsule.radius = 0.25
	shape.shape = capsule
	body.add_child(shape)
	root.add_child(body)
	var no_collision := PhysicsContactEvidenceRef.create({"physics_tick": 4, "source_digest": "cmd"}, body, {"action_instance_id": "a", "marker_id": "m"}, null)
	var no_observation := body.get_slide_collision_count() == 0
	var motor: CharacterMotor = CharacterMotorRef.new()
	root.add_child(motor)
	var wall := StaticBody3D.new()
	var wall_shape := CollisionShape3D.new()
	var wall_box := BoxShape3D.new()
	wall_box.size = Vector3(0.2, 2.0, 2.0)
	wall_shape.shape = wall_box
	wall.add_child(wall_shape)
	wall.position = Vector3(0.45, 0.5, 0.0)
	root.add_child(wall)
	body.position = Vector3(0.0, 0.5, 0.0)
	body.collision_layer = 1
	body.collision_mask = 1
	wall.collision_layer = 1
	wall.collision_mask = 1
	await physics_frame
	for tick in range(5, 15):
		motor.apply_physics_command(body, {"actor_ref": "actor:evidence", "physics_tick": tick, "desired_velocity": Vector3.RIGHT * 10.0, "facing_yaw": 0.0, "root_delta": Vector3.ZERO, "impulse": Vector3.ZERO, "runtime_correction": Vector3.ZERO, "source_digest": "cmd:%s" % tick}, 0.1)
	var records := motor.collect_contact_evidence(body, {"actor_ref": "actor:evidence", "physics_tick": 14, "source_digest": "cmd:14"}, [{"action_instance_id": "a", "marker_id": "marker:contact", "marker_physics_tick": 14, "marker_observed": true}])
	var observed: bool = not records.is_empty() and bool(records[0].get("local_only", false)) and bool(records[0].get("marker_observed", false)) and not bool(records[0].get("contact_confirmation", true)) and records[0].has("command_digest") and records[0].has("collider_refs") and records[0].has("hit_sensor_refs") and str(records[0].get("contact_marker_id", "")) == "marker:contact"
	var joined := PhysicsContactEvidenceRef.join_same_tick(records, [{"action_instance_id": "a", "marker_id": "marker:contact", "physics_tick": 14}], 14)
	var same_tick_join: bool = joined.size() == 1 and str(joined[0].get("attempt_id", "")) == "a" and str(joined[0].get("evidence_id", "")) != "" and str(joined[0].get("evidence_status", "")) == "supported" and not bool(joined[0].get("contact_confirmation", true))
	var evidence_only := motor.collect_contact_evidence(body, {"actor_ref": "actor:evidence", "physics_tick": 14, "source_digest": "cmd:14"}, [{"action_instance_id": "a", "marker_id": "marker:unobserved"}])
	var marker_is_not_confirmation: bool = not evidence_only.is_empty() and str(evidence_only[0].get("marker_id", "")) == "" and not bool(evidence_only[0].get("contact_confirmation", true))
	var airborne := CharacterBody3D.new()
	root.add_child(airborne)
	var support_result: Dictionary = motor.apply_physics_command(airborne, {"actor_ref": "actor:support", "physics_tick": 15, "desired_velocity": Vector3.ZERO, "facing_yaw": 0.0, "support_requirements": ["floor"], "root_delta": Vector3.ZERO, "impulse": Vector3.ZERO, "runtime_correction": Vector3.ZERO, "source_digest": "cmd:15"}, 0.1)
	var support_loss: bool = bool(support_result.get("support_loss", false))
	airborne.queue_free()
	motor.queue_free()
	wall.queue_free()
	body.queue_free()
	return no_observation and no_collision.is_empty() and observed and same_tick_join and marker_is_not_confirmation and support_loss

func _check_recovery_contract() -> bool:
	var controller := EmbodiedActionControllerRef.new()
	root.add_child(controller)
	controller.selected_action_atoms = [{"action_tag": "action:test"}]
	controller.phase_action_atoms = {"contact": [{"action_tag": "action:test"}]}
	controller.apply_authority_recovery({"recovery_directive": "rejected", "damage": 10, "status_write": "stunned"})
	var released := controller.local_ownership_restored and controller.selected_action_atoms.is_empty() and controller.phase_action_atoms.is_empty()
	controller.apply_authority_recovery({"recovery_directive": "unknown"})
	var frozen := controller.unsafe_root_motion_frozen
	controller.queue_free()
	return released and frozen

func _check_stale_correction_contract() -> bool:
	var correction := MotionContributionComposerRef.filter_runtime_correction({"runtime_correction": Vector3.ONE, "projection_revision": 2}, 3)
	return correction.get("runtime_correction", Vector3.ONE) == Vector3.ZERO and bool(correction.get("resync_required", false))


func _check_surface_constraints() -> bool:
	var floor := StaticBody3D.new()
	var floor_shape := CollisionShape3D.new()
	var floor_box := BoxShape3D.new()
	floor_box.size = Vector3(14.0, 0.2, 8.0)
	floor_shape.shape = floor_box
	floor.add_child(floor_shape)
	floor.position = Vector3(0.0, -0.1, 0.0)
	root.add_child(floor)
	var slope := StaticBody3D.new()
	var slope_shape := CollisionShape3D.new()
	var slope_box := BoxShape3D.new()
	slope_box.size = Vector3(3.0, 0.2, 3.0)
	slope_shape.shape = slope_box
	slope_shape.rotation.z = deg_to_rad(-25.0)
	slope.add_child(slope_shape)
	slope.position = Vector3(0.0, 0.55, -1.5)
	root.add_child(slope)
	var step := StaticBody3D.new()
	var step_shape := CollisionShape3D.new()
	var step_box := BoxShape3D.new()
	step_box.size = Vector3(0.6, 0.6, 2.0)
	step_shape.shape = step_box
	step.add_child(step_shape)
	step.position = Vector3(0.0, 0.3, 1.8)
	root.add_child(step)
	var mover := CharacterBody3D.new()
	var mover_shape := CollisionShape3D.new()
	var mover_capsule := CapsuleShape3D.new()
	mover_capsule.height = 1.0
	mover_capsule.radius = 0.25
	mover_shape.shape = mover_capsule
	mover.add_child(mover_shape)
	mover.collision_layer = 1
	mover.collision_mask = 1
	mover.position = Vector3(-2.0, 0.5, -1.5)
	root.add_child(mover)
	var motor: CharacterMotor = CharacterMotorRef.new()
	root.add_child(motor)
	await physics_frame
	for tick in range(1, 31):
		motor.apply_physics_command(mover, {"actor_ref": "actor:surfaces", "physics_tick": tick, "desired_velocity": Vector3.RIGHT * 6.0, "facing_yaw": 0.0, "root_delta": Vector3.ZERO, "impulse": Vector3.ZERO, "runtime_correction": Vector3.ZERO, "source_digest": "surface:%s" % tick}, 0.1)
	var slope_observed := mover.get_slide_collision_count() > 0 and is_finite(mover.global_position.x) and is_finite(mover.global_position.y)
	mover.position = Vector3(-2.0, 0.5, 1.8)
	await physics_frame
	for tick in range(31, 61):
		motor.apply_physics_command(mover, {"actor_ref": "actor:surfaces", "physics_tick": tick, "desired_velocity": Vector3.RIGHT * 6.0, "facing_yaw": 0.0, "root_delta": Vector3.ZERO, "impulse": Vector3.ZERO, "runtime_correction": Vector3.ZERO, "source_digest": "step:%s" % tick}, 0.1)
	var step_observed := mover.get_slide_collision_count() > 0 and is_finite(mover.global_position.x) and is_finite(mover.global_position.y)
	motor.queue_free()
	mover.queue_free()
	step.queue_free()
	slope.queue_free()
	floor.queue_free()
	return slope_observed and step_observed

func _check_replica_runtime() -> bool:
	var replica := CharacterReplicaSceneRef.instantiate()
	replica.patrol_enabled = false
	root.add_child(replica)
	await process_frame
	await physics_frame
	var motor: CharacterMotor = replica.get_node("CharacterMotor") as CharacterMotor
	var moved := int(motor.body_revision) > 0
	replica.queue_free()
	return moved
