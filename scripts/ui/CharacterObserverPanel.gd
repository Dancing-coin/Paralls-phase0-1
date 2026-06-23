extends CanvasLayer

@onready var label: RichTextLabel = RichTextLabel.new()


func _ready() -> void:
	add_child(label)
	label.position = Vector2(980, 48)
	label.size = Vector2(340, 420)
	var state := _get_state()
	if state and state.has_signal("observatory_state_changed"):
		state.observatory_state_changed.connect(_refresh)
	_refresh()


func _refresh() -> void:
	var state := _get_state()
	if state == null:
		return
	var observatory_enabled: Variant = state.get("observatory_enabled")
	visible = observatory_enabled == true
	var payload: Dictionary = state.call("get_selected_actor_state")
	if payload.is_empty():
		label.text = "还没收到这个角色的观测数据。先把镜头对准角色，再做一次对话或交互。"
		return
	label.text = "\n\n".join(
		[
			"看到了什么\n%s" % _compact_value(payload.get("perception_summary", ""), "暂无明显感知"),
			"怎么理解\n%s" % _compact_value(payload.get("interpretation_summary", ""), "暂无判断"),
			"准备做什么\n%s" % _compact_value(_resolve_action_summary(payload), "暂无执行"),
			"世界 / 司命反馈\n%s" % _compact_value(_resolve_feedback_summary(payload), "暂无反馈"),
		]
	)


func _get_state() -> Node:
	return get_node_or_null("../CharacterDirectorState")


func _compact_value(value: Variant, fallback: String) -> String:
	var text := str(value or "")
	if text.is_empty():
		return fallback
	if text.length() > 72:
		return "%s..." % text.substr(0, 72)
	return text


func _resolve_action_summary(payload: Dictionary) -> String:
	var decision := str(payload.get("decision_summary", "") or "")
	var execution := str(payload.get("execution_summary", "") or "")
	if not execution.is_empty():
		return execution
	return decision


func _resolve_feedback_summary(payload: Dictionary) -> String:
	var outcome := str(payload.get("latest_outcome_summary", "") or "")
	var siming := str(payload.get("latest_siming_summary", "") or "")
	if not outcome.is_empty() and not siming.is_empty():
		return "%s | %s" % [outcome, siming]
	if not outcome.is_empty():
		return outcome
	return siming
