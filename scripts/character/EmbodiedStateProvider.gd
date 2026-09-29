extends RefCounted

class_name EmbodiedStateProvider

const ProviderSampleBaseRef = preload("res://scripts/character/ProviderSampleBase.gd")

var provider_kind := "embodied_state"
var provider_role := "sampling_only"
var heavy_inference_allowed := false

func build_query_input_ref(
	subject_id: String,
	posture: String,
	locomotion_state: String,
	grounded: bool,
	los_failure: bool = false,
	reachability_failure: bool = false
) -> Dictionary:
	var runtime_state_ref := "runtime://embodied/%s/state/%s" % [subject_id, Time.get_ticks_msec()]
	var status := "ok" if not los_failure and not reachability_failure else "stub_artifact"
	return ProviderSampleBaseRef.attach_sample_metadata({
		"provider_kind": provider_kind,
		"ref_id": runtime_state_ref,
		"summary": "high-level embodied state slice",
		"retention": "ref_only",
		"runtime_source_refs": [runtime_state_ref],
		"posture": posture,
		"locomotion_state": locomotion_state,
		"grounded": grounded,
		"los_failure": los_failure,
		"reachability_failure": reachability_failure,
		"feeds_query_frame": true,
		"provider_role": provider_role,
	}, "runtime://embodied/%s" % subject_id, status, "")


func build_from_actor_node(
	subject_id: String,
	actor_node: Node,
	los_failure: bool = false,
	reachability_failure: bool = false
) -> Dictionary:
	var actor := _resolve_actor_capability(actor_node)
	var posture := "standing"
	var locomotion_state := "idle"
	var grounded := true
	var runtime_source_refs: Array[String] = []
	var capability_failure := ""
	if actor != null:
		runtime_source_refs.append("runtime://node%s" % str(actor.get_path()))
		if actor.has_method("is_grounded_state"):
			grounded = bool(actor.call("is_grounded_state"))
		elif actor.has_method("is_on_floor"):
			grounded = bool(actor.call("is_on_floor"))
		var planar_velocity := Vector3.ZERO
		if actor.has_method("get_planar_velocity"):
			var candidate_velocity: Variant = actor.call("get_planar_velocity")
			if candidate_velocity is Vector3:
				planar_velocity = candidate_velocity
		else:
			var velocity_candidate: Variant = actor.get("velocity")
			if velocity_candidate is Vector3:
				planar_velocity = Vector3(velocity_candidate.x, 0.0, velocity_candidate.z)
		locomotion_state = "locomotion" if planar_velocity.length() > 0.05 else "idle"
		if actor.has_method("get_locomotion_status"):
			var status: Variant = actor.call("get_locomotion_status")
			if status is Dictionary:
				posture = str(status.get("stance", posture))
				locomotion_state = str(status.get("gait", locomotion_state))
	else:
		capability_failure = "actor_capability_unavailable"
	var payload := build_query_input_ref(subject_id, posture, locomotion_state, grounded, los_failure or not capability_failure.is_empty(), reachability_failure)
	payload["runtime_source_refs"] = payload.get("runtime_source_refs", []) + runtime_source_refs
	payload["actor_node_path"] = str(actor.get_path()) if actor != null else ""
	payload["capability_failure"] = capability_failure
	return payload


func _resolve_actor_capability(root: Node) -> Node:
	if root == null:
		return null
	if _has_actor_capability(root):
		return root
	for child: Node in root.get_children():
		var found := _resolve_actor_capability(child)
		if found != null:
			return found
	return null


func _has_actor_capability(node: Node) -> bool:
	return node != null and node.has_method("apply_control_intent") and node.has_method("get_focus_anchor_position") and node.has_method("get_embodied_forward_vector")
