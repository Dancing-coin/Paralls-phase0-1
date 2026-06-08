extends Node

const RAW_FACT_EMITTER := preload("res://scripts/l1/facts/RawFactEmitter.gd")
const FACT_ENVELOPE_BUILDER := preload("res://scripts/l1/facts/FactEnvelopeBuilder.gd")

@export var room_id := "room_demo"
@export var scene_id := "scene_demo"
@export var zone_id := "zone_focus"

var _raw_fact_emitter
var _fact_envelope_builder = FACT_ENVELOPE_BUILDER.new()


func emit_speaker_active(
	source_actor_id: String,
	target_actor_id: String = "",
	speech_mode: String = "normal",
	loudness_band: String = "medium",
	reachability: String = "clear",
	ambient_noise: String = "quiet",
	producer_ts: int = -1
) -> bool:
	if source_actor_id == "":
		return false

	var payload := _fact_envelope_builder.build_raw_fact_payload(
		"auditory_fact",
		"speaker_active",
		"speech_mode_changed",
		room_id,
		scene_id,
		zone_id,
		source_actor_id,
		"",
		"",
		target_actor_id,
		"",
		"",
		"godot.raw_fact_emitter",
		"L1",
		{},
		{"auditory": true},
		"pulse",
		"",
		null,
		"",
		"",
		producer_ts,
		{
			"loudness_band": loudness_band,
			"speech_mode": speech_mode,
			"reachability": reachability,
			"ambient_noise": ambient_noise,
		}
	)
	return _get_raw_fact_emitter().emit_raw_fact(
		payload,
		"phase0_auditory_fact_emitter",
		"phase0_auditory_fact_emitter:speaker_active:%s:%s" % [source_actor_id, speech_mode]
	)


func emit_auditory_reachability_changed(
	source_actor_id: String,
	target_actor_id: String = "",
	reachability: String = "clear",
	loudness_band: String = "medium",
	speech_mode: String = "normal",
	ambient_noise: String = "quiet",
	producer_ts: int = -1
) -> bool:
	if source_actor_id == "":
		return false

	var payload := _fact_envelope_builder.build_raw_fact_payload(
		"auditory_fact",
		"auditory_reachability_changed",
		"auditory_reachability_changed",
		room_id,
		scene_id,
		zone_id,
		source_actor_id,
		"",
		"",
		target_actor_id,
		"",
		"",
		"godot.raw_fact_emitter",
		"L1",
		{},
		{"auditory": true},
		"pulse",
		"",
		null,
		"",
		"",
		producer_ts,
		{
			"loudness_band": loudness_band,
			"speech_mode": speech_mode,
			"reachability": reachability,
			"ambient_noise": ambient_noise,
		}
	)
	return _get_raw_fact_emitter().emit_raw_fact(
		payload,
		"phase0_auditory_fact_emitter",
		"phase0_auditory_fact_emitter:auditory_reachability_changed:%s:%s" % [source_actor_id, reachability]
	)


func emit_ambient_noise_changed(
	source_actor_id: String,
	ambient_noise: String = "quiet",
	loudness_band: String = "low",
	speech_mode: String = "normal",
	reachability: String = "clear",
	producer_ts: int = -1
) -> bool:
	if source_actor_id == "":
		return false

	var payload := _fact_envelope_builder.build_raw_fact_payload(
		"auditory_fact",
		"ambient_noise_changed",
		"auditory_context_shift",
		room_id,
		scene_id,
		zone_id,
		source_actor_id,
		"",
		"",
		"",
		"",
		"",
		"godot.raw_fact_emitter",
		"L1",
		{},
		{"auditory": true},
		"pulse",
		"",
		null,
		"",
		"",
		producer_ts,
		{
			"loudness_band": loudness_band,
			"speech_mode": speech_mode,
			"reachability": reachability,
			"ambient_noise": ambient_noise,
		}
	)
	return _get_raw_fact_emitter().emit_raw_fact(
		payload,
		"phase0_auditory_fact_emitter",
		"phase0_auditory_fact_emitter:ambient_noise_changed:%s" % ambient_noise
	)


func _get_raw_fact_emitter():
	if _raw_fact_emitter == null:
		_raw_fact_emitter = RAW_FACT_EMITTER.new(self)
	return _raw_fact_emitter
