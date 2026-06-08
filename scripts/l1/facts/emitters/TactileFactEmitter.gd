extends Node

const RAW_FACT_EMITTER := preload("res://scripts/l1/facts/RawFactEmitter.gd")
const FACT_ENVELOPE_BUILDER := preload("res://scripts/l1/facts/FactEnvelopeBuilder.gd")

@export var actor_id := "char_c"
@export var room_id := "room_demo"
@export var scene_id := "scene_demo"
@export var zone_id := "zone_focus"

var _raw_fact_emitter
var _fact_envelope_builder = FACT_ENVELOPE_BUILDER.new()


func emit_contact_fact(target_actor_id: String = "", target_object_id: String = "", intensity_band: String = "light", producer_ts: int = -1) -> bool:
	if actor_id == "":
		return false
	if target_actor_id == "" and target_object_id == "":
		return false

	var payload := _fact_envelope_builder.build_raw_fact_payload(
		"tactile_fact",
		"contact_started",
		"surface_contact",
		room_id,
		scene_id,
		zone_id,
		actor_id,
		"",
		"",
		target_actor_id,
		target_object_id,
		"",
		"godot.raw_fact_emitter",
		"L1",
		{
			"state_after": intensity_band,
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
		"phase0_tactile_fact_emitter",
		"phase0_tactile_fact_emitter:contact_started:%s" % intensity_band
	)


func _get_raw_fact_emitter():
	if _raw_fact_emitter == null:
		_raw_fact_emitter = RAW_FACT_EMITTER.new(self)
	return _raw_fact_emitter
