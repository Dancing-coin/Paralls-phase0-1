extends Node

const VerificationPaths := preload("res://scripts/verification/VerificationPaths.gd")

const MIRROR_BRIDGE := preload("res://scripts/interaction/GameplayMirrorBridge.gd")
const MIRROR_CONSUMER := preload("res://scripts/interaction/GameplayRuntimeStateMirrorConsumer.gd")
const ADVISORY_CONSUMER := preload("res://scripts/interaction/GovernmentDroughtAdvisoryPresentationConsumer.gd")
const POPULATION_PRESENTER := preload("res://scripts/phase0/PopulationPresenter.gd")

var _near_swap_peaks: Dictionary = {}


func _ready() -> void:
	if VerificationPaths.resolve(".harness/verification/.context-check").is_empty():
		get_tree().quit(1)
		return
	call_deferred("_run_probe")


func _run_probe() -> void:
	var bridge = MIRROR_BRIDGE.new()
	var consumer = MIRROR_CONSUMER.new()
	var advisory_consumer = ADVISORY_CONSUMER.new()
	add_child(bridge)
	add_child(consumer)
	add_child(advisory_consumer)
	bridge.register_consumer("actor:visible", consumer)
	bridge.register_government_drought_advisory_consumer("jurisdiction:visible", advisory_consumer)
	var bus := get_node_or_null("/root/LocalPresentationBus")
	var ok := bus != null and bridge.bind_session() == ERR_UNCONFIGURED
	if bus:
		bus.emit_signal("websocket_session_bound_received", {
			"session_ref": "ws_session:probe",
			"connection_epoch": 1,
			"allowed_actor_refs": ["actor:visible"],
			"allowed_government_drought_advisory_jurisdiction_refs": ["jurisdiction:visible"],
		})
		bus.emit_signal("gameplay_runtime_state_projection_received", _projection("actor:hidden", "facade:hidden"))
		ok = ok and consumer.accepted_projection_count == 0
		bus.emit_signal("gameplay_runtime_state_projection_received", _projection("actor:visible", "facade:visible"))
		ok = ok and consumer.accepted_projection_count == 1
		ok = ok and consumer.actor_ref == "actor:visible"
		ok = ok and consumer.visible_groups.get("core.resources", {}).get("payload", {}).get("current", 0) == 7
		bus.emit_signal("government_drought_advisory_projection_received", _advisory_projection("jurisdiction:hidden"))
		ok = ok and advisory_consumer.accepted_projection_count == 0
		bus.emit_signal("government_drought_advisory_projection_received", _advisory_projection("jurisdiction:visible"))
		ok = ok and advisory_consumer.accepted_projection_count == 1
		ok = ok and advisory_consumer.advisory_refs == ["advisory:drought:visible"]
		bus.emit_signal("government_drought_advisory_delivery_received", _advisory_delivery("jurisdiction:visible", 1, 1))
		ok = ok and advisory_consumer.last_delivery_sequence == 1
		bus.emit_signal("backend_disconnected", 1006)
		ok = ok and consumer.actor_ref.is_empty()
		ok = ok and consumer.visible_groups.is_empty()
		ok = ok and advisory_consumer.jurisdiction_ref.is_empty()
		ok = ok and advisory_consumer.advisory_refs.is_empty()
		ok = ok and not bridge.has_pending_enrollment()
		ok = ok and bridge.bind_session() == ERR_UNCONFIGURED
	var delivery_consumer = MIRROR_CONSUMER.new()
	var first_delivery := delivery_consumer.consume_delivery(_delivery(2, 1, "snapshot", "facade:delivery:1"))
	var duplicate_delivery := delivery_consumer.consume_delivery(_delivery(2, 1, "snapshot", "facade:delivery:1"))
	var next_epoch := delivery_consumer.consume_delivery(_delivery(3, 1, "snapshot", "facade:delivery:2"))
	var stale_epoch := delivery_consumer.consume_delivery(_delivery(2, 2, "snapshot", "facade:delivery:stale"))
	var forward_gap := delivery_consumer.consume_delivery(_delivery(3, 3, "snapshot", "facade:delivery:gap"))
	var delta_consumer = MIRROR_CONSUMER.new()
	var base_less_delta := delta_consumer.consume_delivery(_delivery(1, 1, "delta", "facade:delta"))
	var applied_delta_consumer = MIRROR_CONSUMER.new()
	var vectors: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://scripts/verification/fixtures/gameplay-mirror-checksum-vectors.json"))
	var base_projection: Dictionary = vectors["base"]
	var base_snapshot := applied_delta_consumer.consume_delivery(_wrap_projection(base_projection, 1, 1, "snapshot"))
	var applied_delta := applied_delta_consumer.consume_delivery(_wrap_projection(vectors["delta"], 1, 2, "delta"))
	ok = ok and _verify_checksum_failures(vectors)
	ok = ok and _verify_prediction_projection_boundary(vectors)
	ok = ok and _verify_connection_sequence()
	ok = ok and _verify_population_public_boundary()
	ok = ok and _verify_population_near_swap()
	ok = ok and _verify_packet_observation()
	ok = ok and bool(first_delivery.get("accepted", false))
	ok = ok and duplicate_delivery.get("error_code", "") == "mirror_sequence_duplicate"
	ok = ok and bool(next_epoch.get("accepted", false))
	ok = ok and stale_epoch.get("error_code", "") == "mirror_sequence_stale"
	ok = ok and forward_gap.get("error_code", "") == "mirror_sequence_gap"
	ok = ok and delivery_consumer.resync_required
	ok = ok and base_less_delta.get("error_code", "") == "mirror_delta_base_required"
	ok = ok and bool(base_snapshot.get("accepted", false))
	ok = ok and bool(applied_delta.get("accepted", false))
	ok = ok and applied_delta_consumer.facade_revision == str(vectors["target"]["facade_revision"])
	ok = ok and applied_delta_consumer.visible_groups.has("core.status") and not applied_delta_consumer.visible_groups.has("core.resources")
	var report := {
		"status": "godot-runtime-gameplay-mirror-bridge-verified" if ok else "godot-runtime-gameplay-mirror-bridge-failed",
		"accepted_projection_count": consumer.accepted_projection_count,
		"actor_ref_after_disconnect": consumer.actor_ref,
		"visible_groups_after_disconnect": consumer.visible_groups,
		"advisory_refs_after_disconnect": advisory_consumer.advisory_refs,
		"near_swap_peaks": _near_swap_peaks,
	}
	var artifact := _write_json(".harness/verification/gameplay-mirror-bridge-godot-runtime.json", report)
	print("gameplay_mirror_bridge_probe:artifact=%s" % artifact)
	print("gameplay_mirror_bridge_probe:verified=%s" % str(ok).to_lower())
	get_tree().quit(0 if ok else 1)


