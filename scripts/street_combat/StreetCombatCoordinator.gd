extends Node

signal state_changed

const BACKEND_URL := "ws://127.0.0.1:8000/ws"
const ACTOR_NODES := {
	"street_bandage": "../PlayerCharacter",
	"char_a": "../AgentCharacterJK",
	"char_b": "../AgentCharacterT",
}

var target_actor_id := "char_a"
var connected := false
var actor_hp := {"street_bandage": 100, "char_a": 100, "char_b": 100}
var actor_stamina := {"street_bandage": 100, "char_a": 100, "char_b": 100}
var agent_intents := {"char_a": "idle", "char_b": "idle"}
var pending_attempts: Dictionary = {}
var results_by_attempt: Dictionary = {}
var duplicate_attempts: Dictionary = {}
var event_feed: Array[String] = []
var _sequence := 0
var _pose_frame := 0
var _registry := CharacterEmbodimentAssetRegistry.new()


func _ready() -> void:
	var bus := get_node("/root/LocalPresentationBus")
	bus.backend_connected.connect(_on_backend_connected)
	bus.backend_disconnected.connect(_on_backend_disconnected)
	bus.street_combat_result_received.connect(_on_combat_result)
	bus.street_combat_pose_result_received.connect(_on_pose_result)
	bus.character_agent_execution_received.connect(_on_agent_execution)
	if OS.get_environment("PARALLS_STREET_PROBE") != "1":
		call_deferred("_connect_backend")


func _connect_backend() -> void:
	var url := OS.get_environment("PARALLS_BACKEND_WS_URL").strip_edges()
	get_node("/root/BackendBridge").connect_to_backend(url if not url.is_empty() else BACKEND_URL)


func _physics_process(_delta: float) -> void:
	if not connected:
		return
	_pose_frame += 1
	if _pose_frame % 6 == 0:
		for actor_id in ACTOR_NODES:
			send_pose(actor_id)


func send_pose(actor_id: String, physics_tick_override: int = -1) -> bool:
	var actor := get_node_or_null(str(ACTOR_NODES.get(actor_id, ""))) as Node3D
	if actor == null or not connected:
		return false
	var position := actor.global_position
	var physics_tick := physics_tick_override if physics_tick_override >= 0 else Engine.get_physics_frames()
	return get_node("/root/BackendBridge").send_envelope({"message_type": "street_combat_pose", "payload": {"actor_id": actor_id, "position": [position.x, position.y, position.z], "physics_tick": physics_tick}}) == OK


