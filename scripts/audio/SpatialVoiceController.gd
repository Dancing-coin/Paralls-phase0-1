extends AudioStreamPlayer3D

@export_node_path("Node") var auditory_fact_emitter_path := NodePath("/root/MainDemo/VisualFactEmitter/AuditoryFactEmitter")

func play_voice(payload: Dictionary) -> void:
	var raw_audio: Variant = payload.get("audio", {})
	var audio: Dictionary = raw_audio if raw_audio is Dictionary else {}
	if str(audio.get("mode", "stub")) == "clip" and _play_wav_clip(audio):
		_emit_auditory_fact(payload)
		_bus_log("voice_clip_played:%s" % str(payload.get("actor_id", "")))
		return
	play_stub_voice(payload)

func play_stub_voice(_payload: Dictionary) -> void:
	unit_size = 3.0
	max_distance = 15.0
	_emit_auditory_fact(_payload)
	var marker := "voice_stub_played:%s" % str(_payload.get("actor_id", ""))
	print(marker)
	_bus_log(marker)

func _play_wav_clip(audio: Dictionary) -> bool:
	if str(audio.get("content_type", "")) != "audio/wav" or str(audio.get("encoding", "")) != "base64":
		_bus_log("voice_clip_rejected:unsupported_format")
		return false
	var encoded := str(audio.get("payload", ""))
	if encoded.is_empty():
		_bus_log("voice_clip_rejected:empty_payload")
		return false
	var wav_bytes := Marshalls.base64_to_raw(encoded)
	var clip := _decode_pcm_wav(wav_bytes)
	if clip == null:
		_bus_log("voice_clip_rejected:invalid_wav")
		return false
	stream = clip
	play()
	return true

func _decode_pcm_wav(wav_bytes: PackedByteArray) -> AudioStreamWAV:
	if wav_bytes.size() < 12 or _ascii_at(wav_bytes, 0, 4) != "RIFF" or _ascii_at(wav_bytes, 8, 4) != "WAVE":
		return null
	var offset := 12
	var sample_rate := 0
	var channels := 0
	var pcm_data := PackedByteArray()
	while offset + 8 <= wav_bytes.size():
		var chunk_id := _ascii_at(wav_bytes, offset, 4)
		var chunk_size := int(wav_bytes.decode_u32(offset + 4))
		var data_offset := offset + 8
		var data_end := data_offset + chunk_size
		if chunk_id == "data" and data_end > wav_bytes.size():
			# DashScope may retain a streaming size placeholder for a complete clip.
			data_end = wav_bytes.size()
		elif data_end > wav_bytes.size():
			return null
		if chunk_id == "fmt ":
			if chunk_size < 16 or wav_bytes.decode_u16(data_offset) != 1:
				return null
			channels = int(wav_bytes.decode_u16(data_offset + 2))
			sample_rate = int(wav_bytes.decode_u32(data_offset + 4))
			if wav_bytes.decode_u16(data_offset + 14) != 16:
				return null
		elif chunk_id == "data":
			pcm_data = wav_bytes.slice(data_offset, data_end)
		offset = data_end + (chunk_size % 2)
	if channels != 1 or sample_rate <= 0 or pcm_data.is_empty() or pcm_data.size() % 2 != 0:
		return null
	var clip := AudioStreamWAV.new()
	clip.format = AudioStreamWAV.FORMAT_16_BITS
	clip.mix_rate = sample_rate
	clip.stereo = false
	clip.data = pcm_data
	return clip

func _ascii_at(bytes: PackedByteArray, offset: int, length: int) -> String:
	return bytes.slice(offset, offset + length).get_string_from_ascii()

func _bus_log(message: String) -> void:
	var bus := get_node_or_null("/root/LocalPresentationBus")
	if bus and bus.has_method("log_debug"):
		bus.log_debug(message)

func _emit_auditory_fact(payload: Dictionary) -> void:
	var auditory_fact_emitter := _get_auditory_fact_emitter()
	if auditory_fact_emitter == null:
		return
	if not auditory_fact_emitter.has_method("emit_speaker_active"):
		return

	var actor_id := str(payload.get("actor_id", ""))
	var target_actor_id := str(payload.get("target_actor_id", ""))
	var tone := str(payload.get("tone", "neutral"))
	var speech_mode := _resolve_speech_mode(tone)
	var loudness_band := _resolve_loudness_band(speech_mode)
	auditory_fact_emitter.emit_speaker_active(
		actor_id,
		target_actor_id,
		speech_mode,
		loudness_band,
		"clear",
		"quiet",
		int(payload.get("producer_ts", -1)),
	)
	if auditory_fact_emitter.has_method("emit_auditory_reachability_changed"):
		auditory_fact_emitter.emit_auditory_reachability_changed(
			actor_id,
			target_actor_id,
			"clear",
			loudness_band,
			speech_mode,
			"quiet",
			int(payload.get("producer_ts", -1)),
		)
	if auditory_fact_emitter.has_method("emit_ambient_noise_changed"):
		auditory_fact_emitter.emit_ambient_noise_changed(
			actor_id,
			"quiet",
			loudness_band,
			speech_mode,
			"clear",
			int(payload.get("producer_ts", -1)),
		)

func _get_auditory_fact_emitter() -> Node:
	return get_node_or_null(auditory_fact_emitter_path)

func _resolve_speech_mode(tone: String) -> String:
	var normalized := tone.to_lower()
	if normalized.contains("whisper"):
		return "whisper"
	if normalized.contains("shout"):
		return "shout"
	return "normal"

func _resolve_loudness_band(speech_mode: String) -> String:
	match speech_mode:
		"whisper":
			return "low"
		"shout":
			return "high"
		_:
			return "medium"