func _projection(actor_ref: String, facade_revision: String) -> Dictionary:
	var body := {
		"actor_ref": actor_ref, "facade_revision": facade_revision,
		"source_revision_vector": {}, "schema_capabilities": ["gameplay_runtime_state.godot.v1"],
		"enabled_state_groups": ["core.resources"],
		"groups": {"core.resources": {
			"definition_version": "1", "projection_schema_version": 1,
			"projection_revision": facade_revision, "source_revision_vector": {},
			"payload": {"current": 7},
		}},
	}
	var canonical := JSON.stringify(body, "", true, true)
	# 与真实网络 JSON 解析一致，避免 probe 自己混用 int/float Variant。
	var projection: Dictionary = JSON.parse_string(canonical)
	projection["projection_kind"] = "gameplay_runtime_state.godot.v1"
	projection["snapshot_checksum"] = "sha256:" + canonical.sha256_text()
	projection["canonical_snapshot_json"] = canonical
	return projection


func _delivery(epoch: int, sequence: int, delivery_kind: String, facade_revision: String) -> Dictionary:
	return _wrap_projection(_projection("actor:visible", facade_revision), epoch, sequence, delivery_kind)


func _wrap_projection(projection: Dictionary, epoch: int, sequence: int, kind: String) -> Dictionary:
	var delivery := {
		"delivery_kind": kind, "connection_epoch": epoch, "delivery_sequence": sequence,
		"actor_ref": projection["actor_ref"], "projection_schema": projection["projection_kind"],
		"facade_revision": projection["facade_revision"],
		"source_revision_vector": projection["source_revision_vector"], "payload": projection,
	}
	if kind == "delta":
		for key: String in ["base_facade_revision", "base_snapshot_checksum", "target_snapshot_checksum"]:
			delivery[key] = projection.get(key, "")
	return delivery


