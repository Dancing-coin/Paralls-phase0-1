extends CanvasLayer

@onready var label: RichTextLabel = RichTextLabel.new()


func _ready() -> void:
	add_child(label)
	label.position = Vector2(760, 340)
	label.size = Vector2(560, 180)
	var state := _get_state()
	if state and state.has_signal("observatory_state_changed"):
		state.observatory_state_changed.connect(_refresh)
	_refresh()


func _refresh() -> void:
	var state := _get_state()
	if state == null:
		return
	var payload: Dictionary = state.call("get_latest_siming_state")
	var observatory_enabled: Variant = state.get("observatory_enabled")
	var director_mode: Variant = state.get("director_mode")
	visible = observatory_enabled == true and director_mode == true
	label.text = "\n".join(_build_director_rows(payload))


func _get_state() -> Node:
	return get_node_or_null("../CharacterDirectorState")


func _build_director_rows(payload: Dictionary) -> Array[String]:
	return [
		"司命现在看到的公平问题：%s" % str(payload.get("fairness_summary", "") or "暂时没看到失衡"),
		"司命正在考虑的出手方案：%s" % str(payload.get("intervention_candidate", "") or "还没有候选方案"),
		"司命最后怎么决定：%s" % str(payload.get("intervention_decision", "") or "还没拍板"),
		"司命走的是哪条路：%s" % str(payload.get("selected_path", "") or "还没定路径"),
		"司命这次出手属于哪一类：%s" % str(payload.get("intervention_band", "") or "暂时没分类"),
		"司命盯上的对象是：%s" % str(payload.get("target_ref", "") or "还没锁定目标"),
		"司命为什么这么做：%s" % str(payload.get("reason_summary", "") or "还没有明确理由"),
		"司命这步现在走到哪了：%s" % str(payload.get("downstream_status", "") or "还没进入下游"),
		"如果司命没出手，原因是：%s" % str(payload.get("no_action_reason", "") or "这次不是 no-action"),
	]
