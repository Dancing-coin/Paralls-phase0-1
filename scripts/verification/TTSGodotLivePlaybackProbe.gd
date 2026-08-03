extends SceneTree

const SpatialVoiceControllerRef = preload("res://scripts/audio/SpatialVoiceController.gd")
const BACKEND_URL := "ws://127.0.0.1:8000/ws"
const TIMEOUT_MS := 60000

var socket := WebSocketPeer.new()
var voice: AudioStreamPlayer3D
var submitted := false
var deadline_ms := 0
var last_socket_state := -1
var expected_actor_id := ""
var expected_voice_id := ""
var evidence_run_id := ""


func _initialize() -> void:
	expected_actor_id = _argument_value("--actor-id")
	expected_voice_id = _argument_value("--expected-voice-id")
	evidence_run_id = _argument_value("--evidence-run-id")
	if expected_actor_id.is_empty() or expected_voice_id.is_empty() or evidence_run_id.is_empty():
		_finish_failure("missing_probe_arguments")
		return
	voice = SpatialVoiceControllerRef.new()
	root.add_child(voice)
	socket.inbound_buffer_size = 1024 * 1024
	deadline_ms = Time.get_ticks_msec() + TIMEOUT_MS
	var connection_error := socket.connect_to_url(BACKEND_URL)
	if connection_error != OK:
		_finish_failure("connect_failed")
		return
	process_frame.connect(_tick)


func _tick() -> void:
	if Time.get_ticks_msec() > deadline_ms:
		_finish_failure("timeout")
		return
	socket.poll()
	var socket_state := socket.get_ready_state()
	if socket_state != last_socket_state:
		last_socket_state = socket_state
		print("tts_godot_probe_socket_state:%s" % socket_state)
	if socket_state == WebSocketPeer.STATE_OPEN and not submitted:
		_submit_dialogue()
	while socket.get_available_packet_count() > 0:
		_handle_message(socket.get_packet().get_string_from_utf8())


func _submit_dialogue() -> void:
	submitted = true
	print("tts_godot_probe_dialogue_submitted")
	var envelope := {
		"message_type": "player_input",
		"payload": {
			"player_id": "tts_godot_live_probe",
			"room_id": "room_demo",
			"scene_id": "scene_demo",
			"zone_id": "zone_focus",
		"actor_id": "char_c",
			"intent_type": "dialogue_submit",
			"producer_ts": Time.get_ticks_msec(),
			"target_actor_id": expected_actor_id,
			"content": "Please confirm the voice link.",
		},
	}
	if socket.send_text(JSON.stringify(envelope)) != OK:
		_finish_failure("submit_failed")


func _handle_message(raw: String) -> void:
	var parsed: Variant = JSON.parse_string(raw)
	if not (parsed is Dictionary):
		return
	var envelope := parsed as Dictionary
	if str(envelope.get("message_type", "")) != "dialogue_response":
		return
	print("tts_godot_probe_dialogue_response_received")
	var raw_payload: Variant = envelope.get("payload", {})
	if not (raw_payload is Dictionary):
		_finish_failure("missing_dialogue_payload")
		return
	var payload := raw_payload as Dictionary
	if str(payload.get("actor_id", "")) != expected_actor_id:
		_finish_failure("unexpected_response_actor")
		return
	var raw_audio: Variant = payload.get("audio", {})
	if not (raw_audio is Dictionary):
		_finish_failure("missing_audio_payload")
		return
	var audio := raw_audio as Dictionary
	if (
		str(audio.get("mode", "")) != "clip"
		or str(audio.get("provider", "")) != "dashscope_http"
		or str(audio.get("voice_id", "")) != expected_voice_id
	):
		_finish_failure("expected_dashscope_clip")
		return
	voice.play_voice(payload)
	var stream: AudioStream = voice.stream
	if not (stream is AudioStreamWAV):
		_finish_failure("controller_rejected_clip")
		return
	var wav := stream as AudioStreamWAV
	print(
		"tts_godot_playback_verified:actor=%s:provider=%s:sample_rate_hz=%s:channels=%s:playing=%s" % [
			expected_actor_id,
			str(audio.get("provider", "")),
			wav.mix_rate,
			1 if not wav.stereo else 2,
			str(voice.playing),
		]
	)
	quit(0)


func _finish_failure(reason: String) -> void:
	print("tts_godot_playback_failed:%s" % reason)
	quit(1)


func _argument_value(flag: String) -> String:
	var arguments := OS.get_cmdline_user_args()
	for index in range(arguments.size() - 1):
		if str(arguments[index]) == flag:
			return str(arguments[index + 1])
	return ""