func _verify_checksum_failures(vectors: Dictionary) -> bool:
	var consumer = MIRROR_CONSUMER.new()
	add_child(consumer)
	if not bool(consumer.consume_projection(vectors["base"]).get("accepted", false)):
		return false
	var before := consumer.visible_groups.duplicate(true)
	var checksum: String = consumer.snapshot_checksum
	var accepted: int = consumer.accepted_projection_count
	var revision: String = consumer.facade_revision
	consumer.begin_stamina_prediction("p:base", "c:base", -1)
	var predictions: Dictionary = consumer.pending_predictions.duplicate(true)
	var traces: Array = consumer.prediction_resolution_trace.duplicate(true)
	var duplicate := consumer.consume_projection(vectors["base"])
	if not bool(duplicate.get("replayed", false)) or consumer.accepted_projection_count != accepted:
		return false
	for mutation: String in ["payload", "canonical", "metadata", "overlap", "prediction", "outer_actor", "inner_base_revision", "inner_base_checksum", "missing_base_revision", "missing_base_checksum"]:
		var delta: Dictionary = vectors["delta"].duplicate(true)
		var delivery := _wrap_projection(delta, 1, 1, "delta")
		match mutation:
			"payload":
				delta["groups"]["core.status"]["payload"]["current"] = 999
			"canonical":
				delta["canonical_snapshot_json"] += " "
			"metadata":
				delta["groups"]["core.status"]["definition_version"] = "forged"
			"overlap":
				delta["removed_group_ids"].append("core.status")
			"prediction":
				delivery["prediction_resolutions"] = [{"prediction_id": "missing", "command_id": "missing", "resolution": "confirmed", "transaction_id": "tx"}]
			"outer_actor":
				delivery["actor_ref"] = "actor:other"
			"inner_base_revision":
				delta["base_facade_revision"] = "facade:wrong"
			"inner_base_checksum":
				delta["base_snapshot_checksum"] = "sha256:wrong"
			"missing_base_revision":
				delta.erase("base_facade_revision")
			"missing_base_checksum":
				delta.erase("base_snapshot_checksum")
		consumer.resync_required = false
		if bool(consumer.consume_validated_delivery(delivery).get("accepted", false)):
			return false
		if consumer.visible_groups != before or consumer.snapshot_checksum != checksum or consumer.facade_revision != revision or consumer.accepted_projection_count != accepted or consumer.pending_predictions != predictions or consumer.prediction_resolution_trace != traces:
			return false
	consumer.resync_required = false
	var result := consumer.consume_validated_delivery(_wrap_projection(vectors["delta"], 1, 2, "delta"))
	var passed := bool(result.get("accepted", false)) and consumer.snapshot_checksum == str(vectors["target"]["snapshot_checksum"])
	consumer.queue_free()
	return passed


func _verify_prediction_projection_boundary(vectors: Dictionary) -> bool:
	var consumer = MIRROR_CONSUMER.new()
	add_child(consumer)
	if not bool(consumer.consume_projection(vectors["base"]).get("accepted", false)):
		return false
	consumer.begin_stamina_prediction("p:confirm", "c:confirm", -1)
	var groups: Dictionary = consumer.visible_groups.duplicate(true)
	var predictions: Dictionary = consumer.pending_predictions.duplicate(true)
	var traces: Array = consumer.prediction_resolution_trace.duplicate(true)
	var revision: String = consumer.facade_revision
	var checksum: String = consumer.snapshot_checksum
	var accepted: int = consumer.accepted_projection_count
	var resolutions := [{"prediction_id": "p:confirm", "command_id": "c:confirm", "resolution": "confirmed", "transaction_id": "tx:confirm"}]
	var base_replay := _wrap_projection(vectors["base"], 1, 1, "snapshot")
	base_replay["prediction_resolutions"] = resolutions
	var rejected := consumer.consume_validated_delivery(base_replay)
	if rejected.get("error_code", "") != "prediction_confirmation_projection_required":
		return false
	if consumer.visible_groups != groups or consumer.facade_revision != revision or consumer.snapshot_checksum != checksum or consumer.accepted_projection_count != accepted or consumer.pending_predictions != predictions or consumer.prediction_resolution_trace != traces:
		return false
	# 新权威投影可先到，随后相同投影的 replay 携带确认仍应清理旧 base overlay。
	if not bool(consumer.consume_projection(vectors["target"]).get("accepted", false)):
		return false
	var target_replay := _wrap_projection(vectors["target"], 1, 2, "snapshot")
	target_replay["prediction_resolutions"] = resolutions
	var confirmed := consumer.consume_validated_delivery(target_replay)
	if not bool(confirmed.get("accepted", false)) or not bool(confirmed.get("replayed", false)) or not consumer.pending_predictions.is_empty() or consumer.prediction_resolution_trace.size() != 1 or consumer.accepted_projection_count != accepted + 1:
		return false
	# 新 target 与确认同包到达也保持有效。
	consumer.clear_projection()
	consumer.consume_projection(vectors["base"])
	consumer.begin_stamina_prediction("p:confirm", "c:confirm", -1)
	var target_delivery := _wrap_projection(vectors["delta"], 1, 3, "delta")
	target_delivery["prediction_resolutions"] = resolutions
	var together := consumer.consume_validated_delivery(target_delivery)
	var passed := bool(together.get("accepted", false)) and consumer.pending_predictions.is_empty() and consumer.prediction_resolution_trace.size() == 1
	consumer.queue_free()
	return passed


