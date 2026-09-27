class_name CharacterAnimationDebugger
extends RefCounted

static func preview(profile_id: String, clip_id: String, time_s: float) -> Dictionary:
	return {"profile_id": profile_id, "clip_id": clip_id, "time_s": maxf(0.0, time_s), "presentation_only": true}
