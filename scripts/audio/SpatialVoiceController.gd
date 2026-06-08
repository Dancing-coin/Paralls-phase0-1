extends AudioStreamPlayer3D

@export_node_path("Node") var auditory_fact_emitter_path := NodePath("/root/MainDemo/VisualFactEmitter/AuditoryFactEmitter")

func play_stub_voice(_payload: Dictionary) -> void:
    unit_size = 3.0
    max_distance = 15.0
    _emit_auditory_fact(_payload)
    _bus_log("voice_stub_played:%s" % str(_payload.get("actor_id", "")))

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
