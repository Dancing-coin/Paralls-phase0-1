extends Node3D

@export var environment_id := "env_lamp"

var env_state := "stable"
var last_emitted_visual_fact_state := ""

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
    if payload.has("target_environment_id") and payload.has("current_state"):
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

func _get_bridge() -> Node:
    return get_node_or_null("/root/BackendBridge")

func _bus_log(message: String) -> void:
    var bus := _get_bus()
    if bus and bus.has_method("log_debug"):
        bus.log_debug(message)

func _emit_environment_visual_fact(previous_state: String, next_state: String) -> void:
    if previous_state == next_state:
        return
    if next_state != "alerted":
        return
    if last_emitted_visual_fact_state == next_state:
        return
    var bridge := _get_bridge()
    if bridge == null or (bridge.has_method("is_backend_open") and not bridge.is_backend_open()):
        return
    var envelope := {
        "message_type": "visual_fact_event",
        "payload": {
            "actor_id": "char_c",
            "room_id": "room_demo",
            "scene_id": "scene_demo",
            "zone_id": "zone_focus",
            "producer_ts": Time.get_ticks_msec(),
            "fact_type": "light_level_drop",
            "relation_type": "environment_light_drop",
            "target_environment_id": environment_id,
        },
    }
    bridge.send_envelope(envelope)
    last_emitted_visual_fact_state = next_state
    _bus_log("phase0_visual_fact:light_level_drop:%s" % environment_id)
