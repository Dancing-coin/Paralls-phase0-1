extends Node

const RAW_FACT_EMITTER := preload("res://scripts/l1/facts/RawFactEmitter.gd")
const FACT_ENVELOPE_BUILDER := preload("res://scripts/l1/facts/FactEnvelopeBuilder.gd")

@export var actor_id := "char_c"
@export var room_id := "room_demo"
@export var scene_id := "scene_demo"
@export var zone_id := "zone_focus"

var _raw_fact_emitter
var _fact_envelope_builder = FACT_ENVELOPE_BUILDER.new()


func emit_actor_entered_zone(next_zone_id: String = "") -> bool:
	var resolved_zone_id := next_zone_id if next_zone_id != "" else zone_id
	if actor_id == "" or resolved_zone_id == "":
		return false

	return _emit_spatial_access_fact(
		"actor_entered_zone",
		"actor_entered_zone",
		resolved_zone_id,
		"",
		{},
		"phase0_spatial_access_fact:actor_entered_zone:%s" % resolved_zone_id
	)


func emit_actor_approached_actor(target_actor_id: String, distance_m: float = -1.0) -> bool:
	if actor_id == "" or target_actor_id == "":
		return false

	var world := {}
	if distance_m >= 0.0:
		world["distance_m"] = distance_m

	return _emit_spatial_access_fact(
		"actor_approached_actor",
		"actor_approached_actor",
		zone_id,
		target_actor_id,
		world,
		"phase0_spatial_access_fact:actor_approached_actor:%s" % target_actor_id
	)


func emit_privacy_boundary_changed(previous_band: String, next_band: String, next_zone_id: String = "") -> bool:
	var resolved_zone_id := next_zone_id if next_zone_id != "" else zone_id
	if actor_id == "" or resolved_zone_id == "":
		return false
	if next_band == "":
		return false
	if previous_band == next_band:
		return false

	return _emit_spatial_access_fact(
		"privacy_boundary_changed",
		"privacy_boundary_changed",
		resolved_zone_id,
		"",
		{
			"state_before": previous_band,
			"state_after": next_band,
		},
		"phase0_spatial_access_fact:privacy_boundary_changed:%s" % next_band
	)


func _get_raw_fact_emitter():
	if _raw_fact_emitter == null:
		_raw_fact_emitter = RAW_FACT_EMITTER.new(self)
	return _raw_fact_emitter


func _emit_spatial_access_fact(
	fact_type: String,
	relation_type: String,
	next_zone_id: String,
	target_actor_id: String,
	world: Dictionary,
	success_log: String
) -> bool:
	var payload := _fact_envelope_builder.build_raw_fact_payload(
		"spatial_access_fact",
		fact_type,
		relation_type,
		room_id,
		scene_id,
		next_zone_id,
		actor_id,
		"",
		"",
		target_actor_id,
		"",
		"",
		"godot.raw_fact_emitter",
		"L1",
		world,
		{},
		"",
		""
	)
	return _get_raw_fact_emitter().emit_raw_fact(
		payload,
		"phase0_spatial_access_fact_emitter",
		success_log
	)
