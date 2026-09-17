extends RefCounted
class_name PhysicsMotionCommand
static func build(actor_ref: StringName, physics_tick: int, desired_velocity: Vector3, root_delta: Vector3, impulse: Vector3, runtime_correction: Vector3, facing_yaw: float, source_digest: StringName) -> Dictionary:
	return {"actor_ref": actor_ref, "physics_tick": physics_tick, "desired_velocity": desired_velocity, "root_delta": root_delta, "impulse": impulse, "runtime_correction": runtime_correction, "facing_yaw": facing_yaw, "source_digest": source_digest, "claims": [&"root_translation", &"physics_body"]}
