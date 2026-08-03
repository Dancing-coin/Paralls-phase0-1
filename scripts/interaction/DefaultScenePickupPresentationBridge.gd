extends Node

class_name DefaultScenePickupPresentationBridge

const CARRY_PLACE_CONSUMER := preload("res://scripts/interaction/CarryPlaceMirrorConsumer.gd")

@export_node_path("Node3D") var target_object_path := NodePath("../InteractiveArchiveToken")
@export_node_path("Node3D") var presentation_attachment_target_path := NodePath("")
@export var object_id := "obj_archive_token"
@export var asset_ref := "item:archive_token_01"

var presentation_state := "world"
var last_authority_transaction_id := ""
var carry_place_consumer: Node


func _ready() -> void:
	carry_place_consumer = CARRY_PLACE_CONSUMER.new()
	add_child(carry_place_consumer)
	var bus := _get_bus()
	if bus != null and bus.has_signal("embodied_carry_place_event_received"):
		bus.embodied_carry_place_event_received.connect(_on_embodied_carry_place_event)
	if bus != null and bus.has_signal("embodied_inventory_stow_result_received"):
		bus.embodied_inventory_stow_result_received.connect(_on_embodied_inventory_stow_result)
	if bus != null and bus.has_signal("embodied_inventory_retrieve_result_received"):
		bus.embodied_inventory_retrieve_result_received.connect(_on_embodied_inventory_retrieve_result)


func _on_embodied_carry_place_event(payload: Dictionary) -> void:
	if carry_place_consumer == null:
		return
	# CarryPlaceMirrorConsumer accepts only an authority_only placement directive.
	var authority_only_accepted: Dictionary = carry_place_consumer.consume_authority_event(payload)
	if not bool(authority_only_accepted.get("accepted", false)):
		return
	if str(payload.get("asset_ref", "")) != asset_ref:
		return
	_apply_authority_presentation(payload)


func _apply_authority_presentation(payload: Dictionary) -> void:
	var target := get_node_or_null(target_object_path) as Node3D
	if target == null:
		return
	last_authority_transaction_id = str(payload.get("transaction_id", ""))
	presentation_state = "carried"
	var attachment_target := get_node_or_null(presentation_attachment_target_path) as Node3D
	if attachment_target != null:
		target.reparent(attachment_target, true)
		return
	# A reviewed hand mount can opt in later. Until then, hide the world prop only
	# after settlement; this remains presentation, not an inventory or ownership write.
	target.visible = false


func can_request_stow(target_id: String) -> bool:
	return target_id == object_id and presentation_state == "carried"


func _on_embodied_inventory_stow_result(payload: Dictionary) -> void:
	if not bool(payload.get("accepted", false)):
		return
	if str(payload.get("target_object_id", "")) != object_id:
		return
	var directive: Variant = payload.get("presentation_directive", {})
	if typeof(directive) != TYPE_DICTIONARY:
		return
	var presentation_directive: Dictionary = directive
	if str(presentation_directive.get("mode", "")) != "inventory_stowed_for_presentation":
		return
	if not bool(presentation_directive.get("authority_only", false)):
		return
	var transaction_id := str(payload.get("transaction_id", ""))
	if transaction_id.is_empty():
		return
	# This is a read-only local presentation marker. The backend ledger remains
	# the authority for container location, custody, and ownership.
	presentation_state = "stowed"
	last_authority_transaction_id = transaction_id


func _on_embodied_inventory_retrieve_result(payload: Dictionary) -> void:
	if not bool(payload.get("accepted", false)):
		return
	if str(payload.get("asset_ref", "")) != asset_ref:
		return
	var directive: Variant = payload.get("presentation_directive", {})
	if typeof(directive) != TYPE_DICTIONARY:
		return
	var presentation_directive: Dictionary = directive
	if str(presentation_directive.get("mode", "")) != "inventory_retrieved_for_presentation":
		return
	if not bool(presentation_directive.get("authority_only", false)):
		return
	var transaction_id := str(payload.get("transaction_id", ""))
	if transaction_id.is_empty():
		return
	# This only restores the local carried marker after authority settlement.
	# A future reviewed hand mount may render the item; this bridge still owns no
	# inventory, custody, or world-state write.
	presentation_state = "carried"
	last_authority_transaction_id = transaction_id


func _get_bus() -> Node:
	return get_node_or_null("/root/LocalPresentationBus")
