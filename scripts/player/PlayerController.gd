extends CharacterBody3D

@export var speed := 4.0
@export var dialogue_action := "phase0_submit_dialogue"
@export var interact_action := "phase0_interact"
@export var move_forward_action := "phase0_move_forward"
@export var move_backward_action := "phase0_move_backward"
@export var move_left_action := "phase0_move_left"
@export var move_right_action := "phase0_move_right"

@onready var main_demo: Node = get_parent()

var current_intent_frame: Dictionary = {}

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
    }
