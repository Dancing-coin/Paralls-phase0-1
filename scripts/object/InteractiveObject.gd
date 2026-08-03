extends Node3D

@export var object_id := "obj_letter"
@export var display_name := "Letter"
@export var initial_state := "partially_visible"
@export_node_path("Node") var object_visual_fact_emitter_path := NodePath("../VisualFactEmitter/ObjectVisualFactEmitter")
var current_state := "partially_visible"
var focused := false

@onready var mesh_instance: MeshInstance3D = $VisualRoot/GreyboxPropRoot/MeshInstance3D
@onready var label_3d: Label3D = $Label3D

func _ready() -> void:
    current_state = initial_state
    var bus := _get_bus()
    if bus:
        bus.world_result_received.connect(_on_world_result_received)
    _apply_visual_state()

func apply_result(payload: Dictionary) -> void:
    current_state = str(payload.get("current_state", payload.get("result_summary", current_state)))
    _apply_visual_state()
    _bus_log("object_state:%s:%s" % [object_id, current_state])
    _emit_object_visual_fact()

func _on_world_result_received(payload: Dictionary) -> void:
    if str(payload.get("result_type", "")) != "object_state_result":
        return
    if str(payload.get("settlement_status", "")) != "applied":
        return
    if payload.get("target_object_id", "") == object_id:
        apply_result(payload)

func _apply_visual_state() -> void:
    if label_3d:
        label_3d.text = "%s%s: %s" % [display_name, " <" if focused else "", current_state]

    if mesh_instance:
        var material := StandardMaterial3D.new()
        if focused:
            material.albedo_color = Color(1.0, 0.85, 0.25)
        else:
            material.albedo_color = Color(0.85, 0.75, 0.45) if current_state in ["hidden", "partially_visible"] else Color(0.45, 0.85, 0.45)
        mesh_instance.material_override = material

func _get_bus() -> Node:
    return get_node_or_null("/root/LocalPresentationBus")

func _get_object_visual_fact_emitter() -> Node:
    return get_node_or_null(object_visual_fact_emitter_path)

func _bus_log(message: String) -> void:
    var bus := _get_bus()
    if bus and bus.has_method("log_debug"):
        bus.log_debug(message)

func _emit_object_visual_fact() -> void:
    var object_visual_fact_emitter := _get_object_visual_fact_emitter()
    if object_visual_fact_emitter == null:
        return
    if not object_visual_fact_emitter.has_method("emit_object_state_transition"):
        return
    object_visual_fact_emitter.emit_object_state_transition(object_id)

func set_focus_highlight(is_focused: bool) -> void:
    focused = is_focused
    _apply_visual_state()
