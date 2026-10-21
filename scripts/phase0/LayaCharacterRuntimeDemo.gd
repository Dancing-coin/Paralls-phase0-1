extends Node3D

const BACKEND_URL := "ws://127.0.0.1:8000/ws?stream_mode=runtime_only"
const ACTOR_IDS := ["char_a", "char_b"]
const EVENT_LABELS := ["目标保持注视", "环境亮度下降"]
@onready var bridge: Node = get_node_or_null("/root/BackendBridge")
@onready var bus: Node = get_node_or_null("/root/LocalPresentationBus")
@onready var status_label: Label = $DemoUI/Panel/Status
@onready var detail_label: RichTextLabel = $DemoUI/Panel/Details
@onready var event_label: Label = $DemoUI/Panel/Event
@onready var actor_label: Label = $DemoUI/Panel/ActorLabel
@onready var target_ring_a: MeshInstance3D = $ActorA/TargetRing
@onready var target_ring_b: MeshInstance3D = $ActorB/TargetRing
var actor_index := 0
var event_index := 0
var request_sequence := 0

func _ready() -> void:
	if bus != null:
		for signal_name in ["character_agent_output_received", "character_agent_execution_received", "character_agent_debug_snapshot_received", "character_agent_debug_event_received"]:
			if bus.has_signal(signal_name):
				bus.connect(signal_name, _on_backend_result if signal_name.ends_with("received") and not signal_name.contains("debug") else _on_backend_debug)
		if bus.has_signal("backend_ack_received"):
			bus.backend_ack_received.connect(_on_backend_ack)
	_update_selection()
	if bridge != null and bridge.has_method("connect_to_backend"):
		var configured := OS.get_environment("PARALLS_BACKEND_WS_URL").strip_edges()
		bridge.connect_to_backend(configured if not configured.is_empty() else BACKEND_URL)
	status_label.text = "等待 backend 连接；演示只显示获准公开投影。"

func _on_actor_pressed() -> void:
	actor_index = (actor_index + 1) % ACTOR_IDS.size()
	_update_selection()

func _on_event_pressed() -> void:
	event_index = (event_index + 1) % EVENT_LABELS.size()
	event_label.text = "可见事件：%s" % EVENT_LABELS[event_index]
	status_label.text = "事件已改变；请再次点击“让角色判断”。"

func _on_judge_pressed() -> void:
	if bridge == null or not bridge.has_method("is_backend_open") or not bridge.is_backend_open():
		status_label.text = "阻断：backend 不可用，没有复用旧成功。"
		return
	request_sequence += 1
	var selected := ACTOR_IDS[actor_index]
	var target := "char_b" if selected == "char_a" else "char_a"
	var fact_type := "fixed_gaze_on_target" if event_index == 0 else "light_level_drop"
	var relation := "actor_looks_at_actor" if event_index == 0 else "environment_light_drop"
	var payload := {"event_type":"raw_fact_event", "fact_family":"visual_fact", "fact_type":fact_type, "relation_type":relation, "producer_ts":Time.get_ticks_msec(), "room_id":"room_laya_runtime_demo", "scene_id":"scene_laya_runtime_demo", "zone_id":"zone_public_demo", "actor_id":"char_c", "target_actor_id":selected, "target_environment_id":"demo_lamp" if event_index == 1 else "", "request_id":"laya-demo:%s:%s" % [selected, request_sequence], "correlation_id":"laya-demo-round:%s" % request_sequence}
	status_label.text = "已发送真实 visual_fact_event；等待 admission → L3 → Laya → L4。"
	detail_label.text = "request=%s actor=%s target=%s event=%s" % [payload.request_id, selected, target if event_index == 0 else "demo_lamp", fact_type]
	bridge.send_envelope({"message_type":"raw_fact_event", "payload":payload})

func _update_selection() -> void:
	var selected := ACTOR_IDS[actor_index]
	actor_label.text = "当前角色：%s（切换后可对照同一事件）" % selected
	event_label.text = "可见事件：%s" % EVENT_LABELS[event_index]
	target_ring_a.visible = selected == "char_a"
	target_ring_b.visible = selected == "char_b"

func _on_backend_ack(payload: Dictionary) -> void:
	if not bool(payload.get("accepted", false)):
		status_label.text = "backend 阻断：%s" % str(payload.get("route", payload.get("error", "unknown")))

func _on_backend_result(payload: Dictionary) -> void:
	var actor := str(payload.get("actor_id", payload.get("actor_ref", ""))).replace("character:", "")
	if actor != ACTOR_IDS[actor_index] and not str(payload.get("actor_ref", "")).ends_with(ACTOR_IDS[actor_index]):
		return
	var choice := str(payload.get("selected_intent", payload.get("semantic_action_id", payload.get("semantic_intent_id", "未提供"))))
	var target := str(payload.get("target_actor_id", payload.get("target_ref", payload.get("target_refs", "未提供"))))
	var l4 := str(payload.get("l4_status", payload.get("admission_status", payload.get("status", "仅观测"))))
	status_label.text = "收到真实 backend 观测：模型/L4 结果已更新。"
	detail_label.text = "角色=%s\n选择=%s\n目标=%s\nL4=%s\nturn/request=%s/%s\n\n%s" % [actor, choice, target, l4, str(payload.get("turn_id", "")), str(payload.get("request_id", "")), JSON.stringify(payload)]

func _on_backend_debug(payload: Dictionary) -> void:
	status_label.text = "链路阶段：%s" % str(payload.get("stage", payload.get("event", "debug")))
	detail_label.text += "\n\n调试：revision=%s digest=%s 裁剪=%s" % [str(payload.get("revision", payload.get("frame_revision", "unknown"))), str(payload.get("digest", payload.get("frame_digest", "unknown"))), str(payload.get("truncation_reasons", payload.get("pruning_reasons", [])))]