func _verify_connection_sequence() -> bool:
	var bridge = MIRROR_BRIDGE.new()
	var first = MIRROR_CONSUMER.new()
	var second = MIRROR_CONSUMER.new()
	var government = ADVISORY_CONSUMER.new()
	for node: Node in [bridge, first, second, government]:
		add_child(node)
	var displayed: Dictionary = {}
	bridge.projection_applied.connect(func(actor: String, snapshot: Dictionary): displayed[actor] = snapshot)
	bridge.projection_removed.connect(func(actor: String): displayed.erase(actor))
	bridge.register_consumer("actor:a", first)
	bridge.register_consumer("actor:b", second)
	bridge.register_government_drought_advisory_consumer("jurisdiction:visible", government)
	var binding := {"session_ref": "ws_session:mixed", "connection_epoch": 1,
		"allowed_actor_refs": ["actor:a", "actor:b"],
		"allowed_government_drought_advisory_jurisdiction_refs": ["jurisdiction:visible"]}
	bridge._on_session_bound(binding)
	bridge._on_delivery(_wrap_projection(_projection("actor:a", "a:1"), 1, 1, "snapshot"))
	bridge._on_delivery(_wrap_projection(_projection("actor:b", "b:1"), 1, 2, "snapshot"))
	bridge._on_delivery(_wrap_projection(_projection("actor:a", "a:2"), 1, 3, "snapshot"))
	bridge._on_government_drought_advisory_delivery(_advisory_delivery("jurisdiction:visible", 1, 4))
	var fifth := _wrap_projection(_projection("actor:b", "b:2"), 1, 5, "snapshot")
	bridge._on_delivery(fifth)
	if first.accepted_projection_count != 2 or second.accepted_projection_count != 2 or government.last_delivery_sequence != 4 or bridge.connection_gap_count != 0:
		return false
	bridge._on_delivery(fifth)
	bridge._on_delivery(_wrap_projection(_projection("actor:a", "forged:epoch"), 2, 1, "snapshot"))
	if first.facade_revision != "a:2" or second.accepted_projection_count != 2:
		return false
	bridge.unregister_consumer("actor:b")
	bridge._on_delivery(_wrap_projection(_projection("actor:b", "b:inflight"), 1, 6, "snapshot"))
	bridge._on_delivery(_wrap_projection(_projection("actor:a", "a:3"), 1, 7, "snapshot"))
	if not second.visible_groups.is_empty() or first.facade_revision != "a:3" or bridge.connection_gap_count != 0:
		return false
	bridge.register_consumer("actor:b", second)
	bridge._on_delivery(_wrap_projection(_projection("actor:b", "b:3"), 1, 8, "snapshot"))
	bridge._on_delivery(_wrap_projection(_projection("actor:a", "a:gap"), 1, 10, "snapshot"))
	if not first.resync_required or not second.resync_required or bridge.connection_gap_count != 1:
		return false
	bridge._on_delivery(_wrap_projection(_projection("actor:a", "a:delta"), 1, 11, "delta"))
	if first.facade_revision != "a:3":
		return false
	bridge._on_delivery(_wrap_projection(_projection("actor:a", "a:recovered"), 1, 12, "snapshot"))
	bridge._on_projection(_projection("actor:b", "b:raw"))
	if first.resync_required or not second.resync_required or second.facade_revision != "b:3":
		return false
	bridge._on_delivery(_wrap_projection(_projection("actor:b", "b:recovered"), 1, 13, "snapshot"))
	if second.resync_required:
		return false
	# 新 epoch 只由 bound 建立，旧 epoch 的在途消息不能污染新基线。
	if displayed.size() != 2:
		return false
	binding["connection_epoch"] = 2
	binding["session_ref"] = "ws_session:mixed:new"
	bridge._on_session_bound(binding)
	if not displayed.is_empty() or bridge._consumers_by_actor.get("actor:a") != first or bridge._consumers_by_actor.get("actor:b") != second:
		return false
	bridge._on_delivery(_wrap_projection(_projection("actor:a", "a:late"), 1, 14, "snapshot"))
	if not first.visible_groups.is_empty():
		return false
	bridge._on_delivery(_wrap_projection(_projection("actor:a", "a:new"), 2, 1, "snapshot"))
	if first.facade_revision != "a:new" or displayed.size() != 1 or not displayed.has("actor:a"):
		return false
	bridge._on_session_revoked({})
	bridge._on_delivery(_wrap_projection(_projection("actor:a", "a:revoked"), 2, 2, "snapshot"))
	if not first.visible_groups.is_empty() or not bridge._consumers_by_actor.is_empty():
		return false
	# 注册上限与 backend 活动订阅一致，不为万人人口创建万个 consumer。
	for index: int in range(160):
		var consumer = MIRROR_CONSUMER.new()
		add_child(consumer)
		if bridge.register_consumer("actor:limit:%d" % index, consumer) != OK:
			return false
	if bridge.register_consumer("actor:overflow", first) != ERR_OUT_OF_MEMORY:
		return false
	bridge._on_backend_disconnected(1000)
	for node: Node in [bridge, first, second, government]:
		node.queue_free()
	return true


