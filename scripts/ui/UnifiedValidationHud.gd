extends CanvasLayer

class_name UnifiedValidationHud

var _label: Label
var _elapsed := 0.0


func _ready() -> void:
	_label = Label.new()
	_label.position = Vector2(18, 18)
	_label.size = Vector2(720, 120)
	_label.add_theme_color_override("font_color", Color(0.86, 0.93, 1.0, 1.0))
	_label.add_theme_color_override("font_shadow_color", Color(0.0, 0.0, 0.0, 0.8))
	_label.add_theme_constant_override("shadow_offset_x", 2)
	_label.add_theme_constant_override("shadow_offset_y", 2)
	add_child(_label)
	_refresh()


func _process(delta: float) -> void:
	_elapsed += delta
	if int(_elapsed * 4.0) != int((_elapsed - delta) * 4.0):
		_refresh()


func _refresh() -> void:
	if _label == null:
		return
	var root := get_tree().current_scene
	var backend := get_node_or_null("/root/BackendBridge")
	var backend_state := "connected" if backend != null and backend.has_method("is_backend_open") and backend.is_backend_open() else "offline"
	var collision_count := 0
	if root != null:
		collision_count = _count_nodes(root, "CollisionShape3D")
	_label.text = "UNIFIED 3D INTEGRATION VALIDATION\n" + \
		"backend=%s  collision_shapes=%d  art_mode=generic_fallback\n" % [backend_state, collision_count] + \
		"F11 perception debug  |  F6/F7/F8 observatory controls  |  E interact  |  F dialogue"


func _count_nodes(node: Node, type_name: String) -> int:
	var total := 1 if node.get_class() == type_name else 0
	for child in node.get_children():
		total += _count_nodes(child, type_name)
	return total
