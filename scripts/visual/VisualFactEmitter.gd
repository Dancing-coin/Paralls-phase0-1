extends Node

const RAW_FACT_EMITTER := preload("res://scripts/l1/facts/RawFactEmitter.gd")
const FACT_ENVELOPE_BUILDER := preload("res://scripts/l1/facts/FactEnvelopeBuilder.gd")

@export var actor_id := "char_c"
@export var room_id := "room_demo"
@export var scene_id := "scene_demo"
@export var zone_id := "zone_focus"

var _raw_fact_emitter
var _fact_envelope_builder = FACT_ENVELOPE_BUILDER.new()

func emit_visual_fact(
	fact_type: String,
	relation_type: String,
	target_actor_id: String = "",
	target_object_id: String = "",
	target_environment_id: String = "",
	effect_kind: String = "pulse",
	subject_key: String = "",
	ttl_ms: Variant = null
) -> bool:
	var payload := _build_visual_fact_payload(
		fact_type,
		relation_type,
		target_actor_id,
		target_object_id,
		target_environment_id,
		-1,
		effect_kind,
		subject_key,
		ttl_ms
	)
	return _get_raw_fact_emitter().emit_raw_fact(
		payload,
		"phase0_visual_fact_emitter",
		"phase0_visual_fact_emitter:%s:%s" % [
			fact_type,
			relation_type,
		]
	)


func _get_raw_fact_emitter():
	if _raw_fact_emitter == null:
		_raw_fact_emitter = RAW_FACT_EMITTER.new(self)
	return _raw_fact_emitter


func _build_visual_fact_payload(
	fact_type: String,
	relation_type: String,
	target_actor_id: String = "",
	target_object_id: String = "",
	target_environment_id: String = "",
	producer_ts: int = -1,
	effect_kind: String = "pulse",
	subject_key: String = "",
	ttl_ms: Variant = null
) -> Dictionary:
	return _fact_envelope_builder.build_raw_fact_payload(
		"visual_fact",
		fact_type,
		relation_type,
		room_id,
		scene_id,
		zone_id,
		actor_id,
		"",
		"",
		target_actor_id,
		target_object_id,
		target_environment_id,
		"godot.raw_fact_emitter",
		"L1",
		{},
		{},
		effect_kind,
		subject_key,
		ttl_ms,
		"",
		"",
		producer_ts
	)
