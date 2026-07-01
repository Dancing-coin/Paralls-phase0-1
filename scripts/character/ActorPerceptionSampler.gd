extends RefCounted

class_name ActorPerceptionSampler

var range_m := 28.0
var forward_threshold := 0.2

func sample_visible_targets(
	origin: Vector3,
	forward: Vector3,
	candidates: Array[Node3D],
	owner: Node3D,
	position_resolver: Callable = Callable(),
	los_tester: Callable = Callable()
) -> Array[Node3D]:
	var visible: Array[Node3D] = []
	var safe_forward := forward.normalized()
	for candidate: Node3D in candidates:
		if candidate == null or candidate == owner:
			continue
		var candidate_position := _resolve_candidate_position(candidate, position_resolver)
		if not _passes_cone(origin, safe_forward, candidate_position):
			continue
		if not _has_line_of_sight_to_target(owner, candidate, los_tester):
			continue
		visible.append(candidate)
	return visible

func _resolve_candidate_position(candidate: Node3D, position_resolver: Callable) -> Vector3:
	if position_resolver.is_valid():
		var resolved: Variant = position_resolver.call(candidate)
		if resolved is Vector3:
			return resolved
	return candidate.global_position

func _passes_cone(origin: Vector3, forward: Vector3, candidate_position: Vector3) -> bool:
	var offset := candidate_position - origin
	var distance := offset.length()
	if distance > range_m or distance <= 0.001:
		return false
	var direction := offset / distance
	return forward.dot(direction) >= forward_threshold

func _has_line_of_sight_to_target(_owner: Node3D, candidate: Node3D, los_tester: Callable) -> bool:
	if los_tester.is_valid():
		var los_result: Variant = los_tester.call(candidate)
		if los_result is bool:
			return los_result
	return candidate != null
