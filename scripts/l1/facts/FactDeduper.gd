extends RefCounted

var _window_ms := 0
var _last_seen_by_key: Dictionary = {}


func _init(window_ms: int = 0) -> void:
	_window_ms = max(window_ms, 0)


func should_emit(envelope: Dictionary, explicit_key: String = "", now_ms: int = -1) -> bool:
	if _window_ms <= 0:
		return true

	var resolved_now_ms := now_ms if now_ms >= 0 else Time.get_ticks_msec()
	var key := explicit_key
	if key == "":
		key = JSON.stringify(envelope)

	_prune(resolved_now_ms)

	var last_seen_ms := int(_last_seen_by_key.get(key, -1))
	if last_seen_ms >= 0 and resolved_now_ms - last_seen_ms < _window_ms:
		return false

	_last_seen_by_key[key] = resolved_now_ms
	return true


func _prune(now_ms: int) -> void:
	if _last_seen_by_key.is_empty():
		return

	var stale_keys: Array[String] = []
	for key in _last_seen_by_key.keys():
		if now_ms - int(_last_seen_by_key[key]) >= _window_ms:
			stale_keys.append(String(key))

	for key in stale_keys:
		_last_seen_by_key.erase(key)
