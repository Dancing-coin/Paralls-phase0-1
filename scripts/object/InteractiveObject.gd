extends Node3D

@export var object_id := "obj_letter"
var current_state := "idle"
var focused := false

@onready var mesh_instance: MeshInstance3D = $VisualRoot/GreyboxPropRoot/MeshInstance3D
@onready var label_3d: Label3D = $Label3D

func _ready() -> void:
    var bus := _get_bus()
    if bus:
        bus.world_result_received.connect(_on_world_result_received)
    _apply_visual_state()

func apply_result(payload: Dictionary) -> void:
    current_state = str(payload.get("current_state", payload.get("result_summary", current_state)))
    _apply_visual_state()
    _bus_log("object_state:%s:%s" % [object_id, current_state])

func _on_world_result_received(payload: Dictionary) -> void:
    if payload.get("target_object_id", "") == object_id:
        apply_result(payload)

func _apply_visual_state() -> void:
    if label_3d:
        label_3d.text = "Letter%s: %s" % [" <" if focused else "", current_state]

    if mesh_instance:
        var material := StandardMaterial3D.new()
        if focused:
            material.albedo_color = Color(1.0, 0.85, 0.25)
        else:
            material.albedo_color = Color(0.85, 0.75, 0.45) if current_state == "idle" else Color(0.45, 0.85, 0.45)
        mesh_instance.material_override = material

func _get_bus() -> Node:
    return get_node_or_null("/root/LocalPresentationBus")

func _bus_log(message: String) -> void:
    var bus := _get_bus()
    if bus and bus.has_method("log_debug"):
        bus.log_debug(message)

func set_focus_highlight(is_focused: bool) -> void:
    focused = is_focused
    _apply_visual_state()
