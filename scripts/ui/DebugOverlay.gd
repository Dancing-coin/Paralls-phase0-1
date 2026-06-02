extends CanvasLayer

var lines: Array[String] = []
var label: Label

func _ready() -> void:
    label = Label.new()
    label.position = Vector2(16, 16)
    label.size = Vector2(900, 240)
    add_child(label)
    var bus := _get_bus()
    if bus:
        bus.debug_event_logged.connect(_on_debug_event_logged)
    _refresh_label()

func _on_debug_event_logged(message: String) -> void:
    lines.append(message)
    if lines.size() > 14:
        lines = lines.slice(lines.size() - 14, lines.size())
    _refresh_label()

func _refresh_label() -> void:
    if label:
        label.text = "\n".join(lines)

func _get_bus() -> Node:
    return get_node_or_null("/root/LocalPresentationBus")
