extends Node

class_name ArchiveDoorPhysicalPresentation


@export var object_id := "obj_archive_door"
@export_node_path("Node3D") var hinge_pivot_path := NodePath("../HingePivot")
@export_node_path("CollisionShape3D") var closed_passage_blocker_path := NodePath("../ClosedPassageBlocker/CollisionShape3D")
@export_node_path("Label3D") var state_label_path := NodePath("../StateLabel")
@export var open_angle_degrees := -92.0

var current_state := "closed"
var passage_occlusion_state := "closed"
var applied_settlement_id := ""
var closed_transform := Transform3D.IDENTITY
var open_transform := Transform3D.IDENTITY

@onready var hinge_pivot: Node3D = get_node_or_null(hinge_pivot_path) as Node3D
@onready var closed_passage_blocker: CollisionShape3D = get_node_or_null(closed_passage_blocker_path) as CollisionShape3D
@onready var state_label: Label3D = get_node_or_null(state_label_path) as Label3D


func _ready() -> void:
	if hinge_pivot != null:
		closed_transform = hinge_pivot.transform
		open_transform = closed_transform.rotated_local(Vector3.UP, deg_to_rad(open_angle_degrees))
	var bus := _get_bus()
	if bus != null and bus.has_signal("world_result_received"):
		bus.world_result_received.connect(apply_result)
	_apply_closed_presentation()


func apply_result(payload: Dictionary) -> bool:
	if str(payload.get("result_type", "")) != "object_state_result":
		return false
	if str(payload.get("target_object_id", "")) != object_id:
		return false
	if str(payload.get("settlement_status", "")) != "applied":
		return false
	if str(payload.get("current_state", "")) != "open":
		return false
	if hinge_pivot == null or closed_passage_blocker == null:
		return false
	var next_settlement_id := str(payload.get("settlement_id", payload.get("result_id", "")))
	if current_state == "open" and next_settlement_id == applied_settlement_id:
		return true
	current_state = "open"
	passage_occlusion_state = "open"
	applied_settlement_id = next_settlement_id
	hinge_pivot.transform = open_transform
	closed_passage_blocker.set_deferred("disabled", true)
	_apply_label()
	_emit_presentation_observation(payload)
	return true


func snapshot() -> Dictionary:
	return {
		"current_state": current_state,
		"door_leaf_transform": hinge_pivot.transform if hinge_pivot != null else Transform3D.IDENTITY,
		"closed_blocker_enabled": not closed_passage_blocker.disabled if closed_passage_blocker != null else false,
		"passage_occlusion_state": passage_occlusion_state,
		"applied_settlement_id": applied_settlement_id,
	}


func _apply_closed_presentation() -> void:
	current_state = "closed"
	passage_occlusion_state = "closed"
	applied_settlement_id = ""
	if hinge_pivot != null:
		hinge_pivot.transform = closed_transform
	if closed_passage_blocker != null:
		closed_passage_blocker.set_deferred("disabled", false)
	_apply_label()


func _apply_label() -> void:
	if state_label != null:
		state_label.text = "Archive Door: %s" % current_state


func _emit_presentation_observation(payload: Dictionary) -> void:
	var interaction_attempt_id := str(payload.get("interaction_attempt_id", ""))
	if interaction_attempt_id.is_empty() or applied_settlement_id.is_empty():
		return
	var bus := _get_bus()
	if bus == null or not bus.has_signal("embodied_presentation_observed_emitted"):
		return
	bus.emit_signal("embodied_presentation_observed_emitted", {
		"interaction_attempt_id": str(payload.get("interaction_attempt_id", "")),
		"settlement_id": applied_settlement_id,
		"snapshot_digest": _snapshot_digest(),
	})


func _snapshot_digest() -> String:
	var hinge_origin := hinge_pivot.transform.origin if hinge_pivot != null else Vector3.ZERO
	var snapshot_payload := {
		"current_state": current_state,
		"passage_occlusion_state": passage_occlusion_state,
		"closed_blocker_enabled": not closed_passage_blocker.disabled if closed_passage_blocker != null else false,
		"applied_settlement_id": applied_settlement_id,
		"hinge_origin": [hinge_origin.x, hinge_origin.y, hinge_origin.z],
	}
	return "sha256:%s" % JSON.stringify(snapshot_payload).sha256_text()


func _get_bus() -> Node:
	return get_node_or_null("/root/LocalPresentationBus")
