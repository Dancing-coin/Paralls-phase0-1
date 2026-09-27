class_name CharacterPerformanceMonitor
extends RefCounted

const MAX_SAMPLES := 256
var samples: Array[Dictionary] = []

func record(stage: StringName, duration_us: int) -> void:
	samples.append({"stage": String(stage), "duration_us": duration_us})
	while samples.size() > MAX_SAMPLES:
		samples.pop_front()
