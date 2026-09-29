extends Node

## Samples root bone position tracks and emits a local delta exactly once per
## consumer call. It never writes CharacterBody3D transforms.

@export var enabled := true
@export var root_track_suffix := ":root.x"

var animation_player: AnimationPlayer
var _last_clip := ""
var _last_position := 0.0
var _pending_delta := Vector3.ZERO
var _consumption_serial := 0
var _last_consumption_token := ""

func bind(root: Node) -> void:
	animation_player = _find_descendant(root, "AnimationPlayer") as AnimationPlayer
	_last_clip = ""
	_last_position = 0.0
	_pending_delta = Vector3.ZERO

func _process(_delta: float) -> void:
	if not enabled or animation_player == null or not animation_player.is_playing():
		return
	var clip := animation_player.current_animation
	var position := animation_player.current_animation_position
	if clip != _last_clip:
		_last_clip = clip
		_last_position = position
		return
	var animation := animation_player.get_animation(clip)
	if animation == null:
		return
	var previous := _sample_root(animation, _last_position)
	var current := _sample_root(animation, position)
	var delta := current - previous
	if position < _last_position and animation.loop_mode != Animation.LOOP_NONE:
		var end_value := _sample_root(animation, animation.length)
		var start_value := _sample_root(animation, 0.0)
		delta = (end_value - previous) + (current - start_value)
	_pending_delta += delta
	_last_position = position

func sample_from_animation_player() -> Vector3:
	_process(0.0)
	return consume_delta()

func consume_delta() -> Vector3:
	_consumption_serial += 1
	var result := consume_delta_once(StringName("sampler:%s" % _consumption_serial))
	return result.get("root_delta_local", Vector3.ZERO)

func consume_delta_once(consumption_token: StringName = &"") -> Dictionary:
	var token := String(consumption_token)
	if token.is_empty():
		return {"accepted": false, "reason": "malformed_consumption_token", "root_delta_local": Vector3.ZERO}
	if token == _last_consumption_token:
		return {"accepted": false, "reason": "duplicate_consumption", "consumption_token": token, "root_delta_local": Vector3.ZERO}
	if not (_pending_delta is Vector3) or not is_finite(_pending_delta.x) or not is_finite(_pending_delta.y) or not is_finite(_pending_delta.z):
		_pending_delta = Vector3.ZERO
		return {"accepted": false, "reason": "malformed_root_delta", "consumption_token": token, "root_delta_local": Vector3.ZERO}
	_last_consumption_token = token
	var result := _pending_delta
	_pending_delta = Vector3.ZERO
	result.y = 0.0
	return {"accepted": true, "consumption_token": token, "root_delta_local": result}

func reset() -> void:
	_pending_delta = Vector3.ZERO
	_last_clip = ""
	_last_position = 0.0
	_last_consumption_token = ""

func has_root_track(clip_ref: String) -> bool:
	if animation_player == null:
		return false
	var animation := animation_player.get_animation(clip_ref)
	if animation == null:
		return false
	return _find_root_track(animation) >= 0

func _sample_root(animation: Animation, time: float) -> Vector3:
	var track := _find_root_track(animation)
	if track < 0:
		return Vector3.ZERO
	var value: Variant = animation.value_track_interpolate(track, clamp(time, 0.0, animation.length))
	return value as Vector3 if value is Vector3 else Vector3.ZERO

func _find_root_track(animation: Animation) -> int:
	for index in animation.get_track_count():
		if animation.track_get_type(index) != Animation.TYPE_POSITION_3D:
			continue
		var path := str(animation.track_get_path(index)).to_lower()
		if path.ends_with(root_track_suffix.to_lower()):
			return index
	return -1

func _find_descendant(node: Node, type_name: String) -> Node:
	for child in node.get_children():
		if child.is_class(type_name):
			return child
		var found := _find_descendant(child, type_name)
		if found != null:
			return found
	return null
