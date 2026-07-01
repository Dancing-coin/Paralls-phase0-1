extends CanvasLayer

var actor_cards := {}


func _ready() -> void:
	var state := _get_state()
	if state and state.has_signal("observatory_state_changed"):
		state.observatory_state_changed.connect(_refresh)
	_refresh()


func _process(_delta: float) -> void:
	_refresh_card_positions()


func _refresh() -> void:
	var state := _get_state()
	if state == null:
		return
	var observatory_enabled: Variant = state.get("observatory_enabled")
	visible = observatory_enabled == true
	_sync_actor_cards(state)
	_refresh_card_positions()


func _get_state() -> Node:
	return get_node_or_null("../CharacterDirectorState")


func _sync_actor_cards(state: Node) -> void:
	var actor_states: Dictionary = state.call("get_visible_actor_states")
	var selected_actor_id := str(state.get("selected_actor_id"))
	var active_actor_ids: Array[String] = []
	for actor_id in actor_states.keys():
		var actor_id_text := str(actor_id)
		active_actor_ids.append(actor_id_text)
		var card := _get_or_create_card(actor_id_text)
		var payload: Dictionary = actor_states[actor_id]
		var primary := _build_primary_line(actor_id_text, payload)
		var secondary := _build_secondary_line(payload)
		if actor_id_text == selected_actor_id:
			card.text = "\n".join([primary, secondary, _build_reason_line(payload)])
			card.modulate = Color(1.0, 0.97, 0.78, 1.0)
		else:
			card.text = "\n".join([primary, secondary])
			card.modulate = Color(0.92, 0.95, 1.0, 0.78)
		card.visible = true

	for actor_id in actor_cards.keys():
		if not active_actor_ids.has(str(actor_id)):
			var stale_card: Label = actor_cards[actor_id]
			stale_card.visible = false


func _get_or_create_card(actor_id: String) -> Label:
	if actor_cards.has(actor_id):
		return actor_cards[actor_id]
	var card := Label.new()
	card.name = "ActorCard_%s" % actor_id
	card.size = Vector2(240, 54)
	card.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	card.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	card.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(card)
	actor_cards[actor_id] = card
	return card


func _refresh_card_positions() -> void:
	var state := _get_state()
	if state == null:
		return
	var camera: Camera3D = get_viewport().get_camera_3d()
	if camera == null:
		return
	var selected_actor_id := str(state.get("selected_actor_id"))
	for actor_id in actor_cards.keys():
		var actor_node_value: Variant = state.call("resolve_target_node", str(actor_id))
		var card: Label = actor_cards[actor_id]
		if not (actor_node_value is Node3D):
			card.visible = false
			continue
		var actor_node: Node3D = actor_node_value as Node3D
		var world_point: Vector3 = actor_node.global_position + Vector3(0.0, 2.15, 0.0)
		var screen_point: Vector2 = camera.unproject_position(world_point)
		card.position = screen_point - Vector2(card.size.x * 0.5, card.size.y)
		var camera_distance := camera.global_position.distance_to(world_point)
		if camera_distance > 18.0:
			var payload: Dictionary = actor_states_for(state).get(str(actor_id), {})
			card.text = _build_primary_line(str(actor_id), payload)
		elif str(actor_id) != selected_actor_id:
			var payload: Dictionary = actor_states_for(state).get(str(actor_id), {})
			card.text = "\n".join([_build_primary_line(str(actor_id), payload), _build_secondary_line(payload)])


func _build_primary_line(actor_id: String, payload: Dictionary) -> String:
	return "%s | %s" % [
		_actor_label(actor_id),
		str(payload.get("state_label", "") or "状态未知"),
	]


func _build_secondary_line(payload: Dictionary) -> String:
	return "当前意图：%s -> 当前目标：%s" % [
		str(payload.get("current_intent", "") or "暂无"),
		str(payload.get("focus_target", "") or "暂无"),
	]


func _build_reason_line(payload: Dictionary) -> String:
	var why_now := str(payload.get("why_now_summary", "") or "暂无")
	var siming_summary := str(payload.get("latest_siming_summary", "") or "")
	if siming_summary.is_empty():
		return "原因摘要：%s" % why_now
	return "原因摘要：%s | 司命影响：%s" % [why_now, siming_summary]


func _actor_label(actor_id: String) -> String:
	if actor_id == "char_a":
		return "角色A"
	if actor_id == "char_b":
		return "角色B"
	if actor_id == "char_c":
		return "玩家角色"
	return actor_id


func actor_states_for(state: Node) -> Dictionary:
	return state.call("get_visible_actor_states")