func request_attack(actor_id: String, target_id: String, request_key: String = "", expected_revisions: Dictionary = {}, semantic_action_id: String = "action:melee.unarmed_punch") -> String:
	if not ACTOR_NODES.has(actor_id) or not ACTOR_NODES.has(target_id) or actor_id == target_id:
		_append_event("Attack unavailable: connection or target")
		return ""
	var actor := get_node(str(ACTOR_NODES[actor_id])) as CharacterBody3D
	var action_source := StringName("player" if actor_id == "street_bandage" else "agent")
	var action_admission: Dictionary = actor.call("submit_action_intent", StringName(semantic_action_id), StringName("character:%s" % target_id), action_source) if actor.has_method("submit_action_intent") else {"accepted": false, "reason": "action_intent_boundary_missing"}
	if not bool(action_admission.get("accepted", false)):
		_append_event("Attack unavailable: action arbiter rejected")
		return ""
	var skin := actor.get_node("VisualRoot/AssetMount/RotationOffset/ScaleOffset/ImportedModel/RoleAssetRoot/StreetCharacterSkin")
	var package_id := str(actor.get_meta("package_id", ""))
	var adapter := RolePresentationAdapter.new(_registry, skin)
	var presentation := adapter.apply_input({"package_id": package_id, "semantic_action_id": semantic_action_id, "claims": []})
	if not bool(presentation.get("accepted", false)):
		_append_event("Attack unavailable: unqualified action")
		return ""
	if not connected:
		_append_event("本地动作预览  %s" % ("剑击" if semantic_action_id == "action:melee.sword_slash" else "拳击"))
		return ""
	var backend_bridge := get_node_or_null("/root/BackendBridge")
	if backend_bridge == null or not backend_bridge.has_method("next_action_transport_context"):
		_append_event("Attack unavailable: action transport unavailable")
		return ""
	var transport_context: Dictionary = backend_bridge.next_action_transport_context()
	var connection_epoch := int(transport_context.get("connection_epoch", 0))
	var client_sequence := int(transport_context.get("client_sequence", 0))
	if connection_epoch < 1 or client_sequence < 1:
		_append_event("Attack unavailable: action transport epoch not ready")
		return ""
	_sequence += 1
	var key := request_key if not request_key.is_empty() else "%s:%s" % [actor_id, _sequence]
	var attempt_id := "street:attempt:%s" % key
	var profile: Dictionary = presentation.get("selected_profile", {})
	var markers: Array = profile.get("timing_markers", [])
	var marker: Dictionary = markers[0] if not markers.is_empty() else {}
	var contact_time := float(marker.get("time_seconds", 0.0))
	var action_descriptor_digest := _digest_dictionary(profile)
	_append_event("%s → %s  %s" % [actor_id, target_id, "剑击" if semantic_action_id == "action:melee.sword_slash" else "拳击"])
	if contact_time > 0.0:
		await get_tree().create_timer(contact_time).timeout
	if not connected:
		_append_event("Attack pending: backend disconnected")
		return ""
	var target := get_node(str(ACTOR_NODES[target_id])) as CharacterBody3D
	var attempt_physics_tick := Engine.get_physics_frames()
	send_pose(actor_id, attempt_physics_tick)
	send_pose(target_id, attempt_physics_tick)
	var marker_id := str(marker.get("marker_id", "punch_contact_window"))
	var contact_ref := _contact_evidence(actor, target, attempt_id, attempt_physics_tick, marker_id)
	var attempt := {
		"attempt_id": attempt_id,
		"actor_ref": "character:%s" % actor_id,
		"action_instance_id": "action:%s" % key,
		"semantic_action_id": semantic_action_id,
		"target_refs": ["character:%s" % target_id],
		"contact_marker_id": marker_id,
		"contact_marker_time_seconds": contact_time,
		"physics_tick": attempt_physics_tick,
		"connection_epoch": connection_epoch,
		"client_sequence": client_sequence,
		"submitted_at": Time.get_ticks_msec(),
		"physics_evidence_refs": [contact_ref] if not contact_ref.is_empty() else [],
		"physics_evidence_digest": _digest_contact_evidence(contact_ref, attempt_id, attempt_physics_tick, marker_id, "character:%s" % actor_id, "character:%s" % target_id),
		"action_descriptor_digest": action_descriptor_digest,
		"authority_route": "esm",
		"expected_revisions": expected_revisions.duplicate(true),
		"idempotency_key": "street:idem:%s" % key,
		"command_version": "v1",
		"causation_id": "street:cause:%s" % key,
		"correlation_id": "street:corr:%s" % key,
		"source": "player" if actor_id == "street_bandage" else "agent_inf",
		"privacy_scope": "public",
	}
	if get_node("/root/BackendBridge").send_envelope({"message_type": "street_combat_attempt", "payload": {"attempt": attempt}}) != OK:
		_append_event("Attack send failed")
		return ""
	pending_attempts[attempt_id] = {"actor_id": actor_id, "target_id": target_id, "attempt": attempt}
	state_changed.emit()
	return attempt_id


func replay_attempt(attempt_id: String) -> bool:
	var pending: Dictionary = pending_attempts.get(attempt_id, {})
	if pending.is_empty() or not connected:
		return false
	return get_node("/root/BackendBridge").send_envelope({"message_type": "street_combat_attempt", "payload": {"attempt": pending["attempt"]}}) == OK


func _contact_evidence(actor: CharacterBody3D, target: CharacterBody3D, attempt_id: String, physics_tick: int, marker_id: String) -> String:
	var from := actor.global_position + Vector3(0, 1.0, 0)
	var to := target.global_position + Vector3(0, 1.0, 0)
	if from.distance_to(to) > 2.5:
		return ""
	var query := PhysicsRayQueryParameters3D.create(from, to)
	query.exclude = [actor.get_rid()]
	var hit: Dictionary = actor.get_world_3d().direct_space_state.intersect_ray(query)
	return "contact:%s:%s:%s" % [attempt_id, physics_tick, marker_id] if hit.get("collider") == target else ""