func _verify_population_public_boundary() -> bool:
	var vectors: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://scripts/verification/fixtures/population-mirror-vectors.json"))
	var consumer = MIRROR_CONSUMER.new()
	var presenter = POPULATION_PRESENTER.new()
	add_child(consumer)
	add_child(presenter)
	if not bool(consumer.consume_projection(vectors["base"]).get("accepted", false)):
		return false
	presenter.set_population(JSON.parse_string(vectors["base"]["canonical_snapshot_json"]))
	var before: Dictionary = consumer.visible_groups.duplicate(true)
	var checksum: String = consumer.snapshot_checksum
	# 重新计算外层hash，证明领域校验本身挡住非法公开字段，而非只被checksum挡住。
	for mutation: String in ["extra", "missing", "actor", "tick", "position", "animation", "digest"]:
		var payload: Dictionary = vectors["target"].duplicate(true)
		var body: Dictionary = JSON.parse_string(payload["canonical_snapshot_json"])
		var public: Dictionary = body["groups"]["population_public"]["payload"]
		match mutation:
			"extra": public["hidden_need"] = 1
			"missing": public.erase("public_digest")
			"actor": public["actor_id"] = "outsider"
			"tick": public["confirmed_tick"] = -1
			"position": public["presentation_position"] = [0, 1]
			"animation": public["animation_tag"] = "unknown"
			"digest": public["public_digest"] = "unknown"
		var canonical := JSON.stringify(body, "", true, true)
		for key: String in body:
			payload[key] = body[key]
		payload["canonical_snapshot_json"] = canonical
		payload["snapshot_checksum"] = "sha256:" + canonical.sha256_text()
		if bool(consumer.consume_projection(payload).get("accepted", false)):
			return false
		if consumer.visible_groups != before or consumer.snapshot_checksum != checksum or presenter.applied_count != 1:
			return false
	if not bool(consumer.consume_validated_delivery(_wrap_projection(vectors["delta"], 1, 2, "delta")).get("accepted", false)):
		return false
	presenter.set_population(JSON.parse_string(vectors["target"]["canonical_snapshot_json"]))
	if presenter.latest_confirmed_tick != 60 or presenter.applied_count != 2:
		return false
	if not bool(consumer.consume_validated_delivery(_wrap_projection(vectors["remove_delta"], 1, 3, "delta")).get("accepted", false)):
		return false
	presenter.remove_actor("character:one")
	var passed: bool = consumer.visible_groups.is_empty() and presenter.counts()["active_marker_count"] == 0
	consumer.queue_free()
	presenter.queue_free()
	return passed


