extends CharacterBody3D

@export var speed := 4.0
@export var dialogue_action := "phase0_submit_dialogue"
@export var interact_action := "phase0_interact"
@export var move_forward_action := "phase0_move_forward"
@export var move_backward_action := "phase0_move_backward"
@export var move_left_action := "phase0_move_left"
@export var move_right_action := "phase0_move_right"
@export var mouse_sensitivity := 0.004

@onready var main_demo: Node = get_parent()

var current_intent_frame: Dictionary = {}
var desired_facing_yaw := 0.0
var look_pitch := 0.0

func _ready() -> void:
    desired_facing_yaw = rotation.y

func _unhandled_input(event: InputEvent) -> void:
    if event is InputEventMouseMotion and Input.get_mouse_mode() == Input.MOUSE_MODE_CAPTURED:
        var motion := event as InputEventMouseMotion
        rotation.y -= motion.relative.x * mouse_sensitivity
        desired_facing_yaw = rotation.y
        look_pitch -= motion.relative.y * mouse_sensitivity

func _physics_process(_delta: float) -> void:
    current_intent_frame = _build_human_intent_frame()
    var move_local: Vector2 = current_intent_frame.get("move_local", Vector2.ZERO)
    var direction := Vector3(move_local.x, 0.0, move_local.y)
    velocity = direction * speed
    move_and_slide()

func _unhandled_input(event: InputEvent) -> void:
    if event.is_action_pressed(dialogue_action) and main_demo.has_method("submit_dialogue"):
        main_demo.submit_dialogue()

    if event.is_action_pressed(interact_action) and main_demo.has_method("submit_interaction"):
        main_demo.submit_interaction()

func trigger_dialogue() -> void:
    if main_demo.has_method("submit_dialogue"):
        main_demo.submit_dialogue()

func trigger_interaction() -> void:
    if main_demo.has_method("submit_interaction"):
        main_demo.submit_interaction()

func _build_human_intent_frame() -> Dictionary:
    var move_local := Input.get_vector(
        move_left_action,
        move_right_action,
        move_forward_action,
        move_backward_action
    )
    return {
        "controller_source": "human",
        "move_local": move_local,
        "desired_facing_yaw": desired_facing_yaw,
        "look_local": [0.0, look_pitch],
    }