func _on_backend_connected(_url: String) -> void:
	connected = true
	_append_event("Backend connected")


func _on_backend_disconnected(_code: int) -> void:
	connected = false
	_append_event("Backend disconnected")


func _on_pose_result(payload: Dictionary) -> void:
	if not bool(payload.get("accepted", false)):
		_append_event("Pose rejected: %s" % str(payload.get("actor_id", "")))
		return
	var actor_id := str(payload.get("actor_id", ""))
	var state: Dictionary = payload.get("actor_state", {})
	if actor_hp.has(actor_id) and state.has("hp"):
		actor_hp[actor_id] = int(state["hp"])
	if actor_stamina.has(actor_id) and state.has("stamina"):
		actor_stamina[actor_id] = int(state["stamina"])
	state_changed.emit()


func _on_combat_result(payload: Dictionary) -> void:
	var result: Dictionary = payload.get("authority_result", {})
	var attempt_id := str(result.get("attempt_id", ""))
	if attempt_id.is_empty():
		_append_event("Combat request rejected: %s" % str(payload.get("error_code", "invalid")))
		return
	var pending: Dictionary = pending_attempts.get(attempt_id, {})
	if pending.is_empty():
		return
	var prior: Dictionary = results_by_attempt.get(attempt_id, {})
	if not prior.is_empty() and str(prior.get("transaction_id", "")) == str(result.get("transaction_id", "")):
		duplicate_attempts[attempt_id] = true
		state_changed.emit()
		return
	results_by_attempt[attempt_id] = result.duplicate(true)
	if str(result.get("outcome", "")) == "committed":
		var target_id := str(pending.get("target_id", ""))
		var projection: Dictionary = result.get("committed_projection", {})
		actor_hp[target_id] = int(projection.get("target_hp", actor_hp.get(target_id, 100)))
		var actor_id := str(pending.get("actor_id", ""))
		if actor_stamina.has(actor_id) and projection.has("actor_stamina"):
			actor_stamina[actor_id] = int(projection["actor_stamina"])
		var target := get_node(str(ACTOR_NODES[target_id]))
		var skin := target.get_node("VisualRoot/AssetMount/RotationOffset/ScaleOffset/ImportedModel/RoleAssetRoot/StreetCharacterSkin")
		skin.play_recoil()
		_append_event("命中 %s  生命 %s  %s" % [target_id, actor_hp[target_id], attempt_id])
	else:
		_append_event("拒绝 %s  %s" % [str(result.get("failed_code", "unknown")), attempt_id])
	state_changed.emit()


func _on_agent_execution(payload: Dictionary) -> void:
	var actor_id := str(payload.get("actor_id", payload.get("actor_ref", ""))).trim_prefix("character:")
	if actor_id not in ["char_a", "char_b"]:
		return
	var semantic_action := str(payload.get("semantic_action_id", ""))
	agent_intents[actor_id] = semantic_action
	state_changed.emit()
	if semantic_action == "action:melee.unarmed_punch":
		request_attack(actor_id, "street_bandage", "", {}, semantic_action)


func _append_event(message: String) -> void:
	event_feed.push_front(message)
	if event_feed.size() > 6:
		event_feed.resize(6)
	state_changed.emit()


func _digest_text(value: String) -> String:
	return "sha256:" + value.sha256_text()


func _digest_dictionary(value: Dictionary) -> String:
	return _digest_text(JSON.stringify(value))


func _digest_contact_evidence(contact_ref: String, attempt_id: String, physics_tick: int, marker_id: String, actor_ref: String, target_ref: String) -> String:
	var canonical := "street-contact-evidence:v1|ref=%s|attempt=%s|tick=%s|marker=%s|actor=%s|target=%s" % [contact_ref, attempt_id, physics_tick, marker_id, actor_ref, target_ref]
	return _digest_text(canonical)