func _verify_packet_observation() -> bool:
	var backend := get_node("/root/BackendBridge")
	var observed: Array = []
	var receive := func(raw_text: String, packet_bytes: int): observed.append([raw_text, packet_bytes])
	backend.gameplay_mirror_packet_observed.connect(receive)
	var raw := "{  \"message_type\": \"gameplay_mirror_delivery\", \"payload\": {} }"
	backend._dispatch_message(raw, raw.to_utf8_buffer().size())
	backend._dispatch_message("{\"message_type\":\"private_probe\",\"payload\":{}}", 1)
	backend.gameplay_mirror_packet_observed.disconnect(receive)
	return observed == [[raw, raw.to_utf8_buffer().size()]]


func _advisory_projection(jurisdiction_ref: String) -> Dictionary:
	return {
		"projection_kind": "government_drought_advisory.project.v1",
		"jurisdiction_ref": jurisdiction_ref,
		"advisory_refs": ["advisory:drought:visible"],
		"source_revision_vector": {"gameplay:government:advisory:visible": 1},
		"projection_hash": "sha256:advisory-visible",
	}


func _advisory_delivery(jurisdiction_ref: String, epoch: int, sequence: int) -> Dictionary:
	var payload := _advisory_projection(jurisdiction_ref)
	payload["connection_epoch"] = epoch
	payload["delivery_sequence"] = sequence
	return payload


func _write_json(relative_path: String, payload: Dictionary) -> String:
	var path := VerificationPaths.resolve("res://" + relative_path)
	if path.is_empty():
		return ""
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return ""
	file.store_string(JSON.stringify(payload, "\t"))
	file.close()
	return path


func _verify_population_near_swap() -> bool:
	var presenter = POPULATION_PRESENTER.new()
	var camera := Camera3D.new()
	var previous_camera := get_viewport().get_camera_3d()
	add_child(presenter)
	presenter.set_process(false)
	add_child(camera)
	camera.make_current()
	var live_labels: Dictionary = {}
	var peaks := {"peak_labels": 0, "peak_meshes": 0}
	var sample_peak := func():
		var meshes := 0
		for marker: MeshInstance3D in presenter._markers.values():
			if marker.mesh == presenter._near_mesh:
				meshes += 1
		peaks["peak_labels"] = maxi(int(peaks["peak_labels"]), live_labels.size())
		peaks["peak_meshes"] = maxi(int(peaks["peak_meshes"]), meshes)
	var on_added := func(node: Node):
		if node is Label3D and presenter.is_ancestor_of(node):
			live_labels[node.get_instance_id()] = true
			sample_peak.call()
	var on_removed := func(node: Node):
		if live_labels.erase(node.get_instance_id()):
			sample_peak.call()
	get_tree().node_added.connect(on_added)
	get_tree().node_removed.connect(on_removed)
	for index: int in range(64):
		var actor := "actor:near:%d" % index
		presenter.set_population({"actor_ref": actor, "facade_revision": "near:1", "groups": {
			"population_public": {"payload": {"actor_id": actor, "confirmed_tick": 1,
				"presentation_position": [0.0 if index < 32 else 100.0, 0.0, float(index % 32) / 100.0], "animation_tag": "idle"}}}})
	camera.position = Vector3.ZERO
	presenter._process(0.0)
	var before: Array = presenter._near_labels.keys()
	camera.position = Vector3(100.0, 0.0, 0.0)
	presenter._process(0.0)
	var passed: bool = before.size() == 32 and live_labels.size() == 32 and presenter.counts()["near"] == 32 and int(peaks["peak_labels"]) == 32 and int(peaks["peak_meshes"]) == 32
	for actor: String in before:
		passed = passed and not presenter._near_labels.has(actor)
	_near_swap_peaks = peaks.duplicate(true)
	get_tree().node_added.disconnect(on_added)
	get_tree().node_removed.disconnect(on_removed)
	presenter.clear_population()
	remove_child(presenter)
	presenter.queue_free()
	remove_child(camera)
	camera.queue_free()
	if previous_camera != null:
		previous_camera.make_current()
	return passed
