extends RefCounted

class_name ActorActionArbiter

const ContinuousControlLeaseRef = preload("res://scripts/character/ContinuousControlLease.gd")
const ActionInstanceRef = preload("res://scripts/character/ActionInstance.gd")
const ResourceClaimSchedulerRef = preload("res://scripts/character/ResourceClaimScheduler.gd")
const CharacterIntentFrameRef = preload("res://scripts/character/CharacterIntentFrame.gd")


static func resolve(physics_tick: int, leases: Array[Dictionary], actions: Array[Dictionary], runtime: Dictionary) -> Dictionary:
	var requests: Array[Dictionary] = []
	for lease in leases:
		if ContinuousControlLeaseRef.is_active(lease, physics_tick):
			requests.append(lease.duplicate(true))
	for action in actions:
		if str(action.get("lifecycle", "requested")) in ActionInstanceRef.LIFECYCLE:
			requests.append(action.duplicate(true))
	requests.sort_custom(_sort_requests)
	var occupancy: Dictionary = runtime.get("occupancy", {}).duplicate(true)
	var admitted: Array[Dictionary] = []
	var queued: Array[Dictionary] = []
	var rejected: Array[Dictionary] = []
	for request in requests:
		var decision := ResourceClaimSchedulerRef.decide(request, occupancy, physics_tick)
		request["admission"] = decision
		match decision["decision"]:
			&"accept_now":
				admitted.append(request)
				for claim in request.get("claims", []):
					occupancy[claim] = request.get("request_id", "")
			&"queue": queued.append(request)
			_: rejected.append(request)
	return CharacterIntentFrameRef.build(physics_tick, admitted, queued, rejected)


static func _sort_requests(left: Dictionary, right: Dictionary) -> bool:
	var left_key := [-int(left.get("priority", 0)), -int(left.get("source_priority", 0)), str(left.get("source_id", "")), str(left.get("request_id", ""))]
	var right_key := [-int(right.get("priority", 0)), -int(right.get("source_priority", 0)), str(right.get("source_id", "")), str(right.get("request_id", ""))]
	return left_key < right_key
