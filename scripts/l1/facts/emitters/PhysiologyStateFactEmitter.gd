extends Node

const RAW_FACT_EMITTER := preload("res://scripts/l1/facts/RawFactEmitter.gd")
const FACT_ENVELOPE_BUILDER := preload("res://scripts/l1/facts/FactEnvelopeBuilder.gd")

@export var actor_id := "char_c"
@export var room_id := "room_demo"
@export var scene_id := "scene_demo"
@export var zone_id := "zone_focus"

var _raw_fact_emitter
var _fact_envelope_builder = FACT_ENVELOPE_BUILDER.new()


func emit_breathing_strain_fact(strain_band: String = "elevated", producer_ts: int = -1) -> bool:
	if actor_id == "":
		return false

	var payload := _fact_envelope_builder.build_raw_fact_payload(
		"physiology_state_fact",
		"breathing_strain_changed",
		"body_state_anomaly",
		room_id,
		scene_id,
		zone_id,
		actor_id,
		"",
		"",
		"",
		"",
		"",
		"godot.raw_fact_emitter",
		"L1",
		{
			"state_after": strain_band,
		},
		{},
		"pulse",
		"",
		null,
		"",
		"",
		producer_ts
	)
	return _get_raw_fact_emitter().emit_raw_fact(
		payload,
		"phase0_physiology_fact_emitter",
		"phase0_physiology_fact_emitter:breathing_strain_changed:%s" % strain_band
	)


func _get_raw_fact_emitter():
	if _raw_fact_emitter == null:
		_raw_fact_emitter = RAW_FACT_EMITTER.new(self)
	return _raw_fact_emitter
