extends CharacterBody3D

@export var speed := 4.0
@export var dialogue_action := "phase0_submit_dialogue"
@export var interact_action := "phase0_interact"

@onready var main_demo: Node = get_parent()

func _physics_process(_delta: float) -> void:
    var input_vector := Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
    var direction := Vector3(input_vector.x, 0.0, input_vector.y)
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
