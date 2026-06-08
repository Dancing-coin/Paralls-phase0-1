extends Node3D

@export var environment_id := "env_lamp"
@export_node_path("Node") var environment_visual_fact_emitter_path := NodePath("../VisualFactEmitter/EnvironmentVisualFactEmitter")

var env_state := "stable"

@onready var mesh_instance: MeshInstance3D = $VisualRoot/GreyboxFixtureRoot/MeshInstance3D
@onready var label_3d: Label3D = $Label3D

func _ready() -> void:
    var bus := _get_bus()
    if bus:
        bus.world_result_received.connect(_on_world_result_received)
    _apply_visual_state()

func apply_environment_shift(next_state: String) -> void:
    var previous_state := env_state
    env_state = next_state
    _apply_visual_state()
    _bus_log("environment_state:%s" % env_state)
    _emit_environment_visual_fact(previous_state, env_state)

func _on_world_result_received(payload: Dictionary) -> void:
    if payload.get("result_type", "") == "environment_state_result" and payload.has("target_environment_id") and payload.has("current_state"):
        apply_environment_shift(str(payload["current_state"]))

func _apply_visual_state() -> void:
    if label_3d:
        label_3d.text = "Env: %s" % env_state

    if mesh_instance:
        var material := StandardMaterial3D.new()
        material.albedo_color = Color(0.35, 0.65, 1.0) if env_state == "stable" else Color(1.0, 0.55, 0.25)
        mesh_instance.material_override = material

func _get_bus() -> Node:
    return get_node_or_null("/root/LocalPresentationBus")

func _get_environment_visual_fact_emitter() -> Node:
    return get_node_or_null(environment_visual_fact_emitter_path)

func _bus_log(message: String) -> void:
    var bus := _get_bus()
    if bus and bus.has_method("log_debug"):
        bus.log_debug(message)

func _emit_environment_visual_fact(previous_state: String, next_state: String) -> void:
    var environment_visual_fact_emitter := _get_environment_visual_fact_emitter()
    if environment_visual_fact_emitter == null:
        return
    if not environment_visual_fact_emitter.has_method("emit_environment_state_transition"):
        return
    environment_visual_fact_emitter.emit_environment_state_transition(environment_id, previous_state, next_state)
